import { t } from 'fyo';
import { AccountsReceivable } from './AccountsReceivable';

/** What the business owes suppliers on a date, by how many days old each invoice is. */
export class AccountsPayable extends AccountsReceivable {
  static title = t`Accounts Payable`;
  static reportName = 'accounts-payable';
  static serverReportName = 'Books Accounts Payable';
}
