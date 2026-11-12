import { fyo } from 'src/initFyo';
import { createApp, h, ref } from 'vue';
import { DesktopShell, FrappeUI, FrappeUIProvider } from 'frappe-ui';
import { createRouter, createMemoryHistory } from 'vue-router';
import 'src/router';
import Sidebar from 'src/components/Sidebar.vue';
import CommonForm from 'src/pages/CommonForm/CommonForm.vue';
import { languageDirectionKey, shortcutsKey } from 'src/utils/injectionKeys';
import { Shortcuts } from 'src/utils/shortcuts';
import { preparePOSData } from './pos-data';
import 'src/styles/index.css';

/** Mounts the desktop shell with a new sales invoice form, on in-memory data. */
async function mount() {
  await preparePOSData();
  Object.assign(fyo.singles.SystemSettings!, { currency: 'BDT' });
  const form = ref<any>();
  const app = createApp({
    render: () =>
      h(
        FrappeUIProvider,
        {},
        {
          default: () =>
            h(
              DesktopShell,
              { scroll: false, style: { '--w-sidebar': '240px' } },
              {
                sidebar: () =>
                  h(Sidebar, {
                    class: 'flex-shrink-0 border-e border-outline-gray-1',
                  }),
                default: () =>
                  h(
                    'div',
                    {
                      class:
                        'flex min-h-0 flex-1 overflow-hidden bg-surface-base',
                    },
                    [
                      h(CommonForm, {
                        ref: form,
                        schemaName: 'SalesInvoice',
                        name: '',
                      }),
                    ]
                  ),
              }
            ),
        }
      ),
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
  (window as any).formFixture = {
    form,
    /** Fills the invoice's figures as the server's preview would. */
    fillTotals() {
      const doc = form.value.doc;
      const figures: Record<string, number> = {
        net_total: 16050,
        total_taxes_and_charges: 2407.5,
        grand_total: 18457.5,
        base_grand_total: 18457.5,
        outstanding_amount: 18457.5,
      };
      for (const [field, value] of Object.entries(figures)) {
        doc[field] = fyo.pesa(value);
      }
    },
  };
}
mount();
