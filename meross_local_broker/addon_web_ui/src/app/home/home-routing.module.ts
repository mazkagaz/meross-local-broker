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
    {
      path: 'setup/credentials',
      component: SetupComponent,
      data: { title: marker('Broker access'), section: 'credentials' },
    },
    { path: 'setup/pairer', component: SetupComponent, data: { title: marker('Pairer app'), section: 'pairer' } },
    { path: 'setup/pairing', component: SetupComponent, data: { title: marker('Pair devices'), section: 'pairing' } },
    {
      path: 'setup/home-assistant',
      component: SetupComponent,
      data: { title: marker('Home Assistant'), section: 'home-assistant' },
    },
  ]),
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
  providers: [],
})
export class HomeRoutingModule {}
