import {
  Badge,
  Button,
  Card,
  Group,
  Loader,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useMemo, useState } from 'react';

import { useHandover, useShifts, type HandoverFilter } from '../../api/hooks';
import type { AlertOutcome, EventCode } from '../../api/types';
import { AlertStatusBadge, PriorityBadge } from '../../components/Badges';
import { fmt, vi } from '../../i18n/vi';
import {
  formatDate,
  formatDateTime,
  formatTime,
  fromLocalInput,
  shortClock,
  toDateInput,
  toLocalInput,
} from '../../utils/time';
import { currentShiftAndDate } from '../../utils/shift';

export function HandoverPage() {
  const shifts = useShifts();
  const [mode, setMode] = useState<'shift' | 'range'>('shift');
  const [shiftId, setShiftId] = useState<string | null>(null);
  const [date, setDate] = useState<string>('');
  const [from, setFrom] = useState(() => toLocalInput(new Date(Date.now() - 8 * 3600 * 1000)));
  const [to, setTo] = useState(() => toLocalInput(new Date()));

  const current = useMemo(
    () => (shifts.data ? currentShiftAndDate(shifts.data, new Date()) : null),
    [shifts.data],
  );
  const effShift = shiftId ?? (current ? String(current.shift.id) : null);
  const effDate = date || current?.date || toDateInput(new Date());

  const filter: HandoverFilter | null =
    mode === 'shift'
      ? effShift
        ? { shift_id: Number(effShift), date: effDate }
        : null
      : from && to
        ? { from: fromLocalInput(from), to: fromLocalInput(to) }
        : null;
  const handover = useHandover(filter);
  const data = handover.data;
  const shift = shifts.data?.find((s) => String(s.id) === effShift);

  const title =
    mode === 'shift' && shift
      ? fmt(vi.handover.period, {
          name: shift.name,
          start: shortClock(shift.start_time),
          end: shortClock(shift.end_time),
          date: effDate.split('-').reverse().join('/'),
        })
      : data
        ? fmt(vi.handover.range, { from: formatDateTime(data.from), to: formatDateTime(data.to) })
        : '';

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{vi.handover.title}</Title>
        <Button className="no-print" variant="default" onClick={() => window.print()}>
          {vi.handover.print}
        </Button>
      </Group>
      <Group align="end" className="no-print">
        <SegmentedControl
          value={mode}
          onChange={(v) => setMode(v as 'shift' | 'range')}
          data={[
            { value: 'shift', label: vi.handover.byShift },
            { value: 'range', label: vi.handover.byRange },
          ]}
        />
        {mode === 'shift' ? (
          <>
            <Select
              label={vi.handover.shift}
              data={(shifts.data ?? []).map((s) => ({
                value: String(s.id),
                label: `${s.name} ${shortClock(s.start_time)}–${shortClock(s.end_time)}`,
              }))}
              value={effShift}
              onChange={setShiftId}
              allowDeselect={false}
              w={220}
            />
            <TextInput
              type="date"
              label={vi.handover.date}
              value={effDate}
              onChange={(e) => setDate(e.currentTarget.value)}
            />
          </>
        ) : (
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
      </Group>

      <div className="print-area">
        <Title order={3}>{title}</Title>
        <Text size="xs" c="dimmed" className="print-only">
          {fmt(vi.handover.printedAt, {
            time: `${formatDate(new Date())} ${formatTime(new Date())}`,
          })}
        </Text>
        {handover.isPending && filter ? (
          <Loader />
        ) : handover.isError ? (
          <Text c="red">{handover.error.message}</Text>
        ) : data ? (
          <Stack mt="md">
            <Card withBorder data-testid="handover-outstanding">
              <Title order={4} mb="xs">
                {vi.handover.outstanding}
              </Title>
              {data.outstanding_alerts.length === 0 ? (
                <Text c="dimmed">{vi.handover.noOutstanding}</Text>
              ) : (
                <Table striped>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>{vi.common.time}</Table.Th>
                      <Table.Th>{vi.common.bed}</Table.Th>
                      <Table.Th>{vi.alerts.title}</Table.Th>
                      <Table.Th>{vi.alerts.priority}</Table.Th>
                      <Table.Th>{vi.alerts.status}</Table.Th>
                      <Table.Th>{vi.alerts.acknowledgedBy}</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {data.outstanding_alerts.map((a) => (
                      <Table.Tr key={a.id}>
                        <Table.Td>{formatDateTime(a.event.occurred_at)}</Table.Td>
                        <Table.Td>{a.bed?.code}</Table.Td>
                        <Table.Td>{vi.event[a.event.code]}</Table.Td>
                        <Table.Td>
                          <PriorityBadge priority={a.event.priority} />
                        </Table.Td>
                        <Table.Td>
                          {a.status === 'RESOLVED' &&
                          a.resolved_at &&
                          new Date(a.resolved_at) >= new Date(data.to) ? (
                            // Khoảng đã qua: tại cuối khoảng cảnh báo còn tồn đọng (F24 R4).
                            <Badge color="gray" variant="light">
                              {vi.handover.resolvedAfter}
                            </Badge>
                          ) : (
                            <AlertStatusBadge status={a.status} />
                          )}
                        </Table.Td>
                        <Table.Td>{a.acknowledged_by?.full_name ?? vi.common.none}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </Card>
            <Card withBorder>
              <Title order={4} mb="xs">
                {vi.handover.byBed}
              </Title>
              <Table striped data-testid="handover-beds">
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>{vi.common.bed}</Table.Th>
                    <Table.Th>{vi.handover.events}</Table.Th>
                    <Table.Th>{vi.handover.resolved}</Table.Th>
                    <Table.Th>{vi.handover.unresolved}</Table.Th>
                    <Table.Th>{vi.handover.stateChanges}</Table.Th>
                    <Table.Th>{vi.handover.outcomes}</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {data.beds.map((b) => {
                    const counts = Object.entries(b.event_counts) as [EventCode, number][];
                    const outcomes = Object.entries(b.outcome_counts) as [AlertOutcome, number][];
                    return (
                      <Table.Tr key={b.bed_id}>
                        <Table.Td fw={700}>
                          {b.is_active ? b.code : fmt(vi.handover.deletedBed, { code: b.code })}
                        </Table.Td>
                        <Table.Td>
                          {counts.length === 0
                            ? vi.handover.noEvents
                            : counts.map(([code, n]) => (
                                <div key={code}>
                                  {vi.event[code]}: <b>{n}</b>
                                </div>
                              ))}
                        </Table.Td>
                        <Table.Td>{b.alerts_resolved}</Table.Td>
                        <Table.Td>{b.alerts_unresolved}</Table.Td>
                        <Table.Td>{b.state_change_count}</Table.Td>
                        <Table.Td>
                          {outcomes.length === 0
                            ? vi.common.none
                            : outcomes.map(([o, n]) => (
                                <div key={o}>
                                  {vi.outcome[o]}: <b>{n}</b>
                                </div>
                              ))}
                        </Table.Td>
                      </Table.Tr>
                    );
                  })}
                </Table.Tbody>
              </Table>
            </Card>
          </Stack>
        ) : null}
      </div>
    </Stack>
  );
}
