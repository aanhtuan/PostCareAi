// Thành phần dùng chung cho các mục danh mục trên màn hình Quản lý (F03; F37 dùng lại):
// khung mục, nút Sửa/Xóa/Khôi phục, nhãn trạng thái, hộp thoại xác nhận xóa mềm (QA#36).
import { Alert, Badge, Button, Card, Group, Modal, Stack, Table, Text, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import type { ReactNode } from 'react';

import { useCatalogLifecycle, type CatalogResource } from '../../api/hooks';
import { fmt, vi } from '../../i18n/vi';
import { apiErrorMessage } from './errorMessage';

export type DeleteTarget = { resource: CatalogResource; id: number; name: string };

export function ConfirmDeleteDialog({
  target,
  onClose,
}: {
  target: DeleteTarget | null;
  onClose: () => void;
}) {
  const lifecycle = useCatalogLifecycle();
  const close = () => {
    lifecycle.reset();
    onClose();
  };
  const message = apiErrorMessage(lifecycle.error);
  return (
    <Modal
      opened={target !== null}
      onClose={close}
      title={target ? fmt(vi.catalog.deleteTitle, { name: target.name }) : ''}
    >
      <Stack>
        <Text>{vi.catalog.confirmDelete}</Text>
        {message && (
          <Alert color="red" variant="light">
            {message}
          </Alert>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={close}>
            {vi.common.cancel}
          </Button>
          <Button
            color="red"
            loading={lifecycle.isPending}
            onClick={() =>
              target &&
              lifecycle.mutate(
                { resource: target.resource, id: target.id, action: 'delete' },
                {
                  onSuccess: () => {
                    notifications.show({
                      color: 'teal',
                      message: fmt(vi.catalog.deletedDone, { name: target.name }),
                    });
                    close();
                  },
                },
              )
            }
          >
            {vi.catalog.delete}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function UsageBadge({ active }: { active: boolean }) {
  return active ? (
    <Badge color="teal" variant="light">
      {vi.catalog.inUse}
    </Badge>
  ) : (
    <Badge color="gray" variant="filled">
      {vi.catalog.deleted}
    </Badge>
  );
}

type RowActionsProps = {
  active: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onRestore: () => void;
};

export function RowActions({ active, onEdit, onDelete, onRestore }: RowActionsProps) {
  if (!active) {
    return (
      <Button size="xs" variant="light" onClick={onRestore}>
        {vi.catalog.restore}
      </Button>
    );
  }
  return (
    <Group gap="xs" wrap="nowrap">
      <Button size="xs" variant="default" onClick={onEdit}>
        {vi.catalog.edit}
      </Button>
      <Button size="xs" color="red" variant="light" onClick={onDelete}>
        {vi.catalog.delete}
      </Button>
    </Group>
  );
}

export function Section({
  title,
  canAdd,
  onAdd,
  children,
}: {
  title: string;
  canAdd: boolean;
  onAdd: () => void;
  children: ReactNode;
}) {
  return (
    <Card withBorder component="section" aria-label={title}>
      <Group justify="space-between" mb="xs">
        <Title order={4}>{title}</Title>
        {canAdd && (
          <Button size="xs" onClick={onAdd}>
            {vi.catalog.add}
          </Button>
        )}
      </Group>
      <Table.ScrollContainer minWidth={480}>{children}</Table.ScrollContainer>
    </Card>
  );
}
