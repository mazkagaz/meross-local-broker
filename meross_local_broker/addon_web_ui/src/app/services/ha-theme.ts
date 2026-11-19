// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
// Upstream: https://github.com/albertogeniola/ha-meross-local-broker (Apache-2.0).
import { Injectable, OnDestroy } from '@angular/core';

const HA_THEME_VARIABLES = [
  '--primary-color',
  '--accent-color',
  '--app-header-background-color',
  '--app-header-text-color',
  '--primary-background-color',
  '--secondary-background-color',
  '--primary-text-color',
  '--secondary-text-color',
  '--disabled-text-color',
  '--divider-color',
  '--card-background-color',
  '--ha-card-background',
  '--ha-card-border-radius',
  '--ha-card-border-color',
  '--ha-card-border-width',
  '--ha-card-box-shadow',
  '--error-color',
  '--warning-color',
  '--success-color',
  '--text-primary-color',
  '--code-font-family',
];

/**
 * The add-on runs inside a Home Assistant ingress iframe on the same origin.
 * CSS variables do not cross the iframe boundary, so copy the active HA theme
 * variables into this document. Standalone installations keep the fallbacks.
 */
@Injectable({
  providedIn: 'root',
})
export class HaThemeService implements OnDestroy {
  private observer?: MutationObserver;
  private applyTimer?: number;

  start(): void {
    this.apply();
    window.addEventListener('storage', this.scheduleApply);

    const parentWindow = this.parentWindow();
    if (!parentWindow) {
      return;
    }

    const parentDocument = parentWindow.document;
    this.observer = new MutationObserver(this.scheduleApply);
    [parentDocument.documentElement, parentDocument.body, parentDocument.querySelector('home-assistant')]
      .filter((element): element is HTMLElement => element !== null)
      .forEach((element) =>
        this.observer.observe(element, {
          attributes: true,
          attributeFilter: ['style', 'class', 'theme', 'dark', 'color-scheme'],
        })
      );
  }

  ngOnDestroy(): void {
    window.removeEventListener('storage', this.scheduleApply);
    this.observer?.disconnect();
    if (this.applyTimer) {
      window.clearTimeout(this.applyTimer);
    }
  }

  private readonly scheduleApply = (): void => {
    if (this.applyTimer) {
      window.clearTimeout(this.applyTimer);
    }
    this.applyTimer = window.setTimeout(() => this.apply(), 100);
  };

  private apply(): void {
    const parentWindow = this.parentWindow();
    if (!parentWindow) {
      return;
    }

    const parentDocument = parentWindow.document;
    const elements = [
      parentDocument.documentElement,
      parentDocument.body,
      parentDocument.querySelector('home-assistant'),
    ].filter((element): element is HTMLElement => element !== null);
    const styles = elements.map((element) => parentWindow.getComputedStyle(element));
    const root = document.documentElement;

    for (const name of HA_THEME_VARIABLES) {
      const value = styles
        .map((style) => style.getPropertyValue(name).trim())
        .find((candidate) => candidate.length > 0);
      if (value) {
        root.style.setProperty(name, value);
      }
    }

    const colorScheme = styles
      .map((style) => style.getPropertyValue('color-scheme').trim())
      .find((value) => value.length > 0 && value !== 'normal');
    if (colorScheme) {
      root.style.setProperty('color-scheme', colorScheme);
    }
  }

  private parentWindow(): Window | null {
    if (window.parent === window) {
      return null;
    }
    try {
      // Touching document throws for a cross-origin parent.
      return window.parent.document ? window.parent : null;
    } catch {
      return null;
    }
  }
}
