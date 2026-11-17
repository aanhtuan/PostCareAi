// Bed ROI vẽ đè lên ảnh camera (F07 R6). Toạ độ chuẩn hóa 0–1 nhân với kích thước ảnh đang hiển thị.
import { vi } from '../i18n/vi';

type Props = {
  polygon: number[][] | null | undefined;
  width: number;
  height: number;
};

export function RoiOverlay({ polygon, width, height }: Props) {
  if (!polygon || polygon.length < 3 || width <= 0 || height <= 0) return null;
  const points = polygon.map(([x, y]) => `${round(x * width)},${round(y * height)}`).join(' ');
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      aria-label={vi.live.roi}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}
    >
      <polygon
        points={points}
        fill="rgba(46, 204, 113, 0.10)"
        stroke="#2ecc71"
        strokeWidth={2}
        strokeDasharray="6 4"
      />
    </svg>
  );
}

function round(v: number): number {
  return Math.round(v * 10) / 10;
}
