// Ảnh camera trực tiếp qua MJPEG (F07 R3–R6; ADR-0005). `<img>` không gửi được header nên token
// đi qua query (api-conventions.md). Camera không hoạt động hoặc ảnh lỗi → ẩn ảnh, hiện thông báo,
// để không có khung hình đứng yên khiến người xem tưởng vẫn đang quan sát (PDF §4.3).
// Từ F28, worker đã render JPEG theo chế độ hiển thị; component này không đổi.
import { Center, Stack, Text } from '@mantine/core';
import { useEffect, useRef, useState } from 'react';

import { streamUrl } from '../api/stream';
import { vi } from '../i18n/vi';
import { RoiOverlay } from './RoiOverlay';

type Props = {
  cameraId: number;
  token: string | null;
  online: boolean;
  roi: number[][] | null | undefined;
  alt: string;
  /** Câu hiện khi camera không hoạt động (mặc định "Mất kết nối camera"). */
  offlineText?: string;
  offlineHint?: string;
  /** Thử mở lại stream sau lỗi ảnh (giả định 3 s). */
  retryMs?: number;
  view?: 'display' | 'skeleton';
};

const DEFAULT_RETRY_MS = 3000;

export function CameraStream({
  cameraId,
  token,
  online,
  roi,
  alt,
  offlineText = vi.cameraStatus.OFFLINE,
  offlineHint = vi.live.offlineHint,
  retryMs = DEFAULT_RETRY_MS,
  view = 'display',
}: Props) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const [prevOnline, setPrevOnline] = useState(online);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const imgRef = useRef<HTMLImageElement | null>(null);

  // Camera online lại → mở stream mới (URL mới để trình duyệt không dùng lại kết nối cũ).
  if (online !== prevOnline) {
    setPrevOnline(online);
    if (online) {
      setAttempt((a) => a + 1);
      setFailed(false);
    }
  }

  useEffect(() => {
    if (!failed) return;
    const t = setTimeout(() => {
      setFailed(false);
      setAttempt((a) => a + 1);
    }, retryMs);
    return () => clearTimeout(t);
  }, [failed, retryMs]);

  const showImage = online && !failed;

  useEffect(() => {
    const el = imgRef.current;
    if (!showImage || !el) return;
    const observer = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [showImage, attempt]);

  if (!showImage) {
    return (
      <Center
        bg="dark.7"
        style={{ aspectRatio: '16 / 9', width: '100%', borderRadius: 8 }}
        data-testid="camera-offline"
      >
        <Stack gap={4} align="center" p="md">
          <Text c="white" fw={700} size="lg">
            {failed ? vi.cameraStatus.OFFLINE : offlineText}
          </Text>
          <Text c="gray.4" size="sm" ta="center">
            {offlineHint}
          </Text>
        </Stack>
      </Center>
    );
  }

  return (
    <div style={{ position: 'relative', width: '100%', lineHeight: 0 }}>
      <img
        key={attempt}
        ref={imgRef}
        src={streamUrl(cameraId, token, attempt, view)}
        alt={alt}
        style={{ display: 'block', width: '100%', height: 'auto', borderRadius: 8 }}
        onLoad={(e) => setSize({ w: e.currentTarget.clientWidth, h: e.currentTarget.clientHeight })}
        onError={() => setFailed(true)}
      />
      <RoiOverlay polygon={roi} width={size.w} height={size.h} />
    </div>
  );
}
