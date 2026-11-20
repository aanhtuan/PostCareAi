import { Group, Loader, MultiSelect, Select, Stack, Text, TextInput, Title } from '@mantine/core';
import { useState } from 'react';
import { useSearchParams } from 'react-router';

import { useAlerts, useBeds, type AlertFilter } from '../../api/hooks';
import { ALERT_STATUSES, PRIORITIES, type AlertStatus, type Priority } from '../../api/types';
import { AlertCard } from '../../components/AlertCard';
import { AlertDetailModal } from '../../components/AlertDetailModal';
import { fmt, vi } from '../../i18n/vi';
import { bedOptionLabel } from '../../utils/bedLabel';
import { fromLocalInput } from '../../utils/time';

export function AlertsPage() {
  // Gồm cả giường đã xóa để xem lại lịch sử (F03 R17).
  const beds = useBeds(true);
  const [status, setStatus] = useState<AlertStatus[]>([]);
  const [priority, setPriority] = useState<Priority[]>([]);
  const [bedId, setBedId] = useState<string | null>(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [detailId, setDetailId] = useState<number | null>(null);
  const [params, setParams] = useSearchParams();
  const requestedId = Number(params.get('alert'));
  const linkedAlert =
    Number.isSafeInteger(requestedId) && requestedId > 0 ? requestedId : undefined;

  const filter: AlertFilter = {
    status: status.length ? status : undefined,
    priority: priority.length ? priority : undefined,
    bed_id: bedId ? Number(bedId) : undefined,
    from: from ? fromLocalInput(from) : undefined,
    to: to ? fromLocalInput(to) : undefined,
    limit: 100,
  };
  const alerts = useAlerts(filter);
  const items = alerts.data?.items ?? [];
  const detail = items.find((a) => a.id === detailId) ?? null;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{vi.alerts.title}</Title>
        <Text size="sm" c="dimmed">
          {vi.alerts.soundHint}
        </Text>
      </Group>
      <Group align="end" className="no-print">
        <MultiSelect
          label={vi.alerts.status}
          placeholder={vi.common.all}
          data={ALERT_STATUSES.map((s) => ({ value: s, label: vi.alertStatus[s] }))}
          value={status}
          onChange={(v) => setStatus(v as AlertStatus[])}
          clearable
          w={260}
        />
        <MultiSelect
          label={vi.alerts.priority}
          placeholder={vi.common.all}
          data={PRIORITIES.filter((p) => p === 'MEDIUM' || p === 'HIGH').map((p) => ({
            value: p,
            label: vi.priority[p],
          }))}
          value={priority}
          onChange={(v) => setPriority(v as Priority[])}
          clearable
          w={220}
        />
        <Select
          label={vi.common.bed}
          placeholder={vi.common.all}
          data={(beds.data ?? []).map((b) => ({
            value: String(b.id),
            label: bedOptionLabel(b),
          }))}
          value={bedId}
          onChange={setBedId}
          clearable
          w={160}
        />
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
      </Group>
      {alerts.isPending ? (
        <Loader />
      ) : items.length === 0 ? (
        <Text c="dimmed">{vi.alerts.empty}</Text>
      ) : (
        <Stack gap="sm">
          <Text size="sm" c="dimmed">
            {fmt(vi.common.total, { n: alerts.data?.total ?? 0 })}
          </Text>
          {items.map((a) => (
            <AlertCard key={a.id} alert={a} onDetail={() => setDetailId(a.id)} />
          ))}
        </Stack>
      )}
      <AlertDetailModal
        alert={detail}
        alertId={linkedAlert}
        onClose={() => {
          setDetailId(null);
          if (linkedAlert !== undefined) {
            const next = new URLSearchParams(params);
            next.delete('alert');
            setParams(next, { replace: true });
          }
        }}
      />
    </Stack>
  );
}
