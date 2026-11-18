import { describe, expect, it } from 'vitest';

import openapi from '../api/openapi.json';
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

  // Test của test: bộ quét phải bắt chuỗi chứa từ cấm (F20 AC4, testing.md mục 4).
  it.each([
    ['Phát hiện bệnh nhân đau', true],
    ['Bệnh nhân BẤT TỈNH', true],
    ['Có dấu hiệu ngã khỏi giường', true],
    ['Đã chẩn đoán', true],
    ['Phát hiện bệnh nhân rời khỏi vùng giường', false],
    ['Vùng đầu giường', false],
  ])('forbidden-word scanner on "%s" → %s', (text, expected) => {
    expect(FORBIDDEN.some((w) => containsWord(text, w))).toBe(expected);
  });

  // Mỗi giá trị enum trong OpenAPI (sinh từ server/src/postcare/schemas) phải có text tiếng Việt.
  it.each([
    ['EventCode', vi.event],
    ['Priority', vi.priority],
    ['AlertStatus', vi.alertStatus],
    ['AlertOutcome', vi.outcome],
  ] as const)('has text for every enum value: %s', (name, texts) => {
    const schemas = openapi.components.schemas as Record<string, { enum?: string[] }>;
    const values = schemas[name].enum ?? [];
    expect(values.length).toBeGreaterThan(0);
    const map = texts as Record<string, string>;
    expect(values.filter((v) => !map[v]?.trim())).toEqual([]);
    expect(Object.keys(map).sort()).toEqual([...values].sort());
  });

  it('fmt replaces placeholders', () => {
    expect(fmt(vi.shift.label, { start: '14:00', end: '22:00' })).toBe('Ca trực: 14:00–22:00');
  });
});
