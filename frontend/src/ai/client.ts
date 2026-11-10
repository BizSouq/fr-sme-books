import { call } from 'src/web/api';
import type {
  AiProvider,
  AiStatus,
  AssistantTurn,
  ChatMessage,
  ToolOutcome,
} from './types';

/** The `frappe_books.ai.api` endpoints. None of them ever answers with an API key. */
const API = 'frappe_books.ai.api';

export function getAiStatus(): Promise<AiStatus> {
  return call<AiStatus>(`${API}.get_status`);
}

export function saveAiKey(body: {
  scope: 'company' | 'user';
  provider: AiProvider;
  model: string;
  api_key: string;
}): Promise<AiStatus> {
  return call<AiStatus>(`${API}.save_key`, body);
}

export function removeAiKey(scope: 'company' | 'user'): Promise<AiStatus> {
  return call<AiStatus>(`${API}.remove_key`, { scope });
}

export function saveAiSettings(
  values: Partial<
    Pick<
      AiStatus,
      'enabled' | 'allow_writes' | 'allow_destructive' | 'allow_personal_keys'
    >
  >
): Promise<AiStatus> {
  return call<AiStatus>(`${API}.save_settings`, { values });
}

export interface ConnectionTest {
  ok: boolean;
  provider: AiProvider;
  model: string;
  message?: string;
}

export function testAiConnection(): Promise<ConnectionTest> {
  return call<ConnectionTest>(`${API}.test_connection`);
}

export function sendChat(
  messages: ChatMessage[],
  today: string
): Promise<AssistantTurn> {
  return call<AssistantTurn>(`${API}.chat`, { messages, context: { today } });
}

export function runTool(
  name: string,
  args: Record<string, unknown>
): Promise<ToolOutcome> {
  return call<ToolOutcome>(`${API}.run_tool`, { name, args });
}

export function confirmAction(token: string): Promise<ToolOutcome> {
  return call<ToolOutcome>(`${API}.confirm_action`, { token });
}

export function declineAction(
  token: string,
  reason?: string
): Promise<ToolOutcome> {
  return call<ToolOutcome>(`${API}.decline_action`, { token, reason });
}
