// "Kết thúc theo dõi" (F04 R9): luôn hỏi xác nhận trước khi gọi API.
import { Alert, Button, Group, Modal, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useEndSession } from '../../api/hooks';
import type { SessionOut } from '../../api/types';
import { vi } from '../../i18n/vi';
import { apiErrorMessage } from './errorMessage';

export function EndSessionButton({ session }: { session: SessionOut }) {
  const end = useEndSession();
  const [open, setOpen] = useState(false);
  const close = () => {
    end.reset();
    setOpen(false);
  };
  const error = apiErrorMessage(end.error);
  return (
    <>
      <Button size="xs" color="gray" onClick={() => setOpen(true)}>
        {vi.session.end}
      </Button>
      <Modal opened={open} onClose={close} title={vi.session.end}>
        <Stack>
          <Text>{vi.session.confirmEnd}</Text>
          {error && (
            <Alert color="red" variant="light">
              {error}
            </Alert>
          )}
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>
              {vi.common.cancel}
            </Button>
            <Button
              color="red"
              loading={end.isPending}
              onClick={() =>
                end.mutate(session.id, {
                  onSuccess: () => {
                    notifications.show({ color: 'teal', message: vi.session.ended });
                    close();
                  },
                })
              }
            >
              {vi.common.confirm}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
