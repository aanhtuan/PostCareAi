// Hình người que + vùng giường vẽ lại từ trạng thái cơ thể (mô phỏng, không phải hình ảnh thật).
import type { BodyState } from '../../api/types';
import { vi } from '../../i18n/vi';

type P = [number, number];
type Pose = {
  head: P;
  neck: P;
  hip: P;
  hand: [P, P];
  knee: [P, P];
  foot: [P, P];
};

// Toạ độ trong khung 460×300; vùng giường khớp ROI mẫu của seed (x 0.2–0.8, y 0.25–0.85).
const ROI = { x: 80, y: 75, w: 240, h: 180 };

const POSES: Record<Exclude<BodyState, 'NO_OBSERVATION'>, Pose> = {
  LYING: {
    head: [118, 165],
    neck: [138, 165],
    hip: [210, 165],
    hand: [
      [180, 150],
      [180, 180],
    ],
    knee: [
      [250, 158],
      [250, 172],
    ],
    foot: [
      [292, 158],
      [292, 172],
    ],
  },
  RAISING: {
    head: [150, 128],
    neck: [162, 142],
    hip: [210, 175],
    hand: [
      [180, 175],
      [190, 180],
    ],
    knee: [
      [250, 170],
      [250, 180],
    ],
    foot: [
      [292, 170],
      [292, 180],
    ],
  },
  SITTING: {
    head: [200, 100],
    neck: [200, 120],
    hip: [200, 185],
    hand: [
      [182, 175],
      [218, 175],
    ],
    knee: [
      [245, 180],
      [245, 190],
    ],
    foot: [
      [288, 180],
      [288, 190],
    ],
  },
  AT_EDGE: {
    head: [300, 100],
    neck: [300, 120],
    hip: [305, 185],
    hand: [
      [285, 178],
      [322, 178],
    ],
    knee: [
      [345, 188],
      [350, 195],
    ],
    foot: [
      [345, 245],
      [352, 248],
    ],
  },
  STANDING: {
    head: [345, 92],
    neck: [345, 112],
    hip: [345, 180],
    hand: [
      [330, 175],
      [360, 175],
    ],
    knee: [
      [340, 222],
      [352, 222],
    ],
    foot: [
      [338, 265],
      [354, 265],
    ],
  },
  OUT_OF_BED: {
    head: [410, 92],
    neck: [410, 112],
    hip: [410, 180],
    hand: [
      [395, 175],
      [425, 175],
    ],
    knee: [
      [403, 222],
      [418, 222],
    ],
    foot: [
      [400, 265],
      [422, 265],
    ],
  },
};

function line(a: P, b: P, key: string) {
  return <line key={key} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} />;
}

export function SkeletonView({ bodyState }: { bodyState: BodyState | null }) {
  const pose = bodyState && bodyState !== 'NO_OBSERVATION' ? POSES[bodyState] : null;
  const inside = bodyState !== 'OUT_OF_BED';
  return (
    <svg
      viewBox="0 0 460 300"
      role="img"
      aria-label={vi.live.simulatedMode}
      style={{ width: '100%', maxWidth: 640, background: '#10202b', borderRadius: 8 }}
    >
      <polygon
        points={`${ROI.x},${ROI.y} ${ROI.x + ROI.w},${ROI.y} ${ROI.x + ROI.w},${ROI.y + ROI.h} ${ROI.x},${ROI.y + ROI.h}`}
        fill={inside ? 'rgba(46, 204, 113, 0.12)' : 'rgba(231, 76, 60, 0.12)'}
        stroke={inside ? '#2ecc71' : '#e74c3c'}
        strokeDasharray="6 4"
        strokeWidth={2}
      />
      <text x={ROI.x + 6} y={ROI.y + 16} fill="#9fe6bd" fontSize={12}>
        {vi.live.roi}
      </text>
      {pose ? (
        <g stroke="#f1c40f" strokeWidth={4} strokeLinecap="round" fill="none">
          <circle cx={pose.head[0]} cy={pose.head[1]} r={10} fill="#f1c40f" stroke="none" />
          {line(pose.neck, pose.hip, 'torso')}
          {line(pose.neck, pose.hand[0], 'arm0')}
          {line(pose.neck, pose.hand[1], 'arm1')}
          {line(pose.hip, pose.knee[0], 'thigh0')}
          {line(pose.hip, pose.knee[1], 'thigh1')}
          {line(pose.knee[0], pose.foot[0], 'shin0')}
          {line(pose.knee[1], pose.foot[1], 'shin1')}
        </g>
      ) : (
        <text x={230} y={170} fill="#bbb" fontSize={56} textAnchor="middle">
          ?
        </text>
      )}
    </svg>
  );
}
