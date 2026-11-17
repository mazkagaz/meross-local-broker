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
    <div class="toolbar">
      <button mat-icon-button (click)="togglePause()" [matTooltip]="paused ? 'Resume' : 'Pause'">
        <mat-icon>{{ paused ? 'play_arrow' : 'pause' }}</mat-icon>
      </button>
      <button mat-icon-button (click)="toggleWrap()" [matTooltip]="wrap ? 'Disable line wrapping' : 'Wrap lines'">
        <mat-icon>wrap_text</mat-icon>
      </button>
      <button
        mat-icon-button
        [cdkCopyToClipboard]="text"
        (cdkCopyToClipboardCopied)="onCopied($event)"
        matTooltip="Copy all logs"
      >
        <mat-icon>content_copy</mat-icon>
      </button>
      <button mat-icon-button (click)="downloadLogs()" matTooltip="Download logs">
        <mat-icon>download</mat-icon>
      </button>
      <span class="spacer"></span>
      <span class="status" *ngIf="paused">Paused</span>
    </div>
    <mat-dialog-content class="logs" [class.wrap]="wrap" #logsContainer>
      <div
        class="log-line"
        *ngFor="let line of logLines"
        [class.warning]="line.severity === 'warning'"
        [class.error]="line.severity === 'error'"
      >
        <span class="line-text">{{ line.text || ' ' }}</span>
        <button
          mat-icon-button
          class="line-copy"
          [cdkCopyToClipboard]="line.text"
          (cdkCopyToClipboardCopied)="onLineCopied($event)"
          matTooltip="Copy this line"
        >
          <mat-icon>content_copy</mat-icon>
        </button>
      </div>
    </mat-dialog-content>
    <mat-dialog-actions class="actions">
      <span class="spacer"></span>
      <button mat-button mat-dialog-close>Close</button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .toolbar {
        display: flex;
        align-items: center;
        gap: 2px;
        padding: 0 12px 4px;
      }

      .status {
        color: var(--warning-color, #ffa600);
        font-size: 12px;
        margin-right: 8px;
      }

      .logs {
        width: min(80vw, 900px);
        height: 60vh;
        overflow: auto;
        padding: 8px 12px;
        background: var(--ha-card-background, var(--card-background-color, #fff));
        color: var(--primary-text-color, #212121);
        border: 1px solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
        border-radius: var(--ha-card-border-radius, 4px);
        font-family: var(--code-font-family, 'Roboto Mono', monospace);
        font-size: 12px;
        user-select: text;
      }

      .log-line {
        position: relative;
        line-height: 1.45;
        white-space: pre;
        padding-right: 28px;
        min-height: 18px;
      }

      .logs.wrap .log-line {
        white-space: pre-wrap;
        word-break: break-word;
      }

      .log-line.warning {
        color: var(--warning-color, #ffa600);
      }

      .log-line.error {
        color: var(--error-color, #db4437);
      }

      .line-copy {
        position: absolute;
        right: 0;
        top: -6px;
        opacity: 0;
        transform: scale(0.65);
        transition: opacity 120ms ease-in-out;
      }

      .log-line:hover .line-copy,
      .line-copy:focus {
        opacity: 1;
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
  paused = false;
  wrap = false;
  private latestLines: string[] = [];
  private subscription: Subscription;

  constructor(
    @Inject(MAT_DIALOG_DATA) public data: { service: ServiceStatus },
    store: ServiceStore,
    private snackBar: MatSnackBar
  ) {
    this.subscription = store.followServiceLogs(data.service.name).subscribe((lines) => {
      this.latestLines = lines;
      if (!this.paused) {
        this.render();
      }
    });
  }

  togglePause(): void {
    this.paused = !this.paused;
    if (!this.paused) {
      this.render();
    }
  }

  toggleWrap(): void {
    this.wrap = !this.wrap;
  }

  downloadLogs(): void {
    const blob = new Blob([this.text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${this.data.service.name.replace(/[^a-z0-9._-]+/gi, '_')}.log`;
    link.click();
    URL.revokeObjectURL(url);
  }

  onCopied(copied: boolean): void {
    if (copied) {
      this.snackBar.open('Logs copied to clipboard.', 'ok', { duration: 2000 });
    }
  }

  onLineCopied(copied: boolean): void {
    if (copied) {
      this.snackBar.open('Line copied to clipboard.', 'ok', { duration: 1500 });
    }
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }

  private render(): void {
    const element = this.logsContainer?.nativeElement;
    const follow = !this.paused && (!element || element.scrollHeight - element.scrollTop - element.clientHeight < 40);

    this.logLines = this.latestLines.map((raw) => this.toLogLine(raw));
    this.text = this.logLines.map((line) => line.text).join('\n');

    if (follow) {
      setTimeout(() => {
        const container = this.logsContainer?.nativeElement;
        if (container) {
          container.scrollTop = container.scrollHeight;
        }
      });
    }
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
