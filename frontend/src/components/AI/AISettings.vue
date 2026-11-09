<template>
  <POSDialog
    :open-modal="open"
    :title="t`Assistant settings`"
    :subtitle="
      t`The assistant runs on your own AI subscription. Keys are stored encrypted and never sent to the browser.`
    "
    size="2xl"
    @closemodal="$emit('close')"
  >
    <div v-if="!status" class="flex justify-center py-8">
      <FrappeSpinner class="size-5" />
    </div>
    <div v-else class="flex flex-col gap-6">
      <!-- The AI Guard's main switches; the full rules are in the Desk form. -->
      <section v-if="status.is_admin" class="flex flex-col gap-3">
        <h3 class="text-base font-semibold text-ink-gray-9">
          {{ t`AI Guard` }}
        </h3>
        <FrappeSwitch
          v-for="item in switches"
          :key="item.key"
          :model-value="status[item.key]"
          :label="item.label"
          :description="item.description"
          :disabled="
            busy || (item.key === 'allow_destructive' && !status.allow_writes)
          "
          @update:model-value="(value: boolean) => saveSwitch(item.key, value)"
        />
        <a
          href="/app/books-ai-settings"
          target="_blank"
          class="text-sm text-ink-gray-6 underline"
        >
          {{ t`Allowed roles, hidden record types and limits` }}
        </a>
      </section>

      <section
        v-for="scope in scopes"
        :key="scope.key"
        class="flex flex-col gap-3"
      >
        <div class="flex items-baseline gap-2">
          <h3 class="text-base font-semibold text-ink-gray-9">
            {{ scope.title }}
          </h3>
          <span v-if="scope.stored" class="text-xs text-ink-gray-5">{{
            describe(scope.stored)
          }}</span>
        </div>
        <p class="text-sm text-ink-gray-5">{{ scope.hint }}</p>
        <template v-if="scope.editable">
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <FrappeSelect
              v-model="forms[scope.key].provider"
              :label="t`Provider`"
              :options="providerOptions"
              :disabled="busy"
            />
            <FrappeTextInput
              v-model="forms[scope.key].model"
              :label="t`Model`"
              :placeholder="defaultModel(forms[scope.key].provider)"
              :disabled="busy"
            />
          </div>
          <FrappeTextInput
            v-model="forms[scope.key].apiKey"
            type="password"
            autocomplete="off"
            :label="t`API key`"
            :placeholder="scope.stored ? t`Enter a new key to replace it` : ''"
            :disabled="busy"
          />
          <div class="flex gap-2">
            <FrappeButton
              variant="solid"
              :label="t`Save key`"
              :disabled="busy || !forms[scope.key].apiKey.trim()"
              @click="saveKey(scope.key)"
            />
            <FrappeButton
              v-if="scope.stored"
              :label="t`Remove`"
              :disabled="busy"
              @click="removeKey(scope.key)"
            />
          </div>
        </template>
      </section>

      <div
        v-if="status.can_use"
        class="flex items-center gap-3 border-t border-outline-gray-1 pt-4"
      >
        <FrappeButton
          :label="t`Test connection`"
          :disabled="busy || (!status.company_key && !status.user_key)"
          @click="test"
        />
        <span
          v-if="testMessage"
          class="text-sm"
          :class="testOk ? 'text-ink-green-7' : 'text-ink-red-7'"
        >
          {{ testMessage }}
        </span>
      </div>
      <FrappeErrorMessage v-if="error" :message="error" />
    </div>
  </POSDialog>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import {
  Button as FrappeButton,
  ErrorMessage as FrappeErrorMessage,
  Select as FrappeSelect,
  Spinner as FrappeSpinner,
  Switch as FrappeSwitch,
  TextInput as FrappeTextInput,
} from 'frappe-ui';
import {
  getAiStatus,
  removeAiKey,
  saveAiKey,
  saveAiSettings,
  testAiConnection,
} from 'src/ai/client';
import { setAiAccess } from 'src/ai/session';
import type { AiProvider, AiStatus, KeySummary } from 'src/ai/types';
import POSDialog from 'src/components/POS/POSDialog.vue';
import { computed, reactive, ref, watch } from 'vue';

type Scope = 'company' | 'user';
type Switch =
  'enabled' | 'allow_writes' | 'allow_destructive' | 'allow_personal_keys';

const props = defineProps<{ open: boolean }>();
defineEmits<{ close: [] }>();

const status = ref<AiStatus | null>(null);
const busy = ref(false);
const error = ref('');
const testMessage = ref('');
const testOk = ref(false);
const forms = reactive<
  Record<Scope, { provider: AiProvider; model: string; apiKey: string }>
>({
  company: { provider: 'anthropic', model: '', apiKey: '' },
  user: { provider: 'anthropic', model: '', apiKey: '' },
});

const switches: { key: Switch; label: string; description: string }[] = [
  {
    key: 'enabled',
    label: t`Enable the assistant`,
    description: t`For the roles the AI Guard allows.`,
  },
  {
    key: 'allow_writes',
    label: t`Allow proposed changes`,
    description: t`The assistant may propose creating, changing and submitting records. Each change waits for the user's approval.`,
  },
  {
    key: 'allow_destructive',
    label: t`Allow deletes and cancellations`,
    description: t`The assistant may also propose deleting records and cancelling documents.`,
  },
  {
    key: 'allow_personal_keys',
    label: t`Allow personal API keys`,
    description: t`Each user may bring their own key instead of the company's.`,
  },
];

const providerOptions = computed(() =>
  (status.value?.providers ?? []).map((provider) => ({
    label: provider.label,
    value: provider.name,
  }))
);

const scopes = computed(() => {
  const current = status.value;
  if (!current) {
    return [];
  }

  const list = [
    {
      key: 'company' as Scope,
      title: t`Company key`,
      hint: current.is_admin
        ? t`Used by everyone who has not set a key of their own.`
        : t`Only a Books Manager can change the company key.`,
      stored: current.company_key,
      editable: current.is_admin,
    },
  ];
  if (current.allow_personal_keys) {
    list.push({
      key: 'user',
      title: t`Your key`,
      hint: t`Optional. When set, your questions use this key instead of the company's.`,
      stored: current.user_key,
      editable: true,
    });
  }
  return list;
});

watch(
  () => props.open,
  (open) => open && void load(),
  { immediate: true }
);

async function load() {
  await run(async () => setStatus(await getAiStatus()));
}

function setStatus(next: AiStatus) {
  status.value = next;
  setAiAccess(next.can_use);
  for (const scope of ['company', 'user'] as Scope[]) {
    const stored = scope === 'company' ? next.company_key : next.user_key;
    forms[scope].provider =
      stored?.provider ?? next.providers[0]?.name ?? 'anthropic';
    forms[scope].model = stored?.model ?? '';
    forms[scope].apiKey = '';
  }
}

function defaultModel(provider: AiProvider) {
  return (
    status.value?.providers.find((item) => item.name === provider)
      ?.default_model ?? ''
  );
}

function describe(key: KeySummary) {
  const label =
    status.value?.providers.find((item) => item.name === key.provider)?.label ??
    key.provider;
  const model = key.model || defaultModel(key.provider);
  return key.hint
    ? `${label} · ${model} · ••••${key.hint}`
    : `${label} · ${model}`;
}

async function saveKey(scope: Scope) {
  const form = forms[scope];
  await run(async () =>
    setStatus(
      await saveAiKey({
        scope,
        provider: form.provider,
        model: form.model,
        api_key: form.apiKey,
      })
    )
  );
}

async function removeKey(scope: Scope) {
  await run(async () => setStatus(await removeAiKey(scope)));
}

async function saveSwitch(key: Switch, value: boolean) {
  await run(async () => setStatus(await saveAiSettings({ [key]: value })));
}

async function test() {
  testMessage.value = '';
  await run(async () => {
    const result = await testAiConnection();
    testOk.value = result.ok;
    testMessage.value = result.ok
      ? t`Connected to ${result.provider} (${result.model}).`
      : result.message || t`The provider rejected the key.`;
  });
}

async function run(action: () => Promise<void>) {
  busy.value = true;
  error.value = '';
  try {
    await action();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : String(caught);
  } finally {
    busy.value = false;
  }
}
</script>
