// F04 AC4, AC7, R9, R10: mở/kết thúc phiên và tạm dừng thu hình trên "Quản lý giường".
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { a01, a02, bedRow, doctor, nurse, session10, setupSessions } from './sessionTestUtils';

describe('StartSessionDialog', () => {
  it('StartSessionDialog starts session', async () => {
    const calls = setupSessions(nurse);
    const user = userEvent.setup();
    await user.click(within(await bedRow('A02')).getByRole('button', { name: 'Bắt đầu theo dõi' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('textbox', { name: 'Chọn bệnh nhân' }));
    // chỉ bệnh nhân đang dùng và chưa có phiên mở
    const wanted = await screen.findByRole('option', { name: 'BN-002', hidden: true });
    expect(screen.queryByRole('option', { name: 'BN-001', hidden: true })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'BN-004', hidden: true })).not.toBeInTheDocument();
    await user.click(wanted);
    await user.click(within(dialog).getByRole('button', { name: 'Xác nhận' }));
    await waitFor(() =>
      expect(calls).toEqual([
        { method: 'POST', path: '/api/v1/sessions', body: { bed_id: 2, patient_id: 2 } },
      ]),
    );
  });

  it('shows the API message on 409', async () => {
    setupSessions(nurse, {
      post: () =>
        HttpResponse.json(
          {
            error: {
              code: 'SESSION_ALREADY_OPEN',
              message: 'Giường này đang có phiên theo dõi',
              details: { conflict: 'bed', bed_id: 2 },
            },
          },
          { status: 409 },
        ),
    });
    const user = userEvent.setup();
    await user.click(within(await bedRow('A02')).getByRole('button', { name: 'Bắt đầu theo dõi' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('textbox', { name: 'Chọn bệnh nhân' }));
    await user.click(await screen.findByRole('option', { name: 'BN-002', hidden: true }));
    await user.click(within(dialog).getByRole('button', { name: 'Xác nhận' }));
    expect(
      await within(dialog).findByText('Giường này đang có phiên theo dõi'),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/SESSION_ALREADY_OPEN/);
  });

  it('shows start time HH:mm:ss in Vietnam time and camera note', async () => {
    setupSessions(nurse);
    expect(within(await bedRow('A01')).getByText('14:38:34')).toBeInTheDocument();
    expect(within(await bedRow('A02')).getByText('Chưa gắn camera')).toBeInTheDocument();
  });

  it('EndSessionButton asks for confirmation', async () => {
    const calls = setupSessions(nurse);
    const user = userEvent.setup();
    await user.click(
      within(await bedRow('A01')).getByRole('button', { name: 'Kết thúc theo dõi' }),
    );
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Kết thúc phiên theo dõi của giường này?')).toBeInTheDocument();
    expect(calls).toEqual([]);
    await user.click(within(dialog).getByRole('button', { name: 'Xác nhận' }));
    await waitFor(() => expect(calls.map((c) => c.path)).toEqual(['/api/v1/sessions/10/end']));
  });

  it('doctor sees no session buttons', async () => {
    setupSessions(doctor);
    await bedRow('A01');
    for (const name of [
      'Bắt đầu theo dõi',
      'Kết thúc theo dõi',
      'Chuyển giường',
      'Tạm dừng thu hình',
      'Tiếp tục thu hình',
    ]) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
    }
  });

  it('PauseCaptureButton pauses and resumes', async () => {
    const calls = setupSessions(nurse, { beds: [a01, a02] });
    const user = userEvent.setup();
    await user.click(
      within(await bedRow('A01')).getByRole('button', { name: 'Tạm dừng thu hình' }),
    );
    const dialog = await screen.findByRole('dialog');
    await user.type(
      within(dialog).getByRole('textbox', { name: 'Lý do tạm dừng (không bắt buộc)' }),
      'Thay đồ',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Xác nhận' }));
    await waitFor(() =>
      expect(calls).toEqual([
        { method: 'POST', path: '/api/v1/sessions/10/pause', body: { reason: 'Thay đồ' } },
      ]),
    );
  });

  it('paused session shows label and resume button', async () => {
    const paused = { ...a01, active_session: { ...session10, paused_at: '2026-10-12T08:00:00Z' } };
    const calls = setupSessions(nurse, { beds: [paused] });
    const user = userEvent.setup();
    const row = await bedRow('A01');
    expect(within(row).getByText('Đang tạm dừng thu hình')).toBeInTheDocument();
    expect(
      within(row).queryByRole('button', { name: 'Tạm dừng thu hình' }),
    ).not.toBeInTheDocument();
    await user.click(within(row).getByRole('button', { name: 'Tiếp tục thu hình' }));
    await waitFor(() => expect(calls.map((c) => c.path)).toEqual(['/api/v1/sessions/10/resume']));
  });
});
