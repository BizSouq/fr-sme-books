<template>
  <div class="flex h-full min-h-0 flex-col bg-surface-base">
    <PageHeader v-if="!embedded" :title="t`Set up your business`" />
    <div class="min-h-0 flex-1 overflow-y-auto" data-testid="business-setup">
      <div class="mx-auto max-w-4xl space-y-8 px-4 pb-10 pt-6 sm:px-5">
        <header v-if="embedded">
          <h1 class="text-2xl-semibold text-ink-gray-9">
            {{ t`Set up your business` }}
          </h1>
          <p class="mt-1.5 text-p-base text-ink-gray-6">
            {{
              t`Your company is ready. Pick your line of business to start with its items, or skip this and add them later.`
            }}
          </p>
        </header>

        <div v-if="!options" class="flex justify-center py-16">
          <FrappeErrorMessage v-if="loadError" :message="loadError" />
          <FrappeSpinner v-else class="size-6" />
        </div>

        <template v-else>
          <!-- 1. The line of business -->
          <section>
            <h2 class="text-lg-semibold text-ink-gray-8">
              {{ t`What kind of business do you run?` }}
            </h2>
            <div class="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <button
                v-for="business in businessCards"
                :key="business.id"
                type="button"
                class="flex flex-col items-start rounded-6 border p-3.5 text-start transition-colors"
                :class="
                  business.id === businessId
                    ? 'border-outline-gray-5 bg-surface-gray-2'
                    : 'border-outline-gray-1 hover:bg-surface-gray-1'
                "
                :aria-pressed="business.id === businessId"
                :data-testid="`business-${business.id}`"
                @click="selectBusiness(business.id)"
              >
                <span
                  class="size-5 text-ink-gray-7"
                  :class="business.iconClass"
                  aria-hidden="true"
                />
                <span class="mt-3 text-base-medium text-ink-gray-9">{{
                  business.label
                }}</span>
                <span class="mt-1 text-p-sm text-ink-gray-6">{{
                  business.description
                }}</span>
              </button>
            </div>
          </section>

          <!-- 2. Questions about the business -->
          <section v-if="businessId" class="space-y-5">
            <div v-for="question in questions" :key="question.id">
              <h3 class="text-base-medium text-ink-gray-8">
                {{ question.label }}
              </h3>
              <div class="mt-2 flex flex-wrap gap-2">
                <button
                  v-for="option in question.options"
                  :key="option.id"
                  type="button"
                  class="rounded-full border px-3 py-1.5 text-sm transition-colors"
                  :class="
                    answers[question.id]?.includes(option.id)
                      ? 'border-outline-gray-5 bg-surface-gray-7 text-ink-white'
                      : 'border-outline-gray-2 text-ink-gray-8 hover:bg-surface-gray-2'
                  "
                  :aria-pressed="answers[question.id]?.includes(option.id)"
                  @click="pick(question, option.id)"
                >
                  {{ option.label }}
                </button>
              </div>
            </div>

            <div
              class="rounded-6 border border-outline-gray-1 bg-surface-gray-1 p-4"
            >
              <div
                class="flex items-center gap-2 text-base-medium text-ink-gray-8"
              >
                <span class="lucide-sparkles size-4" aria-hidden="true" />
                {{ t`Get ideas from the AI assistant` }}
              </div>
              <template v-if="options.ai.available">
                <FrappeTextarea
                  v-model="note"
                  class="mt-3"
                  :rows="2"
                  :placeholder="
                    t`Describe your business in a line or two, for example: a small kacchi house in Old Dhaka with takeaway`
                  "
                  :disabled="aiBusy !== ''"
                />
                <div class="mt-3 flex flex-wrap items-center gap-2">
                  <FrappeButton
                    variant="solid"
                    icon-left="lucide-sparkles"
                    :label="t`Suggest items`"
                    :loading="aiBusy === 'items'"
                    :disabled="aiBusy !== '' || !canAskAi"
                    data-testid="ai-suggest-items"
                    @click="askForItems"
                  />
                  <FrappeButton
                    :label="t`Ask me more questions`"
                    :loading="aiBusy === 'questions'"
                    :disabled="aiBusy !== '' || !canAskAi"
                    @click="askForQuestions"
                  />
                </div>
              </template>
              <div v-else class="mt-2 flex flex-wrap items-center gap-3">
                <p class="text-p-sm text-ink-gray-6">
                  {{
                    t`The assistant can ask about your business and suggest items that fit. It needs an AI key first.`
                  }}
                </p>
                <FrappeButton
                  v-if="isAiAdmin"
                  :label="t`Set up the assistant`"
                  @click="showAiSettings = true"
                />
              </div>
              <FrappeErrorMessage
                v-if="aiError"
                class="mt-2"
                :message="aiError"
              />
            </div>
          </section>

          <!-- 3. The items -->
          <section v-if="businessId">
            <div class="flex flex-wrap items-center justify-between gap-2">
              <h2 class="text-lg-semibold text-ink-gray-8">
                {{ t`Items to start with` }}
              </h2>
              <span v-if="rows.length" class="text-sm text-ink-gray-6">
                {{ t`${selectedCount} of ${selectableCount} selected` }}
              </span>
            </div>
            <div v-if="itemsLoading" class="flex justify-center py-8">
              <FrappeSpinner class="size-5" />
            </div>
            <p
              v-else-if="!rows.length"
              class="mt-3 rounded-6 border border-dashed border-outline-gray-2 p-6 text-center text-p-sm text-ink-gray-6"
            >
              {{
                options.ai.available
                  ? t`No items yet. Describe your business above and ask the assistant to suggest some.`
                  : t`No items for this business yet. You can add your own after setup.`
              }}
            </p>
            <template v-else>
              <p class="mt-1 text-p-sm text-ink-gray-6">
                {{
                  t`Untick what you do not sell. Prices are typical ones to start from: change them here or later.`
                }}
              </p>
              <div
                v-for="[group, groupItems] in groupedRows"
                :key="group"
                class="mt-4 overflow-hidden rounded-6 border border-outline-gray-1"
              >
                <label
                  class="flex cursor-pointer items-center gap-3 bg-surface-gray-1 px-3 py-2"
                >
                  <input
                    type="checkbox"
                    class="size-4 rounded border-outline-gray-3"
                    :checked="isGroupSelected(groupItems)"
                    :indeterminate.prop="isGroupPartial(groupItems)"
                    @change="toggleGroup(groupItems, $event)"
                  />
                  <span class="text-base-medium text-ink-gray-8">{{
                    group || t`Other items`
                  }}</span>
                  <span class="text-sm text-ink-gray-5">{{
                    groupItems.length
                  }}</span>
                </label>
                <ul class="divide-y divide-outline-gray-1">
                  <li
                    v-for="row in groupItems"
                    :key="row.name"
                    class="flex items-center gap-3 px-3 py-2"
                    :class="row.exists ? 'opacity-60' : ''"
                    data-testid="setup-item"
                  >
                    <input
                      v-model="row.selected"
                      type="checkbox"
                      class="size-4 shrink-0 rounded border-outline-gray-3"
                      :disabled="row.exists"
                      :aria-label="row.name"
                    />
                    <div
                      class="flex size-10 shrink-0 items-center justify-center overflow-hidden rounded bg-surface-gray-2"
                    >
                      <img
                        v-if="choices.fetch_images && row.image"
                        :src="row.image"
                        alt=""
                        loading="lazy"
                        referrerpolicy="no-referrer"
                        class="size-full object-cover"
                      />
                      <span
                        v-else
                        class="lucide-package size-4 text-ink-gray-4"
                        aria-hidden="true"
                      />
                    </div>
                    <div class="min-w-0 flex-1">
                      <div class="flex items-center gap-2">
                        <span class="truncate text-base text-ink-gray-9">{{
                          row.name
                        }}</span>
                        <span
                          v-if="row.exists"
                          class="shrink-0 rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6"
                          >{{ t`Already added` }}</span
                        >
                        <span
                          v-else-if="row.source === 'ai'"
                          class="shrink-0 rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6"
                          >{{ t`AI` }}</span
                        >
                      </div>
                      <p class="truncate text-p-sm text-ink-gray-6">
                        {{ row.description }}
                      </p>
                    </div>
                    <div class="flex shrink-0 items-center gap-1.5">
                      <input
                        v-model.number="row.rate"
                        type="number"
                        min="0"
                        step="any"
                        inputmode="decimal"
                        class="h-7 w-20 rounded border border-outline-gray-2 bg-surface-base px-2 text-end text-sm text-ink-gray-9"
                        :disabled="row.exists"
                        :aria-label="t`Price of ${row.name}`"
                      />
                      <span
                        class="hidden w-14 truncate text-xs text-ink-gray-5 sm:block"
                      >
                        / {{ row.uom || t`Unit` }}
                      </span>
                    </div>
                  </li>
                </ul>
              </div>
            </template>
          </section>

          <!-- 4. Guest parties and local defaults -->
          <section>
            <h2 class="text-lg-semibold text-ink-gray-8">
              {{ t`Also set up` }}
            </h2>
            <div class="mt-3 space-y-4">
              <FrappeSwitch
                v-model="choices.fetch_images"
                :label="t`Add pictures from the internet`"
                :description="
                  t`Looks up a picture for each item on Wikipedia and saves it with the item.`
                "
              />
              <FrappeSwitch
                v-model="choices.guest_parties"
                :label="t`Guest customer and guest supplier`"
                :description="
                  t`For quick sales and purchases without a named party. POS sales use the guest customer.`
                "
              />
              <template v-if="hasLocal('vat')">
                <FrappeSwitch
                  v-model="choices.vat"
                  :label="t`Bangladesh VAT`"
                  :description="
                    t`Adds a VAT account and tax templates for 15%, 10%, 7.5%, 5% and 0%.`
                  "
                />
                <div v-if="choices.vat && selectedCount" class="max-w-xs ps-11">
                  <FrappeSelect
                    v-model="vatRateValue"
                    :label="t`VAT on the new items`"
                    :options="vatOptions"
                  />
                </div>
              </template>
              <FrappeSwitch
                v-if="hasLocal('mobile_wallets')"
                v-model="choices.mobile_wallets"
                :label="t`bKash, Nagad and Rocket payments`"
                :description="
                  t`Adds each as a payment method with its own account.`
                "
              />
              <FrappeSwitch
                v-if="hasLocal('cash_denominations')"
                v-model="choices.cash_denominations"
                :label="t`Taka notes for the POS cash count`"
                :description="t`From 1,000 taka down to 1 taka.`"
              />
            </div>
          </section>
        </template>
      </div>
    </div>

    <div
      v-if="options"
      class="shrink-0 border-t border-outline-gray-1 px-4 pt-3 pb-[max(env(safe-area-inset-bottom),0.75rem)]"
    >
      <div class="mx-auto flex max-w-4xl items-center justify-between gap-3">
        <FrappeButton
          :label="embedded ? t`Skip for now` : t`Cancel`"
          :disabled="applying"
          data-testid="business-setup-skip"
          @click="$emit('done', null)"
        />
        <FrappeErrorMessage v-if="applyError" :message="applyError" />
        <FrappeButton
          variant="solid"
          :label="finishLabel"
          :loading="applying"
          :disabled="itemsLoading || aiBusy !== ''"
          data-testid="business-setup-finish"
          @click="finish"
        />
      </div>
    </div>

    <AISettings :open="showAiSettings" @close="closeAiSettings" />
  </div>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import {
  Button as FrappeButton,
  ErrorMessage as FrappeErrorMessage,
  Select as FrappeSelect,
  Spinner as FrappeSpinner,
  Switch as FrappeSwitch,
  Textarea as FrappeTextarea,
} from 'frappe-ui';
import AISettings from 'src/components/AI/AISettings.vue';
import PageHeader from 'src/components/PageHeader.vue';
import {
  OTHER_BUSINESS,
  applySetup,
  buildApplyOptions,
  describeAnswers,
  findImages,
  getCatalogItems,
  getSetupOptions,
  groupRows,
  mergeItems,
  suggestItems,
  suggestQuestions,
  toggleAnswer,
} from 'src/utils/businessSetup';
import type {
  Answers,
  ApplyResult,
  CatalogItems,
  LocalDefault,
  SetupChoices,
  SetupItemRow,
  SetupOptions,
  SetupQuestion,
} from 'src/utils/businessSetup';
import { computed, onMounted, reactive, ref, watch } from 'vue';

defineProps<{
  /** Shown right after the company setup, before the app itself has loaded. */
  embedded?: boolean;
}>();
const emit = defineEmits<{
  /** The setup is over: with what was made, or null when the user skipped it. */
  done: [result: ApplyResult | null];
}>();

/** Lucide classes by catalog icon name, spelled out so the build keeps them. */
const ICONS: Record<string, string> = {
  pill: 'lucide-pill',
  utensils: 'lucide-utensils',
  'shopping-basket': 'lucide-shopping-basket',
  shirt: 'lucide-shirt',
  smartphone: 'lucide-smartphone',
  scissors: 'lucide-scissors',
  wrench: 'lucide-wrench',
  book: 'lucide-book-open',
  store: 'lucide-store',
};

const options = ref<SetupOptions | null>(null);
const loadError = ref('');
const businessId = ref('');
const answers = ref<Answers>({});
const aiQuestions = ref<SetupQuestion[]>([]);
const note = ref('');
const rows = ref<SetupItemRow[]>([]);
const catalog = ref<Pick<CatalogItems, 'groups' | 'uoms'>>({
  groups: [],
  uoms: [],
});
const itemsLoading = ref(false);
const aiBusy = ref<'' | 'items' | 'questions'>('');
const aiError = ref('');
const applying = ref(false);
const applyError = ref('');
const showAiSettings = ref(false);
const isAiAdmin = !!window.frappe?.boot?.books?.ai?.is_admin;
const choices = reactive<SetupChoices>({
  guest_parties: true,
  vat: true,
  vat_rate: null,
  mobile_wallets: true,
  cash_denominations: true,
  fetch_images: true,
});
/** Each load of catalog items is numbered, so a slow answer to an old question is dropped. */
let itemRequest = 0;

const businessCards = computed(() => [
  ...(options.value?.business_types ?? []).map((business) => ({
    ...business,
    iconClass: ICONS[business.icon] ?? ICONS.store,
  })),
  {
    id: OTHER_BUSINESS,
    label: t`Something else`,
    description: t`Describe it and let the assistant suggest items`,
    iconClass: ICONS.store,
  },
]);
const business = computed(() =>
  options.value?.business_types.find((type) => type.id === businessId.value)
);
const businessLabel = computed(() => business.value?.label ?? '');
const questions = computed(() => [
  ...(business.value?.questions ?? []),
  ...aiQuestions.value,
]);
const groupedRows = computed(() => groupRows(rows.value));
const selectableCount = computed(
  () => rows.value.filter((row) => !row.exists).length
);
const selectedCount = computed(
  () => rows.value.filter((row) => row.selected && !row.exists).length
);
/** The assistant needs something to go on: a listed business, or a description. */
const canAskAi = computed(
  () => businessId.value !== OTHER_BUSINESS || note.value.trim().length > 2
);
const finishLabel = computed(() =>
  selectedCount.value
    ? t`Finish and add ${selectedCount.value} items`
    : t`Finish setup`
);
const vatOptions = computed(() => [
  { label: t`No VAT on items`, value: '' },
  ...(options.value?.vat_rates ?? []).map((rate) => ({
    label: `${rate}%`,
    value: String(rate),
  })),
]);
const vatRateValue = computed({
  get: () => (choices.vat_rate === null ? '' : String(choices.vat_rate)),
  set: (value: string) => {
    choices.vat_rate = value === '' ? null : Number(value);
  },
});

onMounted(loadOptions);
watch(() => choices.fetch_images, loadImages);

async function loadOptions() {
  try {
    options.value = await getSetupOptions();
  } catch (error) {
    loadError.value = getMessage(error);
  }
}

function hasLocal(key: LocalDefault): boolean {
  return !!options.value?.local_defaults.includes(key);
}

async function selectBusiness(id: string) {
  if (id === businessId.value) {
    return;
  }

  businessId.value = id;
  answers.value = {};
  aiQuestions.value = [];
  aiError.value = '';
  rows.value = [];
  catalog.value = { groups: [], uoms: [] };
  await loadCatalogItems();
}

async function pick(question: SetupQuestion, optionId: string) {
  answers.value = toggleAnswer(answers.value, question, optionId);
  // The catalog only knows its own questions; the AI's answers shape the AI's suggestions.
  if (business.value?.questions.some(({ id }) => id === question.id)) {
    await loadCatalogItems();
  }
}

async function loadCatalogItems() {
  const request = ++itemRequest;
  if (!business.value) {
    itemsLoading.value = false;
    return;
  }

  itemsLoading.value = true;
  try {
    const result = await getCatalogItems(businessId.value, answers.value);
    if (request !== itemRequest) {
      return;
    }

    catalog.value = { groups: result.groups, uoms: result.uoms };
    rows.value = mergeItems(
      rows.value,
      result.items,
      'catalog',
      result.existing
    );
    void loadImages();
  } catch (error) {
    applyError.value = getMessage(error);
  } finally {
    if (request === itemRequest) {
      itemsLoading.value = false;
    }
  }
}

/** Find a picture for each row that names one to look for. A failed search leaves rows without one. */
async function loadImages() {
  if (!choices.fetch_images) {
    return;
  }

  const queries = [
    ...new Set(
      rows.value
        .filter((row) => !row.image && row.image_query && !row.exists)
        .map((row) => row.image_query)
    ),
  ];
  if (!queries.length) {
    return;
  }

  try {
    const found = await findImages(queries);
    for (const row of rows.value) {
      row.image ||= found[row.image_query] ?? '';
    }
  } catch {
    // Pictures are a nicety: the setup goes on without them.
  }
}

async function askForQuestions() {
  await askAi('questions', async () => {
    const asked = await suggestQuestions(
      businessLabel.value,
      describeAnswers(questions.value, answers.value),
      note.value
    );
    const known = new Set(questions.value.map((question) => question.id));
    // Ids of the AI's questions must not clash with the catalog's or each other's.
    aiQuestions.value = [
      ...aiQuestions.value,
      ...asked.map((question, index) => ({
        ...question,
        id: known.has(question.id)
          ? `${question.id}_${aiQuestions.value.length + index}`
          : question.id,
      })),
    ];
    if (!asked.length) {
      aiError.value = t`The assistant had no more questions. Ask it to suggest items.`;
    }
  });
}

async function askForItems() {
  await askAi('items', async () => {
    const suggested = await suggestItems(
      businessLabel.value,
      describeAnswers(questions.value, answers.value),
      note.value,
      rows.value.map((row) => row.name)
    );
    if (!suggested.items.length) {
      aiError.value = t`The assistant had nothing more to suggest.`;
      return;
    }

    rows.value = mergeItems(rows.value, suggested.items, 'ai');
    void loadImages();
  });
}

async function askAi(kind: 'items' | 'questions', run: () => Promise<void>) {
  aiBusy.value = kind;
  aiError.value = '';
  try {
    await run();
  } catch (error) {
    aiError.value = getMessage(error);
  } finally {
    aiBusy.value = '';
  }
}

async function closeAiSettings() {
  showAiSettings.value = false;
  // A key saved in the dialog turns the assistant on here.
  const refreshed = await getSetupOptions().catch(() => null);
  if (refreshed && options.value) {
    options.value.ai = refreshed.ai;
  }
}

function isGroupSelected(groupItems: SetupItemRow[]): boolean {
  const selectable = groupItems.filter((row) => !row.exists);
  return selectable.length > 0 && selectable.every((row) => row.selected);
}

function isGroupPartial(groupItems: SetupItemRow[]): boolean {
  const picked = groupItems.filter((row) => !row.exists && row.selected);
  return picked.length > 0 && !isGroupSelected(groupItems);
}

function toggleGroup(groupItems: SetupItemRow[], event: Event) {
  const { checked } = event.target as HTMLInputElement;
  for (const row of groupItems) {
    row.selected = checked && !row.exists;
  }
}

async function finish() {
  applying.value = true;
  applyError.value = '';
  try {
    const result = await applySetup(
      buildApplyOptions(
        rows.value,
        catalog.value,
        choices,
        options.value?.local_defaults ?? []
      )
    );
    emit('done', result);
  } catch (error) {
    applyError.value = getMessage(error);
  } finally {
    applying.value = false;
  }
}

function getMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
</script>
