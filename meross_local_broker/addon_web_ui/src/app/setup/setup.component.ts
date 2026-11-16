import { Component } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

type SetupSection = 'setup' | 'pair-devices';

@Component({
  selector: 'app-setup',
  templateUrl: './setup.component.html',
  styleUrls: ['./setup.component.scss'],
})
export class SetupComponent {
  readonly section: SetupSection;

  constructor(route: ActivatedRoute) {
    this.section = route.snapshot.data.section as SetupSection;
  }
}
