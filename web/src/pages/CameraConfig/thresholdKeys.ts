// Ngưỡng chính hiện trên form "Cấu hình camera" (F08 R5; HS §5.5; event-engine.md §6).
// Danh sách duy nhất phía web. Khóa là đường dẫn trong `config/engine.default.yaml`; nhãn ở vi.ts.

export type ThresholdGroup = 'duration' | 'quality' | 'location' | 'activity' | 'posture';

export const THRESHOLD_GROUPS: readonly { group: ThresholdGroup; keys: readonly string[] }[] = [
  {
    group: 'duration',
    keys: [
      'min_duration_s.RAISING',
      'min_duration_s.SITTING',
      'min_duration_s.AT_EDGE',
      'min_duration_s.STANDING',
      'min_duration_s.OUT_OF_BED',
      'min_duration_s.LYING',
      'min_duration_s.RETURN_TO_BED',
    ],
  },
  {
    group: 'quality',
    keys: ['pose.min_keypoint_visibility', 'quality.low_quality_to_no_observation_s'],
  },
  { group: 'location', keys: ['location.edge_distance_torso', 'location.out_of_roi_margin_torso'] },
  { group: 'activity', keys: ['activity.low_threshold', 'activity.high_threshold'] },
  {
    group: 'posture',
    keys: [
      'posture.lying_enter_deg',
      'posture.lying_exit_deg',
      'posture.sitting_enter_deg',
      'posture.sitting_exit_deg',
    ],
  },
];

export const THRESHOLD_KEYS: readonly string[] = THRESHOLD_GROUPS.flatMap((g) => g.keys);

type Tree = Record<string, unknown>;

/** Đọc giá trị theo đường dẫn `a.b`; không có → `undefined`. */
export function getPath(tree: Tree, path: string): unknown {
  let node: unknown = tree;
  for (const part of path.split('.')) {
    if (!node || typeof node !== 'object') return undefined;
    node = (node as Tree)[part];
  }
  return node;
}

/** Bản sao `tree` với `path` = `value` (`undefined` = xóa khóa, bỏ nhánh rỗng). */
export function setPath(tree: Tree, path: string, value: unknown): Tree {
  const [head, ...rest] = path.split('.');
  const out: Tree = { ...tree };
  if (rest.length === 0) {
    if (value === undefined) delete out[head];
    else out[head] = value;
    return out;
  }
  const child = out[head] && typeof out[head] === 'object' ? (out[head] as Tree) : {};
  const next = setPath(child, rest.join('.'), value);
  if (Object.keys(next).length === 0) delete out[head];
  else out[head] = next;
  return out;
}
