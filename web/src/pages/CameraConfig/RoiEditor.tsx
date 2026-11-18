// Vẽ Bed ROI bằng cách click lên khung hình camera (F08 R8; PDF §7.2; QA#15).
// Toạ độ chuẩn hóa 0–1 theo kích thước khung đang hiển thị: x = px / width, y = py / height.
// Camera offline → nền trống, vẫn sửa được polygon đã lưu (giả định R8).
import { Alert, Box, Button, Center, Group, Stack, Text } from '@mantine/core';
import { useEffect, useRef, useState, type MouseEvent } from 'react';

import { streamUrl } from '../../api/stream';
import { fmt, vi } from '../../i18n/vi';
import { validatePolygon } from '../../utils/polygon';

type Props = {
  cameraId: number;
  token: string | null;
  online: boolean;
  initial: number[][] | null | undefined;
  saving?: boolean;
  onSave: (points: number[][]) => void;
  retryMs?: number;
};

const t = vi.cameraConfig.roi;
const HANDLE_PX = 14;

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));
const round4 = (v: number) => Math.round(v * 10000) / 10000;

export function RoiEditor({
  cameraId,
  token,
  online,
  initial,
  saving = false,
  onSave,
  retryMs = 3000,
}: Props) {
  const [points, setPoints] = useState<number[][]>(() => (initial ?? []).map((p) => [...p]));
  const [selected, setSelected] = useState<number | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const drag = useRef<{ index: number; moved: boolean } | null>(null);
  const suppressClick = useRef(false);

  useEffect(() => {
    if (!failed) return;
    const timer = setTimeout(() => {
      setFailed(false);
      setAttempt((a) => a + 1);
    }, retryMs);
    return () => clearTimeout(timer);
  }, [failed, retryMs]);

  const reason = validatePolygon(points);
  const showImage = online && !failed;

  function toNormalized(e: MouseEvent): [number, number] | null {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) return null;
    return [
      round4(clamp01((e.clientX - rect.left) / rect.width)),
      round4(clamp01((e.clientY - rect.top) / rect.height)),
    ];
  }

  function onCanvasClick(e: MouseEvent) {
    if (suppressClick.current) {
      suppressClick.current = false;
      return;
    }
    const p = toNormalized(e);
    if (!p) return;
    setPoints((prev) => [...prev, p]);
    setSelected(null);
  }

  function onMouseMove(e: MouseEvent) {
    const d = drag.current;
    if (!d) return;
    const p = toNormalized(e);
    if (!p) return;
    d.moved = true;
    setPoints((prev) => prev.map((q, i) => (i === d.index ? p : q)));
  }

  function endDrag() {
    if (drag.current?.moved) suppressClick.current = true;
    drag.current = null;
  }

  function deletePoint() {
    const index = selected ?? points.length - 1;
    setPoints((prev) => prev.filter((_, i) => i !== index));
    setSelected(null);
  }

  const polygonPoints = points.map(([x, y]) => `${x},${y}`).join(' ');

  return (
    <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {t.hint}
      </Text>
      <Box
        ref={canvasRef}
        data-testid="roi-canvas"
        aria-label={t.canvas}
        onClick={onCanvasClick}
        onMouseMove={onMouseMove}
        onMouseUp={endDrag}
        onMouseLeave={endDrag}
        style={{
          position: 'relative',
          width: '100%',
          lineHeight: 0,
          cursor: 'crosshair',
          userSelect: 'none',
          borderRadius: 8,
          overflow: 'hidden',
        }}
      >
        {showImage ? (
          <img
            key={attempt}
            src={streamUrl(cameraId, token, attempt)}
            alt={t.title}
            draggable={false}
            style={{ display: 'block', width: '100%', height: 'auto' }}
            onError={() => setFailed(true)}
          />
        ) : (
          <Center bg="dark.7" style={{ aspectRatio: '16 / 9', width: '100%' }}>
            <Text c="white" fw={700}>
              {vi.cameraStatus.OFFLINE}
            </Text>
          </Center>
        )}
        <svg
          viewBox="0 0 1 1"
          preserveAspectRatio="none"
          width="100%"
          height="100%"
          style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
          aria-hidden
        >
          {points.length >= 3 ? (
            <polygon
              points={polygonPoints}
              fill={reason ? 'rgba(231, 76, 60, 0.15)' : 'rgba(46, 204, 113, 0.15)'}
              stroke={reason ? '#e74c3c' : '#2ecc71'}
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
          ) : (
            points.length === 2 && (
              <polyline
                points={polygonPoints}
                fill="none"
                stroke="#f1c40f"
                strokeWidth={2}
                vectorEffect="non-scaling-stroke"
              />
            )
          )}
        </svg>
        {points.map(([x, y], i) => (
          <button
            key={i}
            type="button"
            aria-label={fmt(t.point, { n: i + 1 })}
            aria-pressed={selected === i}
            onMouseDown={(e) => {
              e.preventDefault();
              e.stopPropagation();
              drag.current = { index: i, moved: false };
            }}
            onClick={(e) => {
              e.stopPropagation();
              suppressClick.current = false;
              setSelected(i);
            }}
            style={{
              position: 'absolute',
              left: `${x * 100}%`,
              top: `${y * 100}%`,
              width: HANDLE_PX,
              height: HANDLE_PX,
              transform: 'translate(-50%, -50%)',
              borderRadius: '50%',
              border: '2px solid white',
              background: selected === i ? '#e67e22' : '#2ecc71',
              cursor: 'grab',
              padding: 0,
            }}
          />
        ))}
      </Box>
      <Group justify="space-between">
        <Text size="sm">{fmt(t.points, { n: points.length })}</Text>
        <Group gap="xs">
          <Button variant="default" onClick={deletePoint} disabled={points.length === 0}>
            {t.deletePoint}
          </Button>
          <Button
            variant="default"
            onClick={() => {
              setPoints([]);
              setSelected(null);
            }}
            disabled={points.length === 0}
          >
            {t.clear}
          </Button>
          <Button onClick={() => onSave(points)} disabled={reason !== null} loading={saving}>
            {t.save}
          </Button>
        </Group>
      </Group>
      {reason && (
        <Alert color="orange" variant="light" py="xs">
          {t.reasons[reason]}
        </Alert>
      )}
    </Stack>
  );
}
