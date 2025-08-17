<template>
  <div class="page auth">
    <h1>Register</h1>
    <form class="card" @submit.prevent="submit">
      <label>Username<input v-model="username" required /></label>
      <label
        >Password<input
          v-model="password"
          type="password"
          required
          minlength="6"
      /></label>
      <label>Email (optional)<input v-model="email" type="email" /></label>
      <label>Full Name (optional)<input v-model="fullName" /></label>
      <button class="btn primary" :disabled="auth.loading">
        Create Account
      </button>
      <p v-if="auth.error" class="err">{{ auth.error }}</p>
    </form>
    <p class="alt">
      Have an account? <RouterLink :to="{ name: 'login' }">Login</RouterLink>
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
<style scoped>
.auth {
  padding: 2rem 1.5rem;
  max-width: 420px;
}
.card {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  background: var(--panel);
  border: 1px solid var(--panel-border);
  padding: 1rem;
  border-radius: 10px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--sub);
}
input {
  padding: 0.55rem 0.65rem;
  border: 1px solid var(--panel-border);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text);
}
.btn {
  padding: 0.6rem 0.9rem;
  background: var(--accent);
  color: var(--accent-fg);
  border-radius: 6px;
  border: none;
}
.err {
  color: var(--danger);
  font-size: 0.75rem;
}
.alt {
  margin-top: 1rem;
  font-size: 0.8rem;
}
</style>
