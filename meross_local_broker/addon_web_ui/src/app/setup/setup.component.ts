// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
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
