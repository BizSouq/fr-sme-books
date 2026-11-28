import type { ListViewSettings } from 'fyo/model/types';
import { FrappeDoc } from 'src/frappe/document';

/**
 * Books Label Template, served by Frappe and named by its name: a barcode
 * label's size, paper and layout, which the label designer edits.
 */
export class LabelTemplate extends FrappeDoc {
  static override doctype = 'Books Label Template';
  static override presentation = { label: 'Label Design' };

  static getListViewSettings(): ListViewSettings {
    return {
      formRoute: (name) => `/label-designer/${encodeURIComponent(name)}`,
      columns: ['name', 'paper', 'label_width', 'label_height', 'is_default'],
    };
  }
}
