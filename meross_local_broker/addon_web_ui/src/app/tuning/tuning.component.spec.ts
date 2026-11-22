// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { NO_ERRORS_SCHEMA } from '@angular/core';
import { fakeAsync, TestBed, tick } from '@angular/core/testing';
import { Clipboard } from '@angular/cdk/clipboard';
import { FormsModule } from '@angular/forms';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { of, throwError } from 'rxjs';

import { TuningComponent } from './tuning.component';
import { TuningService } from './tuning.service';

const PROFILE: any = {
  id: 'p1',
  version: '1',
  source: 'bundled',
  catalog_hash: 'cat-hash',
  override_hash: null,
  revision: 'r1',
  yaml: 'schema_version: 2\nprofile:\n  id: p1\n',
  override_yaml: null,
  bundled_yaml: 'schema_version: 2\nprofile:\n  id: p1\n',
  diff: '',
  devices_affected: 2,
  backups: [],
};

const VALIDATION: any = {
  valid: true,
  profile_id: 'p1',
  errors: [],
  warnings: [],
  summary: {},
  diff: '@@ -1 +1 @@\n+profile: tuned',
  diff_base: 'bundled',
};

const PROFILE_SUMMARY: any = {
  id: 'p1',
  version: '1',
  source: 'bundled',
  hash: 'h',
  requires_engine: null,
  devices_affected: 1,
  override_file: null,
};

const COMMAND: any = {
  id: 'cover.set_position',
  entity: 'cover',
  name: 'Cover',
  platform: 'cover',
  command: 'set_position',
  namespace: 'Appliance.RollerShutter.Position',
  type: 'number',
  unit: null,
  min: null,
  max: null,
  step: null,
  value_scale: null,
  accepts_value: true,
  accepts_channel: true,
  channels: [0],
  channel: 0,
  payload_template: {
    position: { channel: '$channel', position: '$value' },
  },
};

const DEVICE_STATE: any = {
  device: {
    uuid: 'd1',
    name: 'Roller',
    type: 'mrs100',
    sub_type: null,
    online: 'ONLINE',
    last_seen: '2026-11-22T10:00:00',
    local_ip: '192.168.1.10',
    firmware: '1.0.0',
    hardware: '1.0',
    channels: [0],
    subdevices: [],
  },
  profile: {
    id: 'p1',
    version: '1',
    source: 'bundled',
    hash: 'cat-hash',
    requires_engine: '>=2.2',
  },
  ability: {},
  entities: [],
  subdevice_templates: [],
  polling: [
    {
      namespace: 'Appliance.Test',
      scope: 'hub',
      methods: ['PUSH'],
      strategy: 'default',
      period_s: 60,
      push: true,
      response_size: null,
    },
  ],
  cache: {},
  errors: [],
  warnings: [],
};

describe('TuningComponent', () => {
  let component: TuningComponent;
  let service: jasmine.SpyObj<TuningService>;
  let dialog: { open: jasmine.Spy };
  let snackBar: { open: jasmine.Spy };
  let clipboard: { copy: jasmine.Spy };

  beforeEach(() => {
    localStorage.removeItem('tuning-show-all-profiles');
    service = jasmine.createSpyObj<TuningService>('TuningService', [
      'listProfiles',
      'listDevices',
      'listAudit',
      'getProfile',
      'validate',
      'saveOverride',
      'deleteOverride',
      'restoreBackup',
      'downloadProfiles',
      'importFile',
      'captureStatus',
      'captureStart',
      'captureStop',
      'captureDraft',
      'deviceState',
      'preview',
      'readDevice',
      'deviceCommands',
      'executeCommand',
      'refreshAbility',
    ]);
    service.listProfiles.and.returnValue(
      of({
        revision: 'r1',
        profiles: [
          {
            id: 'p1',
            version: '1',
            source: 'bundled',
            hash: 'cat-hash',
            requires_engine: '>=2.2',
            devices_affected: 2,
            override_file: null,
          },
        ],
      })
    );
    service.listDevices.and.returnValue(
      of([
        {
          uuid: 'd1',
          name: 'Roller',
          type: 'mrs100',
          sub_type: null,
          online: 'ONLINE',
          profile: 'p1',
          channels: [0],
          subdevices: [],
        },
      ])
    );
    service.listAudit.and.returnValue(of([]));
    service.captureStatus.and.returnValue(of({}));
    service.getProfile.and.returnValue(of(PROFILE as any));
    service.validate.and.returnValue(of(VALIDATION as any));
    service.saveOverride.and.returnValue(
      of({ id: 'p1', revision: 'r2', override_hash: 'ovr', diff: '', warnings: [] })
    );
    service.deleteOverride.and.returnValue(of({}));
    service.importFile.and.returnValue(of({ dry_run: true, revision: 'r1', profiles: [] }));
    service.deviceState.and.returnValue(of(DEVICE_STATE as any));
    service.preview.and.returnValue(of({} as any));
    service.readDevice.and.returnValue(of({} as any));
    service.deviceCommands.and.returnValue(
      of({
        uuid: 'd1',
        profile_id: 'p1',
        online: 'ONLINE',
        commands: [COMMAND],
        namespaces: ['Appliance.RollerShutter.Position'],
        warnings: [],
      } as any)
    );
    service.executeCommand.and.returnValue(of({} as any));
    service.refreshAbility.and.returnValue(of({ uuid: 'd1', count: 2, namespaces: [] } as any));

    dialog = { open: jasmine.createSpy('open') };
    dialog.open.and.returnValue({ afterClosed: () => of(true) });
    snackBar = { open: jasmine.createSpy('open') };
    clipboard = { copy: jasmine.createSpy('copy') };

    TestBed.configureTestingModule({
      declarations: [TuningComponent],
      imports: [FormsModule],
      providers: [
        { provide: TuningService, useValue: service },
        { provide: MatDialog, useValue: dialog },
        { provide: MatSnackBar, useValue: snackBar },
        { provide: Clipboard, useValue: clipboard },
      ],
      schemas: [NO_ERRORS_SCHEMA],
    });
    const fixture = TestBed.createComponent(TuningComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('loads inventory on init', () => {
    expect(service.listProfiles).toHaveBeenCalled();
    expect(service.listDevices).toHaveBeenCalled();
    expect(service.listAudit).toHaveBeenCalled();
    expect(component.revision).toBe('r1');
    expect(component.profiles.length).toBe(1);
    expect(component.devices.length).toBe(1);
  });

  it('filters profiles to detected ones and searches all', () => {
    component.profiles = [
      { ...PROFILE_SUMMARY, id: 'detected', devices_affected: 1 },
      { ...PROFILE_SUMMARY, id: 'hidden', devices_affected: 0 },
    ];
    expect(component.filteredProfiles.map((item) => item.id)).toEqual(['detected']);
    expect(component.detectedProfileCount).toBe(1);

    component.showAllProfiles = true;
    expect(component.filteredProfiles.length).toBe(2);

    component.profileFilter = 'hid';
    expect(component.filteredProfiles.map((item) => item.id)).toEqual(['hidden']);
  });

  it('persists the show-all toggle and copies identifiers', () => {
    component.persistShowAll(true);
    expect(localStorage.getItem('tuning-show-all-profiles')).toBe('1');

    component.copyValue('abc', 'Revision');
    expect(clipboard.copy).toHaveBeenCalledWith('abc');
    expect(snackBar.open).toHaveBeenCalled();
  });

  it('loads and validates a selected profile', fakeAsync(() => {
    component.selectProfile('p1');
    tick();
    expect(service.getProfile).toHaveBeenCalledWith('p1');
    expect(component.profile.id).toBe('p1');
    expect(component.yamlText).toContain('id: p1');

    tick(600);
    expect(service.validate).toHaveBeenCalled();
    expect(component.validation.valid).toBeTrue();
    expect(component.canApply()).toBeTrue();
  }));

  it('applies an override after confirmation', fakeAsync(() => {
    component.selectProfile('p1');
    tick(600);
    component.applyOverride();
    expect(dialog.open).toHaveBeenCalled();
    expect(service.saveOverride).toHaveBeenCalledWith('p1', component.yamlText, 'cat-hash');
    expect(service.getProfile).toHaveBeenCalledTimes(2);
    tick(600);
  }));

  it('reverts an override with its hash', fakeAsync(() => {
    service.getProfile.and.returnValue(of({ ...PROFILE, source: 'override', override_hash: 'ovr-hash' } as any));
    component.selectProfile('p1');
    tick(600);
    component.revertToBundled();
    expect(service.deleteOverride).toHaveBeenCalledWith('p1', 'ovr-hash');
    tick(600);
  }));

  it('injects a capture draft into the editor', () => {
    component.deviceState = DEVICE_STATE as any;
    service.captureDraft.and.returnValue(
      of({
        path: '/tmp/draft.yaml',
        yaml: 'schema_version: 2\nprofile:\n  id: draft.mrs100\n',
        namespaces: 1,
        frames: 3,
      })
    );
    component.draftCapture();
    expect(component.draftMode).toBeTrue();
    expect(component.tabIndex).toBe(0);
    expect(component.yamlText).toContain('draft.mrs100');
    expect(component.selectedProfileId).toBeNull();
  });

  it('posts a simulation with the parsed payload', () => {
    component.deviceState = DEVICE_STATE as any;
    component.simNamespace = 'Appliance.Test';
    component.simMethod = 'PUSH';
    component.simPayload = '{"channel": 0, "value": 1}';
    component.preview();
    expect(service.preview).toHaveBeenCalledWith(
      'p1',
      jasmine.objectContaining({
        namespace: 'Appliance.Test',
        method: 'PUSH',
        payload: { channel: 0, value: 1 },
      })
    );
  });

  it('surfaces live read errors', () => {
    component.selectedDeviceUuid = 'd1';
    service.readDevice.and.returnValue(throwError({ error: { error: 'device is offline' } }));
    component.readNow();
    expect(component.readError).toBe('device is offline');
  });

  it('loads typed commands with a selected device', () => {
    component.selectDevice('d1');
    expect(service.deviceCommands).toHaveBeenCalledWith('d1');
    expect(component.commands.length).toBe(1);
    expect(component.commandChannel['cover.set_position']).toBe(0);
    expect(component.commandValue['cover.set_position']).toBe(0);
  });

  it('explains when no profile matches a device', () => {
    service.deviceState.and.returnValue(of({ ...DEVICE_STATE, profile: null } as any));
    component.selectDevice('d1');
    expect(service.deviceCommands).not.toHaveBeenCalled();
    expect(component.commandsNote).toContain('No profile matches');
  });

  it('refreshes the ability when no profile matches', () => {
    service.deviceState.and.returnValue(of({ ...DEVICE_STATE, profile: null } as any));
    component.selectDevice('d1');
    component.refreshAbility();
    expect(service.refreshAbility).toHaveBeenCalledWith('d1');
    expect(snackBar.open).toHaveBeenCalled();
    expect(service.deviceState).toHaveBeenCalledTimes(2);
    expect(component.abilityBusy).toBeFalse();
  });

  it('prepares and confirms a device command', () => {
    component.selectDevice('d1');
    service.executeCommand.and.callFake((uuid: string, id: string, body: any) =>
      body.confirm
        ? of({
            ok: true,
            error: null,
            profile_id: 'p1',
            command: {},
            result: {},
            before: {},
            after: {},
          } as any)
        : of({
            requires_confirmation: true,
            token: 'tok',
            expires_in: 60,
            device_uuid: 'd1',
            profile_id: 'p1',
            command: {
              id,
              namespace: 'Appliance.RollerShutter.Position',
              channel: 0,
              value: 42,
              payload: { position: { channel: 0, position: 42 } },
            },
          } as any)
    );
    component.commandValue['cover.set_position'] = 42;
    component.runCommand(component.commands[0]);

    expect(service.executeCommand).toHaveBeenCalledWith('d1', 'cover.set_position', { channel: 0, value: 42 });
    expect(dialog.open).toHaveBeenCalled();
    const message = dialog.open.calls.mostRecent().args[1].data.message;
    expect(message).toContain('"position"');
    expect(service.executeCommand).toHaveBeenCalledWith('d1', 'cover.set_position', { confirm: true, token: 'tok' });
    expect(component.commandBusy).toBeFalse();
    expect(snackBar.open).toHaveBeenCalled();
  });

  it('previews then applies an import', () => {
    const file = new File(['schema_version: 2'], 'profiles.yaml');
    component.onImportFile(({
      target: { files: [file], value: '' },
    } as unknown) as Event);
    expect(service.importFile).toHaveBeenCalledWith(file, true);
    expect(component.importPreview).not.toBeNull();

    service.importFile.and.returnValue(of({ dry_run: false, revision: 'r2', profiles: [] }));
    component.applyImport();
    expect(service.importFile).toHaveBeenCalledWith(file, false);
    expect(component.importPreview).toBeNull();
  });
});
