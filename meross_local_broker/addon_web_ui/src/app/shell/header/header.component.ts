import { Component } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.scss'],
})
export class HeaderComponent {
  constructor(private router: Router) {}

  get showBackButton(): boolean {
    return this.router.url !== '/home' && this.router.url !== '/';
  }

  backToDevices(): void {
    this.router.navigate(['/home']);
  }
}
