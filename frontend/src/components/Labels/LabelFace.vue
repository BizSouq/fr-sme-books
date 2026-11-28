<template>
  <div
    class="label-face"
    :style="{
      position: 'relative',
      width: `${sheet.label_width}mm`,
      height: `${sheet.label_height}mm`,
      overflow: 'hidden',
      background: '#fff',
      color: '#000',
      fontFamily: LABEL_FONT,
    }"
  >
    <div
      v-for="element of elements"
      :key="element.id"
      :style="{
        position: 'absolute',
        left: `${element.x}mm`,
        top: `${element.y}mm`,
        width: `${element.width}mm`,
        height: `${element.height}mm`,
        overflow: 'hidden',
      }"
    >
      <BarcodeBars
        v-if="element.field === 'barcode'"
        :code="data.barcode"
        :show-number="element.showNumber"
        :font-size="element.fontSize"
        :placeholder="noBarcodeText"
      />
      <div
        v-else
        :style="{
          display: 'flex',
          height: '100%',
          alignItems: 'center',
          justifyContent: justify(element.align),
          textAlign: element.align ?? 'left',
          fontSize: `${element.fontSize}pt`,
          fontWeight: element.bold ? 700 : 400,
          lineHeight: 1.15,
          overflowWrap: 'anywhere',
        }"
      >
        <span>{{ getElementText(element, data, priceFormat) }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  getElementText,
  type Align,
  type LabelData,
  type LabelElement,
  type LabelSheet,
  type PriceFormat,
} from 'src/utils/labels';
import BarcodeBars from './BarcodeBars.vue';

/** One label as it prints: millimetres on paper, any scale on screen. */
withDefaults(
  defineProps<{
    sheet: Pick<LabelSheet, 'label_width' | 'label_height'>;
    elements: LabelElement[];
    data: LabelData;
    priceFormat: PriceFormat;
    noBarcodeText?: string;
  }>(),
  { noBarcodeText: '' }
);

// Bangla in Hind Siliguri, which the app ships, else the printer computer's Bangla font.
const LABEL_FONT =
  "Arial, 'Hind Siliguri', 'Noto Sans Bengali', 'Nirmala UI', Vrinda, sans-serif";

function justify(align?: Align) {
  return { left: 'flex-start', center: 'center', right: 'flex-end' }[
    align ?? 'left'
  ];
}
</script>
