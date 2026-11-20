// Thông báo cảnh báo mới từ WebSocket: toast đúng một lần cho mỗi cảnh báo, âm thanh chỉ cho
// mức Ưu tiên cao (QA#17; F20 R6). Message `alert.created` có thể tới lại (kết nối lại…),
// nên khử trùng theo `alert.id`.
import type { AlertCreatedOut, AlertOut } from '../api/types';
import { fmt, vi } from '../i18n/vi';
import { formatTime } from '../utils/time';

export type AlertToast = {
  id: string;
  alertId: number;
  title: string;
  message: string;
  color: string;
  autoClose: number;
};

const SEEN_LIMIT = 500; // giới hạn bộ nhớ của tập id đã thông báo (hằng số UI)

export function createAlertNotifier(deps: {
  show: (toast: AlertToast) => void;
  play: () => void;
}): (data: AlertCreatedOut | { alert: AlertOut }) => void {
  const seen = new Set<number>();
  return ({ alert }) => {
    if (seen.has(alert.id)) return;
    seen.add(alert.id);
    if (seen.size > SEEN_LIMIT) {
      const oldest = seen.values().next().value;
      if (oldest !== undefined) seen.delete(oldest);
    }
    const high = alert.event.priority === 'HIGH';
    deps.show({
      id: `alert-${alert.id}`,
      alertId: alert.id,
      title: fmt(vi.alerts.newNotification, {
        bed: alert.bed?.code ?? '—',
        title: vi.alertTitle[alert.event.priority],
      }),
      message: fmt(vi.alerts.sentence, {
        event: vi.event[alert.event.code],
        time: formatTime(alert.event.occurred_at),
      }),
      color: high ? 'red' : 'orange',
      autoClose: high ? 15000 : 8000,
    });
    if (high) deps.play();
  };
}
