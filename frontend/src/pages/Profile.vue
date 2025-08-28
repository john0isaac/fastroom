<template>
  <div v-if="auth.user" class="p-6">
    <h1 class="text-2xl font-semibold mb-4">Profile</h1>
    <div
      class="rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4 text-neutral-900 dark:text-neutral-100"
    >
      <p><strong>Username:</strong> {{ auth.user.username }}</p>
      <p><strong>Email:</strong> {{ auth.user.email }}</p>
      <p><strong>Full Name:</strong> {{ auth.user.full_name }}</p>
      <p><strong>Active:</strong> {{ auth.user.disabled }}</p>
      <p class="break-words">
        <strong>Access Token:</strong> {{ auth.access }}
      </p>
      <p class="break-words">
        <strong>Refresh Token:</strong> {{ auth.refresh }}
      </p>
    </div>
  </div>
  <div v-else class="p-6"><p>Loading…</p></div>
</template>
<script setup lang="ts">
import { useAuthStore } from '../stores/auth';
const auth = useAuthStore();
if (!auth.user && auth.access) {
  auth.fetchProfile();
}
</script>
