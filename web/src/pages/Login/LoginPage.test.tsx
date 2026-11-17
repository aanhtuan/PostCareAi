import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter, Route, Routes } from 'react-router';
import { beforeEach, describe, expect, it } from 'vitest';

import { tokenStore } from '../../api/client';
import { AuthProvider } from '../../auth/AuthContext';
import { vi as text } from '../../i18n/vi';
import { server } from '../../test/msw';
import { LoginPage } from './LoginPage';

function renderLogin() {
  return render(
    <MantineProvider>
      <MemoryRouter initialEntries={['/login']}>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<p>overview-page</p>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </MantineProvider>,
  );
}

async function fillAndSubmit(username: string, password: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(text.auth.username, { exact: false }), username);
  await user.type(screen.getByLabelText(text.auth.password, { exact: false }), password);
  await user.click(screen.getByRole('button', { name: text.auth.submit }));
}

describe('LoginPage', () => {
  beforeEach(() => localStorage.clear());

  it('renders the Vietnamese login form', () => {
    renderLogin();
    expect(screen.getByRole('heading', { name: text.auth.title })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: text.auth.submit })).toBeInTheDocument();
  });

  it('LoginPage shows error on 401', async () => {
    server.use(
      http.post('*/api/v1/auth/login', () =>
        HttpResponse.json(
          { error: { code: 'INVALID_CREDENTIALS', message: 'x', details: {} } },
          { status: 401 },
        ),
      ),
    );
    renderLogin();
    await fillAndSubmit('nurse', 'sai');
    expect(await screen.findByText(text.auth.invalid)).toBeInTheDocument();
    expect(tokenStore.get()).toBeNull();
    expect(screen.queryByText('overview-page')).not.toBeInTheDocument();
  });

  it('stores the token and goes to the overview after login', async () => {
    server.use(
      http.post('*/api/v1/auth/login', () =>
        HttpResponse.json({
          access_token: 'jwt-abc',
          token_type: 'bearer',
          user: {
            id: 1,
            username: 'nurse',
            full_name: 'Nguyễn Thị Hoa',
            role: 'NURSE',
            is_active: true,
            created_at: '2026-11-17T00:00:00Z',
          },
        }),
      ),
    );
    renderLogin();
    await fillAndSubmit('nurse', 'dung');
    expect(await screen.findByText('overview-page')).toBeInTheDocument();
    expect(tokenStore.get()).toBe('jwt-abc');
  });

  it('returns to the login page when the stored token is rejected', async () => {
    tokenStore.set('expired');
    server.use(
      http.get('*/api/v1/auth/me', () =>
        HttpResponse.json(
          { error: { code: 'UNAUTHORIZED', message: 'x', details: {} } },
          { status: 401 },
        ),
      ),
    );
    renderLogin();
    expect(await screen.findByRole('button', { name: text.auth.submit })).toBeInTheDocument();
    expect(tokenStore.get()).toBeNull();
  });
});
