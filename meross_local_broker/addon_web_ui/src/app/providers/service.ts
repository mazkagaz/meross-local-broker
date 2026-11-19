// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { Injectable } from '@angular/core';
import { ServiceStatus } from '@app/model/service';
import { BehaviorSubject, interval, Observable } from 'rxjs';
import { AdminService } from '../services/admin';
import { share, switchMap } from 'rxjs/operators';

@Injectable({
  providedIn: 'root',
})
export class ServiceStore {
  // Internal handlers
  private _services: BehaviorSubject<ServiceStatus[]> = new BehaviorSubject([]);
  private REFRESH_TIME: number = 10000;

  // Exposed observable
  public readonly services: Observable<ServiceStatus[]> = this._services.asObservable();
  public readonly serviceUpdates: Observable<ServiceStatus[]> = interval(this.REFRESH_TIME).pipe(
    switchMap(() => this.serviceUpdate()),
    //takeUntil(this.reload$),
    share()
  );

  constructor(private adminService: AdminService) {
    // Perform a first poll
    this.serviceUpdate().subscribe((services) => this._services.next(services));
  }

  private serviceUpdate(): Observable<ServiceStatus[]> {
    return this.adminService.listServices();
  }

  private fetchServiceLogs(serviceName: string): Observable<string[]> {
    return this.adminService.getServiceLog(serviceName);
  }

  /**
   * Polls the logs of a given service while the returned observable is
   * subscribed. Unsubscribing stops the polling, so only the visible tab of
   * the log page queries the API.
   */
  public followServiceLogs(serviceName: string): Observable<string[]> {
    return new Observable<string[]>((subscriber) => {
      const poll = () => this.fetchServiceLogs(serviceName).subscribe((lines) => subscriber.next(lines));
      poll();
      const timer = interval(this.REFRESH_TIME).subscribe(() => poll());
      return () => timer.unsubscribe();
    });
  }
}
