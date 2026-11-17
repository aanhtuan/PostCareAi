// Thao tác dùng chung của màn hình Quản lý (F03; F37): báo lỗi API, khôi phục mục đã xóa.
import { notifications } from '@mantine/notifications';

import { useCatalogLifecycle, type CatalogResource } from '../../api/hooks';
import { fmt, vi } from '../../i18n/vi';
import { apiErrorMessage } from './errorMessage';

export function showError(err: unknown) {
  notifications.show({ color: 'red', message: apiErrorMessage(err) ?? vi.common.genericError });
}

/** Khôi phục một mục rồi báo kết quả; lỗi (ví dụ 409 chồng giờ) hiện `message` tiếng Việt. */
export function useRestore() {
  const lifecycle = useCatalogLifecycle();
  return (resource: CatalogResource, id: number, name: string) =>
    lifecycle.mutate(
      { resource, id, action: 'restore' },
      {
        onSuccess: () =>
          notifications.show({ color: 'teal', message: fmt(vi.catalog.restoredDone, { name }) }),
        onError: showError,
      },
    );
}
