// Review F03 #3 (R17): lịch sử của giường đã xóa vẫn chọn được ở Cảnh báo và Lịch sử theo dõi.
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import type { BedOut, UserOut } from '../../api/types';
import { server } from '../../test/msw';
import { renderWithProviders } from '../../test/render';
import { AlertsPage } from '../Alerts/AlertsPage';
import { TimelinePage } from './TimelinePage';

const nurse: UserOut = { id: 1, username: 'nurse', full_name: 'Nguyễn Thị Hoa', role: 'NURSE' };

const bed = (id: number, code: string, is_active: boolean): BedOut => ({
  id,
  code,
  area: 'Khu hậu phẫu',
  is_active,
  camera: null,
  active_session: null,
});

function serve() {
  server.use(
    http.get('*/api/v1/beds', ({ request }) => {
      const all = new URL(request.url).searchParams.get('include_inactive') === 'true';
      const items = all ? [bed(1, 'A01', true), bed(9, 'A09', false)] : [bed(1, 'A01', true)];
      return HttpResponse.json({ items, total: items.length });
    }),
    http.get('*/api/v1/alerts', () => HttpResponse.json({ items: [], total: 0 })),
    http.get('*/api/v1/sessions', () => HttpResponse.json({ items: [], total: 0 })),
    http.get('*/api/v1/timeline', () => HttpResponse.json({ items: [], total: 0 })),
  );
}

async function bedOptions() {
  const user = userEvent.setup();
  const input = screen.getByRole('textbox', { name: 'Giường' });
  // Danh sách giường tải bất đồng bộ; Mantine không mở dropdown rỗng nên thử lại tới khi có.
  await waitFor(async () => {
    if (!screen.queryByRole('option', { name: 'Giường A01', hidden: true }))
      await user.click(input);
    expect(screen.getByRole('option', { name: 'Giường A01', hidden: true })).toBeInTheDocument();
  });
  return {
    active: screen.getByRole('option', { name: 'Giường A01', hidden: true }),
    deleted: await screen.findByRole('option', { name: 'Giường A09 (Đã xóa)', hidden: true }),
  };
}

describe('deleted beds stay selectable for history', () => {
  it('AlertsPage lists deleted beds with a label', async () => {
    serve();
    renderWithProviders(<AlertsPage />, nurse);
    const { active, deleted } = await bedOptions();
    expect(active).toBeInTheDocument();
    expect(deleted).toBeInTheDocument();
  });

  it('TimelinePage lists deleted beds with a label', async () => {
    serve();
    renderWithProviders(<TimelinePage />, nurse, '/timeline');
    const { deleted } = await bedOptions();
    expect(deleted).toBeInTheDocument();
  });
});
