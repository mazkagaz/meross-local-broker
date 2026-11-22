// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { marker } from '@biesbjerg/ngx-translate-extract-marker';

import { TuningComponent } from './tuning.component';

const routes: Routes = [
  {
    path: '',
    component: TuningComponent,
    data: { title: marker('Tuning') },
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class TuningRoutingModule {}
