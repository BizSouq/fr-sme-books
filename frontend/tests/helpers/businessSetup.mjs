import { after } from 'node:test';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const directory = await mkdtemp(path.join(tmpdir(), 'books-setup-tests-'));
after(() => rm(directory, { recursive: true, force: true }));
const output = path.join(directory, 'businessSetup.cjs');
const frontend = fileURLToPath(new URL('../..', import.meta.url));
await build({
  absWorkingDir: frontend,
  entryPoints: ['./src/utils/businessSetup.ts'],
  bundle: true,
  platform: 'node',
  format: 'cjs',
  outfile: output,
  loader: { '.css': 'empty' },
});

export const {
  applySetup,
  buildApplyOptions,
  describeAnswers,
  getCatalogItems,
  groupRows,
  mergeItems,
  toggleAnswer,
} = createRequire(import.meta.url)(output);
