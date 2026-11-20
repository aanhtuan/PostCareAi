// "Theo dõi trực tiếp" (F07; PDF §9.1): ảnh camera qua MJPEG (đã render theo chế độ hiển thị
// trong worker, F28), Bed ROI vẽ đè, chế độ hiển thị, trạng thái camera và phiên. Trạng thái cập nhật realtime qua WebSocket (F21 AC5: `bed.state`,
// `event.created`, `camera.status`); polling 2 s chỉ là đường dự phòng khi mất WebSocket.
import {
  Alert,
  Badge,
  Button,
  Card,
  Center,
  Group,
  Loader,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';

import { useCameraDetail, useOverview } from '../../api/hooks';
import type { CameraStatus } from '../../api/types';
import { useAuth } from '../../auth/useAuth';
import { CameraStream } from '../../components/CameraStream';
import { fmt, vi } from '../../i18n/vi';
import { formatTime } from '../../utils/time';
import { CameraForm } from '../Management/CameraForm';
import { DisplayModeControl } from './DisplayModeControl';
import { LiveJournal } from './LiveJournal';
import { ObservationDetails } from './ObservationDetails';

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
  // Ưu tiên trạng thái từ chi tiết camera (mới hơn), rồi tới tổng quan.
  const cameraStatus: CameraStatus | null = bed?.camera
    ? (cameraDetail.data?.status ?? bed.camera.status)
    : null;
  const roi = cameraDetail.data?.roi_polygon ?? null;
  const paused = !!bed?.session?.paused_at;
  const canObserve = cameraStatus === 'ONLINE' && !waiting && !paused && (!detail || !!roi);
  const state = canObserve ? (bed?.state ?? null) : null;
  const observationReason = paused
    ? vi.capture.pausedShort
    : canObserve
      ? state
        ? vi.quality[state.observation_quality]
        : vi.live.noState
      : undefined;
  const bodyState = state?.body_state ?? 'NO_OBSERVATION';
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
        <Stack>
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
                    c="var(--mantine-color-text)"
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
                  {isAdmin && bed.camera && roi && (
                    <Button
                      component={Link}
                      to={`/cameras/${bed.camera.id}/config?from=live`}
                      size="xs"
                      variant="light"
                    >
                      {vi.live.editRoi}
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
              <Group
                justify="space-between"
                gap={6}
                bg="var(--mantine-color-default-hover)"
                p="xs"
                style={{ borderRadius: 'var(--mantine-radius-sm)' }}
              >
                <Group gap="xs" role="status">
                  <Badge
                    color={bodyState === 'NO_OBSERVATION' ? (state ? 'yellow' : 'gray') : 'teal'}
                    variant="light"
                    c="var(--mantine-color-text)"
                    tt="none"
                  >
                    {vi.bodyState[bodyState]}
                  </Badge>
                  {observationReason && <Text size="sm">{observationReason}</Text>}
                </Group>
                {state && (
                  <Text size="xs" c="dimmed">
                    {fmt(vi.live.updatedAt, { time: formatTime(state.updated_at) })}
                  </Text>
                )}
              </Group>
              {bed.camera && cameraStatus ? (
                <>
                  {cameraDetail.isSuccess && !roi && (
                    <Alert color="yellow" variant="light">
                      <Group justify="space-between" gap="xs">
                        <div>
                          <Text fw={600} size="sm">
                            {vi.live.roiNotConfigured}
                          </Text>
                          <Text size="sm">
                            {isAdmin ? vi.live.drawRoiHint : vi.live.askAdminForRoi}
                          </Text>
                        </div>
                        {isAdmin && (
                          <Button
                            component={Link}
                            to={`/cameras/${bed.camera.id}/config?from=live`}
                          >
                            {vi.live.drawRoi}
                          </Button>
                        )}
                      </Group>
                    </Alert>
                  )}
                  <SimpleGrid type="container" cols={{ base: 1, '640px': 2 }} spacing="sm">
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
                </>
              ) : (
                <Center bg="gray.1" mih={180} style={{ borderRadius: 8 }}>
                  <Text c="dimmed">{statusText}</Text>
                </Center>
              )}
            </Stack>
          </Card>
          <SimpleGrid
            type="container"
            cols={{ base: 1, '640px': 2 }}
            spacing="sm"
            style={{ alignItems: 'start' }}
          >
            <ObservationDetails cameraName={bed.camera?.name} state={state}>
              {bed.camera && detail && (
                <DisplayModeControl cameraId={bed.camera.id} mode={detail.display_mode} />
              )}
              {bed.camera && (
                <Text size="xs" c="dimmed">
                  {vi.live.skeletonHint}
                </Text>
              )}
            </ObservationDetails>
            <LiveJournal key={bed.bed_id} bedId={bed.bed_id} sessionId={bed.session?.id} />
          </SimpleGrid>
        </Stack>
      )}
    </Stack>
  );
}
