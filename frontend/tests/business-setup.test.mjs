import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  applySetup,
  buildApplyOptions,
  describeAnswers,
  getCatalogItems,
  groupRows,
  mergeItems,
  toggleAnswer,
} from './helpers/businessSetup.mjs';
import { stubServer } from './helpers/server.mjs';

const API = 'frappe_books.onboarding.api';
const CUISINE = {
  id: 'cuisine',
  label: 'What kind of food do you serve?',
  multiple: true,
  options: [
    { id: 'biryani', label: 'Biryani and kacchi' },
    { id: 'sweets', label: 'Sweets and desserts' },
  ],
};
const SIZE = {
  id: 'size',
  label: 'How many seats?',
  multiple: false,
  options: [
    { id: 'small', label: 'Under 20' },
    { id: 'large', label: 'Over 20' },
  ],
};
const CHOICES = {
  guest_parties: true,
  vat: true,
  vat_rate: 5,
  mobile_wallets: true,
  cash_denominations: false,
  fetch_images: true,
};

function item(name, values = {}) {
  return {
    name,
    group: 'Biryani & Kacchi',
    description: '',
    type: 'Product',
    uom: 'Plate',
    rate: 100,
    tags: [],
    image: '',
    image_query: name,
    ...values,
  };
}

test('a multiple-choice question keeps every pick, a single-choice one the last', () => {
  let answers = toggleAnswer({}, CUISINE, 'biryani');
  answers = toggleAnswer(answers, CUISINE, 'sweets');
  assert.deepEqual(answers, { cuisine: ['biryani', 'sweets'] });
  answers = toggleAnswer(answers, CUISINE, 'biryani');
  assert.deepEqual(answers, { cuisine: ['sweets'] });

  answers = toggleAnswer(answers, SIZE, 'small');
  answers = toggleAnswer(answers, SIZE, 'large');
  assert.deepEqual(answers.size, ['large']);
  assert.deepEqual(toggleAnswer(answers, SIZE, 'large').size, []);
});

test('answers are told to the AI in words, unanswered questions left out', () => {
  assert.deepEqual(
    describeAnswers([CUISINE, SIZE], { cuisine: ['sweets'], size: [] }),
    [
      {
        question: 'What kind of food do you serve?',
        answers: ['Sweets and desserts'],
      },
    ]
  );
});

test('new catalog answers keep the ticks and prices of rows that still match', () => {
  let rows = mergeItems(
    [],
    [item('Kacchi Biryani'), item('Borhani')],
    'catalog',
    ['borhani']
  );
  assert.deepEqual(
    rows.map((row) => [row.name, row.selected, row.exists]),
    [
      ['Kacchi Biryani', true, false],
      ['Borhani', false, true],
    ]
  );

  rows[0].selected = false;
  rows[0].rate = 420;
  rows = mergeItems(rows, [item('Firni')], 'ai');
  rows = mergeItems(
    rows,
    [item('Kacchi Biryani'), item('Chicken Biryani')],
    'catalog'
  );
  assert.deepEqual(
    rows.map((row) => [row.name, row.source, row.selected, row.rate]),
    [
      ['Kacchi Biryani', 'catalog', false, 420],
      ['Firni', 'ai', true, 100],
      ['Chicken Biryani', 'catalog', true, 100],
    ]
  );

  // The AI never doubles an item the page has, whatever its capitals.
  rows = mergeItems(rows, [item('FIRNI'), item('Jilapi')], 'ai');
  assert.deepEqual(
    rows.map((row) => row.name),
    ['Kacchi Biryani', 'Firni', 'Chicken Biryani', 'Jilapi']
  );
});

test('rows are listed by group, ungrouped ones last', () => {
  const rows = mergeItems(
    [],
    [
      item('Loose', { group: '' }),
      item('Tea', { group: 'Drinks' }),
      item('Kacchi'),
    ],
    'catalog'
  );
  assert.deepEqual(
    groupRows(rows).map(([group, items]) => [group, items.length]),
    [
      ['Drinks', 1],
      ['Biryani & Kacchi', 1],
      ['', 1],
    ]
  );
});

test('only ticked items, their groups and units and the offered defaults are sent', () => {
  const rows = mergeItems(
    [],
    [
      item('Kacchi Biryani', { image: 'https://upload.wikimedia.org/k.jpg' }),
      item('Milk Tea', { group: 'Tea & Coffee', uom: 'Cup', rate: '20' }),
      item('Haircut', { group: 'AI Group', uom: 'Piece', type: 'Service' }),
      item('Borhani'),
    ],
    'catalog',
    ['Borhani']
  );
  rows[1].selected = false;
  const catalog = {
    groups: [
      { name: 'Biryani & Kacchi', image: '' },
      { name: 'Tea & Coffee', image: '' },
    ],
    uoms: [
      { name: 'Plate', whole: 1 },
      { name: 'Cup', whole: 1 },
    ],
  };

  const options = buildApplyOptions(rows, catalog, CHOICES, ['vat']);
  assert.deepEqual(
    options.items.map(({ name, image }) => [name, image]),
    [
      ['Kacchi Biryani', 'https://upload.wikimedia.org/k.jpg'],
      ['Haircut', ''],
    ]
  );
  assert.deepEqual(
    options.groups.map(({ name }) => name),
    ['Biryani & Kacchi', 'AI Group']
  );
  assert.deepEqual(options.uoms, [{ name: 'Plate', whole: 1 }]);
  assert.equal(options.vat, true);
  assert.equal(options.vat_rate, 5);
  // A default the company's country does not offer is never asked for.
  assert.equal(options.mobile_wallets, false);
  assert.equal(options.cash_denominations, false);

  const plain = buildApplyOptions(
    rows,
    catalog,
    { ...CHOICES, vat: false, fetch_images: false },
    ['vat', 'mobile_wallets']
  );
  assert.equal(plain.vat_rate, null);
  assert.equal(plain.mobile_wallets, true);
  assert.equal(plain.items[0].image, '');
});

test('the page talks to the onboarding endpoints', async () => {
  const calls = stubServer((method) =>
    method.endsWith('get_items')
      ? { groups: [], uoms: [], items: [], existing: [] }
      : { items: 2, item_groups: 1, skipped_items: 0, images_queued: 0 }
  );
  await getCatalogItems('restaurant', { cuisine: ['sweets'] });
  const result = await applySetup({ guest_parties: true });
  assert.equal(result.items, 2);
  assert.deepEqual(calls, [
    {
      method: `${API}.get_items`,
      args: { business_type: 'restaurant', answers: { cuisine: ['sweets'] } },
    },
    { method: `${API}.apply`, args: { options: { guest_parties: true } } },
  ]);
});
