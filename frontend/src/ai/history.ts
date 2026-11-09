import { getCharts } from './charts';
import type { AiChartSpec, ChatMessage, TranscriptEntry } from './types';

/** A saved conversation, kept in this browser for this user only. */
export interface AiSessionRecord {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  entries: TranscriptEntry[];
  messages: ChatMessage[];
  charts: AiChartSpec[];
}

/** One user's conversations stay apart from the next user's on a shared computer. */
function getStorageKey(): string {
  const user = window.frappe?.boot?.user?.name ?? 'Guest';
  return `books-ai-history:${user}`;
}

export function loadSavedSessions(): AiSessionRecord[] {
  try {
    const parsed: unknown = JSON.parse(
      localStorage.getItem(getStorageKey()) ?? '[]'
    );
    return Array.isArray(parsed) ? (parsed as AiSessionRecord[]) : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions: AiSessionRecord[]) {
  try {
    localStorage.setItem(getStorageKey(), JSON.stringify(sessions));
  } catch {
    // A full or blocked storage loses history, not the conversation on screen.
  }
}

export function saveSession(
  id: string,
  entries: TranscriptEntry[],
  messages: ChatMessage[]
): AiSessionRecord[] {
  const sessions = loadSavedSessions();
  const now = new Date().toISOString();
  const charts = entries.flatMap((entry) =>
    entry.kind === 'assistant' ? getCharts(entry.text) : []
  );
  const question = entries.find((entry) => entry.kind === 'user')?.text ?? '';
  const title = question.length > 60 ? `${question.slice(0, 60)}…` : question;
  const existing = sessions.find((session) => session.id === id);
  if (existing) {
    Object.assign(existing, { entries, messages, charts, updatedAt: now });
  } else {
    sessions.unshift({
      id,
      title,
      createdAt: now,
      updatedAt: now,
      entries,
      messages,
      charts,
    });
  }

  saveSessions(sessions);
  return sessions;
}

export function deleteSavedSession(id: string): AiSessionRecord[] {
  const sessions = loadSavedSessions().filter((session) => session.id !== id);
  saveSessions(sessions);
  return sessions;
}

export function clearSavedSessions() {
  try {
    localStorage.removeItem(getStorageKey());
  } catch {
    // Nothing to clear.
  }
}
