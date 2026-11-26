// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { SharedModule } from '@shared';
import { MaterialModule } from '@app/material.module';
import { HomeRoutingModule } from './home-routing.module';
import { HomeComponent, SetDeviceNameDialog } from './home.component';
import { ServiceLogsPageComponent } from '@app/logs/service-logs-page.component';
import { OnlineDeviceStatusName, BridgeStatusName } from '../enums.pipe';
import { FormsModule } from '@angular/forms';

@NgModule({
  imports: [CommonModule, TranslateModule, SharedModule, MaterialModule, HomeRoutingModule, FormsModule],
  declarations: [
    HomeComponent,
    OnlineDeviceStatusName,
    BridgeStatusName,
    SetDeviceNameDialog,
    ServiceLogsPageComponent,
  ],
})
export class HomeModule {}
