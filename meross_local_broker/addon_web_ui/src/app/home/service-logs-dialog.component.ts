import { Component, ElementRef, Inject, OnDestroy, ViewChild } from '@angular/core';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { Subscription } from 'rxjs';
import { ServiceStatus } from '@app/model/service';
import { ServiceStore } from '@app/providers/service';

/** Modal window showing the live log stream of one service. */
@Component({
  selector: 'app-service-logs-dialog',
  template: `
    <h2 mat-dialog-title>Logs — {{ data.service.name }}</h2>
    <mat-dialog-content class="logs" #logsContainer>
      <pre>{{ text }}</pre>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .logs {
        width: min(80vw, 900px);
        height: 60vh;
        overflow: auto;
        background: #111;
        color: #eee;
        padding: 12px;
      }

      pre {
        margin: 0;
        white-space: pre-wrap;
        font-size: 12px;
      }
    `,
  ],
})
export class ServiceLogsDialogComponent implements OnDestroy {
  @ViewChild('logsContainer') logsContainer?: ElementRef<HTMLElement>;
  text = '';
  private subscription: Subscription;

  constructor(@Inject(MAT_DIALOG_DATA) public data: { service: ServiceStatus }, store: ServiceStore) {
    this.subscription = store.followServiceLogs(data.service.name).subscribe((lines) => {
      this.text = lines.map((line) => line.replace(/\u001b\[[0-9;]*m/g, '')).join('\n');
      setTimeout(() => {
        const element = this.logsContainer?.nativeElement;
        if (element) {
          element.scrollTop = element.scrollHeight;
        }
      });
    });
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }
}
