<template>
  <main>
    <header class="app-bar">
      <div class="brand">
        <img class="logo" src="/fastroom-logo.svg" alt="FastRoom logo" />
        FastRoom
      </div>
      <div class="tagline">Lightweight realtime chat demo</div>
      <nav class="nav-links">
        <RouterLink to="/">Home</RouterLink>
        <RouterLink to="/rooms">Rooms</RouterLink>
        <RouterLink to="/profile">Profile</RouterLink>
      </nav>
      <div class="auth-area">
        <span v-if="auth.isAuthed" class="welcome"
          >Welcome, {{ auth.user?.username }}</span
        >
        <button v-if="auth.isAuthed" class="btn subtle" @click="doLogout">
          Logout
        </button>
        <RouterLink v-else to="/login" class="btn subtle">Login</RouterLink>
      </div>
      <button class="theme-toggle" @click="cycleTheme">
        <span v-if="theme === 'light'">🌞</span>
        <span v-else-if="theme === 'dark'">🌙</span>
        <span v-else>🌓</span>
      </button>
    </header>
    <RouterView />
    <footer class="foot">
      <span>FastRoom • Demo</span>
      <span class="hint">Redis + FastAPI + WebSocket</span>
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

<style>
:root[data-theme='dark'] {
  --bg: #121417;
  --panel: #1e2227;
  --panel-border: #2b3138;
  --text: #e6eaf0;
  --sub: #9aa4b2;
  --accent: #4f8bff;
  --accent-fg: #fff;
  --danger: #ff4f4f;
  --ok: #3ecf7a;
  --warn: #ffb347;
  --app-bar-bg: linear-gradient(90deg, #222, #303a52);
  --app-bar-fg: #fff;
  --foot-bg: #111;
  --foot-fg: #bbb;
}
:root[data-theme='light'] {
  --bg: #f5f7fb;
  --panel: #ffffff;
  --panel-border: #d9e0e7;
  --text: #1b2430;
  --sub: #5a6876;
  --accent: #2266dd;
  --accent-fg: #fff;
  --danger: #c62828;
  --ok: #1b7f1b;
  --warn: #c96b00;
  --app-bar-bg: linear-gradient(90deg, #ffffff, #e9edf3);
  --app-bar-fg: var(--text);
  --foot-bg: var(--panel);
  --foot-fg: var(--sub);
}

html,
body {
  height: 100%;
  background: var(--bg);
  color: var(--text);
  transition:
    background-color 240ms ease,
    color 240ms ease;
}

main {
  padding: 0 0 3rem;
  font-family:
    system-ui,
    -apple-system,
    Segoe UI,
    Roboto,
    Helvetica,
    Arial,
    sans-serif;
}
.logo {
  width: 48px;
  height: 48px;
}
/* Logo color adaptation: base SVG is black; invert to white in dark mode */
:root[data-theme='dark'] .logo {
  filter: invert(1) brightness(1.1);
}
:root[data-theme='light'] .logo {
  filter: none;
}
.app-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.9rem 1.4rem;
  background: var(--app-bar-bg);
  color: var(--app-bar-fg);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.12);
  position: sticky;
  top: 0;
  z-index: 10;
  transition:
    background 240ms ease,
    color 240ms ease;
}
.theme-toggle {
  margin-left: auto;
  background: none;
  border: none;
  color: var(--app-bar-fg);
  font-size: 1.25rem;
  cursor: pointer;
  padding: 0 0.5rem;
  transition: filter 0.15s;
}
.theme-toggle:hover {
  filter: brightness(1.15);
}
.brand {
  font-weight: 600;
  font-size: 1.15rem;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.tagline {
  font-size: 0.8rem;
  opacity: 0.8;
  color: var(--app-bar-fg);
}
.nav-links {
  display: flex;
  gap: 1rem;
  margin-left: auto;
}
.nav-links a {
  color: var(--app-bar-fg);
  text-decoration: none;
  font-size: 0.85rem;
  opacity: 0.85;
}
.nav-links a.router-link-active {
  font-weight: 600;
  opacity: 1;
}
/* Auth area in header */
.auth-area {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.auth-area .welcome {
  font-size: 0.9rem;
  opacity: 0.95;
}
.btn.subtle {
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.06);
  color: var(--app-bar-fg);
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
}
.foot {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  padding: 0.4rem 0.9rem;
  font-size: 0.7rem;
  background: var(--foot-bg);
  color: var(--foot-fg);
  letter-spacing: 0.5px;
  transition:
    background 240ms ease,
    color 240ms ease;
}

/* Ensure general links use accent color and have sufficient contrast */
a {
  color: var(--accent);
}
</style>
