import { Component, ElementRef, Inject, OnDestroy, ViewChild } from '@angular/core';
import { MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Subscription } from 'rxjs';
import { ServiceStatus } from '@app/model/service';
import { ServiceStore } from '@app/providers/service';

interface LogLine {
  text: string;
  severity: '' | 'warning' | 'error';
}

/** Modal window showing the live log stream of one service. */
@Component({
  selector: 'app-service-logs-dialog',
  template: `
    <h2 mat-dialog-title>Logs — {{ data.service.name }}</h2>
    <mat-dialog-content class="logs" #logsContainer>
      <div
        class="log-line"
        *ngFor="let line of logLines"
        [class.warning]="line.severity === 'warning'"
        [class.error]="line.severity === 'error'"
      >
        {{ line.text || ' ' }}
      </div>
    </mat-dialog-content>
    <mat-dialog-actions class="actions">
      <button mat-button [cdkCopyToClipboard]="text" (cdkCopyToClipboardCopied)="onCopied($event)">
        <mat-icon>content_copy</mat-icon>
        <span>Copy</span>
      </button>
      <span class="spacer"></span>
      <button mat-button mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .logs {
        width: min(80vw, 900px);
        height: 60vh;
        overflow: auto;
        padding: 8px 12px;
        background: var(--card-background-color, #fff);
        color: var(--primary-text-color, #212121);
        border: 1px solid var(--divider-color, #e0e0e0);
        border-radius: var(--ha-card-border-radius, 4px);
        font-family: var(--code-font-family, 'Roboto Mono', monospace);
        font-size: 12px;
      }

      .log-line {
        line-height: 1.45;
        white-space: pre-wrap;
      }

      .log-line.warning {
        color: var(--warning-color, #ffa600);
      }

      .log-line.error {
        color: var(--error-color, #db4437);
      }

      .actions {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .spacer {
        flex: 1 1 auto;
      }
    `,
  ],
})
export class ServiceLogsDialogComponent implements OnDestroy {
  @ViewChild('logsContainer') logsContainer?: ElementRef<HTMLElement>;
  logLines: LogLine[] = [];
  text = '';
  private subscription: Subscription;

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: { service: ServiceStatus },
    store: ServiceStore,
    private snackBar: MatSnackBar
  ) {
    this.subscription = store.followServiceLogs(data.service.name).subscribe((lines) => {
      this.logLines = lines.map((raw) => this.toLogLine(raw));
      this.text = this.logLines.map((line) => line.text).join('\n');
      setTimeout(() => {
        const element = this.logsContainer?.nativeElement;
        if (element) {
          element.scrollTop = element.scrollHeight;
        }
      });
    });
  }

  onCopied(copied: boolean): void {
    if (copied) {
      this.snackBar.open('Logs copied to clipboard.', 'ok', { duration: 2000 });
    }
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }

  private toLogLine(raw: string): LogLine {
    const text = raw.replace(/\u001b\[[0-9;]*m/g, '').replace(/[\r\n]+$/, '');
    if (/\b(error|fatal|critical|crit)\b/i.test(text)) {
      return { text, severity: 'error' };
    }
    if (/\b(warn|warning)\b/i.test(text)) {
      return { text, severity: 'warning' };
    }
    return { text, severity: '' };
  }
}
