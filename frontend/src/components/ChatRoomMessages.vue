<template>
  <ul
    v-if="joined"
    ref="msgList"
    class="list-none px-2 pb-3 m-0 flex-1 min-h-0 overflow-y-auto flex flex-col-reverse gap-2"
    @scroll.passive="onScrollMessages"
  >
    <li
      v-for="(m, i) in messages"
      :key="m._k || m.message_id || i"
      :class="[
        'text-[0.8rem] flex flex-row w-full',
        (m.username || m.user) === myUsername ? 'justify-end' : '',
      ]"
    >
      <template v-if="m.type === 'chat'">
        <div
          :class="[
            'max-w-[620px] border px-3 py-2 rounded-lg relative flex flex-col gap-1 transition-colors',
            (m.username || m.user) === myUsername
              ? 'bg-indigo-600 text-white border-indigo-600 ml-auto'
              : 'bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 border-neutral-200 dark:border-neutral-800 shadow-sm mr-auto',
          ]"
        >
          <div
            class="text-[0.6rem] uppercase tracking-wide font-semibold flex items-center gap-2 flex-wrap opacity-65 text-inherit"
          >
            <span
              :class="[
                'font-bold text-[0.65rem] tracking-wide rounded-md px-1 py-[1px]',
                (m.username || m.user) === myUsername
                  ? 'bg-white/20 text-white'
                  : 'bg-black/10 dark:bg-white/10',
              ]"
              >{{ m.username || m.user }}</span
            >
            <span class="font-medium text-[0.6rem] opacity-80">{{
              ts(m.ts)
            }}</span>
          </div>
          <div
            class="whitespace-pre-wrap break-words text-[0.82rem] leading-tight"
          >
            {{ m.message }}
          </div>
        </div>
      </template>
      <template v-else-if="m.type === 'system'">
        <div
          class="text-[0.7rem] text-center opacity-60 tracking-wide text-neutral-500 dark:text-neutral-400 w-full"
        >
          • {{ m.message }}
        </div>
      </template>
    </li>
    <li
      ref="historySentinel"
      :class="[
        'flex justify-center items-center py-2 text-[0.65rem] opacity-70 min-h-[32px]',
        historyLoading ? '' : !hasMoreHistory ? 'opacity-90' : '',
      ]"
    >
      <div
        v-if="historyLoading"
        class="w-4 h-4 border-2 border-white/30 border-t-indigo-500 rounded-full animate-spin"
        aria-label="Loading older messages"
      ></div>
      <div
        v-else-if="hasMoreHistory"
        class="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 px-3 py-1 rounded-full uppercase tracking-wide flex items-center gap-1 whitespace-nowrap shadow-sm"
      >
        Older messages
      </div>
      <div
        v-else
        class="bg-gradient-to-br from-white to-neutral-200 dark:from-neutral-900 dark:to-neutral-800 border border-neutral-200 dark:border-neutral-700 px-3 py-1.5 rounded-full text-[0.6rem] tracking-widest uppercase flex items-center gap-1 whitespace-nowrap shadow"
        aria-label="Start of conversation"
      >
        ✦ Start of room ✦
      </div>
    </li>
  </ul>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';

// Keep in sync with parent ChatRoom.vue local message shape
interface ChatFeedItem {
  type: string;
  message_id?: number;
  username?: string;
  user?: string;
  message?: string;
  ts?: string;
  edited?: boolean;
  _k?: number;
  [key: string]: unknown;
}

const props = defineProps<{
  joined: boolean;
  messages: ChatFeedItem[];
  myUsername: string;
  historyLoading: boolean;
  hasMoreHistory: boolean;
}>();

const emit = defineEmits<{
  (e: 'load-more', force?: boolean): void;
}>();

const msgList = ref<HTMLElement | null>(null);
const historySentinel = ref<HTMLElement | null>(null);
let historyObserver: IntersectionObserver | null = null;

function ts(d?: string) {
  if (!d) return '';
  try {
    const dt = new Date(d);
    return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function onScrollMessages(e: Event) {
  if (historyObserver) return; // observer handles it
  const el = e.target as HTMLElement;
  if (el.scrollTop <= 4) emit('load-more');
}

function ensureHistoryFill() {
  const list = msgList.value;
  if (!list) return;
  if (!props.hasMoreHistory) return;
  if (list.scrollHeight <= list.clientHeight + 10) {
    setTimeout(() => emit('load-more'), 20);
  }
}

function setupHistoryObserver() {
  if (historyObserver) historyObserver.disconnect();
  if (!('IntersectionObserver' in window)) return;
  const rootEl = msgList.value;
  if (!rootEl) return;
  historyObserver = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) emit('load-more');
      }
    },
    { root: rootEl, threshold: 0, rootMargin: '0px 0px 80px 0px' },
  );
  if (historySentinel.value) historyObserver.observe(historySentinel.value);
}

function teardownHistoryObserver() {
  if (historyObserver) {
    historyObserver.disconnect();
    historyObserver = null;
  }
}

type ScrollSnapshot = { height: number; top: number };
function getScrollSnapshot(): ScrollSnapshot | null {
  const list = msgList.value;
  if (!list) return null;
  return { height: list.scrollHeight, top: list.scrollTop };
}
function restoreScrollAfterPrepend(snap?: ScrollSnapshot | null) {
  const list = msgList.value;
  if (!list || !snap) return;
  const delta = list.scrollHeight - snap.height;
  list.scrollTop = snap.top + delta;
}

onMounted(() => {
  // Allow parent to decide when to setup; still safe to auto-setup here.
  setupHistoryObserver();
  // Give parent a chance to trigger initial fill
  setTimeout(() => ensureHistoryFill(), 0);
});
onUnmounted(() => {
  teardownHistoryObserver();
});

defineExpose<{
  ensureHistoryFill: () => void;
  setupHistoryObserver: () => void;
  teardownHistoryObserver: () => void;
  getScrollSnapshot: () => ScrollSnapshot | null;
  restoreScrollAfterPrepend: (snap?: ScrollSnapshot | null) => void;
}>({
  ensureHistoryFill,
  setupHistoryObserver,
  teardownHistoryObserver,
  getScrollSnapshot,
  restoreScrollAfterPrepend,
});
</script>
