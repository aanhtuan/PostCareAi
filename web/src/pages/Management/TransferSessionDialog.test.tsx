// F04 AC5, R18: "Chuyển giường" trên "Quản lý giường".
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import {
  a01,
  a02,
  a03,
  a04,
  bedRow,
  doctor,
  nurse,
  session10,
  setupSessions,
} from './sessionTestUtils';

async function openTransfer(user: ReturnType<typeof userEvent.setup>) {
  await user.click(within(await bedRow('A01')).getByRole('button', { name: 'Chuyển giường' }));
  return screen.findByRole('dialog');
}

describe('TransferSessionDialog', () => {
  it('TransferSessionDialog transfers patient', async () => {
    const deleted = { ...a04, is_active: false };
    const calls = setupSessions(nurse, { beds: [a01, a02, a03, deleted] });
    const user = userEvent.setup();
    const dialog = await openTransfer(user);
    const confirm = within(dialog).getByRole('button', { name: 'Xác nhận' });
    expect(confirm).toBeDisabled();
    await user.click(within(dialog).getByRole('textbox', { name: 'Giường chuyển đến' }));
    // chỉ giường đang dùng, chưa có phiên mở, khác giường hiện tại
    const wanted = await screen.findByRole('option', { name: 'A02', hidden: true });
    expect(screen.queryByRole('option', { name: 'A01', hidden: true })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'A03', hidden: true })).not.toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'A04', hidden: true })).not.toBeInTheDocument();
    await user.click(wanted);
    expect(
      within(dialog).getByText('Kết thúc theo dõi ở giường A01 và bắt đầu ở giường A02?'),
    ).toBeInTheDocument();
    expect(confirm).toBeDisabled(); // còn thiếu lý do
    await user.type(within(dialog).getByRole('textbox', { name: /Lý do chuyển/ }), '  Đổi phòng ');
    await user.click(confirm);
    await waitFor(() =>
      expect(calls).toEqual([
        {
          method: 'POST',
          path: '/api/v1/sessions/10/transfer',
          body: { target_bed_id: 2, reason: 'Đổi phòng' },
        },
      ]),
    );
  });

  it('shows the API message when the target bed became busy', async () => {
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
    const dialog = await openTransfer(user);
    await user.click(within(dialog).getByRole('textbox', { name: 'Giường chuyển đến' }));
    await user.click(await screen.findByRole('option', { name: 'A02', hidden: true }));
    await user.type(within(dialog).getByRole('textbox', { name: /Lý do chuyển/ }), 'Đổi phòng');
    await user.click(within(dialog).getByRole('button', { name: 'Xác nhận' }));
    expect(
      await within(dialog).findByText('Giường này đang có phiên theo dõi'),
    ).toBeInTheDocument();
  });

  it('shows "Chuyển từ giường" for a transferred session', async () => {
    const moved = {
      ...a02,
      active_session: {
        ...session10,
        id: 12,
        bed_id: 2,
        bed_code: 'A02',
        previous_session_id: 10,
        previous_bed_code: 'A01',
        transfer_reason: 'Đổi phòng',
      },
    };
    setupSessions(nurse, { beds: [moved] });
    expect(within(await bedRow('A02')).getByText('Chuyển từ giường A01')).toBeInTheDocument();
  });

  it('doctor sees no transfer button', async () => {
    setupSessions(doctor);
    await bedRow('A01');
    expect(screen.queryByRole('button', { name: 'Chuyển giường' })).not.toBeInTheDocument();
  });
});
