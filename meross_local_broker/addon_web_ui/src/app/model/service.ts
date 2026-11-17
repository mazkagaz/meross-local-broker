export interface ServiceStatus {
  readonly name: string;
  readonly status: string;
  readonly exitCode: number;
  readonly pid: number;
  readonly description: string;
  readonly logStatus: 'empty' | 'ok' | 'warning' | 'error';
}
