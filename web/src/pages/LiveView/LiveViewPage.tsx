// "Theo dõi trực tiếp" (F07; PDF §9.1): ảnh camera thật qua MJPEG, Bed ROI vẽ đè, trạng thái
// camera và phiên. Trạng thái cập nhật realtime qua WebSocket (F21 AC5: `bed.state`,
// `event.created`, `camera.status`); polling 2 s chỉ là đường dự phòng khi mất WebSocket.
import {
  Badge,
  Card,
  Center,
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

import { useCameraDetail, useEvents, useOverview } from '../../api/hooks';
import type { CameraStatus } from '../../api/types';
import { useAuth } from '../../auth/useAuth';
import { CameraStream } from '../../components/CameraStream';
import { PriorityBadge } from '../../components/Badges';
import { fmt, vi } from '../../i18n/vi';
import { formatTime } from '../../utils/time';

const POLL_MS = 2000; // giả định F07 R5; chỉ khi WebSocket không mở (F21)

const STATUS_COLOR: Record<CameraStatus, string> = {
  ONLINE: 'green',
  OFFLINE: 'red',
  UNKNOWN: 'gray',
};

export function LiveViewPage() {
  const { bedId } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const overview = useOverview();
  const beds = overview.data?.beds ?? [];
  const selectedId = bedId ? Number(bedId) : beds[0]?.bed_id;
  const bed = beds.find((b) => b.bed_id === selectedId);
  const cameraDetail = useCameraDetail(bed?.camera?.id, POLL_MS);
  const latest = useEvents({ bed_id: selectedId, limit: 1 });

  if (overview.isPending) return <Loader />;
  const state = bed?.state ?? null;
  const event = latest.data?.items[0];
  // Ưu tiên trạng thái từ chi tiết camera (mới hơn), rồi tới tổng quan.
  const cameraStatus: CameraStatus | null = bed?.camera
    ? (cameraDetail.data?.status ?? bed.camera.status)
    : null;
  const roi = cameraDetail.data?.roi_polygon ?? null;

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
            <Stack gap="xs">
              <Group justify="space-between">
                <Text fw={700} size="lg">
                  {fmt(vi.bed.title, { code: bed.code })}
                </Text>
                <Badge color={cameraStatus ? STATUS_COLOR[cameraStatus] : 'gray'} variant="light">
                  {cameraStatus ? vi.cameraStatus[cameraStatus] : vi.camera.notAssigned}
                </Badge>
              </Group>
              {bed.session ? (
                <Text size="sm">
                  <Text span fw={600}>
                    {vi.live.monitoring}
                  </Text>
                  {' · '}
                  {fmt(vi.live.sessionDetail, {
                    patient: bed.session.patient_code,
                    time: formatTime(bed.session.started_at),
                  })}
                </Text>
              ) : (
                <Text size="sm" c="dimmed">
                  {vi.live.noSession}
                </Text>
              )}
              {bed.camera && cameraStatus ? (
                <>
                  <CameraStream
                    cameraId={bed.camera.id}
                    token={token}
                    online={cameraStatus === 'ONLINE'}
                    offlineText={vi.cameraStatus[cameraStatus]}
                    roi={roi}
                    alt={fmt(vi.live.streamAlt, { code: bed.code })}
                  />
                  {cameraDetail.isSuccess && !roi && (
                    <Text size="sm" c="dimmed">
                      {vi.live.roiNotConfigured}
                    </Text>
                  )}
                </>
              ) : (
                <Center bg="gray.1" style={{ aspectRatio: '16 / 9', borderRadius: 8 }}>
                  <Text c="dimmed">{vi.camera.notAssigned}</Text>
                </Center>
              )}
            </Stack>
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
                    value={bed.camera ? bed.camera.name : vi.camera.notAssigned}
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
