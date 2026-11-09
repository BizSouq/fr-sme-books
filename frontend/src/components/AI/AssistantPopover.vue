<template>
  <Teleport v-if="canUseAi && !isAiPage" to="body">
    <div
      v-if="isAssistantOpen"
      class="fixed inset-0 z-20 bg-black/25 md:hidden"
      @click="isAssistantOpen = false"
    />
    <aside
      v-if="isAssistantOpen"
      class="fixed inset-y-0 end-0 z-20 flex w-full flex-col border-s border-outline-gray-1 bg-surface-base shadow-2xl sm:w-[28rem]"
      role="dialog"
      :aria-label="t`AI assistant`"
    >
      <header
        class="flex h-12 shrink-0 items-center gap-2 border-b border-outline-gray-1 px-3"
      >
        <FrappeIcon icon="lucide-sparkles" class="size-4 text-ink-gray-6" />
        <h2 class="flex-1 truncate font-semibold text-ink-gray-9">
          {{ t`Assistant` }}
        </h2>
        <FrappeButton
          variant="ghost"
          icon="lucide-plus"
          :label="t`New conversation`"
          :tooltip="t`New conversation`"
          @click="clearConversation"
        />
        <FrappeButton
          variant="ghost"
          icon="lucide-maximize-2"
          :label="t`Open full screen`"
          :tooltip="t`Open full screen`"
          @click="openFullScreen"
        />
        <FrappeButton
          variant="ghost"
          icon="lucide-x"
          :label="t`Close`"
          :tooltip="t`Close`"
          @click="isAssistantOpen = false"
        />
      </header>
      <AssistantPanel ref="panel" class="min-h-0 flex-1" />
    </aside>
    <!-- The way in, at the same spot on every screen. -->
    <FrappeButton
      v-else
      variant="solid"
      size="lg"
      icon="lucide-sparkles"
      class="fixed bottom-6 end-6 z-10 !rounded-full shadow-lg"
      :label="t`Assistant`"
      :tooltip="t`Assistant (Ctrl+J)`"
      @click="isAssistantOpen = true"
    />
  </Teleport>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import { Button as FrappeButton, Icon as FrappeIcon } from 'frappe-ui';
import { canUseAi } from 'src/ai/session';
import { clearConversation, isAssistantOpen } from 'src/ai/store';
import { shortcutsKey } from 'src/utils/injectionKeys';
import { routeTo } from 'src/utils/ui';
import {
  computed,
  inject,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue';
import { useRoute } from 'vue-router';
import AssistantPanel from './AssistantPanel.vue';

/** The slide-over, mounted once in the desk so the conversation survives navigation. */
const shortcuts = inject(shortcutsKey);
const route = useRoute();
const panel = ref<InstanceType<typeof AssistantPanel>>();
const isAiPage = computed(() => route.path === '/ai');

watch(isAssistantOpen, (open) => {
  if (open) {
    shortcuts?.set(
      'AssistantPopover',
      ['Escape'],
      () => (isAssistantOpen.value = false)
    );
    void nextTick(() => panel.value?.focus());
  } else {
    shortcuts?.delete('AssistantPopover');
  }
});

onMounted(() => {
  shortcuts?.pmod.set('AssistantToggle', ['KeyJ'], () => {
    if (canUseAi.value && !isAiPage.value) {
      isAssistantOpen.value = !isAssistantOpen.value;
    }
  });
});

onBeforeUnmount(() => {
  shortcuts?.delete('AssistantToggle');
  shortcuts?.delete('AssistantPopover');
});

async function openFullScreen() {
  isAssistantOpen.value = false;
  await routeTo('/ai');
}
</script>
