<template>
  <section class="chat layout">
    <div class="content-area">
      <aside class="sidebar">
        <div class="panel head">
          <div class="conn">
            Status: <span :class="statusClass">{{ statusText }}</span>
          </div>
          <div class="row gap stretch">
            <button
              v-if="!isOpen"
              class="btn primary full"
              @click="handleUserConnect"
            >
              Connect
            </button>
            <button
              v-else
              class="btn danger full"
              @click="handleUserDisconnect"
            >
              Disconnect
            </button>
          </div>
          <div class="joined-pill" v-if="joined">#{{ currentRoom }}</div>
        </div>
        <div class="panel presence" v-if="joined">
          <div class="presence-head">Users ({{ users.length }})</div>
          <ul>
            <li v-for="u in users" :key="u" :class="{ self: u === myUsername }">
              <span class="name">{{ u }}</span>
              <span
                v-if="typingUsers[u]"
                class="typing-dot"
                title="typing"
              ></span>
            </li>
          </ul>
        </div>
      </aside>
      <div class="main-pane">
        <header class="room-bar-top" v-if="joined">
          <h2>#{{ currentRoom }}</h2>
        </header>
        <div v-else class="empty-room-hint">
          <h2>Welcome to FastRoom ⚡</h2>
          <p class="tag">
            You're authenticated. You will auto-join the
            <code>{{ DEFAULT_ROOM }}</code> room when the WebSocket connects.
          </p>
          <ul class="quick-tips">
            <li>Realtime messages & presence via WebSocket.</li>
            <li>Automatic reconnection with exponential backoff.</li>
            <li>
              Token refresh won't drop your session instantly (debounced).
            </li>
          </ul>
        </div>

        <ul
          v-if="joined"
          class="messages"
          ref="msgList"
          @scroll.passive="onScrollMessages"
        >
          <li
            v-for="(m, i) in messages"
            :key="m.message_id || i"
            :class="[
              'msg',
              m.type,
              (m.username || m.user) === myUsername ? 'own' : '',
            ]"
          >
            <template v-if="m.type === 'chat'">
              <div class="bubble">
                <div class="meta-row">
                  <span class="user">{{ m.username || m.user }}</span>
                  <span class="time">{{ ts(m.ts) }}</span>
                </div>
                <div class="text">{{ m.message }}</div>
              </div>
            </template>
            <template v-else-if="m.type === 'system'">
              <div class="system-line">• {{ m.message }}</div>
            </template>
          </li>
          <!-- Auto-load sentinel / end-of-history marker (column-reverse so visually top) -->
          <li
            ref="historySentinel"
            class="history-sentinel"
            :class="{
              loading: historyLoading,
              done: !hasMoreHistory && !historyLoading,
            }"
          >
            <div
              v-if="historyLoading"
              class="spinner"
              aria-label="Loading older messages"
            ></div>
            <div v-else-if="hasMoreHistory" class="older-hint">
              Older messages
            </div>
            <div v-else class="end-marker" aria-label="Start of conversation">
              ✦ Start of room ✦
            </div>
          </li>
        </ul>
        <form
          v-if="joined"
          class="compose"
          @submit.prevent="send"
          ref="composeForm"
        >
          <textarea
            ref="composer"
            v-model="draft"
            placeholder="Message... (Enter to send, Shift+Enter for newline)"
            :disabled="!isOpen"
            @keydown.enter="onEnterKey"
            @input="onInputTyping"
            rows="1"
          />
          <div class="actions">
            <button
              type="button"
              class="btn subtle"
              @click="clearDraft"
              :disabled="!draft"
            >
              Clear
            </button>
            <button
              type="submit"
              class="btn primary"
              :disabled="!draft.trim() || sending"
            >
              Send
            </button>
          </div>
        </form>
      </div>
      <!-- Toasts -->
      <transition-group name="toast" tag="div" class="toasts">
        <div v-for="t in toasts" :key="t.id" :class="['toast', t.type]">
          <span class="msg">{{ t.message }}</span>
          <button class="close" @click="dismissToast(t.id)">x</button>
        </div>
      </transition-group>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue';
import { useAuthStore } from '../stores/auth';
import { useAuthedWSClient } from '../utils/useAuthedWSClient';

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
const messages = ref<any[]>([]);
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
const historySentinel = ref<HTMLElement | null>(null);
const composer = ref<HTMLTextAreaElement | null>(null);
const composerBaseHeight = ref<number | null>(null); // baseline single-line height
let historyObserver: IntersectionObserver | null = null;
let lastHistoryLoadAt = 0;
const HISTORY_DEBOUNCE_MS = 600; // prevent rapid duplicate loads

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

let lastJoinedRoom: string | null = null; // remember for auto rejoin after reconnect
function joinDefaultRoom() {
  if (joined.value) return;
  client.send({ type: 'join', room: DEFAULT_ROOM.value } as any);
}

// Auto-switch when parent passes a new roomName
function switchRoom(newRoom: string) {
  if (!newRoom) return;
  if (currentRoom.value === newRoom) return; // no-op
  // Send leave for existing room (if any)
  if (currentRoom.value) {
    try {
      client.send({ type: 'leave', room: currentRoom.value } as any);
    } catch (e) {
      // eslint-disable-next-line no-console
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
      client.send({ type: 'join', room: target } as any);
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
  } as any);
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
    // eslint-disable-next-line no-console
    console.debug(
      '[ChatRoom] sending chat while readyState',
      client.readyState?.(),
      'reconnectAttempts',
      client.getReconnectAttempts?.(),
    );
  }
  client.send({ type: 'chat', room: currentRoom.value, message: text } as any);
  draft.value = '';
  autoResize();
  // Clear sending state shortly (simulate ack); then focus once input is enabled
  setTimeout(() => {
    sending.value = false;
    nextTick(() => composer.value?.focus());
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
function autoResize() {
  const el = composer.value;
  if (!el) return;
  // Establish baseline height once (single line with current styles)
  if (composerBaseHeight.value == null) {
    // Use offsetHeight if already styled, fallback to scrollHeight
    composerBaseHeight.value = el.offsetHeight || el.scrollHeight;
  }
  const base = composerBaseHeight.value;
  // Reset to auto to measure content height
  el.style.height = 'auto';
  const contentHeight = el.scrollHeight;
  // If content fits within (base + small buffer), keep single-line height
  const buffer = 4; // px
  let target =
    contentHeight <= base + buffer ? base : Math.min(200, contentHeight);
  el.style.height = target + 'px';
}

client.onOpen(() => {
  const wasReconnecting =
    connected.value === false && client.getReconnectAttempts() > 0;
  // Auto rejoin previous room (only if not manually disconnected & user had joined before)
  if (!manualDisconnect.value) {
    if (lastJoinedRoom && !currentRoom.value) {
      client.send({ type: 'join', room: lastJoinedRoom } as any);
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
client.onClose((ev?: any) => {
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
client.onJSON((data) => {
  // Basic diagnostic hook (could be gated by dev flag)
  // console.debug('[WS] in', data);
  if (data.type === 'pong') return; // ignore heartbeats
  if (data.type === 'joined') {
    currentRoom.value = data.room;
    lastJoinedRoom = data.room; // remember for next reconnect
    // System line should appear as newest (top) so use unshift not push
    messages.value.unshift({
      type: 'system',
      room: data.room,
      message: 'You joined',
    });
    nextTick(() => composer.value?.focus());
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
        messages.value.unshift(m);
      }
    }
    nextTick(() => ensureHistoryFill());
    return;
  }
  if (data.type === 'history_more') {
    if (Array.isArray(data.messages) && data.messages.length) {
      const list = msgList.value;
      const prevScrollHeight = list?.scrollHeight || 0;
      const prevScrollTop = list?.scrollTop || 0;
      // Append in reverse so internal order stays newest->oldest (descending time)
      for (const m of [...data.messages].reverse()) {
        const id = m.message_id;
        if (typeof id === 'number') {
          if (seenMessageIds.has(id)) continue; // skip duplicates
          seenMessageIds.add(id);
        }
        messages.value.push(m);
      }
      nextTick(() => {
        if (list) {
          const newHeight = list.scrollHeight;
          list.scrollTop = prevScrollTop + (newHeight - prevScrollHeight);
        }
        setupHistoryObserver();
        ensureHistoryFill();
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
    if (data.leave?.length) {
      users.value = users.value.filter((u) => !data.leave.includes(u));
      for (const u of data.leave) delete typingUsers.value[u];
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
      messages.value.unshift({
        type: 'system',
        room: data.room,
        message: `${data.username} ${parts.join(', ')}`,
      });
    }
    return;
  }
  if (data.type === 'system' || data.type === 'chat') {
    const id = data.message_id;
    if (typeof id === 'number' && seenMessageIds.has(id)) return;
    if (typeof id === 'number') seenMessageIds.add(id);
    messages.value.unshift(data);
  } else {
    messages.value.unshift({ type: 'debug', raw: data });
  }
  if (messages.value.length > 500) messages.value.splice(500);
});

onMounted(() => {
  autoResize();
  nextTick(() => {
    if (joined.value) composer.value?.focus();
    // Re-run after focus in case fonts caused late layout
    autoResize();
  });
  // Delay observer until initial messages render
  nextTick(() => setupHistoryObserver());
});
onUnmounted(() => {
  // Prevent lingering reconnect attempts when component is destroyed
  manualDisconnect.value = true;
  if (joined.value && currentRoom.value) {
    // Politely inform server we left (optional; server cleans up on close anyway)
    client.send({ type: 'leave', room: currentRoom.value } as any);
  }
  client.disconnect();
  teardownHistoryObserver();
});

const isOpen = computed(() => connected.value);
const statusText = computed(() => (isOpen.value ? 'OPEN' : 'CLOSED'));
const statusClass = computed(() => (isOpen.value ? 'ok' : 'bad'));

// Auto-scroll
const msgList = ref<HTMLElement | null>(null);
// Initial scroll position at top (newest). No auto-scroll needed for reversed layout.

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
  } as any);
}

function ensureHistoryFill() {
  // If the list doesn't overflow yet and more history exists, keep loading
  const list = msgList.value;
  if (!list) return;
  if (!hasMoreHistory.value) return;
  // If total scrollable height is not larger than view (meaning no scroll bar space), fetch more
  if (list.scrollHeight <= list.clientHeight + 10) {
    // Small delay to avoid tight loop if server returns empty
    setTimeout(() => loadMoreHistory(), 20);
  }
}

function setupHistoryObserver() {
  if (historyObserver) historyObserver.disconnect();
  if (!('IntersectionObserver' in window)) return; // fallback to scroll handler
  const rootEl = msgList.value;
  if (!rootEl) return;
  historyObserver = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (e.isIntersecting) {
          loadMoreHistory();
        }
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

function onScrollMessages(e: Event) {
  if (historyObserver) return; // observer handles it
  const el = e.target as HTMLElement;
  // For column-reverse, the visual top (older) corresponds to scrollTop <= 0
  if (el.scrollTop <= 0 + 4) loadMoreHistory();
}

// Keep textarea height in sync even if programmatic changes happen.
watch(draft, () => autoResize());

function ts(d?: string) {
  if (!d) return '';
  try {
    const dt = new Date(d);
    return dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}
</script>

<style scoped>
.layout {
  display: flex;
  flex-direction: column;
  /* Constrain the chat area to the visible viewport (minus footer) so the internal messages list, not the page, scrolls. */
  /* Adjust the 3rem if your footer height changes; or set --app-footer-h on a parent. */
  --_footer-h: var(--app-footer-h, 3rem);
  height: calc(80vh - var(--_footer-h));
  max-height: calc(80vh - var(--_footer-h));
  /* Prevent children from forcing extra page height */
  min-height: 0;
  background: var(--bg);
  color: var(--text);
  transition:
    background-color 240ms ease,
    color 240ms ease;
}
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.7rem 1.5rem 0.7rem 2.2rem;
  z-index: 10;
}
.navbar-title {
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  color: var(--accent);
}
.navbar-theme {
  display: flex;
  gap: 0.5rem;
}
.content-area {
  display: flex;
  flex: 1;
}
.quick-tips {
  list-style: none;
  padding: 0;
  margin: 0.5rem 0 0;
  font-size: 0.85rem;
  color: var(--sub);
}
.sidebar {
  width: 280px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  min-height: 0;
  transition:
    background 240ms ease,
    border-color 240ms ease,
    color 240ms ease;
}
.main-pane {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  position: relative;
  min-height: 0; /* critical so .messages flex item can shrink and scroll */
  overflow: hidden; /* contain internal scroll (only .messages should scroll) */
}
.room-bar-top {
  padding: 0.25rem 0.5rem 0.75rem;
  border-bottom: 1px solid var(--panel-border);
  margin-bottom: 0.5rem;
}
.room-bar-top h2 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text);
}
.empty-room-hint {
  margin-top: 3rem;
  text-align: center;
  opacity: 0.8;
  color: var(--sub);
}

.panel {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  padding: 0.9rem 0.95rem 0.95rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  transition:
    background 240ms ease,
    border-color 240ms ease,
    color 240ms ease;
}
.panel.head {
  gap: 0.75rem;
}
.presence ul {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 220px;
  overflow: auto;
}
.presence li {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.35rem;
  font-size: 0.8rem;
  border-radius: 6px;
  color: var(--text);
}
.presence li.self {
  background: var(--accent);
  color: var(--accent-fg);
}
.presence-head {
  font-size: 0.75rem;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 600;
  opacity: 0.8;
}
.joined-pill {
  background: var(--accent);
  color: var(--accent-fg);
  padding: 2px 8px;
  border-radius: 16px;
  font-size: 0.65rem;
  display: inline-block;
  margin-top: 0.25rem;
}

.chat {
  color: var(--text);
  background: transparent;
}
.field-label {
  font-size: 0.7rem;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  font-weight: 600;
  opacity: 0.65;
  color: var(--sub);
}
.row {
  display: flex;
}
.gap {
  gap: 0.5rem;
}
.warn {
  color: var(--danger);
  font-size: 0.65rem;
}
.hint {
  font-size: 0.65rem;
  opacity: 0.55;
  color: var(--sub);
}
.current-username {
  font-size: 0.7rem;
  opacity: 0.75;
  color: var(--sub);
}

input {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  padding: 0.55rem 0.65rem;
  font: inherit;
  color: inherit;
  width: 100%;
  transition:
    background 200ms ease,
    border-color 200ms ease;
}
input:focus {
  outline: 2px solid var(--accent);
  outline-offset: 0;
}

.btn {
  font: inherit;
  cursor: pointer;
  border-radius: 6px;
  border: 1px solid var(--panel-border);
  background: var(--panel);
  color: var(--text);
  padding: 0.55rem 0.9rem;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  transition:
    background 200ms ease,
    color 200ms ease,
    border-color 200ms ease;
}
.btn.primary {
  background: var(--accent);
  color: var(--accent-fg);
  border-color: var(--accent);
}
.btn.secondary {
  background: var(--panel);
}
.btn.subtle {
  background: var(--panel);
}
.btn.tiny {
  padding: 0.35rem 0.55rem;
  font-size: 0.65rem;
}
.btn.tiny.active {
  background: var(--accent);
  color: var(--accent-fg);
  border-color: var(--accent);
}
.btn.full {
  width: 100%;
  justify-content: center;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.messages {
  list-style: none;
  padding: 0 0.5rem 0.75rem;
  margin: 0;
  /* Make this the ONLY scrollable region in the vertical stack */
  flex: 1 1 0;
  min-height: 0; /* required in Firefox & Safari so flex child can actually shrink */
  overflow-y: auto;
  display: flex;
  flex-direction: column-reverse; /* newest first visually */
  gap: 0.5rem;
  scrollbar-width: thin;
}
.msg {
  font-size: 0.8rem;
  display: flex;
  flex-direction: row;
}
.msg .bubble {
  max-width: 620px;
  background: var(--panel);
  border: 1px solid var(--panel-border);
  padding: 0.55rem 0.7rem 0.6rem;
  border-radius: 10px;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-right: auto;
  transition:
    background 200ms ease,
    border-color 200ms ease,
    color 200ms ease;
  color: var(--text); /* ensure readable text on white */
}
.msg.own {
  justify-content: flex-end;
}
.msg.own .bubble {
  background: var(--accent);
  color: var(--accent-fg);
  border-color: var(--accent);
  margin-left: auto;
  margin-right: 0;
}
.msg.own .bubble .meta {
  opacity: 0.9;
}
.bubble .meta-row {
  font-size: 0.6rem;
  text-transform: uppercase;
  letter-spacing: 0.75px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  opacity: 0.65;
  color: inherit;
}
.bubble .meta-row .user {
  font-weight: 700;
  font-size: 0.65rem;
  letter-spacing: 0.6px;
  background: rgba(0, 0, 0, 0.08);
  padding: 0.1rem 0.1rem;
  border-radius: 12px;
}
.msg.own .bubble .meta-row .user {
  background: rgba(255, 255, 255, 0.18);
  color: var(--accent-fg);
}
.bubble .meta-row .time {
  font-weight: 500;
  font-size: 0.6rem;
  opacity: 0.85;
}
.bubble .text {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 0.82rem;
  line-height: 1.25;
  color: inherit;
}
.system-line {
  font-size: 0.7rem;
  text-align: center;
  opacity: 0.6;
  letter-spacing: 0.5px;
  color: var(--sub);
}
.error-line {
  font-size: 0.75rem;
  color: var(--danger);
}

.typing-dot {
  width: 8px;
  height: 8px;
  background: var(--accent);
  border-radius: 50%;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%,
  100% {
    transform: scale(0.6);
    opacity: 0.4;
  }
  50% {
    transform: scale(1);
    opacity: 1;
  }
}

.status .ok {
  color: var(--ok);
}
.status .bad {
  color: var(--danger);
}

.compose {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
  padding: 0.65rem 0.5rem 0.75rem;
  background: var(--bg);
  border-top: 1px solid var(--panel-border);
}
.compose textarea {
  flex: 1;
  resize: none;
  max-height: 200px;
  min-height: 42px;
  line-height: 1.3;
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  padding: 0.5rem 0.5rem;
  font: inherit;
  color: inherit;
}
.compose textarea:focus {
  outline: 2px solid var(--accent);
}
.compose .actions {
  display: flex;
  gap: 0.5rem;
}
.toasts {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  z-index: 1000;
}
.toast {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 10px;
  padding: 0.65rem 0.85rem;
  font-size: 0.75rem;
  min-width: 200px;
  max-width: 320px;
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  box-shadow:
    0 4px 20px -4px rgba(0, 0, 0, 0.35),
    0 2px 6px rgba(0, 0, 0, 0.25);
  animation: slideIn 0.35s ease;
  transition:
    background 240ms ease,
    border-color 240ms ease,
    color 240ms ease;
}
.toast.error {
  border-color: var(--danger);
}
.toast .msg {
  flex: 1;
  line-height: 1.2;
}
.toast .close {
  background: transparent;
  border: none;
  color: inherit;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0 0.25rem;
}
@keyframes slideIn {
  from {
    transform: translateY(8px) scale(0.95);
    opacity: 0;
  }
  to {
    transform: translateY(0) scale(1);
    opacity: 1;
  }
}
.toast-leave-active {
  transition: all 0.25s ease;
}
.toast-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.95);
}

::-webkit-scrollbar {
  width: 10px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.35);
}

@media (max-width: 960px) {
  .layout {
    flex-direction: column;
  }
  .navbar {
    padding-left: 1rem;
    padding-right: 1rem;
  }
  .content-area {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }
  .main-pane {
    height: auto;
    min-height: 60vh;
  }
}

.history-sentinel {
  display: flex;
  justify-content: center;
  padding: 0.5rem 0 0.25rem;
  font-size: 0.65rem;
  opacity: 0.7;
  min-height: 32px;
  align-items: center;
}
.history-sentinel .older-hint {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  padding: 0.25rem 0.6rem;
  border-radius: 12px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
}
.history-sentinel.loading .older-hint {
  display: none;
}
.history-sentinel.done {
  opacity: 0.9;
}
.end-marker {
  background: linear-gradient(135deg, var(--panel), var(--panel-border));
  border: 1px solid var(--panel-border);
  padding: 0.3rem 0.75rem;
  border-radius: 14px;
  font-size: 0.6rem;
  letter-spacing: 1px;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  white-space: nowrap;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.25);
}
.spinner {
  width: 18px;
  height: 18px;
  border: 3px solid rgba(255, 255, 255, 0.22);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
