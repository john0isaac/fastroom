<template>
  <main
    class="min-h-screen pb-12 font-sans bg-neutral-50 text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100"
  >
    <header
      class="sticky top-0 z-10 flex items-center gap-2 px-5 py-3 bg-white/80 text-neutral-900 shadow-sm backdrop-blur dark:bg-neutral-900/80 dark:text-neutral-50"
    >
      <div
        class="flex items-center gap-2 font-semibold text-base tracking-wide"
      >
        <img
          class="h-12 w-12 dark:invert dark:brightness-110"
          src="/fastroom-logo.svg"
          alt="FastRoom logo"
        />
        FastRoom
      </div>
      <div class="text-sm opacity-80 ml-2">Lightweight realtime chat demo</div>
      <nav class="ml-auto hidden md:flex items-center gap-4">
        <RouterLink class="text-sm opacity-80 hover:opacity-100" to="/"
          >Home</RouterLink
        >
        <RouterLink class="text-sm opacity-80 hover:opacity-100" to="/rooms"
          >Rooms</RouterLink
        >
        <RouterLink class="text-sm opacity-80 hover:opacity-100" to="/profile"
          >Profile</RouterLink
        >
      </nav>
      <div class="ml-4 flex items-center gap-2">
        <span v-if="auth.isAuthed" class="text-sm opacity-90"
          >Welcome, {{ auth.user?.username }}</span
        >
        <button
          v-if="auth.isAuthed"
          class="inline-flex items-center rounded-md border border-white/10 px-3 py-1 text-sm hover:bg-white/10 dark:border-white/10"
          @click="doLogout"
        >
          Logout
        </button>
        <RouterLink
          v-else
          to="/login"
          class="inline-flex items-center rounded-md border border-black/10 px-3 py-1 text-sm hover:bg-black/5 dark:border-white/10 dark:hover:bg-white/10"
          >Login</RouterLink
        >
        <button
          class="ml-1 inline-flex items-center justify-center rounded-md px-2 py-1 text-lg hover:brightness-110"
          title="Toggle theme"
          @click="cycleTheme"
        >
          <span v-if="theme === 'light'">🌞</span>
          <span v-else-if="theme === 'dark'">🌙</span>
          <span v-else>🌓</span>
        </button>
      </div>
    </header>
    <RouterView />
    <footer
      class="fixed bottom-0 left-0 right-0 flex items-center justify-between px-4 py-2 text-xs bg-neutral-100 text-neutral-600 dark:bg-neutral-900 dark:text-neutral-400"
    >
      <span>FastRoom • Demo</span>
      <span class="opacity-80">Redis + FastAPI + WebSocket</span>
    </footer>
  </main>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useAuthStore } from './stores/auth';
import { useRouter } from 'vue-router';

const auth = useAuthStore();
const router = useRouter();

function doLogout() {
  auth.logout();
  router.replace('/');
}

const THEME_KEY = 'fastroom.theme';
const prefers = window.matchMedia('(prefers-color-scheme: dark)');
const storedTheme = localStorage.getItem(THEME_KEY);
const initialTheme: 'light' | 'dark' | 'auto' =
  storedTheme === 'light' || storedTheme === 'dark' || storedTheme === 'auto'
    ? storedTheme
    : 'auto';
const theme = ref<'light' | 'dark' | 'auto'>(initialTheme);

function applyTheme(t: 'light' | 'dark' | 'auto') {
  if (t === 'auto') {
    document.documentElement.dataset.theme = prefers.matches ? 'dark' : 'light';
  } else {
    document.documentElement.dataset.theme = t;
  }
}

function cycleTheme() {
  if (theme.value === 'light') theme.value = 'dark';
  else if (theme.value === 'dark') theme.value = 'auto';
  else theme.value = 'light';
}

watch(theme, (t) => {
  localStorage.setItem(THEME_KEY, t);
  applyTheme(t);
});
onMounted(() => {
  applyTheme(theme.value);
  prefers.addEventListener('change', () => {
    if (theme.value === 'auto') applyTheme('auto');
  });
});
</script>
