/**
 * Generic JSON message envelope sent over the WebSocket.
 * The server currently only requires a `type` field; `version` is optional.
 */
export type Envelope = {
  version?: number;
  type: string;
  topic?: string;
  msgId?: string;
  payload?: Record<string, unknown>;
  // Allow any extra ad‑hoc fields without casting to any
  [k: string]: unknown;
};

/** Options for WSClient construction and behaviour */
export interface WSClientOptions {
  /** Initial heartbeat interval in ms (will be overridden if server supplies heartbeatInterval). */
  heartbeatIntervalMs?: number;
  /** Maximum reconnect delay in ms (cap). */
  maxReconnectDelayMs?: number;
  /** Maximum number of reconnect attempts (Infinity = no cap). */
  maxReconnectAttempts?: number;
  /** Base reconnect delay in ms (first retry). */
  baseReconnectDelayMs?: number;
  /** Jitter factor (0-1) applied multiplicatively to base delay (default 0.5 meaning 50-100%). */
  jitterRatio?: number;
  /** Whether to automatically start heartbeats (default true). */
  enableHeartbeat?: boolean;
  /** Auto connect immediately (default false). */
  autoConnect?: boolean;
}

type Listener = (data: MessageEvent<string>) => void;
type OpenListener = () => void;
type CloseListener = (ev: CloseEvent) => void;
type ErrorListener = (ev: Event) => void;
type ReconnectListener = (attempt: number, nextDelay: number) => void;

export class WSClient {
  private ws?: WebSocket;
  private msgListeners = new Set<Listener>();
  private openListeners = new Set<OpenListener>();
  private closeListeners = new Set<CloseListener>();
  private errorListeners = new Set<ErrorListener>();
  private heartbeatTimer?: number;
  private hbInterval: number;
  private reconnectAttempts = 0;
  private reconnectTimer?: number;
  private shouldReconnect = true;
  private manualClose = false;
  private reconnectingListeners = new Set<ReconnectListener>();
  private pending: Envelope[] = []; // queue messages until socket OPEN
  private opts: Required<WSClientOptions>;
  jsonListeners = new Set<(data: any) => void>();

  constructor(
    private url: string,
    options: WSClientOptions = {},
  ) {
    this.opts = {
      heartbeatIntervalMs: options.heartbeatIntervalMs ?? 15000,
      maxReconnectDelayMs: options.maxReconnectDelayMs ?? 30000,
      maxReconnectAttempts: options.maxReconnectAttempts ?? Infinity,
      baseReconnectDelayMs: options.baseReconnectDelayMs ?? 1000,
      jitterRatio: options.jitterRatio ?? 0.5,
      enableHeartbeat: options.enableHeartbeat ?? true,
      autoConnect: options.autoConnect ?? false,
    };
    this.hbInterval = this.opts.heartbeatIntervalMs;
    if (this.opts.autoConnect) this.connect();
  }

  /** Register a JSON message listener (already parsed). */
  onJSON(fn: (data: any) => void) {
    this.jsonListeners.add(fn);
    return () => this.jsonListeners.delete(fn);
  }

  /** Register for reconnect attempt notifications (attempt count, planned delay). */
  onReconnecting(fn: ReconnectListener) {
    this.reconnectingListeners.add(fn);
    return () => this.reconnectingListeners.delete(fn);
  }

  /** Update the target URL (will reconnect if currently connected). */
  setUrl(url: string, reconnect = true) {
    if (url === this.url) {
      // No change; skip.
      return;
    }
    this.url = url;
    if (reconnect) {
      if (import.meta.env.DEV) {

        console.debug('[WSClient] setUrl -> reconnect', url);
      }
      this.disconnect();
      this.connect();
    } else if (import.meta.env.DEV) {

      console.debug('[WSClient] setUrl (no immediate reconnect)', url);
    }
  }

  /** Current raw WebSocket readyState (undefined if never created). */
  connect() {
    this.shouldReconnect = true;
    this.manualClose = false;
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING)
    )
      return;
    this._openSocket();
  }

  private _openSocket() {
    if (import.meta.env.DEV) {

      console.debug('[WSClient] opening', this.url);
    }
    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = undefined;
      }
      if (this.opts.enableHeartbeat) this.startHeartbeat();
      this.openListeners.forEach((l) => l());
      // Flush queued messages
      if (this.pending.length) {
        for (const msg of this.pending.splice(0)) {
          try {
            this.ws!.send(JSON.stringify(msg));
          } catch {
            /* ignore */
          }
        }
      }
    };
    this.ws.onmessage = (ev) => {
      this.msgListeners.forEach((l) => l(ev));
      try {
        const data = JSON.parse(ev.data);
        // Adjust heartbeat interval if server suggests one
        if (
          data.heartbeatInterval &&
          typeof data.heartbeatInterval === 'number'
        ) {
          this.hbInterval = data.heartbeatInterval * 1000; // server sends seconds
        }
        this.jsonListeners.forEach((l) => l(data));
      } catch {
        console.error('Failed to parse JSON from WebSocket message:', ev.data);
      }
    };
    this.ws.onclose = (ev) => {
      this.stopHeartbeat();
      this.closeListeners.forEach((l) => l(ev));
      if (!this.manualClose && this.shouldReconnect) {
        this.scheduleReconnect();
      }
      if (import.meta.env.DEV) {

        console.debug('[WSClient] closed', ev.code, ev.reason);
      }
    };
    this.ws.onerror = (e) => {
      this.errorListeners.forEach((l) => l(e));
      if (import.meta.env.DEV) {

        console.debug('[WSClient] error', e);
      }
    };
  }

  private scheduleReconnect() {
    if (this.reconnectAttempts >= this.opts.maxReconnectAttempts) return;
    this.reconnectAttempts += 1;
    const expBackoff =
      this.opts.baseReconnectDelayMs * 2 ** (this.reconnectAttempts - 1);
    const capped = Math.min(this.opts.maxReconnectDelayMs, expBackoff);
    const jitterMin = 1 - this.opts.jitterRatio;
    const jitterMax = 1;
    const jitterFactor = jitterMin + Math.random() * (jitterMax - jitterMin);
    const jitter = capped * jitterFactor;
    const delay = Math.round(jitter);
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectingListeners.forEach((l) => l(this.reconnectAttempts, delay));
    this.reconnectTimer = window.setTimeout(() => {
      this._openSocket();
    }, delay);
    // Optional debug
    // console.debug(`WS reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
  }

  /** Explicitly close and stop auto-reconnect. */
  disconnect() {
    this.shouldReconnect = false;
    this.manualClose = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.close();
    }
  }

  /** Start sending periodic heartbeat pings (internal). */
  private startHeartbeat() {
    this.stopHeartbeat();
    const tick = () => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
        // jitter ±10%
        const jitter = this.hbInterval * (0.9 + Math.random() * 0.2);
        this.heartbeatTimer = window.setTimeout(tick, jitter);
      }
    };
    this.heartbeatTimer = window.setTimeout(tick, this.hbInterval);
  }

  /** Stop heartbeats (internal). */
  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      window.clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
  }

  /** Register a raw message listener (string event). */
  onMessage(fn: Listener) {
    this.msgListeners.add(fn);
    return () => this.msgListeners.delete(fn);
  }
  /** Register an onOpen listener. */
  onOpen(fn: OpenListener) {
    this.openListeners.add(fn);
    return () => this.openListeners.delete(fn);
  }
  /** Register an onClose listener. */
  onClose(fn: CloseListener) {
    this.closeListeners.add(fn);
    return () => this.closeListeners.delete(fn);
  }
  /** Register an onError listener. */
  onError(fn: ErrorListener) {
    this.errorListeners.add(fn);
    return () => this.errorListeners.delete(fn);
  }

  /** Send a raw string (immediately; discarded if socket not OPEN). */
  sendRaw(text: string) {
    this.ws?.send(text);
  }

  /**
   * Send an envelope. If the socket isn't OPEN yet, the message is queued
   * and flushed upon successful connection. Returns true if sent immediately
   * or queued, false if discarded (e.g., closed & auto-reconnect disabled).
   */
  send(obj: Envelope): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(obj));
        return true;
      } catch {
        return false;
      }
    }
    if (this.shouldReconnect) {
      this.pending.push(obj);
      return true;
    }
    return false;
  }

  /** Get current reconnect attempt counter (0 while connected / before first retry). */
  getReconnectAttempts() {
    return this.reconnectAttempts;
  }

  /** Current WebSocket readyState (undefined if never created). */
  readyState() {
    return this.ws?.readyState;
  }
}
