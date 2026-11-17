// "Tạm dừng thu hình" / "Tiếp tục thu hình" theo phiên (F04 R19–R22; F36 R21).
import { Alert, Button, Group, Modal, Stack, TextInput } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useCaptureToggle } from '../../api/hooks';
import type { SessionOut } from '../../api/types';
import { vi } from '../../i18n/vi';
import { apiErrorMessage } from './errorMessage';

export function PauseCaptureButton({ session }: { session: SessionOut }) {
  const toggle = useCaptureToggle();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const paused = session.paused_at !== null;
  const close = () => {
    toggle.reset();
    setReason('');
    setOpen(false);
  };
  const error = apiErrorMessage(toggle.error);

  if (paused) {
    return (
      <Button
        size="xs"
        variant="light"
        loading={toggle.isPending}
        onClick={() =>
          toggle.mutate(
            { sessionId: session.id, pause: false },
            {
              onSuccess: () =>
                notifications.show({ color: 'teal', message: vi.capture.resumedDone }),
              onError: (err) =>
                notifications.show({
                  color: 'red',
                  message: apiErrorMessage(err) ?? vi.common.genericError,
                }),
            },
          )
        }
      >
        {vi.capture.resume}
      </Button>
    );
  }
  return (
    <>
      <Button size="xs" variant="light" color="orange" onClick={() => setOpen(true)}>
        {vi.capture.pause}
      </Button>
      <Modal opened={open} onClose={close} title={vi.capture.pause}>
        <Stack>
          <TextInput
            label={vi.capture.pauseReason}
            value={reason}
            onChange={(e) => setReason(e.currentTarget.value)}
            maxLength={1000}
          />
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
              color="orange"
              loading={toggle.isPending}
              onClick={() =>
                toggle.mutate(
                  { sessionId: session.id, pause: true, reason },
                  {
                    onSuccess: () => {
                      notifications.show({ color: 'teal', message: vi.capture.pausedDone });
                      close();
                    },
                  },
                )
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
