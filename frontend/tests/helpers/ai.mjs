import { after } from 'node:test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const directory = await mkdtemp(path.join(tmpdir(), 'books-ai-tests-'));
after(() => rm(directory, { recursive: true, force: true }));
const output = path.join(directory, 'ai.cjs');
const frontend = fileURLToPath(new URL('../..', import.meta.url));
await build({
  absWorkingDir: frontend,
  stdin: {
    contents: `
      export { ask, getLocalDate, trimForHistory } from './src/ai/agent';
      export { getAxisRows, getCharts, getDonutRows, splitMessage } from './src/ai/charts';
      export { loadSavedSessions } from './src/ai/history';
      export {
        aiState,
        clearConversation,
        loadHistory,
        persistCurrentSession,
        resolveConfirmation,
      } from './src/ai/store';
    `,
    resolveDir: frontend,
  },
  bundle: true,
  platform: 'node',
  format: 'cjs',
  outfile: output,
  loader: { '.css': 'empty' },
});

export const {
  aiState,
  ask,
  clearConversation,
  getAxisRows,
  getCharts,
  getDonutRows,
  getLocalDate,
  loadHistory,
  loadSavedSessions,
  persistCurrentSession,
  resolveConfirmation,
  splitMessage,
  trimForHistory,
} = createRequire(import.meta.url)(output);
