<template>
  <div class="p-4">
    <h1 class="text-2xl font-semibold mb-3">#{{ roomName }}</h1>
    <ChatRoom :room-name="roomName" />
  </div>
</template>
<script setup lang="ts">
import ChatRoom from '../components/ChatRoom.vue';
import { useRoute } from 'vue-router';
import { computed } from 'vue';
const route = useRoute();
const roomName = computed(() => route.params.roomName as string);
</script>
