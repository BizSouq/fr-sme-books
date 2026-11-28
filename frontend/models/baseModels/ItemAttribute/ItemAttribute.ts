import type { ListViewSettings } from 'fyo/model/types';
import { FrappeDoc } from 'src/frappe/document';

/**
 * Books Item Attribute, served by Frappe and named by its name: what an
 * article's sizes or colors differ by, like Size, with its values in order.
 */
export class ItemAttribute extends FrappeDoc {
  static override doctype = 'Books Item Attribute';
  static override presentation = {
    label: 'Item Attribute',
    quickEditFields: ['values'],
    fields: { values: { emptyMessage: 'No values' } },
  };

  static getListViewSettings(): ListViewSettings {
    return { columns: ['name'] };
  }
}
