<template>
  <div class="page rooms">
    <header class="bar">
      <h1>Rooms</h1>
      <form class="create" @submit.prevent="createRoom">
        <input v-model="newRoom" placeholder="new room name" />
        <button class="btn primary" :disabled="!newRoom.trim()">Create</button>
      </form>
    </header>
    <ul class="list">
      <li v-for="r in rooms" :key="r.id">
        <RouterLink :to="{ name: 'room', params: { roomName: r.name } }"
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
import { useAuthStore } from '../stores/auth';
const auth = useAuthStore();
const rooms = ref<any[]>([]);
const loading = ref(false);
const newRoom = ref('');
async function load() {
  loading.value = true;
  const res = await listRoomsRoomsGet({
    headers: { Authorization: `Bearer ${auth.access}` },
  });
  rooms.value = res.data?.items || [];
  loading.value = false;
}
async function createRoom() {
  const name = newRoom.value.trim();
  if (!name) return;
  const res = await createRoomRoomsPost({
    body: { name },
    headers: { Authorization: `Bearer ${auth.access}` },
  } as any);
  rooms.value.unshift(res.data);
  newRoom.value = '';
}
onMounted(load);
</script>
<style scoped>
.rooms {
  padding: 1.5rem;
}
.bar {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  margin-bottom: 1rem;
}
.create {
  display: flex;
  gap: 0.5rem;
}
input {
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text);
}
.list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}
a {
  text-decoration: none;
  color: var(--accent);
}
</style>
