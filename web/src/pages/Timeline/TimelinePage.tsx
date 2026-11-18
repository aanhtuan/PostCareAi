import {
  Alert,
  Button,
  Card,
  Divider,
  Group,
  Loader,
  MultiSelect,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router';

import { useBeds, useSessions, useTimeline, type TimelineFilter } from '../../api/hooks';
import { PRIORITIES, type Priority, type TimelineItemOut } from '../../api/types';
import { AlertActions } from '../../components/AlertActions';
import { AlertStatusBadge, OutcomeText, PriorityBadge } from '../../components/Badges';
import { fmt, vi } from '../../i18n/vi';
import { bedOptionLabel } from '../../utils/bedLabel';
import {
  formatDate,
  formatDateTime,
  formatTime,
  fromLocalInput,
  toLocalInput,
} from '../../utils/time';

const RANGE = 'range';

function itemText(item: TimelineItemOut): string {
  const name = item.actor?.full_name ?? vi.timeline.system;
  switch (item.action) {
    case 'alert.acknowledge':
      return fmt(vi.timeline.acknowledge, { name });
    case 'alert.outcome':
      return fmt(vi.timeline.outcome, {
        outcome: item.outcome ? vi.outcome[item.outcome] : vi.alerts.noOutcome,
        name,
      });
    case 'alert.resolve':
      return fmt(vi.timeline.resolve, { name });
    case 'session.transfer':
      return fmt(vi.timeline.transfer, {
        from: item.from_bed_code ?? vi.common.none,
        to: item.bed_code ?? vi.common.none,
        name,
      });
    case 'session.pause':
      return fmt(vi.timeline.pause, { name });
    case 'session.resume':
      return fmt(vi.timeline.resume, { name });
    default:
      return item.code ? vi.event[item.code] : vi.common.none;
  }
}

function TimelineRow({ item }: { item: TimelineItemOut }) {
  const isAction = item.kind !== 'event';
  return (
    <Group
      align="flex-start"
      wrap="nowrap"
      pl={isAction ? 'xl' : 0}
      py={4}
      style={{ borderBottom: '1px solid #f0f0f0' }}
    >
      <Stack gap={4} style={{ flex: 1 }}>
        <Group gap="xs">
          <Text ff="monospace" fw={isAction ? 400 : 600} c={isAction ? 'dimmed' : undefined}>
            {fmt(vi.timeline.line, { time: formatTime(item.time), text: itemText(item) })}
          </Text>
          {!isAction && item.priority && <PriorityBadge priority={item.priority} />}
          {isAction && item.note && (
            <Text size="sm" c="dimmed">
              · {item.kind === 'session_action' ? vi.timeline.reason : vi.alerts.note}: {item.note}
            </Text>
          )}
        </Group>
        {!isAction && item.alert && (
          <Group gap="xs">
            <AlertStatusBadge status={item.alert.status} />
            <Text size="sm" c="dimmed">
              {vi.alerts.acknowledgedBy}: {item.alert.acknowledged_by?.full_name ?? vi.common.none}{' '}
              · {vi.alerts.outcomeLabel}: <OutcomeText outcome={item.alert.outcome} />
            </Text>
          </Group>
        )}
        {!isAction && item.alert && item.alert.status !== 'RESOLVED' && (
          <AlertActions
            compact
            alert={{
              id: item.alert.id,
              status: item.alert.status,
              outcome: item.alert.outcome ?? null,
              note: null,
            }}
          />
        )}
      </Stack>
    </Group>
  );
}

export function TimelinePage() {
  const [params] = useSearchParams();
  // Gồm cả giường đã xóa để xem lại lịch sử (F03 R17).
  const beds = useBeds(true);
  const bedList = beds.data ?? [];
  const [bedId, setBedId] = useState<string | null>(params.get('bed'));
  const firstBed = bedList.find((b) => b.is_active) ?? bedList[0];
  const effectiveBed = bedId ?? (firstBed ? String(firstBed.id) : null);
  const sessions = useSessions(
    { bed_id: effectiveBed ? Number(effectiveBed) : undefined, limit: 20 },
    effectiveBed !== null,
  );
  const [mode, setMode] = useState<string | null>(params.get('session'));
  const [from, setFrom] = useState(() => toLocalInput(new Date(Date.now() - 24 * 3600 * 1000)));
  const [to, setTo] = useState('');
  const [priority, setPriority] = useState<Priority[]>([]);

  const sessionItems = sessions.data?.items ?? [];
  const defaultMode = sessionItems.find((s) => s.ended_at === null)?.id;
  const effectiveMode = mode ?? (defaultMode ? String(defaultMode) : RANGE);

  const filter: TimelineFilter | null = useMemo(() => {
    if (!effectiveBed) return null;
    const p = priority.length ? priority : undefined;
    if (effectiveMode !== RANGE)
      return { mode: 'session', session_id: Number(effectiveMode), priority: p };
    return {
      mode: 'range',
      bed_id: Number(effectiveBed),
      from: from ? fromLocalInput(from) : undefined,
      to: to ? fromLocalInput(to) : undefined,
      priority: p,
    };
  }, [effectiveBed, effectiveMode, from, to, priority]);

  const timeline = useTimeline(filter);
  const items = useMemo(() => timeline.data?.pages.flatMap((p) => p.items) ?? [], [timeline.data]);
  const multiDay = new Set(items.map((i) => formatDate(i.time))).size > 1;

  return (
    <Stack>
      <Title order={2}>{vi.timeline.title}</Title>
      <Group align="end" className="no-print">
        <Select
          label={vi.common.bed}
          data={bedList.map((b) => ({
            value: String(b.id),
            label: bedOptionLabel(b),
          }))}
          value={effectiveBed}
          onChange={(v) => {
            setBedId(v);
            setMode(null);
          }}
          allowDeselect={false}
          w={160}
        />
        <Select
          label={vi.timeline.session}
          data={[
            ...sessionItems.map((s) => ({
              value: String(s.id),
              label:
                fmt(vi.timeline.sessionOption, {
                  patient: s.patient_code,
                  time: formatDateTime(s.started_at),
                }) + (s.ended_at ? '' : ` (${vi.timeline.sessionActive})`),
            })),
            { value: RANGE, label: vi.timeline.byRange },
          ]}
          value={effectiveMode}
          onChange={setMode}
          allowDeselect={false}
          w={340}
        />
        {effectiveMode === RANGE && (
          <>
            <TextInput
              type="datetime-local"
              label={vi.common.from}
              value={from}
              onChange={(e) => setFrom(e.currentTarget.value)}
            />
            <TextInput
              type="datetime-local"
              label={vi.common.to}
              value={to}
              onChange={(e) => setTo(e.currentTarget.value)}
            />
          </>
        )}
        <MultiSelect
          label={vi.timeline.priority}
          placeholder={vi.common.all}
          data={PRIORITIES.map((p) => ({ value: p, label: vi.priority[p] }))}
          value={priority}
          onChange={(v) => setPriority(v as Priority[])}
          clearable
          w={260}
        />
      </Group>
      <Alert variant="light" color="gray">
        {vi.timeline.hint}
      </Alert>
      <Card withBorder>
        {timeline.isPending && filter ? (
          <Loader />
        ) : items.length === 0 ? (
          <Text c="dimmed">{vi.timeline.empty}</Text>
        ) : (
          <Stack gap={0}>
            {items.map((item, idx) => {
              const day = formatDate(item.time);
              const showDay = multiDay && (idx === 0 || formatDate(items[idx - 1].time) !== day);
              return (
                <div key={`${item.kind}-${item.event_id ?? ''}-${idx}`}>
                  {showDay && <Divider my="sm" label={day} labelPosition="left" />}
                  <TimelineRow item={item} />
                </div>
              );
            })}
            {timeline.hasNextPage && (
              <Group justify="center" mt="sm" className="no-print">
                <Button
                  variant="default"
                  loading={timeline.isFetchingNextPage}
                  onClick={() => void timeline.fetchNextPage()}
                >
                  {vi.timeline.loadMore}
                </Button>
              </Group>
            )}
          </Stack>
        )}
      </Card>
    </Stack>
  );
}
