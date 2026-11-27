<template>
  <section
    class="flex flex-col gap-3"
    :class="isMobile ? 'p-4' : ''"
    data-testid="item-variants"
  >
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="min-w-0">
        <h2 class="text-lg font-semibold text-ink-gray-8">
          {{ t`Sizes and colors` }}
        </h2>
        <p class="text-sm text-ink-gray-5">{{ summary }}</p>
      </div>
      <FrappeButton
        v-if="data?.attributes.length && grid?.rows.length && canCreate"
        icon-left="lucide-plus"
        :label="t`Add sizes or colors`"
        @click="isCreatorOpen = true"
      />
    </div>

    <p v-if="error" class="text-base text-ink-red-6">{{ error }}</p>
    <div
      v-else-if="!data"
      class="h-24 animate-pulse rounded-lg bg-surface-gray-2"
    />
    <p
      v-else-if="!data.attributes.length"
      class="rounded-lg border border-dashed border-outline-gray-2 p-4 text-base text-ink-gray-6"
    >
      {{
        t`Add an attribute, like Size or Color, under Attributes and save. Then pick its sizes and colors here.`
      }}
    </p>
    <div
      v-else-if="!grid || !grid.rows.length"
      class="flex flex-col items-start gap-3 rounded-lg border border-dashed border-outline-gray-2 p-4"
    >
      <p class="text-base text-ink-gray-6">
        {{
          t`No sizes or colors yet. Pick the ones this article comes in, and Books creates an item for each, with its own stock.`
        }}
      </p>
      <FrappeButton
        v-if="canCreate"
        variant="solid"
        icon-left="lucide-grid-3x3"
        :label="t`Pick sizes and colors`"
        @click="isCreatorOpen = true"
      />
    </div>
    <template v-else>
      <VariantGrid :grid="grid" @select="open" />
      <p class="text-sm text-ink-gray-5">
        {{
          t`Numbers are stock in hand. Tap one to open that size, to set its price or barcode.`
        }}
      </p>
    </template>

    <VariantCreatorDialog
      v-if="data"
      :open="isCreatorOpen"
      :item="doc.name!"
      :item-name="(doc.item_name as string) || doc.name!"
      :default-rate="defaultRate"
      :data="data"
      @close="isCreatorOpen = false"
      @created="onCreated"
    />
  </section>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import { Button as FrappeButton } from 'frappe-ui';
import type { Money } from 'pesa';
import type { FrappeDoc } from 'src/frappe/document';
import { fyo } from 'src/initFyo';
import { getErrorMessage } from 'src/utils';
import {
  getVariantGrid,
  getVariants,
  type Variant,
  type VariantData,
} from 'src/utils/itemVariants';
import { getFormRoute, routeTo } from 'src/utils/ui';
import { isMobile } from 'src/utils/viewport';
import { computed, onMounted, ref, watch } from 'vue';
import VariantCreatorDialog from './VariantCreatorDialog.vue';
import VariantGrid from './VariantGrid.vue';

/** A saved article's sizes and colors on its Item form: a stock grid, and a way to add more. */
const props = defineProps<{ doc: FrappeDoc }>();

const data = ref<VariantData>();
const error = ref('');
const isCreatorOpen = ref(false);

const grid = computed(() => data.value && getVariantGrid(data.value));
const canCreate = computed(() => fyo.can('Item', 'create'));
const defaultRate = computed(
  () => (props.doc.standard_rate as Money | undefined)?.float ?? 0
);
const summary = computed(() => {
  if (!data.value) {
    return '';
  }

  const count = data.value.variants.length;
  const stock = data.value.variants.reduce(
    (total, { stock_qty }) => total + stock_qty,
    0
  );
  const attributes = data.value.attributes.map(({ attribute }) => attribute);
  return [attributes.join(' × '), t`${count} items`, t`${stock} in stock`].join(
    ' · '
  );
});

async function load() {
  error.value = '';
  try {
    data.value = await getVariants(props.doc.name!);
  } catch (err) {
    error.value = getErrorMessage(err as Error);
  }
}

async function onCreated() {
  isCreatorOpen.value = false;
  await load();
}

async function open(variant: Variant) {
  await routeTo(getFormRoute('Item', variant.name));
}

onMounted(load);
// A save can change the attributes the grid is by.
watch(() => props.doc.modified, load);
</script>
