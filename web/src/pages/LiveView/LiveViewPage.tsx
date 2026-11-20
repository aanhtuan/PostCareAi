// "Theo dõi trực tiếp" (F07; PDF §9.1): ảnh camera qua MJPEG (đã render theo chế độ hiển thị
// trong worker, F28), Bed ROI vẽ đè, chế độ hiển thị, trạng thái camera và phiên. Trạng thái cập nhật realtime qua WebSocket (F21 AC5: `bed.state`,
// `event.created`, `camera.status`); polling 2 s chỉ là đường dự phòng khi mất WebSocket.
import {
  Anchor,
  Badge,
  Button,
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
import { useState, type ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router';

import { useCameraDetail, useEvents, useOverview } from '../../api/hooks';
import type { CameraStatus } from '../../api/types';
import { useAuth } from '../../auth/useAuth';
import { CameraStream } from '../../components/CameraStream';
import { PriorityBadge } from '../../components/Badges';
import { RestStatusBadge } from '../../components/RestStatusBadge';
import { fmt, vi } from '../../i18n/vi';
import { formatTime } from '../../utils/time';
import { CameraForm } from '../Management/CameraForm';
import { DisplayModeControl } from './DisplayModeControl';
import { FaceSignalsPanel } from './FaceSignalsPanel';

const POLL_MS = 2000; // giả định F07 R5; chỉ khi WebSocket không mở (F21)

const STATUS_COLOR: Record<CameraStatus, string> = {
  ONLINE: 'green',
  OFFLINE: 'red',
  UNKNOWN: 'gray',
};

export function LiveViewPage() {
  const { bedId } = useParams();
  const navigate = useNavigate();
  const { token, user } = useAuth();
  const isAdmin = user?.role === 'ADMIN';
  const [editBed, setEditBed] = useState<number | null>(null);
  const [connection, setConnection] = useState<{
    bedId: number;
    cameraId: number;
    version: number;
  } | null>(null);
  const overview = useOverview();
  const beds = overview.data?.beds ?? [];
  const selectedId = bedId ? Number(bedId) : beds[0]?.bed_id;
  const bed = beds.find((b) => b.bed_id === selectedId);
  const connecting = connection?.bedId === selectedId ? connection : null;
  const cameraDetail = useCameraDetail(
    connecting?.cameraId ?? bed?.camera?.id,
    POLL_MS,
    connecting !== null,
  );
  const latest = useEvents({ bed_id: selectedId, limit: 1 });
  const detail = cameraDetail.data;
  const ready =
    connecting &&
    bed?.camera?.id === connecting.cameraId &&
    detail?.status === 'ONLINE' &&
    detail.has_current_frames &&
    detail.config_version >= connecting.version;
  if (ready) setConnection(null);
  const waiting = connecting && !ready;

  if (overview.isPending) return <Loader />;
  const state = bed?.state ?? null;
  const event = latest.data?.items[0];
  // Ưu tiên trạng thái từ chi tiết camera (mới hơn), rồi tới tổng quan.
  const cameraStatus: CameraStatus | null = bed?.camera
    ? (cameraDetail.data?.status ?? bed.camera.status)
    : null;
  const roi = cameraDetail.data?.roi_polygon ?? null;
  const statusText = waiting
    ? vi.live.waitingForCamera
    : cameraStatus
      ? vi.cameraStatus[cameraStatus]
      : vi.camera.notAssigned;

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
                <Group gap="xs">
                  <Badge
                    color={waiting ? 'yellow' : cameraStatus ? STATUS_COLOR[cameraStatus] : 'gray'}
                    variant="light"
                    role="status"
                  >
                    {statusText}
                  </Badge>
                  {isAdmin && (
                    <Button
                      size="xs"
                      variant="light"
                      disabled={!!bed.session || (!!bed.camera && detail?.id !== bed.camera.id)}
                      onClick={() => setEditBed(bed.bed_id)}
                    >
                      {vi.live.connectCamera}
                    </Button>
                  )}
                </Group>
              </Group>
              {isAdmin && editBed === bed.bed_id && !bed.session && (
                <CameraForm
                  camera={bed.camera && detail?.id === bed.camera.id ? detail : null}
                  onClose={() => setEditBed(null)}
                  connect={{
                    bedId: bed.bed_id,
                    bedCode: bed.code,
                    onSaved: (saved) =>
                      setConnection({
                        bedId: bed.bed_id,
                        cameraId: saved.id,
                        version: saved.config_version,
                      }),
                  }}
                />
              )}
              {waiting && (
                <Text size="sm" c="dimmed" role="status">
                  {!detail?.worker_active
                    ? fmt(vi.live.startWorkerHint, { id: String(connecting.cameraId) })
                    : vi.live.checkCameraSource}
                </Text>
              )}
              {isAdmin && bed.session && cameraStatus !== 'ONLINE' && (
                <Text size="sm" c="dimmed">
                  {vi.live.connectActiveSession}
                </Text>
              )}
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
              {/* F22 R7: từ thẻ giường → trang này → Lịch sử theo dõi của giường/phiên. */}
              <Anchor
                size="sm"
                component={Link}
                to={`/timeline?bed=${bed.bed_id}${bed.session ? `&session=${bed.session.id}` : ''}`}
              >
                {vi.alerts.openTimeline}
              </Anchor>
              {bed.camera && cameraStatus ? (
                <>
                  <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                    <Stack gap={4}>
                      <Text size="sm" fw={600}>
                        {vi.live.displayTitle}
                      </Text>
                      <CameraStream
                        cameraId={bed.camera.id}
                        token={token}
                        online={!waiting && cameraStatus === 'ONLINE'}
                        offlineText={statusText}
                        roi={roi}
                        alt={fmt(vi.live.streamAlt, { code: bed.code })}
                      />
                    </Stack>
                    <Stack gap={4}>
                      <Text size="sm" fw={600}>
                        {vi.live.skeletonTitle}
                      </Text>
                      <CameraStream
                        cameraId={bed.camera.id}
                        token={token}
                        online={!waiting && cameraStatus === 'ONLINE'}
                        offlineText={statusText}
                        roi={null}
                        view="skeleton"
                        alt={vi.live.skeletonTitle}
                      />
                    </Stack>
                  </SimpleGrid>
                  <Text size="xs" c="dimmed">
                    {vi.live.skeletonHint}
                  </Text>
                  {cameraDetail.isSuccess && !roi && (
                    <Text size="sm" c="dimmed">
                      {vi.live.roiNotConfigured}
                    </Text>
                  )}
                  {cameraDetail.data && (
                    <DisplayModeControl
                      cameraId={bed.camera.id}
                      mode={cameraDetail.data.display_mode}
                    />
                  )}
                </>
              ) : (
                <Center bg="gray.1" style={{ aspectRatio: '16 / 9', borderRadius: 8 }}>
                  <Text c="dimmed">{statusText}</Text>
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
                    value={state ? <RestStatusBadge status={state.rest_status} /> : vi.common.none}
                  />
                  <Row label={vi.live.faceSignals} value={<FaceSignalsPanel state={state} />} />
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
