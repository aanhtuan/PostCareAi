// Trạng thái kết nối WebSocket cho các hook dữ liệu (F21: polling chỉ là đường dự phòng).
import { createContext, useContext } from 'react';

import type { WsStatus } from './wsClient';

export const RealtimeContext = createContext<WsStatus>('connecting');

export function useRealtimeStatus(): WsStatus {
  return useContext(RealtimeContext);
}

/** Khi WebSocket mở thì không polling; khi mất kết nối thì polling với chu kỳ `ms`. */
export function fallbackInterval(status: WsStatus, ms: number): number | false {
  return status === 'open' ? false : ms;
}
