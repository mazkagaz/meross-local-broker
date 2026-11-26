// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { Component, OnInit, ChangeDetectionStrategy } from '@angular/core';
import { QRCodeElementType, QRCodeErrorCorrectionLevel } from 'angularx-qrcode';
import { AdminService } from '@app/services/admin';
import { User } from '@app/model/user';
import { UntypedFormBuilder } from '@angular/forms';
import { Validators } from '@angular/forms';
import { Output, EventEmitter } from '@angular/core';
import { Configuration } from '@app/model/configuration';

@Component({
  selector: 'configuration-account',
  templateUrl: './account.component.html',
  styleUrls: ['./account.component.scss'],
  changeDetection: ChangeDetectionStrategy.Eager,
  standalone: false,
})
export class AccountComponent implements OnInit {
  accountForm = this.fb.group({
    email: ['', Validators.required],
    password: ['', Validators.required],
  });

  @Output() configurationUpdatedEvent = new EventEmitter<string>();

  public hidePassword: boolean = true;
  public processing: boolean = false;

  public elementType: QRCodeElementType = 'img';
  public correctionLevel: QRCodeErrorCorrectionLevel = 'M';
  public encodedAccountLoginData: string = null;
  public reconfigure: boolean = false;

  public configuration: Configuration = null;

  constructor(private fb: UntypedFormBuilder, private adminService: AdminService) {}

  private loadConfiguration(conf: Configuration | null) {
    if (!conf) {
      this.configuration = null;
      this.reconfigure = true;
    } else {
      // Fetch configured data
      this.configuration = conf;
      this.accountForm.controls.password.setValue(null);
      this.accountForm.controls.email.setValue(conf.email);
    }
  }

  ngOnInit(): void {
    this.adminService.getConfiguration().subscribe((configuration: Configuration) => {
      this.loadConfiguration(configuration);
    });
  }

  editConfiguration(reconfigure: boolean): void {
    if (reconfigure) {
      this.adminService.getConfiguration().subscribe(
        (configuration: Configuration) => {
          this.loadConfiguration(configuration);
        },
        (error) => {}
      );
    }
    this.reconfigure = reconfigure;
  }

  onSubmit(): void {
    this.processing = true;
    this.adminService
      .updateConfiguration(this.accountForm.controls.email.value, this.accountForm.controls.password.value)
      .subscribe((configuration: Configuration) => {
        if (configuration != null) {
          this.loadConfiguration(configuration);
          this.editConfiguration(false);
          this.configurationUpdatedEvent.emit('ACCOUNT_CONFIGURED');
        }
        this.processing = false;
      });
  }
}
