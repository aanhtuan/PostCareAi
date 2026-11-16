import { describe, expect, it } from 'vitest';

import { fmt, vi } from './vi';

// Danh sách từ cấm trên UI: docs/01-product/glossary.md#từ-cấm-trên-ui
const FORBIDDEN = [
  'chẩn đoán',
  'đau',
  'bất tỉnh',
  'mất ý thức',
  'té ngã',
  'ngã',
  'ngủ',
  'tỉnh',
  'fall detected',
  'pain detected',
];

function collectStrings(value: unknown, out: string[] = []): string[] {
  if (typeof value === 'string') out.push(value);
  else if (value && typeof value === 'object') {
    for (const v of Object.values(value)) collectStrings(v, out);
  }
  return out;
}

/** Khớp theo từ nguyên vẹn, không phân biệt hoa thường, sau khi chuẩn hóa NFC. */
function containsWord(text: string, word: string): boolean {
  const norm = (s: string) => s.normalize('NFC').toLocaleLowerCase('vi');
  const escaped = norm(word).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`(?<![\\p{L}\\p{N}])${escaped}(?![\\p{L}\\p{N}])`, 'u');
  return re.test(norm(text));
}

const ALL = collectStrings(vi);

describe('vi.ts', () => {
  it('has strings', () => {
    expect(ALL.length).toBeGreaterThan(100);
  });

  it.each(FORBIDDEN)('does not contain forbidden word "%s"', (word) => {
    const hits = ALL.filter((s) => containsWord(s, word));
    expect(hits).toEqual([]);
  });

  it('does not contain internal codes such as BED_EXIT', () => {
    const hits = ALL.filter((s) => /\b[A-Z]{2,}(?:_[A-Z]+)+\b/.test(s));
    expect(hits).toEqual([]);
  });

  it('word matching is NFC-aware and whole-word only', () => {
    // "đau" dựng bằng ký tự tổ hợp (NFD) vẫn phải bị bắt.
    expect(containsWord('Bệnh nhân đau'.normalize('NFD'), 'đau')).toBe(true);
    expect(containsWord('Vùng đầu', 'đau')).toBe(false);
    expect(containsWord('Đang nghỉ', 'ngủ')).toBe(false);
    expect(containsWord('Phát hiện TÉ NGÃ', 'té ngã')).toBe(true);
  });

  it('fmt replaces placeholders', () => {
    expect(fmt(vi.shift.label, { start: '14:00', end: '22:00' })).toBe('Ca trực: 14:00–22:00');
  });
});
