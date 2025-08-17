import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import {
  loginForAccessTokenTokenPost,
  refreshTokensRefreshPost,
  registerUserRegisterPost,
  readUsersMeUsersMeGet,
  logoutLogoutPost,
} from '../generated/openapiclient/sdk.gen';
import type {
  BodyLoginForAccessTokenTokenPost,
  User,
  TokenPair,
} from '../generated/openapiclient/types.gen';

const ACCESS_KEY = 'fastroom.access';
const REFRESH_KEY = 'fastroom.refresh';

export const useAuthStore = defineStore('auth', () => {
  const access = ref<string | null>(localStorage.getItem(ACCESS_KEY));
  const refresh = ref<string | null>(localStorage.getItem(REFRESH_KEY));
  const user = ref<User | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);

  function setTokens(tp: TokenPair) {
    access.value = tp.access_token;
    refresh.value = tp.refresh_token;
    localStorage.setItem(ACCESS_KEY, tp.access_token);
    localStorage.setItem(REFRESH_KEY, tp.refresh_token);
  }
  function clear() {
    access.value = null;
    refresh.value = null;
    user.value = null;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }

  async function register(
    username: string,
    password: string,
    email?: string,
    fullName?: string,
  ) {
    loading.value = true;
    error.value = null;
    try {
      await registerUserRegisterPost({
        query: { username, password, email, full_name: fullName },
      });
      // auto login
      await login(username, password);
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'registration failed';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function login(username: string, password: string) {
    loading.value = true;
    error.value = null;
    try {
      const body: BodyLoginForAccessTokenTokenPost = {
        username,
        password,
        grant_type: 'password',
      };
      const res = await loginForAccessTokenTokenPost({ body });
      const tokenPair = res.data;
      if (!tokenPair) {
        throw new Error('No token pair returned');
      }
      setTokens(tokenPair);
      await fetchProfile();
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : 'login failed';
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function refreshTokens() {
    if (!refresh.value) return;
    try {
      const res = await refreshTokensRefreshPost({
        body: { refresh_token: refresh.value },
      });
      if (res.data) setTokens(res.data);
    } catch (e) {
      console.error('Refresh token failed:', e);
      clear();
    }
  }

  async function fetchProfile() {
    if (!access.value) return;
    try {
      const res = await readUsersMeUsersMeGet();
      if (!res.data) {
        throw new Error('No user data returned');
      }
      user.value = res.data;
    } catch (e) {
      console.error('Fetch profile failed:', e);
      // maybe expired; try refresh
      await refreshTokens();
      if (access.value) {
        const res2 = await readUsersMeUsersMeGet();
        if (!res2.data) {
          throw new Error('No user data returned after refresh');
        }
        user.value = res2.data;
      }
    }
  }

  async function logout() {
    if (refresh.value) {
      try {
        await logoutLogoutPost({
          body: { refresh_token: refresh.value },
        });
      } catch {
        // ignore errors (token may already be invalid)
      }
    }
    clear();
  }

  const isAuthed = computed(() => !!access.value && !!user.value);

  return {
    access,
    refresh,
    user,
    loading,
    error,
    isAuthed,
    register,
    login,
    fetchProfile,
    refreshTokens,
    logout,
    clear,
  };
});
