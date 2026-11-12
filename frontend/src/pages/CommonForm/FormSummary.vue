<template>
  <aside class="flex flex-col gap-4" :aria-label="t`Summary`">
    <section
      v-if="grandTotal"
      class="books-kpi p-5"
      style="--kpi: var(--books-brand)"
      data-testid="form-summary-total"
    >
      <p class="text-base text-ink-gray-6">{{ grandTotal.label }}</p>
      <p
        class="mt-1 truncate text-3xl font-semibold tabular-nums"
        dir="ltr"
        :data-fieldname="grandTotal.fieldname"
      >
        {{ getValue(grandTotal) }}
      </p>
      <dl
        v-if="rows.length"
        class="mt-4 flex flex-col gap-2 border-t border-white/20 pt-4 text-base"
      >
        <div
          v-for="field of rows"
          :key="field.fieldname"
          class="flex justify-between gap-3"
          :data-fieldname="field.fieldname"
        >
          <dt class="min-w-0 truncate text-ink-gray-6">{{ field.label }}</dt>
          <dd class="font-semibold tabular-nums" dir="ltr">
            {{ getValue(field) }}
          </dd>
        </div>
      </dl>
      <div
        v-if="outstanding"
        class="mt-4 flex justify-between gap-3 rounded-lg bg-surface-gray-3 px-4 py-2.5 text-base"
        :data-fieldname="outstanding.fieldname"
      >
        <span class="min-w-0 truncate">{{ outstanding.label }}</span>
        <span class="font-semibold tabular-nums" dir="ltr">
          {{ getValue(outstanding) }}
        </span>
      </div>
    </section>

    <!-- Fields outside the money card, e.g. stock not shipped. -->
    <div
      v-for="field of stats"
      :key="field.fieldname"
      class="books-panel flex items-center gap-3 border border-outline-gray-1 p-4"
      :data-fieldname="field.fieldname"
    >
      <div
        class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-surface-amber-2 text-ink-amber-7"
      >
        <span class="lucide-package size-5" aria-hidden="true" />
      </div>
      <dl class="min-w-0">
        <dt class="truncate text-sm text-ink-gray-5">{{ field.label }}</dt>
        <dd
          class="text-lg font-semibold tabular-nums text-ink-gray-9"
          dir="ltr"
        >
          {{ getValue(field) }}
        </dd>
      </dl>
    </div>
  </aside>
</template>
<script lang="ts">
import { Field } from 'schemas/types';
import { isCalculating } from 'src/frappe/calculated';
import type { FrappeDoc } from 'src/frappe/document';
import { fyo } from 'src/initFyo';
import { defineComponent, PropType } from 'vue';

/**
 * The invoice form's side column: the grand total card with the amounts
 * that make it up, the outstanding amount, then any other read-only figures.
 */
export default defineComponent({
  props: {
    doc: { type: Object as PropType<FrappeDoc>, required: true },
    fields: { type: Array as PropType<Field[]>, required: true },
  },
  computed: {
    grandTotal(): Field | undefined {
      return this.fields.find((field) => field.fieldname === 'grand_total');
    },
    outstanding(): Field | undefined {
      return this.fields.find(
        (field) => field.fieldname === 'outstanding_amount'
      );
    },
    rows(): Field[] {
      return this.fields.filter(
        (field) =>
          field.fieldtype === 'Currency' &&
          field !== this.grandTotal &&
          field !== this.outstanding
      );
    },
    stats(): Field[] {
      return this.fields.filter(
        (field) =>
          field !== this.grandTotal &&
          field !== this.outstanding &&
          !this.rows.includes(field)
      );
    },
  },
  methods: {
    getValue(field: Field): string {
      if (isCalculating(this.doc, field)) {
        return this.t`Calculating…`;
      }

      return fyo.format(this.doc.get(field.fieldname), field, this.doc);
    },
  },
});
</script>
