import type { BedOut } from '../api/types';
import { fmt, vi } from '../i18n/vi';

/** Nhãn giường trong bộ chọn xem lịch sử: giường đã xóa vẫn chọn được, có nhãn "Đã xóa" (F03 R17). */
export function bedOptionLabel(bed: Pick<BedOut, 'code' | 'is_active'>): string {
  return fmt(bed.is_active ? vi.bed.title : vi.catalog.deletedBed, { code: bed.code });
}
