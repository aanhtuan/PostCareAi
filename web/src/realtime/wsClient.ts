// Một kết nối WebSocket mỗi tab; tự kết nối lại theo exponential backoff (F18 R9).
export type WsMessage = { type: string; payload: unknown; sent_at: string };
export type WsStatus = 'connecting' | 'open' | 'reconnecting';

const BACKOFF_MIN_MS = 1000;
const BACKOFF_MAX_MS = 15000;
const PING_MS = 20000;
export const CLOSE_UNAUTHORIZED = 4401;
// Không còn là nhân viên (đổi vai trò sang FAMILY…): không thử lại, định tuyến theo vai trò mới.
export const CLOSE_FORBIDDEN = 4403;

type Handlers = {
  onMessage: (msg: WsMessage) => void;
  onStatus: (status: WsStatus) => void;
  onReconnected: () => void;
  onUnauthorized: () => void;
  onForbidden: () => void;
};

export function wsUrl(token: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/v1/ws?token=${encodeURIComponent(token)}`;
}

export class RealtimeClient {
  private ws: WebSocket | null = null;
  private retry = 0;
  private stopped = false;
  private everOpened = false;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private ping: ReturnType<typeof setInterval> | null = null;
  private readonly token: string;
  private readonly handlers: Handlers;

  constructor(token: string, handlers: Handlers) {
    this.token = token;
    this.handlers = handlers;
  }

  start(): void {
    this.stopped = false;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    if (this.ping) clearInterval(this.ping);
    this.ws?.close();
    this.ws = null;
  }

  private connect(): void {
    this.handlers.onStatus(this.everOpened ? 'reconnecting' : 'connecting');
    const ws = new WebSocket(wsUrl(this.token));
    this.ws = ws;
    ws.onopen = () => {
      const wasReconnect = this.everOpened;
      this.everOpened = true;
      this.retry = 0;
      this.handlers.onStatus('open');
      // Kết nối lại: refetch thay vì giả định không bỏ lỡ gì (api-conventions.md).
      if (wasReconnect) this.handlers.onReconnected();
      this.ping = setInterval(() => ws.send(JSON.stringify({ type: 'ping' })), PING_MS);
    };
    ws.onmessage = (e: MessageEvent<string>) => {
      try {
        this.handlers.onMessage(JSON.parse(e.data) as WsMessage);
      } catch {
        /* bỏ qua message lạ */
      }
    };
    ws.onclose = (e: CloseEvent) => {
      if (this.ping) clearInterval(this.ping);
      if (this.stopped) return;
      if (e.code === CLOSE_UNAUTHORIZED) {
        this.handlers.onUnauthorized();
        return;
      }
      if (e.code === CLOSE_FORBIDDEN) {
        this.handlers.onForbidden();
        return;
      }
      this.handlers.onStatus('reconnecting');
      const delay = Math.min(BACKOFF_MAX_MS, BACKOFF_MIN_MS * 2 ** this.retry);
      this.retry += 1;
      this.timer = setTimeout(() => this.connect(), delay);
    };
  }
}
