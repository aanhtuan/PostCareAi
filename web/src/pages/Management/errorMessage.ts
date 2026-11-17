import { ApiError } from '../../api/client';
import { vi } from '../../i18n/vi';

/** Lỗi API → câu hiển thị: dùng `message` tiếng Việt của API, không hiện mã lỗi (F03 R12). */
export function apiErrorMessage(err: unknown): string | null {
  if (!err) return null;
  if (err instanceof ApiError) return err.status === 403 ? vi.common.forbidden : err.message;
  return vi.common.genericError;
}
