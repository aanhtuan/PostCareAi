// Nút thao tác cảnh báo đúng PDF §9.2 và ADR-0007. DOCTOR không thấy nút (F20 R7).
import { Button, Group, Stack, Textarea } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

import { ApiError } from '../api/client';
import { useAlertAction, type AlertAction } from '../api/hooks';
import type { AlertOut, AlertOutcome } from '../api/types';
import { useAuth } from '../auth/useAuth';
import { vi } from '../i18n/vi';

const OUTCOME_BUTTONS: { outcome: AlertOutcome; label: string; color: string }[] = [
  { outcome: 'CONFIRMED', label: vi.alerts.confirmed, color: 'red' },
  { outcome: 'FALSE_ALARM', label: vi.alerts.falseAlarm, color: 'gray' },
  { outcome: 'PATIENT_SAFE', label: vi.alerts.patientSafe, color: 'teal' },
];

type Props = {
  alert: Pick<AlertOut, 'id' | 'status' | 'outcome' | 'note'>;
  onDetail?: () => void;
  compact?: boolean;
};

export function AlertActions({ alert, onDetail, compact = false }: Props) {
  const { canWrite } = useAuth();
  const mutation = useAlertAction(alert.id);
  const [note, setNote] = useState(alert.note ?? '');

  const run = (action: AlertAction) =>
    mutation.mutate(action, {
      onError: (err) => {
        const message =
          err instanceof ApiError
            ? err.status === 403
              ? vi.common.forbidden
              : err.message
            : vi.common.genericError;
        notifications.show({ color: 'red', message });
      },
    });

  const detail = onDetail ? (
    <Button size="xs" variant="default" onClick={onDetail}>
      {vi.alerts.detail}
    </Button>
  ) : null;

  if (!canWrite || alert.status === 'RESOLVED')
    return detail ? <Group gap="xs">{detail}</Group> : null;

  if (alert.status === 'PENDING') {
    return (
      <Group gap="xs">
        <Button
          size="xs"
          color="red"
          loading={mutation.isPending}
          onClick={() => run({ kind: 'acknowledge' })}
        >
          {vi.alerts.acknowledge}
        </Button>
        {detail}
      </Group>
    );
  }

  return (
    <Stack gap="xs">
      <Group gap="xs">
        {OUTCOME_BUTTONS.map((b) => (
          <Button
            key={b.outcome}
            size="xs"
            color={b.color}
            variant={alert.outcome === b.outcome ? 'filled' : 'outline'}
            aria-pressed={alert.outcome === b.outcome}
            disabled={mutation.isPending}
            onClick={() => run({ kind: 'outcome', outcome: b.outcome, note })}
          >
            {b.label}
          </Button>
        ))}
        <Button
          size="xs"
          color="green"
          loading={mutation.isPending}
          onClick={() => run({ kind: 'resolve', note })}
        >
          {vi.alerts.resolve}
        </Button>
        {detail}
      </Group>
      {!compact && (
        <Textarea
          size="xs"
          aria-label={vi.alerts.note}
          placeholder={vi.alerts.notePlaceholder}
          autosize
          minRows={1}
          maxLength={1000}
          value={note}
          onChange={(e) => setNote(e.currentTarget.value)}
        />
      )}
    </Stack>
  );
}
