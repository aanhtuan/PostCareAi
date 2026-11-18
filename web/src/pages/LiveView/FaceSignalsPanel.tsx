// Khối "Tín hiệu khuôn mặt" trên "Theo dõi trực tiếp" (F26 R9): trạng thái mặt và các tín hiệu
// đang bật từ `bed.state`. Mặt không quan sát được → "Không đủ dữ liệu khuôn mặt", không bao giờ
// hàm ý bình thường (HS §9.1).
import { Badge, Group, Stack, Text } from '@mantine/core';

import type { BedStateOut } from '../../api/types';
import { vi } from '../../i18n/vi';

type FaceSignals = BedStateOut['face_signals'];
type SignalKey = keyof FaceSignals;

// Thứ tự hiển thị. "Nhắm mắt kéo dài" thay cho "Mắt đóng" khi cả hai cùng bật.
const ORDER: SignalKey[] = [
  'eyes_closed_prolonged',
  'eyes_closed',
  'brow_down',
  'eye_squint',
  'nose_sneer',
  'mouth_change',
];

function activeFaceSignals(signals: FaceSignals): SignalKey[] {
  return ORDER.filter(
    (key) => signals[key] && !(key === 'eyes_closed' && signals.eyes_closed_prolonged),
  );
}

export function FaceSignalsPanel({
  state,
}: {
  state: Pick<BedStateOut, 'face_status' | 'face_signals'> | null;
}) {
  if (!state) return <Text size="sm">{vi.common.none}</Text>;
  if (state.face_status !== 'OK') {
    return (
      <Stack gap={0} aria-label={vi.live.faceSignals}>
        <Text size="sm">{vi.live.faceNoData}</Text>
        <Text size="xs" c="dimmed">
          {vi.faceStatus[state.face_status]}
        </Text>
      </Stack>
    );
  }
  const active = activeFaceSignals(state.face_signals);
  return (
    <Stack gap={4} aria-label={vi.live.faceSignals}>
      <Text size="sm">{vi.faceStatus.OK}</Text>
      {active.length > 0 ? (
        <Group gap={4}>
          {active.map((key) => (
            <Badge key={key} color="orange" variant="light">
              {vi.faceSignal[key]}
            </Badge>
          ))}
        </Group>
      ) : (
        <Text size="xs" c="dimmed">
          {vi.live.faceNoSignal}
        </Text>
      )}
    </Stack>
  );
}
