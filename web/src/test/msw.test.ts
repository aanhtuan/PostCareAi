// F00 R11: msw được cài và khởi động trong setup.ts với onUnhandledRequest: 'error'.
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from './msw';

describe('msw test server', () => {
  it('serves a handler added in a test', async () => {
    server.use(
      http.get('http://localhost/api/v1/health', () => HttpResponse.json({ status: 'ok' })),
    );
    const res = await fetch('http://localhost/api/v1/health');
    expect(await res.json()).toEqual({ status: 'ok' });
  });

  it('rejects requests without a handler', async () => {
    await expect(fetch('http://localhost/api/v1/khong-co-handler')).rejects.toThrow();
  });

  it('resets handlers between tests', async () => {
    await expect(fetch('http://localhost/api/v1/health')).rejects.toThrow();
  });
});
