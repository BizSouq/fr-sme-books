import { fyo } from 'src/initFyo';
import { createApp, h, KeepAlive, ref } from 'vue';
import { DesktopShell, FrappeUI, FrappeUIProvider } from 'frappe-ui';
import { createRouter, createMemoryHistory } from 'vue-router';
import 'src/router';
import Sidebar from 'src/components/Sidebar.vue';
import Dashboard from 'src/pages/Dashboard/Dashboard.vue';
import { languageDirectionKey, shortcutsKey } from 'src/utils/injectionKeys';
import { Shortcuts } from 'src/utils/shortcuts';
import { preparePOSData } from './pos-data';
import 'src/styles/index.css';

const months = [
  '2025-11', '2025-12', '2026-01', '2026-02', '2026-03', '2026-04',
  '2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10',
];
const inflow = [40, 55, 55, 40, 10, 85, 135, 10, 75, 40, 32, 50];
const outflow = [95, 2, 40, 155, 10, 65, 40, 125, 45, 2, 100, 2];
const profit = [12, 40, -28, 34, 15, -19, 12, 33, -20, 19, 0.6, 1.5];

/** What the dashboard's server methods answer, in thousands. */
const dashboard: Record<string, unknown> = {
  get_invoice_summary: {
    paid: 536642.87,
    unpaid: 94336.18,
    paid_count: 41,
    unpaid_count: 7,
    from_date: '2025-11-01',
    before_date: '2026-11-01',
  },
  get_cashflow: {
    months: months.map((yearmonth, index) => ({
      yearmonth,
      inflow: inflow[index] * 1000,
      outflow: outflow[index] * 1000,
    })),
    has_data: true,
  },
  get_profit_and_loss: {
    months: months.map((yearmonth, index) => ({
      yearmonth,
      balance: profit[index] * 1000,
    })),
    has_data: true,
  },
  get_top_expenses: [
    ['Cost of Goods Sold', 295000],
    ['Office Rent', 109000],
    ['Utility Expenses', 22700],
    ['Telephone Expenses', 13600],
    ['Freight and Forwarding Charges', 13600],
  ].map(([account, total]) => ({ account, total })),
};

/** Mounts the desktop shell with the sidebar and the dashboard, on in-memory data. */
async function mount() {
  await preparePOSData();
  Object.assign(fyo.singles.SystemSettings!, { currency: 'BDT' });
  const serve = window.fetch;
  window.fetch = async (input, init) => {
    const method = String(input).split('/').pop()!.split('?')[0];
    const name = method.replace('frappe_books.reports.dashboard.', '');
    return name in dashboard
      ? Response.json({ message: dashboard[name] })
      : serve(input, init);
  };

  const app = createApp({
    render: () =>
      h(FrappeUIProvider, {}, {
        default: () =>
          h(DesktopShell, { scroll: false, style: { '--w-sidebar': '240px' } }, {
            sidebar: () =>
              h(Sidebar, {
                class: 'flex-shrink-0 border-e border-outline-gray-1',
              }),
            default: () =>
              h('div', { class: 'flex min-h-0 flex-1 overflow-hidden' }, [
                // The dashboard loads its figures when keep-alive activates it.
                h(KeepAlive, null, [h(Dashboard, { class: 'min-w-0 flex-1' })]),
              ]),
          }),
      }),
  });
  app.use(FrappeUI);
  app.use(
    createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/:path(.*)*', component: { render: () => null } }],
    })
  );
  app.mixin({
    computed: { fyo: () => fyo, platform: () => 'Web' },
    methods: { t: fyo.t, T: fyo.T },
  });
  app.provide(languageDirectionKey, ref('ltr'));
  const shortcuts = new Shortcuts();
  shortcuts.start();
  app.provide(shortcutsKey, shortcuts);
  app.mount('#app');
  (window as any).deskFixture = { fyo };
}
mount();
