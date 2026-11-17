import { Component, OnDestroy } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Subscription } from 'rxjs';

type SetupSection = 'setup' | 'pair-devices';

@Component({
  selector: 'app-setup',
  templateUrl: './setup.component.html',
  styleUrls: ['./setup.component.scss'],
})
export class SetupComponent implements OnDestroy {
  section: SetupSection;
  private subscription: Subscription;

  constructor(route: ActivatedRoute) {
    this.subscription = route.data.subscribe((data) => (this.section = data.section as SetupSection));
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }
}
