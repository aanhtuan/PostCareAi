// Kiểm tra polygon Bed ROI phía web để báo lỗi ngay khi vẽ (F08 R3). Bản tương đương của
// `validate_roi_polygon` (server/src/postcare/schemas/roi.py), cùng mã lý do; backend vẫn quyết định.

export const MAX_ROI_POINTS = 20;
const EPS = 1e-9;

export type RoiReason =
  | 'TOO_FEW_POINTS'
  | 'TOO_MANY_POINTS'
  | 'INVALID_POINT'
  | 'OUT_OF_RANGE'
  | 'DUPLICATE_POINT'
  | 'SELF_INTERSECTION'
  | 'ZERO_AREA';

type P = [number, number];

/** `null` = hợp lệ; ngược lại là lý do đầu tiên gặp (cùng thứ tự kiểm tra với backend). */
export function validatePolygon(points: readonly (readonly number[])[]): RoiReason | null {
  const pts: P[] = [];
  for (const p of points) {
    if (p.length !== 2 || !p.every((v) => typeof v === 'number' && Number.isFinite(v))) {
      return 'INVALID_POINT';
    }
    const [x, y] = p as [number, number];
    if (x < 0 || x > 1 || y < 0 || y > 1) return 'OUT_OF_RANGE';
    pts.push([x, y]);
  }
  const n = pts.length;
  if (n < 3) return 'TOO_FEW_POINTS';
  if (n > MAX_ROI_POINTS) return 'TOO_MANY_POINTS';
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (Math.abs(pts[i][0] - pts[j][0]) < EPS && Math.abs(pts[i][1] - pts[j][1]) < EPS) {
        return 'DUPLICATE_POINT';
      }
    }
  }
  for (let i = 0; i < n; i++) {
    const a1 = pts[i];
    const a2 = pts[(i + 1) % n];
    for (let j = i + 1; j < n; j++) {
      if ((j + 1) % n === i || j === (i + 1) % n) continue; // cạnh kề chung một đỉnh
      if (segmentsIntersect(a1, a2, pts[j], pts[(j + 1) % n])) return 'SELF_INTERSECTION';
    }
  }
  if (Math.abs(area(pts)) < EPS) return 'ZERO_AREA';
  return null;
}

function area(pts: P[]): number {
  let s = 0;
  for (let i = 0; i < pts.length; i++) {
    const [x1, y1] = pts[i];
    const [x2, y2] = pts[(i + 1) % pts.length];
    s += x1 * y2 - x2 * y1;
  }
  return s / 2;
}

function orient(p: P, q: P, r: P): number {
  return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]);
}

function onSegment(p: P, q: P, r: P): boolean {
  return (
    Math.min(p[0], q[0]) - EPS <= r[0] &&
    r[0] <= Math.max(p[0], q[0]) + EPS &&
    Math.min(p[1], q[1]) - EPS <= r[1] &&
    r[1] <= Math.max(p[1], q[1]) + EPS
  );
}

function opposite(a: number, b: number): boolean {
  return (a > EPS && b < -EPS) || (a < -EPS && b > EPS);
}

function segmentsIntersect(a1: P, a2: P, b1: P, b2: P): boolean {
  const d1 = orient(b1, b2, a1);
  const d2 = orient(b1, b2, a2);
  const d3 = orient(a1, a2, b1);
  const d4 = orient(a1, a2, b2);
  if (opposite(d1, d2) && opposite(d3, d4)) return true;
  return (
    (Math.abs(d1) <= EPS && onSegment(b1, b2, a1)) ||
    (Math.abs(d2) <= EPS && onSegment(b1, b2, a2)) ||
    (Math.abs(d3) <= EPS && onSegment(a1, a2, b1)) ||
    (Math.abs(d4) <= EPS && onSegment(a1, a2, b2))
  );
}
