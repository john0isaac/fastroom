import { useAuthStore } from '../stores/auth';
import { client } from '../generated/openapiclient/client.gen';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

let installed = false;
export function installAuthInterceptors() {
  if (installed) return;
  installed = true;
  const auth = useAuthStore();
  client.instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      if (auth.access) {
        (config.headers as any) = config.headers || {};
        (config.headers as any).Authorization = `Bearer ${auth.access}`;
      }
      return config;
    },
  );
  client.instance.interceptors.response.use(
    (res) => res,
    async (error: AxiosError) => {
      if (error.response?.status === 401) {
        try {
          await auth.refreshTokens();
          if (auth.access) {
            const cfg = error.config! as InternalAxiosRequestConfig;
            (cfg.headers as any).Authorization = `Bearer ${auth.access}`;
            return client.instance(cfg);
          }
        } catch {
          auth.clear();
        }
      }
      throw error;
    },
  );
}
