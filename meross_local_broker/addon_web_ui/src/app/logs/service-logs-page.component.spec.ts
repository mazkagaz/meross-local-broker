// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { ComponentFixture, TestBed, waitForAsync } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { MatSnackBar as MatSnackBar } from '@angular/material/snack-bar';
import { Observable } from 'rxjs';

import { MaterialModule } from '@app/material.module';
import { ServiceStatus } from '@app/model/service';
import { ServiceStore } from '@app/providers/service';
import { ServiceLogsPageComponent } from './service-logs-page.component';

const SERVICES: ServiceStatus[] = [
  { name: 'MQTT Service', status: 'RUNNING', exitCode: 0, pid: 1, description: '', logStatus: 'ok' },
  { name: 'Local API', status: 'RUNNING', exitCode: 0, pid: 2, description: '', logStatus: 'ok' },
  { name: 'Local Agent', status: 'RUNNING', exitCode: 0, pid: 3, description: '', logStatus: 'ok' },
  { name: 'Web UI Proxy', status: 'RUNNING', exitCode: 0, pid: 4, description: '', logStatus: 'ok' },
];

class ServiceStoreStub {
  logs = new Map<string, string[]>();
  active = new Map<string, number>();

  followServiceLogs(name: string): Observable<string[]> {
    return new Observable<string[]>((subscriber) => {
      this.active.set(name, (this.active.get(name) || 0) + 1);
      subscriber.next(this.logs.get(name) || []);
      return () => this.active.set(name, (this.active.get(name) || 0) - 1);
    });
  }
}

describe('ServiceLogsPageComponent', () => {
  let component: ServiceLogsPageComponent;
  let fixture: ComponentFixture<ServiceLogsPageComponent>;
  let store: ServiceStoreStub;

  beforeEach(
    waitForAsync(() => {
      store = new ServiceStoreStub();
      TestBed.configureTestingModule({
        imports: [BrowserAnimationsModule, MaterialModule, FormsModule],
        declarations: [ServiceLogsPageComponent],
        providers: [
          { provide: ServiceStore, useValue: store },
          { provide: MatSnackBar, useValue: { open: (): void => undefined } },
        ],
      }).compileComponents();
    })
  );

  function create(initialService: string): void {
    fixture = TestBed.createComponent(ServiceLogsPageComponent);
    component = fixture.componentInstance;
    component.services = SERVICES;
    component.initialService = initialService;
    fixture.detectChanges();
  }

  it('opens on the clicked service tab', () => {
    create('Local Agent');
    expect(component.selectedIndex).toBe(2);
    expect(store.active.get('Local Agent')).toBe(1);
  });

  it('stops polling the previous tab when switching', () => {
    create('MQTT Service');
    component.selectTab(1);

    expect(store.active.get('MQTT Service')).toBe(0);
    expect(store.active.get('Local API')).toBe(1);
  });

  it('filters lines by case-insensitive search', () => {
    store.logs.set('Local API', ['INFO ready', 'ERROR device failed', 'WARNING slow']);
    create('Local API');

    component.searchText = 'error';
    component.applyFilters();

    expect(component.logLines.length).toBe(1);
    expect(component.logLines[0].segments.some((segment) => segment.match)).toBe(true);
  });

  it('filters lines by level', () => {
    store.logs.set('Local API', ['INFO ready', 'ERROR device failed', 'WARNING slow']);
    create('Local API');

    component.levelFilter = 'warning';
    component.applyFilters();

    expect(component.logLines.length).toBe(1);
    expect(component.logLines[0].severity).toBe('warning');
  });

  it('emits closed when going back', () => {
    create('MQTT Service');
    spyOn(component.closed, 'emit');

    component.close();

    expect(component.closed.emit).toHaveBeenCalled();
  });
});
