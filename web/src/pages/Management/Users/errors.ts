import { notifications } from '@mantine/notifications';

import { ApiError } from '../../../api/client';
import { vi } from '../../../i18n/vi';

/** 409 (trùng tên, ADMIN cuối cùng, tự khóa…) hiện `message` tiếng Việt của API (F35 R11). */
export function showUserError(err: unknown) {
  const message =
    err instanceof ApiError
      ? err.status === 403
        ? vi.common.forbidden
        : err.message
      : vi.common.genericError;
  notifications.show({ color: 'red', message });
}
