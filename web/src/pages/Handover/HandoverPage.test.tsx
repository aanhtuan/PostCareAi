// F24 AC1, AC2, AC4, R7–R10: màn hình "Bàn giao ca".
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi as vitest } from 'vitest';

import type { HandoverBedOut, HandoverOut, ShiftOut } from '../../api/types';
import { acknowledged, makeAlert, nurse } from '../../test/alertFixtures';
import { server } from '../../test/msw';
import { renderWithProviders } from '../../test/render';
import { HandoverPage } from './HandoverPage';

const SHIFTS: ShiftOut[] = [
  { id: 1, name: 'Ca sáng', start_time: '06:00:00', end_time: '14:00:00', is_active: true },
  { id: 2, name: 'Ca chiều', start_time: '14:00:00', end_time: '22:00:00', is_active: true },
  { id: 3, name: 'Ca đêm', start_time: '22:00:00', end_time: '06:00:00', is_active: true },
];

const bedRow = (over: Partial<HandoverBedOut>): HandoverBedOut => ({
  bed_id: 1,
  code: 'A01',
  is_active: true,
  event_counts: {},
  alerts_resolved: 0,
  alerts_unresolved: 0,
  state_change_count: 0,
  outcome_counts: {},
  ...over,
});

const BODY: HandoverOut = {
  from: '2026-10-12T07:00:00Z',
  to: '2026-10-12T15:00:00Z',
  shift: SHIFTS[1]!,
  outstanding_alerts: [
    acknowledged(7, { bed: { id: 1, code: 'A01' } }),
    makeAlert(8, {
      bed: { id: 2, code: 'A02' },
      event: {
        id: 108,
        code: 'BED_EDGE',
        priority: 'MEDIUM',
        occurred_at: '2026-10-12T06:00:00Z',
        observation_quality: 'GOOD',
      },
    }),
  ],
  beds: [
    bedRow({
      event_counts: { SIT_UP: 2, BED_EXIT: 1 },
      alerts_resolved: 1,
      alerts_unresolved: 2,
      state_change_count: 3,
      outcome_counts: { CONFIRMED: 1, PATIENT_SAFE: 2 },
    }),
    bedRow({ bed_id: 2, code: 'A02' }),
    bedRow({ bed_id: 3, code: 'A03', is_active: false, event_counts: { BED_EDGE: 4 } }),
  ],
};

function serve(body: HandoverOut = BODY) {
  const calls: URLSearchParams[] = [];
  server.use(
    http.get('*/api/v1/shifts', () => HttpResponse.json(SHIFTS)),
    http.get('*/api/v1/handover', ({ request }) => {
      calls.push(new URL(request.url).searchParams);
      return HttpResponse.json(body);
    }),
  );
  return calls;
}

function at(iso: string) {
  vitest.useFakeTimers({ shouldAdvanceTime: true, toFake: ['Date'] });
  vitest.setSystemTime(new Date(iso));
}

afterEach(() => {
  vitest.useRealTimers();
  vitest.restoreAllMocks();
});

describe('HandoverPage', () => {
  it('renders per-bed summary', async () => {
    serve();
    renderWithProviders(<HandoverPage />, nurse, '/handover');
    const table = await screen.findByTestId('handover-beds');
    const rows = within(table).getAllByRole('row');
    expect(rows).toHaveLength(4); // tiêu đề + 3 giường, kể cả giường không có sự kiện
    const a01 = rows[1]!;
    expect(within(a01).getByText('A01')).toBeInTheDocument();
    expect(a01).toHaveTextContent('Bệnh nhân ngồi dậy: 2');
    expect(a01).toHaveTextContent('Bệnh nhân rời khỏi vùng giường: 1');
    expect(a01).toHaveTextContent('Xác nhận đúng: 1');
    expect(a01).toHaveTextContent('Bệnh nhân an toàn: 2');
    expect(
      within(a01)
        .getAllByRole('cell')
        .map((c) => c.textContent),
    ).toEqual(expect.arrayContaining(['1', '2', '3']));
    expect(rows[2]).toHaveTextContent('Không có sự kiện');
    expect(rows[3]).toHaveTextContent('A03 (Đã xóa)');
  });

  it('outstanding alerts rendered first', async () => {
    serve();
    renderWithProviders(<HandoverPage />, nurse, '/handover');
    const outstanding = await screen.findByTestId('handover-outstanding');
    const beds = screen.getByTestId('handover-beds');
    // Tồn đọng nằm trước bảng theo giường trong thứ tự tài liệu (HS §2.2).
    expect(
      outstanding.compareDocumentPosition(beds) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    const rows = within(outstanding).getAllByRole('row').slice(1);
    expect(rows.map((r) => within(r).getAllByRole('cell')[1]!.textContent)).toEqual(['A01', 'A02']);
    expect(rows[0]).toHaveTextContent('12/10/2026 14:38:34');
    expect(rows[0]).toHaveTextContent('Trần Văn Nam');
    expect(rows[1]).toHaveTextContent('Bệnh nhân đang ở mép giường');
  });

  it('alert resolved after the window shows "Đã xử lý sau ca"', async () => {
    serve({
      ...BODY,
      outstanding_alerts: [
        acknowledged(9, {
          status: 'RESOLVED',
          resolved_at: '2026-10-12T16:00:00Z', // sau `to` (15:00Z)
          resolved_by: { id: 2, full_name: 'Trần Văn Nam' },
        }),
      ],
    });
    renderWithProviders(<HandoverPage />, nurse, '/handover');
    const outstanding = await screen.findByTestId('handover-outstanding');
    expect(within(outstanding).getByText('Đã xử lý sau ca')).toBeInTheDocument();
    expect(within(outstanding).queryByText('Đã xử lý')).not.toBeInTheDocument();
  });

  it('shows empty outstanding text', async () => {
    serve({ ...BODY, outstanding_alerts: [] });
    renderWithProviders(<HandoverPage />, nurse, '/handover');
    expect(await screen.findByText('Không có cảnh báo tồn đọng')).toBeInTheDocument();
  });

  it('print button calls window.print', async () => {
    serve();
    const print = vitest.spyOn(window, 'print').mockImplementation(() => {});
    renderWithProviders(<HandoverPage />, nurse, '/handover');
    await screen.findByTestId('handover-beds');
    const button = screen.getByRole('button', { name: 'In' });
    expect(button).toHaveClass('no-print');
    await userEvent.click(button);
    expect(print).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/^In lúc /)).toHaveClass('print-only');
  });

  it('does not render internal codes', async () => {
    serve();
    const { container } = renderWithProviders(<HandoverPage />, nurse, '/handover');
    await screen.findByTestId('handover-beds');
    const text = container.textContent ?? '';
    for (const code of ['SIT_UP', 'BED_EXIT', 'BED_EDGE', 'CONFIRMED', 'PATIENT_SAFE', 'HIGH']) {
      expect(text).not.toContain(code);
    }
    expect(text).not.toMatch(/\b[A-Z]{2,}_[A-Z_]+\b/);
  });

  it('defaults to current shift and shows period title in Asia/Ho_Chi_Minh', async () => {
    at('2026-10-12T08:00:00Z'); // 15:00 giờ VN: ca chiều
    const calls = serve();
    renderWithProviders(<HandoverPage />, nurse, '/handover');
    expect(await screen.findByText('Ca chiều 14:00–22:00, 12/10/2026')).toBeInTheDocument();
    await waitFor(() => expect(calls.length).toBeGreaterThan(0));
    expect(calls.at(-1)?.get('shift_id')).toBe('2');
    expect(calls.at(-1)?.get('date')).toBe('2026-10-12');
  });

  it('night shift after midnight defaults to the start date', async () => {
    at('2026-10-12T18:30:00Z'); // 01:30 giờ VN ngày 13/10: ca đêm bắt đầu 12/10
    const calls = serve({ ...BODY, shift: SHIFTS[2]! });
    renderWithProviders(<HandoverPage />, nurse, '/handover');
    expect(await screen.findByText('Ca đêm 22:00–06:00, 12/10/2026')).toBeInTheDocument();
    expect(calls.at(-1)?.get('shift_id')).toBe('3');
    expect(calls.at(-1)?.get('date')).toBe('2026-10-12');
  });

  it('sends custom range as ISO with +07:00', async () => {
    const calls = serve({ ...BODY, shift: null });
    const u = userEvent.setup();
    renderWithProviders(<HandoverPage />, nurse, '/handover');
    await screen.findByTestId('handover-beds');
    await u.click(screen.getByText('Khoảng thời gian tùy chọn'));
    fireEvent.change(screen.getByLabelText('Từ'), { target: { value: '2026-10-12T17:00' } });
    fireEvent.change(screen.getByLabelText('Đến'), { target: { value: '2026-10-12T19:30' } });
    await waitFor(() => expect(calls.at(-1)?.get('to')).toBe('2026-10-12T19:30:00+07:00'));
    expect(calls.at(-1)?.get('from')).toBe('2026-10-12T17:00:00+07:00');
    expect(calls.at(-1)?.get('shift_id')).toBeNull();
    // Tiêu đề khoảng tùy chọn hiển thị theo giờ VN từ `from`/`to` của API.
    expect(
      await screen.findByText('Từ 12/10/2026 14:00:00 đến 12/10/2026 22:00:00'),
    ).toBeInTheDocument();
  });
});
