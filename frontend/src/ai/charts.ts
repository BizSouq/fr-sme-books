import type { AiChartSpec } from './types';

export type MessageBlock =
  { type: 'text'; text: string } | { type: 'chart'; chart: AiChartSpec };

const CHART_BLOCK = /```(?:json\s+chart|chart)\s*\n([\s\S]*?)\n```/gi;
const CHART_TYPES = ['bar', 'line', 'donut'];

/** Splits a reply into Markdown and the ```chart blocks the model writes; a malformed block stays text. */
export function splitMessage(text: string): MessageBlock[] {
  const blocks: MessageBlock[] = [];
  let last = 0;
  for (const match of text.matchAll(CHART_BLOCK)) {
    pushText(blocks, text.slice(last, match.index));
    const chart = parseChart(match[1]);
    blocks.push(
      chart ? { type: 'chart', chart } : { type: 'text', text: match[0] }
    );
    last = (match.index ?? 0) + match[0].length;
  }

  pushText(blocks, text.slice(last));
  return blocks.length ? blocks : [{ type: 'text', text }];
}

export function getCharts(text: string): AiChartSpec[] {
  return splitMessage(text).flatMap((block) =>
    block.type === 'chart' ? [block.chart] : []
  );
}

function pushText(blocks: MessageBlock[], text: string) {
  if (text.trim()) {
    blocks.push({ type: 'text', text: text.trim() });
  }
}

function parseChart(json: string): AiChartSpec | null {
  try {
    const chart = JSON.parse(json.trim()) as AiChartSpec;
    return chart && CHART_TYPES.includes(chart.type) ? chart : null;
  } catch {
    return null;
  }
}

/** Rows for a frappe-ui axis chart: one per label, one key per dataset. */
export function getAxisRows(chart: AiChartSpec) {
  const datasets = chart.datasets ?? [];
  const rows = (chart.labels ?? []).map((label, index) => {
    const row: Record<string, string | number> = { label };
    datasets.forEach((dataset, series) => {
      row[`s${series}`] = Number(dataset.data[index]) || 0;
    });
    return row;
  });
  const seriesConfig = Object.fromEntries(
    datasets.map((dataset, series) => [
      `s${series}`,
      { label: dataset.label ?? chart.title ?? '' },
    ])
  );
  return { rows, y: Object.keys(seriesConfig), seriesConfig };
}

/** Rows for a donut: from its sectors, or from the first dataset by label. */
export function getDonutRows(chart: AiChartSpec) {
  if (chart.sectors?.length) {
    return chart.sectors.map(({ label, value }) => ({
      label,
      value: Number(value) || 0,
    }));
  }

  const data = chart.datasets?.[0]?.data ?? [];
  return (chart.labels ?? []).map((label, index) => ({
    label,
    value: Number(data[index]) || 0,
  }));
}
