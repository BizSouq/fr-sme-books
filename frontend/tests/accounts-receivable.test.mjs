import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadFrappeModels } from './helpers/frappeModels.mjs';
import {
  AccountsReceivable,
  frappeModels,
  fyo,
  getRowReference,
  MobileTree,
} from './helpers/frappe.mjs';

await loadFrappeModels(frappeModels);

const amounts = ['outstanding', 'range_0_30', 'range_91_above'];

function invoice(party, name, range, outstanding) {
  return {
    type: 'invoice',
    party,
    voucher_no: name,
    voucher_type: 'Books Sales Invoice',
    outstanding,
    range_0_30: range === '0-30' ? outstanding : 0,
    range_91_above: range === '91+' ? outstanding : 0,
  };
}

function total(party, values) {
  return {
    type: 'total',
    party,
    ...Object.fromEntries(amounts.map((key, index) => [key, values[index]])),
  };
}

/** The report with rows grouped by party, as the server sends them. */
function getReport() {
  const report = new AccountsReceivable(fyo);
  report.fyo = Object.assign(Object.create(fyo), { can: () => true });
  report.columns = [
    { fieldname: 'party', label: 'Party', fieldtype: 'Data' },
    { fieldname: 'voucher_no', label: 'Invoice', fieldtype: 'Data' },
    { fieldname: 'voucher_type', label: 'Ref Type', fieldtype: 'Data' },
    ...amounts.map((fieldname) => ({
      fieldname,
      label: fieldname,
      fieldtype: 'Currency',
    })),
  ];
  report.reportData = [
    invoice('Acme', 'SINV-1001', '91+', 300),
    invoice('Acme', 'SINV-1004', '0-30', 50),
    total('Acme', [350, 50, 300]),
    {},
    invoice('Globex', 'SINV-1002', '0-30', 120),
    total('Globex', [120, 120, 0]),
    {},
    total('Total', [470, 170, 300]),
  ].map((row) =>
    Object.keys(row).length ? report.getReportRow(row) : report.getEmptyRow()
  );
  return report;
}

test('the totals of the receivables are bold summary rows', () => {
  const rows = getReport().reportData.filter((row) => !row.isEmpty);

  assert.deepEqual(
    rows.map((row) => [!!row.isSummary, row.cells.every((cell) => cell.bold)]),
    [
      [false, false],
      [false, false],
      [true, true],
      [false, false],
      [true, true],
      [true, true],
    ]
  );
});

test('a phone groups receivables by party without counting the totals twice', () => {
  const report = getReport();
  const tree = new MobileTree(report, AccountsReceivable.phoneLayout);

  const rows = tree.getRows(tree.getValueColumns());

  assert.deepEqual(
    rows.map(({ label, subtitle, values }) => [
      label,
      subtitle,
      values.map(({ text }) => text),
    ]),
    [
      ['Acme', '2 invoices', ['350.00', '300.00']],
      ['SINV-1001', undefined, ['300.00', '300.00']],
      ['SINV-1004', undefined, ['50.00', '0.00']],
      ['Globex', '1 invoice', ['120.00', '0.00']],
      ['SINV-1002', undefined, ['120.00', '0.00']],
      ['Total', undefined, ['470.00', '300.00']],
    ]
  );
});

test('a receivable opens its invoice', () => {
  const report = getReport();

  assert.deepEqual(getRowReference(report, report.reportData[0]), {
    schemaName: 'SalesInvoice',
    name: 'SINV-1001',
  });
});
