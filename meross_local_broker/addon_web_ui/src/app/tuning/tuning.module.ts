// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { MaterialModule } from '@app/material.module';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { TuningRoutingModule } from './tuning-routing.module';
import { TuningComponent } from './tuning.component';
import { YamlEditorComponent } from './yaml-editor.component';

@NgModule({
  declarations: [TuningComponent, YamlEditorComponent, ConfirmDialogComponent],
  imports: [CommonModule, FormsModule, MaterialModule, TuningRoutingModule],
})
export class TuningModule {}
