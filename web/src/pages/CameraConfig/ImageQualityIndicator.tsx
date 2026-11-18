// Chỉ báo chất lượng hình ảnh (F08 R10; PDF §9.1): độ sáng trung bình 0–255 và FPS từ heartbeat
// của worker (khối `runtime`, F06). Chỉ hiển thị số liệu, không kết luận tốt/kém (nguồn không có ngưỡng).
import { Card, Group, Stack, Text } from '@mantine/core';

import type { CameraRuntimeOut } from '../../api/types';
import { fmt, vi } from '../../i18n/vi';
import { formatTime } from '../../utils/time';

const t = vi.cameraConfig.imageQuality;
const number = (v: number, digits: number) =>
  v.toLocaleString('vi-VN', { maximumFractionDigits: digits, minimumFractionDigits: 0 });

export function ImageQualityIndicator({
  runtime,
}: {
  runtime: CameraRuntimeOut | null | undefined;
}) {
  return (
    <Card withBorder>
      <Text fw={700} mb="xs">
        {t.title}
      </Text>
      {runtime ? (
        <Stack gap={4}>
          <Group gap="xl">
            <Stack gap={0}>
              <Text size="sm" c="dimmed">
                {t.brightness}
              </Text>
              <Text size="xl" fw={700} data-testid="quality-brightness">
                {runtime.brightness == null ? vi.common.none : number(runtime.brightness, 0)}
              </Text>
            </Stack>
            <Stack gap={0}>
              <Text size="sm" c="dimmed">
                {t.fps}
              </Text>
              <Text size="xl" fw={700} data-testid="quality-fps">
                {runtime.fps == null ? vi.common.none : number(runtime.fps, 1)}
              </Text>
            </Stack>
          </Group>
          <Text size="xs" c="dimmed">
            {fmt(t.updatedAt, { time: formatTime(runtime.updated_at) })}
          </Text>
        </Stack>
      ) : (
        <Text c="dimmed">{t.noData}</Text>
      )}
    </Card>
  );
}
