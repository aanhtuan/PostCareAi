// Hook TanStack Query. Dữ liệu server chỉ lấy qua đây; WebSocket chỉ làm mới cache.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { keepNewerStates } from '../realtime/invalidation';
import { fallbackInterval, useRealtimeStatus } from '../realtime/status';
import { api, type QueryValue } from './client';
import type {
  AlertOut,
  AlertOutcome,
  AlertStatus,
  AreaOut,
  BedOut,
  CameraDetailOut,
  CameraOut,
  CameraRoiOut,
  CameraThresholdsOut,
  DisplayMode,
  EventOut,
  HandoverOut,
  OverviewOut,
  Page,
  PatientOut,
  Priority,
  SessionOut,
  ShiftOut,
  TimelineItemOut,
} from './types';

export const qk = {
  overview: ['overview'] as const,
  events: (p: object) => ['events', p] as const,
  alerts: (p: object) => ['alerts', p] as const,
  shifts: (includeInactive: boolean) => ['shifts', { includeInactive }] as const,
  sessions: (p: object) => ['sessions', p] as const,
  timeline: (p: object) => ['timeline', p] as const,
  handover: (p: object) => ['handover', p] as const,
};

/**
 * F21 R8: Tổng quan cập nhật qua WebSocket (F18). Polling ≤5 giây (F09 R6) chỉ còn là đường dự
 * phòng khi WebSocket không mở *(giả định F21)*; kết nối lại thì refetch (`invalidateAll`).
 */
export const OVERVIEW_POLL_MS = 5000;

export function useOverview() {
  const ws = useRealtimeStatus();
  const qc = useQueryClient();
  return useQuery({
    queryKey: qk.overview,
    queryFn: async () =>
      keepNewerStates(
        await api<OverviewOut>('/overview'),
        qc.getQueryData<OverviewOut>(qk.overview),
      ),
    refetchInterval: fallbackInterval(ws, OVERVIEW_POLL_MS),
  });
}

export type EventFilter = { bed_id?: number; limit?: number; priority?: Priority[] };

export function useEvents(filter: EventFilter) {
  return useQuery({
    queryKey: qk.events(filter),
    queryFn: () => api<Page<EventOut>>('/events', { query: filter as Record<string, QueryValue> }),
  });
}

export type AlertFilter = {
  status?: AlertStatus[];
  bed_id?: number;
  priority?: Priority[];
  from?: string;
  to?: string;
  limit?: number;
};

export function useAlerts(filter: AlertFilter) {
  return useQuery({
    queryKey: qk.alerts(filter),
    queryFn: () => api<Page<AlertOut>>('/alerts', { query: filter as Record<string, QueryValue> }),
  });
}

// Danh mục (F03): API phân trang; màn hình cần toàn bộ nên lấy tối đa 200 (api-conventions.md).
const CATALOG_LIMIT = 200;

function catalogQuery<T>(resource: CatalogResource, includeInactive: boolean) {
  return {
    queryKey: [resource, { includeInactive }] as const,
    queryFn: () =>
      api<Page<T>>(`/${resource}`, {
        query: { limit: CATALOG_LIMIT, include_inactive: includeInactive || undefined },
      }),
    select: (page: Page<T>) => page.items,
  };
}

export function useBeds(includeInactive = false) {
  return useQuery(catalogQuery<BedOut>('beds', includeInactive));
}

export function usePatients(includeInactive = false) {
  return useQuery(catalogQuery<PatientOut>('patients', includeInactive));
}

export function useCameras(includeInactive = false) {
  return useQuery(catalogQuery<CameraOut>('cameras', includeInactive));
}

export function useAreas(includeInactive = false) {
  return useQuery(catalogQuery<AreaOut>('areas', includeInactive));
}

/** Ca trực (F24; F37 thêm `include_inactive`). Không phân trang. */
export function useShifts(includeInactive = false) {
  return useQuery({
    queryKey: qk.shifts(includeInactive),
    queryFn: () =>
      api<ShiftOut[]>('/shifts', { query: { include_inactive: includeInactive || undefined } }),
    staleTime: Infinity,
  });
}

export function useSessions(filter: { bed_id?: number; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: qk.sessions(filter),
    queryFn: () => api<Page<SessionOut>>('/sessions', { query: filter }),
    enabled,
  });
}

export type TimelineFilter =
  | { mode: 'session'; session_id: number; priority?: Priority[] }
  | { mode: 'range'; bed_id: number; from?: string; to?: string; priority?: Priority[] };

export function useTimeline(filter: TimelineFilter | null) {
  return useQuery({
    queryKey: qk.timeline(filter ?? {}),
    enabled: filter !== null,
    queryFn: () => {
      if (!filter) throw new Error('no filter');
      if (filter.mode === 'session') {
        return api<Page<TimelineItemOut>>(`/sessions/${filter.session_id}/timeline`, {
          query: { priority: filter.priority },
        });
      }
      const { mode: _mode, ...query } = filter;
      void _mode;
      return api<Page<TimelineItemOut>>('/timeline', { query });
    },
  });
}

export type HandoverFilter = { shift_id: number; date: string } | { from: string; to: string };

export function useHandover(filter: HandoverFilter | null) {
  return useQuery({
    queryKey: qk.handover(filter ?? {}),
    enabled: filter !== null,
    queryFn: () => api<HandoverOut>('/handover', { query: filter as Record<string, QueryValue> }),
  });
}

/** Sau mỗi thao tác ghi: làm mới mọi màn hình liên quan. */
function useInvalidateMonitoring() {
  const qc = useQueryClient();
  return () => {
    for (const key of [
      'overview',
      'alerts',
      'events',
      'timeline',
      'handover',
      'beds',
      'sessions',
      'patients',
      'cameras',
      'areas',
      'shifts',
    ]) {
      void qc.invalidateQueries({ queryKey: [key] });
    }
  };
}

export type AlertAction =
  | { kind: 'acknowledge' }
  | { kind: 'outcome'; outcome: AlertOutcome; note?: string }
  | { kind: 'resolve'; note?: string };

export function useAlertAction(alertId: number) {
  const invalidate = useInvalidateMonitoring();
  return useMutation({
    mutationFn: (action: AlertAction) => {
      const path = `/alerts/${alertId}/${action.kind}`;
      if (action.kind === 'acknowledge') return api<AlertOut>(path, { method: 'POST' });
      if (action.kind === 'outcome') {
        return api<AlertOut>(path, {
          method: 'POST',
          body: { outcome: action.outcome, note: action.note || null },
        });
      }
      return api<AlertOut>(path, { method: 'POST', body: { note: action.note || null } });
    },
    onSettled: invalidate,
  });
}

export function useStartSession() {
  const invalidate = useInvalidateMonitoring();
  return useMutation({
    mutationFn: (body: { bed_id: number; patient_id: number }) =>
      api<SessionOut>('/sessions', { method: 'POST', body }),
    onSettled: invalidate,
  });
}

export function useEndSession() {
  const invalidate = useInvalidateMonitoring();
  return useMutation({
    mutationFn: (sessionId: number) =>
      api<SessionOut>(`/sessions/${sessionId}/end`, { method: 'POST' }),
    onSettled: invalidate,
  });
}

/** Chuyển giường (F04 R12): trả phiên mới ở giường đích. */
export function useTransferSession() {
  const invalidate = useInvalidateMonitoring();
  return useMutation({
    mutationFn: (v: { sessionId: number; target_bed_id: number; reason: string }) =>
      api<SessionOut>(`/sessions/${v.sessionId}/transfer`, {
        method: 'POST',
        body: { target_bed_id: v.target_bed_id, reason: v.reason },
      }),
    onSettled: invalidate,
  });
}

/** Tạm dừng / tiếp tục thu hình của phiên (F04 R19). */
export function useCaptureToggle() {
  const invalidate = useInvalidateMonitoring();
  return useMutation({
    mutationFn: (v: { sessionId: number; pause: boolean; reason?: string }) =>
      v.pause
        ? api<SessionOut>(`/sessions/${v.sessionId}/pause`, {
            method: 'POST',
            body: { reason: v.reason?.trim() || null },
          })
        : api<SessionOut>(`/sessions/${v.sessionId}/resume`, { method: 'POST' }),
    onSettled: invalidate,
  });
}

export type CatalogResource = 'beds' | 'patients' | 'cameras' | 'areas' | 'shifts';

/** Thêm (`id` rỗng) hoặc sửa (`PATCH`) một mục danh mục. Chỉ ADMIN (F03 R2). */
export function useSaveCatalogItem<TBody>(resource: CatalogResource) {
  const invalidate = useInvalidateMonitoring();
  return useMutation({
    mutationFn: ({ id, body }: { id?: number; body: TBody }) =>
      id === undefined
        ? api<unknown>(`/${resource}`, { method: 'POST', body })
        : api<unknown>(`/${resource}/${id}`, { method: 'PATCH', body }),
    onSettled: invalidate,
  });
}

/** Xóa mềm (`DELETE`) hoặc khôi phục (`POST .../restore`) (QA#36). */
export function useCatalogLifecycle() {
  const invalidate = useInvalidateMonitoring();
  return useMutation({
    mutationFn: ({
      resource,
      id,
      action,
    }: {
      resource: CatalogResource;
      id: number;
      action: 'delete' | 'restore';
    }) =>
      action === 'delete'
        ? api<unknown>(`/${resource}/${id}`, { method: 'DELETE' })
        : api<unknown>(`/${resource}/${id}/restore`, { method: 'POST' }),
    onSettled: invalidate,
  });
}

/**
 * Chi tiết camera (trạng thái, Bed ROI) cho "Theo dõi trực tiếp". `camera.status` qua WebSocket
 * làm mới query này (F21); `pollMs` chỉ áp dụng khi WebSocket không mở.
 */
export function useCameraDetail(cameraId: number | undefined, pollMs?: number) {
  const ws = useRealtimeStatus();
  return useQuery({
    queryKey: ['cameras', 'detail', cameraId] as const,
    queryFn: () => api<CameraDetailOut>(`/cameras/${cameraId}`),
    enabled: cameraId !== undefined,
    refetchInterval: pollMs === undefined ? false : fallbackInterval(ws, pollMs),
  });
}

// ---------- Cấu hình camera (F08): chỉ ADMIN ----------

const thresholdsKey = (cameraId: number) => ['cameras', 'thresholds', cameraId] as const;

/** Ngưỡng mặc định, override và giá trị đang áp dụng của camera. */
export function useCameraThresholds(cameraId: number) {
  return useQuery({
    queryKey: thresholdsKey(cameraId),
    queryFn: () => api<CameraThresholdsOut>(`/cameras/${cameraId}/thresholds`),
  });
}

/** Lưu Bed ROI; xong thì làm mới chi tiết camera (ROI, config_version) và danh sách camera. */
export function useSaveRoi(cameraId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (roi: number[][]) =>
      api<CameraRoiOut>(`/cameras/${cameraId}/roi`, {
        method: 'PUT',
        body: { roi_polygon: roi },
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  });
}

/** Thay toàn bộ override ngưỡng; `{}` = khôi phục mặc định. */
export function useSaveThresholds(cameraId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (thresholds: Record<string, unknown>) =>
      api<CameraThresholdsOut>(`/cameras/${cameraId}/thresholds`, {
        method: 'PUT',
        body: { thresholds },
      }),
    onSuccess: (data) => qc.setQueryData(thresholdsKey(cameraId), data),
    onSettled: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  });
}

// ---------- Chế độ hiển thị (F28): ADMIN và CHARGE_NURSE ----------

/** Đổi chế độ hiển thị của camera; xong thì làm mới chi tiết camera (worker áp dụng ≤ 5 s). */
export function useSaveDisplayMode(cameraId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (displayMode: DisplayMode) =>
      api<CameraOut>(`/cameras/${cameraId}/display-mode`, {
        method: 'PUT',
        body: { display_mode: displayMode },
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  });
}
