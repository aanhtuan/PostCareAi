// Ánh xạ message WebSocket → cập nhật cache TanStack Query (không giữ state song song).
import type { QueryClient } from '@tanstack/react-query';

import type { BedStateOut, CameraStatusOut, OverviewOut } from '../api/types';
import type { WsMessage } from './wsClient';

const MONITORING_KEYS = ['overview', 'alerts', 'events', 'timeline', 'handover'];

export function invalidateAll(qc: QueryClient): void {
  for (const key of [...MONITORING_KEYS, 'beds', 'sessions', 'patients', 'cameras']) {
    void qc.invalidateQueries({ queryKey: [key] });
  }
}

export function applyMessage(qc: QueryClient, msg: WsMessage): void {
  switch (msg.type) {
    case 'bed.state': {
      const state = msg.payload as BedStateOut;
      qc.setQueryData<OverviewOut>(['overview'], (old) =>
        old
          ? {
              ...old,
              beds: old.beds.map((b) => (b.bed_id === state.bed_id ? { ...b, state } : b)),
            }
          : old,
      );
      break;
    }
    case 'camera.status': {
      const cam = msg.payload as CameraStatusOut;
      qc.setQueryData<OverviewOut>(['overview'], (old) =>
        old
          ? {
              ...old,
              beds: old.beds.map((b) =>
                b.camera && b.camera.id === cam.camera_id
                  ? { ...b, camera: { ...b.camera, status: cam.status } }
                  : b,
              ),
            }
          : old,
      );
      void qc.invalidateQueries({ queryKey: ['beds'] });
      void qc.invalidateQueries({ queryKey: ['cameras'] });
      break;
    }
    case 'event.created':
      for (const key of ['events', 'timeline', 'handover']) {
        void qc.invalidateQueries({ queryKey: [key] });
      }
      break;
    case 'alert.created':
    case 'alert.updated':
      for (const key of MONITORING_KEYS) void qc.invalidateQueries({ queryKey: [key] });
      break;
    case 'session.updated':
      for (const key of ['overview', 'beds', 'sessions', 'patients']) {
        void qc.invalidateQueries({ queryKey: [key] });
      }
      break;
    default:
      break;
  }
}
