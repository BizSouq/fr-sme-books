<template>
  <div class="flex h-full min-h-0 w-full min-w-0 overflow-x-auto">
    <div class="flex min-w-0 flex-1 flex-col">
      <slot name="header" />
      <FrappeScrollArea class="min-h-0 flex-1" viewport-class="pb-10">
        <div
          v-if="withAside"
          :class="columnClasses"
          class="grid grid-cols-[minmax(0,1fr)_20rem] items-start gap-6"
        >
          <div class="min-w-0"><slot name="body" /></div>
          <!-- The summary column on the other side from the app sidebar. -->
          <div class="sticky top-4 pt-5"><slot name="aside" /></div>
        </div>
        <div v-else :class="columnClasses">
          <slot name="body" />
        </div>
      </FrappeScrollArea>
      <div
        v-if="$slots.footer"
        class="shrink-0 border-t border-outline-gray-1 py-4"
      >
        <div :class="columnClasses">
          <slot name="footer" />
        </div>
      </div>
    </div>

    <!-- Side panels: quick edit, row editor, linked entries -->
    <slot name="quickedit" />
  </div>
</template>
<script lang="ts">
import { ScrollArea as FrappeScrollArea } from 'frappe-ui';
import { defineComponent } from 'vue';

export default defineComponent({
  components: { FrappeScrollArea },
  props: {
    useFullWidth: Boolean,
    /** Shows the `aside` slot as a column beside the body. */
    withAside: Boolean,
  },
  computed: {
    /** Full width lifts the reading-width cap; a summary column widens it. */
    columnClasses(): string[] {
      const cap = this.withAside ? 'max-w-[1280px]' : 'max-w-[940px]';
      return ['mx-auto w-full px-3 sm:px-5', this.useFullWidth ? '' : cap];
    },
  },
});
</script>
