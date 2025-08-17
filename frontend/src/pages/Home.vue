<template>
  <div class="page home">
    <h1 class="logo-heading">
      <img class="logo" src="/fastroom-logo.svg" alt="FastRoom logo" />
      FastRoom
    </h1>
    <p>A lightweight realtime chat demo.</p>
    <div class="actions">
      <RouterLink
        v-if="!auth.isAuthed"
        class="btn primary"
        :to="{ name: 'login' }"
        >Get Started</RouterLink
      >
      <RouterLink
        v-if="auth.isAuthed"
        class="btn primary"
        :to="{ name: 'rooms' }"
        >Enter Rooms</RouterLink
      >
    </div>
  </div>
</template>
<script setup lang="ts">
import { useAuthStore } from '../stores/auth';
const auth = useAuthStore();
</script>
<style scoped>
.home {
  padding: 2rem 1.5rem;
}
.logo-heading {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 2.2rem;
  letter-spacing: 0.5px;
}
.logo {
  width: 48px;
  height: 48px;
}
.actions {
  margin-top: 1.25rem;
  display: flex;
  gap: 1rem;
}
.btn {
  text-decoration: none;
  color: var(--accent-fg);
  background: var(--accent);
  border-radius: 6px;
  padding: 0.5rem 0.8rem;
}
</style>
