<template>
  <Modal
    :open-modal="openModal"
    :title="t`Pick size or color`"
    :subtitle="itemName"
    size="2xl"
    @closemodal="close"
  >
    <div class="flex flex-col gap-3" data-testid="pos-variant-picker">
      <p v-if="isMobile" class="break-words text-base text-ink-gray-6">
        {{ itemName }}
      </p>
      <p v-if="error" class="text-base text-ink-red-6">{{ error }}</p>
      <div
        v-else-if="!grid"
        class="h-28 animate-pulse rounded-lg bg-surface-gray-2"
      />
      <p v-else-if="!grid.rows.length" class="text-base text-ink-gray-6">
        {{ t`This article has no sizes or colors yet. Add them on its item.` }}
      </p>
      <template v-else>
        <VariantGrid :grid="grid" :stock="stock" mode="pick" @select="select" />
        <p class="text-sm text-ink-gray-5">
          {{ t`Numbers are stock here. Grey sizes are sold out.` }}
        </p>
      </template>
    </div>
    <template #actions="{ size }">
      <FrappeButton :size="size" class="min-w-24" @click="close">{{
        t`Cancel`
      }}</FrappeButton>
    </template>
  </Modal>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import { Button as FrappeButton } from 'frappe-ui';
import VariantGrid from 'src/components/ItemVariants/VariantGrid.vue';
import Modal from 'src/components/POS/POSDialog.vue';
import type { ItemQtyMap } from 'src/components/POS/types';
import { getErrorMessage } from 'src/utils';
import {
  getVariantGrid,
  getVariants,
  type Variant,
  type VariantGrid as Grid,
} from 'src/utils/itemVariants';
import { isMobile } from 'src/utils/viewport';
import { computed, ref, watch } from 'vue';

/** The POS's size and color picker: tap a size of an article to add it to the cart. */
const props = defineProps<{
  openModal: boolean;
  itemCode: string;
  itemName: string;
  itemQtyMap: ItemQtyMap;
}>();
const emit = defineEmits<{
  toggleModal: [name: string];
  variantSelected: [name: string];
}>();

const grid = ref<Grid>();
const error = ref('');

const stock = computed(() =>
  Object.fromEntries(
    Object.entries(props.itemQtyMap).map(([name, { availableQty }]) => [
      name,
      availableQty,
    ])
  )
);

watch(
  () => [props.openModal, props.itemCode] as const,
  async ([open, item]) => {
    if (!open || !item) {
      return;
    }

    grid.value = undefined;
    error.value = '';
    try {
      grid.value = getVariantGrid(await getVariants(item)) ?? {
        columnAttribute: '',
        columns: [],
        rows: [],
      };
    } catch (err) {
      error.value = getErrorMessage(err as Error);
    }
  },
  { immediate: true }
);

function select(variant: Variant) {
  emit('variantSelected', variant.name);
  emit('toggleModal', 'VariantSelection');
}

function close() {
  emit('toggleModal', 'VariantSelection');
}
</script>
