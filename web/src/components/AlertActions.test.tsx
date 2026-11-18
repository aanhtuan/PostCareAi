// F20 AC2, AC5: bộ nút theo trạng thái (PDF §9.2; ADR-0007) và phân quyền (QA#18).
import { Notifications } from '@mantine/notifications';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi as vitest } from 'vitest';

import type { AlertOut, UserOut } from '../api/types';
import { vi } from '../i18n/vi';
import { acknowledged, doctor, makeAlert, nurse, otherNurse } from '../test/alertFixtures';
import { server } from '../test/msw';
import { renderWithProviders } from '../test/render';
import { AlertActions } from './AlertActions';

function renderActions(alert: AlertOut, user: UserOut = nurse, onDetail = vitest.fn()) {
  renderWithProviders(
    <>
      <Notifications />
      <AlertActions alert={alert} onDetail={onDetail} />
    </>,
    user,
  );
  return onDetail;
}

const buttonNames = () => screen.queryAllByRole('button').map((b) => b.textContent);

type Captured = { path: string; body: unknown };

function captureAction(status = 200, payload: Record<string, unknown> = {}) {
  const calls: Captured[] = [];
  server.use(
    http.post('*/api/v1/alerts/:id/:action', async ({ request }) => {
      const text = await request.text();
      calls.push({ path: new URL(request.url).pathname, body: text ? JSON.parse(text) : null });
      return HttpResponse.json(payload, { status });
    }),
  );
  return calls;
}

describe('AlertActions', () => {
  it('pending shows acknowledge and detail', async () => {
    const onDetail = renderActions(makeAlert(1));
    expect(buttonNames()).toEqual([vi.alerts.acknowledge, vi.alerts.detail]);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: vi.alerts.detail }));
    expect(onDetail).toHaveBeenCalledOnce();
  });

  it('acknowledged shows three outcomes, resolve and note', () => {
    renderActions(acknowledged(1, { outcome: 'FALSE_ALARM' }));
    expect(buttonNames()).toEqual([
      vi.alerts.confirmed,
      vi.alerts.falseAlarm,
      vi.alerts.patientSafe,
      vi.alerts.resolve,
      vi.alerts.detail,
    ]);
    expect(screen.getByRole('textbox', { name: vi.alerts.note })).toBeInTheDocument();
    // Nút kết quả đang chọn có dấu hiệu rõ, đọc được bằng trình đọc màn hình.
    expect(screen.getByRole('button', { name: vi.alerts.falseAlarm })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: vi.alerts.confirmed })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
  });

  it('resolved shows only detail', () => {
    renderActions(makeAlert(1, { status: 'RESOLVED', outcome: null }));
    expect(buttonNames()).toEqual([vi.alerts.detail]);
  });

  it('buttons call correct endpoints', async () => {
    const user = userEvent.setup();
    const calls = captureAction();
    renderActions(makeAlert(4));
    await user.click(screen.getByRole('button', { name: vi.alerts.acknowledge }));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]).toEqual({ path: '/api/v1/alerts/4/acknowledge', body: null });
  });

  it('outcome and resolve send the note', async () => {
    const user = userEvent.setup();
    const calls = captureAction();
    renderActions(acknowledged(4));
    await user.type(screen.getByRole('textbox', { name: vi.alerts.note }), 'Đã kiểm tra');
    await user.click(screen.getByRole('button', { name: vi.alerts.patientSafe }));
    await waitFor(() => expect(calls).toHaveLength(1));
    await user.click(screen.getByRole('button', { name: vi.alerts.resolve }));
    await waitFor(() => expect(calls).toHaveLength(2));
    expect(calls).toEqual([
      {
        path: '/api/v1/alerts/4/outcome',
        body: { outcome: 'PATIENT_SAFE', note: 'Đã kiểm tra' },
      },
      { path: '/api/v1/alerts/4/resolve', body: { note: 'Đã kiểm tra' } },
    ]);
  });

  it('doctor sees only detail button', () => {
    renderActions(makeAlert(1), doctor);
    expect(buttonNames()).toEqual([vi.alerts.detail]);
    renderActions(acknowledged(2), doctor);
    expect(screen.queryByRole('button', { name: vi.alerts.resolve })).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('shows 409 message with acknowledger name', async () => {
    const message = `Cảnh báo đã được tiếp nhận bởi ${otherNurse.full_name}`;
    captureAction(409, {
      error: {
        code: 'ALERT_ALREADY_ACKNOWLEDGED',
        message,
        details: { acknowledged_by: otherNurse, acknowledged_at: '2026-10-12T07:39:00Z' },
      },
    });
    renderActions(makeAlert(1));
    await userEvent.setup().click(screen.getByRole('button', { name: vi.alerts.acknowledge }));
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByText('ALERT_ALREADY_ACKNOWLEDGED')).not.toBeInTheDocument();
  });

  it('shows forbidden message on 403', async () => {
    captureAction(403, { error: { code: 'FORBIDDEN', message: 'x', details: {} } });
    renderActions(makeAlert(1));
    await userEvent.setup().click(screen.getByRole('button', { name: vi.alerts.acknowledge }));
    expect(await screen.findByText(vi.common.forbidden)).toBeInTheDocument();
  });
});
