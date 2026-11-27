<template>
  <div v-if="hasArticles" class="flex items-end">
    <FrappeButton
      icon-left="lucide-grid-3x3"
      :label="t`Add by size`"
      data-testid="add-by-size"
      @click="isOpen = true"
    />
    <SizeQuantitiesDialog :open="isOpen" :doc="doc" @close="isOpen = false" />
  </div>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import { Button as FrappeButton } from 'frappe-ui';
import { getCount } from 'src/frappe/api';
import type { FrappeDoc } from 'src/frappe/document';
import { onMounted, ref } from 'vue';
import SizeQuantitiesDialog from './SizeQuantitiesDialog.vue';

/** Opens the size sheet over a document's items, once the shop has an article with sizes. */
defineProps<{ doc: FrappeDoc }>();

const hasArticles = ref(false);
const isOpen = ref(false);

onMounted(async () => {
  try {
    hasArticles.value =
      (await getCount('Books Item', [['has_variants', '=', 1]], [])) > 0;
  } catch {
    hasArticles.value = false;
  }
});
</script>
