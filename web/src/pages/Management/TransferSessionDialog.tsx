// "Chuyển giường" (F04 R18; QA#36): chọn giường đích đang dùng, chưa có phiên mở, nhập lý do.
// Hộp thoại ghi rõ "Kết thúc theo dõi ở giường A01 và bắt đầu ở giường A02?" trước khi xác nhận.
import { Alert, Button, Group, Modal, Select, Stack, Text, Textarea } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { useTransferSession } from '../../api/hooks';
import type { BedOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { apiErrorMessage } from './errorMessage';

type Props = { bed: BedOut | null; beds: BedOut[]; onClose: () => void };

export function TransferSessionDialog({ bed, beds, onClose }: Props) {
  const transfer = useTransferSession();
  const [targetId, setTargetId] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const free = beds.filter((b) => b.is_active && b.active_session === null && b.id !== bed?.id);
  const target = free.find((b) => String(b.id) === targetId) ?? null;
  const session = bed?.active_session ?? null;
  const close = () => {
    transfer.reset();
    setTargetId(null);
    setReason('');
    onClose();
  };
  const error = apiErrorMessage(transfer.error);

  return (
    <Modal
      opened={bed !== null}
      onClose={close}
      title={bed ? fmt(vi.session.transferTitle, { bed: bed.code }) : ''}
    >
      <Stack>
        {free.length === 0 ? (
          <Text c="dimmed">{vi.session.noFreeBed}</Text>
        ) : (
          <Select
            label={vi.session.transferTarget}
            data={free.map((b) => ({ value: String(b.id), label: b.code }))}
            value={targetId}
            onChange={setTargetId}
          />
        )}
        <Textarea
          label={vi.session.transferReason}
          required
          value={reason}
          onChange={(e) => setReason(e.currentTarget.value)}
          maxLength={1000}
        />
        {bed && target && (
          <Text fw={600}>
            {fmt(vi.session.confirmTransfer, { from: bed.code, to: target.code })}
          </Text>
        )}
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
            disabled={!session || !target || reason.trim() === ''}
            loading={transfer.isPending}
            onClick={() =>
              session &&
              target &&
              transfer.mutate(
                { sessionId: session.id, target_bed_id: target.id, reason: reason.trim() },
                {
                  onSuccess: () => {
                    notifications.show({
                      color: 'teal',
                      message: fmt(vi.session.transferred, { bed: target.code }),
                    });
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
  );
}
