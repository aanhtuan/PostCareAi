import { Anchor, Group, Stack, Text, Title, UnstyledButton } from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';

import { OVERVIEW_POLL_MS, useEvents } from '../../api/hooks';
import { AlertDetailModal } from '../../components/AlertDetailModal';
import { AlertStatusBadge, PriorityBadge } from '../../components/Badges';
import { vi } from '../../i18n/vi';
import { formatDateTime, formatTime } from '../../utils/time';

const RECENT_EVENT_LIMIT = 4;

export function LiveJournal({ bedId, sessionId }: { bedId: number; sessionId?: number }) {
  const events = useEvents({ bed_id: bedId, limit: RECENT_EVENT_LIMIT }, OVERVIEW_POLL_MS);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [alertId, setAlertId] = useState<number>();
  const items = events.data?.items ?? [];

  return (
    <>
      <Stack gap="xs">
        <Group justify="space-between" gap="xs">
          <Title order={3} size="h4">
            {vi.live.recentJournal}
          </Title>
          <Anchor
            size="sm"
            component={Link}
            to={`/timeline?bed=${bedId}${sessionId === undefined ? '' : `&session=${sessionId}`}`}
          >
            {vi.alerts.openTimeline}
          </Anchor>
        </Group>
        {items.length > 0 ? (
          <Stack
            gap={6}
            mah={300}
            style={{ overflowY: 'auto' }}
            aria-label={vi.live.recentJournal}
            tabIndex={0}
            role="region"
          >
            {items.map((event) => (
              <Stack
                key={event.id}
                gap={0}
                bd="1px solid var(--mantine-color-default-border)"
                style={{ borderRadius: 'var(--mantine-radius-sm)' }}
              >
                <UnstyledButton
                  p="sm"
                  aria-expanded={event.alert_id === null ? expanded === event.id : undefined}
                  onClick={() => {
                    if (event.alert_id !== null) setAlertId(event.alert_id);
                    else setExpanded((id) => (id === event.id ? null : event.id));
                  }}
                >
                  <Group gap="xs" wrap="nowrap" align="flex-start">
                    <Text
                      component="time"
                      dateTime={event.occurred_at}
                      c="dimmed"
                      size="sm"
                      style={{ fontVariantNumeric: 'tabular-nums' }}
                    >
                      {formatTime(event.occurred_at)}
                    </Text>
                    <Stack gap={4}>
                      <Text size="md" fw={600}>
                        {vi.event[event.code]}
                      </Text>
                      <Group gap={4}>
                        <PriorityBadge priority={event.priority} />
                        {event.alert_status && <AlertStatusBadge status={event.alert_status} />}
                      </Group>
                    </Stack>
                  </Group>
                </UnstyledButton>
                {expanded === event.id && event.alert_id === null && (
                  <Stack gap={2} px="xs" pb="xs" aria-label={vi.live.eventDetails}>
                    <Text c="dimmed" size="xs">
                      {formatDateTime(event.occurred_at)}
                    </Text>
                    <Text size="sm">
                      {vi.bedCard.quality} · {vi.quality[event.observation_quality]}
                    </Text>
                  </Stack>
                )}
              </Stack>
            ))}
          </Stack>
        ) : (
          <Text c="dimmed" size="sm">
            {events.isError
              ? vi.common.loadError
              : events.isPending
                ? vi.common.loading
                : vi.live.noEvent}
          </Text>
        )}
      </Stack>
      <AlertDetailModal alertId={alertId} onClose={() => setAlertId(undefined)} />
    </>
  );
}
