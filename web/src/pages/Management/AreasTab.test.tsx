// F37 AC2, AC4: mục "Khu vực" trong Quản lý (R13; QA#36).
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import type { AreaOut, UserOut } from '../../api/types';
import { server } from '../../test/msw';
import { renderWithProviders } from '../../test/render';
import { AreasTab } from './AreasTab';

const admin: UserOut = {
  id: 4,
  username: 'admin',
  full_name: 'Phạm Thu Hà',
  role: 'ADMIN',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
const T = '2026-11-18T00:00:00Z';
const kv01: AreaOut = {
  id: 1,
  code: 'KV01',
  name: 'Khu hậu phẫu',
  is_active: true,
  created_at: T,
  bed_count: 3,
};
const hp9: AreaOut = {
  id: 9,
  code: 'HP-9',
  name: 'Hậu phẫu 9',
  is_active: false,
  created_at: T,
  bed_count: 0,
};

type Call = { method: string; path: string; body: unknown };

function setup(showDeleted: boolean, deleteResponse?: () => Response) {
  const calls: Call[] = [];
  const record = async (request: Request) => {
    const text = request.method === 'GET' ? '' : await request.text();
    calls.push({
      method: request.method,
      path: new URL(request.url).pathname,
      body: text ? JSON.parse(text) : null,
    });
  };
  server.use(
    http.get('*/api/v1/areas', ({ request }) => {
      const all = new URL(request.url).searchParams.get('include_inactive') === 'true';
      const items = all ? [kv01, hp9] : [kv01];
      return HttpResponse.json({ items, total: items.length });
    }),
    http.post('*/api/v1/areas', async ({ request }) => {
      await record(request);
      return HttpResponse.json(
        {
          error: {
            code: 'DUPLICATE_CODE',
            message: 'Mã khu vực KV01 đã tồn tại',
            details: { field: 'code' },
          },
        },
        { status: 409 },
      );
    }),
    http.delete('*/api/v1/areas/:id', async ({ request }) => {
      await record(request);
      return deleteResponse ? deleteResponse() : HttpResponse.json({ ...kv01, is_active: false });
    }),
    http.post('*/api/v1/areas/:id/restore', async ({ request }) => {
      await record(request);
      return HttpResponse.json({ ...hp9, is_active: true });
    }),
  );
  renderWithProviders(<AreasTab isAdmin showDeleted={showDeleted} />, admin);
  return calls;
}

async function row(code: string) {
  return (await screen.findByText(code)).closest('tr') as HTMLElement;
}

describe('AreasTab', () => {
  it('lists code, name and bed count', async () => {
    setup(false);
    const r = await row('KV01');
    expect(within(r).getByText('Khu hậu phẫu')).toBeInTheDocument();
    expect(within(r).getByText('3')).toBeInTheDocument();
    expect(within(r).getByText('Đang dùng')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Số giường' })).toBeInTheDocument();
  });

  it('AreasTab shows restore for deleted area', async () => {
    const calls = setup(true);
    const r = await row('HP-9');
    expect(within(r).getByText('Đã xóa')).toBeInTheDocument();
    expect(within(r).queryByRole('button', { name: 'Xóa' })).not.toBeInTheDocument();
    await userEvent.setup().click(within(r).getByRole('button', { name: 'Khôi phục' }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')?.path).toBe('/api/v1/areas/9/restore'),
    );
  });

  it('delete of area in use shows the API message', async () => {
    setup(false, () =>
      HttpResponse.json(
        {
          error: {
            code: 'AREA_IN_USE',
            message: 'Khu vực Khu hậu phẫu còn 3 giường đang dùng.',
            details: { bed_ids: [1, 2, 3] },
          },
        },
        { status: 409 },
      ),
    );
    const user = userEvent.setup();
    await user.click(within(await row('KV01')).getByRole('button', { name: 'Xóa' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Xóa' }));
    expect(
      await within(dialog).findByText('Khu vực Khu hậu phẫu còn 3 giường đang dùng.'),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/AREA_IN_USE/);
  });

  it('add form sends trimmed code and name and shows duplicate message', async () => {
    const calls = setup(false);
    const user = userEvent.setup();
    await row('KV01');
    await user.click(screen.getByRole('button', { name: 'Thêm' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText(/Mã khu vực/), ' KV01 ');
    await user.type(within(dialog).getByLabelText(/Tên khu vực/), 'Khác');
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }));
    expect(await within(dialog).findByText('Mã khu vực KV01 đã tồn tại')).toBeInTheDocument();
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ code: 'KV01', name: 'Khác' });
  });
});
