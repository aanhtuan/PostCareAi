// Màn hình "Cấu hình camera" (F08 R8–R10; PDF §9.1). Chỉ ADMIN (route bọc RequireRole; API kiểm tra
// lại). Lưu ROI hoặc ngưỡng → API tăng config_version → worker tải lại ≤5 s (F06; A02).
import { Alert, Button, Card, Grid, Group, Loader, Stack, Text, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { Link, useParams } from 'react-router';

import { ApiError } from '../../api/client';
import {
  useCameraDetail,
  useCameraThresholds,
  useSaveRoi,
  useSaveThresholds,
} from '../../api/hooks';
import { useAuth } from '../../auth/useAuth';
import { fmt, vi } from '../../i18n/vi';
import { apiErrorMessage } from '../Management/errorMessage';
import { ImageQualityIndicator } from './ImageQualityIndicator';
import { RoiEditor } from './RoiEditor';
import { ThresholdsForm } from './ThresholdsForm';

/** Làm mới số liệu chất lượng hình ảnh mỗi 2 giây (giả định R10). */
const RUNTIME_POLL_MS = 2000;

const t = vi.cameraConfig;

/** Lỗi lưu → câu tiếng Việt; ROI sai dùng câu theo `details.reason` (cùng mã với web). */
function errorMessage(err: unknown): string {
  if (err instanceof ApiError && err.code === 'INVALID_ROI_POLYGON') {
    const reason = String(err.details.reason ?? '');
    if (reason in t.roi.reasons) return t.roi.reasons[reason as keyof typeof t.roi.reasons];
  }
  return apiErrorMessage(err) ?? vi.common.genericError;
}

export function CameraConfigPage() {
  const cameraId = Number(useParams().cameraId);
  const { token } = useAuth();
  const camera = useCameraDetail(cameraId, RUNTIME_POLL_MS);
  const thresholds = useCameraThresholds(cameraId);
  const saveRoi = useSaveRoi(cameraId);
  const saveThresholds = useSaveThresholds(cameraId);

  if (camera.isPending) return <Loader />;
  if (!camera.data) return <Alert color="red">{vi.common.loadError}</Alert>;
  const cam = camera.data;
  const online = cam.status === 'ONLINE';

  const onError = (err: unknown) =>
    notifications.show({ color: 'red', message: errorMessage(err) });

  return (
    <Stack>
      <Group justify="space-between">
        <Stack gap={0}>
          <Title order={2}>{t.title}</Title>
          <Text c="dimmed">
            {fmt(t.subtitle, {
              name: cam.name,
              bed: cam.bed_code ? fmt(vi.bed.title, { code: cam.bed_code }) : t.noBed,
            })}
          </Text>
        </Stack>
        <Button component={Link} to="/management" variant="default">
          {t.back}
        </Button>
      </Group>
      {!online && (
        <Alert color="orange" variant="light">
          {t.offline}
        </Alert>
      )}
      <Grid>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Card withBorder>
            <Title order={4} mb="xs">
              {t.roi.title}
            </Title>
            <RoiEditor
              cameraId={cam.id}
              token={token}
              online={online}
              initial={cam.roi_polygon}
              saving={saveRoi.isPending}
              onSave={(points) =>
                saveRoi.mutate(points, {
                  onSuccess: () => notifications.show({ color: 'green', message: t.roi.saved }),
                  onError,
                })
              }
            />
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <ImageQualityIndicator runtime={cam.runtime} />
        </Grid.Col>
      </Grid>
      <Card withBorder>
        {thresholds.data ? (
          <ThresholdsForm
            data={thresholds.data}
            saving={saveThresholds.isPending}
            onSave={(overrides) =>
              saveThresholds.mutate(overrides, {
                onSuccess: () =>
                  notifications.show({ color: 'green', message: t.thresholds.saved }),
                onError,
              })
            }
            onReset={() =>
              saveThresholds.mutate(
                {},
                {
                  onSuccess: () =>
                    notifications.show({ color: 'green', message: t.thresholds.resetDone }),
                  onError,
                },
              )
            }
          />
        ) : thresholds.isError ? (
          <Alert color="red">{errorMessage(thresholds.error)}</Alert>
        ) : (
          <Loader />
        )}
      </Card>
    </Stack>
  );
}
