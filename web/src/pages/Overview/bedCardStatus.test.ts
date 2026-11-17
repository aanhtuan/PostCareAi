import { describe, expect, it } from 'vitest';

import { bedCardStatus, type BedCardInput } from './bedCardStatus';

const base: BedCardInput = {
  hasSession: true,
  paused: false,
  pendingCount: 0,
  acknowledgedCount: 0,
  bodyState: 'LYING',
};

describe('bedCardStatus (A12)', () => {
  it('pending alert gives Cảnh báo mới', () => {
    expect(bedCardStatus({ ...base, pendingCount: 1 })).toBe('NEW_ALERT');
  });

  it('pending wins over acknowledged and no observation', () => {
    expect(
      bedCardStatus({
        ...base,
        pendingCount: 2,
        acknowledgedCount: 1,
        bodyState: 'NO_OBSERVATION',
      }),
    ).toBe('NEW_ALERT');
  });

  it('acknowledged open alert gives Cần kiểm tra', () => {
    expect(bedCardStatus({ ...base, acknowledgedCount: 1 })).toBe('NEEDS_CHECK');
  });

  it('no observation gives Cần kiểm tra', () => {
    expect(bedCardStatus({ ...base, bodyState: 'NO_OBSERVATION' })).toBe('NEEDS_CHECK');
  });

  it('missing state is treated as no observation', () => {
    expect(bedCardStatus({ ...base, bodyState: null })).toBe('NEEDS_CHECK');
  });

  it('otherwise Đang theo dõi (resolved alerts are not counted)', () => {
    for (const s of ['LYING', 'SITTING', 'OUT_OF_BED'] as const) {
      expect(bedCardStatus({ ...base, bodyState: s })).toBe('MONITORING');
    }
  });

  it('bed without session is Không theo dõi, not Đang theo dõi', () => {
    expect(bedCardStatus({ ...base, hasSession: false, pendingCount: 3 })).toBe('NOT_MONITORED');
  });

  it('paused session gives Đang tạm dừng thu hình, not Đang theo dõi', () => {
    expect(bedCardStatus({ ...base, paused: true })).toBe('PAUSED');
    expect(bedCardStatus({ ...base, paused: true, bodyState: null })).toBe('PAUSED');
    expect(bedCardStatus({ ...base, paused: true, acknowledgedCount: 1 })).toBe('PAUSED');
  });

  it('pending alert still wins over paused', () => {
    expect(bedCardStatus({ ...base, paused: true, pendingCount: 1 })).toBe('NEW_ALERT');
  });
});
