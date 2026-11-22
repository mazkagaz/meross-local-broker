// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
export interface TuningProfileSummary {
  id: string;
  version: string | null;
  source: string;
  hash: string;
  requires_engine: string | null;
  devices_affected: number;
  override_file: string | null;
}

export interface TuningProfileList {
  revision: string;
  profiles: TuningProfileSummary[];
}

export interface TuningBackup {
  file: string;
  created_at: string;
  hash: string;
}

export interface TuningProfileDetail {
  id: string;
  version: string | null;
  source: string;
  catalog_hash: string;
  override_hash: string | null;
  revision: string;
  yaml: string;
  override_yaml: string | null;
  bundled_yaml: string;
  diff: string;
  devices_affected: number;
  backups: TuningBackup[];
}

export interface TuningValidation {
  valid: boolean;
  profile_id: string | null;
  errors: string[];
  warnings: string[];
  summary: {
    id?: string;
    version?: string;
    requires_engine?: string;
    entities?: Array<{ key: string; platform: string; name: string; channel: number | null }>;
  };
  diff: string;
  diff_base: string | null;
}

export interface TuningSaveResult {
  id: string;
  revision: string;
  override_hash: string;
  diff: string;
  warnings: string[];
}

export interface TuningImportEntry {
  id: string;
  filename: string;
  warnings: string[];
}

export interface TuningImportResult {
  dry_run: boolean;
  revision: string;
  profiles: TuningImportEntry[];
}

export interface TuningSubdevice {
  id: string;
  type: string;
  name: string;
}

export interface TuningDeviceSummary {
  uuid: string;
  name: string;
  type: string;
  sub_type: string | null;
  online: string | null;
  profile: string | null;
  channels: number[];
  subdevices: TuningSubdevice[];
}

export interface TuningEntityRow {
  key: string;
  platform: string;
  name: string | null;
  channel: number | null;
  device: string;
  namespace: string | null;
  fields: string[];
  commands: string[];
}

export interface TuningPollingRow {
  namespace: string;
  scope: string;
  methods: string[];
  strategy: string;
  period_s: number;
  push: boolean;
  response_size: number | null;
}

export interface TuningDeviceState {
  device: {
    uuid: string;
    name: string;
    type: string;
    sub_type: string | null;
    online: string | null;
    last_seen: string | null;
    local_ip: string | null;
    firmware: string | null;
    hardware: string | null;
    channels: number[];
    subdevices: TuningSubdevice[];
  };
  profile: {
    id: string;
    version: string | null;
    source: string;
    hash: string;
    requires_engine: string | null;
  } | null;
  ability: { [key: string]: unknown };
  entities: TuningEntityRow[];
  subdevice_templates: Array<{
    name: string | null;
    match: { [key: string]: unknown };
    entities: TuningEntityRow[];
  }>;
  polling: TuningPollingRow[];
  cache: { [key: string]: unknown };
  errors: string[];
  warnings: string[];
}

export interface TuningPreviewResult {
  profile_id: string;
  namespace: string;
  method: string;
  known_namespace: boolean;
  applied: number;
  ignored: number;
  updates: number;
  messages: number;
  entities: { [key: string]: { [key: string]: unknown } };
  subdevices: { [key: string]: { [key: string]: { [key: string]: unknown } } };
  errors: string[];
  warnings: string[];
}

export interface TuningReadResult {
  uuid: string;
  namespace: string;
  method: string | null;
  ok: boolean;
  header: { [key: string]: unknown };
  payload: { [key: string]: unknown };
  elapsed_ms: number;
  received_at: string;
  profile_id: string;
}

export interface TuningAbilityResult {
  uuid: string;
  count: number;
  namespaces: string[];
}

export interface TuningCommand {
  id: string;
  entity: string;
  name: string | null;
  platform: string;
  command: string;
  namespace: string;
  type: 'number' | 'action';
  unit: string | null;
  min: number | null;
  max: number | null;
  step: number | null;
  value_scale: number | null;
  accepts_value: boolean;
  accepts_channel: boolean;
  channels: number[];
  channel: number | null;
  payload_template: { [key: string]: unknown };
}

export interface TuningCommandCatalog {
  uuid: string;
  profile_id: string;
  online: string | null;
  commands: TuningCommand[];
  namespaces: string[];
  warnings: string[];
}

export interface TuningCommandPreview {
  requires_confirmation: boolean;
  token: string;
  expires_in: number;
  device_uuid: string;
  profile_id: string;
  command: {
    id: string;
    namespace: string;
    channel: number | null;
    value: number | null;
    payload: { [key: string]: unknown };
  };
}

export interface TuningCommandResult {
  ok: boolean;
  error: string | null;
  profile_id: string;
  command: {
    id: string;
    namespace: string;
    channel: number | null;
    value: number | null;
    payload: { [key: string]: unknown };
  };
  result: { [key: string]: unknown };
  before: { [key: string]: unknown };
  after: { [key: string]: unknown };
}

export interface TuningCaptureStatus {
  session_id?: string;
  active?: boolean;
  frames?: number;
  bytes?: number;
  reason?: string | null;
  started_at?: number;
  stopped_at?: number | null;
}

export interface TuningCaptureDraft {
  path: string;
  yaml: string;
  namespaces: number;
  frames: number;
}

export interface TuningAuditEntry {
  at: string;
  action: string;
  profile_id?: string;
  actor?: string;
  revision?: string;
  before_hash?: string | null;
  after_hash?: string | null;
  backup?: string;
}
