import { reactive, ref } from 'vue';
import {
  AiSessionRecord,
  deleteSavedSession,
  loadSavedSessions,
  saveSession,
} from './history';
import type { ChatMessage, TranscriptEntry } from './types';

/**
 * The conversation the slide-over panel and the /ai page share, so opening
 * the page mid-conversation continues it.
 */
export interface AiState {
  entries: TranscriptEntry[];
  messages: ChatMessage[];
  isBusy: boolean;
  /** Set while a proposed change waits on the user. */
  awaitingConfirmation: boolean;
  activeSessionId: string;
  savedSessions: AiSessionRecord[];
}

export const aiState = reactive<AiState>({
  entries: [],
  messages: [],
  isBusy: false,
  awaitingConfirmation: false,
  activeSessionId: newSessionId(),
  savedSessions: [],
});

/** Whether the slide-over panel shows. The /ai page ignores it. */
export const isAssistantOpen = ref(false);

type Decision = { approved: boolean; reason?: string };
const pendingConfirmations = new Map<string, (decision: Decision) => void>();
let nextId = 0;
// A question's loop checks this after each wait, so a cleared conversation's loop stops writing.
let epoch = 0;

function newSessionId(): string {
  return `ai-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export function getConversationEpoch(): number {
  return epoch;
}

export function newEntryId(): string {
  nextId += 1;
  return `e${nextId}-${Date.now()}`;
}

export function pushEntry<T extends TranscriptEntry>(entry: T): T {
  aiState.entries.push(entry);
  return aiState.entries[aiState.entries.length - 1] as T;
}

export function persistCurrentSession() {
  if (aiState.entries.length) {
    aiState.savedSessions = saveSession(
      aiState.activeSessionId,
      aiState.entries,
      aiState.messages
    );
  }
}

/** Loads this user's saved conversations; the app calls it once the user is known. */
export function loadHistory() {
  aiState.savedSessions = loadSavedSessions();
}

export function loadSession(id: string) {
  const session = aiState.savedSessions.find((saved) => saved.id === id);
  if (!session) {
    return;
  }

  resetConversation();
  aiState.activeSessionId = session.id;
  aiState.entries = [...session.entries];
  aiState.messages = [...session.messages];
}

export function deleteSession(id: string) {
  aiState.savedSessions = deleteSavedSession(id);
  if (aiState.activeSessionId === id) {
    clearConversation();
  }
}

export function clearConversation() {
  resetConversation();
  aiState.activeSessionId = newSessionId();
}

function resetConversation() {
  epoch += 1;
  for (const id of [...pendingConfirmations.keys()]) {
    resolveConfirmation(id, false, 'the conversation was cleared');
  }
  aiState.entries = [];
  aiState.messages = [];
  aiState.isBusy = false;
  aiState.awaitingConfirmation = false;
}

export function waitForConfirmation(entryId: string): Promise<Decision> {
  aiState.awaitingConfirmation = true;
  return new Promise((resolve) => {
    pendingConfirmations.set(entryId, (decision) => {
      pendingConfirmations.delete(entryId);
      aiState.awaitingConfirmation = pendingConfirmations.size > 0;
      resolve(decision);
    });
  });
}

export function resolveConfirmation(
  entryId: string,
  approved: boolean,
  reason?: string
) {
  pendingConfirmations.get(entryId)?.({ approved, reason });
}
