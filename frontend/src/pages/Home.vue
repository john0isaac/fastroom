<template>
  <div class="p-6 md:p-8">
    <h1 class="flex items-center gap-2 text-3xl font-semibold tracking-wide">
      <img
        class="h-12 w-12 dark:invert dark:brightness-110"
        src="/fastroom-logo.svg"
        alt="FastRoom logo"
      />
      FastRoom
    </h1>
    <p class="mt-2 text-neutral-600 dark:text-neutral-300">
      A lightweight realtime chat demo.
    </p>
    <div class="mt-5 flex gap-3">
      <RouterLink
        v-if="!auth.isAuthed"
        class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-white shadow-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        :to="{ name: 'login' }"
        >Get Started</RouterLink
      >
      <RouterLink
        v-if="auth.isAuthed"
        class="inline-flex items-center rounded-md bg-indigo-600 px-3 py-2 text-white shadow-sm hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
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
