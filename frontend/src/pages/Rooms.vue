<template>
  <div class="p-6">
    <header class="flex items-center gap-6 mb-4">
      <h1 class="text-2xl font-semibold flex items-center gap-3">
        Rooms
        <button
          type="button"
          class="inline-flex items-center justify-center h-8 w-8 rounded-full bg-indigo-600 text-white shadow-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          aria-label="Create room"
          title="Create room"
          @click="openCreateModal"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            class="h-5 w-5"
          >
            <path
              fill-rule="evenodd"
              d="M10 3a1 1 0 0 1 1 1v5h5a1 1 0 1 1 0 2h-5v5a1 1 0 1 1-2 0v-5H4a1 1 0 1 1 0-2h5V4a1 1 0 0 1 1-1Z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </h1>
    </header>

    <!-- Create Room Modal -->
    <div
      v-if="showCreateModal"
      class="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div class="absolute inset-0 bg-black/50" @click="closeCreateModal"></div>
      <div
        class="relative bg-white dark:bg-neutral-900 rounded-lg shadow-xl w-full max-w-md p-5"
        role="dialog"
        aria-modal="true"
        aria-label="Create Room"
      >
        <div class="flex items-center justify-between mb-3">
          <h2 class="text-lg font-medium">Create Room</h2>
          <button
            type="button"
            class="h-8 w-8 inline-flex items-center justify-center rounded-md hover:bg-neutral-100 dark:hover:bg-neutral-800"
            aria-label="Close"
            @click="closeCreateModal"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              class="h-5 w-5"
            >
              <path
                fill-rule="evenodd"
                d="M4.293 4.293a1 1 0 0 1 1.414 0L10 8.586l4.293-4.293a1 1 0 1 1 1.414 1.414L11.414 10l4.293 4.293a1 1 0 0 1-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 0 1-1.414-1.414L8.586 10 4.293 5.707a1 1 0 0 1 0-1.414Z"
                clip-rule="evenodd"
              />
            </svg>
          </button>
        </div>
        <form @submit.prevent="createRoom" class="space-y-4">
          <div>
            <label class="block text-sm mb-1" for="room-name">Room name</label>
            <input
              id="room-name"
              v-model="newRoom"
              placeholder="e.g. general"
              class="w-full rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              autofocus
            />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">Private room</span>
            <button
              type="button"
              role="switch"
              :aria-checked="isPrivate"
              @click="isPrivate = !isPrivate"
              @keydown.enter.prevent="isPrivate = !isPrivate"
              @keydown.space.prevent="isPrivate = !isPrivate"
              class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
              :class="
                isPrivate
                  ? 'bg-indigo-600'
                  : 'bg-neutral-300 dark:bg-neutral-700'
              "
            >
              <span class="sr-only">Toggle private</span>
              <span
                class="inline-block h-5 w-5 transform rounded-full bg-white transition-transform"
                :class="isPrivate ? 'translate-x-5' : 'translate-x-1'"
              />
            </button>
          </div>
          <div class="flex justify-end gap-2">
            <button
              type="button"
              class="px-3 py-2 rounded-md border border-neutral-300 dark:border-neutral-700"
              @click="closeCreateModal"
            >
              Cancel
            </button>
            <button
              class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
              :disabled="!newRoom.trim()"
            >
              Create
            </button>
          </div>
        </form>
      </div>
    </div>
    <ul class="list-none p-0 flex flex-col gap-1">
      <li v-for="r in rooms" :key="r.id" class="flex items-center gap-2">
        <RouterLink
          class="text-indigo-600 hover:underline"
          :to="{ name: 'room', params: { roomName: r.name } }"
          >#{{ r.name }}</RouterLink
        >
        <span
          v-if="r.is_private"
          class="inline-flex items-center text-xs text-neutral-500"
          title="Private room"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            class="h-4 w-4"
          >
            <path
              fill-rule="evenodd"
              d="M10 2a4 4 0 0 0-4 4v2H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-1V6a4 4 0 0 0-4-4Zm2 6V6a2 2 0 1 0-4 0v2h4Z"
              clip-rule="evenodd"
            />
          </svg>
          Private
        </span>
      </li>
    </ul>
    <p v-if="loading">Loading…</p>
  </div>
</template>
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import {
  listRoomsRoomsGet,
  createRoomRoomsPost,
} from '../generated/openapiclient/sdk.gen';
import { Room } from '../generated/openapiclient/types.gen';
const rooms = ref<Room[]>([]);
const loading = ref(false);
const newRoom = ref('');
const isPrivate = ref(false);
const showCreateModal = ref(false);

function openCreateModal() {
  showCreateModal.value = true;
}
function closeCreateModal() {
  showCreateModal.value = false;
}
async function load() {
  loading.value = true;
  const res = await listRoomsRoomsGet();
  rooms.value = res.data?.items || [];
  loading.value = false;
}
async function createRoom() {
  const name = newRoom.value.trim();
  if (!name) return;
  const res = await createRoomRoomsPost({
    body: { name, is_private: isPrivate.value },
  });
  if (!res.data) return;
  rooms.value.unshift(res.data);
  newRoom.value = '';
  isPrivate.value = false;
  closeCreateModal();
}
onMounted(load);
</script>
