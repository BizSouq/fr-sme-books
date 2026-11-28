<template>
  <label class="flex min-w-0 flex-col gap-1.5">
    <span class="truncate text-xs text-ink-gray-5">{{ label }}</span>
    <input
      type="number"
      inputmode="decimal"
      class="h-7 w-full min-w-0 rounded border border-outline-gray-2 bg-surface-base px-2 text-base tabular-nums text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none"
      :value="value"
      :step="step"
      min="0"
      @change="onChange"
    />
  </label>
</template>

<script setup lang="ts">
/** A number of millimetres or points, given back when the field is left. */
withDefaults(defineProps<{ label: string; value: number; step?: number }>(), {
  step: 0.1,
});
const emit = defineEmits<{ change: [value: number] }>();

function onChange(event: Event) {
  const value = Number((event.target as HTMLInputElement).value);
  if (Number.isFinite(value)) {
    emit('change', value);
  }
}
</script>
