import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router';

import {
  useAlerts,
  useCameraDetail,
  useDemoAction,
  useEvents,
  useOverview,
  useSessions,
  useVideoDemo,
} from '../../api/hooks';
import { useAuth } from '../../auth/useAuth';
import { AlertCard } from '../../components/AlertCard';
import { AlertDetailModal } from '../../components/AlertDetailModal';
import { PriorityBadge } from '../../components/Badges';
import { CameraStream } from '../../components/CameraStream';
import { fmt, vi } from '../../i18n/vi';
import { formatDateTime } from '../../utils/time';
import { DisplayModeControl } from '../LiveView/DisplayModeControl';

export function DemoPage() {
  const { user, token } = useAuth();
  const demo = useVideoDemo();
  const action = useDemoAction();
  const overview = useOverview();
  const setup = demo.data?.setup;
  const run = demo.data?.run;
  const camera = useCameraDetail(setup?.camera_id, 1000);
  const events = useEvents({ session_id: run?.session_id, limit: 50 }, !!run);
  const alerts = useAlerts(
    { bed_id: setup?.bed_id, status: ['PENDING', 'ACKNOWLEDGED'], limit: 200 },
    !!setup,
  );
  const history = useSessions({ bed_id: setup?.bed_id, limit: 50 }, !!setup);
  const [detailId, setDetailId] = useState<number | null>(null);
  const admin = user?.role === 'ADMIN';
  const running = run?.status === 'RUNNING';
  const active = running || run?.status === 'FINISHING' || run?.status === 'INTERRUPTED';
  const bed = overview.data?.beds.find((b) => b.bed_id === setup?.bed_id);
  const detail = alerts.data?.items.find((a) => a.id === detailId) ?? null;

  if (demo.isPending) return <Loader />;
  if (demo.isError) return <Alert color="red">{vi.demo.loadError}</Alert>;

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>{vi.demo.title}</Title>
        <Badge color="violet" variant="light">
          {vi.demo.recorded}
        </Badge>
      </Group>
      <Text>{vi.demo.description}</Text>
      {!demo.data?.enabled && <Alert color="yellow">{vi.demo.disabled}</Alert>}
      {!demo.data?.available && <Alert color="yellow">{vi.demo.missing}</Alert>}
      <Card withBorder>
        <Stack gap="sm">
          <Select
            label={vi.demo.clip}
            data={[{ value: 'pexels-8090735', label: vi.demo.clipTitle }]}
            value="pexels-8090735"
            allowDeselect={false}
          />
          <Group>
            <Text size="sm" c="dimmed">
              {vi.demo.credit}
            </Text>
            <Anchor href="https://www.pexels.com/video/8090735/" target="_blank" rel="noreferrer">
              {vi.demo.source}
            </Anchor>
          </Group>
          <Text size="sm" c="dimmed">
            {vi.demo.limitation}
          </Text>
          <Group>
            <Badge color={running ? 'green' : 'gray'}>
              {run ? vi.demo.statuses[run.status] : vi.demo.idle}
            </Badge>
            {run && (
              <Text size="sm">
                {fmt(vi.demo.run, { id: run.session_id, time: formatDateTime(run.started_at) })}
              </Text>
            )}
          </Group>
          {admin ? (
            <Group>
              {!setup && (
                <Button
                  variant="default"
                  disabled={!demo.data?.enabled || !demo.data?.available}
                  loading={action.isPending}
                  onClick={() => action.mutate({ kind: 'prepare' })}
                >
                  {vi.demo.prepare}
                </Button>
              )}
              <Button
                disabled={!demo.data?.enabled || !demo.data?.available || active}
                loading={action.isPending}
                onClick={() => action.mutate({ kind: 'start' })}
              >
                {run ? vi.demo.replay : vi.demo.start}
              </Button>
              {active && (
                <Button
                  color="red"
                  variant="outline"
                  loading={action.isPending}
                  onClick={() => action.mutate({ kind: 'stop', sessionId: run.session_id })}
                >
                  {run.status === 'INTERRUPTED' ? vi.demo.closeInterrupted : vi.demo.stop}
                </Button>
              )}
              {setup && (
                <Anchor component={Link} to={`/cameras/${setup.camera_id}/config`}>
                  {vi.demo.configure}
                </Anchor>
              )}
            </Group>
          ) : (
            <Text size="sm" c="dimmed">
              {vi.demo.adminOnly}
            </Text>
          )}
          {action.isError && <Alert color="red">{action.error.message}</Alert>}
          {run && !active && <Text size="sm">{vi.demo.completedHint}</Text>}
        </Stack>
      </Card>
      {setup && (
        <>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {(['display', 'skeleton'] as const).map((view) => (
              <Card key={view} withBorder>
                <Stack gap="xs">
                  <Text fw={600}>
                    {view === 'display' ? vi.live.displayTitle : vi.live.skeletonTitle}
                  </Text>
                  <CameraStream
                    key={`${run?.session_id}-${view}`}
                    cameraId={setup.camera_id}
                    token={token}
                    online={running && camera.data?.status === 'ONLINE'}
                    offlineText={
                      running ? vi.demo.starting : run ? vi.demo.statuses[run.status] : vi.demo.idle
                    }
                    offlineHint={running ? vi.demo.starting : vi.demo.readyHint}
                    roi={
                      view === 'display' && camera.data?.display_mode !== 'SKELETON'
                        ? (camera.data?.roi_polygon ?? null)
                        : null
                    }
                    view={view}
                    alt={view === 'display' ? vi.live.displayTitle : vi.live.skeletonTitle}
                  />
                </Stack>
              </Card>
            ))}
          </SimpleGrid>
          {camera.data && (
            <DisplayModeControl cameraId={setup.camera_id} mode={camera.data.display_mode} />
          )}
          {running && (
            <Text fw={700} size="xl">
              {
                vi.bodyState[
                  bed?.state && new Date(bed.state.updated_at) >= new Date(run.started_at)
                    ? bed.state.body_state
                    : 'NO_OBSERVATION'
                ]
              }
            </Text>
          )}
          <SimpleGrid cols={{ base: 1, md: 2 }}>
            <Card withBorder>
              <Stack>
                <Title order={3}>{vi.demo.events}</Title>
                {events.isError ? (
                  <Alert color="red">{vi.demo.loadError}</Alert>
                ) : events.isPending && run ? (
                  <Loader />
                ) : !events.data?.items.length ? (
                  <Text c="dimmed">{vi.live.noEvent}</Text>
                ) : (
                  events.data.items.map((event) => (
                    <Group key={event.id}>
                      <Text>
                        {formatDateTime(event.occurred_at)} · {vi.event[event.code]}
                      </Text>
                      <PriorityBadge priority={event.priority} />
                    </Group>
                  ))
                )}
                {run && (
                  <Anchor
                    component={Link}
                    to={`/timeline?bed=${setup.bed_id}&session=${run.session_id}`}
                  >
                    {vi.alerts.openTimeline}
                  </Anchor>
                )}
              </Stack>
            </Card>
            <Stack>
              <Title order={3}>{vi.demo.openAlerts}</Title>
              <Text size="sm" c="dimmed">
                {vi.demo.openAlertsHint}
              </Text>
              {alerts.isError ? (
                <Alert color="red">{vi.demo.loadError}</Alert>
              ) : alerts.isPending ? (
                <Loader />
              ) : !alerts.data?.items.length ? (
                <Text c="dimmed">{vi.demo.noOpenAlerts}</Text>
              ) : (
                alerts.data.items.map((alert) => (
                  <AlertCard key={alert.id} alert={alert} onDetail={() => setDetailId(alert.id)} />
                ))
              )}
            </Stack>
          </SimpleGrid>
          <Card withBorder>
            <Stack gap="xs">
              <Title order={3}>{vi.demo.history}</Title>
              {history.data?.items.map((session) => (
                <Anchor
                  key={session.id}
                  component={Link}
                  to={`/timeline?bed=${setup.bed_id}&session=${session.id}`}
                >
                  {fmt(vi.demo.run, { id: session.id, time: formatDateTime(session.started_at) })}
                </Anchor>
              ))}
            </Stack>
          </Card>
        </>
      )}
      <AlertDetailModal alert={detail} onClose={() => setDetailId(null)} />
    </Stack>
  );
}
