<template>
  <div class="flex min-w-0 flex-col gap-2">
    <template v-for="(block, index) in blocks" :key="index">
      <AiChartCard v-if="block.type === 'chart'" :chart="block.chart" />
      <!-- Sanitized below: only formatting tags and safe links survive. -->
      <!-- eslint-disable-next-line vue/no-v-html -->
      <div v-else class="ai-markdown text-p-base" v-html="render(block.text)" />
    </template>
  </div>
</template>

<script setup lang="ts">
import DOMPurify from 'dompurify';
import { marked } from 'marked';
import { splitMessage } from 'src/ai/charts';
import { computed } from 'vue';
import AiChartCard from './AiChartCard.vue';

const props = defineProps<{ text: string }>();
const blocks = computed(() => splitMessage(props.text));

const ALLOWED_TAGS = [
  'p',
  'br',
  'strong',
  'em',
  'del',
  'code',
  'pre',
  'blockquote',
  'ul',
  'ol',
  'li',
  'h1',
  'h2',
  'h3',
  'h4',
  'hr',
  'a',
  'table',
  'thead',
  'tbody',
  'tr',
  'th',
  'td',
];

/** The model's Markdown, with anything that could run or load content stripped. */
function render(text: string): string {
  const html = marked.parse(text, { async: false, breaks: true, gfm: true });
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS,
    ALLOWED_ATTR: ['href', 'title'],
    ALLOWED_URI_REGEXP: /^(?:https?:|mailto:|#|\/)/i,
  });
}
</script>

<style scoped>
.ai-markdown :deep(p),
.ai-markdown :deep(ul),
.ai-markdown :deep(ol),
.ai-markdown :deep(pre),
.ai-markdown :deep(blockquote),
.ai-markdown :deep(table) {
  margin-bottom: 0.625rem;
}
.ai-markdown :deep(> *:last-child) {
  margin-bottom: 0;
}
.ai-markdown :deep(h1),
.ai-markdown :deep(h2),
.ai-markdown :deep(h3),
.ai-markdown :deep(h4) {
  font-weight: 600;
  margin: 0.75rem 0 0.5rem;
}
.ai-markdown :deep(ul) {
  list-style: disc;
  padding-inline-start: 1.25rem;
}
.ai-markdown :deep(ol) {
  list-style: decimal;
  padding-inline-start: 1.25rem;
}
.ai-markdown :deep(strong) {
  font-weight: 600;
}
.ai-markdown :deep(a) {
  text-decoration: underline;
}
.ai-markdown :deep(code) {
  font-size: 0.875em;
  padding: 0.1em 0.3em;
  border-radius: 0.25rem;
  background-color: var(--surface-gray-2);
}
.ai-markdown :deep(pre) {
  padding: 0.625rem 0.75rem;
  border-radius: 0.375rem;
  background-color: var(--surface-gray-2);
  overflow-x: auto;
}
.ai-markdown :deep(pre code) {
  padding: 0;
}
.ai-markdown :deep(blockquote) {
  border-inline-start: 2px solid var(--outline-gray-2);
  padding-inline-start: 0.75rem;
}
.ai-markdown :deep(table) {
  display: block;
  overflow-x: auto;
  border-collapse: collapse;
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
}
.ai-markdown :deep(th),
.ai-markdown :deep(td) {
  border: 1px solid var(--outline-gray-2);
  padding: 0.3rem 0.5rem;
  text-align: start;
  white-space: nowrap;
}
.ai-markdown :deep(th) {
  font-weight: 600;
  background-color: var(--surface-gray-2);
}
</style>
