<template>
  <Modal
    :open-modal="open"
    :title="t`Add sizes and colors`"
    :subtitle="itemName"
    size="2xl"
    @closemodal="$emit('close')"
  >
    <div class="flex flex-col gap-5">
      <p class="text-base text-ink-gray-6">
        {{
          t`Tap each size and color this article comes in. Books creates one item for each combination, with its own stock and barcode.`
        }}
      </p>
      <fieldset
        v-for="attribute of data.attributes"
        :key="attribute.attribute"
        class="flex flex-col gap-2"
      >
        <div class="flex items-center justify-between gap-2">
          <legend class="text-lg font-semibold text-ink-gray-8">
            {{ attribute.attribute }}
            <span class="ms-1 text-sm font-normal text-ink-gray-5">{{
              t`${chosen[attribute.attribute]?.length ?? 0} picked`
            }}</span>
          </legend>
          <FrappeButton
            size="sm"
            variant="ghost"
            :label="allChosen(attribute.attribute) ? t`Clear` : t`Select all`"
            @click="toggleAll(attribute.attribute)"
          />
        </div>
        <div class="flex flex-wrap gap-2" role="group">
          <button
            v-for="value of attribute.values"
            :key="value.value"
            type="button"
            class="flex min-h-10 min-w-12 items-center justify-center gap-2 rounded-lg border px-3 text-base font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-outline-gray-4"
            :class="
              isChosen(attribute.attribute, value.value)
                ? 'border-transparent bg-surface-gray-10 text-white'
                : 'border-outline-gray-2 bg-surface-base text-ink-gray-8 hover:bg-surface-gray-2'
            "
            :aria-pressed="isChosen(attribute.attribute, value.value)"
            :data-value="value.value"
            @click="toggle(attribute.attribute, value.value)"
          >
            <span
              v-if="value.color"
              class="size-4 rounded-full border border-outline-gray-2"
              :style="{ background: value.color }"
              aria-hidden="true"
            />
            {{ value.value }}
          </button>
        </div>
      </fieldset>
      <label class="flex max-w-60 flex-col gap-1.5">
        <span class="text-sm text-ink-gray-6">{{ t`Selling price` }}</span>
        <FrappeTextInput
          v-model="rate"
          type="number"
          min="0"
          :placeholder="String(defaultRate)"
        />
        <span class="text-xs text-ink-gray-5">{{
          t`Each new item gets this price. Change one later on its own item.`
        }}</span>
      </label>
    </div>
    <template #actions="{ size }">
      <p class="me-auto text-base text-ink-gray-6" data-testid="variant-count">
        {{ countLabel }}
      </p>
      <FrappeButton :size="size" @click="$emit('close')">{{
        t`Cancel`
      }}</FrappeButton>
      <FrappeButton
        :size="size"
        variant="solid"
        :disabled="!newCount"
        :loading="isCreating"
        @click="create"
      >
        {{ t`Create ${newCount} items` }}
      </FrappeButton>
    </template>
  </Modal>
</template>

<script setup lang="ts">
import { t } from 'fyo';
import {
  Button as FrappeButton,
  TextInput as FrappeTextInput,
} from 'frappe-ui';
import Modal from 'src/components/POS/POSDialog.vue';
import { handleErrorWithDialog } from 'src/errorHandling';
import {
  countNewVariants,
  createVariants,
  type VariantData,
} from 'src/utils/itemVariants';
import { showToast } from 'src/utils/interactive';
import { computed, ref, watch } from 'vue';

/**
 * Picks the sizes and colors of an article in one go and creates an item for
 * each combination that it lacks. The values its variants have start picked.
 */
const props = defineProps<{
  open: boolean;
  item: string;
  itemName: string;
  defaultRate: number;
  data: VariantData;
}>();
const emit = defineEmits<{ close: []; created: [names: string[]] }>();

const chosen = ref<Record<string, string[]>>({});
const rate = ref('');
const isCreating = ref(false);

watch(
  () => [props.open, props.data] as const,
  ([open]) => {
    if (open) {
      chosen.value = getUsedValues();
      rate.value = '';
    }
  },
  { immediate: true }
);

function getUsedValues(): Record<string, string[]> {
  return Object.fromEntries(
    props.data.attributes.map(({ attribute, values }) => [
      attribute,
      values
        .map(({ value }) => value)
        .filter((value) =>
          props.data.variants.some(
            (variant) => variant.values[attribute] === value
          )
        ),
    ])
  );
}

const newCount = computed(() => countNewVariants(props.data, chosen.value));
const countLabel = computed(() => {
  if (!newCount.value) {
    return t`Pick a value of each attribute`;
  }

  return t`${newCount.value} new items`;
});

function isChosen(attribute: string, value: string): boolean {
  return !!chosen.value[attribute]?.includes(value);
}

function toggle(attribute: string, value: string) {
  const values = chosen.value[attribute] ?? [];
  chosen.value = {
    ...chosen.value,
    [attribute]: values.includes(value)
      ? values.filter((entry) => entry !== value)
      : [...values, value],
  };
}

function allChosen(attribute: string): boolean {
  const values = props.data.attributes.find(
    (entry) => entry.attribute === attribute
  )?.values;
  return (chosen.value[attribute]?.length ?? 0) === (values?.length ?? 0);
}

function toggleAll(attribute: string) {
  const values =
    props.data.attributes.find((entry) => entry.attribute === attribute)
      ?.values ?? [];
  chosen.value = {
    ...chosen.value,
    [attribute]: allChosen(attribute) ? [] : values.map(({ value }) => value),
  };
}

async function create() {
  isCreating.value = true;
  try {
    const price = rate.value === '' ? undefined : Number(rate.value);
    const { created } = await createVariants(props.item, chosen.value, price);
    showToast({
      type: 'success',
      message: t`Created ${created.length} items`,
    });
    emit('created', created);
  } catch (error) {
    await handleErrorWithDialog(error, undefined, true);
  } finally {
    isCreating.value = false;
  }
}
</script>
