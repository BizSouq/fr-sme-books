import { t } from 'fyo';

export interface SuggestedQuestion {
  id: string;
  category: 'daily' | 'monthly';
  label: string;
  prompt: string;
  icon: string;
}

export function getSuggestedQuestions(): SuggestedQuestion[] {
  return [
    {
      id: 'daily-expense',
      category: 'daily',
      label: t`Today's expenses`,
      prompt: t`What are today's total expenses? Show a breakdown by account.`,
      icon: 'lucide-arrow-down-right',
    },
    {
      id: 'daily-income',
      category: 'daily',
      label: t`Today's income`,
      prompt: t`What is today's total income and sales revenue?`,
      icon: 'lucide-arrow-up-right',
    },
    {
      id: 'daily-unpaid',
      category: 'daily',
      label: t`Unpaid invoices`,
      prompt: t`Which sales invoices are unpaid, and how much is outstanding in total?`,
      icon: 'lucide-receipt',
    },
    {
      id: 'monthly-expense',
      category: 'monthly',
      label: t`This month's expenses`,
      prompt: t`What are my top expenses this month? Show a chart.`,
      icon: 'lucide-chart-column',
    },
    {
      id: 'monthly-pnl',
      category: 'monthly',
      label: t`Monthly profit and loss`,
      prompt: t`Show the profit and loss for this month with a chart.`,
      icon: 'lucide-activity',
    },
    {
      id: 'monthly-cashflow',
      category: 'monthly',
      label: t`Cash flow`,
      prompt: t`Show the cash flow of this quarter, month by month, with a chart.`,
      icon: 'lucide-wallet',
    },
  ];
}
