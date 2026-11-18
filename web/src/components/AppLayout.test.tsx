import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import type { UserOut } from '../api/types';
import { vi as text } from '../i18n/vi';
import { RealtimeContext } from '../realtime/RealtimeProvider';
import type { WsStatus } from '../realtime/wsClient';
import { renderWithProviders } from '../test/render';
import { AppLayout } from './AppLayout';

const USERS: UserOut[] = [
  {
    id: 1,
    username: 'nurse',
    full_name: 'Nguyễn Thị Hoa',
    role: 'NURSE',
    is_active: true,
    created_at: '2026-11-17T00:00:00Z',
  },
  {
    id: 2,
    username: 'charge',
    full_name: 'Trần Văn Minh',
    role: 'CHARGE_NURSE',
    is_active: true,
    created_at: '2026-11-17T00:00:00Z',
  },
  {
    id: 3,
    username: 'doctor',
    full_name: 'Lê Quốc Bảo',
    role: 'DOCTOR',
    is_active: true,
    created_at: '2026-11-17T00:00:00Z',
  },
  {
    id: 4,
    username: 'admin',
    full_name: 'Phạm Thu Hà',
    role: 'ADMIN',
    is_active: true,
    created_at: '2026-11-17T00:00:00Z',
  },
];

describe('AppLayout header', () => {
  it.each(USERS)('header shows full name and role label ($role)', (user) => {
    renderWithProviders(<AppLayout />, user);
    expect(screen.getByText(user.full_name)).toBeInTheDocument();
    const header = screen.getByText(user.full_name).closest('p');
    expect(header?.textContent).toContain(text.role[user.role]);
    // Không hiện mã vai trò nội bộ.
    expect(document.body.textContent ?? '').not.toContain(user.role);
  });

  it('role labels are Vietnamese', () => {
    expect(text.role).toEqual({
      NURSE: 'Điều dưỡng',
      CHARGE_NURSE: 'Phụ trách ca',
      DOCTOR: 'Bác sĩ',
      ADMIN: 'Quản trị',
      FAMILY: 'Người nhà',
    });
  });

  it('users menu item only for ADMIN', () => {
    for (const user of USERS) {
      const { unmount } = renderWithProviders(<AppLayout />, user);
      const link = screen.queryByRole('link', { name: text.users.title });
      if (user.role === 'ADMIN') expect(link).toBeInTheDocument();
      else expect(link).not.toBeInTheDocument();
      unmount();
    }
  });

  it('logout button calls logout', async () => {
    const logout = vi.fn();
    renderWithProviders(<AppLayout />, USERS[0], '/', { logout });
    await userEvent.setup().click(screen.getByRole('button', { name: text.auth.logout }));
    expect(logout).toHaveBeenCalledTimes(1);
  });
});

describe('RealtimeStatus (F18 R13)', () => {
  const renderWith = (status: WsStatus) =>
    renderWithProviders(
      <RealtimeContext.Provider value={status}>
        <AppLayout />
      </RealtimeContext.Provider>,
      USERS[0],
    );

  it('shows the lost-connection indicator while reconnecting', () => {
    renderWith('reconnecting');
    expect(screen.getByText(text.realtime.reconnecting)).toBeInTheDocument();
    expect(screen.queryByText(text.realtime.connected)).not.toBeInTheDocument();
  });

  it('hides the indicator once connected', () => {
    renderWith('open');
    expect(screen.getByText(text.realtime.connected)).toBeInTheDocument();
    expect(screen.queryByText(text.realtime.reconnecting)).not.toBeInTheDocument();
  });

  it('first connection is not shown as lost', () => {
    renderWith('connecting');
    expect(screen.getByText(text.realtime.connecting)).toBeInTheDocument();
    expect(screen.queryByText(text.realtime.reconnecting)).not.toBeInTheDocument();
  });
});
