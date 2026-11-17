// F02 R10: client gắn token vào mọi request; 401 → xóa token và về trang đăng nhập.
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { server } from '../test/msw';
import { ApiError, api, setUnauthorizedHandler, tokenStore } from './client';

const UNAUTHORIZED = {
  error: { code: 'UNAUTHORIZED', message: 'Chưa đăng nhập', details: {} },
};

describe('api client', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => setUnauthorizedHandler(null));

  it('attaches the bearer token to every request', async () => {
    tokenStore.set('abc');
    let seen: string | null = null;
    server.use(
      http.get('*/api/v1/overview', ({ request }) => {
        seen = request.headers.get('Authorization');
        return HttpResponse.json({ ok: true });
      }),
    );
    await api('/overview');
    expect(seen).toBe('Bearer abc');
  });

  it('client redirects to login on 401', async () => {
    tokenStore.set('expired');
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    server.use(http.get('*/api/v1/alerts', () => HttpResponse.json(UNAUTHORIZED, { status: 401 })));

    const err = await api('/alerts').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe('UNAUTHORIZED');
    expect(tokenStore.get()).toBeNull();
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not treat a failed login as an expired session', async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    server.use(
      http.post('*/api/v1/auth/login', () =>
        HttpResponse.json(
          { error: { code: 'INVALID_CREDENTIALS', message: 'sai', details: {} } },
          { status: 401 },
        ),
      ),
    );
    const err = await api('/auth/login', { method: 'POST', body: {} }).catch((e: unknown) => e);
    expect((err as ApiError).code).toBe('INVALID_CREDENTIALS');
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('does not redirect on 403', async () => {
    tokenStore.set('abc');
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    server.use(
      http.post('*/api/v1/sessions', () =>
        HttpResponse.json(
          { error: { code: 'FORBIDDEN', message: 'Không đủ quyền', details: {} } },
          { status: 403 },
        ),
      ),
    );
    const err = await api('/sessions', { method: 'POST', body: {} }).catch((e: unknown) => e);
    expect((err as ApiError).status).toBe(403);
    expect(tokenStore.get()).toBe('abc');
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
