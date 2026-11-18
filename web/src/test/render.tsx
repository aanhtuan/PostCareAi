import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';

import type { UserOut } from '../api/types';
import { AuthContext, type AuthState } from '../auth/AuthContext';
import { RealtimeContext } from '../realtime/status';
import type { WsStatus } from '../realtime/wsClient';

export function renderWithProviders(
  ui: ReactElement,
  user: UserOut,
  route = '/',
  authOverrides: Partial<AuthState> = {},
  opts: { ws?: WsStatus; qc?: QueryClient } = {},
) {
  const qc = opts.qc ?? new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const auth: AuthState = {
    user,
    token: 'test-token',
    loading: false,
    canWrite: user.role !== 'DOCTOR',
    login: async () => {},
    logout: () => {},
    reloadUser: () => {},
    ...authOverrides,
  };
  const result = render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[route]}>
          <AuthContext.Provider value={auth}>
            <RealtimeContext.Provider value={opts.ws ?? 'connecting'}>
              {ui}
            </RealtimeContext.Provider>
          </AuthContext.Provider>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
  return { ...result, qc };
}

/** QueryClient cho test cần đẩy message WebSocket giả qua `applyMessage`. */
export function testQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

/** Mock fetch theo đường dẫn API: `{ '/api/v1/overview': {...} }`. */
export function mockFetch(routes: Record<string, unknown>) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString();
    const path = url.split('?')[0];
    if (!(path in routes)) return new Response('{}', { status: 404 });
    return new Response(JSON.stringify(routes[path]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  });
  globalThis.fetch = fn as unknown as typeof fetch;
  return fn;
}
