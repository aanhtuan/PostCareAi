import { Anchor, Card, Group, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { Link } from 'react-router';

import { useAlerts, useEvents, useOverview } from '../../api/hooks';
import type { AlertOut, EventOut, ShiftOut } from '../../api/types';
import { AlertActions } from '../../components/AlertActions';
import { AlertStatusBadge, PriorityBadge } from '../../components/Badges';
import { fmt, vi } from '../../i18n/vi';
import { formatHm, shortClock } from '../../utils/time';
import { BedCard } from './BedCard';

const RECENT_LIMIT = 10; // F21 R6 (giả định hằng số UI)

function shiftLabel(shift: ShiftOut | null | undefined): string {
  if (!shift) return vi.shift.none;
  return fmt(vi.shift.label, {
    start: shortClock(shift.start_time),
    end: shortClock(shift.end_time),
  });
}

function AttentionEvents({ alerts }: { alerts: AlertOut[] }) {
  return (
    <Card withBorder>
      <Group justify="space-between" mb="xs">
        <Title order={4}>{vi.overview.attention}</Title>
        <Anchor component={Link} to="/alerts" size="sm">
          {vi.overview.seeAll}
        </Anchor>
      </Group>
      {alerts.length === 0 ? (
        <Text c="dimmed">{vi.overview.noAttention}</Text>
      ) : (
        <Stack gap="sm">
          {alerts.map((a) => (
            <Stack key={a.id} gap={4} pb="xs" style={{ borderBottom: '1px solid #eee' }}>
              <Group gap="xs">
                <Text fw={600}>
                  {formatHm(a.event.occurred_at)} - {fmt(vi.bed.title, { code: a.bed?.code ?? '' })}
                </Text>
                <PriorityBadge priority={a.event.priority} />
              </Group>
              <Text size="sm">{vi.event[a.event.code]}</Text>
              <Group gap="xs">
                <Text size="sm" c="dimmed">
                  {vi.overview.status}
                </Text>
                <AlertStatusBadge status={a.status} />
                {a.acknowledged_by && (
                  <Text size="sm" c="dimmed">
                    ({a.acknowledged_by.full_name})
                  </Text>
                )}
              </Group>
              {a.status === 'PENDING' && <AlertActions alert={a} compact />}
            </Stack>
          ))}
        </Stack>
      )}
    </Card>
  );
}

function RecentActivity({ events }: { events: EventOut[] }) {
  return (
    <Card withBorder>
      <Title order={4} mb="xs">
        {vi.overview.recent}
      </Title>
      {events.length === 0 ? (
        <Text c="dimmed">{vi.overview.noRecent}</Text>
      ) : (
        <Stack gap={4}>
          {events.map((e) => (
            <Group key={e.id} gap="xs" wrap="nowrap">
              <Text size="sm" ff="monospace">
                {formatHm(e.occurred_at)}
              </Text>
              <Text size="sm" fw={600}>
                {e.bed_code}
              </Text>
              <Text size="sm">· {vi.event[e.code]}</Text>
            </Group>
          ))}
        </Stack>
      )}
    </Card>
  );
}

export function OverviewPage() {
  const overview = useOverview();
  const attention = useAlerts({ status: ['PENDING', 'ACKNOWLEDGED'], limit: 20 });
  const recent = useEvents({ limit: RECENT_LIMIT });

  if (overview.isPending) return <Loader />;
  if (overview.isError && !overview.data) return <Text c="red">{vi.common.loadError}</Text>;
  const data = overview.data;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{vi.overview.title}</Title>
        <Text fw={600} size="lg">
          {shiftLabel(data?.current_shift)}
        </Text>
      </Group>
      <SimpleGrid cols={{ base: 1, xs: 2, lg: 3 }}>
        {data?.beds.map((b) => (
          <BedCard key={b.bed_id} bed={b} />
        ))}
      </SimpleGrid>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <AttentionEvents alerts={attention.data?.items ?? []} />
        <RecentActivity events={recent.data?.items ?? []} />
      </SimpleGrid>
    </Stack>
  );
}
