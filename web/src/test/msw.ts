// Server msw dùng chung cho test (testing.md §4). Không có handler mặc định:
// mỗi test tự thêm handler bằng `server.use(...)`; request không có handler sẽ lỗi.
import { setupServer } from 'msw/node';

export const server = setupServer();
