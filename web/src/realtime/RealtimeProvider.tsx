import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';

import type { AlertCreatedOut } from '../api/types';
import { useAuth } from '../auth/useAuth';
import { createAlertNotifier } from './alertNotifier';
import { applyMessage, invalidateAll } from './invalidation';
import { playAlertSound } from './sound';
import { RealtimeContext } from './status';
import { RealtimeClient, type WsStatus } from './wsClient';

export { RealtimeContext } from './status';

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { token, logout, reloadUser } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState<WsStatus>('connecting');
  // Một notifier cho cả vòng đời provider: khử trùng toast/âm thanh qua các lần kết nối lại.
  const [notifyAlert] = useState(() =>
    createAlertNotifier({ show: (t) => notifications.show(t), play: playAlertSound }),
  );

  useEffect(() => {
    if (!token) return;
    // alert.created có thể đến lại (gửi lại sau khi kết nối lại): mỗi cảnh báo chỉ báo một lần.
    const notified = new Set<number>();
    const client = new RealtimeClient(token, {
      onMessage: (msg) => {
        applyMessage(qc, msg);
        if (msg.type === 'alert.created') {
          const data = msg.payload as AlertCreatedOut;
          if (notified.has(data.alert.id)) return;
          notified.add(data.alert.id);
          if (notified.size > 500) notified.delete(notified.values().next().value as number);
          notifyAlert(data);
        }
      },
      onStatus: setStatus,
      onReconnected: () => invalidateAll(qc),
      onUnauthorized: logout,
      onForbidden: reloadUser,
    });
    client.start();
    return () => client.stop();
  }, [token, qc, logout, reloadUser, notifyAlert]);

  return <RealtimeContext.Provider value={status}>{children}</RealtimeContext.Provider>;
}
