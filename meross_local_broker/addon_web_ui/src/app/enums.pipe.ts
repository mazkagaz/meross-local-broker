import { Pipe, PipeTransform } from '@angular/core';
import { BridgeStatus, DeviceOnlineStatus } from './model/device';

@Pipe({
  name: 'onlineDeviceStatusName',
  standalone: false,
})
export class OnlineDeviceStatusName implements PipeTransform {
  transform(value: DeviceOnlineStatus): string {
    return DeviceOnlineStatus[value];
  }
}

@Pipe({
  name: 'bridgeStatusName',
  standalone: false,
})
export class BridgeStatusName implements PipeTransform {
  transform(value: BridgeStatus): string {
    return value;
  }
}
