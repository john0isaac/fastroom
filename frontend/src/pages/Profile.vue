<template>
  <div class="page profile" v-if="auth.user">
    <h1>Profile</h1>
    <div class="card">
      <p><strong>Username:</strong> {{ auth.user.username }}</p>
      <p><strong>Email:</strong> {{ auth.user.email }}</p>
      <p><strong>Full Name:</strong> {{ auth.user.full_name }}</p>
      <p><strong>Active:</strong> {{ auth.user.disabled }}</p>
      <p><strong>Access Token:</strong> {{ auth.access }}</p>
      <p><strong>Refresh Token:</strong> {{ auth.refresh }}</p>
    </div>
  </div>
  <div v-else class="page"><p>Loading…</p></div>
</template>
<script setup lang="ts">
import { useAuthStore } from '../stores/auth';
const auth = useAuthStore();
if (!auth.user && auth.access) {
  auth.fetchProfile();
}
</script>
<style scoped>
.profile {
  padding: 2rem 1.5rem;
}
.card {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  padding: 1rem 1.25rem;
  border-radius: 10px;
  color: var(--text);
}
.card p {
  word-break: break-word;
}
</style>
