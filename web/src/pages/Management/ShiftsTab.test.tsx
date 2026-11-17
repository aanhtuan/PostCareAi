// F37 AC3, AC4: mục "Ca trực" trong Quản lý (R13; QA#19, QA#36).
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { notifications } from '@mantine/notifications';
import { describe, expect, it, vi } from 'vitest';

import type { ShiftOut, UserOut } from '../../api/types';
import { server } from '../../test/msw';
import { renderWithProviders } from '../../test/render';
import { ShiftsTab } from './ShiftsTab';

const admin: UserOut = {
  id: 4,
  username: 'admin',
  full_name: 'Phạm Thu Hà',
  role: 'ADMIN',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
const nurse: UserOut = { ...admin, id: 1, username: 'nurse', role: 'NURSE' };

const shifts: ShiftOut[] = [
  { id: 1, name: 'Ca sáng', start_time: '06:00:00', end_time: '14:00:00', is_active: true },
  { id: 2, name: 'Ca chiều', start_time: '14:00:00', end_time: '22:00:00', is_active: true },
  { id: 3, name: 'Ca đêm', start_time: '22:00:00', end_time: '06:00:00', is_active: true },
];
const old: ShiftOut = {
  id: 7,
  name: 'Ca cũ',
  start_time: '07:00:00',
  end_time: '13:00:00',
  is_active: false,
};

type Call = { method: string; path: string; body: unknown };

function setup(user: UserOut, showDeleted = false) {
  const calls: Call[] = [];
  const record = async (request: Request) => {
    const text = await request.text();
    calls.push({
      method: request.method,
      path: new URL(request.url).pathname,
      body: text ? JSON.parse(text) : null,
    });
  };
  server.use(
    http.get('*/api/v1/shifts', ({ request }) => {
      const all = new URL(request.url).searchParams.get('include_inactive') === 'true';
      return HttpResponse.json(all ? [...shifts, old] : shifts);
    }),
    http.post('*/api/v1/shifts', async ({ request }) => {
      await record(request);
      return HttpResponse.json(
        {
          error: {
            code: 'SHIFT_OVERLAP',
            message: 'Giờ ca bị chồng với: Ca đêm (22:00–06:00)',
            details: { conflicting_shift_ids: [3] },
          },
        },
        { status: 409 },
      );
    }),
    http.patch('*/api/v1/shifts/:id', async ({ request }) => {
      await record(request);
      return HttpResponse.json(shifts[0]);
    }),
    http.post('*/api/v1/shifts/:id/restore', async ({ request }) => {
      await record(request);
      return HttpResponse.json(
        {
          error: {
            code: 'SHIFT_OVERLAP',
            message: 'Giờ ca bị chồng với: Ca sáng (06:00–14:00)',
            details: { conflicting_shift_ids: [1] },
          },
        },
        { status: 409 },
      );
    }),
  );
  renderWithProviders(
    <ShiftsTab isAdmin={user.role === 'ADMIN'} showDeleted={showDeleted} />,
    user,
  );
  return calls;
}

async function row(name: string) {
  return (await screen.findByText(name)).closest('tr') as HTMLElement;
}

describe('ShiftsTab', () => {
  it('ShiftsTab marks overnight shift', async () => {
    setup(admin);
    const night = await row('Ca đêm');
    expect(within(night).getByText('22:00')).toBeInTheDocument();
    expect(within(night).getByText(/qua nửa đêm/)).toBeInTheDocument();
    const day = await row('Ca sáng');
    expect(within(day).queryByText(/qua nửa đêm/)).not.toBeInTheDocument();
    expect(within(day).getByText('06:00')).toBeInTheDocument();
  });

  it('non-admin sees no edit buttons', async () => {
    setup(nurse);
    await row('Ca sáng');
    for (const name of ['Thêm', 'Sửa', 'Xóa', 'Khôi phục']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
    }
  });

  it('add overlapping shift shows the API message', async () => {
    const calls = setup(admin);
    const user = userEvent.setup();
    await row('Ca sáng');
    await user.click(screen.getByRole('button', { name: 'Thêm' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText(/Tên ca/), 'Ca rạng sáng');
    await user.type(within(dialog).getByLabelText(/Bắt đầu/), '04:00');
    await user.type(within(dialog).getByLabelText(/Kết thúc/), '07:00');
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }));
    expect(
      await within(dialog).findByText('Giờ ca bị chồng với: Ca đêm (22:00–06:00)'),
    ).toBeInTheDocument();
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      name: 'Ca rạng sáng',
      start_time: '04:00',
      end_time: '07:00',
    });
    expect(document.body.textContent).not.toMatch(/SHIFT_OVERLAP/);
  });

  it('same start and end is rejected before sending', async () => {
    const calls = setup(admin);
    const user = userEvent.setup();
    await row('Ca sáng');
    await user.click(screen.getByRole('button', { name: 'Thêm' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText(/Tên ca/), 'Ca lỗi');
    await user.type(within(dialog).getByLabelText(/Bắt đầu/), '08:00');
    await user.type(within(dialog).getByLabelText(/Kết thúc/), '08:00');
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }));
    expect(
      await within(dialog).findByText('Giờ kết thúc phải khác giờ bắt đầu'),
    ).toBeInTheDocument();
    expect(calls).toEqual([]);
  });

  it('edit shows warning about past handovers and sends PATCH', async () => {
    const calls = setup(admin);
    const user = userEvent.setup();
    await user.click(within(await row('Ca sáng')).getByRole('button', { name: 'Sửa' }));
    const dialog = await screen.findByRole('dialog');
    expect(
      within(dialog).getByText('Sửa giờ ca sẽ thay đổi cách tổng hợp bàn giao của các ngày trước'),
    ).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'PATCH')).toMatchObject({
        path: '/api/v1/shifts/1',
        body: { name: 'Ca sáng', start_time: '06:00', end_time: '14:00' },
      }),
    );
  });

  it('restore conflict shows the API message', async () => {
    const show = vi.spyOn(notifications, 'show');
    setup(admin, true);
    const user = userEvent.setup();
    const r = await row('Ca cũ');
    expect(within(r).getByText('Đã xóa')).toBeInTheDocument();
    await user.click(within(r).getByRole('button', { name: 'Khôi phục' }));
    await waitFor(() =>
      expect(show).toHaveBeenCalledWith(
        expect.objectContaining({ message: 'Giờ ca bị chồng với: Ca sáng (06:00–14:00)' }),
      ),
    );
    show.mockRestore();
  });
});
