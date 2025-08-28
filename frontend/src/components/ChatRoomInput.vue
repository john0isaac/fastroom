<template>
  <form
    v-if="joined"
    ref="composeForm"
    class="flex items-end gap-3 px-2 py-3 border-t border-neutral-200 dark:border-neutral-800 bg-transparent"
    @submit.prevent="send"
  >
    <textarea
      ref="composer"
      :value="draft"
      placeholder="Message... (Enter to send, Shift+Enter for newline)"
      :disabled="!isOpen"
      rows="1"
      class="flex-1 resize-none max-h-[200px] min-h-[42px] leading-6 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 px-2.5 py-2 text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
      @keydown.enter="onEnterKey"
      @input="handleInput"
    />
    <div class="flex gap-2">
      <button
        type="button"
        class="inline-flex items-center rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 px-3 py-2 text-sm hover:bg-neutral-50 dark:hover:bg-neutral-800 disabled:opacity-50"
        :disabled="!draft"
        @click="clearDraft"
      >
        Clear
      </button>
      <button
        type="submit"
        class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-sm text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
        :disabled="!draft.trim() || sending"
      >
        Send
      </button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';

const props = defineProps<{
  joined: boolean;
  isOpen: boolean;
  draft: string;
  sending: boolean;
  send: () => void;
  clearDraft: () => void;
  onEnterKey: (e: KeyboardEvent) => void;
  onInputTyping: () => void;
  onInputDraft: (v: string) => void;
}>();

const composer = ref<HTMLTextAreaElement | null>(null);
let baseHeight: number | null = null;

function autoResize() {
  const el = composer.value;
  if (!el) return;
  if (baseHeight == null) baseHeight = el.offsetHeight || el.scrollHeight;
  el.style.height = 'auto';
  const content = el.scrollHeight;
  const buffer = 4;
  el.style.height =
    Math.min(200, content <= baseHeight + buffer ? baseHeight : content) + 'px';
}
function focusComposer() {
  composer.value?.focus();
}

function handleInput(e: Event) {
  const v = (e.target as HTMLTextAreaElement).value;
  props.onInputDraft(v);
  props.onInputTyping();
  // resize after value change
  nextTick(() => autoResize());
}

onMounted(() => {
  nextTick(() => autoResize());
});
watch(
  () => props.draft,
  () => nextTick(() => autoResize()),
);

defineExpose({
  focusComposer,
  autoResize,
});
</script>
