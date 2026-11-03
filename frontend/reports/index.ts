import { AccountsPayable } from './AccountsReceivable/AccountsPayable';
import { AccountsReceivable } from './AccountsReceivable/AccountsReceivable';
import { BalanceSheet } from './BalanceSheet/BalanceSheet';
import { GeneralLedger } from './GeneralLedger/GeneralLedger';
import { GSTR1 } from './GoodsAndServiceTax/GSTR1';
import { GSTR2 } from './GoodsAndServiceTax/GSTR2';
import { ProfitAndLoss } from './ProfitAndLoss/ProfitAndLoss';
import { TrialBalance } from './TrialBalance/TrialBalance';
import { StockBalance } from './inventory/StockBalance';
import { StockLedger } from './inventory/StockLedger';

export const reports = {
  GeneralLedger,
  ProfitAndLoss,
  BalanceSheet,
  TrialBalance,
  AccountsReceivable,
  AccountsPayable,
  GSTR1,
  GSTR2,
  StockLedger,
  StockBalance,
} as const;
