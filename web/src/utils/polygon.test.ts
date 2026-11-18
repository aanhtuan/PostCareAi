// Cùng bộ ca với server/tests/schemas/test_roi.py (F08 AC2): web báo lỗi ngay khi vẽ.
import { describe, expect, it } from 'vitest';

import { MAX_ROI_POINTS, validatePolygon } from './polygon';

const SQUARE = [
  [0.2, 0.2],
  [0.8, 0.2],
  [0.8, 0.8],
  [0.2, 0.8],
];

describe('validatePolygon', () => {
  it('accepts convex and concave polygons', () => {
    expect(validatePolygon(SQUARE)).toBeNull();
    expect(
      validatePolygon([
        [0.1, 0.1],
        [0.9, 0.1],
        [0.5, 0.9],
      ]),
    ).toBeNull();
    // Lõm: không được từ chối.
    expect(
      validatePolygon([
        [0.1, 0.1],
        [0.9, 0.1],
        [0.9, 0.9],
        [0.5, 0.4],
        [0.1, 0.9],
      ]),
    ).toBeNull();
  });

  it('rejects a bow-tie (self intersection)', () => {
    expect(
      validatePolygon([
        [0.1, 0.1],
        [0.9, 0.9],
        [0.9, 0.1],
        [0.1, 0.9],
      ]),
    ).toBe('SELF_INTERSECTION');
  });

  it('rejects overlapping edges', () => {
    expect(
      validatePolygon([
        [0.1, 0.5],
        [0.9, 0.5],
        [0.9, 0.9],
        [0.5, 0.5],
      ]),
    ).toBe('SELF_INTERSECTION');
  });

  it('rejects fewer than 3 points', () => {
    expect(validatePolygon([])).toBe('TOO_FEW_POINTS');
    expect(validatePolygon(SQUARE.slice(0, 2))).toBe('TOO_FEW_POINTS');
  });

  it('rejects more than 20 points', () => {
    const circle = (n: number) =>
      Array.from({ length: n }, (_, i) => [
        0.5 + 0.4 * Math.cos((2 * Math.PI * i) / n),
        0.5 + 0.4 * Math.sin((2 * Math.PI * i) / n),
      ]);
    expect(validatePolygon(circle(MAX_ROI_POINTS + 1))).toBe('TOO_MANY_POINTS');
    expect(validatePolygon(circle(MAX_ROI_POINTS))).toBeNull();
  });

  it('rejects coordinates outside [0, 1] and non numbers', () => {
    expect(
      validatePolygon([
        [0.1, 0.1],
        [1.5, 0.1],
        [0.5, 0.9],
      ]),
    ).toBe('OUT_OF_RANGE');
    expect(
      validatePolygon([
        [0.1, 0.1],
        [Number.NaN, 0.1],
        [0.5, 0.9],
      ]),
    ).toBe('INVALID_POINT');
    expect(validatePolygon([[0.1, 0.1], [0.9], [0.5, 0.9]])).toBe('INVALID_POINT');
  });

  it('rejects collinear and duplicate points', () => {
    expect(
      validatePolygon([
        [0.1, 0.1],
        [0.5, 0.5],
        [0.9, 0.9],
      ]),
    ).toBe('ZERO_AREA');
    expect(
      validatePolygon([
        [0.1, 0.1],
        [0.1, 0.1],
        [0.9, 0.1],
        [0.5, 0.9],
      ]),
    ).toBe('DUPLICATE_POINT');
  });
});
