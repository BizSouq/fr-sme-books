<template>
  <div class="rounded-lg border text-sm" :class="cardClass">
    <div class="flex items-center gap-2 px-3 py-2">
      <span class="size-2 shrink-0 rounded-full" :class="dotClass" />
      <span class="font-medium text-ink-gray-8">{{ title }}</span>
      <span v-if="entry.summary" class="min-w-0 truncate text-ink-gray-5">
        {{ entry.summary }}
      </span>
    </div>

    <!-- The guard holds the change until this is answered; the user approves these exact values. -->
    <div
      v-if="entry.status === 'awaiting-confirmation' && preview"
      class="flex flex-col gap-3 px-3 pb-3"
    >
      <p class="text-ink-gray-7">{{ prompt }}</p>
      <dl
        v-if="preview.rows.length"
        class="divide-y divide-outline-gray-1 rounded border border-outline-gray-1 bg-surface-base"
      >
        <div
          v-for="row in preview.rows"
          :key="row.fieldname"
          class="flex gap-3 px-2.5 py-1.5"
        >
          <dt class="w-32 shrink-0 text-ink-gray-5">{{ row.label }}</dt>
          <dd class="min-w-0 flex-1 break-words text-ink-gray-8">
            <template v-if="row.after !== undefined">
              <span :class="{ 'font-medium': row.changed }">{{
                row.after
              }}</span>
              <span
                v-if="row.before !== undefined && row.changed"
                class="text-ink-gray-5"
              >
                · {{ t`was` }} <s>{{ row.before }}</s>
              </span>
              <span
                v-else-if="row.before !== undefined"
                class="text-ink-gray-5"
              >
                · {{ t`unchanged` }}
              </span>
              <ul
                v-if="row.rows?.length"
                class="mt-1 list-disc ps-4 text-ink-gray-6"
              >
                <li v-for="(line, index) in row.rows" :key="index">
                  {{ line }}
                </li>
              </ul>
            </template>
            <template v-else>{{ row.before }}</template>
          </dd>
        </div>
      </dl>
      <div class="flex gap-2">
        <FrappeButton
          variant="solid"
          :theme="preview.destructive ? 'red' : 'gray'"
          :label="confirmLabel"
          @click="$emit('confirm', entry.id)"
        />
        <FrappeButton :label="t`Cancel`" @click="$emit('cancel', entry.id)" />
      </div>
    </div>

    <!-- Results stay folded: the model already read them; this is for checking its work. -->
    <div
      v-else-if="entry.result !== undefined && entry.result !== null"
      class="px-3 pb-2"
    >
      <button
        class="text-ink-gray-5 hover:underline"
        @click="showResult = !showResult"
      >
        {{ showResult ? t`Hide details` : t`Show details` }}
      </button>
      <pre
        v-if="showResult"
        class="mt-2 max-h-64 overflow-auto rounded bg-surface-gray-1 p-2 text-xs text-ink-gray-7"
        >{{ JSON.stringify(entry.result, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import { Button as FrappeButton } from 'frappe-ui';
import type { ToolEntry } from 'src/ai/types';
import { computed, ref } from 'vue';

/**
 * One tool call of the transcript. A read is one line. A change shows what it
 * would do and waits for a click, because the model proposes and the person decides.
 */
const props = defineProps<{ entry: ToolEntry }>();
defineEmits<{ confirm: [id: string]; cancel: [id: string] }>();

const showResult = ref(false);
const preview = computed(() => props.entry.preview);

const TITLES: Record<string, () => string> = {
  list_record_types: () => t`Looking up record types`,
  describe_record_type: () => t`Looking up fields`,
  list_records: () => t`Reading records`,
  get_record: () => t`Reading a record`,
  count_records: () => t`Counting records`,
  list_reports: () => t`Looking up reports`,
  run_report: () => t`Running a report`,
  get_dashboard_summary: () => t`Reading summary figures`,
  open_screen: () => t`Opening a screen`,
  create_record: () => t`Create a record`,
  update_record: () => t`Change a record`,
  delete_record: () => t`Delete a record`,
  submit_document: () => t`Submit a document`,
  cancel_document: () => t`Cancel a document`,
};

const title = computed(
  () => TITLES[props.entry.call.name]?.() ?? props.entry.call.name
);

// A delete looks different from a create, so nobody learns to click through.
const cardClass = computed(() => {
  if (!preview.value) {
    return 'border-outline-gray-1';
  }

  return preview.value.destructive
    ? 'border-outline-red-2 bg-surface-red-1'
    : 'border-outline-amber-2 bg-surface-amber-1';
});

const dotClass = computed(() => {
  switch (props.entry.status) {
    case 'running':
      return 'bg-surface-blue-3 animate-pulse';
    case 'awaiting-confirmation':
      return preview.value?.destructive
        ? 'bg-surface-red-5'
        : 'bg-surface-amber-3';
    case 'failed':
      return 'bg-surface-red-5';
    case 'cancelled':
      return 'bg-surface-gray-4';
    default:
      return 'bg-surface-green-3';
  }
});

const prompt = computed(() => {
  const p = preview.value;
  const what = [p?.doctype_label, p?.name].filter(Boolean).join(' ');
  switch (p?.action) {
    case 'create':
      return t`The assistant wants to create a ${p.doctype_label}. Nothing has happened yet.`;
    case 'delete':
      return t`The assistant wants to delete ${what}. Nothing has happened yet.`;
    case 'cancel':
      return t`The assistant wants to cancel ${what}, reversing its ledger entries. Nothing has happened yet.`;
    case 'submit':
      return t`The assistant wants to submit ${what}, posting its ledger entries. Nothing has happened yet.`;
    default:
      return t`The assistant wants to change ${what}. Nothing has happened yet.`;
  }
});

const confirmLabel = computed(
  () =>
    ({
      create: t`Create`,
      update: t`Save changes`,
      delete: t`Delete`,
      submit: t`Submit`,
      cancel: t`Cancel document`,
    })[preview.value?.action ?? 'update']
);
</script>
