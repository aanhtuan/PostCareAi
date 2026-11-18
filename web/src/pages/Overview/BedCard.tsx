import { Badge, Card, Group, Stack, Text } from '@mantine/core';
import { useNavigate } from 'react-router';

import type { OverviewBedOut } from '../../api/types';
import { PriorityBadge } from '../../components/Badges';
import { fmt, vi } from '../../i18n/vi';
import { CARD_COLOR, bedCardStatus } from './bedCardStatus';

export function BedCard({ bed }: { bed: OverviewBedOut }) {
  const navigate = useNavigate();
  const status = bedCardStatus({
    hasSession: bed.session !== null,
    paused: bed.session?.paused_at != null,
    pendingCount: bed.pending_alert_count,
    acknowledgedCount: bed.acknowledged_alert_count,
    bodyState: bed.state?.body_state ?? null,
    cameraOffline: bed.camera?.status === 'OFFLINE',
  });
  const color = CARD_COLOR[status];
  const open = () => navigate(`/beds/${bed.bed_id}/live`);
  const cameraLabel = bed.camera ? vi.cameraStatus[bed.camera.status] : vi.camera.notAssigned;

  return (
    <Card
      withBorder
      padding="md"
      role="button"
      tabIndex={0}
      aria-label={`${fmt(vi.bed.title, { code: bed.code })} - ${vi.bedCard.openLive}`}
      onClick={open}
      onKeyDown={(e) => {
        if (e.key === 'Enter') open();
      }}
      style={{
        cursor: 'pointer',
        borderTop: `6px solid var(--mantine-color-${color}-6)`,
      }}
    >
      <Stack gap={6}>
        <Group justify="space-between" wrap="nowrap">
          <Text fw={700} size="lg">
            {fmt(vi.bed.title, { code: bed.code })}
          </Text>
          <Badge color={color} variant={status === 'NEW_ALERT' ? 'filled' : 'light'}>
            {vi.bedCard[status]}
          </Badge>
        </Group>
        <Text size="sm" c="dimmed">
          {bed.area}
          {bed.session ? ` · ${fmt(vi.bedCard.patient, { code: bed.session.patient_code })}` : ''}
        </Text>
        {bed.session && status !== 'PAUSED' && (
          <>
            <Text size="sm">
              {vi.bedCard.bodyState}:{' '}
              <b>{vi.bodyState[bed.state?.body_state ?? 'NO_OBSERVATION']}</b>
            </Text>
            <Text size="sm">
              {vi.bedCard.quality}:{' '}
              {bed.state ? vi.quality[bed.state.observation_quality] : vi.common.none}
            </Text>
            <Group gap="xs">
              <Text size="sm">
                {vi.bedCard.pending}: <b>{bed.pending_alert_count}</b>
              </Text>
              {bed.max_open_priority && (
                <>
                  <Text size="sm">· {vi.bedCard.maxPriority}:</Text>
                  <PriorityBadge priority={bed.max_open_priority} />
                </>
              )}
            </Group>
          </>
        )}
        <Text size="xs" c={bed.camera?.status === 'OFFLINE' ? 'red' : 'dimmed'}>
          {cameraLabel}
        </Text>
      </Stack>
    </Card>
  );
}
