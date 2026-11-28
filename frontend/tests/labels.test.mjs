import assert from 'node:assert/strict';
import { test } from 'node:test';
import { barcode, labels } from './helpers/frappe.mjs';

const { encodeBarcode, getBars, gs1CheckDigit, hasValidCheckDigit } = barcode;

test('GS1 check digits match the standard examples', () => {
  assert.equal(gs1CheckDigit('400638133393'), 1);
  assert.equal(gs1CheckDigit('03600029145'), 2);
  assert.equal(gs1CheckDigit('9638507'), 4);
  assert.ok(hasValidCheckDigit('4006381333931'));
  assert.ok(!hasValidCheckDigit('4006381333932'));
});

test('retail codes draw as EAN or UPC, anything else as Code 128', () => {
  const ean = encodeBarcode('4006381333931');
  assert.equal(ean.format, 'EAN-13');
  // 11 quiet, 95 symbol, 7 quiet modules.
  assert.equal(ean.modules.length, 113);
  assert.equal(ean.modules.slice(11, 14), '101');
  assert.equal(encodeBarcode('036000291452').format, 'UPC-A');
  assert.equal(encodeBarcode('96385074').format, 'EAN-8');
  // A wrong check digit is a code like any other.
  assert.equal(encodeBarcode('4006381333932').format, 'Code 128');
  assert.equal(encodeBarcode('SHOE-42-BLK').format, 'Code 128');
  assert.equal(encodeBarcode('জুতা'), undefined);
});

test('Code 128 packs digits two to a symbol', () => {
  const { getCode128Symbols } = barcode;
  // Start C, 12, 34, 56, check digit.
  assert.deepEqual(getCode128Symbols('123456').slice(0, 4), [105, 12, 34, 56]);
  // Letters start in set B; a long run of digits switches to set C.
  const mixed = getCode128Symbols('AB123456');
  assert.deepEqual(mixed.slice(0, 7), [104, 33, 34, 99, 12, 34, 56]);
  const code = encodeBarcode('AB123456');
  // Every symbol is 11 modules, the stop 13, with 10 quiet modules each side.
  assert.equal(code.modules.length, 20 + mixed.length * 11 + 13);
  assert.ok(
    getBars(code.modules).every((bar) => bar.width >= 1 && bar.width <= 4)
  );
});

test('an A4 sheet holds its rows and columns; a roll, a row at a time', () => {
  const [roll] = labels.getLabelPresets();
  assert.deepEqual(labels.getPageLayout(roll.sheet), {
    pageWidth: 38,
    pageHeight: 25,
    perPage: 1,
    rows: 1,
    columns: 1,
  });

  const twoAcross = labels
    .getLabelPresets()
    .find((p) => p.key === 'roll-2x33x25');
  assert.equal(labels.getPageLayout(twoAcross.sheet).pageWidth, 68);

  const sheet65 = labels.getLabelPresets().find((p) => p.key === 'a4-65').sheet;
  const layout = labels.getPageLayout(sheet65);
  assert.equal(layout.perPage, 65);
  assert.deepEqual(labels.getLabelPosition(sheet65, 6, layout), {
    left: 45.3,
    top: 31.9,
  });
});

test('each row prints as many labels as its quantity, after skipped places', () => {
  const rows = [
    { item_code: 'A', qty: 3 },
    { item_code: 'B', qty: 0 },
    { item_code: 'C', qty: 2.7 },
  ];
  assert.equal(labels.countLabels(rows), 5);
  const pages = labels.getPages(rows, 4, 2);
  assert.equal(pages.length, 2);
  assert.deepEqual(
    pages.map((page) => page.map((label) => label?.item_code ?? null)),
    [
      [null, null, 'A', 'A'],
      ['A', 'C', 'C'],
    ]
  );
  assert.deepEqual(labels.getPages([{ qty: 0 }], 4, 3), []);
});

test('prices show in the shop currency, whole taka without decimals', () => {
  const format = {
    symbol: '৳',
    formatNumber: (value, precision) =>
      value.toLocaleString('en-IN', {
        minimumFractionDigits: precision,
        maximumFractionDigits: precision,
      }),
  };
  assert.equal(labels.formatLabelPrice(125000, {}, format), '৳1,25,000');
  assert.equal(labels.formatLabelPrice(99.5, {}, format), '৳99.50');
  assert.equal(
    labels.formatLabelPrice(2450, { banglaDigits: true }, format),
    '৳২,৪৫০'
  );
  assert.equal(
    labels.formatLabelPrice(80, { hideCurrency: true }, format),
    '80'
  );

  const data = {
    item_code: 'S-42',
    item_name: 'জুতা',
    price: 2450,
    attributes: { Size: '42', Color: 'Black' },
  };
  const element = (field, more = {}) => ({
    id: 'e',
    field,
    x: 0,
    y: 0,
    width: 10,
    height: 5,
    fontSize: 8,
    ...more,
  });
  assert.equal(
    labels.getElementText(element('item_name'), data, format),
    'জুতা'
  );
  const size = {
    ...data,
    item_name: 'Shoe - 42 / Black',
    article_name: 'Shoe',
  };
  assert.equal(
    labels.getElementText(element('item_name'), size, format),
    'Shoe'
  );
  assert.equal(
    labels.getElementText(element('full_name'), size, format),
    'Shoe - 42 / Black'
  );
  assert.equal(
    labels.getElementText(element('price', { text: 'মূল্য' }), data, format),
    'মূল্য ৳2,450'
  );
  assert.equal(
    labels.getElementText(element('variant'), data, format),
    '42 / Black'
  );
  assert.equal(
    labels.getElementText(
      element('attribute:Size', { banglaDigits: true }),
      data,
      format
    ),
    '৪২'
  );
  assert.equal(
    labels.getElementText(element('batch_no', { text: 'Batch' }), data, format),
    ''
  );
  assert.equal(
    labels.getElementText(element('text', { text: 'Thank you' }), data, format),
    'Thank you'
  );
});

test('a label of another size keeps its layout in proportion', () => {
  const elements = labels.getDefaultElements(38, 25);
  assert.deepEqual(
    elements.map((element) => element.field),
    ['item_name', 'variant', 'barcode', 'price']
  );
  const scaled = labels.scaleElements(
    elements,
    { width: 38, height: 25 },
    { width: 76, height: 50 }
  );
  assert.equal(scaled[2].width, elements[2].width * 2);
  assert.equal(scaled[3].fontSize, elements[3].fontSize * 2);

  const clamped = labels.clampElement(
    { ...elements[0], x: 30, width: 20 },
    { label_width: 38, label_height: 25 }
  );
  assert.equal(clamped.x + clamped.width, 38);
});

test('a saved template reads back as it was laid out', () => {
  const template = labels.getNewTemplate('Shoe tag');
  const saved = labels.serializeTemplate(template);
  assert.equal(typeof saved.layout, 'string');
  const read = labels.parseTemplate({ ...saved, name: 'Shoe tag' });
  assert.deepEqual(read.elements, template.elements);
  assert.equal(read.paper, 'Label Printer');
  assert.ok(labels.findPreset(read));
  assert.deepEqual(
    labels.parseTemplate({ layout: '{oops', name: 'X' }).elements,
    []
  );
});
