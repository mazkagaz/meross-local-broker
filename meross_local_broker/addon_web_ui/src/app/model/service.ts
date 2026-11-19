// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
export interface ServiceStatus {
  readonly name: string;
  readonly status: string;
  readonly exitCode: number;
  readonly pid: number;
  readonly description: string;
  readonly logStatus: 'empty' | 'ok' | 'warning' | 'error';
}
