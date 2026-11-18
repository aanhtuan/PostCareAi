import { MantineProvider } from '@mantine/core';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { RestStatus } from '../api/types';
import { RestStatusBadge } from './RestStatusBadge';

function show(status: RestStatus) {
  return render(
    <MantineProvider>
      <RestStatusBadge status={status} />
    </MantineProvider>,
  );
}

// F27 AC4: câu hiển thị đúng; không có "ngủ" / "tỉnh" (HS §5.3; glossary.md).
describe('RestStatusBadge', () => {
  it.each([
    ['RESTING', 'Đang nghỉ - dữ liệu tham khảo'],
    ['ACTIVE', 'Đang hoạt động'],
    ['UNKNOWN', 'Mức hoạt động: không đủ dữ liệu'],
  ] as const)('shows %s as "%s"', (status, text) => {
    const { container } = show(status);
    expect(screen.getByText(text)).toBeInTheDocument();
    const shown = (container.textContent ?? '').toLocaleLowerCase('vi');
    expect(shown).not.toMatch(/ngủ|tỉnh/u);
    expect(shown).not.toContain(status.toLowerCase());
  });
});
