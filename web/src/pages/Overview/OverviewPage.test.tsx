import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { AlertOut, EventOut, OverviewOut, UserOut } from '../../api/types';
import { mockFetch, renderWithProviders } from '../../test/render';
import { OverviewPage } from './OverviewPage';

const nurse: UserOut = { id: 1, username: 'nurse', full_name: 'Nguyễn Thị Hoa', role: 'NURSE' };
const doctor: UserOut = { id: 3, username: 'doctor', full_name: 'Lê Quốc Bảo', role: 'DOCTOR' };
const T = '2026-10-12T07:38:34Z'; // 14:38:34 giờ VN

function bed(
  id: number,
  code: string,
  extra: Partial<OverviewOut['beds'][number]> = {},
): OverviewOut['beds'][number] {
  return {
    bed_id: id,
    code,
    area: 'Khu hậu phẫu',
    session: { id: id, patient_code: `BN-00${id}`, started_at: T },
    camera: { id, name: `Camera ${code}`, status: 'ONLINE' },
    pending_alert_count: 0,
    acknowledged_alert_count: 0,
    max_open_priority: null,
    state: {
      bed_id: id,
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

const overview: OverviewOut = {
  current_shift: { id: 2, name: 'Ca chiều', start_time: '14:00:00', end_time: '22:00:00' },
  beds: [
    bed(1, 'A01'),
    bed(2, 'A02', { acknowledged_alert_count: 1, max_open_priority: 'MEDIUM' }),
    bed(3, 'A03', { pending_alert_count: 2, max_open_priority: 'HIGH' }),
  ],
};

const pendingAlert: AlertOut = {
  id: 7,
  status: 'PENDING',
  outcome: null,
  note: null,
  created_at: T,
  acknowledged_by: null,
  acknowledged_at: null,
  outcome_by: null,
  outcome_at: null,
  resolved_by: null,
  resolved_at: null,
  event: { id: 9, code: 'BED_EXIT', priority: 'HIGH', occurred_at: T, observation_quality: 'GOOD' },
  bed: { id: 3, code: 'A03' },
  session: { id: 3, patient_code: 'BN-003' },
};

const event: EventOut = {
  id: 9,
  event_uid: 'x',
  session_id: 3,
  bed_id: 3,
  bed_code: 'A03',
  camera_id: 3,
  code: 'SIT_UP',
  priority: 'INFO',
  occurred_at: '2026-10-12T07:37:00Z',
  detected_at: T,
  created_at: T,
  confidence: 0.9,
  observation_quality: 'GOOD',
  explanation: {},
  alert_id: null,
  alert_status: null,
};

function setup(user: UserOut = nurse) {
  mockFetch({
    '/api/v1/overview': overview,
    '/api/v1/alerts': { items: [pendingAlert], total: 1 },
    '/api/v1/events': { items: [event], total: 1 },
  });
  return renderWithProviders(<OverviewPage />, user);
}

describe('OverviewPage', () => {
  it('header shows current shift', async () => {
    setup();
    expect(await screen.findByText('Ca trực: 14:00–22:00')).toBeInTheDocument();
  });

  it('renders a card per bed with A12 status, body state and quality', async () => {
    setup();
    const a01 = await screen.findByRole('button', { name: /Giường A01/ });
    expect(within(a01).getByText('Đang theo dõi')).toBeInTheDocument();
    expect(within(a01).getByText('Nằm')).toBeInTheDocument();
    expect(within(a01).getByText(/Quan sát tốt/)).toBeInTheDocument();
    const a02 = screen.getByRole('button', { name: /Giường A02/ });
    expect(within(a02).getByText('Cần kiểm tra')).toBeInTheDocument();
    const a03 = screen.getByRole('button', { name: /Giường A03/ });
    expect(within(a03).getByText('Cảnh báo mới')).toBeInTheDocument();
    expect(within(a03).getByText('Ưu tiên cao')).toBeInTheDocument();
  });

  it('shows attention and recent activity blocks without internal codes', async () => {
    setup();
    expect(await screen.findByText('Sự kiện cần chú ý')).toBeInTheDocument();
    expect(await screen.findByText('Bệnh nhân rời khỏi vùng giường')).toBeInTheDocument();
    expect(await screen.findByText(/Bệnh nhân ngồi dậy/)).toBeInTheDocument();
    expect(screen.getByText('14:38 - Giường A03')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Đã tiếp nhận' })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/BED_EXIT|SIT_UP|PENDING|NO_OBSERVATION/);
  });

  it('doctor sees no action buttons', async () => {
    setup(doctor);
    expect(await screen.findByText('Bệnh nhân rời khỏi vùng giường')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Đã tiếp nhận' })).not.toBeInTheDocument();
  });
});
