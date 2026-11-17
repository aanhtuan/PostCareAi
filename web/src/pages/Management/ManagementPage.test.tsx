// F03 AC3, AC5: màn hình "Quản lý giường" (PDF §9.1; QA#15, QA#36).
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import type { BedOut, CameraOut, PatientOut, UserOut } from '../../api/types';
import { server } from '../../test/msw';
import { renderWithProviders } from '../../test/render';
import { ManagementPage } from './ManagementPage';

const admin: UserOut = {
  id: 4,
  username: 'admin',
  full_name: 'Phạm Thu Hà',
  role: 'ADMIN',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};
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
const T = '2026-10-12T07:38:34Z';

const a01: BedOut = {
  id: 1,
  code: 'A01',
  area: 'Khu hậu phẫu',
  is_active: true,
  camera: { id: 1, name: 'Camera A01', status: 'ONLINE' },
  active_session: {
    id: 10,
    bed_id: 1,
    bed_code: 'A01',
    patient_id: 1,
    patient_code: 'BN-001',
    camera_id: 1,
    started_at: T,
    started_by: { id: 1, full_name: 'Nguyễn Thị Hoa' },
    ended_at: null,
    ended_by: null,
  },
};
const a02: BedOut = {
  id: 2,
  code: 'A02',
  area: 'Khu hậu phẫu',
  is_active: true,
  camera: null,
  active_session: null,
};
const a09: BedOut = { ...a02, id: 9, code: 'A09', is_active: false };

const patients: PatientOut[] = [
  { id: 1, code: 'BN-001', note: null, is_active: true, active_session_id: 10 },
  { id: 2, code: 'BN-002', note: 'Sau mổ', is_active: true, active_session_id: null },
];
const cameras: CameraOut[] = [
  {
    id: 1,
    name: 'Camera A01',
    bed_id: 1,
    bed_code: 'A01',
    source_type: 'WEBCAM',
    source: '0',
    display_mode: 'BLUR',
    status: 'ONLINE',
    last_seen_at: null,
    config_version: 1,
    is_active: true,
  },
];

type Call = { method: string; path: string; search: string; body: unknown };

function setup(user: UserOut, overrides: { deleteBed?: () => Response } = {}) {
  const calls: Call[] = [];
  const record = async (request: Request) => {
    const url = new URL(request.url);
    const text = request.method === 'GET' ? '' : await request.text();
    calls.push({
      method: request.method,
      path: url.pathname,
      search: url.search,
      body: text ? JSON.parse(text) : null,
    });
    return url;
  };
  server.use(
    http.get('*/api/v1/beds', async ({ request }) => {
      const url = await record(request);
      const items =
        url.searchParams.get('include_inactive') === 'true' ? [a01, a02, a09] : [a01, a02];
      return HttpResponse.json({ items, total: items.length });
    }),
    http.get('*/api/v1/patients', async ({ request }) => {
      await record(request);
      return HttpResponse.json({ items: patients, total: patients.length });
    }),
    http.get('*/api/v1/cameras', async ({ request }) => {
      await record(request);
      return HttpResponse.json({ items: cameras, total: cameras.length });
    }),
    http.post('*/api/v1/beds', async ({ request }) => {
      await record(request);
      return HttpResponse.json(
        {
          error: {
            code: 'DUPLICATE_CODE',
            message: 'Mã giường A01 đã tồn tại',
            details: { field: 'code' },
          },
        },
        { status: 409 },
      );
    }),
    http.patch('*/api/v1/beds/:id', async ({ request }) => {
      await record(request);
      return HttpResponse.json({ ...a02, area: 'Khu hồi sức' });
    }),
    http.delete('*/api/v1/beds/:id', async ({ request }) => {
      await record(request);
      return overrides.deleteBed
        ? overrides.deleteBed()
        : HttpResponse.json({ ...a02, is_active: false });
    }),
    http.post('*/api/v1/beds/:id/restore', async ({ request }) => {
      await record(request);
      return HttpResponse.json({ ...a09, is_active: true });
    }),
  );
  renderWithProviders(<ManagementPage />, user);
  return calls;
}

async function bedRow(code: string) {
  const region = await screen.findByRole('region', { name: 'Giường' });
  const cell = await within(region).findByText(code);
  return cell.closest('tr') as HTMLElement;
}

describe('ManagementPage', () => {
  it('lists beds with camera and current patient', async () => {
    setup(nurse);
    const row = await bedRow('A01');
    expect(within(row).getByText('Camera A01 · Camera hoạt động')).toBeInTheDocument();
    expect(within(row).getByText('BN-001')).toBeInTheDocument();
    const row2 = await bedRow('A02');
    expect(within(row2).getByText('Chưa gắn camera')).toBeInTheDocument();
    expect(within(row2).getAllByText('—').length).toBeGreaterThan(0);
    const cams = screen.getByRole('region', { name: 'Camera' });
    expect(await within(cams).findByText('Webcam')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/WEBCAM|ONLINE|BLUR/);
  });

  it.each([nurse, doctor])('non-admin sees no edit buttons ($role)', async (user) => {
    setup(user);
    await bedRow('A01');
    for (const name of ['Thêm', 'Sửa', 'Xóa', 'Khôi phục']) {
      expect(screen.queryByRole('button', { name })).not.toBeInTheDocument();
    }
    expect(screen.getByText('Bạn chỉ có quyền xem danh mục.')).toBeInTheDocument();
  });

  it('admin sees add, edit and delete buttons', async () => {
    setup(admin);
    await bedRow('A01');
    for (const region of ['Giường', 'Bệnh nhân', 'Camera']) {
      const r = screen.getByRole('region', { name: region });
      expect(within(r).getByRole('button', { name: 'Thêm' })).toBeInTheDocument();
    }
    const row = await bedRow('A02');
    expect(within(row).getByRole('button', { name: 'Sửa' })).toBeInTheDocument();
    expect(within(row).getByRole('button', { name: 'Xóa' })).toBeInTheDocument();
  });

  it('delete asks for confirmation', async () => {
    const calls = setup(admin);
    const user = userEvent.setup();
    await user.click(within(await bedRow('A02')).getByRole('button', { name: 'Xóa' }));
    const dialog = await screen.findByRole('dialog');
    expect(
      within(dialog).getByText('Xóa mục này? Lịch sử theo dõi vẫn được giữ và có thể khôi phục.'),
    ).toBeInTheDocument();
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false);
    await user.click(within(dialog).getByRole('button', { name: 'Xóa' }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'DELETE')?.path).toBe('/api/v1/beds/2'),
    );
  });

  it('delete conflict shows the API message', async () => {
    setup(admin, {
      deleteBed: () =>
        HttpResponse.json(
          {
            error: {
              code: 'BED_HAS_OPEN_SESSION',
              message: 'Giường A02 đang có phiên theo dõi. Kết thúc phiên trước khi xóa.',
              details: { session_id: 3 },
            },
          },
          { status: 409 },
        ),
    });
    const user = userEvent.setup();
    await user.click(within(await bedRow('A02')).getByRole('button', { name: 'Xóa' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Xóa' }));
    expect(
      await within(dialog).findByText(
        'Giường A02 đang có phiên theo dõi. Kết thúc phiên trước khi xóa.',
      ),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/BED_HAS_OPEN_SESSION/);
  });

  it('shows restore for deleted items', async () => {
    const calls = setup(admin);
    const user = userEvent.setup();
    await bedRow('A01');
    expect(screen.queryByText('A09')).not.toBeInTheDocument();
    await user.click(screen.getByRole('switch', { name: 'Hiện mục đã xóa' }));
    const row = await bedRow('A09');
    expect(within(row).getByText('Đã xóa')).toBeInTheDocument();
    expect(within(row).queryByRole('button', { name: 'Xóa' })).not.toBeInTheDocument();
    expect(
      calls.some((c) => c.path === '/api/v1/beds' && c.search.includes('include_inactive=true')),
    ).toBe(true);
    await user.click(within(row).getByRole('button', { name: 'Khôi phục' }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST' && c.path.endsWith('/restore'))?.path).toBe(
        '/api/v1/beds/9/restore',
      ),
    );
  });

  it('add bed form sends code and area and shows duplicate message', async () => {
    const calls = setup(admin);
    const user = userEvent.setup();
    await bedRow('A01');
    const region = screen.getByRole('region', { name: 'Giường' });
    await user.click(within(region).getByRole('button', { name: 'Thêm' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText(/Mã giường/), 'A01');
    await user.type(within(dialog).getByLabelText(/Khu vực/), 'Khu hậu phẫu');
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }));
    expect(await within(dialog).findByText('Mã giường A01 đã tồn tại')).toBeInTheDocument();
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({
      code: 'A01',
      area: 'Khu hậu phẫu',
    });
  });

  it('edit bed sends form values via PATCH', async () => {
    const calls = setup(admin);
    const user = userEvent.setup();
    await user.click(within(await bedRow('A02')).getByRole('button', { name: 'Sửa' }));
    const dialog = await screen.findByRole('dialog');
    const area = within(dialog).getByLabelText(/Khu vực/);
    expect(area).toHaveValue('Khu hậu phẫu');
    await user.clear(area);
    await user.type(area, 'Khu hồi sức');
    await user.click(within(dialog).getByRole('button', { name: 'Lưu' }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'PATCH')).toMatchObject({
        path: '/api/v1/beds/2',
        body: { code: 'A02', area: 'Khu hồi sức' },
      }),
    );
  });
});
