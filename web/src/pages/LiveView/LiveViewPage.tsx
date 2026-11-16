import {
  Alert,
  Badge,
  Card,
  Group,
  Loader,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import type { ReactNode } from 'react';
import { useNavigate, useParams } from 'react-router';

import { useEvents, useOverview } from '../../api/hooks';
import { PriorityBadge } from '../../components/Badges';
import { fmt, vi } from '../../i18n/vi';
import { formatDateTime, formatTime } from '../../utils/time';
import { SkeletonView } from './SkeletonView';

export function LiveViewPage() {
  const { bedId } = useParams();
  const navigate = useNavigate();
  const overview = useOverview();
  const beds = overview.data?.beds ?? [];
  const selectedId = bedId ? Number(bedId) : beds[0]?.bed_id;
  const bed = beds.find((b) => b.bed_id === selectedId);
  const latest = useEvents({ bed_id: selectedId, limit: 1 });

  if (overview.isPending) return <Loader />;
  const state = bed?.state ?? null;
  const event = latest.data?.items[0];

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{vi.live.title}</Title>
        <Select
          label={vi.live.chooseBed}
          data={beds.map((b) => ({
            value: String(b.bed_id),
            label: fmt(vi.bed.title, { code: b.code }),
          }))}
          value={selectedId ? String(selectedId) : null}
          onChange={(v) => v && navigate(`/beds/${v}/live`)}
          allowDeselect={false}
          w={200}
        />
      </Group>
      {bed && (
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          <Card withBorder>
            <Group justify="space-between" mb="xs">
              <Text fw={700}>{fmt(vi.bed.title, { code: bed.code })}</Text>
              <Badge color="grape" variant="light">
                {vi.live.simulatedMode}
              </Badge>
            </Group>
            <SkeletonView bodyState={state?.body_state ?? null} />
            <Alert color="grape" variant="light" mt="sm">
              {vi.live.simulatedHint}
            </Alert>
          </Card>
          <Card withBorder>
            <Stack gap="sm">
              <Text size="xl" fw={700}>
                {vi.bodyState[state?.body_state ?? 'NO_OBSERVATION']}
              </Text>
              {!state && <Text c="dimmed">{vi.live.noState}</Text>}
              <Table withRowBorders={false} verticalSpacing={4}>
                <Table.Tbody>
                  <Row
                    label={vi.bedCard.quality}
                    value={state ? vi.quality[state.observation_quality] : vi.common.none}
                  />
                  <Row
                    label={vi.live.activity}
                    value={state ? vi.activity[state.activity_level] : vi.common.none}
                  />
                  <Row
                    label={vi.live.rest}
                    value={state ? vi.rest[state.rest_status] : vi.common.none}
                  />
                  <Row
                    label={vi.live.face}
                    value={state ? vi.faceStatus[state.face_status] : vi.common.none}
                  />
                  <Row
                    label={vi.live.camera}
                    value={
                      bed.camera
                        ? `${bed.camera.name} · ${vi.cameraStatus[bed.camera.status]}`
                        : vi.camera.notAssigned
                    }
                  />
                  <Row
                    label={vi.live.session}
                    value={
                      bed.session
                        ? `${fmt(vi.bedCard.patient, { code: bed.session.patient_code })} · ${vi.management.startedAt} ${formatDateTime(bed.session.started_at)}`
                        : vi.bedCard.NOT_MONITORED
                    }
                  />
                  {state && (
                    <Row
                      label={vi.common.time}
                      value={fmt(vi.live.updatedAt, { time: formatTime(state.updated_at) })}
                    />
                  )}
                </Table.Tbody>
              </Table>
              <Card withBorder bg="gray.0">
                <Text size="sm" c="dimmed">
                  {vi.live.latestEvent}
                </Text>
                {event ? (
                  <Group gap="xs">
                    <Text fw={600}>
                      {formatTime(event.occurred_at)} - {vi.event[event.code]}
                    </Text>
                    <PriorityBadge priority={event.priority} />
                  </Group>
                ) : (
                  <Text>{vi.live.noEvent}</Text>
                )}
              </Card>
            </Stack>
          </Card>
        </SimpleGrid>
      )}
    </Stack>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <Table.Tr>
      <Table.Td w={170}>
        <Text c="dimmed" size="sm">
          {label}
        </Text>
      </Table.Td>
      <Table.Td>{value}</Table.Td>
    </Table.Tr>
  );
}
