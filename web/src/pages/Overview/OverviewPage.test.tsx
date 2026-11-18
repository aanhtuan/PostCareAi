import { act, screen, within } from '@testing-library/react';
import type { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AlertOut, EventOut, OverviewOut, UserOut } from '../../api/types';
import { vi as viText } from '../../i18n/vi';
import { applyMessage, flushInvalidations, invalidateAll } from '../../realtime/invalidation';
import { mockFetch, renderWithProviders, testQueryClient } from '../../test/render';
import { OverviewPage } from './OverviewPage';

const nurse: UserOut = {
  id: 1,
  username: 'nurse',
  full_name: 'Nguyễn Thị Hoa',
  role: 'NURSE',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
const doctor: UserOut = {
  id: 3,
  username: 'doctor',
  full_name: 'Lê Quốc Bảo',
  role: 'DOCTOR',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
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
    session: { id: id, patient_code: `BN-00${id}`, started_at: T, paused_at: null },
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
  current_shift: {
    id: 2,
    name: 'Ca chiều',
    start_time: '14:00:00',
    end_time: '22:00:00',
    is_active: true,
  },
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

function setup(user: UserOut = nurse, data: OverviewOut = overview) {
  mockFetch({
    '/api/v1/overview': data,
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

  it('header shows no shift', async () => {
    setup(nurse, { ...overview, current_shift: null });
    expect(await screen.findByText('Ca trực: —')).toBeInTheDocument();
  });

  it('shows empty state when no beds', async () => {
    setup(nurse, { ...overview, beds: [] });
    expect(await screen.findByText('Chưa có giường nào đang dùng')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Giường/ })).not.toBeInTheDocument();
  });

  describe('realtime (F21)', () => {
    afterEach(() => {
      vi.useRealTimers();
    });

    const msg = (type: string, payload: unknown) => ({ type, payload, sent_at: T });
    const routes = (extra: Record<string, unknown> = {}): Record<string, unknown> => ({
      '/api/v1/overview': overview,
      '/api/v1/alerts': { items: [], total: 0 },
      '/api/v1/events': { items: [], total: 0 },
      ...extra,
    });
    const calls = (fn: ReturnType<typeof mockFetch>, path: string) =>
      fn.mock.calls.filter((c) => String(c[0]).split('?')[0] === path).length;
    function push(qc: QueryClient, type: string, payload: unknown) {
      act(() => {
        applyMessage(qc, msg(type, payload));
        flushInvalidations(qc);
      });
    }
    function live(r = routes()) {
      const fetchFn = mockFetch(r);
      const qc = testQueryClient();
      renderWithProviders(<OverviewPage />, nurse, '/', {}, { ws: 'open', qc });
      return { fetchFn, qc };
    }

    it('renders body state and observation quality', async () => {
      live();
      const a01 = await screen.findByRole('button', { name: /Giường A01/ });
      expect(within(a01).getByText('Nằm')).toBeInTheDocument();
      expect(within(a01).getByText(/Quan sát tốt/)).toBeInTheDocument();
    });

    it('shows pending count and max priority', async () => {
      live();
      const a03 = await screen.findByRole('button', { name: /Giường A03/ });
      expect(within(a03).getByText('2')).toBeInTheDocument();
      expect(within(a03).getByText('Ưu tiên cao')).toBeInTheDocument();
    });

    it('card updates from bed.state without refetch', async () => {
      const { fetchFn, qc } = live();
      const a01 = await screen.findByRole('button', { name: /Giường A01/ });
      const before = calls(fetchFn, '/api/v1/overview');
      push(qc, 'bed.state', {
        ...overview.beds[0].state,
        body_state: 'SITTING',
        observation_quality: 'LOW_CONFIDENCE',
      });
      expect(await within(a01).findByText('Ngồi')).toBeInTheDocument();
      expect(within(a01).getByText(/Độ tin cậy thấp/)).toBeInTheDocument();
      expect(calls(fetchFn, '/api/v1/overview')).toBe(before);
    });

    it('card turns to Cảnh báo mới immediately on alert.created', async () => {
      const r = routes();
      const { qc } = live(r);
      const a01 = await screen.findByRole('button', { name: /Giường A01/ });
      expect(within(a01).getByText('Đang theo dõi')).toBeInTheDocument();
      // Server đã lưu cảnh báo trước khi phát (lưu trước, phát sau): refetch phải khớp.
      const beds = overview.beds.map((b) =>
        b.bed_id === 1 ? { ...b, pending_alert_count: 1, max_open_priority: 'HIGH' as const } : b,
      );
      mockFetch({ ...r, '/api/v1/overview': { ...overview, beds } });
      push(qc, 'alert.created', {
        alert: { ...pendingAlert, id: 11, bed: { id: 1, code: 'A01' } },
        event: { ...event, bed_id: 1, priority: 'HIGH' },
      });
      expect(await within(a01).findByText('Cảnh báo mới')).toBeInTheDocument();
    });

    it('attention block updates on alert.created', async () => {
      const r = routes();
      const { qc } = live(r);
      expect(await screen.findByText(viText.overview.noAttention)).toBeInTheDocument();
      mockFetch({ ...r, '/api/v1/alerts': { items: [pendingAlert], total: 1 } });
      push(qc, 'alert.created', { alert: pendingAlert, event: { ...event, code: 'BED_EXIT' } });
      expect(await screen.findByText('Bệnh nhân rời khỏi vùng giường')).toBeInTheDocument();
      expect(screen.getByText('14:38 - Giường A03')).toBeInTheDocument();
      expect(screen.getByText('Chờ tiếp nhận')).toBeInTheDocument();
    });

    it('recent activity updates on event.created', async () => {
      const r = routes();
      const { qc } = live(r);
      expect(await screen.findByText(viText.overview.noRecent)).toBeInTheDocument();
      const logEvent: EventOut = { ...event, id: 20, code: 'POSTURE_CHANGE', priority: 'LOG' };
      mockFetch({ ...r, '/api/v1/events': { items: [logEvent], total: 1 } });
      push(qc, 'event.created', logEvent);
      expect(await screen.findByText(/Bệnh nhân thay đổi tư thế/)).toBeInTheDocument();
      // Ca âm: sự kiện mức LOG không tạo cảnh báo nên không vào "Sự kiện cần chú ý".
      expect(screen.getByText(viText.overview.noAttention)).toBeInTheDocument();
    });

    it('does not render internal codes', async () => {
      live(
        routes({
          '/api/v1/alerts': { items: [pendingAlert], total: 1 },
          '/api/v1/events': { items: [event], total: 1 },
        }),
      );
      expect(await screen.findByText('Bệnh nhân rời khỏi vùng giường')).toBeInTheDocument();
      expect(document.body.textContent).not.toMatch(
        /BED_EXIT|SIT_UP|PENDING|ACKNOWLEDGED|NO_OBSERVATION|HIGH|MEDIUM|LYING|GOOD/,
      );
    });

    it('no refetch interval while WebSocket open', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      const { fetchFn } = live();
      expect(await screen.findByRole('button', { name: /Giường A01/ })).toBeInTheDocument();
      const before = fetchFn.mock.calls.length;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });
      expect(fetchFn.mock.calls.length).toBe(before);
    });

    it('polls as fallback while WebSocket disconnected', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });
      const r = routes({ '/api/v1/overview': { ...overview, beds: [bed(1, 'A01')] } });
      mockFetch(r);
      renderWithProviders(<OverviewPage />, nurse, '/', {}, { ws: 'reconnecting' });
      expect(await screen.findByRole('button', { name: /Giường A01/ })).toBeInTheDocument();
      mockFetch({
        ...r,
        '/api/v1/overview': { ...overview, beds: [bed(1, 'A01'), bed(4, 'A04')] },
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(await screen.findByRole('button', { name: /Giường A04/ })).toBeInTheDocument();
    });

    it('refetches after reconnect', async () => {
      const r = routes({ '/api/v1/overview': { ...overview, beds: [bed(1, 'A01')] } });
      const { qc } = live(r);
      expect(await screen.findByRole('button', { name: /Giường A01/ })).toBeInTheDocument();
      mockFetch({
        ...r,
        '/api/v1/overview': { ...overview, beds: [bed(1, 'A01'), bed(4, 'A04')] },
      });
      act(() => invalidateAll(qc));
      expect(await screen.findByRole('button', { name: /Giường A04/ })).toBeInTheDocument();
    });
  });
});
