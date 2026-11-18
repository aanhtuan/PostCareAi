import { Card, Group, Stack, Text } from '@mantine/core';

import type { AlertOut } from '../api/types';
import { fmt, vi } from '../i18n/vi';
import { formatTime } from '../utils/time';
import { AlertActions } from './AlertActions';
import { AlertStatusBadge, OutcomeText, PriorityBadge } from './Badges';

export function AlertCard({ alert, onDetail }: { alert: AlertOut; onDetail: () => void }) {
  const high = alert.event.priority === 'HIGH' && alert.status !== 'RESOLVED';
  return (
    <Card
      withBorder
      padding="md"
      data-priority={alert.event.priority}
      style={high ? { borderColor: 'var(--mantine-color-red-6)', borderWidth: 2 } : undefined}
      bg={alert.status === 'PENDING' ? (high ? 'red.0' : 'orange.0') : undefined}
    >
      <Stack gap={6}>
        <Group justify="space-between" wrap="nowrap">
          <Text fw={700}>
            {fmt(vi.alerts.heading, {
              bed: alert.bed?.code ?? vi.common.none,
              title: vi.alertTitle[alert.event.priority],
            })}
          </Text>
          <Group gap="xs">
            <PriorityBadge priority={alert.event.priority} />
            <AlertStatusBadge status={alert.status} />
          </Group>
        </Group>
        <Text>
          {fmt(vi.alerts.sentence, {
            event: vi.event[alert.event.code],
            time: formatTime(alert.event.occurred_at),
          })}
        </Text>
        <Group gap="lg">
          {alert.acknowledged_by && alert.acknowledged_at && (
            <Text size="sm" c="dimmed">
              {vi.alerts.acknowledgedBy}:{' '}
              {fmt(vi.alerts.personAt, {
                name: alert.acknowledged_by.full_name,
                time: formatTime(alert.acknowledged_at),
              })}
            </Text>
          )}
          {alert.status !== 'PENDING' && (
            <Text size="sm" c="dimmed">
              {vi.alerts.outcomeLabel}: <OutcomeText outcome={alert.outcome} />
            </Text>
          )}
          {alert.session && (
            <Text size="sm" c="dimmed">
              {fmt(vi.bedCard.patient, { code: alert.session.patient_code })}
            </Text>
          )}
        </Group>
        <AlertActions alert={alert} onDetail={onDetail} />
      </Stack>
    </Card>
  );
}
