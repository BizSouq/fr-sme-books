import assert from 'node:assert/strict';
import { beforeEach, test } from 'node:test';
import {
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
} from './helpers/ai.mjs';
import { stubServer } from './helpers/server.mjs';

const API = 'frappe_books.ai.api';
const CREATE = {
  id: 'c1',
  name: 'create_record',
  args: { doctype: 'Books Customer', values: { customer_name: 'Acme' } },
};
const PREVIEW = {
  action: 'create',
  doctype: 'Books Customer',
  doctype_label: 'Customer',
  name: null,
  destructive: false,
  rows: [],
};

/** A model that answers with `turns`, one per chat request. */
function stubModel(turns, tools = () => ({ status: 'done', content: {} })) {
  const queue = [...turns];
  return stubServer((method, args) =>
    method === `${API}.chat`
      ? { tool_calls: [], finish_reason: 'end', ...queue.shift() }
      : tools(method, args)
  );
}

function makeDeps() {
  const opened = [];
  return {
    opened,
    deps: {
      openScreen: async (screen) => void opened.push(screen),
      confirmDestructive: async () => true,
    },
  };
}

function storage() {
  const items = new Map();
  return {
    getItem: (key) => items.get(key) ?? null,
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: (key) => items.delete(key),
  };
}

/** Resolves each confirmation card as it appears. */
function answerCards(approved) {
  const timer = setInterval(() => {
    for (const entry of aiState.entries) {
      if (entry.status === 'awaiting-confirmation') {
        resolveConfirmation(entry.id, approved, 'not today');
      }
    }
  }, 1);
  return () => clearInterval(timer);
}

beforeEach(() => {
  globalThis.localStorage = storage();
  clearConversation();
});

test('reads run on the server and their results go back to the model', async () => {
  const calls = stubModel([
    {
      tool_calls: [
        { id: 't1', name: 'count_records', args: { doctype: 'Books Customer' } },
      ],
      finish_reason: 'tool_calls',
    },
    { text: 'You have **3** customers.' },
  ]);

  await ask('How many customers?', makeDeps().deps);

  const methods = calls.map(({ method }) => method.replace(`${API}.`, ''));
  assert.deepEqual(methods, ['chat', 'run_tool', 'chat']);
  assert.deepEqual(calls[1].args, {
    name: 'count_records',
    args: { doctype: 'Books Customer' },
  });
  assert.equal(calls[0].args.context.today, getLocalDate());
  assert.deepEqual(aiState.messages.at(-2), {
    role: 'tool',
    results: [{ id: 't1', name: 'count_records', content: {} }],
  });
  assert.deepEqual(
    aiState.entries.map(({ kind }) => kind),
    ['user', 'tool', 'assistant']
  );
  assert.equal(aiState.isBusy, false);
});

test('an approved change runs the proposal the server holds, by its token', async () => {
  const calls = stubModel(
    [
      { tool_calls: [CREATE], finish_reason: 'tool_calls' },
      { text: 'Done.' },
    ],
    (method) =>
      method.endsWith('run_tool')
        ? { status: 'proposed', token: 'tok', preview: PREVIEW }
        : { status: 'done', content: { name: 'Acme' } }
  );

  const stop = answerCards(true);
  await ask('Add Acme', makeDeps().deps);
  stop();

  const confirm = calls.find(({ method }) => method.endsWith('confirm_action'));
  assert.deepEqual(confirm.args, { token: 'tok' });
  assert.equal(aiState.entries[1].status, 'done');
  assert.deepEqual(aiState.messages.at(-2).results[0].content, {
    name: 'Acme',
  });
});

test('a declined change is declined on the server and told to the model', async () => {
  const calls = stubModel(
    [
      { tool_calls: [CREATE], finish_reason: 'tool_calls' },
      { text: 'What would you rather do?' },
    ],
    (method) =>
      method.endsWith('run_tool')
        ? { status: 'proposed', token: 'tok', preview: PREVIEW }
        : { status: 'cancelled' }
  );

  const stop = answerCards(false);
  await ask('Add Acme', makeDeps().deps);
  stop();

  const methods = calls.map(({ method }) => method.replace(`${API}.`, ''));
  assert.ok(!methods.includes('confirm_action'));
  assert.deepEqual(calls[2].args, { token: 'tok', reason: 'not today' });
  assert.equal(aiState.entries[1].status, 'cancelled');
  assert.deepEqual(aiState.messages.at(-2).results[0].content, {
    cancelled: true,
    reason: 'not today',
  });
});

test('a refused tool is an error result the model can read', async () => {
  stubModel(
    [
      {
        tool_calls: [{ id: 't1', name: 'list_records', args: {} }],
        finish_reason: 'tool_calls',
      },
      { text: 'That is hidden from me.' },
    ],
    () => ({ status: 'failed', content: { error: 'hidden' } })
  );

  await ask('List users', makeDeps().deps);

  assert.equal(aiState.entries[1].status, 'failed');
  assert.equal(aiState.entries[1].summary, 'hidden');
  assert.equal(aiState.messages.at(-2).results[0].is_error, true);
});

test('the guard stopping a question shows why', async () => {
  stubModel([{ finish_reason: 'rate_limit', error: 'Slow down.' }]);
  await ask('Hi', makeDeps().deps);
  assert.deepEqual(aiState.entries.at(-1), {
    kind: 'error',
    id: aiState.entries.at(-1).id,
    text: 'Slow down.',
  });
});

test('screens the server allowed are opened by the app', async () => {
  const { deps, opened } = makeDeps();
  stubModel(
    [
      {
        tool_calls: [{ id: 't1', name: 'open_screen', args: {} }],
        finish_reason: 'tool_calls',
      },
      { text: 'Opened.' },
    ],
    () => ({ status: 'done', content: { open: 'dashboard' } })
  );

  await ask('Show the dashboard', deps);
  assert.deepEqual(opened, [{ open: 'dashboard' }]);
});

test('large results are shortened for the model only', () => {
  const rows = Array.from({ length: 2000 }, (_, index) => ({ index }));
  const trimmed = trimForHistory({ rows });
  assert.equal(trimmed.truncated, true);
  assert.equal(trimmed.preview.length, 8000);
  assert.deepEqual(trimForHistory({ count: 3 }), { count: 3 });
});

test('chart blocks become charts and malformed ones stay text', () => {
  const chart =
    '{"type": "bar", "labels": ["Jan", "Feb"], "datasets": [{"label": "Sales", "data": [10, 20]}]}';
  const blocks = splitMessage(
    `Sales rose.\n\`\`\`chart\n${chart}\n\`\`\`\nThen\n\`\`\`chart\n{oops}\n\`\`\``
  );
  assert.deepEqual(
    blocks.map(({ type }) => type),
    ['text', 'chart', 'text', 'text']
  );
  assert.deepEqual(getAxisRows(blocks[1].chart), {
    rows: [
      { label: 'Jan', s0: 10 },
      { label: 'Feb', s0: 20 },
    ],
    y: ['s0'],
    seriesConfig: { s0: { label: 'Sales' } },
  });
  assert.deepEqual(getDonutRows(blocks[1].chart), [
    { label: 'Jan', value: 10 },
    { label: 'Feb', value: 20 },
  ]);
  assert.equal(getCharts('no charts').length, 0);
});

test('saved chats are kept per user', () => {
  globalThis.window = { frappe: { boot: { user: { name: 'a@example.com' } } } };
  aiState.entries.push({ kind: 'user', id: 'u1', text: 'Cash this month?' });
  persistCurrentSession();
  assert.equal(loadSavedSessions()[0].title, 'Cash this month?');

  window.frappe.boot.user.name = 'b@example.com';
  loadHistory();
  assert.deepEqual(aiState.savedSessions, []);
});
