import { fireEvent, screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { describe, expect, it } from 'vitest';

import type { OverviewBedOut, UserOut } from '../../api/types';
import { renderWithProviders } from '../../test/render';
import { BedCard } from './BedCard';

const nurse: UserOut = {
  id: 1,
  username: 'nurse',
  full_name: 'Nguyễn Thị Hoa',
  role: 'NURSE',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
const T = '2026-10-12T07:38:34Z';

function bed(extra: Partial<OverviewBedOut> = {}): OverviewBedOut {
  return {
    bed_id: 4,
    code: 'A01',
    area: 'Khu hậu phẫu',
    session: { id: 1, patient_code: 'BN-001', started_at: T, paused_at: null },
    camera: { id: 1, name: 'Camera A01', status: 'ONLINE' },
    pending_alert_count: 0,
    acknowledged_alert_count: 0,
    max_open_priority: null,
    state: {
      bed_id: 4,
      body_state: 'LYING',
      observation_quality: 'GOOD',
      activity_level: 'LOW',
      rest_status: 'UNKNOWN',
      face_status: 'NOT_VISIBLE',
      face_signals: {
        eyes_closed: false,
        eyes_closed_prolonged: false,
        brow_down: false,
        eye_squint: false,
        nose_sneer: false,
        mouth_change: false,
      },
      updated_at: T,
    },
    ...extra,
  };
}

function renderCard(b: OverviewBedOut) {
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<BedCard bed={b} />} />
      <Route path="/beds/:bedId/live" element={<p>Trang theo dõi trực tiếp</p>} />
    </Routes>,
    nurse,
  );
}

function card() {
  return screen.getByRole('button', { name: /Giường A01/ });
}

describe('BedCard', () => {
  it('shows session and camera labels', () => {
    renderCard(bed());
    expect(screen.getByText('Giường A01')).toBeInTheDocument();
    expect(screen.getByText('Đang theo dõi')).toBeInTheDocument();
    expect(screen.getByText(/Bệnh nhân BN-001/)).toBeInTheDocument();
    expect(screen.getByText('Camera hoạt động')).toBeInTheDocument();
  });

  it('bed without session shows Không theo dõi', () => {
    renderCard(bed({ session: null, state: null }));
    expect(screen.getByText('Không theo dõi')).toBeInTheDocument();
    expect(screen.queryByText('Đang theo dõi')).not.toBeInTheDocument();
    expect(screen.queryByText(/BN-001/)).not.toBeInTheDocument();
  });

  it.each([
    ['OFFLINE', 'Mất kết nối camera'],
    ['UNKNOWN', 'Chưa rõ trạng thái camera'],
  ] as const)('camera %s shows its label', (status, label) => {
    renderCard(bed({ camera: { id: 1, name: 'Camera A01', status } }));
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it('bed without camera shows Chưa gắn camera', () => {
    renderCard(bed({ camera: null }));
    expect(screen.getByText('Chưa gắn camera')).toBeInTheDocument();
  });

  it('no observation shows Cần kiểm tra, never Đang theo dõi', () => {
    renderCard(bed({ state: { ...bed().state!, body_state: 'NO_OBSERVATION' } }));
    expect(screen.getByText('Cần kiểm tra')).toBeInTheDocument();
    expect(screen.getByText('Không đủ dữ liệu quan sát')).toBeInTheDocument();
    expect(screen.queryByText('Đang theo dõi')).not.toBeInTheDocument();
  });

  it('pending alert shows Cảnh báo mới', () => {
    renderCard(bed({ pending_alert_count: 1, max_open_priority: 'HIGH' }));
    expect(screen.getByText('Cảnh báo mới')).toBeInTheDocument();
  });

  it('paused session shows capture paused and hides stale body state', () => {
    renderCard(bed({ session: { ...bed().session!, paused_at: T } }));
    expect(screen.getByText('Đang tạm dừng thu hình')).toBeInTheDocument();
    expect(screen.queryByText('Đang theo dõi')).not.toBeInTheDocument();
    expect(screen.queryByText('Nằm')).not.toBeInTheDocument();
    expect(screen.getByText(/Bệnh nhân BN-001/)).toBeInTheDocument();
  });

  it('clicking a bed card navigates to live view', () => {
    renderCard(bed());
    fireEvent.click(card());
    expect(screen.getByText('Trang theo dõi trực tiếp')).toBeInTheDocument();
  });

  it('Enter on a focused bed card navigates to live view', () => {
    renderCard(bed());
    fireEvent.keyDown(card(), { key: 'Enter' });
    expect(screen.getByText('Trang theo dõi trực tiếp')).toBeInTheDocument();
  });

  it('shows no internal codes', () => {
    renderCard(bed({ camera: { id: 1, name: 'Camera A01', status: 'OFFLINE' } }));
    expect(document.body.textContent).not.toMatch(/ONLINE|OFFLINE|LYING|NO_OBSERVATION|GOOD/);
  });
});
