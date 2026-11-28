<template>
  <div
    class="flex h-full w-full flex-col"
    :style="{ textAlign: 'center' }"
    data-testid="label-barcode"
  >
    <svg
      v-if="encoded"
      class="min-h-0 w-full flex-1"
      :viewBox="`0 0 ${encoded.modules.length} 10`"
      preserveAspectRatio="none"
      shape-rendering="crispEdges"
      role="img"
      :aria-label="encoded.text"
    >
      <rect
        v-for="bar of bars"
        :key="bar.x"
        :x="bar.x"
        y="0"
        :width="bar.width"
        height="10"
        fill="#000"
      />
    </svg>
    <div
      v-else
      class="flex min-h-0 w-full flex-1 items-center justify-center"
      :style="{ border: '0.2mm dashed #999', color: '#666' }"
    >
      {{ placeholder }}
    </div>
    <div
      v-if="showNumber && encoded"
      :style="{
        fontSize: `${fontSize}pt`,
        lineHeight: 1.1,
        letterSpacing: encoded.format === 'Code 128' ? '0' : '0.08em',
        fontFamily: 'Arial, Helvetica, sans-serif',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
      }"
    >
      {{ encoded.text }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { encodeBarcode, getBars } from 'src/utils/barcode';
import { computed } from 'vue';

/** A barcode's bars, stretched to fill the box, with its digits under them. */
const props = defineProps<{
  code?: string;
  showNumber?: boolean;
  fontSize: number;
  /** Shown in place of a code that's missing or can't be drawn. */
  placeholder: string;
}>();

const encoded = computed(() =>
  props.code ? encodeBarcode(props.code) : undefined
);
const bars = computed(() =>
  encoded.value ? getBars(encoded.value.modules) : []
);
</script>
