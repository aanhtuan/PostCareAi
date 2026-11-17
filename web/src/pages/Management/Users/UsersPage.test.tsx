import { MantineProvider } from '@mantine/core';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it } from 'vitest';

import { tokenStore } from '../../../api/client';
import type { UserOut } from '../../../api/types';
import { App } from '../../../App';
import { AuthProvider } from '../../../auth/AuthContext';
import { vi as text } from '../../../i18n/vi';
import { server } from '../../../test/msw';
import { renderWithProviders } from '../../../test/render';
import { UsersPage } from './UsersPage';

const T = '2026-11-17T00:00:00Z';
const admin: UserOut = {
  id: 4,
  username: 'admin',
  full_name: 'Phạm Thu Hà',
  role: 'ADMIN',
  is_active: true,
  created_at: T,
};
const nurse: UserOut = {
  id: 1,
  username: 'nurse',
  full_name: 'Nguyễn Thị Hoa',
  role: 'NURSE',
  is_active: true,
  created_at: T,
};
const family: UserOut = {
  id: 7,
  username: 'nguoinha01',
  full_name: 'Trần Văn Nam',
  role: 'FAMILY',
  is_active: true,
  created_at: T,
};
const doctor: UserOut = { ...nurse, id: 3, username: 'doctor', role: 'DOCTOR' };

function listHandler(items: UserOut[]) {
  return http.get('*/api/v1/users', () => HttpResponse.json({ items, total: items.length }));
}

function renderApp(route: string) {
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

describe('UsersPage', () => {
  beforeEach(() => localStorage.clear());

  it('UsersPage lists users with Vietnamese role labels', async () => {
    server.use(listHandler([admin, nurse, family]));
    renderWithProviders(<UsersPage />, admin);
    const row = (await screen.findByText('nguoinha01')).closest('tr');
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText(text.role.FAMILY)).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText(text.users.status.active)).toBeInTheDocument();
    const nurseRow = screen.getByText('nurse').closest('tr') as HTMLElement;
    expect(within(nurseRow).getByText(text.role.NURSE)).toBeInTheDocument();
    expect(document.body.textContent ?? '').not.toMatch(/\b(FAMILY|CHARGE_NURSE|ADMIN|NURSE)\b/);
  });

  it('asks for confirmation before locking', async () => {
    let locked = 0;
    server.use(
      listHandler([admin, nurse]),
      http.post('*/api/v1/users/1/lock', () => {
        locked += 1;
        return HttpResponse.json({ ...nurse, is_active: false });
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<UsersPage />, admin);
    const row = (await screen.findByText('nurse')).closest('tr') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: text.users.lock }));
    expect(await screen.findByText(text.users.confirmLock)).toBeInTheDocument();
    expect(locked).toBe(0);
    await user.click(screen.getByRole('button', { name: text.common.confirm }));
    await waitFor(() => expect(locked).toBe(1));
  });

  it('does not allow locking yourself from the table', async () => {
    server.use(listHandler([admin]));
    renderWithProviders(<UsersPage />, admin);
    const row = (await screen.findByText('admin')).closest('tr') as HTMLElement;
    expect(within(row).getByRole('button', { name: text.users.lock })).toBeDisabled();
  });

  it('shows the Vietnamese API message on 409', async () => {
    server.use(
      listHandler([admin, nurse]),
      http.patch('*/api/v1/users/4', () =>
        HttpResponse.json(
          {
            error: {
              code: 'LAST_ADMIN',
              message: 'Không thể khóa hoặc đổi vai trò quản trị viên cuối cùng',
              details: {},
            },
          },
          { status: 409 },
        ),
      ),
    );
    const { Notifications } = await import('@mantine/notifications');
    const user = userEvent.setup();
    renderWithProviders(
      <>
        <Notifications />
        <UsersPage />
      </>,
      admin,
    );
    const row = (await screen.findByText('admin')).closest('tr') as HTMLElement;
    await user.click(within(row).getByRole('button', { name: text.users.edit }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText(text.users.username, { exact: false })).toBeDisabled();
    await user.click(within(dialog).getByRole('button', { name: text.users.save }));
    expect(
      await screen.findByText('Không thể khóa hoặc đổi vai trò quản trị viên cuối cùng'),
    ).toBeInTheDocument();
  });

  it('non-admin cannot open users page', async () => {
    tokenStore.set('t');
    server.use(
      http.get('*/api/v1/auth/me', () => HttpResponse.json(doctor)),
      http.get('*/api/v1/overview', () => HttpResponse.json({ beds: [], shift: null })),
      listHandler([admin]),
    );
    renderApp('/management/users');
    await screen.findByText(text.app.name);
    await waitFor(() => expect(screen.queryByText(text.users.add)).not.toBeInTheDocument());
    expect(screen.queryByRole('link', { name: text.users.title })).not.toBeInTheDocument();
  });

  it('admin sees the users menu item', async () => {
    tokenStore.set('t');
    server.use(
      http.get('*/api/v1/auth/me', () => HttpResponse.json(admin)),
      listHandler([admin]),
    );
    renderApp('/management/users');
    expect(await screen.findByRole('button', { name: text.users.add })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: text.users.title })).toBeInTheDocument();
  });

  it('family user redirected to /family', async () => {
    tokenStore.set('t');
    server.use(http.get('*/api/v1/auth/me', () => HttpResponse.json(family)));
    renderApp('/');
    expect(await screen.findByText(text.family.noAccess)).toBeInTheDocument();
    expect(screen.queryByText(text.nav.overview)).not.toBeInTheDocument();
    expect(screen.queryByText(text.nav.alerts)).not.toBeInTheDocument();
  });
});
