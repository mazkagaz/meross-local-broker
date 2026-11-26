// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { Component, NgZone, OnDestroy, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { Clipboard } from '@angular/cdk/clipboard';
import { MatDialog as MatDialog } from '@angular/material/dialog';
import { MatSnackBar as MatSnackBar } from '@angular/material/snack-bar';
import { of, Subject, Subscription } from 'rxjs';
import { catchError, debounceTime, distinctUntilChanged, switchMap } from 'rxjs/operators';

import {
  TuningAuditEntry,
  TuningCaptureStatus,
  TuningCommand,
  TuningCommandCatalog,
  TuningCommandPreview,
  TuningCommandResult,
  TuningDeviceState,
  TuningDeviceSummary,
  TuningImportResult,
  TuningPreviewResult,
  TuningProfileDetail,
  TuningProfileSummary,
  TuningReadResult,
  TuningValidation,
} from '@app/model/tuning';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { Download, TuningService, tuningErrorMessage } from './tuning.service';

interface ValidationInput {
  text: string;
  id: string | null;
}

@Component({
  selector: 'app-tuning',
  templateUrl: './tuning.component.html',
  styleUrls: ['./tuning.component.scss'],
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: false,
})
export class TuningComponent implements OnInit, OnDestroy {
  tabIndex = 0;
  revision = '';
  profiles: TuningProfileSummary[] = [];
  devices: TuningDeviceSummary[] = [];
  auditEntries: TuningAuditEntry[] = [];
  showAllProfiles = false;
  profileFilter = '';

  selectedProfileId: string | null = null;
  profile: TuningProfileDetail | null = null;
  yamlText = '';
  validation: TuningValidation | null = null;
  validationError = '';
  draftMode = false;
  busy = false;

  importFile: File | null = null;
  importPreview: TuningImportResult | null = null;

  selectedDeviceUuid: string | null = null;
  deviceState: TuningDeviceState | null = null;
  capture: TuningCaptureStatus | null = null;
  captureType = '';

  simNamespace = '';
  simMethod = 'PUSH';
  simPayload = '{\n  "channel": 0\n}';
  simChannels = '';
  simSubdeviceId = '';
  simSubdeviceType = '';
  previewResult: TuningPreviewResult | null = null;
  previewError = '';

  readNamespace = 'Appliance.System.All';
  readTimeoutMs = 6000;
  readResult: TuningReadResult | null = null;
  readError = '';

  commandCatalog: TuningCommandCatalog | null = null;
  commands: TuningCommand[] = [];
  commandChannel: { [key: string]: number } = {};
  commandValue: { [key: string]: number } = {};
  commandBusy = false;
  commandsNote = '';
  abilityBusy = false;

  entityColumns = ['key', 'platform', 'namespace', 'channel', 'commands'];

  private subscriptions = new Subscription();
  private validationInput = new Subject<ValidationInput>();
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  constructor(
    private tuning: TuningService,
    private dialog: MatDialog,
    private snackBar: MatSnackBar,
    private clipboard: Clipboard,
    private zone: NgZone
  ) {}

  ngOnInit(): void {
    this.showAllProfiles = localStorage.getItem('tuning-show-all-profiles') === '1';
    this.subscriptions.add(
      this.validationInput
        .pipe(
          debounceTime(600),
          distinctUntilChanged((a, b) => a.text === b.text && a.id === b.id),
          switchMap((input) => this.validateText(input))
        )
        .subscribe((result) => {
          this.validation = result;
          if (result && result.valid) {
            this.validationError = '';
          }
        })
    );
    this.loadAll();
    this.refreshCapture();
    this.zone.runOutsideAngular(() => {
      this.pollTimer = setInterval(() => this.zone.run(() => this.pollInventory()), 20000);
    });
  }

  ngOnDestroy(): void {
    if (this.pollTimer !== null) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    this.subscriptions.unsubscribe();
  }

  pollInventory(): void {
    this.loadProfiles();
    this.loadDevices();
  }

  loadAll(): void {
    this.loadProfiles();
    this.loadDevices();
    this.loadAudit();
  }

  loadProfiles(): void {
    this.subscriptions.add(
      this.tuning.listProfiles().subscribe(
        (result) => {
          this.revision = result.revision;
          this.profiles = result.profiles;
        },
        (error) => this.fail(error, 'Profiles')
      )
    );
  }

  loadDevices(): void {
    this.subscriptions.add(
      this.tuning.listDevices().subscribe(
        (devices) => {
          this.devices = devices;
          this.syncSelectedDeviceProfile();
        },
        (error) => this.fail(error, 'Devices')
      )
    );
  }

  loadAudit(): void {
    this.subscriptions.add(
      this.tuning.listAudit(200, this.selectedProfileId).subscribe(
        (entries) => (this.auditEntries = entries),
        (error) => this.fail(error, 'Audit')
      )
    );
  }

  get filteredProfiles(): TuningProfileSummary[] {
    const term = this.profileFilter.trim().toLowerCase();
    if (term) {
      return this.profiles.filter((item) => item.id.toLowerCase().includes(term));
    }
    if (this.showAllProfiles) {
      return this.profiles;
    }
    return this.profiles.filter((item) => item.devices_affected > 0);
  }

  get detectedProfileCount(): number {
    return this.profiles.filter((item) => item.devices_affected > 0).length;
  }

  persistShowAll(value: boolean): void {
    this.showAllProfiles = value;
    localStorage.setItem('tuning-show-all-profiles', value ? '1' : '0');
  }

  copyValue(value: string, label: string): void {
    if (!value) {
      return;
    }
    this.clipboard.copy(value);
    this.snackBar.open(`${label} copied.`, 'Dismiss', { duration: 2000 });
  }

  selectProfile(profileId: string): void {
    this.selectedProfileId = profileId;
    this.draftMode = false;
    this.busy = true;
    this.subscriptions.add(
      this.tuning.getProfile(profileId).subscribe(
        (profile) => {
          this.profile = profile;
          this.yamlText = profile.override_yaml || profile.yaml;
          this.validation = null;
          this.validationError = '';
          this.validationInput.next({ text: this.yamlText, id: profileId });
          this.loadAudit();
        },
        (error) => this.fail(error, 'Profile'),
        () => (this.busy = false)
      )
    );
  }

  onYamlChange(text: string): void {
    this.yamlText = text;
    if (text.trim()) {
      this.validationInput.next({ text, id: this.effectiveProfileId() });
    }
  }

  validateNow(): void {
    this.validationInput.next({
      text: this.yamlText,
      id: this.effectiveProfileId(),
    });
  }

  canApply(): boolean {
    return !!this.validation && this.validation.valid && !!this.validation.profile_id && !this.busy;
  }

  applyOverride(): void {
    const targetId = this.effectiveProfileId();
    if (!this.canApply() || !targetId) {
      this.snackBar.open('Validate the profile before applying it.', 'Dismiss', {
        duration: 4000,
      });
      return;
    }
    const expected = this.profile ? this.profile.override_hash || this.profile.catalog_hash : null;
    const impact = this.profile ? this.profile.devices_affected : 0;
    const message =
      `Apply the override for ${targetId}?\n\n` +
      `${impact} device(s) currently match this profile.\n` +
      `Revision expected: ${expected || 'new profile'}.\n\n` +
      (this.validation && this.validation.diff ? this.validation.diff : 'No textual difference from the current base.');
    this.confirm('Apply profile override', message, 'Apply').subscribe((ok) => {
      if (!ok) {
        return;
      }
      this.busy = true;
      this.subscriptions.add(
        this.tuning.saveOverride(targetId, this.yamlText, expected).subscribe(
          (result) => {
            this.snackBar.open(`Saved ${result.id} (revision ${result.revision}).`, 'Dismiss', { duration: 4000 });
            this.selectedProfileId = result.id;
            this.draftMode = false;
            this.loadProfiles();
            this.loadAudit();
            this.reloadProfile(result.id);
          },
          (error) => this.fail(error, 'Apply'),
          () => (this.busy = false)
        )
      );
    });
  }

  revertToBundled(): void {
    if (!this.profile || !this.profile.override_hash) {
      return;
    }
    const profileId = this.profile.id;
    this.confirm(
      'Revert to the bundled profile',
      `Remove the override for ${profileId}?\n\n` +
        `${this.profile.devices_affected} device(s) will use the bundled profile again.`,
      'Revert'
    ).subscribe((ok) => {
      if (!ok) {
        return;
      }
      this.busy = true;
      this.subscriptions.add(
        this.tuning.deleteOverride(profileId, this.profile.override_hash).subscribe(
          () => {
            this.snackBar.open(`Override removed for ${profileId}.`, 'Dismiss', {
              duration: 4000,
            });
            this.loadProfiles();
            this.loadAudit();
            this.reloadProfile(profileId);
          },
          (error) => this.fail(error, 'Revert'),
          () => (this.busy = false)
        )
      );
    });
  }

  restoreBackup(filename: string): void {
    if (!this.profile) {
      return;
    }
    const profileId = this.profile.id;
    this.confirm(
      'Restore a backup',
      `Restore ${filename} for ${profileId}? The current override is backed up first.`,
      'Restore'
    ).subscribe((ok) => {
      if (!ok) {
        return;
      }
      this.busy = true;
      this.subscriptions.add(
        this.tuning.restoreBackup(profileId, filename).subscribe(
          () => {
            this.snackBar.open(`Restored ${filename}.`, 'Dismiss', {
              duration: 4000,
            });
            this.loadProfiles();
            this.loadAudit();
            this.reloadProfile(profileId);
          },
          (error) => this.fail(error, 'Restore'),
          () => (this.busy = false)
        )
      );
    });
  }

  exportProfiles(format: string, source: string): void {
    const profileId = format === 'yaml' ? this.selectedProfileId : null;
    if (format === 'yaml' && !profileId) {
      return;
    }
    this.subscriptions.add(
      this.tuning.downloadProfiles(format, source, profileId).subscribe(
        (download) => this.saveDownload(download),
        (error) => this.fail(error, 'Export')
      )
    );
  }

  onImportFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files && input.files.length ? input.files[0] : null;
    input.value = '';
    if (!file) {
      return;
    }
    this.importFile = file;
    this.importPreview = null;
    this.subscriptions.add(
      this.tuning.importFile(file, true).subscribe(
        (preview) => {
          this.importPreview = preview;
          this.snackBar.open(`Import ready: ${preview.profiles.length} profile(s), dry run.`, 'Dismiss', {
            duration: 4000,
          });
        },
        (error) => this.fail(error, 'Import preview')
      )
    );
  }

  applyImport(): void {
    if (!this.importFile) {
      return;
    }
    this.confirm(
      'Apply import',
      `Apply ${this.importPreview ? this.importPreview.profiles.length : ''} ` +
        `profile(s) from ${this.importFile.name}? Existing overrides are backed up first.`,
      'Apply import'
    ).subscribe((ok) => {
      if (!ok) {
        return;
      }
      this.subscriptions.add(
        this.tuning.importFile(this.importFile, false).subscribe(
          (result) => {
            this.snackBar.open(
              `Imported ${result.profiles.length} profile(s), revision ${result.revision}.`,
              'Dismiss',
              { duration: 4000 }
            );
            this.importFile = null;
            this.importPreview = null;
            this.loadProfiles();
            this.loadAudit();
          },
          (error) => this.fail(error, 'Import')
        )
      );
    });
  }

  selectDevice(uuid: string): void {
    this.selectedDeviceUuid = uuid;
    this.previewResult = null;
    this.previewError = '';
    this.readResult = null;
    this.readError = '';
    this.subscriptions.add(
      this.tuning.deviceState(uuid).subscribe(
        (state) => {
          this.deviceState = state;
          this.captureType = state.device.type || '';
          this.readNamespace = 'Appliance.System.All';
          const polling = state.polling && state.polling.length ? state.polling[0] : null;
          this.simNamespace = polling ? polling.namespace : '';
          this.simMethod = 'PUSH';
          this.commands = [];
          this.commandCatalog = null;
          this.commandsNote = '';
          if (state.profile) {
            this.loadCommands(uuid);
          } else {
            this.commandsNote =
              'No profile matches this device. The broker requests the ability ' +
              'document from the device; reload once it has answered.';
          }
        },
        (error) => this.fail(error, 'Device state')
      )
    );
  }

  refreshCapture(): void {
    this.subscriptions.add(
      this.tuning.captureStatus().subscribe(
        (status) => (this.capture = status),
        (error) => this.fail(error, 'Capture')
      )
    );
  }

  startCapture(): void {
    if (!this.selectedDeviceUuid) {
      return;
    }
    this.subscriptions.add(
      this.tuning.captureStart(this.selectedDeviceUuid, this.captureType || null).subscribe(
        (status) => {
          this.capture = status;
          this.snackBar.open('Capture started.', 'Dismiss', { duration: 3000 });
        },
        (error) => this.fail(error, 'Capture')
      )
    );
  }

  stopCapture(): void {
    this.subscriptions.add(
      this.tuning.captureStop().subscribe(
        (status) => {
          this.capture = status;
          this.snackBar.open('Capture stopped.', 'Dismiss', { duration: 3000 });
        },
        (error) => this.fail(error, 'Capture')
      )
    );
  }

  draftCapture(): void {
    const type = this.deviceState ? this.deviceState.device.type : this.captureType;
    if (!type) {
      this.snackBar.open('Select a device first.', 'Dismiss', { duration: 3000 });
      return;
    }
    this.subscriptions.add(
      this.tuning.captureDraft(type).subscribe(
        (draft) => {
          this.selectedProfileId = null;
          this.profile = null;
          this.draftMode = true;
          this.yamlText = draft.yaml;
          this.validation = null;
          this.tabIndex = 0;
          this.validationInput.next({ text: draft.yaml, id: null });
          this.snackBar.open(`Draft from ${draft.frames} frame(s) injected into the editor.`, 'Dismiss', {
            duration: 4000,
          });
        },
        (error) => this.fail(error, 'Draft')
      )
    );
  }

  downloadCapture(): void {
    this.subscriptions.add(
      this.tuning.captureExport().subscribe(
        (download) => this.saveDownload(download),
        (error) => this.fail(error, 'Capture export')
      )
    );
  }

  preview(): void {
    const profileId =
      this.deviceState && this.deviceState.profile ? this.deviceState.profile.id : this.selectedProfileId;
    if (!profileId) {
      this.snackBar.open('No matched profile for this device.', 'Dismiss', {
        duration: 3000,
      });
      return;
    }
    let payload: unknown;
    try {
      payload = JSON.parse(this.simPayload || '{}');
    } catch (error) {
      this.snackBar.open('Payload is not valid JSON.', 'Dismiss', { duration: 4000 });
      return;
    }
    const body: { [key: string]: unknown } = {
      namespace: this.simNamespace,
      method: this.simMethod,
      payload,
    };
    const channels = this.simChannels
      .split(/[,\s]+/)
      .filter((value) => value.length)
      .map((value) => Number(value));
    if (channels.length) {
      body.channels = channels;
    }
    if (this.simSubdeviceId && this.simSubdeviceType) {
      body.subdevice = { id: this.simSubdeviceId, type: this.simSubdeviceType };
    }
    this.previewError = '';
    this.subscriptions.add(
      this.tuning.preview(profileId, body).subscribe(
        (result) => (this.previewResult = result),
        (error) => {
          this.previewResult = null;
          this.previewError = tuningErrorMessage(error);
        }
      )
    );
  }

  readNow(): void {
    if (!this.selectedDeviceUuid) {
      return;
    }
    this.readError = '';
    this.readResult = null;
    this.subscriptions.add(
      this.tuning
        .readDevice(this.selectedDeviceUuid, {
          namespace: this.readNamespace || undefined,
          timeout_ms: Number(this.readTimeoutMs) || 6000,
        })
        .subscribe(
          (result) => (this.readResult = result),
          (error) => (this.readError = tuningErrorMessage(error))
        )
    );
  }

  refreshAbility(): void {
    if (!this.selectedDeviceUuid || this.abilityBusy) {
      return;
    }
    this.abilityBusy = true;
    this.subscriptions.add(
      this.tuning.refreshAbility(this.selectedDeviceUuid).subscribe(
        (result) => {
          this.abilityBusy = false;
          this.snackBar.open(`Ability refreshed (${result.count} namespaces).`, 'Dismiss', { duration: 4000 });
          this.selectDevice(this.selectedDeviceUuid);
          this.loadProfiles();
          this.loadDevices();
        },
        (error) => {
          this.abilityBusy = false;
          this.fail(error, 'Ability');
        }
      )
    );
  }

  loadCommands(uuid: string): void {
    this.commandCatalog = null;
    this.commands = [];
    this.subscriptions.add(
      this.tuning.deviceCommands(uuid).subscribe(
        (catalog) => {
          this.commandCatalog = catalog;
          this.commands = catalog.commands;
          this.commandChannel = {};
          this.commandValue = {};
          for (const command of catalog.commands) {
            if (command.channels.length) {
              this.commandChannel[command.id] = command.channel !== null ? command.channel : command.channels[0];
            }
            if (command.accepts_value) {
              this.commandValue[command.id] = command.min !== null ? command.min : 0;
            }
          }
        },
        (error) => {
          if (error && error.status === 409) {
            this.commands = [];
            this.commandCatalog = null;
            this.commandsNote =
              'No profile matches this device. The broker requests the ability ' +
              'document from the device; reload once it has answered.';
          } else {
            this.fail(error, 'Commands');
          }
        }
      )
    );
  }

  runCommand(command: TuningCommand): void {
    if (!this.selectedDeviceUuid || this.commandBusy) {
      return;
    }
    const body: { [key: string]: unknown } = {};
    if (command.accepts_channel && command.channels.length) {
      body.channel = this.commandChannel[command.id];
    }
    if (command.accepts_value) {
      body.value = Number(this.commandValue[command.id]);
    }
    this.commandBusy = true;
    this.subscriptions.add(
      this.tuning.executeCommand(this.selectedDeviceUuid, command.id, body).subscribe(
        (response) => {
          const preview = response as TuningCommandPreview;
          this.confirm('Send device command', this.commandMessage(command, preview), 'Send command').subscribe((ok) => {
            if (!ok) {
              this.commandBusy = false;
              return;
            }
            this.subscriptions.add(
              this.tuning
                .executeCommand(this.selectedDeviceUuid, command.id, {
                  confirm: true,
                  token: preview.token,
                })
                .subscribe(
                  (result) => this.commandDone(command, result as TuningCommandResult),
                  (error) => {
                    this.commandBusy = false;
                    this.fail(error, 'Command');
                  }
                )
            );
          });
        },
        (error) => {
          this.commandBusy = false;
          this.fail(error, 'Command');
        }
      )
    );
  }

  diffLines(text: string | null): Array<{ text: string; cls: string }> {
    if (!text) {
      return [];
    }
    return text.split('\n').map((line) => {
      let cls = '';
      if (line.startsWith('@@')) {
        cls = 'hunk';
      } else if (line.startsWith('+') && !line.startsWith('+++')) {
        cls = 'add';
      } else if (line.startsWith('-') && !line.startsWith('---')) {
        cls = 'del';
      }
      return { text: line, cls };
    });
  }

  captureState(): string {
    if (!this.capture || !this.capture.session_id) {
      return 'idle';
    }
    if (this.capture.active) {
      return `active, ${this.capture.frames} frame(s)`;
    }
    return `stopped (${this.capture.reason || 'user'}), ${this.capture.frames} frame(s)`;
  }

  private effectiveProfileId(): string | null {
    return this.selectedProfileId || (this.validation && this.validation.profile_id) || null;
  }

  private validateText(input: ValidationInput) {
    this.validationError = '';
    return this.tuning.validate(input.text, input.id).pipe(
      catchError((error) => {
        this.validationError = tuningErrorMessage(error);
        return of(null);
      })
    );
  }

  private reloadProfile(profileId: string): void {
    this.subscriptions.add(
      this.tuning.getProfile(profileId).subscribe(
        (profile) => {
          this.profile = profile;
          this.yamlText = profile.override_yaml || profile.yaml;
          this.validation = null;
          this.validationInput.next({ text: this.yamlText, id: profileId });
        },
        (error) => this.fail(error, 'Profile')
      )
    );
  }

  private saveDownload(download: Download): void {
    const url = URL.createObjectURL(download.blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = download.filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  private syncSelectedDeviceProfile(): void {
    if (!this.selectedDeviceUuid) {
      return;
    }
    const row = this.devices.find((device) => device.uuid === this.selectedDeviceUuid);
    const listed = row && row.profile ? row.profile : null;
    const current = this.deviceState && this.deviceState.profile ? this.deviceState.profile.id : null;
    if (listed !== current) {
      this.selectDevice(this.selectedDeviceUuid);
    }
  }

  private commandMessage(command: TuningCommand, preview: TuningCommandPreview): string {
    const device = this.deviceState
      ? `${this.deviceState.device.name || this.deviceState.device.uuid} (${this.deviceState.device.uuid})`
      : '';
    const lines = [
      `${command.name || command.id} — ${command.id}`,
      `Device: ${device}`,
      `Namespace: ${preview.command.namespace}`,
    ];
    if (preview.command.channel !== null) {
      lines.push(`Channel: ${preview.command.channel}`);
    }
    if (preview.command.value !== null) {
      lines.push(`Value: ${preview.command.value}`);
    }
    lines.push(
      '',
      'Payload:',
      JSON.stringify(preview.command.payload, null, 2),
      '',
      `Confirmation expires in ${preview.expires_in}s.`
    );
    return lines.join('\n');
  }

  private commandDone(command: TuningCommand, result: TuningCommandResult): void {
    this.commandBusy = false;
    if (result.ok) {
      this.snackBar.open(`${command.id} acknowledged.`, 'Dismiss', {
        duration: 4000,
      });
    } else {
      this.snackBar.open(`${command.id}: ${result.error || 'device error'}`, 'Dismiss', { duration: 6000 });
    }
    this.loadAudit();
    if (this.selectedDeviceUuid) {
      this.selectDevice(this.selectedDeviceUuid);
    }
  }

  private confirm(title: string, message: string, confirmLabel: string) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '640px',
      data: { title, message, confirm: confirmLabel },
    });
    return dialogRef.afterClosed();
  }

  private fail(error: unknown, context: string): void {
    this.snackBar.open(`${context}: ${tuningErrorMessage(error)}`, 'Dismiss', {
      duration: 6000,
    });
  }
}
