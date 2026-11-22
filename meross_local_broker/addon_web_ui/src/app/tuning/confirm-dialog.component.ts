// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { Component, Inject } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';

export interface ConfirmDialogData {
  title: string;
  message: string;
  confirm?: string;
}

@Component({
  selector: 'app-confirm-dialog',
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>
      <pre class="confirm-message">{{ data.message }}</pre>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button type="button" (click)="close(false)">Cancel</button>
      <button mat-raised-button color="primary" type="button" (click)="close(true)">
        {{ data.confirm || 'Confirm' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .confirm-message {
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 45vh;
        overflow: auto;
        font-size: 12px;
        margin: 0;
      }
    `,
  ],
})
export class ConfirmDialogComponent {
  constructor(
    public dialogRef: MatDialogRef<ConfirmDialogComponent, boolean>,
    @Inject(MAT_DIALOG_DATA) public data: ConfirmDialogData
  ) {}

  close(result: boolean): void {
    this.dialogRef.close(result);
  }
}
