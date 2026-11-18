import { QueryClient } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';

import type { OverviewOut } from '../api/types';
import { applyMessage, invalidateAll } from './invalidation';

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
  const keys = () => spy.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
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

describe('invalidateAll', () => {
  it('invalidates overview, alerts, events and timeline after reconnect', () => {
    const { qc, keys } = setup();
    invalidateAll(qc);
    expect(keys()).toEqual(
      expect.arrayContaining(['overview', 'alerts', 'events', 'timeline', 'handover', 'beds']),
    );
  });
});
