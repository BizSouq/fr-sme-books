import { getSchema } from 'src/frappe/registry';
import { call } from 'src/web/api';

/** The `frappe_books.inventory.variants` endpoints: an article's sizes and colors. */
const API = 'frappe_books.inventory.variants';

export type AttributeValue = {
  value: string;
  abbreviation?: string;
  color?: string;
};

export type VariantAttribute = {
  attribute: string;
  values: AttributeValue[];
};

export type Variant = {
  name: string;
  item_name: string;
  standard_rate: number;
  image?: string;
  is_stock_item?: number;
  stock_qty: number;
  /** The variant's value of each attribute, like { Size: '42', Color: 'Black' }. */
  values: Record<string, string>;
};

export type VariantData = {
  attributes: VariantAttribute[];
  variants: Variant[];
};

/** One row of a size grid: the variants of one color, say, by size. */
export type VariantGridRow = {
  label: string;
  /** The row's color swatch, when its one value has one. */
  color?: string;
  cells: (Variant | undefined)[];
};

/** A size grid: sizes across, the other values (like colors) down. */
export type VariantGrid = {
  columnAttribute: string;
  columns: AttributeValue[];
  rows: VariantGridRow[];
};

export async function getVariants(item: string): Promise<VariantData> {
  return await call<VariantData>(`${API}.get_variants`, { item });
}

export async function createVariants(
  item: string,
  values: Record<string, string[]>,
  rate?: number
): Promise<{ created: string[]; existing: number }> {
  return await call(`${API}.create_variants`, { item, values, rate });
}

/**
 * The grid of an article's variants. The first attribute's values that a
 * variant has are the columns; each combination of the other attributes'
 * values that a variant has is a row. With one attribute, the grid has one row.
 */
export function getVariantGrid({
  attributes,
  variants,
}: VariantData): VariantGrid | undefined {
  const [first, ...others] = attributes;
  if (!first) {
    return;
  }

  const used = (attribute: VariantAttribute) =>
    attribute.values.filter(({ value }) =>
      variants.some((variant) => variant.values[attribute.attribute] === value)
    );
  const columns = used(first);
  const rowKeys = combinations(others.map(used));
  const rows = rowKeys
    .map((key) => ({
      label: key.map(({ value }) => value).join(' / '),
      color: key.length === 1 ? key[0].color || undefined : undefined,
      cells: columns.map((column) =>
        variants.find(
          (variant) =>
            variant.values[first.attribute] === column.value &&
            key.every(
              (value, idx) =>
                variant.values[others[idx].attribute] === value.value
            )
        )
      ),
    }))
    .filter((row) => row.cells.some(Boolean));
  return { columnAttribute: first.attribute, columns, rows };
}

/** Every combination that takes one entry of each list, in order. */
export function combinations<T>(lists: T[][]): T[][] {
  return lists.reduce<T[][]>(
    (combos, list) =>
      combos.flatMap((combo) => list.map((entry) => [...combo, entry])),
    [[]]
  );
}

/** How many new items the chosen values make: the combinations no variant has yet. */
export function countNewVariants(
  data: VariantData,
  chosen: Record<string, string[]>
): number {
  const lists = data.attributes.map(({ attribute }) =>
    (chosen[attribute] ?? []).map((value) => [attribute, value] as const)
  );
  return combinations(lists).filter(
    (combo) =>
      combo.length > 0 &&
      !data.variants.some((variant) =>
        combo.every(([attribute, value]) => variant.values[attribute] === value)
      )
  ).length;
}

/** The variant's values in the template's order, as a POS line or a cell names it: "42 / Black". */
export function getVariantLabel(
  variant: Pick<Variant, 'values'>,
  attributes: Pick<VariantAttribute, 'attribute'>[]
): string {
  return attributes
    .map(({ attribute }) => variant.values[attribute])
    .filter(Boolean)
    .join(' / ');
}

/** Whether a document is a saved article with sizes or colors, whose form shows their grid. */
export function isItemTemplate(
  doc:
    | { schemaName?: string; notInserted?: boolean; has_variants?: unknown }
    | null
    | undefined
): boolean {
  return doc?.schemaName === 'Item' && !doc.notInserted && !!doc.has_variants;
}

/** Whether a form section holds the attributes table, under which the size grid goes. */
export function hasAttributesTable(fields: { fieldname: string }[]): boolean {
  return fields.some(({ fieldname }) => fieldname === 'attributes');
}

/** The sizes given a quantity, in the order they were filled, as item rows to add. */
export function getSizeLines(
  quantities: Record<string, number | string | undefined>
): { item: string; qty: number }[] {
  return Object.entries(quantities)
    .map(([item, qty]) => ({ item, qty: Number(qty) || 0 }))
    .filter(({ qty }) => qty > 0);
}

/** The field a row's rate goes in: an invoice row's price, a stock entry's basic rate, a transfer's rate. */
export function getRateField(doc: {
  fieldMap: Record<string, unknown>;
}): string | undefined {
  const target = (doc.fieldMap.items as { target?: string } | undefined)
    ?.target;
  if (!target) {
    return;
  }

  const fields = (getSchema(target)?.fields ?? []).map(
    ({ fieldname }) => fieldname
  );
  return ['price_list_rate', 'basic_rate', 'rate'].find((fieldname) =>
    fields.includes(fieldname)
  );
}
