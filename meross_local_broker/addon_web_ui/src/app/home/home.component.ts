// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { Component, AfterViewInit, ViewChild, OnInit, OnDestroy, Inject, ChangeDetectionStrategy } from '@angular/core';
import { MatTableDataSource as MatTableDataSource } from '@angular/material/table';
import { Subscription } from 'rxjs';
import { MatSort } from '@angular/material/sort';
import { MatPaginator as MatPaginator } from '@angular/material/paginator';
import { Device } from '@app/model/device';
import { DeviceStore } from '@app/providers/device';
import { Subdevice } from '@app/model/subdevice';
import { SubdeviceStore } from '@app/providers/subdevice';
import { AdminService } from '@app/services/admin';
import {
  MatDialog as MatDialog,
  MatDialogRef as MatDialogRef,
  MAT_DIALOG_DATA as MAT_DIALOG_DATA,
} from '@angular/material/dialog';
import { Configuration } from '@app/model/configuration';
import { MatSnackBar as MatSnackBar } from '@angular/material/snack-bar';
import { ServiceStatus } from '@app/model/service';
import { ServiceStore } from '@app/providers/service';

export interface SetNameDialogData {
  device: Device;
}

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrls: ['./home.component.scss'],
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: false,
})
export class HomeComponent implements AfterViewInit, OnInit, OnDestroy {
  devicesColumns: string[] = [];
  subdevicesColumns: string[] = ['subdeviceId', 'type', 'hubId'];
  advanced = localStorage.getItem('broker-advanced') === '1';
  deviceSource = new MatTableDataSource<Device>([]);
  subdeviceSource = new MatTableDataSource<Subdevice>([]);
  services: ServiceStatus[] = [];
  logsService: ServiceStatus = null;
  autoUpdate = true;
  unconfigured = true;
  private pollSubscription = new Subscription();

  @ViewChild(MatPaginator) paginator: MatPaginator;
  @ViewChild(MatSort) sort: MatSort;

  constructor(
    private deviceStore: DeviceStore,
    private subdeviceStore: SubdeviceStore,
    private serviceStore: ServiceStore,
    private adminService: AdminService,
    private snackBarService: MatSnackBar,
    public dialog: MatDialog
  ) {}
  ngOnInit(): void {
    this.applyColumns();
    // Update the device and subdevice lists once
    this.pollSubscription.add(this.deviceStore.devices.subscribe((devices) => (this.deviceSource.data = devices)));
    this.pollSubscription.add(
      this.subdeviceStore.devices.subscribe((devices) => (this.subdeviceSource.data = devices))
    );
    if (this.autoUpdate) {
      // Keep the paired tables in sync with pairer/broker changes without a
      // manual page refresh.
      this.pollSubscription.add(
        this.deviceStore.deviceUpdates.subscribe((devices) => (this.deviceSource.data = devices))
      );
      this.pollSubscription.add(
        this.subdeviceStore.deviceUpdates.subscribe((devices) => (this.subdeviceSource.data = devices))
      );
    }
    this.pollSubscription.add(this.serviceStore.services.subscribe((services) => (this.services = services)));
    this.pollSubscription.add(this.serviceStore.serviceUpdates.subscribe((services) => (this.services = services)));
    this.adminService.getConfiguration().subscribe((account: Configuration) => {
      this.unconfigured = !account;
    });
  }

  ngOnDestroy(): void {
    this.pollSubscription.unsubscribe();
  }

  alertCopied(): void {
    this.snackBarService.open('Device uuid copied to clipboard.', 'ok', { duration: 2000 });
  }

  ngAfterViewInit() {
    this.deviceSource.paginator = this.paginator;
    this.deviceSource.sort = this.sort;
  }

  toggleAdvanced(): void {
    this.advanced = !this.advanced;
    localStorage.setItem('broker-advanced', this.advanced ? '1' : '0');
    this.applyColumns();
  }

  private applyColumns(): void {
    this.devicesColumns = this.advanced
      ? ['deviceId', 'type', 'network', 'userId', 'profile', 'status']
      : ['deviceId', 'type', 'status'];
  }

  profileVersion(device: Device): string {
    if (!device.profile) {
      return '—';
    }
    return device.profile.version || device.profile.id;
  }

  isCustomProfile(device: Device): boolean {
    return !!device.profile && device.profile.source === 'override';
  }

  profileTooltip(device: Device): string {
    if (!device.profile) {
      return 'No matched profile';
    }
    return `${device.profile.id} · ${device.profile.source}`;
  }

  deviceIcon(device: Device): string {
    const rollerShutters = ['mrs100', 'mss560', 'mss570', 'mrs200'];
    return rollerShutters.includes((device.deviceType || '').toLowerCase()) ? 'window' : 'power';
  }

  isRunning(service: ServiceStatus): boolean {
    return service.status === 'RUNNING';
  }

  statusClass(service: ServiceStatus): 'ok' | 'warn' | 'ko' | 'idle' {
    if (service.logStatus === 'error') {
      return 'ko';
    }
    if (service.logStatus === 'warning') {
      return 'warn';
    }
    if (service.logStatus === 'ok' && this.isRunning(service)) {
      return 'ok';
    }
    return 'idle';
  }

  logStatusText(service: ServiceStatus): string {
    switch (service.logStatus) {
      case 'error':
        return 'errors in logs';
      case 'warning':
        return 'warnings in logs';
      case 'ok':
        return this.isRunning(service) ? 'ok' : 'stopped';
      default:
        return 'no logs';
    }
  }

  serviceShortName(service: ServiceStatus): string {
    return service.name.replace(' Service', '').replace('Local ', '');
  }

  openServiceLogs(service: ServiceStatus): void {
    this.logsService = service;
  }

  closeServiceLogs(): void {
    this.logsService = null;
  }

  assignName(device: Device) {
    const dialogRef = this.dialog.open(SetDeviceNameDialog, {
      data: { device: device },
    });
  }

  forgetDevice(device: Device) {
    const label = device.devName || device.uuid;
    if (!window.confirm(`Forget ${label}? Reset the device afterwards to clear its pairing.`)) {
      return;
    }
    this.adminService.deleteDevice(device.uuid).subscribe((deleted) => {
      if (deleted) {
        this.deviceStore.refresh();
        this.snackBarService.open('Device forgotten.', 'ok', { duration: 2000 });
      }
    });
  }
}

@Component({
  selector: 'set-device-name-dialog',
  templateUrl: 'set-device-name-dialog.html',
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: false,
})
export class SetDeviceNameDialog {
  newDeviceName: string;

  constructor(
    public dialogRef: MatDialogRef<SetDeviceNameDialog>,
    private deviceStore: DeviceStore,
    @Inject(MAT_DIALOG_DATA) public data: SetNameDialogData
  ) {
    this.newDeviceName = data.device.devName;
  }

  onNoClick(): void {
    this.dialogRef.close();
  }

  setDeviceName(): void {
    this.deviceStore.updateDeviceName(this.data.device.uuid, this.newDeviceName).subscribe((d) => {
      if (d !== null) {
        this.data.device.devName = this.newDeviceName;
      }
      this.dialogRef.close();
    });
  }
}
