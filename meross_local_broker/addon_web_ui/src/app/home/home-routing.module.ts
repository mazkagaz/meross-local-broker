import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { marker } from '@biesbjerg/ngx-translate-extract-marker';
import { HomeComponent } from './home.component';
import { Shell } from '@app/shell/shell.service';
import { WizardComponent } from '@app/wizard/wizard.component';
import { SetupComponent } from '@app/setup/setup.component';

const routes: Routes = [
  Shell.childRoutes([
    { path: '', redirectTo: '/home', pathMatch: 'full' },
    { path: 'home', component: HomeComponent, data: { title: marker('Home') } },
    { path: 'wizard', component: WizardComponent, data: { title: marker('Wizard') } },
    { path: 'setup', component: SetupComponent, data: { title: marker('Setup'), section: 'setup' } },
    {
      path: 'pair-devices',
      component: SetupComponent,
      data: { title: marker('Pair devices'), section: 'pair-devices' },
    },
  ]),
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
  providers: [],
})
export class HomeRoutingModule {}
