import { t } from 'fyo';
import { call } from 'src/web/api';

/**
 * Barcode labels: a template lays out an item's name, price, barcode, size and
 * color on a label of a set size, and a sheet places the labels on paper, one
 * label a page on a label printer's roll, or rows of them on an A4 sheet.
 * Lengths are millimetres, as label stock is sold; font sizes are points.
 */

const API = 'frappe_books.inventory.labels';
export const LABEL_DOCTYPE = 'Books Label Template';

export type Paper = 'Label Printer' | 'A4 Sheet';
export type Align = 'left' | 'center' | 'right';

export interface LabelElement {
  id: string;
  /** What it shows: a field of the item, `attribute:<name>`, `barcode` or `text`. */
  field: string;
  /** The text of a `text` element, or what a field's value follows, like `MRP`. */
  text?: string;
  x: number;
  y: number;
  width: number;
  height: number;
  fontSize: number;
  bold?: boolean;
  align?: Align;
  /** A barcode's digits under its bars. */
  showNumber?: boolean;
  /** Numbers in Bangla digits, like ৳ ১,২৫০. */
  banglaDigits?: boolean;
  /** A price without its currency sign. */
  hideCurrency?: boolean;
}

export interface LabelSheet {
  paper: Paper;
  label_width: number;
  label_height: number;
  columns: number;
  column_gap: number;
  row_gap: number;
  margin_top: number;
  margin_left: number;
}

export interface LabelTemplate extends LabelSheet {
  name?: string;
  template_name: string;
  is_default?: number;
  elements: LabelElement[];
}

/** What a label prints for one item. */
export interface LabelData {
  item_code: string;
  item_name: string;
  /** The article's name for a size or color, else the item's name. */
  article_name?: string;
  barcode?: string;
  price?: number;
  uom?: string;
  item_group?: string;
  batch_no?: string;
  company?: string;
  /** A size or color's values, like { Size: '42', Color: 'Black' }. */
  attributes: Record<string, string>;
}

/** An item to print, with how many labels. */
export interface LabelRow extends LabelData {
  qty: number;
}

export interface LabelField {
  field: string;
  label: string;
  icon: string;
}

/** The fields a label can show, besides each size or color attribute. */
export function getLabelFields(attributes: string[] = []): LabelField[] {
  return [
    { field: 'item_name', label: t`Item name`, icon: 'lucide-type' },
    { field: 'price', label: t`Price`, icon: 'lucide-banknote' },
    { field: 'barcode', label: t`Barcode`, icon: 'lucide-barcode' },
    { field: 'variant', label: t`Size and color`, icon: 'lucide-ruler' },
    ...attributes.map((attribute) => ({
      field: `attribute:${attribute}`,
      label: attribute,
      icon: 'lucide-tag',
    })),
    { field: 'full_name', label: t`Name with size`, icon: 'lucide-text' },
    { field: 'item_code', label: t`Item code`, icon: 'lucide-hash' },
    { field: 'company', label: t`Shop name`, icon: 'lucide-store' },
    { field: 'item_group', label: t`Item group`, icon: 'lucide-folder' },
    { field: 'uom', label: t`Unit`, icon: 'lucide-box' },
    { field: 'batch_no', label: t`Batch`, icon: 'lucide-layers' },
    { field: 'text', label: t`Your own text`, icon: 'lucide-pencil-line' },
  ];
}

export function getFieldLabel(field: string, attributes: string[] = []) {
  return (
    getLabelFields(attributes).find((option) => option.field === field)
      ?.label ?? field.replace(/^attribute:/, '')
  );
}

export interface LabelPreset {
  key: string;
  label: string;
  sheet: LabelSheet;
}

const roll = (
  width: number,
  height: number,
  columns = 1,
  gap = 0
): LabelSheet => ({
  paper: 'Label Printer',
  label_width: width,
  label_height: height,
  columns,
  column_gap: gap,
  row_gap: 0,
  margin_top: 0,
  margin_left: 0,
});

const a4 = (
  width: number,
  height: number,
  columns: number,
  [top, left, columnGap, rowGap]: number[]
): LabelSheet => ({
  paper: 'A4 Sheet',
  label_width: width,
  label_height: height,
  columns,
  column_gap: columnGap,
  row_gap: rowGap,
  margin_top: top,
  margin_left: left,
});

/** Label stock that shops buy, by how its box names it. */
export function getLabelPresets(): LabelPreset[] {
  return [
    {
      key: 'roll-38x25',
      label: t`Label printer, 38 × 25 mm`,
      sheet: roll(38, 25),
    },
    {
      key: 'roll-50x25',
      label: t`Label printer, 50 × 25 mm`,
      sheet: roll(50, 25),
    },
    {
      key: 'roll-40x30',
      label: t`Label printer, 40 × 30 mm`,
      sheet: roll(40, 30),
    },
    {
      key: 'roll-50x30',
      label: t`Label printer, 50 × 30 mm`,
      sheet: roll(50, 30),
    },
    {
      key: 'roll-60x40',
      label: t`Label printer, 60 × 40 mm`,
      sheet: roll(60, 40),
    },
    {
      key: 'roll-2x33x25',
      label: t`Label printer, 2 across, 33 × 25 mm`,
      sheet: roll(33, 25, 2, 2),
    },
    {
      key: 'a4-65',
      label: t`A4 sheet, 65 labels, 38.1 × 21.2 mm`,
      sheet: a4(38.1, 21.2, 5, [10.7, 4.7, 2.5, 0]),
    },
    {
      key: 'a4-40',
      label: t`A4 sheet, 40 labels, 52.5 × 29.7 mm`,
      sheet: a4(52.5, 29.7, 4, [0, 0, 0, 0]),
    },
    {
      key: 'a4-24',
      label: t`A4 sheet, 24 labels, 70 × 37 mm`,
      sheet: a4(70, 37, 3, [0.5, 0, 0, 0]),
    },
  ];
}

/** The preset the sheet is, or undefined for a size of the shop's own. */
export function findPreset(sheet: LabelSheet): LabelPreset | undefined {
  const keys: (keyof LabelSheet)[] = [
    'paper',
    'label_width',
    'label_height',
    'columns',
    'column_gap',
    'row_gap',
    'margin_top',
    'margin_left',
  ];
  return getLabelPresets().find((preset) =>
    keys.every((key) => preset.sheet[key] === sheet[key])
  );
}

let lastId = 0;
export function newElementId(): string {
  lastId += 1;
  return `el${Date.now().toString(36)}${lastId}`;
}

/** Name, size and color, barcode and price, laid out for the label's size. */
export function getDefaultElements(
  width: number,
  height: number
): LabelElement[] {
  const pad = Math.min(1.5, width * 0.04);
  const inner = width - pad * 2;
  // Laid out on a 38 × 25 mm label, then scaled to this one.
  const base: Omit<LabelElement, 'id'>[] = [
    {
      field: 'item_name',
      x: 0,
      y: 1,
      width: 1,
      height: 4,
      fontSize: 7,
      bold: true,
      align: 'center',
    },
    {
      field: 'variant',
      x: 0,
      y: 5,
      width: 1,
      height: 3.5,
      fontSize: 6.5,
      align: 'center',
    },
    {
      field: 'barcode',
      x: 0.03,
      y: 8.5,
      width: 0.94,
      height: 10.5,
      fontSize: 6,
      showNumber: true,
      align: 'center',
    },
    {
      field: 'price',
      x: 0,
      y: 19.5,
      width: 1,
      height: 4.5,
      fontSize: 9,
      bold: true,
      align: 'center',
    },
  ];
  const scaleY = height / 25;
  const scaleFont = Math.min(width / 38, scaleY);
  return base.map((element) => ({
    ...element,
    id: newElementId(),
    x: round(pad + element.x * inner),
    width: round(element.width * inner),
    y: round(element.y * scaleY),
    height: round(element.height * scaleY),
    fontSize: round(element.fontSize * scaleFont, 1),
  }));
}

export function getNewTemplate(name = ''): LabelTemplate {
  const sheet = getLabelPresets()[0].sheet;
  return {
    template_name: name,
    ...sheet,
    elements: getDefaultElements(sheet.label_width, sheet.label_height),
  };
}

/**
 * The elements moved and sized to a label of another size, each keeping its
 * place and share of the label, its text sized by the smaller change.
 */
export function scaleElements(
  elements: LabelElement[],
  from: { width: number; height: number },
  to: { width: number; height: number }
): LabelElement[] {
  if (!from.width || !from.height) {
    return elements;
  }

  const sx = to.width / from.width;
  const sy = to.height / from.height;
  const sf = Math.min(sx, sy);
  return elements.map((element) => ({
    ...element,
    x: round(element.x * sx),
    width: round(element.width * sx),
    y: round(element.y * sy),
    height: round(element.height * sy),
    fontSize: round(Math.max(4, element.fontSize * sf), 1),
  }));
}

/** Keeps an element on its label, and at least 2 mm across. */
export function clampElement(
  element: LabelElement,
  sheet: Pick<LabelSheet, 'label_width' | 'label_height'>
): LabelElement {
  const width = clamp(element.width, 2, sheet.label_width);
  const height = clamp(element.height, 2, sheet.label_height);
  return {
    ...element,
    width,
    height,
    x: clamp(element.x, 0, sheet.label_width - width),
    y: clamp(element.y, 0, sheet.label_height - height),
  };
}

export interface PageLayout {
  pageWidth: number;
  pageHeight: number;
  /** Labels on one page. */
  perPage: number;
  rows: number;
  columns: number;
}

const A4 = { width: 210, height: 297 };

/** The paper's page and how many labels it holds. */
export function getPageLayout(sheet: LabelSheet): PageLayout {
  const columns = Math.max(1, Math.floor(sheet.columns) || 1);
  if (sheet.paper === 'A4 Sheet') {
    const rows = Math.max(
      1,
      Math.floor(
        (A4.height - sheet.margin_top + sheet.row_gap + 0.01) /
          (sheet.label_height + sheet.row_gap)
      )
    );
    return {
      pageWidth: A4.width,
      pageHeight: A4.height,
      perPage: rows * columns,
      rows,
      columns,
    };
  }

  // A roll prints a row of labels a page: the printer feeds to the next gap.
  return {
    pageWidth: round(
      columns * sheet.label_width + (columns - 1) * sheet.column_gap,
      2
    ),
    pageHeight: sheet.label_height,
    perPage: columns,
    rows: 1,
    columns,
  };
}

/** Where a page's nth label sits, from the page's top left. */
export function getLabelPosition(
  sheet: LabelSheet,
  index: number,
  layout = getPageLayout(sheet)
): { left: number; top: number } {
  const column = index % layout.columns;
  const row = Math.floor(index / layout.columns);
  return {
    left: round(
      sheet.margin_left + column * (sheet.label_width + sheet.column_gap),
      2
    ),
    top: round(
      sheet.margin_top + row * (sheet.label_height + sheet.row_gap),
      2
    ),
  };
}

/**
 * The labels page by page: each row as many times as its quantity, after
 * `skip` empty places, for an A4 sheet whose first labels were used already.
 */
export function getPages<T extends { qty: number }>(
  rows: T[],
  perPage: number,
  skip = 0
): (T | null)[][] {
  const labels: (T | null)[] = Array(Math.max(0, Math.floor(skip))).fill(null);
  for (const row of rows) {
    const qty = Math.max(0, Math.floor(row.qty));
    for (let i = 0; i < qty; i++) {
      labels.push(row);
    }
  }

  const pages: (T | null)[][] = [];
  for (let i = 0; i < labels.length; i += perPage) {
    pages.push(labels.slice(i, i + perPage));
  }

  if (pages.length && pages.every((page) => page.every((label) => !label))) {
    return [];
  }

  return pages;
}

export function countLabels(rows: { qty: number }[]): number {
  return rows.reduce(
    (total, row) => total + Math.max(0, Math.floor(row.qty)),
    0
  );
}

const BANGLA_DIGITS = '০১২৩৪৫৬৭৮৯';

export function toBanglaDigits(text: string): string {
  return text.replace(/\d/g, (digit) => BANGLA_DIGITS[Number(digit)]);
}

export interface PriceFormat {
  /** The number in the shop's number format, like 1,250.50. */
  formatNumber: (value: number, precision: number) => string;
  /** The currency's sign, like ৳. */
  symbol?: string;
}

/** A price as labels show it: whole amounts without decimals, after the currency sign. */
export function formatLabelPrice(
  value: number,
  element: Pick<LabelElement, 'hideCurrency' | 'banglaDigits'>,
  format: PriceFormat
): string {
  const precision = Number.isInteger(Math.round(value * 100) / 100) ? 0 : 2;
  let text = format.formatNumber(value, precision);
  if (!element.hideCurrency && format.symbol) {
    text = `${format.symbol}${text}`;
  }

  return element.banglaDigits ? toBanglaDigits(text) : text;
}

/** What a text element shows for the item: its value after the element's own text. */
export function getElementText(
  element: LabelElement,
  data: LabelData,
  format: PriceFormat
): string {
  if (element.field === 'text') {
    return digits(element.text ?? '');
  }

  const value = getFieldValue(element, data, format);
  if (!value) {
    return '';
  }

  const prefix = element.text?.trim();
  return digits(prefix ? `${prefix} ${value}` : value);

  function digits(text: string) {
    return element.banglaDigits ? toBanglaDigits(text) : text;
  }
}

function getFieldValue(
  element: LabelElement,
  data: LabelData,
  format: PriceFormat
): string {
  const { field } = element;
  if (field === 'price') {
    return typeof data.price === 'number'
      ? formatLabelPrice(
          data.price,
          { ...element, banglaDigits: false },
          format
        )
      : '';
  }

  if (field === 'variant') {
    return Object.values(data.attributes ?? {})
      .filter(Boolean)
      .join(' / ');
  }

  if (field === 'item_name') {
    // A size's label shows its article's name; its size and color show apart.
    return data.article_name || data.item_name;
  }

  if (field === 'full_name') {
    return data.item_name;
  }

  if (field.startsWith('attribute:')) {
    return data.attributes?.[field.slice('attribute:'.length)] ?? '';
  }

  const value = data[field as keyof LabelData];
  return typeof value === 'string' || typeof value === 'number'
    ? String(value)
    : '';
}

/** An item to show while designing, when the shop picked none. */
export function getSampleData(company = ''): LabelData {
  return {
    item_code: 'SHOE-42-BLK',
    item_name: t`Leather Shoe - 42 / Black`,
    article_name: t`Leather Shoe`,
    barcode: '2000000000015',
    price: 2450,
    uom: t`Pair`,
    item_group: t`Shoes`,
    batch_no: '',
    company,
    attributes: { Size: '42', Color: t`Black` },
  };
}

/** The template's sheet and elements from a saved Books Label Template. */
export function parseTemplate(values: Record<string, unknown>): LabelTemplate {
  const defaults = getNewTemplate();
  let elements: LabelElement[] = [];
  try {
    const parsed: unknown = JSON.parse(String(values.layout || '[]'));
    if (Array.isArray(parsed)) {
      elements = (parsed as LabelElement[]).map((element) => ({
        ...element,
        id: element.id || newElementId(),
      }));
    }
  } catch {
    elements = [];
  }

  const number = (key: keyof LabelSheet) => {
    const value = Number(values[key]);
    return Number.isFinite(value) ? value : (defaults[key] as number);
  };
  return {
    name: values.name as string | undefined,
    template_name: String(values.template_name ?? values.name ?? ''),
    is_default: Number(values.is_default) || 0,
    paper: values.paper === 'A4 Sheet' ? 'A4 Sheet' : 'Label Printer',
    label_width: number('label_width') || defaults.label_width,
    label_height: number('label_height') || defaults.label_height,
    columns: Math.max(1, number('columns')),
    column_gap: number('column_gap'),
    row_gap: number('row_gap'),
    margin_top: number('margin_top'),
    margin_left: number('margin_left'),
    elements,
  };
}

/** The values a Books Label Template saves. */
export function serializeTemplate(template: LabelTemplate) {
  return {
    template_name: template.template_name.trim(),
    is_default: template.is_default ? 1 : 0,
    paper: template.paper,
    label_width: template.label_width,
    label_height: template.label_height,
    columns: template.columns,
    column_gap: template.column_gap,
    row_gap: template.row_gap,
    margin_top: template.margin_top,
    margin_left: template.margin_left,
    layout: JSON.stringify(template.elements),
  };
}

export type LabelSource = 'Item' | 'Purchase Receipt';

export interface LabelRowsResult {
  rows: LabelRow[];
  attributes: string[];
  company: string;
}

/** The items to label: an item's sizes and colors, or what a receipt received. */
export async function getLabelRows(
  source: LabelSource | '',
  names: string[]
): Promise<LabelRowsResult> {
  return await call<LabelRowsResult>(`${API}.get_label_rows`, {
    source,
    names,
  });
}

/** What labels show for each item, one label each. */
export async function getLabelItems(items: string[]): Promise<LabelRow[]> {
  return await call<LabelRow[]>(`${API}.get_label_items`, { items });
}

/** Gives each item that has no barcode a new one; returns the barcodes by item. */
export async function createBarcodes(
  items: string[]
): Promise<Record<string, string>> {
  return await call<Record<string, string>>(`${API}.create_barcodes`, {
    items,
  });
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

export function round(value: number, places = 1): number {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}
