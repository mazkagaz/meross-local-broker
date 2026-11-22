// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { basicSetup, EditorView } from 'codemirror';
import { Compartment } from '@codemirror/state';
import { yaml } from '@codemirror/lang-yaml';

@Component({
  selector: 'app-yaml-editor',
  template: '<div #host class="editor-host"></div>',
  styles: [
    `
      :host {
        display: block;
      }
      .editor-host {
        border: 1px solid rgba(0, 0, 0, 0.12);
        border-radius: 4px;
        overflow: hidden;
      }
      :host ::ng-deep .cm-editor {
        height: 360px;
        font-size: 13px;
      }
      :host ::ng-deep .cm-scroller {
        overflow: auto;
      }
    `,
  ],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: YamlEditorComponent,
      multi: true,
    },
  ],
})
export class YamlEditorComponent implements AfterViewInit, OnDestroy, ControlValueAccessor {
  @ViewChild('host', { static: true }) host: ElementRef<HTMLDivElement>;

  private view: EditorView | null = null;
  private pending = '';
  private writeGuard = false;
  private editable = new Compartment();
  private onChange: (value: string) => void;
  private onTouched: () => void;

  constructor() {
    this.onChange = () => {};
    this.onTouched = () => {};
  }

  ngAfterViewInit(): void {
    this.view = new EditorView({
      doc: this.pending,
      extensions: [
        basicSetup,
        yaml(),
        this.editable.of(EditorView.editable.of(true)),
        EditorView.updateListener.of((update) => {
          if (update.docChanged && !this.writeGuard) {
            this.onChange(update.state.doc.toString());
          }
        }),
      ],
      parent: this.host.nativeElement,
    });
  }

  ngOnDestroy(): void {
    if (this.view) {
      this.view.destroy();
      this.view = null;
    }
  }

  writeValue(value: string | null): void {
    const text = value || '';
    this.pending = text;
    if (this.view) {
      if (this.view.state.doc.toString() === text) {
        return;
      }
      this.writeGuard = true;
      this.view.dispatch({
        changes: {
          from: 0,
          to: this.view.state.doc.length,
          insert: text,
        },
      });
      this.writeGuard = false;
    }
  }

  registerOnChange(fn: (value: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    if (this.view) {
      this.view.dispatch({
        effects: this.editable.reconfigure(EditorView.editable.of(!isDisabled)),
      });
    }
  }
}
