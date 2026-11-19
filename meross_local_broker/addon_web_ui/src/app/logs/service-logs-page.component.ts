import { Component, ElementRef, EventEmitter, Input, OnDestroy, OnInit, Output, ViewChild } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Subscription } from 'rxjs';
import { ServiceStatus } from '@app/model/service';
import { ServiceStore } from '@app/providers/service';

type LogLevel = 'debug' | 'info' | 'warning' | 'error';
type LevelFilter = 'all' | LogLevel;

interface LogSegment {
  text: string;
  match: boolean;
}

interface LogLine {
  text: string;
  severity: '' | 'warning' | 'error';
  level: LogLevel;
  segments: LogSegment[];
}

/** Full-page viewer for one service log at a time, styled after HA's log page. */
@Component({
  selector: 'app-service-logs-page',
  template: `
    <div class="page">
      <div class="header">
        <button mat-icon-button (click)="close()" matTooltip="Back" aria-label="Back to home">
          <mat-icon>arrow_back</mat-icon>
        </button>
        <span class="title">Logs</span>
      </div>

      <nav mat-tab-nav-bar class="tabs">
        <a
          mat-tab-link
          *ngFor="let service of services; let i = index"
          [active]="i === selectedIndex"
          (click)="selectTab(i)"
        >
          {{ serviceShortName(service) }}
        </a>
      </nav>

      <div class="toolbar">
        <button
          mat-icon-button
          type="button"
          (click)="togglePause()"
          [matTooltip]="paused ? 'Resume' : 'Pause'"
          aria-label="Pause or resume"
        >
          <mat-icon>{{ paused ? 'play_arrow' : 'pause' }}</mat-icon>
        </button>
        <button
          mat-icon-button
          type="button"
          (click)="toggleWrap()"
          [matTooltip]="wrap ? 'Disable line wrapping' : 'Wrap lines'"
          aria-label="Toggle line wrapping"
        >
          <mat-icon>wrap_text</mat-icon>
        </button>
        <button
          mat-icon-button
          type="button"
          [cdkCopyToClipboard]="text"
          (cdkCopyToClipboardCopied)="onCopied($event)"
          matTooltip="Copy visible logs"
          aria-label="Copy visible logs"
        >
          <mat-icon>content_copy</mat-icon>
        </button>
        <button
          mat-icon-button
          type="button"
          (click)="downloadLogs()"
          matTooltip="Download full log"
          aria-label="Download full log"
        >
          <mat-icon>download</mat-icon>
        </button>

        <span class="spacer"></span>

        <mat-form-field class="search" appearance="standard">
          <mat-label>Search</mat-label>
          <input matInput [(ngModel)]="searchText" (ngModelChange)="applyFilters()" aria-label="Search log lines" />
          <button
            mat-icon-button
            matSuffix
            type="button"
            *ngIf="searchText"
            (click)="clearSearch()"
            aria-label="Clear search"
          >
            <mat-icon>close</mat-icon>
          </button>
        </mat-form-field>

        <mat-form-field class="level" appearance="standard">
          <mat-label>Level</mat-label>
          <mat-select [(ngModel)]="levelFilter" (selectionChange)="applyFilters()" aria-label="Filter by log level">
            <mat-option value="all">All</mat-option>
            <mat-option value="debug">Debug</mat-option>
            <mat-option value="info">Info</mat-option>
            <mat-option value="warning">Warning</mat-option>
            <mat-option value="error">Error</mat-option>
          </mat-select>
        </mat-form-field>

        <span class="counter">{{ logLines.length }} / {{ totalCount }} lines</span>
        <span class="paused-label" *ngIf="paused">Paused</span>
      </div>

      <div class="logs" [class.wrap]="wrap" #logsContainer>
        <div
          class="log-line"
          *ngFor="let line of logLines"
          [class.warning]="line.severity === 'warning'"
          [class.error]="line.severity === 'error'"
        >
          <span class="line-text">
            <span *ngFor="let segment of line.segments" [class.match]="segment.match">{{ segment.text }}</span>
          </span>
          <button
            mat-icon-button
            class="line-copy"
            type="button"
            [cdkCopyToClipboard]="line.text"
            (cdkCopyToClipboardCopied)="onLineCopied($event)"
            matTooltip="Copy this line"
            aria-label="Copy this line"
          >
            <mat-icon>content_copy</mat-icon>
          </button>
        </div>
        <div class="empty" *ngIf="logLines.length === 0">No matching log lines.</div>
      </div>
    </div>
  `,
  styles: [
    `
      .page {
        display: flex;
        flex-direction: column;
        width: 100%;
        box-sizing: border-box;
      }

      .header {
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .title {
        font-size: 20px;
        font-weight: 500;
      }

      .tabs {
        margin-bottom: 4px;
      }

      .toolbar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 0 8px 4px;
      }

      .spacer {
        flex: 1 1 auto;
      }

      .search {
        width: 220px;
      }

      .level {
        width: 120px;
      }

      .counter,
      .paused-label {
        color: var(--secondary-text-color, #727272);
        font-size: 12px;
        white-space: nowrap;
      }

      .paused-label {
        color: var(--warning-color, #ffa600);
      }

      .logs {
        height: calc(100vh - 280px);
        min-height: 240px;
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

      .match {
        background: var(--mark-color, rgba(255, 214, 0, 0.35));
        border-radius: 2px;
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

      .empty {
        color: var(--secondary-text-color, #727272);
        font-style: italic;
      }
    `,
  ],
})
export class ServiceLogsPageComponent implements OnInit, OnDestroy {
  @Input() services: ServiceStatus[] = [];
  @Input() initialService: string;
  @Output() closed = new EventEmitter<void>();

  @ViewChild('logsContainer') logsContainer?: ElementRef<HTMLElement>;

  selectedIndex = 0;
  logLines: LogLine[] = [];
  text = '';
  paused = false;
  wrap = false;
  searchText = '';
  levelFilter: LevelFilter = 'all';
  totalCount = 0;

  private latestLines: string[] = [];
  private subscription?: Subscription;

  constructor(private store: ServiceStore, private snackBar: MatSnackBar) {}

  ngOnInit(): void {
    const index = this.services.findIndex((service) => service.name === this.initialService);
    this.selectedIndex = index >= 0 ? index : 0;
    this.followSelectedService();
  }

  ngOnDestroy(): void {
    this.unsubscribeLogs();
  }

  serviceShortName(service: ServiceStatus): string {
    return service.name.replace(' Service', '').replace('Local ', '');
  }

  selectTab(index: number): void {
    if (index === this.selectedIndex) {
      return;
    }
    this.selectedIndex = index;
    this.followSelectedService();
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

  clearSearch(): void {
    this.searchText = '';
    this.applyFilters();
  }

  applyFilters(): void {
    this.render();
  }

  close(): void {
    this.closed.emit();
  }

  downloadLogs(): void {
    const lines = this.latestLines.map((raw) => this.cleanLine(raw));
    const blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const name = (this.services[this.selectedIndex]?.name || 'logs').replace(/[^a-z0-9._-]+/gi, '_');
    const link = document.createElement('a');
    link.href = url;
    link.download = `${name}.log`;
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

  private get filtering(): boolean {
    return this.searchText.trim().length > 0 || this.levelFilter !== 'all';
  }

  private followSelectedService(): void {
    this.unsubscribeLogs();
    const service = this.services[this.selectedIndex];
    this.latestLines = [];
    this.logLines = [];
    this.text = '';
    this.totalCount = 0;
    if (!service) {
      return;
    }
    this.subscription = this.store.followServiceLogs(service.name).subscribe((lines) => {
      this.latestLines = lines;
      if (!this.paused) {
        this.render();
      }
    });
  }

  private unsubscribeLogs(): void {
    if (this.subscription) {
      this.subscription.unsubscribe();
      this.subscription = undefined;
    }
  }

  private render(): void {
    const element = this.logsContainer?.nativeElement;
    const follow =
      !this.paused &&
      !this.filtering &&
      (!element || element.scrollHeight - element.scrollTop - element.clientHeight < 40);

    const search = this.searchText.trim().toLowerCase();
    const allLines = this.latestLines.map((raw) => this.toLogLine(raw));
    this.totalCount = allLines.length;
    this.logLines = allLines
      .filter((line) => this.levelFilter === 'all' || line.level === this.levelFilter)
      .filter((line) => !search || line.text.toLowerCase().includes(search))
      .map((line) => ({ ...line, segments: this.segment(line.text, search) }));
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

  private segment(text: string, search: string): LogSegment[] {
    if (!search) {
      return [{ text, match: false }];
    }
    const lower = text.toLowerCase();
    const segments: LogSegment[] = [];
    let from = 0;
    while (from < text.length) {
      const at = lower.indexOf(search, from);
      if (at < 0) {
        segments.push({ text: text.slice(from), match: false });
        break;
      }
      if (at > from) {
        segments.push({ text: text.slice(from, at), match: false });
      }
      segments.push({ text: text.substr(at, search.length), match: true });
      from = at + search.length;
    }
    return segments.length > 0 ? segments : [{ text, match: false }];
  }

  private toLogLine(raw: string): LogLine {
    const text = this.cleanLine(raw);
    if (/\b(error|fatal|critical|crit)\b/i.test(text)) {
      return { text, severity: 'error', level: 'error', segments: [] };
    }
    if (/\b(warn|warning)\b/i.test(text)) {
      return { text, severity: 'warning', level: 'warning', segments: [] };
    }
    if (/\bdebug\b/i.test(text)) {
      return { text, severity: '', level: 'debug', segments: [] };
    }
    return { text, severity: '', level: 'info', segments: [] };
  }

  private cleanLine(raw: string): string {
    return raw.replace(/\u001b\[[0-9;]*m/g, '').replace(/[\r\n]+$/, '');
  }
}
