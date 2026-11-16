import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { createContext, useEffect, useState, type ReactNode } from 'react';

import type { AlertCreatedOut } from '../api/types';
import { useAuth } from '../auth/useAuth';
import { fmt, vi } from '../i18n/vi';
import { formatTime } from '../utils/time';
import { applyMessage, invalidateAll } from './invalidation';
import { playAlertSound } from './sound';
import { RealtimeClient, type WsStatus } from './wsClient';

// eslint-disable-next-line react-refresh/only-export-components
export const RealtimeContext = createContext<WsStatus>('connecting');

function notifyAlert(data: AlertCreatedOut): void {
  const { alert } = data;
  const high = alert.event.priority === 'HIGH';
  notifications.show({
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
  if (high) playAlertSound();
}

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { token, logout } = useAuth();
  const qc = useQueryClient();
  const [status, setStatus] = useState<WsStatus>('connecting');

  useEffect(() => {
    if (!token) return;
    const client = new RealtimeClient(token, {
      onMessage: (msg) => {
        applyMessage(qc, msg);
        if (msg.type === 'alert.created') notifyAlert(msg.payload as AlertCreatedOut);
      },
      onStatus: setStatus,
      onReconnected: () => invalidateAll(qc),
      onUnauthorized: logout,
    });
    client.start();
    return () => client.stop();
  }, [token, qc, logout]);

  return <RealtimeContext.Provider value={status}>{children}</RealtimeContext.Provider>;
}
