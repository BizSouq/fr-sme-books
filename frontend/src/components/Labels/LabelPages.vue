<template>
  <div class="label-pages">
    <div
      v-for="(page, pageIndex) of pages"
      :key="pageIndex"
      class="label-page"
      :style="{
        position: 'relative',
        width: `${layout.pageWidth}mm`,
        height: `${layout.pageHeight}mm`,
        overflow: 'hidden',
        background: '#fff',
        breakAfter: pageIndex < pages.length - 1 ? 'page' : 'auto',
        pageBreakAfter: pageIndex < pages.length - 1 ? 'always' : 'auto',
      }"
    >
      <template v-for="(label, index) of page" :key="index">
        <LabelFace
          v-if="label"
          :style="{
            position: 'absolute',
            left: `${getLabelPosition(sheet, index, layout).left}mm`,
            top: `${getLabelPosition(sheet, index, layout).top}mm`,
          }"
          :sheet="sheet"
          :elements="elements"
          :data="label"
          :price-format="priceFormat"
          :no-barcode-text="noBarcodeText"
        />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  getLabelPosition,
  getPageLayout,
  type LabelData,
  type LabelElement,
  type LabelSheet,
  type PriceFormat,
} from 'src/utils/labels';
import { computed } from 'vue';
import LabelFace from './LabelFace.vue';

/** Pages of labels as they print: a roll's row of labels, or an A4 sheet. */
const props = defineProps<{
  sheet: LabelSheet;
  elements: LabelElement[];
  pages: (LabelData | null)[][];
  priceFormat: PriceFormat;
  noBarcodeText?: string;
}>();

const layout = computed(() => getPageLayout(props.sheet));
</script>
