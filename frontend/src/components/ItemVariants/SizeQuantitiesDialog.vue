<template>
  <Modal
    :open-modal="open"
    :title="t`Add by size`"
    :subtitle="t`Pick an article, then type how many of each size.`"
    size="3xl"
    @closemodal="$emit('close')"
  >
    <div class="flex flex-col gap-4" data-testid="size-quantities">
      <div
        class="grid grid-cols-1 gap-4 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]"
      >
        <Link
          :df="articleField"
          :value="article"
          :border="true"
          :show-label="true"
          @change="setArticle"
        />
        <label class="flex flex-col gap-1.5">
          <span class="text-sm text-ink-gray-6">{{
            t`Rate for all sizes`
          }}</span>
          <FrappeTextInput
            v-model="rate"
            type="number"
            min="0"
            data-testid="size-rate"
            :placeholder="t`Item's own price`"
          />
        </label>
      </div>

      <p v-if="error" class="text-base text-ink-red-6">{{ error }}</p>
      <div
        v-else-if="article && !grid"
        class="h-28 animate-pulse rounded-lg bg-surface-gray-2"
      />
      <p
        v-else-if="grid && !grid.rows.length"
        class="text-base text-ink-gray-6"
      >
        {{ t`This article has no sizes or colors yet. Add them on its item.` }}
      </p>
      <div
        v-else-if="grid"
        class="max-w-full overflow-x-auto rounded-lg border border-outline-gray-1"
      >
        <table class="w-full border-collapse text-base">
          <thead>
            <tr class="bg-surface-gray-1 text-sm text-ink-gray-5">
              <th class="px-3 py-2 text-start font-medium" scope="col">
                {{ grid.columnAttribute }}
              </th>
              <th
                v-for="column of grid.columns"
                :key="column.value"
                scope="col"
                class="min-w-16 px-1 py-2 text-center font-semibold text-ink-gray-7"
              >
                {{ column.value }}
              </th>
              <th class="px-3 py-2 text-end font-medium" scope="col">
                {{ t`Qty` }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row of grid.rows"
              :key="row.label"
              class="border-t border-outline-gray-1"
            >
              <th
                scope="row"
                class="whitespace-nowrap px-3 py-2 text-start font-medium text-ink-gray-8"
              >
                <span class="flex items-center gap-2">
                  <span
                    v-if="row.color"
                    class="size-4 shrink-0 rounded-full border border-outline-gray-2"
                    :style="{ background: row.color }"
                    aria-hidden="true"
                  />
                  {{ row.label || t`Qty` }}
                </span>
              </th>
              <td v-for="(cell, idx) of row.cells" :key="idx" class="p-1">
                <input
                  v-if="cell"
                  v-model.number="quantities[cell.name]"
                  type="number"
                  min="0"
                  inputmode="numeric"
                  class="h-9 w-full min-w-14 rounded-md border border-outline-gray-2 bg-surface-base px-1 text-center text-base tabular-nums text-ink-gray-9 focus:border-outline-gray-4 focus:outline-none"
                  :aria-label="
                    [grid.columns[idx].value, row.label]
                      .filter(Boolean)
                      .join(' / ')
                  "
                  :data-variant="cell.name"
                  placeholder="0"
                />
                <span
                  v-else
                  class="flex h-9 items-center justify-center text-ink-gray-3"
                  aria-hidden="true"
                  >·</span
                >
              </td>
              <td
                class="px-3 text-end font-semibold tabular-nums text-ink-gray-8"
              >
                {{ rowTotal(row.cells) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    <template #actions="{ size }">
      <p class="me-auto text-base text-ink-gray-6" data-testid="size-total">
        {{ summary }}
      </p>
      <FrappeButton :size="size" @click="$emit('close')">{{
        t`Cancel`
      }}</FrappeButton>
      <FrappeButton
        :size="size"
        variant="solid"
        :disabled="!totalQuantity || isAdding"
        :loading="isAdding"
        @click="add"
      >
        {{ t`Add ${totalQuantity} to items` }}
      </FrappeButton>
    </template>
  </Modal>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import {
  Button as FrappeButton,
  TextInput as FrappeTextInput,
} from 'frappe-ui';
import { addItem } from 'models/helpers';
import Link from 'src/components/Controls/Link.vue';
import Modal from 'src/components/POS/POSDialog.vue';
import type { FrappeDoc } from 'src/frappe/document';
import { fyo } from 'src/initFyo';
import { getErrorMessage } from 'src/utils';
import {
  getRateField,
  getSizeLines,
  getVariantGrid,
  getVariants,
  type Variant,
  type VariantGrid,
} from 'src/utils/itemVariants';
import type { TargetField } from 'schemas/types';
import { computed, ref, watch } from 'vue';

/**
 * Adds an article to a document's items by size: one row per size with a
 * quantity, all at one rate when given, as a buyer fills an order sheet.
 */
const props = defineProps<{ open: boolean; doc: FrappeDoc }>();
const emit = defineEmits<{ close: [] }>();

const article = ref('');
const grid = ref<VariantGrid>();
const quantities = ref<Record<string, number | ''>>({});
const rate = ref('');
const error = ref('');
const isAdding = ref(false);

const articleField: TargetField = {
  fieldname: 'article',
  fieldtype: 'Link',
  target: 'Item',
  label: t`Article`,
  placeholder: t`Search an article with sizes`,
  create: false,
  filters: [['has_variants', '=', 1]],
} as TargetField;

watch(
  () => props.open,
  (open) => {
    if (open) {
      article.value = '';
      grid.value = undefined;
      quantities.value = {};
      rate.value = '';
      error.value = '';
    }
  }
);

const totalQuantity = computed(() =>
  getSizeLines(quantities.value).reduce((total, { qty }) => total + qty, 0)
);
const summary = computed(() => {
  if (!totalQuantity.value) {
    return t`No quantities yet`;
  }

  if (rate.value === '') {
    return t`${totalQuantity.value} pcs`;
  }

  const amount = fyo.pesa(Number(rate.value)).mul(totalQuantity.value);
  return t`${totalQuantity.value} pcs · ${fyo.format(amount, 'Currency')}`;
});

function rowTotal(cells: (Variant | undefined)[]): number {
  return cells.reduce(
    (total, cell) => total + (Number(cell && quantities.value[cell.name]) || 0),
    0
  );
}

async function setArticle(value: string) {
  article.value = value;
  grid.value = undefined;
  quantities.value = {};
  error.value = '';
  if (!value) {
    return;
  }

  try {
    grid.value = getVariantGrid(await getVariants(value)) ?? {
      columnAttribute: '',
      columns: [],
      rows: [],
    };
  } catch (err) {
    error.value = getErrorMessage(err as Error);
  }
}

async function add() {
  isAdding.value = true;
  try {
    const rateField = getRateField(props.doc);
    for (const { item, qty } of getSizeLines(quantities.value)) {
      await addItem(item, props.doc, qty);
      if (rate.value === '' || !rateField) {
        continue;
      }

      const rows = (props.doc.items ?? []) as FrappeDoc[];
      const row = rows.find((existing) => existing.item_code === item);
      await row?.set(rateField, fyo.pesa(Number(rate.value)));
    }

    emit('close');
  } catch (err) {
    error.value = getErrorMessage(err as Error);
  } finally {
    isAdding.value = false;
  }
}
</script>
