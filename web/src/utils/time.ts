// Giờ hiển thị luôn theo Asia/Ho_Chi_Minh (PDF §9.3; data-model.md). API trả UTC.
export const DISPLAY_TZ = 'Asia/Ho_Chi_Minh';
const VN_OFFSET = '+07:00'; // Việt Nam không có giờ mùa hè.

function parts(iso: string | Date): Record<string, string> {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  const out: Record<string, string> = {};
  for (const p of new Intl.DateTimeFormat('en-GB', {
    timeZone: DISPLAY_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(d)) {
    out[p.type] = p.value;
  }
  return out;
}

/** HH:mm:ss */
export function formatTime(iso: string | Date): string {
  const p = parts(iso);
  return `${p.hour}:${p.minute}:${p.second}`;
}

/** HH:mm */
export function formatHm(iso: string | Date): string {
  const p = parts(iso);
  return `${p.hour}:${p.minute}`;
}

/** dd/MM/yyyy */
export function formatDate(iso: string | Date): string {
  const p = parts(iso);
  return `${p.day}/${p.month}/${p.year}`;
}

/** dd/MM/yyyy HH:mm:ss */
export function formatDateTime(iso: string | Date): string {
  return `${formatDate(iso)} ${formatTime(iso)}`;
}

/** "14:00:00" (giờ ca trực từ API) → "14:00" */
export function shortClock(t: string): string {
  return t.slice(0, 5);
}

/** Giá trị cho <input type="datetime-local"> theo giờ VN. */
export function toLocalInput(iso: string | Date): string {
  const p = parts(iso);
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

/** Giá trị <input type="datetime-local"> (hiểu là giờ VN) → ISO có múi giờ. */
export function fromLocalInput(value: string): string {
  return `${value.length === 16 ? `${value}:00` : value}${VN_OFFSET}`;
}

/** yyyy-MM-dd theo giờ VN. */
export function toDateInput(iso: string | Date): string {
  const p = parts(iso);
  return `${p.year}-${p.month}-${p.day}`;
}

/** Giờ VN dạng "HH:mm" của một thời điểm, dùng để so sánh với giờ ca trực. */
export function vnClock(d: Date): string {
  return formatHm(d);
}
