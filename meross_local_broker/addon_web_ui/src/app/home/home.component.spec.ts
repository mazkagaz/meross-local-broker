// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

import { CoreModule } from '@core';
import { SharedModule } from '@shared';
import { MaterialModule } from '@app/material.module';
import { HomeComponent } from './home.component';
import { QuoteService } from './quote.service';
import { ServiceLogsPageComponent } from '@app/logs/service-logs-page.component';
import { provideHttpClient, withInterceptorsFromDi, withXhr } from '@angular/common/http';

describe('HomeComponent', () => {
  let component: HomeComponent;
  let fixture: ComponentFixture<HomeComponent>;

  beforeEach(
    waitForAsync(() => {
      TestBed.configureTestingModule({
        declarations: [HomeComponent, ServiceLogsPageComponent],
        imports: [BrowserAnimationsModule, MaterialModule, CoreModule, SharedModule],
        providers: [QuoteService, provideHttpClient(withXhr(), withInterceptorsFromDi()), provideHttpClientTesting()],
      }).compileComponents();
    })
  );

  beforeEach(() => {
    localStorage.removeItem('broker-advanced');
    fixture = TestBed.createComponent(HomeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('shows the profile column only in advanced mode', () => {
    const device: any = {
      profile: {
        id: 'meross.mrs100',
        version: '2026.11.2',
        source: 'bundled',
        hash: 'h',
      },
    };
    expect(component.profileVersion(device)).toBe('2026.11.2');
    expect(component.isCustomProfile(device)).toBeFalse();
    expect(component.profileTooltip(device)).toBe('meross.mrs100 · bundled');
    expect(component.profileVersion({ profile: null } as any)).toBe('—');
    expect(component.profileTooltip({ profile: null } as any)).toBe('No matched profile');

    (component as any).advanced = true;
    (component as any).applyColumns();
    expect(component.devicesColumns).toContain('profile');

    (component as any).advanced = false;
    (component as any).applyColumns();
    expect(component.devicesColumns).not.toContain('profile');
  });

  it('marks an override profile as custom', () => {
    const device: any = {
      profile: {
        id: 'meross.mod',
        version: '2',
        source: 'override',
        hash: 'h',
      },
    };
    expect(component.isCustomProfile(device)).toBeTrue();
    expect(component.profileTooltip(device)).toBe('meross.mod · override');
  });
});
