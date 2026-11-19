// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TranslateModule } from '@ngx-translate/core';
import { RouterModule } from '@angular/router';
import { FlexLayoutModule } from '@angular/flex-layout';

import { MaterialModule } from '@app/material.module';
import { ShellComponent } from './shell.component';
import { HeaderComponent } from './header/header.component';

@NgModule({
  imports: [CommonModule, TranslateModule, FlexLayoutModule, MaterialModule, RouterModule],
  declarations: [HeaderComponent, ShellComponent],
})
export class ShellModule {}
