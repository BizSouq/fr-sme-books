import assert from 'node:assert/strict';
import { test } from 'node:test';
import { itemVariants, pos } from './helpers/frappe.mjs';

const { combinations, countNewVariants, getVariantGrid, getVariantLabel } =
  itemVariants;

const shoe = {
  attributes: [
    {
      attribute: 'Shoe Size',
      values: ['39', '40', '41', '42'].map((value) => ({ value })),
    },
    {
      attribute: 'Color',
      values: [
        { value: 'Black', color: '#111827' },
        { value: 'White', color: '#F9FAFB' },
        { value: 'Red', color: '#DC2626' },
      ],
    },
  ],
  variants: [
    variant('R-40-BLK', { 'Shoe Size': '40', Color: 'Black' }, 3),
    variant('R-41-BLK', { 'Shoe Size': '41', Color: 'Black' }, 0),
    variant('R-41-WHT', { 'Shoe Size': '41', Color: 'White' }, 5),
  ],
};

function variant(name, values, stock_qty) {
  return {
    name,
    item_name: name,
    standard_rate: 2500,
    is_stock_item: 1,
    stock_qty,
    values,
  };
}

test('the size grid has the sizes in use across and the colors in use down', () => {
  const grid = getVariantGrid(shoe);

  assert.equal(grid.columnAttribute, 'Shoe Size');
  assert.deepEqual(
    grid.columns.map(({ value }) => value),
    ['40', '41']
  );
  assert.deepEqual(
    grid.rows.map(({ label, color, cells }) => [
      label,
      color,
      cells.map((cell) => cell?.name),
    ]),
    [
      ['Black', '#111827', ['R-40-BLK', 'R-41-BLK']],
      ['White', '#F9FAFB', [undefined, 'R-41-WHT']],
    ]
  );
});

test('an article by one attribute has one row of sizes', () => {
  const grid = getVariantGrid({
    attributes: [shoe.attributes[0]],
    variants: [variant('T-42', { 'Shoe Size': '42' }, 1)],
  });

  assert.deepEqual(grid.rows.length, 1);
  assert.equal(grid.rows[0].label, '');
  assert.deepEqual(
    grid.rows[0].cells.map((cell) => cell.name),
    ['T-42']
  );
  assert.equal(getVariantGrid({ attributes: [], variants: [] }), undefined);
});

test('the creator counts only the combinations no size has yet', () => {
  assert.equal(
    countNewVariants(shoe, {
      'Shoe Size': ['40', '41', '42'],
      Color: ['Black', 'White'],
    }),
    3
  );
  assert.equal(countNewVariants(shoe, { 'Shoe Size': ['42'], Color: [] }), 0);
  assert.deepEqual(combinations([[1, 2], ['a']]), [
    [1, 'a'],
    [2, 'a'],
  ]);
  assert.equal(
    getVariantLabel(shoe.variants[2], shoe.attributes),
    '41 / White'
  );
});

test('the POS lists an article once, with the stock of all its sizes', () => {
  const [record] = [{ name: 'Runner', has_variants: 1, is_stock_item: 1 }];
  const stock = pos.getArticleStock(
    [
      { name: 'R-40-BLK', variant_of: 'Runner' },
      { name: 'R-41-WHT', variant_of: 'Runner' },
    ],
    { 'R-40-BLK': { availableQty: 3 }, 'R-41-WHT': { availableQty: 5 } }
  );

  assert.equal(stock.Runner.availableQty, 8);
  assert.equal(stock['R-40-BLK'].availableQty, 3);
  const item = pos.toPOSItem(record, stock);
  assert.equal(item.hasVariants, true);
  assert.equal(item.availableQty, 8);
  assert.deepEqual(pos.getPOSItemFilters('Inventory Items'), [
    ['variant_of', 'is', 'not set'],
    ['is_stock_item', '=', 1],
  ]);
});

test('the size sheet adds a row for each size given a quantity', () => {
  assert.deepEqual(
    itemVariants.getSizeLines({
      'R-40': 6,
      'R-41': '',
      'R-42': '3',
      'R-43': 0,
    }),
    [
      { item: 'R-40', qty: 6 },
      { item: 'R-42', qty: 3 },
    ]
  );
});
