import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it } from 'vitest';

import { App } from './App';
import { AuthProvider } from './auth/AuthContext';
import { vi as text } from './i18n/vi';

function renderApp(route = '/') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MantineProvider>
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider>
            <App />
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    </MantineProvider>,
  );
}

describe('App', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('App renders Vietnamese title', async () => {
    renderApp('/');
    expect(await screen.findByText(text.app.name)).toBeInTheDocument();
    expect(screen.getByText(text.app.tagline)).toBeInTheDocument();
  });

  it('does not show internal codes on the landing page', async () => {
    renderApp('/');
    await screen.findByText(text.app.name);
    expect(document.body.textContent ?? '').not.toMatch(/\b[A-Z]+(?:_[A-Z]+)+\b/);
  });
});
