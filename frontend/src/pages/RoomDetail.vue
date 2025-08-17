<template>
  <div class="page room-detail">
    <h1>#{{ roomName }}</h1>
    <ChatRoom :roomName="roomName" />
  </div>
</template>
<script setup lang="ts">
import ChatRoom from '../components/ChatRoom.vue';
import { useRoute } from 'vue-router';
import { computed } from 'vue';
const route = useRoute();
const roomName = computed(() => route.params.roomName as string);
</script>
<style scoped>
.room-detail {
  padding: 1rem;
}
</style>
