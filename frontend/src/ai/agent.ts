import { t } from 'fyo';
import { confirmAction, declineAction, runTool, sendChat } from './client';
import {
  aiState,
  getConversationEpoch,
  newEntryId,
  persistCurrentSession,
  pushEntry,
  waitForConfirmation,
} from './store';
import type {
  AssistantTurn,
  ToolCall,
  ToolEntry,
  ToolOutcome,
  ToolResult,
  WritePreview,
} from './types';

/**
 * The conversation loop: ask, run the tools the model asked for on the
 * server, send the results back, until the model answers in words. The
 * server's AI Guard checks every step; this loop only drives it.
 */

/** What the loop needs from the app: opening screens and the last check before a delete or cancel. */
export interface AgentDeps {
  openScreen: (screen: Record<string, unknown>) => Promise<void>;
  confirmDestructive: (preview: WritePreview) => Promise<boolean>;
}

/**
 * How much of one result goes back to the model. The whole transcript is sent
 * again with each request, so a large result costs on every later one; the
 * tool card keeps the full result.
 */
const MAX_RESULT_CHARS = 8_000;
/** A safety net only; the server's lookup limit stops a question first. */
const MAX_ROUNDS = 20;

export function trimForHistory(content: unknown): unknown {
  const json = JSON.stringify(content) ?? '';
  if (json.length <= MAX_RESULT_CHARS) {
    return content;
  }

  return {
    truncated: true,
    note:
      `this result was ${json.length} characters and has been shortened. ` +
      'Ask for a narrower slice (fewer fields, a tighter filter or a smaller limit) if you need the rest.',
    preview: json.slice(0, MAX_RESULT_CHARS),
  };
}

/** Today where the user sits, not in UTC, so "this month" means their month. */
export function getLocalDate(date: Date = new Date()): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

export function getStopMessage(turn: AssistantTurn): string {
  switch (turn.finish_reason) {
    case 'rate_limit':
      return (
        turn.error ||
        t`You have reached the assistant's request limit. Try again later.`
      );
    case 'limit':
      return t`The assistant kept looking things up without reaching an answer, so the AI Guard stopped it. Try asking something more specific.`;
    case 'length':
      return t`The reply was cut short before it said anything. Try asking for a narrower slice of the data.`;
    case 'refusal':
      return t`The assistant declined to answer that. Rephrasing the question may help.`;
    default:
      return t`The assistant finished without saying anything. Try asking again.`;
  }
}

const TOOL_SUMMARIES: Record<string, () => string> = {
  list_record_types: () => t`Looked up record types`,
  describe_record_type: () => t`Looked up fields`,
  list_records: () => t`Read records`,
  get_record: () => t`Read a record`,
  count_records: () => t`Counted records`,
  list_reports: () => t`Looked up reports`,
  run_report: () => t`Ran a report`,
  get_dashboard_summary: () => t`Read summary figures`,
  open_screen: () => t`Opened a screen`,
  create_record: () => t`Created a record`,
  update_record: () => t`Changed a record`,
  delete_record: () => t`Deleted a record`,
  submit_document: () => t`Submitted a document`,
  cancel_document: () => t`Cancelled a document`,
};

function settle(
  entry: ToolEntry,
  call: ToolCall,
  outcome: ToolOutcome
): ToolResult {
  if (outcome.status === 'failed') {
    entry.status = 'failed';
    entry.summary = outcome.content.error;
    entry.result = outcome.content;
    return {
      id: call.id,
      name: call.name,
      content: outcome.content,
      is_error: true,
    };
  }

  const content = outcome.status === 'done' ? outcome.content : null;
  entry.status = 'done';
  entry.summary = TOOL_SUMMARIES[call.name]?.() ?? call.name;
  entry.result = content;
  return { id: call.id, name: call.name, content: trimForHistory(content) };
}

async function runCall(
  call: ToolCall,
  deps: AgentDeps,
  isCurrent: () => boolean
): Promise<ToolResult> {
  const entry = pushEntry<ToolEntry>({
    kind: 'tool',
    id: newEntryId(),
    call,
    status: 'running',
  });

  const outcome = await runTool(call.name, call.args ?? {});
  if (outcome.status === 'done' && call.name === 'open_screen') {
    await deps.openScreen(outcome.content as Record<string, unknown>);
  }

  if (outcome.status !== 'proposed') {
    return settle(entry, call, outcome);
  }

  // The server holds the change; only this exact proposal can run, and only on a click.
  entry.preview = outcome.preview;
  entry.status = 'awaiting-confirmation';
  if (!isCurrent()) {
    await declineAction(outcome.token, 'the conversation was cleared');
    return cancelled(call, 'the conversation was cleared');
  }

  const decision = await waitForConfirmation(entry.id);
  const approved =
    decision.approved &&
    (!outcome.preview.destructive ||
      (await deps.confirmDestructive(outcome.preview)));

  if (!approved) {
    const reason = decision.reason || 'the user declined this change';
    await declineAction(outcome.token, reason);
    entry.status = 'cancelled';
    entry.summary = t`Cancelled`;
    // The model is told, so it offers something else instead of proposing the same change again.
    return cancelled(call, reason);
  }

  entry.status = 'running';
  return settle(entry, call, await confirmAction(outcome.token));
}

function cancelled(call: ToolCall, reason: string): ToolResult {
  return { id: call.id, name: call.name, content: { cancelled: true, reason } };
}

/**
 * Puts one question to the assistant and drives it to an answer. Never
 * rejects: whatever goes wrong is written into the transcript.
 */
export async function ask(question: string, deps: AgentDeps): Promise<void> {
  const text = question.trim();
  if (!text || aiState.isBusy) {
    return;
  }

  const epoch = getConversationEpoch();
  const isCurrent = () => getConversationEpoch() === epoch;

  pushEntry({ kind: 'user', id: newEntryId(), text });
  aiState.messages.push({ role: 'user', text });
  aiState.isBusy = true;

  try {
    for (let round = 0; round < MAX_ROUNDS; round++) {
      const turn = await sendChat(aiState.messages, getLocalDate());
      if (!isCurrent()) {
        return;
      }

      if (
        turn.finish_reason === 'limit' ||
        turn.finish_reason === 'rate_limit'
      ) {
        pushEntry({
          kind: 'error',
          id: newEntryId(),
          text: getStopMessage(turn),
        });
        return;
      }

      const reply = (turn.text ?? '').trim();
      const calls = turn.tool_calls ?? [];
      aiState.messages.push({
        role: 'assistant',
        text: turn.text ?? '',
        tool_calls: calls,
        raw: turn.raw,
      });

      if (reply) {
        pushEntry({ kind: 'assistant', id: newEntryId(), text: reply });
      }

      // A turn with neither words nor calls says why, rather than leaving the user at their question.
      if (!calls.length) {
        if (!reply) {
          pushEntry({
            kind: 'error',
            id: newEntryId(),
            text: getStopMessage(turn),
          });
        }
        return;
      }

      // One at a time: a later call often depends on an earlier one, and cards should not pile up.
      const results: ToolResult[] = [];
      for (const call of calls) {
        results.push(await runCall(call, deps, isCurrent));
        if (!isCurrent()) {
          return;
        }
      }

      aiState.messages.push({ role: 'tool', results });
    }
  } catch (error) {
    if (isCurrent()) {
      pushEntry({
        kind: 'error',
        id: newEntryId(),
        text: (error as Error).message || t`Something went wrong.`,
      });
    }
  } finally {
    // A superseded loop leaves `isBusy` to the question asked after the clear.
    if (isCurrent()) {
      aiState.isBusy = false;
      persistCurrentSession();
    }
  }
}
