<template>
  <div class="flex h-full min-h-0 flex-col bg-surface-base">
    <PageHeader :title="t`Print Labels`">
      <template #mobile>
        <FrappeButton
          variant="solid"
          icon="lucide-printer"
          :label="printLabel"
          :loading="isPrinting"
          :disabled="!labelCount || !activeTemplate"
          @click="print"
        />
      </template>
      <FrappeButton
        variant="solid"
        icon-left="lucide-printer"
        :label="printLabel"
        :loading="isPrinting"
        :disabled="!labelCount || !activeTemplate"
        data-testid="labels-print"
        @click="print"
      />
    </PageHeader>

    <div
      v-if="isLoaded"
      class="min-h-0 flex-1 overflow-y-auto lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:overflow-hidden"
      data-testid="print-labels"
    >
      <!-- What to label, and how many of each -->
      <section class="flex flex-col gap-3 p-4 lg:min-h-0 lg:overflow-y-auto">
        <div class="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 class="text-base-semibold text-ink-gray-9">
              {{ sourceTitle }}
            </h2>
            <p class="text-p-sm text-ink-gray-6">
              {{ t`Change how many labels each item gets, or add more items.` }}
            </p>
          </div>
          <FrappeButton
            v-if="rows.length"
            size="sm"
            :label="t`One label each`"
            @click="rows.forEach((row) => (row.qty = 1))"
          />
        </div>

        <div
          v-if="rows.length"
          class="shrink-0 overflow-hidden rounded-lg border border-outline-gray-1"
        >
          <table class="w-full border-collapse text-base">
            <thead>
              <tr class="bg-surface-gray-1 text-sm text-ink-gray-5">
                <th class="px-3 py-2 text-start font-medium" scope="col">
                  {{ t`Item` }}
                </th>
                <th
                  class="hidden px-3 py-2 text-start font-medium sm:table-cell"
                  scope="col"
                >
                  {{ t`Barcode` }}
                </th>
                <th class="w-28 px-3 py-2 text-end font-medium" scope="col">
                  {{ t`Labels` }}
                </th>
                <th class="w-10" scope="col">
                  <span class="sr-only">{{ t`Remove` }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, index) of rows"
                :key="`${row.item_code}-${index}`"
                class="border-t border-outline-gray-1"
                data-testid="label-row"
              >
                <td class="px-3 py-2">
                  <div class="text-ink-gray-9">{{ row.item_name }}</div>
                  <div class="text-sm text-ink-gray-5">
                    {{ formatPrice(row.price) }}
                    <span class="sm:hidden"
                      >· {{ row.barcode || t`New barcode` }}</span
                    >
                  </div>
                </td>
                <td class="hidden px-3 py-2 sm:table-cell">
                  <span
                    v-if="row.barcode"
                    class="font-mono text-sm text-ink-gray-7"
                    >{{ row.barcode }}</span
                  >
                  <FrappeBadge
                    v-else
                    theme="amber"
                    :label="t`Gets one on print`"
                  />
                </td>
                <td class="px-3 py-1.5">
                  <input
                    v-model.number="row.qty"
                    type="number"
                    min="0"
                    step="1"
                    inputmode="numeric"
                    class="h-8 w-full rounded-md border border-outline-gray-2 bg-surface-base px-2 text-end text-base tabular-nums text-ink-gray-9 focus:border-outline-gray-4 focus:outline-none"
                    :aria-label="t`Labels for ${row.item_name}`"
                    data-testid="label-qty"
                  />
                </td>
                <td class="pe-2">
                  <FrappeButton
                    variant="ghost"
                    icon="lucide-x"
                    :label="t`Remove`"
                    @click="rows.splice(index, 1)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState
          v-else
          class="rounded-lg border border-dashed border-outline-gray-2 py-10"
          icon="lucide-barcode"
          :title="t`Pick the items to label`"
          :description="
            t`Or print from an item or a purchase receipt: open it and pick Print Labels.`
          "
        />

        <Link
          class="max-w-md"
          :df="addItemField"
          :value="''"
          :border="true"
          :show-label="true"
          data-testid="labels-add-item"
          @change="addItem"
        />
        <p
          v-if="missingCount"
          class="flex items-start gap-2 rounded-lg bg-surface-amber-1 p-3 text-p-sm text-ink-gray-8"
        >
          <span class="lucide-info mt-0.5 size-4 shrink-0" aria-hidden="true" />
          {{
            t`${missingCount} items have no barcode yet. Books gives each a new one when you print, and saves it on the item so the till can scan it.`
          }}
        </p>
      </section>

      <!-- The label design and a preview of the first page -->
      <aside
        class="flex flex-col gap-4 border-outline-gray-1 bg-surface-gray-1 p-4 lg:min-h-0 lg:overflow-y-auto lg:border-s"
      >
        <div class="flex flex-col gap-2">
          <FrappeSelect
            :label="t`Label design`"
            :model-value="templateName"
            :options="templateOptions"
            data-testid="labels-template"
            @update:model-value="
              (value) => (templateName = String(value ?? ''))
            "
          />
          <div class="flex flex-wrap gap-2">
            <FrappeButton
              v-if="activeTemplate"
              size="sm"
              icon-left="lucide-pencil-ruler"
              :label="t`Edit design`"
              @click="
                routeTo(`/label-designer/${encodeURIComponent(templateName)}`)
              "
            />
            <FrappeButton
              size="sm"
              icon-left="lucide-plus"
              :label="t`New design`"
              @click="routeTo('/label-designer/new-label')"
            />
            <FrappeButton
              size="sm"
              variant="ghost"
              :label="t`All designs`"
              @click="routeTo('/list/LabelTemplate')"
            />
          </div>
        </div>

        <NumberInput
          v-if="activeTemplate?.paper === 'A4 Sheet'"
          class="max-w-48"
          :label="t`Skip used labels on the sheet`"
          :value="skip"
          :step="1"
          @change="(value) => (skip = Math.max(0, Math.round(value)))"
        />

        <div v-if="activeTemplate" class="flex flex-col gap-2">
          <div
            class="flex items-baseline justify-between text-sm text-ink-gray-6"
          >
            <span>{{ t`Preview` }}</span>
            <span>{{ pageSummary }}</span>
          </div>
          <div
            ref="previewArea"
            class="flex justify-center overflow-hidden rounded-lg bg-surface-gray-2 p-4"
          >
            <div
              class="shrink-0 shadow-sm ring-1 ring-outline-gray-2"
              :style="{
                width: `${layout.pageWidth * PX_PER_MM * previewScale}px`,
                height: `${layout.pageHeight * PX_PER_MM * previewScale}px`,
              }"
            >
              <div
                :style="{
                  transform: `scale(${previewScale})`,
                  transformOrigin: 'top left',
                }"
              >
                <LabelPages
                  :sheet="activeTemplate"
                  :elements="activeTemplate.elements"
                  :pages="previewPages"
                  :price-format="priceFormat"
                  :no-barcode-text="t`New barcode`"
                />
              </div>
            </div>
          </div>
          <p class="text-p-sm text-ink-gray-5">{{ printerHint }}</p>
        </div>
      </aside>
    </div>
    <div v-else class="flex flex-1 items-center justify-center">
      <FrappeErrorMessage v-if="loadError" :message="loadError" />
      <FrappeSpinner v-else class="size-6" />
    </div>

    <!-- Every page, out of sight, for the print document -->
    <div
      v-if="printPages.length && activeTemplate"
      ref="printArea"
      aria-hidden="true"
      style="position: fixed; left: -10000px; top: 0"
    >
      <LabelPages
        :sheet="activeTemplate"
        :elements="activeTemplate.elements"
        :pages="printPages"
        :price-format="priceFormat"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useElementSize } from '@vueuse/core';
import { t } from 'fyo';
import {
  Badge as FrappeBadge,
  Button as FrappeButton,
  ErrorMessage as FrappeErrorMessage,
  Select as FrappeSelect,
  Spinner as FrappeSpinner,
} from 'frappe-ui';
import type { TargetField } from 'schemas/types';
import Link from 'src/components/Controls/Link.vue';
import EmptyState from 'src/components/EmptyState.vue';
import LabelPages from 'src/components/Labels/LabelPages.vue';
import NumberInput from 'src/components/Labels/NumberInput.vue';
import { getPriceFormat } from 'src/components/Labels/priceFormat';
import PageHeader from 'src/components/PageHeader.vue';
import { getAllDocuments } from 'src/frappe/api';
import { getErrorMessage } from 'src/utils';
import { showToast } from 'src/utils/interactive';
import {
  countLabels,
  createBarcodes,
  formatLabelPrice,
  getLabelItems,
  getLabelRows,
  getPageLayout,
  getPages,
  LABEL_DOCTYPE,
  parseTemplate,
  type LabelData,
  type LabelRow,
  type LabelSource,
  type LabelTemplate,
} from 'src/utils/labels';
import { printDocument } from 'src/utils/printDocument';
import { routeTo } from 'src/utils/ui';
import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';

/**
 * Prints barcode labels for an item's sizes, a purchase receipt's items or
 * items picked here: a label a piece by default, in the shop's label design.
 */
const route = useRoute();
const PX_PER_MM = 96 / 25.4;

const rows = ref<LabelRow[]>([]);
const templates = ref<LabelTemplate[]>([]);
const templateName = ref('');
const company = ref('');
const skip = ref(0);
const isLoaded = ref(false);
const loadError = ref('');
const isPrinting = ref(false);
const printPages = ref<(LabelData | null)[][]>([]);
const printArea = ref<HTMLElement>();
const previewArea = ref<HTMLElement>();
const { width: previewWidth } = useElementSize(previewArea);
const priceFormat = getPriceFormat();

const source = computed(() => {
  const value = route.query.source;
  return value === 'Item' || value === 'Purchase Receipt'
    ? (value as LabelSource)
    : '';
});
const sourceNames = computed(() =>
  ([] as unknown[])
    .concat(route.query.names ?? [])
    .flatMap((name) => String(name).split(','))
    .filter(Boolean)
);
const sourceTitle = computed(() => {
  const names = sourceNames.value.join(', ');
  if (source.value === 'Purchase Receipt') {
    return t`Items received on ${names}`;
  }

  if (source.value === 'Item') {
    return t`Labels for ${names}`;
  }

  return t`Items to label`;
});

const activeTemplate = computed(() =>
  templates.value.find((template) => template.name === templateName.value)
);
const templateOptions = computed(() =>
  templates.value.map((template) => ({
    label: template.template_name,
    value: template.name!,
  }))
);
const layout = computed(() =>
  activeTemplate.value
    ? getPageLayout(activeTemplate.value)
    : { pageWidth: 0, pageHeight: 0, perPage: 1, rows: 1, columns: 1 }
);
const labelCount = computed(() => countLabels(rows.value));
const missingCount = computed(
  () => rows.value.filter((row) => !row.barcode && row.qty > 0).length
);
const printLabel = computed(() =>
  labelCount.value === 1
    ? t`Print 1 label`
    : t`Print ${labelCount.value} labels`
);
const pageCount = computed(
  () =>
    getPages(rows.value, layout.value.perPage, isA4.value ? skip.value : 0)
      .length
);
const isA4 = computed(() => activeTemplate.value?.paper === 'A4 Sheet');
const pageSummary = computed(() =>
  isA4.value ? t`${pageCount.value} A4 sheets` : t`${labelCount.value} labels`
);
const previewPages = computed(() => {
  const withCompany = rows.value.map((row) => ({
    ...row,
    company: company.value,
  }));
  const [first] = getPages(
    withCompany,
    layout.value.perPage,
    isA4.value ? skip.value : 0
  );
  return [first ?? []];
});
const previewScale = computed(() => {
  const width = layout.value.pageWidth * PX_PER_MM;
  if (!width || !previewWidth.value) {
    return 1;
  }

  // Small labels show bigger; an A4 page shrinks to the panel.
  return Math.min(4, (previewWidth.value - 32) / width);
});
const printerHint = computed(() => {
  if (isA4.value) {
    return t`Print at actual size (100%), not "Fit to page", so the labels line up with the sheet.`;
  }

  return t`In the print dialog, pick the label printer and set the paper to ${layout.value.pageWidth} × ${layout.value.pageHeight} mm, with no margins.`;
});

const addItemField = {
  fieldname: 'add_item',
  fieldtype: 'Link',
  target: 'Item',
  label: t`Add an item`,
  placeholder: t`Search items`,
  create: false,
  filters: [['has_variants', '=', 0]],
} as TargetField;

onMounted(load);
watch(() => route.fullPath, load);

async function load() {
  if (route.path !== '/print-labels') {
    return;
  }

  isLoaded.value = false;
  loadError.value = '';
  try {
    const [result, saved] = await Promise.all([
      getLabelRows(source.value, sourceNames.value),
      getAllDocuments(LABEL_DOCTYPE, {
        fields: ['*'],
        orderBy: 'is_default desc, creation asc',
      }),
    ]);
    rows.value = result.rows;
    company.value = result.company;
    templates.value = saved.map(parseTemplate);
    const asked = route.query.template;
    templateName.value =
      (typeof asked === 'string' &&
      templates.value.some((tmpl) => tmpl.name === asked)
        ? asked
        : templates.value[0]?.name) ?? '';
    isLoaded.value = true;
  } catch (error) {
    loadError.value = getErrorMessage(error as Error);
  }
}

async function addItem(item: string) {
  if (!item) {
    return;
  }

  const existing = rows.value.find((row) => row.item_code === item);
  if (existing) {
    existing.qty += 1;
    return;
  }

  try {
    rows.value.push(...(await getLabelItems([item])));
  } catch (error) {
    showToast({ type: 'error', message: getErrorMessage(error as Error) });
  }
}

function formatPrice(price?: number) {
  return typeof price === 'number'
    ? formatLabelPrice(price, {}, priceFormat)
    : '';
}

/** Gives the items without a barcode one, so every label scans. */
async function ensureBarcodes() {
  const missing = [
    ...new Set(
      rows.value
        .filter((row) => !row.barcode && row.qty > 0)
        .map((row) => row.item_code)
    ),
  ];
  if (!missing.length) {
    return;
  }

  const barcodes = await createBarcodes(missing);
  for (const row of rows.value) {
    row.barcode ||= barcodes[row.item_code] ?? '';
  }

  showToast({
    type: 'success',
    message:
      missing.length === 1
        ? t`Gave 1 item a new barcode`
        : t`Gave ${missing.length} items a new barcode`,
  });
}

async function print() {
  const template = activeTemplate.value;
  if (!template) {
    return;
  }

  isPrinting.value = true;
  try {
    await ensureBarcodes();
    const withCompany = rows.value.map((row) => ({
      ...row,
      company: company.value,
    }));
    printPages.value = getPages(
      withCompany,
      layout.value.perPage,
      isA4.value ? skip.value : 0
    );
    await nextTick();
    const html = printArea.value?.innerHTML ?? '';
    await printDocument(
      template.template_name,
      html,
      layout.value.pageWidth / 10,
      layout.value.pageHeight / 10
    );
  } catch (error) {
    showToast({ type: 'error', message: getErrorMessage(error as Error) });
  } finally {
    isPrinting.value = false;
    printPages.value = [];
  }
}
</script>
