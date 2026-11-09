<template>
  <div class="h-64 min-w-0">
    <FrappeDonutChart
      v-if="chart.type === 'donut'"
      :title="chart.title"
      :data="donutRows"
      category="label"
      value="value"
      :format="format"
    />
    <FrappeLineChart
      v-else-if="chart.type === 'line'"
      :title="chart.title"
      :data="axis.rows"
      x="label"
      :y="axis.y"
      :series-config="axis.seriesConfig"
      :x-axis="{ type: 'category' }"
      :y-axis="{ format }"
    />
    <FrappeBarChart
      v-else
      :title="chart.title"
      :data="axis.rows"
      x="label"
      :y="axis.y"
      :series-config="axis.seriesConfig"
      :x-axis="{ type: 'category' }"
      :y-axis="{ format }"
    />
  </div>
</template>

<script setup lang="ts">
import {
  BarChart as FrappeBarChart,
  DonutChart as FrappeDonutChart,
  LineChart as FrappeLineChart,
} from 'frappe-ui/charts';
import { getAxisRows, getDonutRows } from 'src/ai/charts';
import type { AiChartSpec } from 'src/ai/types';
import { fyo } from 'src/initFyo';
import { computed } from 'vue';

/** A chart the assistant wrote into its reply, drawn as the dashboard draws its own. */
const props = defineProps<{ chart: AiChartSpec }>();

const axis = computed(() => getAxisRows(props.chart));
const donutRows = computed(() => getDonutRows(props.chart));
const format = (value: number) => fyo.format(value ?? 0, 'Float');
</script>
