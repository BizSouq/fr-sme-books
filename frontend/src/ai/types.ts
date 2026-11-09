/** The assistant's shapes, as `frappe_books.ai` sends and takes them. */

export type AiProvider = 'anthropic' | 'openai' | 'gemini';

export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
}

export interface ToolResult {
  id: string;
  name: string;
  content: unknown;
  is_error?: boolean;
}

export interface RawAssistantContent {
  provider: AiProvider;
  content: unknown;
}

export interface AssistantMessage {
  role: 'assistant';
  text?: string;
  tool_calls?: ToolCall[];
  /** The provider's own turn, sent back untouched; Anthropic rejects a follow-up without its thinking blocks. */
  raw?: RawAssistantContent;
}

export type ChatMessage =
  | { role: 'user'; text: string }
  | AssistantMessage
  | { role: 'tool'; results: ToolResult[] };

/** `limit` and `rate_limit` are the AI Guard stopping the question. */
export type FinishReason =
  'end' | 'tool_calls' | 'length' | 'refusal' | 'limit' | 'rate_limit';

export interface AssistantTurn {
  text: string;
  tool_calls: ToolCall[];
  raw?: RawAssistantContent;
  finish_reason: FinishReason;
  error?: string;
}

export interface KeySummary {
  provider: AiProvider;
  model: string | null;
  /** The key's last four characters; the key itself never reaches the browser. */
  hint: string;
}

export interface ProviderInfo {
  name: AiProvider;
  label: string;
  default_model: string;
  models: string[];
}

export interface AiStatus {
  enabled: boolean;
  can_use: boolean;
  is_admin: boolean;
  allow_writes: boolean;
  allow_destructive: boolean;
  allow_personal_keys: boolean;
  providers: ProviderInfo[];
  company_key: KeySummary | null;
  user_key: KeySummary | null;
}

export interface WritePreviewRow {
  fieldname: string;
  label: string;
  /** Absent when the record does not exist yet. */
  before?: string;
  /** Absent for a delete, submit or cancel, which change no field. */
  after?: string;
  changed?: boolean;
  /** One line per child row, for a table. */
  rows?: string[];
}

export interface WritePreview {
  action: 'create' | 'update' | 'delete' | 'submit' | 'cancel';
  doctype: string;
  doctype_label: string;
  name: string | null;
  /** Deletes and cancellations reverse work; they get a louder card. */
  destructive: boolean;
  rows: WritePreviewRow[];
}

/** What the server answers for one tool call. */
export type ToolOutcome =
  | { status: 'done'; content: unknown }
  | { status: 'failed'; content: { error: string } }
  | { status: 'proposed'; token: string; preview: WritePreview }
  | { status: 'cancelled' };

export type ToolStatus =
  'running' | 'awaiting-confirmation' | 'done' | 'failed' | 'cancelled';

export interface ToolEntry {
  kind: 'tool';
  id: string;
  call: ToolCall;
  status: ToolStatus;
  /** What a proposed change would do, shown while the user decides. */
  preview?: WritePreview;
  summary?: string;
  result?: unknown;
}

/** One entry of the transcript the user sees. */
export type TranscriptEntry =
  | { kind: 'user'; id: string; text: string }
  | { kind: 'assistant'; id: string; text: string }
  | { kind: 'error'; id: string; text: string }
  | ToolEntry;

export interface AiChartSpec {
  type: 'bar' | 'donut' | 'line';
  title?: string;
  labels?: string[];
  datasets?: { label?: string; data: number[] }[];
  sectors?: { label: string; value: number }[];
}
