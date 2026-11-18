// F20 AC1, AC3, AC4: danh sách, bộ lọc, realtime, âm thanh, không hiện mã nội bộ.
import { Notifications } from '@mantine/notifications';
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi as vitest } from 'vitest';

import type { AlertOut, BedOut, EventOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { RealtimeProvider } from '../../realtime/RealtimeProvider';
import { acknowledged, makeAlert, nurse, otherNurse, T } from '../../test/alertFixtures';
import { server } from '../../test/msw';
import { renderWithProviders } from '../../test/render';
import { AlertsPage } from './AlertsPage';

// WebSocket giả: giữ handler để test đẩy message như gateway F18.
const ws = vitest.hoisted(() => ({
  handlers: null as null | { onMessage: (m: { type: string; payload: unknown }) => void },
}));
vitest.mock('../../realtime/wsClient', () => ({
  RealtimeClient: class {
    constructor(_token: string, handlers: typeof ws.handlers) {
      ws.handlers = handlers;
    }
    start() {}
    stop() {}
  },
}));
const sound = vitest.hoisted(() => ({ play: vitest.fn() }));
vitest.mock('../../realtime/sound', () => ({ playAlertSound: sound.play }));

const bed: BedOut = {
  id: 3,
  code: 'A03',
  area: { id: 1, code: 'KV01', name: 'Khu hậu phẫu' },
  is_active: true,
  camera: null,
  active_session: null,
};

type Store = { items: AlertOut[]; queries: URLSearchParams[] };

function serve(items: AlertOut[]): Store {
  const store: Store = { items, queries: [] };
  server.use(
    http.get('*/api/v1/beds', () => HttpResponse.json({ items: [bed], total: 1 })),
    http.get('*/api/v1/alerts', ({ request }) => {
      store.queries.push(new URL(request.url).searchParams);
      return HttpResponse.json({ items: store.items, total: store.items.length });
    }),
  );
  return store;
}

function renderPage() {
  return renderWithProviders(
    <RealtimeProvider>
      <Notifications />
      <AlertsPage />
    </RealtimeProvider>,
    nurse,
  );
}

const cards = () => screen.getAllByText(/^Giường A0\d - /).map((h) => h.textContent);

function push(type: string, payload: unknown) {
  act(() => ws.handlers?.onMessage({ type, payload }));
}

function createdPayload(alert: AlertOut): { alert: AlertOut; event: EventOut } {
  return {
    alert,
    event: {
      id: alert.event.id,
      event_uid: `u${alert.id}`,
      session_id: alert.session?.id ?? null,
      bed_id: alert.bed?.id ?? null,
      bed_code: alert.bed?.code ?? null,
      camera_id: 1,
      code: alert.event.code,
      priority: alert.event.priority,
      occurred_at: alert.event.occurred_at,
      detected_at: T,
      created_at: T,
      confidence: 0.9,
      observation_quality: 'GOOD',
      explanation: {},
      alert_id: alert.id,
      alert_status: alert.status,
    },
  };
}

beforeEach(() => {
  sound.play.mockReset();
  ws.handlers = null;
});

describe('AlertsPage', () => {
  it('renders alerts with bed, priority, status', async () => {
    serve([
      makeAlert(1),
      acknowledged(2, {
        bed: { id: 4, code: 'A04' },
        event: {
          id: 2,
          code: 'SIT_UP',
          priority: 'MEDIUM',
          occurred_at: T,
          observation_quality: 'GOOD',
        },
      }),
    ]);
    renderPage();
    expect(await screen.findByText('Giường A03 - Cảnh báo ưu tiên cao')).toBeInTheDocument();
    expect(screen.getByText('Giường A04 - Cảnh báo cần chú ý')).toBeInTheDocument();
    expect(
      screen.getByText(fmt(vi.alerts.sentence, { event: vi.event.BED_EXIT, time: '14:38:34' })),
    ).toBeInTheDocument();
    expect(screen.getAllByText(vi.alertStatus.PENDING).length).toBeGreaterThan(0);
    expect(screen.getAllByText(vi.alertStatus.ACKNOWLEDGED).length).toBeGreaterThan(0);
    expect(screen.getAllByText(vi.priority.HIGH).length).toBeGreaterThan(0);
    expect(screen.getByText(new RegExp(otherNurse.full_name))).toBeInTheDocument();
  });

  it('keeps unresolved alerts on top', async () => {
    // API (F19 R9) đã sắp chưa xử lý trước; trang giữ nguyên thứ tự, không sắp lại.
    serve([
      makeAlert(1, { bed: { id: 1, code: 'A01' } }),
      acknowledged(2, { bed: { id: 2, code: 'A02' } }),
      makeAlert(3, { status: 'RESOLVED', bed: { id: 5, code: 'A05' } }),
    ]);
    renderPage();
    await screen.findByText(/^Giường A01 - /);
    expect(cards().map((c) => c?.slice(0, 11))).toEqual([
      'Giường A01 ',
      'Giường A02 ',
      'Giường A05 ',
    ]);
  });

  it('resolved without outcome shows Chưa ghi kết quả', async () => {
    serve([makeAlert(1, { status: 'RESOLVED', outcome: null })]);
    renderPage();
    expect(
      await screen.findByText(`${vi.alerts.outcomeLabel}: ${vi.alerts.noOutcome}`),
    ).toBeInTheDocument();
  });

  it('shows empty text when no alert matches', async () => {
    serve([]);
    renderPage();
    expect(await screen.findByText(vi.alerts.empty)).toBeInTheDocument();
  });

  it('sends filter params to API', async () => {
    const store = serve([makeAlert(1)]);
    const user = userEvent.setup();
    renderPage();
    await screen.findByText(/^Giường A03 - /);

    await user.click(screen.getByRole('textbox', { name: vi.alerts.status }));
    await user.click(
      await screen.findByRole('option', { name: vi.alertStatus.PENDING, hidden: true }),
    );
    await user.click(screen.getByRole('textbox', { name: vi.alerts.priority }));
    await user.click(await screen.findByRole('option', { name: vi.priority.HIGH, hidden: true }));
    await user.click(screen.getByRole('textbox', { name: vi.common.bed }));
    await user.click(await screen.findByRole('option', { name: 'Giường A03', hidden: true }));
    fireEvent.change(screen.getByLabelText(vi.common.from), {
      target: { value: '2026-10-12T14:00' },
    });
    fireEvent.change(screen.getByLabelText(vi.common.to), {
      target: { value: '2026-10-12T15:00' },
    });

    await waitFor(() => {
      const q = store.queries.at(-1)!;
      expect(q.getAll('status')).toEqual(['PENDING']);
      expect(q.getAll('priority')).toEqual(['HIGH']);
      expect(q.get('bed_id')).toBe('3');
      expect(q.get('from')).toBe('2026-10-12T14:00:00+07:00');
      expect(q.get('to')).toBe('2026-10-12T15:00:00+07:00');
    });
  });

  it('high priority card is highlighted', async () => {
    serve([
      makeAlert(1),
      makeAlert(2, {
        bed: { id: 4, code: 'A04' },
        event: {
          id: 2,
          code: 'SIT_UP',
          priority: 'MEDIUM',
          occurred_at: T,
          observation_quality: 'GOOD',
        },
      }),
    ]);
    renderPage();
    const high = (await screen.findByText(/^Giường A03 - /)).closest('[data-priority]');
    const medium = screen.getByText(/^Giường A04 - /).closest('[data-priority]');
    expect(high).toHaveAttribute('data-priority', 'HIGH');
    expect(medium).toHaveAttribute('data-priority', 'MEDIUM');
    // Ưu tiên cao: viền đỏ đậm; Cần chú ý: viền thường.
    expect(high?.getAttribute('style')).toContain('--mantine-color-red-6');
    expect(medium?.getAttribute('style') ?? '').not.toContain('--mantine-color-red-6');
  });

  it('detail dialog shows people, outcome and links without technical values', async () => {
    serve([
      acknowledged(1, {
        outcome: 'CONFIRMED',
        outcome_by: otherNurse,
        outcome_at: '2026-10-12T07:40:00Z',
        note: 'Đã đỡ bệnh nhân về giường',
      }),
    ]);
    renderPage();
    await userEvent.setup().click(await screen.findByRole('button', { name: vi.alerts.detail }));
    const dialog = await screen.findByRole('dialog', { name: vi.alerts.detailTitle });
    const d = within(dialog);
    expect(d.getByText('BN-003')).toBeInTheDocument();
    expect(d.getByText(vi.quality.GOOD)).toBeInTheDocument();
    expect(d.getAllByText(new RegExp(otherNurse.full_name)).length).toBe(2);
    expect(d.getByText(vi.outcome.CONFIRMED)).toBeInTheDocument();
    expect(d.getByText('Đã đỡ bệnh nhân về giường')).toBeInTheDocument();
    expect(d.getByRole('link', { name: vi.alerts.openLive })).toHaveAttribute(
      'href',
      '/beds/3/live',
    );
    expect(d.getByRole('link', { name: vi.alerts.openTimeline })).toHaveAttribute(
      'href',
      '/timeline?bed=3&session=5',
    );
  });

  it('does not render internal codes', async () => {
    serve([
      makeAlert(1),
      acknowledged(2, { outcome: 'FALSE_ALARM' }),
      makeAlert(3, { status: 'RESOLVED', outcome: 'PATIENT_SAFE' }),
    ]);
    const { container } = renderPage();
    await screen.findAllByText(/^Giường A03 - /);
    await userEvent.setup().click(screen.getAllByRole('button', { name: vi.alerts.detail })[0]);
    await screen.findByRole('dialog');
    const text = `${container.textContent} ${document.body.textContent}`;
    expect(text).not.toMatch(/\b[A-Z]{2,}(?:_[A-Z]+)+\b/);
    for (const code of ['PENDING', 'ACKNOWLEDGED', 'RESOLVED', 'HIGH', 'MEDIUM', 'GOOD']) {
      expect(text).not.toMatch(new RegExp(`\\b${code}\\b`));
    }
  });

  it('new alert appears after alert.created message', async () => {
    const store = serve([]);
    renderPage();
    expect(await screen.findByText(vi.alerts.empty)).toBeInTheDocument();
    const created = makeAlert(9, { bed: { id: 7, code: 'A07' } });
    store.items = [created];
    push('alert.created', createdPayload(created));
    expect(await screen.findByText('Giường A07 - Cảnh báo ưu tiên cao')).toBeInTheDocument();
  });

  it('alert.updated refreshes card status without reload', async () => {
    const store = serve([makeAlert(1)]);
    renderPage();
    expect(await screen.findByRole('button', { name: vi.alerts.acknowledge })).toBeInTheDocument();
    store.items = [acknowledged(1)];
    push('alert.updated', acknowledged(1));
    expect(await screen.findByRole('button', { name: vi.alerts.resolve })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: vi.alerts.acknowledge })).not.toBeInTheDocument();
  });

  it('409 shows message and refreshes the card', async () => {
    const store = serve([makeAlert(1)]);
    server.use(
      http.post('*/api/v1/alerts/1/acknowledge', () => {
        store.items = [acknowledged(1)];
        return HttpResponse.json(
          {
            error: {
              code: 'ALERT_ALREADY_ACKNOWLEDGED',
              message: `Cảnh báo đã được tiếp nhận bởi ${otherNurse.full_name}`,
              details: {},
            },
          },
          { status: 409 },
        );
      }),
    );
    renderPage();
    await userEvent
      .setup()
      .click(await screen.findByRole('button', { name: vi.alerts.acknowledge }));
    expect(
      await screen.findByText(`Cảnh báo đã được tiếp nhận bởi ${otherNurse.full_name}`),
    ).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: vi.alerts.resolve })).toBeInTheDocument();
  });

  it('high priority plays sound once', async () => {
    serve([]);
    renderPage();
    await screen.findByText(vi.alerts.empty);
    // Cùng một cảnh báo gửi lại (ví dụ sau khi kết nối lại) không phát âm thanh lần nữa.
    push('alert.created', createdPayload(makeAlert(9)));
    push('alert.created', createdPayload(makeAlert(9)));
    expect(sound.play).toHaveBeenCalledTimes(1);
  });

  it('medium priority does not play sound', async () => {
    serve([]);
    renderPage();
    await screen.findByText(vi.alerts.empty);
    const medium = makeAlert(9, {
      event: {
        id: 9,
        code: 'SIT_UP',
        priority: 'MEDIUM',
        occurred_at: T,
        observation_quality: 'GOOD',
      },
    });
    push('alert.created', createdPayload(medium));
    push('alert.updated', makeAlert(10));
    expect(sound.play).not.toHaveBeenCalled();
  });
});
