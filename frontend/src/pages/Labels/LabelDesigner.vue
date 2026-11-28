<template>
  <div class="flex h-full min-h-0 flex-col bg-surface-base">
    <PageHeader :title="isNew ? t`New label` : template.template_name">
      <template #mobile>
        <FrappeButton
          variant="solid"
          :label="t`Save`"
          :loading="isSaving"
          :disabled="!canSave"
          @click="save"
        />
      </template>
      <template v-if="isNew" #left>
        <FrappeTextInput
          v-model="template.template_name"
          class="w-60"
          size="sm"
          data-testid="label-template-name"
          :placeholder="t`Name this label, like Shoe tag`"
          @update:model-value="dirty = true"
        />
      </template>
      <FrappeButton
        v-if="!isNew"
        icon-left="lucide-printer"
        :label="t`Print labels`"
        @click="openPrint"
      />
      <FrappeButton
        variant="solid"
        :label="t`Save`"
        :loading="isSaving"
        :disabled="!canSave"
        data-testid="label-save"
        @click="save"
      />
    </PageHeader>

    <div
      v-if="isLoaded"
      class="min-h-0 flex-1 overflow-y-auto lg:grid lg:grid-cols-[minmax(0,1fr)_22rem] lg:overflow-hidden"
      data-testid="label-designer"
    >
      <!-- The label, to drag and size what it shows -->
      <div class="flex min-h-[18rem] min-w-0 flex-col bg-surface-gray-1">
        <div
          ref="canvasArea"
          class="relative flex min-h-0 flex-1 items-center justify-center overflow-auto p-6"
          @pointerdown.self="selectedId = ''"
        >
          <div
            class="relative shrink-0 shadow-md ring-1 ring-outline-gray-2"
            :style="{
              width: `${template.label_width * PX_PER_MM * scale}px`,
              height: `${template.label_height * PX_PER_MM * scale}px`,
            }"
          >
            <div
              :style="{
                transform: `scale(${scale})`,
                transformOrigin: 'top left',
                width: `${template.label_width}mm`,
                height: `${template.label_height}mm`,
              }"
            >
              <LabelFace
                :sheet="template"
                :elements="template.elements"
                :data="previewData"
                :price-format="priceFormat"
                :no-barcode-text="t`New barcode`"
              />
            </div>

            <!-- Handles over the label, in screen pixels so they stay a usable size. -->
            <div
              class="absolute inset-0"
              style="touch-action: none"
              @pointerdown.self="selectedId = ''"
            >
              <div
                v-if="centerGuide"
                class="pointer-events-none absolute inset-y-0 w-px bg-ink-blue-3"
                :style="{
                  left: `${(template.label_width / 2) * PX_PER_MM * scale}px`,
                }"
              />
              <div
                v-for="element of template.elements"
                :key="element.id"
                class="absolute cursor-move rounded-[2px] outline-offset-0"
                :class="
                  element.id === selectedId
                    ? 'outline outline-2 outline-ink-blue-3'
                    : 'outline-dashed outline-1 outline-transparent hover:outline-ink-gray-4'
                "
                :style="toScreen(element)"
                :data-element="element.field"
                :title="getFieldLabel(element.field, attributes)"
                @pointerdown.stop="startDrag($event, element, 'move')"
              >
                <span
                  v-if="element.id === selectedId"
                  class="absolute -bottom-1.5 -end-1.5 size-3 cursor-nwse-resize rounded-sm border border-ink-blue-3 bg-surface-white"
                  data-testid="label-resize"
                  @pointerdown.stop="startDrag($event, element, 'resize')"
                />
              </div>
            </div>
          </div>
        </div>

        <div
          class="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-outline-gray-1 bg-surface-base px-4 py-2 text-sm text-ink-gray-6"
        >
          <span>
            {{ t`${template.label_width} × ${template.label_height} mm` }}
          </span>
          <span class="hidden sm:inline">{{
            t`Drag to move. Drag the corner to resize. Arrow keys nudge.`
          }}</span>
          <div class="ms-auto flex min-w-0 items-center gap-2">
            <span class="whitespace-nowrap">{{ t`Preview with` }}</span>
            <Link
              class="w-52"
              size="small"
              :df="previewItemField"
              :value="previewItem"
              :border="true"
              @change="setPreviewItem"
            />
          </div>
        </div>
      </div>

      <!-- Settings -->
      <aside
        class="flex flex-col gap-6 border-outline-gray-1 p-4 lg:min-h-0 lg:overflow-y-auto lg:border-s"
      >
        <section class="flex flex-col gap-3">
          <h2 class="text-base-semibold text-ink-gray-9">
            {{ t`Label size` }}
          </h2>
          <FrappeSelect
            :model-value="presetKey"
            :options="presetOptions"
            data-testid="label-preset"
            @update:model-value="(value) => setPreset(String(value ?? ''))"
          />
          <div v-if="presetKey === CUSTOM" class="grid grid-cols-2 gap-3">
            <FrappeSelect
              class="col-span-2"
              :label="t`Paper`"
              :model-value="template.paper"
              :options="paperOptions"
              @update:model-value="
                (value) => setSheet({ paper: value as Paper })
              "
            />
            <NumberInput
              :label="t`Width (mm)`"
              :value="template.label_width"
              @change="(value) => setSize(value, template.label_height)"
            />
            <NumberInput
              :label="t`Height (mm)`"
              :value="template.label_height"
              @change="(value) => setSize(template.label_width, value)"
            />
            <NumberInput
              :label="t`Labels across`"
              :value="template.columns"
              :step="1"
              @change="
                (value) => setSheet({ columns: Math.max(1, Math.round(value)) })
              "
            />
            <NumberInput
              :label="t`Gap across (mm)`"
              :value="template.column_gap"
              @change="(value) => setSheet({ column_gap: value })"
            />
            <template v-if="template.paper === 'A4 Sheet'">
              <NumberInput
                :label="t`Gap down (mm)`"
                :value="template.row_gap"
                @change="(value) => setSheet({ row_gap: value })"
              />
              <NumberInput
                :label="t`Top margin (mm)`"
                :value="template.margin_top"
                @change="(value) => setSheet({ margin_top: value })"
              />
              <NumberInput
                :label="t`Left margin (mm)`"
                :value="template.margin_left"
                @change="(value) => setSheet({ margin_left: value })"
              />
            </template>
          </div>
          <p class="text-p-sm text-ink-gray-5">{{ paperHint }}</p>
        </section>

        <section class="flex flex-col gap-3">
          <h2 class="text-base-semibold text-ink-gray-9">
            {{ t`Add to label` }}
          </h2>
          <div class="flex flex-wrap gap-1.5">
            <FrappeButton
              v-for="option of fieldOptions"
              :key="option.field"
              size="sm"
              :icon-left="option.icon"
              :label="option.label"
              :data-testid="`label-add-${option.field}`"
              @click="addElement(option.field)"
            />
          </div>
        </section>

        <section
          v-if="selected"
          class="flex flex-col gap-3"
          data-testid="label-element-settings"
        >
          <div class="flex items-center justify-between">
            <h2 class="text-base-semibold text-ink-gray-9">
              {{ getFieldLabel(selected.field, attributes) }}
            </h2>
            <FrappeButton
              variant="ghost"
              theme="red"
              icon-left="lucide-trash-2"
              :label="t`Remove`"
              @click="removeSelected"
            />
          </div>

          <FrappeTextInput
            v-if="selected.field === 'text'"
            :model-value="selected.text ?? ''"
            :label="t`Text`"
            :placeholder="t`Like মূল্য or Thank you`"
            data-testid="label-text"
            @update:model-value="(value: string) => update({ text: value })"
          />
          <FrappeTextInput
            v-else-if="selected.field !== 'barcode'"
            :model-value="selected.text ?? ''"
            :label="t`Text before it`"
            :placeholder="
              selected.field === 'price' ? t`Like MRP or মূল্য` : t`Optional`
            "
            @update:model-value="(value: string) => update({ text: value })"
          />

          <div class="grid grid-cols-2 gap-3">
            <NumberInput
              :label="
                selected.field === 'barcode'
                  ? t`Number size (pt)`
                  : t`Text size (pt)`
              "
              :value="selected.fontSize"
              :step="0.5"
              @change="(value) => update({ fontSize: Math.max(3, value) })"
            />
            <div
              v-if="selected.field !== 'barcode'"
              class="flex flex-col gap-1.5"
            >
              <span class="text-xs text-ink-gray-5">{{ t`Align` }}</span>
              <FrappeTabButtons
                :model-value="selected.align ?? 'left'"
                :options="alignOptions"
                @update:model-value="
                  (value) => update({ align: value as Align })
                "
              />
            </div>
          </div>

          <FrappeSwitch
            v-if="selected.field !== 'barcode'"
            :model-value="!!selected.bold"
            :label="t`Bold`"
            @update:model-value="(value: boolean) => update({ bold: value })"
          />
          <FrappeSwitch
            v-if="selected.field === 'barcode'"
            :model-value="!!selected.showNumber"
            :label="t`Show the number under the bars`"
            @update:model-value="
              (value: boolean) => update({ showNumber: value })
            "
          />
          <FrappeSwitch
            v-if="selected.field === 'price'"
            :model-value="!selected.hideCurrency"
            :label="t`Show the currency sign`"
            @update:model-value="
              (value: boolean) => update({ hideCurrency: !value })
            "
          />
          <FrappeSwitch
            v-if="selected.field !== 'barcode'"
            :model-value="!!selected.banglaDigits"
            :label="t`Bangla digits (১২৩)`"
            @update:model-value="
              (value: boolean) => update({ banglaDigits: value })
            "
          />

          <div class="grid grid-cols-4 gap-2">
            <NumberInput
              v-for="key of positionKeys"
              :key="key.key"
              :label="key.label"
              :value="selected[key.key]"
              :step="0.5"
              @change="(value) => update({ [key.key]: value })"
            />
          </div>
          <FrappeButton
            icon-left="lucide-align-center-horizontal"
            :label="t`Center on label`"
            @click="update({ x: (template.label_width - selected.width) / 2 })"
          />
        </section>
        <p v-else class="text-p-sm text-ink-gray-5">
          {{
            t`Tap something on the label to change its size, text or position.`
          }}
        </p>

        <section
          class="mt-auto flex flex-col gap-3 border-t border-outline-gray-1 pt-4"
        >
          <FrappeSwitch
            :model-value="!!template.is_default"
            :label="t`Use this label by default`"
            @update:model-value="
              (value: boolean) => {
                template.is_default = value ? 1 : 0;
                dirty = true;
              }
            "
          />
          <FrappeButton
            icon-left="lucide-rotate-ccw"
            :label="t`Start again from the standard layout`"
            @click="resetLayout"
          />
        </section>
      </aside>
    </div>
    <div v-else class="flex flex-1 items-center justify-center">
      <FrappeErrorMessage v-if="loadError" :message="loadError" />
      <FrappeSpinner v-else class="size-6" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useElementSize } from '@vueuse/core';
import { t } from 'fyo';
import {
  Button as FrappeButton,
  ErrorMessage as FrappeErrorMessage,
  Select as FrappeSelect,
  Spinner as FrappeSpinner,
  Switch as FrappeSwitch,
  TabButtons as FrappeTabButtons,
  TextInput as FrappeTextInput,
} from 'frappe-ui';
import { NotFoundError } from 'fyo/utils/errors';
import type { TargetField } from 'schemas/types';
import Link from 'src/components/Controls/Link.vue';
import LabelFace from 'src/components/Labels/LabelFace.vue';
import NumberInput from 'src/components/Labels/NumberInput.vue';
import { getPriceFormat } from 'src/components/Labels/priceFormat';
import PageHeader from 'src/components/PageHeader.vue';
import { getDocument, insertDocument, updateDocument } from 'src/frappe/api';
import { getErrorMessage } from 'src/utils';
import { showToast } from 'src/utils/interactive';
import {
  clampElement,
  findPreset,
  getDefaultElements,
  getFieldLabel,
  getLabelFields,
  getLabelItems,
  getLabelPresets,
  getLabelRows,
  getNewTemplate,
  getPageLayout,
  getSampleData,
  LABEL_DOCTYPE,
  newElementId,
  parseTemplate,
  round,
  scaleElements,
  serializeTemplate,
  type Align,
  type LabelData,
  type LabelElement,
  type LabelSheet,
  type LabelTemplate,
  type Paper,
} from 'src/utils/labels';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';

/**
 * Lays out a label: the shop picks its size, adds the item's name, price,
 * barcode, size and color, and drags each where it goes, seeing a real item.
 */
const props = defineProps<{ name: string }>();
const router = useRouter();

const PX_PER_MM = 96 / 25.4;
const CUSTOM = 'custom';
const SNAP = 0.5;

const template = ref<LabelTemplate>(getNewTemplate());
const savedName = ref('');
const modified = ref<unknown>();
const isLoaded = ref(false);
const loadError = ref('');
const isSaving = ref(false);
const dirty = ref(false);
const selectedId = ref('');
const centerGuide = ref(false);
const attributes = ref<string[]>([]);
const company = ref('');
const previewItem = ref('');
const previewRow = ref<LabelData>();
const priceFormat = getPriceFormat();
// A size the shop typed stays custom while it matches no preset.
const customSize = ref(false);

const canvasArea = ref<HTMLElement>();
const { width: areaWidth, height: areaHeight } = useElementSize(canvasArea);

const isNew = computed(() => !savedName.value);
const canSave = computed(
  () => !!template.value.template_name.trim() && (dirty.value || isNew.value)
);
const selected = computed(() =>
  template.value.elements.find((element) => element.id === selectedId.value)
);
const previewData = computed(
  () => previewRow.value ?? getSampleData(company.value)
);
const fieldOptions = computed(() => getLabelFields(attributes.value));
const presetKey = computed(() =>
  customSize.value ? CUSTOM : (findPreset(template.value)?.key ?? CUSTOM)
);
const presetOptions = computed(() => [
  ...getLabelPresets().map(({ key, label }) => ({ label, value: key })),
  { label: t`Other size…`, value: CUSTOM },
]);
const paperOptions = [
  { label: t`Label printer (roll)`, value: 'Label Printer' },
  { label: t`A4 sheet of labels`, value: 'A4 Sheet' },
];
const alignOptions = [
  { label: t`Left`, value: 'left', icon: 'lucide-align-left' },
  { label: t`Center`, value: 'center', icon: 'lucide-align-center' },
  { label: t`Right`, value: 'right', icon: 'lucide-align-right' },
];
const positionKeys: { key: 'x' | 'y' | 'width' | 'height'; label: string }[] = [
  { key: 'x', label: t`Left` },
  { key: 'y', label: t`Top` },
  { key: 'width', label: t`Width` },
  { key: 'height', label: t`Height` },
];
const previewItemField = {
  fieldname: 'preview_item',
  fieldtype: 'Link',
  target: 'Item',
  label: t`Item`,
  placeholder: t`Sample item`,
  create: false,
  filters: [['has_variants', '=', 0]],
} as TargetField;

const paperHint = computed(() => {
  const layout = getPageLayout(template.value);
  if (template.value.paper === 'A4 Sheet') {
    return t`${layout.perPage} labels on each A4 sheet.`;
  }

  return layout.columns > 1
    ? t`${layout.columns} labels across the roll. Set the printer's paper to ${layout.pageWidth} × ${layout.pageHeight} mm.`
    : t`One label at a time. Set the printer's paper to ${layout.pageWidth} × ${layout.pageHeight} mm.`;
});

/** The label at a size that fits the screen, up to ten times its print size. */
const scale = computed(() => {
  const width = template.value.label_width * PX_PER_MM;
  const height = template.value.label_height * PX_PER_MM;
  const fit = Math.min(
    (areaWidth.value - 48) / width,
    (areaHeight.value - 48) / height
  );
  return Math.max(1, Math.min(10, Number.isFinite(fit) ? fit : 4));
});

onMounted(async () => {
  window.addEventListener('keydown', onKeydown);
  try {
    await Promise.all([loadTemplate(), loadFields()]);
    isLoaded.value = true;
  } catch (error) {
    loadError.value = getErrorMessage(error as Error);
  }
});

onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));

async function loadTemplate() {
  if (!props.name || props.name.startsWith('new-')) {
    return;
  }

  try {
    const values = await getDocument(LABEL_DOCTYPE, props.name);
    template.value = parseTemplate(values);
    savedName.value = String(values.name);
    modified.value = values.modified;
    customSize.value = !findPreset(template.value);
  } catch (error) {
    if (!(error instanceof NotFoundError)) {
      throw error;
    }
  }
}

async function loadFields() {
  const result = await getLabelRows('', []);
  attributes.value = result.attributes;
  company.value = result.company;
}

async function setPreviewItem(value: string) {
  previewItem.value = value;
  previewRow.value = undefined;
  if (!value) {
    return;
  }

  try {
    [previewRow.value] = await getLabelItems([value]);
    if (previewRow.value) {
      previewRow.value.company = company.value;
    }
  } catch (error) {
    showToast({ type: 'error', message: getErrorMessage(error as Error) });
  }
}

function setPreset(key: string) {
  if (key === CUSTOM) {
    customSize.value = true;
    return;
  }

  const preset = getLabelPresets().find((option) => option.key === key);
  if (!preset) {
    return;
  }

  customSize.value = false;
  setSheet(preset.sheet);
}

/** Changes the paper or label size; what the label shows keeps its place on it. */
function setSheet(sheet: Partial<LabelSheet>) {
  const from = {
    width: template.value.label_width,
    height: template.value.label_height,
  };
  Object.assign(template.value, sheet);
  const to = {
    width: template.value.label_width,
    height: template.value.label_height,
  };
  if (to.width !== from.width || to.height !== from.height) {
    template.value.elements = scaleElements(template.value.elements, from, to);
  }

  dirty.value = true;
}

function setSize(width: number, height: number) {
  if (width < 10 || height < 5 || width > 210 || height > 297) {
    showToast({
      type: 'warning',
      message: t`Labels can be 10 to 210 mm wide and 5 to 297 mm high.`,
    });
    return;
  }

  setSheet({ label_width: width, label_height: height });
}

function addElement(field: string) {
  const { label_width: width, label_height: height } = template.value;
  const isBarcode = field === 'barcode';
  const element: LabelElement = clampElement(
    {
      id: newElementId(),
      field,
      text: field === 'text' ? t`Your text` : '',
      x: round(width * 0.1),
      y: round(height * 0.35),
      width: round(width * 0.8),
      height: round(isBarcode ? height * 0.4 : Math.max(3, height * 0.16)),
      fontSize: round(Math.max(5, Math.min(10, height / 3.5)), 1),
      align: 'center',
      showNumber: isBarcode,
      bold: field === 'price',
    },
    template.value
  );
  template.value.elements.push(element);
  selectedId.value = element.id;
  dirty.value = true;
}

function update(changes: Partial<LabelElement>) {
  const element = selected.value;
  if (!element) {
    return;
  }

  Object.assign(
    element,
    clampElement({ ...element, ...changes }, template.value)
  );
  dirty.value = true;
}

function removeSelected() {
  template.value.elements = template.value.elements.filter(
    (element) => element.id !== selectedId.value
  );
  selectedId.value = '';
  dirty.value = true;
}

function resetLayout() {
  template.value.elements = getDefaultElements(
    template.value.label_width,
    template.value.label_height
  );
  selectedId.value = '';
  dirty.value = true;
}

function toScreen(element: LabelElement) {
  const k = PX_PER_MM * scale.value;
  return {
    left: `${element.x * k}px`,
    top: `${element.y * k}px`,
    width: `${element.width * k}px`,
    height: `${element.height * k}px`,
  };
}

function snap(value: number) {
  return Math.round(value / SNAP) * SNAP;
}

function startDrag(
  event: PointerEvent,
  element: LabelElement,
  mode: 'move' | 'resize'
) {
  if (event.button !== 0) {
    return;
  }

  event.preventDefault();
  selectedId.value = element.id;
  const start = { x: event.clientX, y: event.clientY, element: { ...element } };
  const k = PX_PER_MM * scale.value;

  const onMove = (move: PointerEvent) => {
    const dx = (move.clientX - start.x) / k;
    const dy = (move.clientY - start.y) / k;
    const next = { ...start.element };
    if (mode === 'move') {
      next.x = snap(start.element.x + dx);
      next.y = snap(start.element.y + dy);
      // Snaps to the label's middle, the way most tags are laid out.
      const middle = template.value.label_width / 2 - next.width / 2;
      centerGuide.value = Math.abs(next.x - middle) < 0.75;
      if (centerGuide.value) {
        next.x = round(middle, 2);
      }
    } else {
      next.width = snap(start.element.width + dx);
      next.height = snap(start.element.height + dy);
    }

    Object.assign(element, clampElement(next, template.value));
    dirty.value = true;
  };
  const onUp = () => {
    centerGuide.value = false;
    window.removeEventListener('pointermove', onMove);
    window.removeEventListener('pointerup', onUp);
    window.removeEventListener('pointercancel', onUp);
  };
  window.addEventListener('pointermove', onMove);
  window.addEventListener('pointerup', onUp);
  window.addEventListener('pointercancel', onUp);
}

function onKeydown(event: KeyboardEvent) {
  const element = selected.value;
  const target = event.target as HTMLElement | null;
  if (
    !element ||
    target?.closest('input, textarea, select, [contenteditable="true"]')
  ) {
    return;
  }

  if ((event.key === 'Delete' || event.key === 'Backspace') && !event.repeat) {
    event.preventDefault();
    removeSelected();
    return;
  }

  const step = event.shiftKey ? 2 : SNAP;
  const moves: Record<string, Partial<LabelElement>> = {
    ArrowLeft: { x: element.x - step },
    ArrowRight: { x: element.x + step },
    ArrowUp: { y: element.y - step },
    ArrowDown: { y: element.y + step },
  };
  const move = moves[event.key];
  if (move) {
    event.preventDefault();
    update(move);
  }
}

async function save() {
  isSaving.value = true;
  try {
    const values = serializeTemplate(template.value);
    const saved = isNew.value
      ? await insertDocument(LABEL_DOCTYPE, values)
      : await updateDocument(LABEL_DOCTYPE, savedName.value, {
          ...values,
          modified: modified.value,
        });
    modified.value = saved.modified;
    dirty.value = false;
    showToast({ type: 'success', message: t`Label saved` });
    if (isNew.value) {
      savedName.value = String(saved.name);
      await router.replace(
        `/label-designer/${encodeURIComponent(savedName.value)}`
      );
    }
  } catch (error) {
    showToast({ type: 'error', message: getErrorMessage(error as Error) });
  } finally {
    isSaving.value = false;
  }
}

async function openPrint() {
  if (dirty.value) {
    await save();
  }

  await router.push({
    path: '/print-labels',
    query: { template: savedName.value },
  });
}
</script>
