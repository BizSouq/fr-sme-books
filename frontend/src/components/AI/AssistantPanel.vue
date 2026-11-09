<template>
  <div class="flex h-full min-h-0 flex-col bg-surface-base">
    <div ref="scroller" class="min-h-0 flex-1 overflow-y-auto">
      <div
        class="mx-auto flex w-full flex-col gap-4 p-4"
        :class="{ 'max-w-3xl': wide }"
      >
        <!-- Suggestions beat a blinking cursor. -->
        <div v-if="!aiState.entries.length" class="flex flex-col gap-5 pt-2">
          <p class="text-base text-ink-gray-6">
            {{
              t`Ask about your books and get answers and charts from your own records.`
            }}
          </p>
          <div
            v-for="group in groups"
            :key="group.key"
            class="flex flex-col gap-2"
          >
            <h4
              class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5"
            >
              {{ group.label }}
            </h4>
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <button
                v-for="question in group.questions"
                :key="question.id"
                class="flex items-center gap-2.5 rounded-lg border border-outline-gray-2 px-3 py-2.5 text-start text-sm text-ink-gray-8 hover:bg-surface-gray-2"
                @click="submit(question.prompt)"
              >
                <FrappeIcon
                  :icon="question.icon"
                  class="size-4 shrink-0 text-ink-gray-5"
                />
                <span class="font-medium">{{ question.label }}</span>
              </button>
            </div>
          </div>
        </div>

        <template v-for="entry in aiState.entries" :key="entry.id">
          <div v-if="entry.kind === 'user'" class="flex justify-end">
            <div
              class="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-ee-sm bg-surface-gray-7 px-3.5 py-2 text-base text-ink-white"
            >
              {{ entry.text }}
            </div>
          </div>
          <MessageBody
            v-else-if="entry.kind === 'assistant'"
            class="text-ink-gray-9"
            :text="entry.text"
          />
          <div
            v-else-if="entry.kind === 'error'"
            class="rounded-lg border border-outline-red-2 bg-surface-red-1 px-3 py-2 text-sm text-ink-red-7"
          >
            {{ entry.text }}
          </div>
          <ToolCallCard
            v-else
            :entry="entry"
            @confirm="onConfirm"
            @cancel="onCancel"
          />
        </template>

        <div
          v-if="aiState.isBusy && !aiState.awaitingConfirmation"
          class="flex items-center gap-2 text-ink-gray-5"
        >
          <FrappeSpinner class="size-4" />
          <span class="text-sm">{{ t`Thinking` }}</span>
        </div>
      </div>
    </div>

    <div class="border-t border-outline-gray-1 p-3">
      <div class="mx-auto w-full" :class="{ 'max-w-3xl': wide }">
        <p v-if="interim" class="mb-1.5 text-sm italic text-ink-gray-5">
          {{ interim }}
        </p>
        <div
          class="flex items-end gap-2 rounded-xl border border-outline-gray-2 bg-surface-white px-2.5 py-2 focus-within:border-outline-gray-4"
        >
          <textarea
            ref="input"
            v-model="draft"
            rows="1"
            :placeholder="isListening ? t`Listening…` : t`Ask about your books`"
            :disabled="aiState.isBusy"
            class="max-h-32 flex-1 resize-none border-0 bg-transparent p-0 text-base text-ink-gray-9 placeholder-ink-gray-4 outline-none focus:ring-0 disabled:opacity-60"
            @input="resize"
            @keydown.enter.exact.prevent="submit()"
          />
          <FrappeButton
            v-if="isSpeechSupported"
            variant="ghost"
            :icon="isListening ? 'lucide-mic-off' : 'lucide-mic'"
            :label="isListening ? t`Stop dictation` : t`Dictate`"
            :tooltip="isListening ? t`Stop dictation` : t`Dictate`"
            @click="toggleDictation"
          />
          <FrappeButton
            variant="solid"
            icon="lucide-arrow-up"
            :label="t`Send`"
            :tooltip="t`Send`"
            :disabled="!canSend"
            @click="submit()"
          />
        </div>
        <p class="mt-1.5 text-xs text-ink-gray-5">
          {{
            t`The assistant can be wrong. Check figures before acting on them. Changes always wait for your approval.`
          }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import {
  Button as FrappeButton,
  Icon as FrappeIcon,
  Spinner as FrappeSpinner,
} from 'frappe-ui';
import { ask } from 'src/ai/agent';
import { getAppAgentDeps } from 'src/ai/screens';
import { Dictation, isSpeechSupported, startDictation } from 'src/ai/speech';
import { aiState, resolveConfirmation } from 'src/ai/store';
import { getSuggestedQuestions } from 'src/ai/suggestions';
import { showToast } from 'src/utils/interactive';
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';
import MessageBody from './MessageBody.vue';
import ToolCallCard from './ToolCallCard.vue';

/** The conversation and its composer, shared by the slide-over and the /ai page. */
withDefaults(defineProps<{ wide?: boolean }>(), { wide: false });

const draft = ref('');
const interim = ref('');
const isListening = ref(false);
const input = ref<HTMLTextAreaElement>();
const scroller = ref<HTMLElement>();
let dictation: Dictation | null = null;

const canSend = computed(() => !!draft.value.trim() && !aiState.isBusy);
const groups = computed(() => {
  const questions = getSuggestedQuestions();
  return [
    {
      key: 'daily',
      label: t`Daily questions`,
      questions: questions.filter((q) => q.category === 'daily'),
    },
    {
      key: 'monthly',
      label: t`Monthly questions`,
      questions: questions.filter((q) => q.category === 'monthly'),
    },
  ];
});

// New entries and status changes both move the view to the end.
const scrollSignal = computed(() =>
  aiState.entries
    .map((entry) => ('status' in entry ? entry.status : entry.id))
    .join()
);
watch(scrollSignal, () => void scrollToEnd());
onMounted(() => void scrollToEnd());
onBeforeUnmount(stopDictation);

async function submit(text?: string) {
  const question = (text ?? draft.value).trim();
  if (!question || aiState.isBusy) {
    return;
  }

  stopDictation();
  draft.value = '';
  await nextTick();
  resize();
  await ask(question, getAppAgentDeps());
}

function onConfirm(id: string) {
  resolveConfirmation(id, true);
}

function onCancel(id: string) {
  resolveConfirmation(id, false, 'the user declined this change');
}

function focus() {
  input.value?.focus();
}

function resize() {
  if (input.value) {
    input.value.style.height = 'auto';
    input.value.style.height = `${input.value.scrollHeight}px`;
  }
}

async function scrollToEnd() {
  await nextTick();
  if (scroller.value) {
    scroller.value.scrollTop = scroller.value.scrollHeight;
  }
}

function toggleDictation() {
  if (isListening.value) {
    stopDictation();
    return;
  }

  isListening.value = true;
  dictation = startDictation(navigator.language || 'en', {
    onInterim: (text) => (interim.value = text),
    onFinal: (text) => {
      draft.value = [draft.value.trim(), text].filter(Boolean).join(' ');
      interim.value = '';
      void nextTick(resize);
    },
    onError: (message) => {
      stopDictation();
      showToast({ message, type: 'error' });
    },
    onEnd: () => {
      isListening.value = false;
      interim.value = '';
    },
  });
}

function stopDictation() {
  dictation?.stop();
  dictation = null;
  isListening.value = false;
  interim.value = '';
}

defineExpose({ focus });
</script>
