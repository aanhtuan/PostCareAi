// Dữ liệu giả dùng chung cho test màn hình Cảnh báo (F20).
import type { AlertOut, UserOut } from '../api/types';

export const T = '2026-10-12T07:38:34Z'; // 14:38:34 giờ Việt Nam

export const nurse: UserOut = {
  id: 1,
  username: 'nurse',
  full_name: 'Nguyễn Thị Hoa',
  role: 'NURSE',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};

export const otherNurse = { id: 2, full_name: 'Trần Văn Nam' };

export const doctor: UserOut = {
  id: 3,
  username: 'doctor',
  full_name: 'Lê Quốc Bảo',
  role: 'DOCTOR',
  is_active: true,
  created_at: '2026-11-17T00:00:00Z',
};

export function makeAlert(id: number, extra: Partial<AlertOut> = {}): AlertOut {
  return {
    id,
    status: 'PENDING',
    outcome: null,
    note: null,
    created_at: T,
    acknowledged_by: null,
    acknowledged_at: null,
    outcome_by: null,
    outcome_at: null,
    resolved_by: null,
    resolved_at: null,
    event: {
      id: id + 100,
      code: 'BED_EXIT',
      priority: 'HIGH',
      occurred_at: T,
      observation_quality: 'GOOD',
    },
    bed: { id: 3, code: 'A03' },
    session: { id: 5, patient_code: 'BN-003' },
    ...extra,
  };
}

export function acknowledged(id: number, extra: Partial<AlertOut> = {}): AlertOut {
  return makeAlert(id, {
    status: 'ACKNOWLEDGED',
    acknowledged_by: otherNurse,
    acknowledged_at: '2026-10-12T07:39:00Z',
    ...extra,
  });
}
