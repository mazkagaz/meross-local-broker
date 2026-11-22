// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { environment } from '@env/environment';
import { TuningService, tuningErrorMessage } from './tuning.service';

describe('TuningService', () => {
  let service: TuningService;
  let http: HttpTestingController;
  const base = environment.backend + '/_admin_';

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(TuningService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists profiles', () => {
    let revision = '';
    service.listProfiles().subscribe((result) => (revision = result.revision));
    const request = http.expectOne(base + '/profiles');
    expect(request.request.method).toBe('GET');
    request.flush({ revision: 'rev-1', profiles: [] });
    expect(revision).toBe('rev-1');
  });

  it('posts validation with the optional profile id', () => {
    service.validate('schema_version: 2', 'meross.mod').subscribe();
    const request = http.expectOne(base + '/profiles/validate');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      yaml: 'schema_version: 2',
      profile_id: 'meross.mod',
    });
    request.flush({ valid: true, profile_id: 'meross.mod' });
  });

  it('saves an override with the expected hash', () => {
    service.saveOverride('meross.mod', 'profile: {}', 'abc').subscribe();
    const request = http.expectOne(base + '/profiles/meross.mod/override');
    expect(request.request.method).toBe('PUT');
    expect(request.request.body).toEqual({
      yaml: 'profile: {}',
      expected_hash: 'abc',
    });
    request.flush({ id: 'meross.mod', revision: 'r' });
  });

  it('imports a file as multipart with a dry-run flag', () => {
    const file = new File(['schema_version: 2'], 'profiles.zip', {
      type: 'application/zip',
    });
    service.importFile(file, true).subscribe();
    const request = http.expectOne(
      (candidate) => candidate.url === base + '/profiles/import' && candidate.params.get('dry_run') === 'true'
    );
    expect(request.request.method).toBe('POST');
    expect(request.request.body instanceof FormData).toBeTrue();
    request.flush({ dry_run: true, revision: 'r', profiles: [] });
  });

  it('downloads a profile with the server filename', () => {
    let filename = '';
    let size = 0;
    service.downloadProfiles('yaml', 'effective', 'meross.mod').subscribe((download) => {
      filename = download.filename;
      size = download.blob.size;
    });
    const request = http.expectOne(
      (candidate) =>
        candidate.url === base + '/profiles/export' &&
        candidate.params.get('format') === 'yaml' &&
        candidate.params.get('id') === 'meross.mod'
    );
    request.flush(new Blob(['abc']), {
      headers: { 'Content-Disposition': 'attachment; filename="meross.mod.yaml"' },
    });
    expect(filename).toBe('meross.mod.yaml');
    expect(size).toBe(3);
  });

  it('reads a device with a timeout', () => {
    service.readDevice('dev-1', { namespace: 'Appliance.System.All', timeout_ms: 2000 }).subscribe();
    const request = http.expectOne(base + '/tuning/devices/dev-1/read');
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({
      namespace: 'Appliance.System.All',
      timeout_ms: 2000,
    });
    request.flush({ ok: true });
  });

  it('lists and executes typed commands', () => {
    service.deviceCommands('dev-1').subscribe();
    const catalogRequest = http.expectOne(base + '/tuning/devices/dev-1/commands');
    expect(catalogRequest.request.method).toBe('GET');
    catalogRequest.flush({ uuid: 'dev-1', commands: [] });

    service
      .executeCommand('dev-1', 'cover.set_position', {
        channel: 0,
        value: 42,
      })
      .subscribe();
    const commandRequest = http.expectOne(base + '/tuning/devices/dev-1/commands/cover.set_position');
    expect(commandRequest.request.method).toBe('POST');
    expect(commandRequest.request.body).toEqual({
      channel: 0,
      value: 42,
    });
    commandRequest.flush({ requires_confirmation: true, token: 'tok' });
  });

  it('extracts API and rate-limit error messages', () => {
    expect(tuningErrorMessage({ error: { error: 'device is offline' } })).toBe('device is offline');
    expect(tuningErrorMessage({ error: { error: 'wait', retry_after: 2 } })).toBe('wait (retry in 2s)');
  });
});
