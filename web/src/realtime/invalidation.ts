// Ánh xạ message WebSocket → cập nhật cache TanStack Query (không giữ state song song).
import type { QueryClient } from '@tanstack/react-query';

import {
  PRIORITIES,
  type AlertCreatedOut,
  type BedStateOut,
  type CameraStatusOut,
  type OverviewOut,
  type Priority,
} from '../api/types';
import type { WsMessage } from './wsClient';

const MONITORING_KEYS = ['overview', 'alerts', 'events', 'timeline', 'handover'];

/**
 * F21: invalidate được gộp trong cửa sổ ngắn. Một chuỗi message liên tiếp (worker gửi nhiều sự
 * kiện, nhiều thao tác cảnh báo) chỉ gây một lần refetch cho mỗi query thay vì một lần mỗi
 * message (`invalidateQueries` mặc định hủy rồi gọi lại request đang chạy). Hằng số UI
 * *(giả định F21)*, vẫn trong mục tiêu cập nhật ≤ 1 s.
 */
export const INVALIDATE_COALESCE_MS = 200;

type Pending = { keys: Set<string>; timer: ReturnType<typeof setTimeout> };
const pending = new WeakMap<QueryClient, Pending>();

function scheduleInvalidate(qc: QueryClient, keys: readonly string[]): void {
  let p = pending.get(qc);
  if (!p) {
    p = {
      keys: new Set(),
      timer: setTimeout(() => flushInvalidations(qc), INVALIDATE_COALESCE_MS),
    };
    pending.set(qc, p);
  }
  for (const k of keys) p.keys.add(k);
}

/** Thực hiện ngay các invalidate đang chờ (dùng khi kết nối lại và trong test). */
export function flushInvalidations(qc: QueryClient): void {
  const p = pending.get(qc);
  if (!p) return;
  clearTimeout(p.timer);
  pending.delete(qc);
  for (const key of p.keys) void qc.invalidateQueries({ queryKey: [key] });
}

export function invalidateAll(qc: QueryClient): void {
  const p = pending.get(qc);
  if (p) {
    clearTimeout(p.timer);
    pending.delete(qc);
  }
  for (const key of [...MONITORING_KEYS, 'beds', 'sessions', 'patients', 'cameras']) {
    void qc.invalidateQueries({ queryKey: [key] });
  }
}

function higher(a: Priority | null, b: Priority): Priority {
  return a !== null && PRIORITIES.indexOf(a) >= PRIORITIES.indexOf(b) ? a : b;
}

function updateOverview(qc: QueryClient, fn: (old: OverviewOut) => OverviewOut): void {
  qc.setQueryData<OverviewOut>(['overview'], (old) => (old ? fn(old) : old));
}

export function applyMessage(qc: QueryClient, msg: WsMessage): void {
  switch (msg.type) {
    case 'bed.state': {
      const state = msg.payload as BedStateOut;
      updateOverview(qc, (old) => ({
        ...old,
        beds: old.beds.map((b) => (b.bed_id === state.bed_id ? { ...b, state } : b)),
      }));
      break;
    }
    case 'camera.status': {
      const cam = msg.payload as CameraStatusOut;
      updateOverview(qc, (old) => ({
        ...old,
        beds: old.beds.map((b) =>
          b.camera && b.camera.id === cam.camera_id
            ? { ...b, camera: { ...b.camera, status: cam.status } }
            : b,
        ),
      }));
      scheduleInvalidate(qc, ['beds', 'cameras']);
      break;
    }
    case 'event.created':
      scheduleInvalidate(qc, ['events', 'timeline', 'handover']);
      break;
    case 'alert.created': {
      // Thẻ giường đổi ngay sang "Cảnh báo mới" (F21 R7); refetch gộp sau đó xác nhận số liệu.
      const { alert } = msg.payload as AlertCreatedOut;
      const bedId = alert?.bed?.id;
      const priority = alert?.event?.priority;
      if (bedId !== undefined && priority) {
        updateOverview(qc, (old) => ({
          ...old,
          beds: old.beds.map((b) =>
            b.bed_id === bedId
              ? {
                  ...b,
                  pending_alert_count: b.pending_alert_count + 1,
                  max_open_priority: higher(b.max_open_priority, priority),
                }
              : b,
          ),
        }));
      }
      scheduleInvalidate(qc, MONITORING_KEYS);
      break;
    }
    case 'alert.updated':
      scheduleInvalidate(qc, MONITORING_KEYS);
      break;
    case 'session.updated':
      scheduleInvalidate(qc, ['overview', 'beds', 'sessions', 'patients']);
      break;
    default:
      break;
  }
}
