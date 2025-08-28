<template>
  <div class="p-6 max-w-md">
    <h1 class="text-2xl font-semibold mb-4">Register</h1>
    <form
      class="flex flex-col gap-3 rounded-xl border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-900 p-4"
      @submit.prevent="submit"
    >
      <label
        class="flex flex-col gap-1 text-xs uppercase tracking-wide text-neutral-500"
      >
        Username
        <input
          v-model="username"
          required
          class="rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </label>
      <label
        class="flex flex-col gap-1 text-xs uppercase tracking-wide text-neutral-500"
      >
        Password
        <input
          v-model="password"
          type="password"
          required
          minlength="6"
          class="rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </label>
      <label
        class="flex flex-col gap-1 text-xs uppercase tracking-wide text-neutral-500"
      >
        Email (optional)
        <input
          v-model="email"
          type="email"
          class="rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </label>
      <label
        class="flex flex-col gap-1 text-xs uppercase tracking-wide text-neutral-500"
      >
        Full Name (optional)
        <input
          v-model="fullName"
          class="rounded-md border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-neutral-100 px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
        />
      </label>
      <button
        class="inline-flex items-center justify-center rounded-md bg-indigo-600 px-4 py-2 text-white shadow-sm hover:bg-indigo-500 disabled:opacity-50"
        :disabled="auth.loading"
      >
        Create Account
      </button>
      <p v-if="auth.error" class="text-red-600 text-sm">{{ auth.error }}</p>
    </form>
    <p class="mt-3 text-sm text-neutral-600 dark:text-neutral-300">
      Have an account?
      <RouterLink
        class="text-indigo-600 hover:underline"
        :to="{ name: 'login' }"
        >Login</RouterLink
      >
    </p>
  </div>
</template>
<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/auth';
const auth = useAuthStore();
const username = ref('');
const password = ref('');
const email = ref('');
const fullName = ref('');
const router = useRouter();
async function submit() {
  await auth.register(
    username.value,
    password.value,
    email.value || undefined,
    fullName.value || undefined,
  );
  router.replace('/rooms');
}
</script>
