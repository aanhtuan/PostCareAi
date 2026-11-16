// Âm thanh ngắn cho cảnh báo Ưu tiên cao, tạo bằng Web Audio (không cần file media; F20 R6).
let ctx: AudioContext | null = null;

export function playAlertSound(): void {
  try {
    const Ctor =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return;
    ctx = ctx ?? new Ctor();
    const now = ctx.currentTime;
    for (const [i, freq] of [880, 660, 880].entries()) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      const t = now + i * 0.22;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.3, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.2);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t);
      osc.stop(t + 0.21);
    }
  } catch {
    // Trình duyệt chặn tự phát âm thanh trước khi người dùng thao tác: chấp nhận được.
  }
}
