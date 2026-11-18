import { Badge } from '@mantine/core';

import type { RestStatus } from '../api/types';
import { vi } from '../i18n/vi';

// F27: trạng thái tham khảo, không phải phân loại giấc ngủ; không tạo cảnh báo.
const REST_COLOR: Record<RestStatus, string> = {
  RESTING: 'indigo',
  ACTIVE: 'teal',
  UNKNOWN: 'gray',
};

export function RestStatusBadge({ status }: { status: RestStatus }) {
  return (
    <Badge color={REST_COLOR[status]} variant="light" tt="none">
      {vi.rest[status]}
    </Badge>
  );
}
