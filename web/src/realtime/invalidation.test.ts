import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import type { OverviewOut } from '../api/types';
import {
  INVALIDATE_COALESCE_MS,
  applyMessage,
  flushInvalidations,
  invalidateAll,
} from './invalidation';

function setup() {
  const qc = new QueryClient();
  const spy = vi.spyOn(qc, 'invalidateQueries');
  const overview = {
    beds: [
      { bed_id: 1, state: null, camera: { id: 10, status: 'ONLINE' } },
      { bed_id: 2, state: null, camera: { id: 20, status: 'ONLINE' } },
    ],
  } as unknown as OverviewOut;
  qc.setQueryData(['overview'], overview);
  // Invalidate từ WebSocket được gộp (F21): `keys()` xả hàng chờ trước khi đọc.
  const keys = () => {
    flushInvalidations(qc);
    return spy.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
  };
  return { qc, keys };
}

const msg = (type: string, payload: unknown) => ({ type, payload, sent_at: '' });

describe('applyMessage', () => {
  it('bed.state updates only that bed in the overview cache', () => {
    const { qc, keys } = setup();
    applyMessage(qc, msg('bed.state', { bed_id: 2, body_state: 'SITTING' }));
    const beds = qc.getQueryData<OverviewOut>(['overview'])!.beds;
    expect(beds[0].state).toBeNull();
    expect(beds[1].state).toMatchObject({ body_state: 'SITTING' });
    expect(keys()).toEqual([]); // setQueryData, không refetch
  });

  it('camera.status updates the camera status and refreshes camera lists', () => {
    const { qc, keys } = setup();
    applyMessage(qc, msg('camera.status', { camera_id: 20, bed_id: 2, status: 'OFFLINE' }));
    const beds = qc.getQueryData<OverviewOut>(['overview'])!.beds;
    expect(beds[1].camera?.status).toBe('OFFLINE');
    expect(beds[0].camera?.status).toBe('ONLINE');
    expect(keys()).toEqual(expect.arrayContaining(['beds', 'cameras']));
  });

  it.each(['alert.created', 'alert.updated'])('%s invalidates monitoring queries', (type) => {
    const { qc, keys } = setup();
    applyMessage(qc, msg(type, {}));
    expect(keys()).toEqual(
      expect.arrayContaining(['overview', 'alerts', 'events', 'timeline', 'handover']),
    );
  });

  it('event.created invalidates events and timeline', () => {
    const { qc, keys } = setup();
    applyMessage(qc, msg('event.created', {}));
    expect(keys()).toEqual(expect.arrayContaining(['events', 'timeline']));
  });

  it('session.updated invalidates overview and sessions', () => {
    const { qc, keys } = setup();
    applyMessage(qc, msg('session.updated', {}));
    expect(keys()).toEqual(expect.arrayContaining(['overview', 'sessions', 'beds']));
  });

  it('ignores unknown types', () => {
    const { qc, keys } = setup();
    applyMessage(qc, msg('family.state', {}));
    expect(keys()).toEqual([]);
  });
});

describe('F21 realtime cache updates', () => {
  const alertCreated = (bedId: number, priority: string, id = 1) =>
    msg('alert.created', {
      alert: { id, status: 'PENDING', bed: { id: bedId, code: 'A0' }, event: { priority } },
      event: { id, bed_id: bedId, priority },
    });

  it('alert.created bumps the bed card immediately', () => {
    const { qc } = setup();
    applyMessage(qc, alertCreated(1, 'MEDIUM'));
    const beds = qc.getQueryData<OverviewOut>(['overview'])!.beds;
    expect(beds[0].pending_alert_count).toBe(1);
    expect(beds[0].max_open_priority).toBe('MEDIUM');
    // Ca âm: giường khác giữ nguyên; mức thấp hơn không hạ mức ưu tiên cao nhất.
    expect(beds[1].pending_alert_count).toBe(1);
    applyMessage(qc, alertCreated(2, 'INFO', 2));
    const after = qc.getQueryData<OverviewOut>(['overview'])!.beds;
    expect(after[1].pending_alert_count).toBe(2);
    expect(after[1].max_open_priority).toBe('HIGH');
  });

  it('bursts of messages coalesce into one invalidation per key', () => {
    vi.useFakeTimers();
    try {
      const qc = new QueryClient();
      const spy = vi.spyOn(qc, 'invalidateQueries');
      for (let i = 0; i < 20; i++) {
        applyMessage(qc, msg('event.created', { id: i }));
        applyMessage(qc, msg('alert.updated', { id: i }));
      }
      expect(spy).not.toHaveBeenCalled(); // chưa refetch ngay từng message
      vi.advanceTimersByTime(INVALIDATE_COALESCE_MS);
      const called = spy.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
      expect(called.filter((k) => k === 'events')).toHaveLength(1);
      expect(called.filter((k) => k === 'overview')).toHaveLength(1);
      expect(new Set(called).size).toBe(called.length);
      // Vẫn trong mục tiêu cập nhật ≤ 1 s.
      expect(INVALIDATE_COALESCE_MS).toBeLessThanOrEqual(500);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('invalidateAll', () => {
  it('invalidates overview, alerts, events and timeline after reconnect', () => {
    const { qc, keys } = setup();
    invalidateAll(qc);
    expect(keys()).toEqual(
      expect.arrayContaining(['overview', 'alerts', 'events', 'timeline', 'handover', 'beds']),
    );
  });
});
