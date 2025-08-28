<template>
  <aside class="w-[280px] flex flex-col gap-4 p-4 min-h-0">
    <div
      class="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 shadow-sm flex flex-col gap-3"
    >
      <div>
        Status: <span :class="statusClass">{{ statusText }}</span>
      </div>
      <div class="flex gap-2">
        <button
          v-if="!isOpen"
          class="w-full inline-flex items-center justify-center rounded-md bg-indigo-600 px-3 py-2 text-sm text-white shadow-sm hover:bg-indigo-500"
          @click="handleUserConnect"
        >
          Connect
        </button>
        <button
          v-else
          class="w-full inline-flex items-center justify-center rounded-md bg-red-600 px-3 py-2 text-sm text-white shadow-sm hover:bg-red-500"
          @click="handleUserDisconnect"
        >
          Disconnect
        </button>
      </div>
      <div
        v-if="joined"
        class="inline-block mt-1 rounded-full bg-indigo-600 text-white text-xs px-2.5 py-0.5"
      >
        #{{ currentRoom || '' }}
      </div>
    </div>
    <div
      v-if="joined"
      class="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 shadow-sm"
    >
      <div
        class="text-xs uppercase tracking-wide font-semibold opacity-80 mb-2"
      >
        Users ({{ users.length }})
      </div>
      <ul class="list-none m-0 p-0 max-h-[220px] overflow-auto">
        <li
          v-for="u in users"
          :key="u"
          :class="[
            'flex items-center gap-2 px-1 py-1 text-sm rounded-md',
            u === myUsername ? 'bg-indigo-600 text-white' : 'text-inherit',
          ]"
        >
          <span>{{ u }}</span>
          <span
            v-if="typingUsers[u]"
            class="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"
            title="typing"
          ></span>
        </li>
      </ul>
    </div>
  </aside>
</template>

<script setup lang="ts">
defineProps<{
  isOpen: boolean;
  joined: boolean;
  users: string[];
  myUsername: string;
  typingUsers: Record<string, boolean>;
  currentRoom: string | null;
  statusText: string;
  statusClass: string;
  handleUserConnect: () => void;
  handleUserDisconnect: () => void;
}>();
</script>
