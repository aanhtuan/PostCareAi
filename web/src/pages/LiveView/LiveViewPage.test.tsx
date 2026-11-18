import { fireEvent, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';

import type { OverviewOut, UserOut } from '../../api/types';
import { vi } from '../../i18n/vi';
import { mockFetch, renderWithProviders } from '../../test/render';
import { LiveViewPage } from './LiveViewPage';

const nurse: UserOut = {
  id: 1,
  username: 'nurse',
  full_name: 'Nguyễn Thị Hoa',
  role: 'NURSE',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
const T = '2026-10-12T07:38:34Z'; // 14:38:34 giờ VN

type Bed = OverviewOut['beds'][number];

function bed(extra: Partial<Bed> = {}): Bed {
  return {
    bed_id: 1,
    code: 'A01',
    area: 'Khu hậu phẫu',
    session: { id: 5, patient_code: 'BN-001', started_at: T, paused_at: null },
    camera: { id: 1, name: 'Camera A01', status: 'ONLINE' },
    pending_alert_count: 0,
    acknowledged_alert_count: 0,
    max_open_priority: null,
    state: null,
    ...extra,
  };
}

function camera(status: 'ONLINE' | 'OFFLINE' | 'UNKNOWN', roi: number[][] | null) {
  return {
    id: 1,
    name: 'Camera A01',
    bed_id: 1,
    bed_code: 'A01',
    source_type: 'FILE',
    source: 'clip.mp4',
    display_mode: 'RAW',
    status,
    last_seen_at: T,
    config_version: 1,
    is_active: true,
    runtime: null,
    roi_polygon: roi,
  };
}

const ROI = [
  [0.2, 0.25],
  [0.8, 0.25],
  [0.8, 0.85],
  [0.2, 0.85],
];

function setup(b: Bed, cam = camera(b.camera?.status ?? 'UNKNOWN', ROI)) {
  mockFetch({
    '/api/v1/overview': { current_shift: null, beds: [b] },
    '/api/v1/cameras/1': cam,
    '/api/v1/events': { items: [], total: 0 },
  });
  return renderWithProviders(
    <Routes>
      <Route path="/beds/:bedId/live" element={<LiveViewPage />} />
    </Routes>,
    nurse,
    '/beds/1/live',
  );
}

const streamImg = () => screen.queryByRole('img', { name: 'Giường A01' });

describe('LiveViewPage', () => {
  it('LiveViewPage shows bed, session and camera status', async () => {
    setup(bed());
    expect(await screen.findByText(vi.cameraStatus.ONLINE)).toBeInTheDocument();
    expect(screen.getAllByText('Giường A01').length).toBeGreaterThan(0);
    expect(screen.getByText(/Đang theo dõi/)).toBeInTheDocument();
    expect(screen.getByText(/BN-001/)).toBeInTheDocument();
    expect(screen.getByText(/14:38:34/)).toBeInTheDocument();
    const img = await screen.findByRole('img', { name: 'Giường A01' });
    expect(img.getAttribute('src')).toContain('/api/v1/cameras/1/stream.mjpeg?token=test-token');
    // Không còn hình người que mô phỏng.
    expect(screen.queryByText(/mô phỏng/)).toBeNull();
    expect(screen.queryByText(vi.live.roiNotConfigured)).toBeNull();
  });

  it('LiveViewPage shows no-session label', async () => {
    setup(bed({ session: null }));
    expect(await screen.findByText(vi.live.noSession)).toBeInTheDocument();
    expect(screen.queryByText(/BN-001/)).toBeNull();
  });

  it('LiveViewPage shows "Chưa gắn camera" and no image without a camera', async () => {
    setup(bed({ camera: null }));
    expect((await screen.findAllByText(vi.camera.notAssigned)).length).toBeGreaterThan(0);
    expect(streamImg()).toBeNull();
  });

  it('LiveViewPage hides stream when camera offline', async () => {
    setup(bed({ camera: { id: 1, name: 'Camera A01', status: 'OFFLINE' } }));
    expect((await screen.findAllByText(vi.cameraStatus.OFFLINE)).length).toBeGreaterThan(0);
    expect(streamImg()).toBeNull();
  });

  it('LiveViewPage hides stream on image error', async () => {
    setup(bed());
    const img = await screen.findByRole('img', { name: 'Giường A01' });
    fireEvent.error(img);
    expect(streamImg()).toBeNull();
    expect(screen.getAllByText(vi.cameraStatus.OFFLINE).length).toBeGreaterThan(0);
  });

  it('LiveViewPage notes when the bed region is not configured', async () => {
    setup(bed(), camera('ONLINE', null));
    expect(await screen.findByText(vi.live.roiNotConfigured)).toBeInTheDocument();
  });

  it('LiveViewPage shows no internal codes', async () => {
    const { container } = setup(bed());
    await screen.findByRole('img', { name: 'Giường A01' });
    const text = container.textContent ?? '';
    for (const code of ['ONLINE', 'OFFLINE', 'UNKNOWN', 'NO_OBSERVATION', 'RAW', 'FILE']) {
      expect(text).not.toContain(code);
    }
  });
});
