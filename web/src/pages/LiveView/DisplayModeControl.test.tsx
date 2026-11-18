// F28 AC5, R10: tên chế độ hiển thị bằng tiếng Việt; chỉ ADMIN và CHARGE_NURSE đổi được.
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { UserOut, UserRole } from '../../api/types';
import { vi } from '../../i18n/vi';
import { mockFetch, renderWithProviders } from '../../test/render';
import { DisplayModeControl } from './DisplayModeControl';

function user(role: UserRole): UserOut {
  return {
    id: 1,
    username: role.toLowerCase(),
    full_name: 'Người dùng',
    role,
    is_active: true,
    created_at: '2026-11-17T00:00:00Z',
  };
}

function setup(role: UserRole, mode: 'RAW' | 'BLUR' | 'SKELETON' = 'BLUR') {
  const fetchFn = mockFetch({
    '/api/v1/cameras/1/display-mode': { id: 1, display_mode: 'SKELETON' },
  });
  renderWithProviders(<DisplayModeControl cameraId={1} mode={mode} />, user(role));
  return fetchFn;
}

describe('DisplayModeControl', () => {
  it.each<['RAW' | 'BLUR' | 'SKELETON', string]>([
    ['RAW', 'Video gốc'],
    ['BLUR', 'Làm mờ khuôn mặt'],
    ['SKELETON', 'Chỉ skeleton + ROI'],
  ])('shows the current mode %s in Vietnamese', (mode, label) => {
    setup('NURSE', mode);
    expect(vi.displayMode[mode]).toBe(label);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.queryByText(mode)).toBeNull();
  });

  it.each<UserRole>(['ADMIN', 'CHARGE_NURSE'])('%s sees the mode switch', (role) => {
    setup(role);
    for (const label of Object.values(vi.displayMode)) {
      expect(screen.getByRole('radio', { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole('radio', { name: vi.displayMode.BLUR })).toBeChecked();
  });

  it.each<UserRole>(['NURSE', 'DOCTOR'])('%s does not see the mode switch', (role) => {
    setup(role);
    expect(screen.queryAllByRole('radio')).toHaveLength(0);
    expect(screen.getByText(vi.displayMode.BLUR)).toBeInTheDocument();
  });

  it('changing the mode sends PUT display-mode', async () => {
    const fetchFn = setup('CHARGE_NURSE');
    fireEvent.click(screen.getByRole('radio', { name: vi.displayMode.SKELETON }));
    await waitFor(() => {
      const calls = fetchFn.mock.calls as unknown as [RequestInfo, RequestInit | undefined][];
      const put = calls.find(
        ([url, init]) => String(url).endsWith('/cameras/1/display-mode') && init?.method === 'PUT',
      );
      expect(put).toBeDefined();
      expect(JSON.parse(String(put?.[1]?.body))).toEqual({ display_mode: 'SKELETON' });
    });
  });
});
