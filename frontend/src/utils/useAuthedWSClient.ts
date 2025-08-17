import { ref, watch, onMounted } from 'vue';
import { useAuthStore } from '../stores/auth';
import { WSClient, type WSClientOptions } from './wsClient';

export interface UseAuthedWSClientOptions extends WSClientOptions {
  /** Attempt to connect automatically on mount if a token is present (default true). */
  connectOnMount?: boolean;
}

function buildWsUrl(baseUrl: string, access?: string | null) {
  try {
    const url = new URL(baseUrl, window.location.href);
    if (access) url.searchParams.set('access_token', access);
    return url.toString();
  } catch {
    if (access) {
      const joiner = baseUrl.includes('?') ? '&' : '?';
      return `${baseUrl}${joiner}access_token=${encodeURIComponent(access)}`;
    }
    return baseUrl;
  }
}

export function useAuthedWSClient(
  baseUrl: string,
  opts: UseAuthedWSClientOptions = {},
) {
  const auth = useAuthStore();
  const { connectOnMount = true, ...wsOpts } = opts;

  // We deliberately disable autoConnect here; lifecycle handled manually.
  const client = new WSClient(buildWsUrl(baseUrl, auth.access), {
    ...wsOpts,
    autoConnect: false,
  });

  const connected = ref(false);
  const manualDisconnect = ref(false);
  const pendingUrl = ref<string | null>(null); // defer URL swap until next reconnect

  function connect() {
    manualDisconnect.value = false;
    client.setUrl(buildWsUrl(baseUrl, auth.access), false);
    client.connect();
  }
  function disconnect() {
    manualDisconnect.value = true;
    client.disconnect();
  }

  client.onOpen(() => {
    connected.value = true;
  });
  client.onClose(() => {
    connected.value = false;
  });

  // Sync URL + connection with token changes
  watch(
    () => auth.access,
    (newToken, oldToken) => {
      if (newToken && newToken !== oldToken) {
        const newUrl = buildWsUrl(baseUrl, newToken);
        if (connected.value) {
          // Defer until socket naturally reconnects / closes
          pendingUrl.value = newUrl;
        } else {
          client.setUrl(newUrl);
        }
      } else if (!newToken && oldToken) {
        // Lost auth -> disconnect immediately
        client.disconnect();
      }
    },
  );

  // When the socket closes (and auto reconnect triggers), apply any pending URL
  client.onClose(() => {
    if (pendingUrl.value) {
      client.setUrl(pendingUrl.value, false); // update internal URL without forcing extra disconnect
      pendingUrl.value = null;
    }
  });

  onMounted(() => {
    if (connectOnMount && auth.access) connect();
  });

  return { client, connect, disconnect, connected, manualDisconnect };
}
