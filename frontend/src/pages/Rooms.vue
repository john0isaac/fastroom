<template>
  <div class="p-6">
    <header class="flex items-center gap-6 mb-4">
      <h1 class="text-2xl font-semibold">Rooms</h1>
      <form class="flex gap-2" @submit.prevent="createRoom">
        <input
          v-model="newRoom"
          placeholder="new room name"
          class="rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
        <button
          class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
          :disabled="!newRoom.trim()"
        >
          Create
        </button>
      </form>
    </header>
    <ul class="list-none p-0 flex flex-col gap-1">
      <li v-for="r in rooms" :key="r.id">
        <RouterLink
          class="text-indigo-600 hover:underline"
          :to="{ name: 'room', params: { roomName: r.name } }"
          >#{{ r.name }}</RouterLink
        >
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
    body: { name },
  });
  if (!res.data) return;
  rooms.value.unshift(res.data);
  newRoom.value = '';
}
onMounted(load);
</script>
