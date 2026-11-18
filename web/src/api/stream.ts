// URL MJPEG xem trực tiếp (F07; api-conventions.md). `<img>` không gửi được header nên token đi qua
// query; `attempt` đổi để trình duyệt mở kết nối mới. Dùng chung cho CameraStream và RoiEditor (F08).
export function streamUrl(
  cameraId: number,
  token: string | null,
  attempt: number,
  view: 'display' | 'skeleton' = 'display',
): string {
  const query = new URLSearchParams({ token: token ?? '', n: String(attempt) });
  if (view === 'skeleton') query.set('view', view);
  return `/api/v1/cameras/${cameraId}/stream.mjpeg?${query.toString()}`;
}
