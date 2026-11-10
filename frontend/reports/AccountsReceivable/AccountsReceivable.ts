import { t } from 'fyo';
import { Action } from 'fyo/model/types';
import getCommonExportActions from 'reports/commonExporter';
import { Report } from 'reports/Report';
import { ServerRow } from 'reports/serverReport';
import { PhoneLayout, ReportRow } from 'reports/types';
import { Field } from 'schemas/types';

/** What customers owe on a date, by how many days old each invoice is. */
export class AccountsReceivable extends Report {
  static title = t`Accounts Receivable`;
  static reportName = 'accounts-receivable';
  static serverReportName = 'Books Accounts Receivable';
  static phoneLayout: PhoneLayout = {
    type: 'tree',
    label: 'voucher_no',
    groupBy: 'party',
    describeGroup: (count) =>
      count === 1 ? t`1 invoice` : t`${count} invoices`,
    icon: 'lucide-file-text',
    values: [
      { fieldname: 'outstanding', label: t`Outstanding`, width: 112 },
      { fieldname: 'range_91_above', label: t`91+`, width: 96 },
    ],
    chips: ['toDate', 'party'],
  };

  toDate?: string;
  party?: string;
  groupBy: 'none' | 'party' = 'none';

  /** The schema of the report's parties. */
  get partySchema(): string {
    return 'Customer';
  }

  async setDefaultFilters() {
    if (!this.toDate) {
      const { toDate } = await this.getDefaultFilters();
      this.toDate = toDate as string;
    }
  }

  getReportRow(row: ServerRow): ReportRow {
    const reportRow = super.getReportRow(row);
    const isTotal = row.type === 'total';
    reportRow.isSummary = isTotal;
    // The phone adds up its own totals in place of these.
    reportRow.isTotal = isTotal;
    for (const cell of reportRow.cells) {
      cell.bold = isTotal;
    }

    return reportRow;
  }

  getActions(): Action[] {
    return getCommonExportActions(this);
  }

  getFilters(): Field[] {
    return [
      {
        fieldtype: 'Link',
        target: this.partySchema,
        label: t`Party`,
        placeholder: t`Party`,
        fieldname: 'party',
      },
      {
        fieldtype: 'Date',
        label: t`As On Date`,
        placeholder: t`As On Date`,
        fieldname: 'toDate',
      },
      {
        fieldtype: 'Select',
        label: t`Group By`,
        fieldname: 'groupBy',
        options: [
          { label: t`None`, value: 'none' },
          { label: t`Party`, value: 'party' },
        ],
      },
    ] as Field[];
  }
}
