import type { ShiftOut } from '../api/types';
import { shortClock, toDateInput, vnClock } from './time';

/** Ca hiện tại theo giờ VN và ngày bắt đầu ca (ca đêm sau 00:00 thuộc ngày hôm trước). */
export function currentShiftAndDate(
  shifts: ShiftOut[],
  now: Date,
): { shift: ShiftOut; date: string } | null {
  const t = vnClock(now);
  for (const s of shifts) {
    const start = shortClock(s.start_time);
    const end = shortClock(s.end_time);
    const inShift = start < end ? t >= start && t < end : t >= start || t < end;
    if (!inShift) continue;
    const overnightMorning = start > end && t < end;
    const day = overnightMorning ? new Date(now.getTime() - 24 * 3600 * 1000) : now;
    return { shift: s, date: toDateInput(day) };
  }
  return null;
}

/** Giờ kết thúc nhỏ hơn giờ bắt đầu: ca vắt qua nửa đêm (data-model.md; F37). */
export function isOvernight(s: Pick<ShiftOut, 'start_time' | 'end_time'>): boolean {
  return shortClock(s.end_time) < shortClock(s.start_time);
}
