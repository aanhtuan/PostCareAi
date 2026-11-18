import { describe, expect, it, vi } from 'vitest';

import type { AlertCreatedOut, Priority } from '../api/types';
import { createAlertNotifier } from './alertNotifier';

const T = '2026-10-12T07:38:34Z';

function created(id: number, priority: Priority): AlertCreatedOut {
  return {
    alert: {
      id,
      status: 'PENDING',
      bed: { id: 1, code: 'A01' },
      event: { id, code: 'BED_EXIT', priority, occurred_at: T, observation_quality: 'GOOD' },
    },
    event: { id },
  } as unknown as AlertCreatedOut;
}

function setup() {
  const show = vi.fn();
  const play = vi.fn();
  return { show, play, notify: createAlertNotifier({ show, play }) };
}

describe('createAlertNotifier', () => {
  it('HIGH alert shows toast and sound once', () => {
    const { show, play, notify } = setup();
    notify(created(7, 'HIGH'));
    expect(show).toHaveBeenCalledTimes(1);
    expect(play).toHaveBeenCalledTimes(1);
    const toast = show.mock.calls[0][0] as { title: string; message: string; color: string };
    expect(toast.title).toContain('A01');
    expect(toast.message).toContain('Bệnh nhân rời khỏi vùng giường');
    expect(`${toast.title} ${toast.message}`).not.toMatch(/BED_EXIT|HIGH|PENDING/);
  });

  it('MEDIUM alert toast without sound', () => {
    const { show, play, notify } = setup();
    notify(created(8, 'MEDIUM'));
    expect(show).toHaveBeenCalledTimes(1);
    expect(play).not.toHaveBeenCalled();
  });

  it('duplicate alert.created is ignored', () => {
    const { show, play, notify } = setup();
    notify(created(7, 'HIGH'));
    notify(created(7, 'HIGH')); // gửi lại (kết nối lại, nhiều tab của server…)
    expect(show).toHaveBeenCalledTimes(1);
    expect(play).toHaveBeenCalledTimes(1);
    notify(created(9, 'HIGH'));
    expect(show).toHaveBeenCalledTimes(2);
    expect(play).toHaveBeenCalledTimes(2);
  });
});
