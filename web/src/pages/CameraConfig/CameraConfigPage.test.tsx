import { fireEvent, screen, waitFor } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';

import type { UserOut, UserRole } from '../../api/types';
import { RequireRole } from '../../auth/RequireRole';
import { fmt, vi } from '../../i18n/vi';
import { mockFetch, renderWithProviders } from '../../test/render';
import { CameraConfigPage } from './CameraConfigPage';

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

const ROI = [
  [0.2, 0.25],
  [0.8, 0.25],
  [0.8, 0.85],
  [0.2, 0.85],
];

const camera = {
  id: 1,
  name: 'Camera A01',
  bed_id: 1,
  bed_code: 'A01',
  source_type: 'FILE',
  source: 'clip.mp4',
  display_mode: 'RAW',
  status: 'ONLINE',
  last_seen_at: null,
  config_version: 2,
  is_active: true,
  runtime: null,
  roi_polygon: ROI,
};

const DEFAULTS = { posture: { lying_enter_deg: 25 } };

function setup(role: UserRole) {
  const fetchFn = mockFetch({
    '/api/v1/cameras/1': camera,
    '/api/v1/cameras/1/thresholds': {
      defaults: DEFAULTS,
      overrides: {},
      effective: DEFAULTS,
      rules: { allowed: ['posture.*'], limits: {}, relations: [] },
      config_version: 2,
    },
    '/api/v1/cameras/1/roi': { camera_id: 1, roi_polygon: ROI, config_version: 3 },
  });
  renderWithProviders(
    <Routes>
      <Route
        path="/cameras/:cameraId/config"
        element={
          <RequireRole roles={['ADMIN']}>
            <CameraConfigPage />
          </RequireRole>
        }
      />
      <Route path="/" element={<div>overview-page</div>} />
    </Routes>,
    user(role),
    '/cameras/1/config',
  );
  return fetchFn;
}

describe('CameraConfigPage', () => {
  it('admin sees title, saved ROI and image quality block', async () => {
    setup('ADMIN');
    expect(await screen.findByRole('heading', { name: vi.cameraConfig.title })).toBeInTheDocument();
    expect(await screen.findByText(fmt(vi.cameraConfig.roi.points, { n: 4 }))).toBeInTheDocument();
    expect(screen.getByText(vi.cameraConfig.imageQuality.noData)).toBeInTheDocument();
  });

  it('saving the ROI sends PUT with normalized polygon', async () => {
    const fetchFn = setup('ADMIN');
    const save = await screen.findByRole('button', { name: vi.cameraConfig.roi.save });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);
    await waitFor(() => {
      const calls = fetchFn.mock.calls as unknown as [RequestInfo, RequestInit | undefined][];
      const put = calls.find(
        ([url, init]) => String(url).endsWith('/cameras/1/roi') && init?.method === 'PUT',
      );
      expect(put).toBeDefined();
      expect(JSON.parse(String(put?.[1]?.body))).toEqual({ roi_polygon: ROI });
    });
  });

  it.each<UserRole>(['NURSE', 'CHARGE_NURSE', 'DOCTOR'])('%s is sent back to overview', (role) => {
    setup(role);
    expect(screen.getByText('overview-page')).toBeInTheDocument();
    expect(screen.queryByText(vi.cameraConfig.title)).toBeNull();
  });
});
