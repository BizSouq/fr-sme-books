<template>
  <div class="flex h-full min-h-0 flex-col">
    <PageHeader :title="t`AI Assistant`">
      <FrappeButton
        v-if="canUseAi"
        icon-left="lucide-history"
        :label="t`History`"
        @click="showHistory = !showHistory"
      />
      <FrappeButton
        v-if="aiState.entries.length"
        icon-left="lucide-plus"
        :label="t`New chat`"
        @click="clearConversation"
      />
      <FrappeButton
        icon-left="lucide-settings"
        :label="t`Settings`"
        @click="showSettings = true"
      />
    </PageHeader>

    <div
      v-if="!canUseAi"
      class="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center"
    >
      <p class="text-ink-gray-6">
        {{ t`The AI assistant is not turned on for you.` }}
      </p>
      <FrappeButton
        v-if="isAiAdmin"
        variant="solid"
        :label="t`Set up the assistant`"
        @click="showSettings = true"
      />
    </div>

    <div v-else class="relative flex min-h-0 flex-1 overflow-hidden">
      <AssistantPanel ref="panel" class="min-h-0 flex-1" wide />

      <aside
        v-if="showHistory"
        class="absolute inset-y-0 end-0 z-10 flex w-80 flex-col border-s border-outline-gray-1 bg-surface-base shadow-lg sm:relative sm:shadow-none"
      >
        <div
          class="flex items-center justify-between border-b border-outline-gray-1 p-3"
        >
          <h3 class="text-sm font-semibold text-ink-gray-9">
            {{ t`Saved chats` }}
          </h3>
          <FrappeButton
            variant="ghost"
            icon="lucide-x"
            :label="t`Close`"
            @click="showHistory = false"
          />
        </div>
        <div class="flex gap-1 border-b border-outline-gray-1 p-1 text-xs">
          <FrappeButton
            class="flex-1"
            :variant="tab === 'all' ? 'subtle' : 'ghost'"
            :label="t`All (${aiState.savedSessions.length})`"
            @click="tab = 'all'"
          />
          <FrappeButton
            class="flex-1"
            :variant="tab === 'charts' ? 'subtle' : 'ghost'"
            :label="t`With charts (${chartSessions.length})`"
            @click="tab = 'charts'"
          />
        </div>
        <div class="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto p-2">
          <p
            v-if="!shownSessions.length"
            class="p-6 text-center text-sm text-ink-gray-5"
          >
            {{
              tab === 'charts'
                ? t`No saved charts yet.`
                : t`No saved chats yet.`
            }}
          </p>
          <div
            v-for="session in shownSessions"
            :key="session.id"
            class="group relative cursor-pointer rounded-lg border p-3"
            :class="
              session.id === aiState.activeSessionId
                ? 'border-outline-gray-4 bg-surface-gray-2'
                : 'border-outline-gray-1 hover:bg-surface-gray-1'
            "
            @click="loadSession(session.id)"
          >
            <h4 class="line-clamp-2 pe-6 text-sm font-medium text-ink-gray-8">
              {{ session.title || t`Conversation` }}
            </h4>
            <div class="mt-1 flex justify-between text-xs text-ink-gray-5">
              <span>{{ formatDate(session.updatedAt) }}</span>
              <span v-if="session.charts.length">{{
                t`${session.charts.length} chart(s)`
              }}</span>
            </div>
            <FrappeButton
              variant="ghost"
              size="sm"
              icon="lucide-trash-2"
              class="absolute end-1 top-1 opacity-0 group-hover:opacity-100"
              :label="t`Delete chat`"
              @click.stop="deleteSession(session.id)"
            />
          </div>
        </div>
        <div
          v-if="aiState.savedSessions.length"
          class="border-t border-outline-gray-1 p-2"
        >
          <FrappeButton
            variant="ghost"
            theme="red"
            :label="t`Clear all history`"
            @click="clearHistory"
          />
        </div>
      </aside>
    </div>

    <AISettings :open="showSettings" @close="showSettings = false" />
  </div>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import { Button as FrappeButton } from 'frappe-ui';
import { clearSavedSessions } from 'src/ai/history';
import { canUseAi, isAiAdmin } from 'src/ai/session';
import {
  aiState,
  clearConversation,
  deleteSession,
  loadSession,
} from 'src/ai/store';
import AISettings from 'src/components/AI/AISettings.vue';
import AssistantPanel from 'src/components/AI/AssistantPanel.vue';
import PageHeader from 'src/components/PageHeader.vue';
import { showDialog } from 'src/utils/interactive';
import { computed, onActivated, ref } from 'vue';

const panel = ref<InstanceType<typeof AssistantPanel>>();
const showHistory = ref(false);
const showSettings = ref(false);
const tab = ref<'all' | 'charts'>('all');

const chartSessions = computed(() =>
  aiState.savedSessions.filter((session) => session.charts.length)
);
const shownSessions = computed(() =>
  tab.value === 'charts' ? chartSessions.value : aiState.savedSessions
);

onActivated(() => panel.value?.focus());

function formatDate(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

async function clearHistory() {
  const confirmed = await showDialog({
    title: t`Clear history?`,
    type: 'warning',
    destructive: true,
    detail: t`This removes every saved conversation from this browser.`,
    buttons: [
      { label: t`Cancel`, action: () => false, isEscape: true },
      { label: t`Clear history`, action: () => true, isPrimary: true },
    ],
  });
  if (confirmed) {
    clearSavedSessions();
    clearConversation();
    aiState.savedSessions = [];
  }
}
</script>
