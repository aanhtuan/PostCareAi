import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RealtimeClient, wsUrl, type WsStatus } from './wsClient';

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    /* client tự đóng: không phát onclose trong test */
  }
  open() {
    this.onopen?.();
  }
  serverClose(code: number) {
    this.onclose?.({ code });
  }
}

function makeClient() {
  const h = {
    onMessage: vi.fn(),
    onStatus: vi.fn<(s: WsStatus) => void>(),
    onReconnected: vi.fn(),
    onUnauthorized: vi.fn(),
    onForbidden: vi.fn(),
  };
  const client = new RealtimeClient('tok', h);
  client.start();
  return { client, h };
}

const last = () => FakeWebSocket.instances[FakeWebSocket.instances.length - 1];

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.useFakeTimers();
  vi.stubGlobal('WebSocket', FakeWebSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('RealtimeClient', () => {
  it('connects with the token in the query', () => {
    makeClient();
    expect(last().url).toBe(wsUrl('tok'));
    expect(last().url).toContain('/api/v1/ws?token=tok');
  });

  it('reconnects with backoff after close', () => {
    const { h } = makeClient();
    last().serverClose(1006);
    expect(h.onStatus).toHaveBeenLastCalledWith('reconnecting');
    vi.advanceTimersByTime(999);
    expect(FakeWebSocket.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(2);
    last().serverClose(1006); // lần 2: 2 s
    vi.advanceTimersByTime(1999);
    expect(FakeWebSocket.instances).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(FakeWebSocket.instances).toHaveLength(3);
  });

  it('caps backoff and resets it after a successful open', () => {
    makeClient();
    for (let i = 0; i < 10; i += 1) {
      last().serverClose(1006);
      vi.advanceTimersByTime(15000);
    }
    const n = FakeWebSocket.instances.length;
    expect(n).toBe(11); // mỗi lần chờ tối đa 15 s
    last().open();
    last().serverClose(1006);
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(n + 1);
  });

  it('invalidates queries after reconnect', () => {
    const { h } = makeClient();
    last().open();
    expect(h.onReconnected).not.toHaveBeenCalled(); // lần đầu không cần refetch
    expect(h.onStatus).toHaveBeenLastCalledWith('open');
    last().serverClose(1006);
    vi.advanceTimersByTime(1000);
    last().open();
    expect(h.onReconnected).toHaveBeenCalledTimes(1);
  });

  it('does not retry after 4401', () => {
    const { h } = makeClient();
    last().open();
    last().serverClose(4401);
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(h.onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not retry after 4403', () => {
    const { h } = makeClient();
    last().open();
    last().serverClose(4403);
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(h.onForbidden).toHaveBeenCalledTimes(1);
    expect(h.onUnauthorized).not.toHaveBeenCalled();
  });

  it('reconnects after the server drops a slow client (1013)', () => {
    makeClient();
    last().open();
    last().serverClose(1013);
    vi.advanceTimersByTime(1000);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it('sends ping periodically while open', () => {
    makeClient();
    last().open();
    vi.advanceTimersByTime(20000);
    expect(last().sent).toEqual([JSON.stringify({ type: 'ping' })]);
    last().serverClose(1006);
    const ws = FakeWebSocket.instances[0];
    vi.advanceTimersByTime(40000);
    expect(ws.sent).toHaveLength(1); // ngừng ping khi đã đóng
  });

  it('parses messages and ignores malformed ones', () => {
    const { h } = makeClient();
    last().open();
    last().onmessage?.({ data: 'không phải JSON' });
    last().onmessage?.({
      data: JSON.stringify({ type: 'bed.state', payload: {}, sent_at: 'x' }),
    });
    expect(h.onMessage).toHaveBeenCalledTimes(1);
    expect(h.onMessage.mock.calls[0][0].type).toBe('bed.state');
  });

  it('stop() prevents further reconnects', () => {
    const { client } = makeClient();
    client.stop();
    last().serverClose(1006);
    vi.advanceTimersByTime(60000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
