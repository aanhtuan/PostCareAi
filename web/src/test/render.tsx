import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router';

import type { UserOut } from '../api/types';
import { AuthContext, type AuthState } from '../auth/AuthContext';

export function renderWithProviders(
  ui: ReactElement,
  user: UserOut,
  route = '/',
  authOverrides: Partial<AuthState> = {},
) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const auth: AuthState = {
    user,
    token: 'test-token',
    loading: false,
    canWrite: user.role !== 'DOCTOR',
    login: async () => {},
    logout: () => {},
    ...authOverrides,
  };
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[route]}>
          <AuthContext.Provider value={auth}>{ui}</AuthContext.Provider>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
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
