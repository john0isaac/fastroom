import { useAuthStore } from '../stores/auth';
import { client } from '../generated/openapiclient/client.gen';
import { AxiosHeaders } from 'axios';
import type {
  AxiosError,
  InternalAxiosRequestConfig,
  AxiosRequestHeaders,
} from 'axios';

let installed = false;
export function installAuthInterceptors() {
  if (installed) return;
  installed = true;
  const auth = useAuthStore();
  client.instance.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
      if (auth.access) {
        if (!config.headers) {
          config.headers = new AxiosHeaders();
        }
        if (config.headers instanceof AxiosHeaders) {
          config.headers.set('Authorization', `Bearer ${auth.access}`);
        } else {
          // Convert raw headers object to AxiosHeaders then set
          const h = new AxiosHeaders(config.headers as AxiosRequestHeaders);
          h.set('Authorization', `Bearer ${auth.access}`);
          config.headers = h;
        }
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
            if (!cfg.headers) {
              cfg.headers = new AxiosHeaders();
            }
            if (cfg.headers instanceof AxiosHeaders) {
              cfg.headers.set('Authorization', `Bearer ${auth.access}`);
            } else {
              const h = new AxiosHeaders(cfg.headers as AxiosRequestHeaders);
              h.set('Authorization', `Bearer ${auth.access}`);
              cfg.headers = h;
            }
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
