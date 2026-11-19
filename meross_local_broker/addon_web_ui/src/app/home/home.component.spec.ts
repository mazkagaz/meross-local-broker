// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { waitForAsync, ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { FlexLayoutModule } from '@angular/flex-layout';

import { CoreModule } from '@core';
import { SharedModule } from '@shared';
import { MaterialModule } from '@app/material.module';
import { HomeComponent } from './home.component';
import { QuoteService } from './quote.service';
import { ServiceLogsPageComponent } from '@app/logs/service-logs-page.component';

describe('HomeComponent', () => {
  let component: HomeComponent;
  let fixture: ComponentFixture<HomeComponent>;

  beforeEach(
    waitForAsync(() => {
      TestBed.configureTestingModule({
        imports: [
          BrowserAnimationsModule,
          FlexLayoutModule,
          MaterialModule,
          CoreModule,
          SharedModule,
          HttpClientTestingModule,
        ],
        declarations: [HomeComponent, ServiceLogsPageComponent],
        providers: [QuoteService],
      }).compileComponents();
    })
  );

  beforeEach(() => {
    fixture = TestBed.createComponent(HomeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
