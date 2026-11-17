// Dữ liệu và MSW dùng chung cho test phiên theo dõi trên "Quản lý giường" (F04).
import { screen, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';

import type { BedOut, PatientOut, SessionOut, UserOut } from '../../api/types';
import { server } from '../../test/msw';
import { renderWithProviders } from '../../test/render';
import { ManagementPage } from './ManagementPage';

const created = '2026-11-17T00:00:00Z';
export const nurse: UserOut = {
  id: 1,
  username: 'nurse',
  full_name: 'Nguyễn Thị Hoa',
  role: 'NURSE',
  is_active: true,
  created_at: created,
};
export const doctor: UserOut = { ...nurse, id: 3, username: 'doctor', role: 'DOCTOR' };

// 07:38:34Z = 14:38:34 giờ Việt Nam
export const session10: SessionOut = {
  id: 10,
  bed_id: 1,
  bed_code: 'A01',
  patient_id: 1,
  patient_code: 'BN-001',
  camera_id: 1,
  started_at: '2026-10-12T07:38:34Z',
  started_by: { id: 1, full_name: 'Nguyễn Thị Hoa' },
  ended_at: null,
  ended_by: null,
  previous_session_id: null,
  previous_bed_code: null,
  next_session_id: null,
  transfer_reason: null,
  paused_at: null,
  paused_by: null,
};

function bed(id: number, code: string, extra: Partial<BedOut> = {}): BedOut {
  return {
    id,
    code,
    area: 'Khu hậu phẫu',
    is_active: true,
    camera: null,
    active_session: null,
    ...extra,
  };
}

export const a01 = bed(1, 'A01', {
  camera: { id: 1, name: 'Camera A01', status: 'ONLINE' },
  active_session: session10,
});
export const a02 = bed(2, 'A02');
export const a03 = bed(3, 'A03', {
  active_session: { ...session10, id: 11, bed_id: 3, bed_code: 'A03', patient_code: 'BN-003' },
});
export const a04 = bed(4, 'A04');

export const patients: PatientOut[] = [
  { id: 1, code: 'BN-001', note: null, is_active: true, active_session_id: 10 },
  { id: 2, code: 'BN-002', note: null, is_active: true, active_session_id: null },
  { id: 4, code: 'BN-004', note: null, is_active: false, active_session_id: null },
];

export type Call = { method: string; path: string; body: unknown };

type Options = { beds?: BedOut[]; post?: (path: string) => Response | undefined };

export function setupSessions(user: UserOut, options: Options = {}): Call[] {
  const calls: Call[] = [];
  const beds = options.beds ?? [a01, a02, a03];
  server.use(
    http.get('*/api/v1/beds', () => HttpResponse.json({ items: beds, total: beds.length })),
    http.get('*/api/v1/patients', () =>
      HttpResponse.json({ items: patients, total: patients.length }),
    ),
    http.get('*/api/v1/cameras', () => HttpResponse.json({ items: [], total: 0 })),
    http.post('*/api/v1/sessions*', async ({ request }) => {
      const url = new URL(request.url);
      const text = await request.text();
      calls.push({ method: 'POST', path: url.pathname, body: text ? JSON.parse(text) : null });
      const custom = options.post?.(url.pathname);
      if (custom) return custom;
      return HttpResponse.json(session10, {
        status: url.pathname.endsWith('/sessions') ? 201 : 200,
      });
    }),
  );
  renderWithProviders(<ManagementPage />, user);
  return calls;
}

export async function bedRow(code: string): Promise<HTMLElement> {
  const region = await screen.findByRole('region', { name: 'Giường' });
  const cell = await within(region).findByText(code);
  return cell.closest('tr') as HTMLElement;
}
