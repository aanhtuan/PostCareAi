// Ánh xạ trạng thái thẻ giường theo A12 (qa-decisions.md), hàm thuần để test riêng (F21 R2).
import type { BodyState } from '../../api/types';

export type BedCardStatus = 'NOT_MONITORED' | 'NEW_ALERT' | 'NEEDS_CHECK' | 'MONITORING';

export type BedCardInput = {
  hasSession: boolean;
  pendingCount: number;
  acknowledgedCount: number;
  /** null = chưa nhận trạng thái nào từ worker. */
  bodyState: BodyState | null;
};

export function bedCardStatus(input: BedCardInput): BedCardStatus {
  // Giường không có phiên mở: không áp dụng A12 (giả định F21).
  if (!input.hasSession) return 'NOT_MONITORED';
  if (input.pendingCount > 0) return 'NEW_ALERT';
  // Chưa nhận trạng thái được coi như không đủ dữ liệu quan sát (giả định, PRD US07):
  // không có dữ liệu không có nghĩa là an toàn.
  if (
    input.acknowledgedCount > 0 ||
    input.bodyState === 'NO_OBSERVATION' ||
    input.bodyState === null
  ) {
    return 'NEEDS_CHECK';
  }
  return 'MONITORING';
}

export const CARD_COLOR: Record<BedCardStatus, string> = {
  NOT_MONITORED: 'gray',
  NEW_ALERT: 'red',
  NEEDS_CHECK: 'yellow',
  MONITORING: 'teal',
};
