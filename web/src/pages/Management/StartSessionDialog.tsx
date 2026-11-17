// "Bắt đầu theo dõi" (F04 R9): chọn bệnh nhân đang dùng và chưa có phiên mở.
import { Alert, Button, Group, Modal, Select, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { usePatients, useStartSession } from '../../api/hooks';
import type { BedOut } from '../../api/types';
import { vi } from '../../i18n/vi';
import { apiErrorMessage } from './errorMessage';

export function StartSessionDialog({ bed, onClose }: { bed: BedOut | null; onClose: () => void }) {
  const patients = usePatients();
  const start = useStartSession();
  const [patientId, setPatientId] = useState<string | null>(null);
  const free = (patients.data ?? []).filter((p) => p.is_active && p.active_session_id === null);
  const close = () => {
    start.reset();
    setPatientId(null);
    onClose();
  };
  const error = apiErrorMessage(start.error);

  return (
    <Modal opened={bed !== null} onClose={close} title={`${vi.session.start} - ${bed?.code ?? ''}`}>
      <Stack>
        {free.length === 0 ? (
          <Text c="dimmed">{vi.session.noFreePatient}</Text>
        ) : (
          <Select
            label={vi.session.choosePatient}
            data={free.map((p) => ({ value: String(p.id), label: p.code }))}
            value={patientId}
            onChange={setPatientId}
          />
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
            disabled={!patientId || !bed}
            loading={start.isPending}
            onClick={() =>
              bed &&
              patientId &&
              start.mutate(
                { bed_id: bed.id, patient_id: Number(patientId) },
                {
                  onSuccess: () => {
                    notifications.show({ color: 'teal', message: vi.session.started });
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
