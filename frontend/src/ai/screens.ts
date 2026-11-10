import { t } from 'fyo';
import { getReports } from 'reports';
import { toSchemaName } from 'src/frappe/registry';
import { showDialog } from 'src/utils/interactive';
import { getFormRoute, routeTo } from 'src/utils/ui';
import type { AgentDeps } from './agent';
import type { WritePreview } from './types';

/** The loop's hooks into the running app. */
export function getAppAgentDeps(): AgentDeps {
  return { openScreen, confirmDestructive };
}

/** Opens what `open_screen` checked on the server: its DocTypes and reports, by Books route. */
async function openScreen(screen: Record<string, unknown>) {
  const route = getScreenRoute(screen);
  if (route) {
    await routeTo(route);
  }
}

function getScreenRoute(screen: Record<string, unknown>): string | undefined {
  const schemaName = toSchemaName(String(screen.doctype ?? ''));
  switch (screen.open) {
    case 'dashboard':
      return '/';
    case 'list':
      return schemaName && `/list/${schemaName}`;
    case 'record':
      return schemaName && getFormRoute(schemaName, String(screen.name));
    case 'report': {
      const [name] =
        Object.entries(getReports()).find(
          ([, report]) => report?.serverReportName === screen.report_name
        ) ?? [];
      return name && `/report/${name}`;
    }
  }
}

/**
 * The last gate before a delete or a cancel. The card said what would happen;
 * this makes the irreversible step take a second, deliberate click.
 */
async function confirmDestructive(preview: WritePreview): Promise<boolean> {
  const what = [preview.doctype_label, preview.name].filter(Boolean).join(' ');
  const isCancel = preview.action === 'cancel';
  return (await showDialog({
    title: isCancel ? t`Cancel ${what}?` : t`Delete ${what}?`,
    type: 'warning',
    destructive: true,
    detail: isCancel
      ? t`This reverses the document's ledger entries.`
      : t`This action is permanent.`,
    buttons: [
      { label: t`Go back`, action: () => false, isEscape: true },
      {
        label: isCancel ? t`Cancel it` : t`Delete`,
        action: () => true,
        isPrimary: true,
      },
    ],
  })) as boolean;
}
