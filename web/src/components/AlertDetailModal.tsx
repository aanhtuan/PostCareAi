import { Anchor, Group, Modal, Stack, Table, Text } from '@mantine/core';
import type { ReactNode } from 'react';
import { Link } from 'react-router';

import type { AlertOut, UserRef } from '../api/types';
import { fmt, vi } from '../i18n/vi';
import { formatDateTime } from '../utils/time';
import { AlertStatusBadge, OutcomeText, PriorityBadge } from './Badges';

function person(user: UserRef | null | undefined, at: string | null | undefined): string {
  if (!user || !at) return vi.common.none;
  return fmt(vi.alerts.personAt, { name: user.full_name, time: formatDateTime(at) });
}

export function AlertDetailModal({
  alert,
  onClose,
}: {
  alert: AlertOut | null;
  onClose: () => void;
}) {
  return (
    <Modal opened={alert !== null} onClose={onClose} title={vi.alerts.detailTitle} size="lg">
      {alert && (
        <Stack>
          <Text fw={600}>{vi.event[alert.event.code]}</Text>
          <Table withRowBorders={false} verticalSpacing={4}>
            <Table.Tbody>
              <Row label={vi.alerts.occurredAt} value={formatDateTime(alert.event.occurred_at)} />
              <Row label={vi.common.bed} value={alert.bed?.code ?? vi.common.none} />
              <Row
                label={vi.alerts.session}
                value={alert.session?.patient_code ?? vi.common.none}
              />
              <Row
                label={vi.alerts.priority}
                value={<PriorityBadge priority={alert.event.priority} />}
              />
              <Row label={vi.alerts.quality} value={vi.quality[alert.event.observation_quality]} />
              <Row label={vi.alerts.status} value={<AlertStatusBadge status={alert.status} />} />
              <Row
                label={vi.alerts.acknowledgedBy}
                value={person(alert.acknowledged_by, alert.acknowledged_at)}
              />
              <Row label={vi.alerts.outcomeLabel} value={<OutcomeText outcome={alert.outcome} />} />
              <Row label={vi.alerts.outcomeBy} value={person(alert.outcome_by, alert.outcome_at)} />
              <Row
                label={vi.alerts.resolvedBy}
                value={person(alert.resolved_by, alert.resolved_at)}
              />
              <Row label={vi.alerts.note} value={alert.note || vi.common.none} />
            </Table.Tbody>
          </Table>
          {alert.bed && (
            <Group>
              <Anchor component={Link} to={`/beds/${alert.bed.id}/live`}>
                {vi.alerts.openLive}
              </Anchor>
              <Anchor
                component={Link}
                to={`/timeline?bed=${alert.bed.id}${alert.session ? `&session=${alert.session.id}` : ''}`}
              >
                {vi.alerts.openTimeline}
              </Anchor>
            </Group>
          )}
        </Stack>
      )}
    </Modal>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Table.Tr>
      <Table.Td w={200}>
        <Text c="dimmed" size="sm">
          {label}
        </Text>
      </Table.Td>
      <Table.Td>{value}</Table.Td>
    </Table.Tr>
  );
}
