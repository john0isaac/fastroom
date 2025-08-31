<template>
  <section
    class="flex flex-col min-h-0 bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100 transition-colors duration-200"
    :style="{
      height: 'calc(80vh - var(--app-footer-h, 3rem))',
      maxHeight: 'calc(80vh - var(--app-footer-h, 3rem))',
    }"
  >
    <div class="flex flex-1 min-h-0">
      <ChatRoomSideBar
        :is-open="isOpen"
        :joined="joined"
        :users="users"
        :my-username="myUsername"
        :typing-users="typingUsers"
        :current-room="currentRoom"
        :status-text="statusText"
        :status-class="statusClass"
        :handle-user-connect="handleUserConnect"
        :handle-user-disconnect="handleUserDisconnect"
      />
      <div
        class="flex-1 min-w-0 flex flex-col relative min-h-0 overflow-hidden"
      >
        <header
          v-if="joined"
          class="px-2 pt-1 pb-3 border-b border-neutral-200 dark:border-neutral-800 mb-2"
        >
          <h2 class="m-0 text-[1.05rem] font-semibold">#{{ currentRoom }}</h2>
        </header>
        <div
          v-else
          class="mt-12 text-center opacity-80 text-neutral-500 dark:text-neutral-400"
        >
          <h2 class="text-xl font-semibold">Welcome to FastRoom ⚡</h2>
          <p class="mt-2">
            You're authenticated. You will auto-join the
            <code>{{ DEFAULT_ROOM }}</code> room when the WebSocket connects.
          </p>
          <ul
            class="list-none p-0 m-0 mt-2 text-[0.85rem] text-neutral-500 dark:text-neutral-400"
          >
            <li class="mt-1">Realtime messages & presence via WebSocket.</li>
            <li class="mt-1">
              Automatic reconnection with exponential backoff.
            </li>
            <li class="mt-1">
              Token refresh won't drop your session instantly (debounced).
            </li>
          </ul>
        </div>

        <ChatRoomMessages
          v-if="joined"
          ref="messagesRef"
          :joined="joined"
          :messages="messages"
          :my-username="myUsername"
          :history-loading="historyLoading"
          :has-more-history="hasMoreHistory"
          @load-more="loadMoreHistory"
        />
        <ChatRoomInput
          ref="inputRef"
          :joined="joined"
          :is-open="isOpen"
          :draft="draft"
          :sending="sending"
          :send="send"
          :clear-draft="clearDraft"
          :on-enter-key="onEnterKey"
          :on-input-typing="onInputTyping"
          :on-input-draft="updateDraft"
        />
      </div>
      <ChatRoomToasts :toasts="toasts" :dismiss-toast="dismissToast" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useAuthedWSClient } from '../utils/useAuthedWSClient';
import ChatRoomSideBar from './ChatRoomSideBar.vue';
import ChatRoomToasts from './ChatRoomToasts.vue';
import ChatRoomInput from './ChatRoomInput.vue';
import ChatRoomMessages from './ChatRoomMessages.vue';
import type { Envelope } from '../utils/wsClient';

// Base WS endpoint (without auth query param). The backend expects an access_token query param.
const BASE_WS_URL =
  (import.meta.env.VITE_WS_URL as string) ||
  `ws://${location.hostname}:8000/ws`;

// Accept optional roomName prop from parent (e.g. RoomDetail)
const props = defineProps<{ roomName?: string }>();
// Use prop as default room when provided, otherwise fall back to 'general'
const DEFAULT_ROOM = computed(() => props.roomName ?? 'general');

// Use composable to manage authenticated WebSocket lifecycle.
const {
  client,
  connect,
  disconnect,
  connected: wsConnected,
  manualDisconnect,
} = useAuthedWSClient(BASE_WS_URL, { connectOnMount: true });

const connected = wsConnected; // alias for existing code paths
const sending = ref(false);
const currentRoom = ref<string | null>(null);
const joined = computed(() => !!currentRoom.value);

const draft = ref('');
// Messages newest at TOP of array for simpler prepend of older pages (render reversed via CSS)
// Use Envelope (generic WS message shape) for flexible strongly-typed messages.
// Local message shape used in the chat feed (extends generic Envelope with optional fields)
interface ChatFeedItem extends Envelope {
  message_id?: number;
  username?: string;
  user?: string;
  message?: string;
  ts?: string;
  edited?: boolean;
  _k?: number; // internal unique key (becomes non-enumerable only after being processed by tagMessage())
  type: string; // narrower (system|chat|...) but keep as string for flexibility
}

const messages = ref<ChatFeedItem[]>([]);
// Local monotonically increasing sequence to tag each message with a stable, unique key.
// We avoid using the array index (breaks with unshift) or server message_id (may be absent/duplicated during pagination or reconnect).
let messageSeq = 0;
function tagMessage(m: ChatFeedItem): ChatFeedItem {
  if (m._k == null) {
    Object.defineProperty(m, '_k', {
      value: ++messageSeq,
      enumerable: false, // keep internal; not sent back to server or rendered via v-for spreads
      configurable: false,
      writable: false,
    });
  }
  return m;
}
const seenMessageIds = new Set<number>(); // track to avoid duplicate pagination loops
// Helper to fully reset message history state (e.g. on manual disconnect)
function resetHistoryState() {
  messages.value = [];
  seenMessageIds.clear();
  hasMoreHistory.value = true;
  historyLoading.value = false;
  lastHistoryLoadAt = 0;
}

const hasMoreHistory = ref(true);
const historyLoading = ref(false);
let lastHistoryLoadAt = 0;
const HISTORY_DEBOUNCE_MS = 600; // prevent rapid duplicate loads

const inputRef = ref<InstanceType<typeof ChatRoomInput> | null>(null);
const messagesRef = ref<InstanceType<typeof ChatRoomMessages> | null>(null);

function autoResize() {
  inputRef.value?.autoResize();
}
function updateDraft(v: string) {
  draft.value = v;
}

// Toasts
interface Toast {
  id: number;
  message: string;
  type: 'info' | 'error';
}
const toasts = ref<Toast[]>([]);
let toastSeq = 0;
function pushToast(message: string, type: Toast['type'] = 'info', ttl = 4000) {
  const id = ++toastSeq;
  toasts.value.push({ id, message, type });
  if (ttl > 0) setTimeout(() => dismissToast(id), ttl);
}
function dismissToast(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id);
}

const users = ref<string[]>([]);
const typingUsers = ref<Record<string, number>>({});
let typingActive = false;
let typingStopTimer: number | null = null;

// Auth user (source of truth for username now)
const authStore = useAuthStore();
const authUsername = computed(
  () => authStore.user?.username || authStore.user?.email || '',
);
// For highlighting own messages in feed
const myUsername = authUsername;

// Define a discriminated union of inbound messages we handle to provide type safety.
type InboundMessage =
  | { type: 'pong' }
  | { type: 'joined'; room: string }
  | { type: 'presence_state'; users: string[] }
  | { type: 'history'; messages: Envelope[] }
  | { type: 'history_more'; messages: Envelope[]; more: boolean }
  | { type: 'presence_diff'; join?: string[]; leave?: string[] }
  | { type: 'typing'; user: string; isTyping: boolean }
  | { type: 'error'; message?: string; error?: string }
  | { type: 'message_updated'; message_id: number; content: string }
  | { type: 'message_deleted'; message_id: number }
  | {
      type: 'member_update';
      room: string;
      username: string;
      is_moderator?: boolean;
      is_banned?: boolean;
      is_muted?: boolean;
    }
  | ({
      type: 'system';
      message?: string;
      room?: string;
      message_id?: number;
      username?: string;
      user?: string;
      ts?: string;
    } & Record<string, unknown>)
  | ({
      type: 'chat';
      message?: string;
      room?: string;
      message_id?: number;
      username?: string;
      user?: string;
      ts?: string;
    } & Record<string, unknown>);

let lastJoinedRoom: string | null = null; // remember for auto rejoin after reconnect
function joinDefaultRoom() {
  if (joined.value) return;
  client.send({ type: 'join', room: DEFAULT_ROOM.value } as Envelope);
}

// Auto-switch when parent passes a new roomName
function switchRoom(newRoom: string) {
  if (!newRoom) return;
  if (currentRoom.value === newRoom) return;
  // Send leave for existing room (if any)
  if (currentRoom.value) {
    try {
      client.send({ type: 'leave', room: currentRoom.value } as Envelope);
    } catch (e) {
      console.warn('[ChatRoom] failed to send leave', e);
    }
  }
  // Clear local state immediately so UI reflects transition
  resetHistoryState();
  users.value = [];
  typingUsers.value = {};
  currentRoom.value = null; // until joined event arrives
  // Defer join slightly to avoid race where backend still processes leave
  const target = newRoom;
  setTimeout(() => {
    if (connected.value) {
      client.send({ type: 'join', room: target } as Envelope);
    } else {
      lastJoinedRoom = target; // will auto-join on reconnect/open
    }
  }, 60);
}

watch(
  () => props.roomName,
  (newRoom) => {
    if (!newRoom) return;
    switchRoom(newRoom);
  },
);

function sendTyping(start: boolean) {
  if (!currentRoom.value) return;
  client.send({
    type: 'typing',
    room: currentRoom.value,
    isTyping: start,
  } as Envelope);
}

function onInputTyping() {
  if (!joined.value) return;
  if (!typingActive) {
    typingActive = true;
    sendTyping(true);
  }
  if (typingStopTimer) window.clearTimeout(typingStopTimer);
  typingStopTimer = window.setTimeout(() => {
    typingActive = false;
    sendTyping(false);
  }, 1500);
}

function pruneTyping() {
  const now = Date.now();
  for (const [u, ts] of Object.entries(typingUsers.value)) {
    if (now - ts > 3000) delete typingUsers.value[u];
  }
}

function send() {
  const text = draft.value.trim();
  if (!text || !currentRoom.value || sending.value) return;
  sending.value = true;
  if (import.meta.env.DEV) {
    console.debug(
      '[ChatRoom] sending chat while readyState',
      client.readyState?.(),
      'reconnectAttempts',
      client.getReconnectAttempts?.(),
    );
  }
  client.send({
    type: 'chat',
    room: currentRoom.value,
    message: text,
  } as Envelope);
  draft.value = '';
  autoResize();
  setTimeout(() => {
    sending.value = false;
    nextTick(() => inputRef.value?.focusComposer());
  }, 30);
}
function clearDraft() {
  draft.value = '';
  autoResize();
}
function onEnterKey(e: KeyboardEvent) {
  if (e.shiftKey) return;
  if (!e.isComposing) {
    e.preventDefault();
    send();
  }
}
function handleUserDisconnect() {
  manualDisconnect.value = true;
  disconnect();
  resetHistoryState();
  users.value = [];
  typingUsers.value = {};
  currentRoom.value = null;
}
function handleUserConnect() {
  // User explicitly wants to reconnect and auto-join previous/default room.
  manualDisconnect.value = false; // re-enable auto join logic in onOpen
  // Prepare for fresh history load
  resetHistoryState();
  currentRoom.value = null; // ensure onOpen logic joins
  connect();
}
client.onOpen(() => {
  const wasReconnecting =
    connected.value === false && client.getReconnectAttempts() > 0;
  // Auto rejoin previous room (only if not manually disconnected & user had joined before)
  if (!manualDisconnect.value) {
    if (lastJoinedRoom && !currentRoom.value) {
      client.send({ type: 'join', room: lastJoinedRoom } as Envelope);
      pushToast(`Rejoining #${lastJoinedRoom}…`, 'info', 2500);
    } else if (!currentRoom.value) {
      joinDefaultRoom();
    }
  }
  if (wasReconnecting) {
    pushToast('Reconnected', 'info', 2500);
  } else if (!manualDisconnect.value) {
    pushToast('Connected', 'info', 2000);
  }
});
client.onClose((ev?: CloseEvent) => {
  currentRoom.value = null;
  // If closure comes from manual disconnect ensure chat state is cleared.
  if (manualDisconnect.value) {
    messages.value = [];
    users.value = [];
    typingUsers.value = {};
  }
  // Only show toast if we didn't intentionally disconnect
  if (!manualDisconnect.value) {
    pushToast('Disconnected. Attempting to reconnect…', 'error', 4000);
  }
  console.debug('[WS] closed', ev?.code, ev?.reason);
});
client.onReconnecting((attempt, nextDelay) => {
  pushToast(
    `Reconnecting (attempt ${attempt}) in ${nextDelay}ms`,
    'info',
    Math.min(2500, nextDelay + 500),
  );
});
client.onJSON((raw) => {
  const data = raw as InboundMessage;
  // Basic diagnostic hook (could be gated by dev flag)
  if (data.type === 'pong') return; // ignore heartbeats
  if (data.type === 'joined') {
    currentRoom.value = data.room;
    lastJoinedRoom = data.room;
    messages.value.unshift(
      tagMessage({ type: 'system', room: data.room, message: 'You joined' }),
    );
    nextTick(() => inputRef.value?.focusComposer());
    return;
  }
  if (data.type === 'presence_state') {
    users.value = data.users;
    return;
  }
  if (data.type === 'history') {
    if (Array.isArray(data.messages)) {
      for (const m of data.messages) {
        const id = m.message_id;
        if (typeof id === 'number') {
          if (seenMessageIds.has(id)) continue;
          seenMessageIds.add(id);
        }
        messages.value.unshift(tagMessage(m));
      }
    }
    nextTick(() => messagesRef.value?.ensureHistoryFill());
    return;
  }
  if (data.type === 'history_more') {
    if (Array.isArray(data.messages) && data.messages.length) {
      const snap = messagesRef.value?.getScrollSnapshot();
      // Append in reverse so internal order stays newest->oldest (descending time)
      for (const m of [...data.messages].reverse()) {
        const id = m.message_id;
        if (typeof id === 'number') {
          if (seenMessageIds.has(id)) continue; // skip duplicates
          seenMessageIds.add(id);
        }
        messages.value.push(tagMessage(m));
      }
      nextTick(() => {
        messagesRef.value?.restoreScrollAfterPrepend(snap);
        messagesRef.value?.setupHistoryObserver();
        messagesRef.value?.ensureHistoryFill();
      });
    }
    if (typeof data.more === 'boolean') hasMoreHistory.value = data.more;
    historyLoading.value = false;
    return;
  }
  if (data.type === 'presence_diff') {
    if (data.join?.length)
      for (const u of data.join)
        if (!users.value.includes(u)) users.value.push(u);
    if (data.leave && data.leave.length) {
      users.value = users.value.filter((u) => !data.leave!.includes(u));
      for (const u of data.leave!) delete typingUsers.value[u];
    }
    return;
  }
  if (data.type === 'typing') {
    if (data.isTyping) typingUsers.value[data.user] = Date.now();
    else delete typingUsers.value[data.user];
    pruneTyping();
    return;
  }
  if (data.type === 'error') {
    const errMsg =
      (data.message && typeof data.message === 'string' && data.message) ||
      (data.error && typeof data.error === 'string' && data.error) ||
      'Unknown error';
    // Avoid duplicate prefixing
    const toastMsg = /^(error|failed)/i.test(errMsg)
      ? errMsg
      : `Error: ${errMsg}`;
    pushToast(toastMsg, 'error', 5000);
    // Also keep it in the feed for historical context
  }
  if (data.type === 'message_updated') {
    const idx = messages.value.findIndex(
      (m) => m.message_id === data.message_id,
    );
    if (idx !== -1) {
      messages.value[idx].message = data.content;
      messages.value[idx].edited = true;
    }
    return;
  }
  if (data.type === 'message_deleted') {
    const idx = messages.value.findIndex(
      (m) => m.message_id === data.message_id,
    );
    if (idx !== -1) {
      messages.value.splice(idx, 1);
    }
    return;
  }
  if (data.type === 'member_update') {
    // Show system line summarizing change
    const parts: string[] = [];
    if (typeof data.is_moderator === 'boolean')
      parts.push(
        data.is_moderator ? 'is now a moderator' : 'is no longer a moderator',
      );
    if (typeof data.is_banned === 'boolean')
      parts.push(data.is_banned ? 'was banned' : 'was unbanned');
    if (typeof data.is_muted === 'boolean')
      parts.push(data.is_muted ? 'was muted' : 'was unmuted');
    if (parts.length) {
      // Unshift so it appears at top with newest-first semantics
      messages.value.unshift(
        tagMessage({
          type: 'system',
          room: data.room,
          message: `${data.username} ${parts.join(', ')}`,
        }),
      );
    }
    return;
  }
  if (data.type === 'system' || data.type === 'chat') {
    const id = data.message_id;
    if (typeof id === 'number' && seenMessageIds.has(id)) return;
    if (typeof id === 'number') seenMessageIds.add(id);
    messages.value.unshift(tagMessage(data));
  } else {
    messages.value.unshift(tagMessage({ type: 'debug', raw: data }));
  }
  if (messages.value.length > 500) messages.value.splice(500);
});

onMounted(() => {
  autoResize();
  nextTick(() => {
    if (joined.value) inputRef.value?.focusComposer();
    autoResize();
  });
  // Delay observer until initial messages render
  nextTick(() => messagesRef.value?.setupHistoryObserver());
});
onUnmounted(() => {
  // Prevent lingering reconnect attempts when component is destroyed
  manualDisconnect.value = true;
  if (joined.value && currentRoom.value) {
    // Politely inform server we left (optional; server cleans up on close anyway)
    client.send({ type: 'leave', room: currentRoom.value } as Envelope);
  }
  client.disconnect();
  messagesRef.value?.teardownHistoryObserver();
});

const isOpen = computed(() => connected.value);
const statusText = computed(() => (isOpen.value ? 'OPEN' : 'CLOSED'));
const statusClass = computed(() =>
  isOpen.value
    ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-red-600 dark:text-red-400',
);

function loadMoreHistory(force = false) {
  if (!currentRoom.value) return;
  if (historyLoading.value) return;
  if (!hasMoreHistory.value && !force) return;
  const now = Date.now();
  if (!force && now - lastHistoryLoadAt < HISTORY_DEBOUNCE_MS) return;
  let before_id: number | undefined;
  for (let i = messages.value.length - 1; i >= 0; i--) {
    const m = messages.value[i];
    if (m && typeof m.message_id === 'number') {
      before_id = m.message_id;
      break;
    }
  }
  if (!before_id) return;
  // If we've already seen this before_id as the absolute oldest (no more) avoid spamming
  // (Optional: rely on hasMoreHistory flag primarily)
  historyLoading.value = true;
  lastHistoryLoadAt = now;
  client.send({
    type: 'history_more',
    room: currentRoom.value,
    before_id,
  } as Envelope);
}

// Keep textarea height in sync even if programmatic changes happen.
watch(draft, () => autoResize());
</script>
