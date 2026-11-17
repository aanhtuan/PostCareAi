// Khung chung cho form thêm/sửa danh mục (F03): hộp thoại, nút Lưu/Hủy, lỗi API tiếng Việt.
import { Alert, Button, Group, Modal, Stack } from '@mantine/core';
import type { FormEvent, ReactNode } from 'react';

import { vi } from '../../i18n/vi';
import { apiErrorMessage } from './errorMessage';

type Props = {
  opened: boolean;
  title: string;
  onClose: () => void;
  onSubmit: () => void;
  saving: boolean;
  error: unknown;
  children: ReactNode;
};

export function CatalogFormModal({
  opened,
  title,
  onClose,
  onSubmit,
  saving,
  error,
  children,
}: Props) {
  const message = apiErrorMessage(error);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit();
  };
  return (
    <Modal opened={opened} onClose={onClose} title={title}>
      <form onSubmit={submit} noValidate>
        <Stack>
          {children}
          {message && (
            <Alert color="red" variant="light">
              {message}
            </Alert>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {vi.common.cancel}
            </Button>
            <Button type="submit" loading={saving}>
              {vi.catalog.save}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
