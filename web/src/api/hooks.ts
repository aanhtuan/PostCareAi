// Hook TanStack Query. Dữ liệu server chỉ lấy qua đây; WebSocket chỉ làm mới cache.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, type QueryValue } from './client';
import type {
  AlertOut,
  AlertOutcome,
  AlertStatus,
  BedOut,
  CameraOut,
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
  shifts: ['shifts'] as const,
  sessions: (p: object) => ['sessions', p] as const,
  timeline: (p: object) => ['timeline', p] as const,
  handover: (p: object) => ['handover', p] as const,
};

export function useOverview() {
  return useQuery({ queryKey: qk.overview, queryFn: () => api<OverviewOut>('/overview') });
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

export function useShifts() {
  return useQuery({
    queryKey: qk.shifts,
    queryFn: () => api<ShiftOut[]>('/shifts'),
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

export type CatalogResource = 'beds' | 'patients' | 'cameras';

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
