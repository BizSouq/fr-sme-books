<template>
  <div
    class="max-w-full overflow-x-auto rounded-lg border border-outline-gray-1"
    data-testid="variant-grid"
  >
    <table class="w-full border-collapse text-base">
      <thead>
        <tr class="bg-surface-gray-1 text-sm text-ink-gray-5">
          <th
            class="sticky start-0 z-[1] bg-surface-gray-1 px-3 py-2 text-start font-medium"
            scope="col"
          >
            {{ grid.columnAttribute }}
          </th>
          <th
            v-for="column of grid.columns"
            :key="column.value"
            scope="col"
            class="min-w-16 px-2 py-2 text-center font-semibold text-ink-gray-7"
          >
            {{ column.value }}
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
            class="sticky start-0 z-[1] whitespace-nowrap bg-surface-base px-3 py-2 text-start font-medium text-ink-gray-8"
          >
            <span class="flex items-center gap-2">
              <span
                v-if="row.color"
                class="size-4 shrink-0 rounded-full border border-outline-gray-2"
                :style="{ background: row.color }"
                aria-hidden="true"
              />
              {{ row.label || t`All` }}
            </span>
          </th>
          <td v-for="(cell, idx) of row.cells" :key="idx" class="p-1">
            <button
              v-if="cell"
              type="button"
              class="flex w-full min-w-14 flex-col items-center rounded-md px-2 py-1.5 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-4 disabled:cursor-not-allowed"
              :class="cellClass(cell)"
              :disabled="isUnavailable(cell)"
              :aria-label="
                getCellLabel(cell, row.label, grid.columns[idx].value)
              "
              :data-variant="cell.name"
              @click="$emit('select', cell)"
            >
              <span class="text-lg font-semibold tabular-nums" dir="ltr">
                {{ getQuantity(cell) }}
              </span>
              <span
                v-if="showRate"
                class="text-xs tabular-nums text-ink-gray-5"
                dir="ltr"
              >
                {{ fyo.format(cell.standard_rate, 'Currency') }}
              </span>
            </button>
            <span
              v-else
              class="flex h-full min-h-10 items-center justify-center text-ink-gray-3"
              aria-hidden="true"
              >·</span
            >
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import { fyo } from 'src/initFyo';
import type { Variant, VariantGrid } from 'src/utils/itemVariants';

/**
 * An article's sizes across and its other values, like colors, down. Each cell
 * is a variant with its stock; picking one emits it. In `pick` mode, a tracked
 * variant without stock can't be picked, as the POS sells only what it has.
 */
const props = withDefaults(
  defineProps<{
    grid: VariantGrid;
    /** Stock by variant, when it differs from the variants' own, as at a POS location. */
    stock?: Record<string, number>;
    showRate?: boolean;
    mode?: 'view' | 'pick';
  }>(),
  { stock: undefined, showRate: true, mode: 'view' }
);
defineEmits<{ select: [variant: Variant] }>();

function quantityOf(variant: Variant): number {
  return props.stock ? (props.stock[variant.name] ?? 0) : variant.stock_qty;
}

function getQuantity(variant: Variant): string {
  if (!variant.is_stock_item) {
    return '✓';
  }

  return String(quantityOf(variant));
}

function isUnavailable(variant: Variant): boolean {
  return (
    props.mode === 'pick' && !!variant.is_stock_item && quantityOf(variant) <= 0
  );
}

function cellClass(variant: Variant): string {
  if (isUnavailable(variant)) {
    return 'bg-surface-gray-1 text-ink-gray-4';
  }

  const low = variant.is_stock_item && quantityOf(variant) <= 0;
  return low
    ? 'bg-surface-red-1 text-ink-red-6 hover:bg-surface-red-2'
    : 'bg-surface-green-1 text-ink-green-7 hover:bg-surface-green-2';
}

function getCellLabel(variant: Variant, row: string, column: string): string {
  const name = [column, row].filter(Boolean).join(' / ');
  if (!variant.is_stock_item) {
    return name;
  }

  return t`${name}: ${quantityOf(variant)} in stock`;
}
</script>
