// Modified or added for the MRS100 fork of ha-meross-local-broker (2026-11).
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';

import { YamlEditorComponent } from './yaml-editor.component';

describe('YamlEditorComponent', () => {
  let fixture: ComponentFixture<YamlEditorComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [YamlEditorComponent],
      imports: [FormsModule],
    });
    fixture = TestBed.createComponent(YamlEditorComponent);
    fixture.detectChanges();
  });

  afterEach(() => fixture.destroy());

  it('emits document changes through the control value accessor', () => {
    const component = fixture.componentInstance as any;
    const values: string[] = [];
    component.registerOnChange((value: string) => values.push(value));

    component.view.dispatch({
      changes: { from: 0, to: 0, insert: 'schema_version: 2' },
    });

    expect(values[values.length - 1]).toBe('schema_version: 2');
  });

  it('writes external values into the editor', () => {
    const component = fixture.componentInstance as any;
    component.writeValue('profile:\n  id: test\n');
    expect(component.view.state.doc.toString()).toBe('profile:\n  id: test\n');

    component.writeValue('profile:\n  id: test\n');
    expect(component.view.state.doc.toString()).toBe('profile:\n  id: test\n');
  });

  it('supports the disabled state', () => {
    const component = fixture.componentInstance as any;
    expect(() => component.setDisabledState(true)).not.toThrow();
    expect(() => component.setDisabledState(false)).not.toThrow();
  });
});
