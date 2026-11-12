import { call } from 'src/web/api';

/** The `frappe_books.onboarding.api` endpoints of the business setup page. */
const API = 'frappe_books.onboarding.api';

export type SetupOption = { id: string; label: string };
export type SetupQuestion = {
  id: string;
  label: string;
  multiple: boolean;
  options: SetupOption[];
};
export type BusinessType = {
  id: string;
  label: string;
  description: string;
  icon: string;
  questions: SetupQuestion[];
  item_count: number;
};
export type SetupUom = { name: string; whole: number };
export type SetupGroup = { name: string; image?: string; image_query?: string };
export type SetupItem = {
  name: string;
  group: string;
  description: string;
  type: 'Product' | 'Service';
  uom: string;
  rate: number;
  tags: string[];
  image: string;
  image_query: string;
};
/** An item on the page: what the catalog or the AI offered, and whether the user wants it. */
export type SetupItemRow = SetupItem & {
  selected: boolean;
  /** An item of this name is in the books already, so it cannot be added again. */
  exists: boolean;
  source: 'catalog' | 'ai';
};
export type LocalDefault = 'vat' | 'mobile_wallets' | 'cash_denominations';
export type SetupOptions = {
  country: string | null;
  currency: string | null;
  business_types: BusinessType[];
  local_defaults: LocalDefault[];
  vat_rates: number[];
  ai: { available: boolean };
};
export type CatalogItems = {
  groups: SetupGroup[];
  uoms: SetupUom[];
  items: SetupItem[];
  existing: string[];
};
/** Picked option ids by question id. */
export type Answers = Record<string, string[]>;
export type AnswerText = { question: string; answers: string[] };
export type SetupChoices = {
  guest_parties: boolean;
  vat: boolean;
  /** The VAT rate new items are taxed at, or null to leave them untaxed. */
  vat_rate: number | null;
  mobile_wallets: boolean;
  cash_denominations: boolean;
  fetch_images: boolean;
};
export type ApplyResult = {
  items: number;
  item_groups: number;
  skipped_items: number;
  images_queued: number;
};

/** The business type for a line of work the catalog does not list; the AI suggests its items. */
export const OTHER_BUSINESS = 'other';

export function getSetupOptions(): Promise<SetupOptions> {
  return call<SetupOptions>(`${API}.get_options`);
}

export function getCatalogItems(
  businessType: string,
  answers: Answers
): Promise<CatalogItems> {
  return call<CatalogItems>(`${API}.get_items`, {
    business_type: businessType,
    answers,
  });
}

export function findImages(queries: string[]): Promise<Record<string, string>> {
  return call<Record<string, string>>(`${API}.find_images`, { queries });
}

/** Picture phrases per lookup; the server looks up at most 120 at once. */
export const IMAGE_BATCH = 100;

/**
 * Look up pictures for any number of phrases, in batches the server takes, handing each batch's
 * finds to `onFound` as it comes. A failed batch ends the lookup: pictures are a nicety.
 */
export async function findImagesInBatches(
  queries: string[],
  onFound: (found: Record<string, string>) => void
): Promise<void> {
  for (let start = 0; start < queries.length; start += IMAGE_BATCH) {
    try {
      onFound(await findImages(queries.slice(start, start + IMAGE_BATCH)));
    } catch {
      return;
    }
  }
}

export async function suggestQuestions(
  businessLabel: string,
  answers: AnswerText[],
  note: string
): Promise<SetupQuestion[]> {
  const { questions } = await call<{ questions: SetupQuestion[] }>(
    `${API}.suggest_questions`,
    { business_label: businessLabel, answers, note }
  );
  return questions;
}

export function suggestItems(
  businessLabel: string,
  answers: AnswerText[],
  note: string,
  existing: string[]
): Promise<{ groups: string[]; items: SetupItem[] }> {
  return call(`${API}.suggest_items`, {
    business_label: businessLabel,
    answers,
    note,
    existing,
  });
}

export function applySetup(
  options: Record<string, unknown>
): Promise<ApplyResult> {
  return call<ApplyResult>(`${API}.apply`, { options });
}

/** Pick or unpick an option: a single-choice question keeps one, picked again it is cleared. */
export function toggleAnswer(
  answers: Answers,
  question: SetupQuestion,
  optionId: string
): Answers {
  const picked = answers[question.id] ?? [];
  const isPicked = picked.includes(optionId);
  let next: string[];
  if (isPicked) {
    next = picked.filter((id) => id !== optionId);
  } else {
    next = question.multiple ? [...picked, optionId] : [optionId];
  }

  return { ...answers, [question.id]: next };
}

/** The answers in words, as the AI is told them. */
export function describeAnswers(
  questions: SetupQuestion[],
  answers: Answers
): AnswerText[] {
  return questions
    .map((question) => ({
      question: question.label,
      answers: question.options
        .filter((option) => answers[question.id]?.includes(option.id))
        .map((option) => option.label),
    }))
    .filter((answer) => answer.answers.length > 0);
}

/**
 * The page's rows after the catalog or the AI offered `incoming`.
 *
 * A row the user already has keeps its place, its tick and the price they typed. Catalog rows the new
 * answers no longer match are dropped; the AI's rows stay until the business type changes.
 */
export function mergeItems(
  rows: SetupItemRow[],
  incoming: SetupItem[],
  source: SetupItemRow['source'],
  existing: string[] = []
): SetupItemRow[] {
  const taken = new Set(existing.map((name) => name.toLowerCase()));
  const incomingNames = new Set(
    incoming.map((item) => item.name.toLowerCase())
  );
  const kept = rows.filter(
    (row) =>
      row.source !== source ||
      source === 'ai' ||
      incomingNames.has(row.name.toLowerCase())
  );
  const known = new Set(kept.map((row) => row.name.toLowerCase()));
  const added = incoming
    .filter((item) => !known.has(item.name.toLowerCase()))
    .map((item) => {
      const exists = taken.has(item.name.toLowerCase());
      return { ...item, source, exists, selected: !exists };
    });
  return [...kept, ...added];
}

/** Rows by item group, in the order the groups first appear; ungrouped rows come last. */
export function groupRows(rows: SetupItemRow[]): [string, SetupItemRow[]][] {
  const groups = new Map<string, SetupItemRow[]>();
  for (const row of rows) {
    const list = groups.get(row.group) ?? [];
    list.push(row);
    groups.set(row.group, list);
  }

  const ungrouped = groups.get('');
  groups.delete('');
  return ungrouped ? [...groups, ['', ungrouped]] : [...groups];
}

/** What the server is asked to make: the ticked items, their groups and units, and the chosen defaults. */
export function buildApplyOptions(
  rows: SetupItemRow[],
  catalog: Pick<CatalogItems, 'groups' | 'uoms'>,
  choices: SetupChoices,
  localDefaults: LocalDefault[]
): Record<string, unknown> {
  const items = rows.filter((row) => row.selected && !row.exists);
  const usedGroups = new Set(items.map((item) => item.group).filter(Boolean));
  const usedUoms = new Set(items.map((item) => item.uom));
  const catalogGroups = catalog.groups.filter((group) =>
    usedGroups.has(group.name)
  );
  const listed = new Set(catalogGroups.map((group) => group.name));
  const has = (key: LocalDefault) =>
    localDefaults.includes(key) && choices[key];
  return {
    guest_parties: choices.guest_parties,
    vat: has('vat'),
    vat_rate: has('vat') ? choices.vat_rate : null,
    mobile_wallets: has('mobile_wallets'),
    cash_denominations: has('cash_denominations'),
    fetch_images: choices.fetch_images,
    uoms: catalog.uoms.filter((uom) => usedUoms.has(uom.name)),
    groups: [
      ...catalogGroups.map(({ name, image }) => ({ name, image: image ?? '' })),
      ...[...usedGroups]
        .filter((name) => !listed.has(name))
        .map((name) => ({ name, image: '' })),
    ],
    items: items.map(
      ({ name, group, description, type, uom, rate, image }) => ({
        name,
        group,
        description,
        type,
        uom,
        rate: Number(rate) || 0,
        image: choices.fetch_images ? image : '',
      })
    ),
  };
}
