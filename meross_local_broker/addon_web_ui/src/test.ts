/*
 * Prepare environment for unit tests.
 * This file is required by karma.conf.js and loads recursively all the .spec and framework files.
 */

import 'zone.js/testing';
import { getTestBed } from '@angular/core/testing';
import { BrowserDynamicTestingModule, platformBrowserDynamicTesting } from '@angular/platform-browser-dynamic/testing';

// Karma does not load assets/env.js, so provide the runtime configuration
// that environment.ts expects before any spec is loaded.
(window as any).__env = {
  production: false,
  version: 'test',
  defaultLanguage: 'en-US',
  supportedLanguages: ['en-US'],
  backend: '',
};

// First, initialize the Angular testing environment.
getTestBed().initTestEnvironment(BrowserDynamicTestingModule, platformBrowserDynamicTesting(), {
  teardown: { destroyAfterEach: false },
});
