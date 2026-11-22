// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { HttpClient, HttpHeaders, HttpParams, HttpErrorResponse } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '@env/environment';

import {
  TuningAuditEntry,
  TuningCaptureDraft,
  TuningCaptureStatus,
  TuningCommandCatalog,
  TuningCommandPreview,
  TuningCommandResult,
  TuningDeviceState,
  TuningDeviceSummary,
  TuningImportResult,
  TuningPreviewResult,
  TuningProfileDetail,
  TuningProfileList,
  TuningReadResult,
  TuningSaveResult,
  TuningValidation,
} from '@app/model/tuning';

export interface Download {
  blob: Blob;
  filename: string;
}

export function tuningErrorMessage(error: unknown): string {
  const response = error as HttpErrorResponse;
  const body = response && response.error;
  if (body && typeof body === 'object' && typeof body.error === 'string') {
    if (typeof body.retry_after === 'number') {
      return `${body.error} (retry in ${body.retry_after}s)`;
    }
    return body.error;
  }
  if (response && typeof response.message === 'string') {
    return response.message;
  }
  return 'Request failed';
}

@Injectable({
  providedIn: 'root',
})
export class TuningService {
  private readonly base = environment.backend + '/_admin_';

  constructor(private http: HttpClient) {}

  listProfiles(): Observable<TuningProfileList> {
    return this.http.get<TuningProfileList>(this.base + '/profiles');
  }

  getProfile(profileId: string): Observable<TuningProfileDetail> {
    return this.http.get<TuningProfileDetail>(this.base + '/profiles/' + encodeURIComponent(profileId));
  }

  validate(yaml: string, profileId?: string | null): Observable<TuningValidation> {
    const body: { yaml: string; profile_id?: string } = { yaml };
    if (profileId) {
      body.profile_id = profileId;
    }
    return this.http.post<TuningValidation>(this.base + '/profiles/validate', body, { headers: this.jsonHeaders() });
  }

  saveOverride(profileId: string, yaml: string, expectedHash?: string | null): Observable<TuningSaveResult> {
    const body: { yaml: string; expected_hash?: string } = { yaml };
    if (expectedHash) {
      body.expected_hash = expectedHash;
    }
    return this.http.put<TuningSaveResult>(
      this.base + '/profiles/' + encodeURIComponent(profileId) + '/override',
      body,
      { headers: this.jsonHeaders() }
    );
  }

  deleteOverride(profileId: string, expectedHash?: string | null): Observable<unknown> {
    const body: { expected_hash?: string } = {};
    if (expectedHash) {
      body.expected_hash = expectedHash;
    }
    return this.http.request('delete', this.base + '/profiles/' + encodeURIComponent(profileId) + '/override', {
      body,
      headers: this.jsonHeaders(),
    });
  }

  restoreBackup(profileId: string, filename: string): Observable<unknown> {
    return this.http.post(
      this.base +
        '/profiles/' +
        encodeURIComponent(profileId) +
        '/backups/' +
        encodeURIComponent(filename) +
        '/restore',
      {},
      { headers: this.jsonHeaders() }
    );
  }

  downloadProfiles(format: string, source: string, profileId?: string | null): Observable<Download> {
    return this.download(format, source, profileId);
  }

  importFile(file: File, dryRun: boolean): Observable<TuningImportResult> {
    const data = new FormData();
    data.append('file', file, file.name);
    const params = new HttpParams().set('dry_run', dryRun ? 'true' : 'false');
    return this.http.post<TuningImportResult>(this.base + '/profiles/import', data, { params });
  }

  listAudit(limit: number = 200, profileId?: string | null): Observable<TuningAuditEntry[]> {
    let params = new HttpParams().set('limit', String(limit));
    if (profileId) {
      params = params.set('profile_id', profileId);
    }
    return this.http.get<TuningAuditEntry[]>(this.base + '/tuning/audit', { params });
  }

  listDevices(): Observable<TuningDeviceSummary[]> {
    return this.http.get<TuningDeviceSummary[]>(this.base + '/tuning/devices');
  }

  deviceState(uuid: string): Observable<TuningDeviceState> {
    return this.http.get<TuningDeviceState>(this.base + '/tuning/devices/' + encodeURIComponent(uuid));
  }

  preview(profileId: string, body: unknown): Observable<TuningPreviewResult> {
    return this.http.post<TuningPreviewResult>(
      this.base + '/profiles/' + encodeURIComponent(profileId) + '/preview',
      body,
      { headers: this.jsonHeaders() }
    );
  }

  readDevice(uuid: string, body: unknown): Observable<TuningReadResult> {
    return this.http.post<TuningReadResult>(this.base + '/tuning/devices/' + encodeURIComponent(uuid) + '/read', body, {
      headers: this.jsonHeaders(),
    });
  }

  deviceCommands(uuid: string): Observable<TuningCommandCatalog> {
    return this.http.get<TuningCommandCatalog>(this.base + '/tuning/devices/' + encodeURIComponent(uuid) + '/commands');
  }

  executeCommand(
    uuid: string,
    commandId: string,
    body: unknown
  ): Observable<TuningCommandPreview | TuningCommandResult> {
    return this.http.post<TuningCommandPreview | TuningCommandResult>(
      this.base + '/tuning/devices/' + encodeURIComponent(uuid) + '/commands/' + encodeURIComponent(commandId),
      body,
      { headers: this.jsonHeaders() }
    );
  }

  captureStatus(): Observable<TuningCaptureStatus> {
    return this.http.get<TuningCaptureStatus>(this.base + '/tuning/capture/status');
  }

  captureStart(uuid: string, type: string | null, durationS: number = 300): Observable<TuningCaptureStatus> {
    return this.http.post<TuningCaptureStatus>(
      this.base + '/tuning/capture/start',
      { uuid, type, duration_s: durationS },
      { headers: this.jsonHeaders() }
    );
  }

  captureStop(): Observable<TuningCaptureStatus> {
    return this.http.post<TuningCaptureStatus>(this.base + '/tuning/capture/stop', {}, { headers: this.jsonHeaders() });
  }

  captureDraft(type: string): Observable<TuningCaptureDraft> {
    return this.http.post<TuningCaptureDraft>(
      this.base + '/tuning/capture/draft',
      { type },
      { headers: this.jsonHeaders() }
    );
  }

  private jsonHeaders(): HttpHeaders {
    return new HttpHeaders({ 'Content-Type': 'application/json; charset=utf-8' });
  }

  private download(format: string, source: string, profileId?: string | null): Observable<Download> {
    let params = new HttpParams().set('format', format).set('source', source);
    if (profileId) {
      params = params.set('id', profileId);
    }
    return new Observable<Download>((subscriber) => {
      const request = this.http
        .get(this.base + '/profiles/export', {
          params,
          observe: 'response',
          responseType: 'blob',
        })
        .subscribe(
          (response) => {
            const header = response.headers.get('content-disposition') || '';
            const match = /filename="?([^";]+)"?/i.exec(header);
            const fallback = (profileId || 'meross-profiles') + '.' + (format === 'zip' ? 'zip' : 'yaml');
            subscriber.next({
              blob: response.body as Blob,
              filename: match ? match[1] : fallback,
            });
            subscriber.complete();
          },
          (error) => subscriber.error(error)
        );
      return () => request.unsubscribe();
    });
  }
}
