// F22 AC2–AC4, R7–R9: màn hình "Lịch sử theo dõi".
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import type { BedOut, SessionOut, TimelineItemOut, UserOut } from '../../api/types';
import { server } from '../../test/msw';
import { renderWithProviders } from '../../test/render';
import { TimelinePage } from './TimelinePage';

const user = (role: UserOut['role'], full_name: string): UserOut => ({
  id: role === 'DOCTOR' ? 3 : 1,
  username: role.toLowerCase(),
  full_name,
  role,
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
});
const nurse = user('NURSE', 'Nguyễn Thị Hoa');
const doctor = user('DOCTOR', 'Lê Văn Bác Sĩ');

const bed: BedOut = {
  id: 1,
  code: 'A01',
  area: { id: 1, code: 'KV01', name: 'Khu hậu phẫu' },
  is_active: true,
  camera: null,
  active_session: null,
};

const session = {
  id: 5,
  bed_id: 1,
  bed_code: 'A01',
  patient_id: 1,
  patient_code: 'BN-001',
  camera_id: 1,
  started_at: '2026-11-18T07:00:00Z',
  ended_at: null,
  previous_session_id: null,
  next_session_id: null,
} as unknown as SessionOut;

const base = {
  session_id: 5,
  bed_code: 'A01',
  observation_quality: null,
  alert: null,
  action: null,
  actor: null,
  outcome: null,
  note: null,
  alert_id: null,
  event_code: null,
  from_bed_code: null,
};

const ev = (over: Partial<TimelineItemOut>): TimelineItemOut => ({
  ...base,
  kind: 'event',
  time: '2026-11-18T07:38:12Z',
  event_id: 1,
  code: 'SIT_UP',
  priority: 'INFO',
  observation_quality: 'GOOD',
  ...over,
});

const act = (over: Partial<TimelineItemOut>): TimelineItemOut => ({
  ...base,
  kind: 'alert_action',
  time: '2026-11-18T07:38:41Z',
  event_id: 2,
  code: 'BED_EXIT',
  priority: 'HIGH',
  event_code: 'BED_EXIT',
  alert_id: 7,
  actor: { id: 1, full_name: 'Nguyễn Văn A' },
  ...over,
});

const sessionAct = (over: Partial<TimelineItemOut>): TimelineItemOut => ({
  ...base,
  kind: 'session_action',
  time: '2026-11-18T07:45:00Z',
  event_id: null,
  code: null,
  priority: null,
  actor: { id: 2, full_name: 'Trần Văn Minh' },
  ...over,
});

const exitWithAlert = ev({
  event_id: 2,
  code: 'BED_EXIT',
  priority: 'HIGH',
  time: '2026-11-18T07:38:20Z',
  alert_id: 7,
  alert: {
    id: 7,
    status: 'ACKNOWLEDGED',
    outcome: null,
    acknowledged_by: { id: 1, full_name: 'Nguyễn Văn A' },
  },
});

const ITEMS: TimelineItemOut[] = [
  ev({}),
  exitWithAlert,
  act({ action: 'alert.acknowledge' }),
  act({ action: 'alert.outcome', outcome: 'PATIENT_SAFE', time: '2026-11-18T07:39:00Z' }),
  act({ action: 'alert.resolve', time: '2026-11-18T07:40:05Z' }),
  sessionAct({ action: 'session.pause', note: 'Vệ sinh', time: '2026-11-18T07:41:00Z' }),
  sessionAct({ action: 'session.resume', time: '2026-11-18T07:42:00Z' }),
  sessionAct({
    action: 'session.transfer',
    bed_code: 'A02',
    from_bed_code: 'A01',
    session_id: 6,
    note: 'Đổi phòng',
  }),
];

type Captured = { path: string; params: URLSearchParams; body?: unknown };

function serve(items: TimelineItemOut[] = ITEMS, total?: number) {
  const calls: Captured[] = [];
  const page = ({ request }: { request: Request }) => {
    const url = new URL(request.url);
    calls.push({ path: url.pathname, params: url.searchParams });
    const offset = Number(url.searchParams.get('offset') ?? 0);
    return HttpResponse.json({ items: offset ? [] : items, total: total ?? items.length });
  };
  server.use(
    http.get('*/api/v1/beds', () => HttpResponse.json({ items: [bed], total: 1 })),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [session], total: 1 })),
    http.get('*/api/v1/sessions/:id/timeline', page),
    http.get('*/api/v1/timeline', page),
    http.post('*/api/v1/alerts/:id/:action', async ({ request }) => {
      const url = new URL(request.url);
      calls.push({ path: url.pathname, params: url.searchParams, body: await request.json() });
      return HttpResponse.json({});
    }),
  );
  return calls;
}

describe('TimelinePage', () => {
  it('formats line as HH:mm:ss - text in Asia/Ho_Chi_Minh', async () => {
    const calls = serve();
    renderWithProviders(<TimelinePage />, nurse, '/timeline');
    expect(await screen.findByText('14:38:12 - Bệnh nhân ngồi dậy')).toBeInTheDocument();
    expect(screen.getByText('14:38:41 - Đã tiếp nhận cảnh báo (Nguyễn Văn A)')).toBeInTheDocument();
    expect(
      screen.getByText('14:39:00 - Ghi kết quả: Bệnh nhân an toàn (Nguyễn Văn A)'),
    ).toBeInTheDocument();
    expect(screen.getByText('14:40:05 - Sự kiện đã xử lý (Nguyễn Văn A)')).toBeInTheDocument();
    // Mặc định: phiên đang mở của giường, gộp cả chuỗi chuyển giường.
    const tl = calls.find((c) => c.path === '/api/v1/sessions/5/timeline');
    expect(tl?.params.get('chain')).toBe('true');
  });

  it('shows session actions: pause, resume, transfer', async () => {
    serve();
    renderWithProviders(<TimelinePage />, nurse, '/timeline');
    expect(
      await screen.findByText('14:41:00 - Tạm dừng thu hình (Trần Văn Minh)'),
    ).toBeInTheDocument();
    expect(screen.getByText('14:42:00 - Tiếp tục thu hình (Trần Văn Minh)')).toBeInTheDocument();
    expect(
      screen.getByText('14:45:00 - Chuyển từ giường A01 sang giường A02 (Trần Văn Minh)'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Đổi phòng/)).toBeInTheDocument();
  });

  it('does not render internal codes', async () => {
    serve();
    const { container } = renderWithProviders(<TimelinePage />, nurse, '/timeline');
    await screen.findByText('14:38:12 - Bệnh nhân ngồi dậy');
    const text = container.textContent ?? '';
    for (const code of [
      'SIT_UP',
      'BED_EXIT',
      'ACKNOWLEDGED',
      'PATIENT_SAFE',
      'alert.',
      'session.',
      'HIGH',
    ]) {
      expect(text).not.toContain(code);
    }
    expect(text).not.toMatch(/\b[A-Z]{2,}_[A-Z_]+\b/);
  });

  it('sends filter params', async () => {
    const calls = serve();
    const u = userEvent.setup();
    renderWithProviders(<TimelinePage />, nurse, '/timeline?bed=1&session=range');
    await screen.findByText('14:38:12 - Bệnh nhân ngồi dậy');
    const first = calls.find((c) => c.path === '/api/v1/timeline');
    expect(first?.params.get('bed_id')).toBe('1');
    expect(first?.params.get('from')).toMatch(/Z$|[+-]\d\d:\d\d$/);
    const input = screen.getByRole('textbox', { name: 'Mức ưu tiên' });
    await waitFor(async () => {
      if (!screen.queryByRole('option', { name: 'Ưu tiên cao', hidden: true }))
        await u.click(input);
      expect(screen.getByRole('option', { name: 'Ưu tiên cao', hidden: true })).toBeInTheDocument();
    });
    await u.click(screen.getByRole('option', { name: 'Ưu tiên cao', hidden: true }));
    await waitFor(() =>
      expect(
        calls.some(
          (c) => c.path === '/api/v1/timeline' && c.params.getAll('priority')[0] === 'HIGH',
        ),
      ).toBe(true),
    );
  });

  it('shows acknowledger name and empty outcome text', async () => {
    serve();
    renderWithProviders(<TimelinePage />, nurse, '/timeline');
    await screen.findByText('14:38:20 - Bệnh nhân rời khỏi vùng giường');
    expect(screen.getByText(/Người tiếp nhận: Nguyễn Văn A/)).toBeInTheDocument();
    expect(screen.getByText(/Kết quả kiểm tra: Chưa ghi kết quả/)).toBeInTheDocument();
  });

  it('records outcome from timeline row', async () => {
    const calls = serve();
    const u = userEvent.setup();
    renderWithProviders(<TimelinePage />, nurse, '/timeline');
    await u.click(await screen.findByRole('button', { name: 'Bệnh nhân an toàn' }));
    await waitFor(() =>
      expect(calls.find((c) => c.path === '/api/v1/alerts/7/outcome')?.body).toEqual({
        outcome: 'PATIENT_SAFE',
        note: null,
      }),
    );
  });

  it('doctor sees no action buttons', async () => {
    serve();
    renderWithProviders(<TimelinePage />, doctor, '/timeline');
    await screen.findByText('14:38:20 - Bệnh nhân rời khỏi vùng giường');
    expect(screen.getByText(/Người tiếp nhận: Nguyễn Văn A/)).toBeInTheDocument();
    for (const name of ['Bệnh nhân an toàn', 'Cảnh báo sai', 'Đã tiếp nhận', 'Đã xử lý']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
    }
  });

  it('loads more when total exceeds loaded items', async () => {
    const calls = serve([ev({})], 201);
    const u = userEvent.setup();
    renderWithProviders(<TimelinePage />, nurse, '/timeline');
    await u.click(await screen.findByRole('button', { name: 'Xem thêm' }));
    await waitFor(() =>
      expect(
        calls.some(
          (c) => c.path === '/api/v1/sessions/5/timeline' && c.params.get('offset') === '1',
        ),
      ).toBe(true),
    );
  });
});
