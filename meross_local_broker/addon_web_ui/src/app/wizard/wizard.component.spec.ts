import { NO_ERRORS_SCHEMA } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MatSnackBar as MatSnackBar } from '@angular/material/snack-bar';
import { of } from 'rxjs';

import { AdminService } from '@app/services/admin';
import { WizardComponent } from './wizard.component';

describe('WizardComponent', () => {
  let component: WizardComponent;
  let fixture: ComponentFixture<WizardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [WizardComponent],
      providers: [
        {
          provide: AdminService,
          useValue: {
            getConfiguration: () => of(null),
            getEvents: () => of([]),
            updateConfiguration: () => of(null),
          },
        },
        { provide: MatSnackBar, useValue: { open: (): void => undefined } },
      ],
      schemas: [NO_ERRORS_SCHEMA],
    }).compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(WizardComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
