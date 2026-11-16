# Workflow: Triển khai một feature

**Đầu vào:** mã feature đã có "Kế hoạch triển khai" (trạng thái `Planned`). **Vai trò:** developer; dùng [test-writer](../roles/test-writer.md) cho phần test.

## Các bước

1. **Chuẩn bị:**
   - Đọc `AGENTS.md`, spec, `TASKS.md`, entry cuối `session-log.md`.
   - `git switch main && git pull`, rồi `git switch -c feat/Fxx-<slug>`. Nếu nhánh đã tồn tại: `git switch feat/Fxx-<slug>`.
   - Chạy `make check` để chắc điểm xuất phát đang xanh.
   - Spec: `Trạng thái: In progress`.
2. **Làm theo từng bước của kế hoạch**, mỗi bước:
   1. Viết test trước, nhất là với rule engine và vòng đời cảnh báo. Chạy test, xác nhận test **fail đúng lý do**.
   2. Viết code tối thiểu để test pass. Tuân thủ [coding-standards.md](../../04-guides/coding-standards.md).
   3. Chạy `make check`.
   4. Commit nhỏ: `feat(Fxx): <mô tả>` / `test(Fxx): …`.
   5. Tick bước tương ứng trong `TASKS.md`.
3. **Giữ phạm vi:**
   - Không làm việc ngoài spec. Thấy cần thêm thì ghi vào "Câu hỏi mở" hoặc đề xuất feature mới trong `TASKS.md` (mục Backlog).
   - Không thêm thư viện khi chưa cập nhật spec và `tech-stack.md`.
4. **Cập nhật tài liệu cùng PR:**
   - data-model, api-conventions, event-engine, catalog sự kiện, `vi.ts`, ngưỡng mặc định;
   - `make gen-api-types` nếu API đổi.
5. **Kiểm chứng acceptance criteria:**
   - Từng AC phải có test tự động hoặc bước kiểm chứng thủ công đã thực hiện. Ghi kết quả vào mục "Ghi chú bàn giao" của spec.
   - Feature vision: chạy `make test-vision` hoặc `postcare replay` trên video dev.
6. **Chuyển sang review** theo [review.md](review.md).

## Nếu phải dừng giữa chừng

- Commit phần đang làm (có thể là WIP, test có thể đỏ nếu đã ghi rõ lý do).
- Ghi `session-log.md`: đã làm gì, đang dở ở bước nào, lệnh tiếp theo cần chạy, blocker.
- AI khác đọc session-log là tiếp tục được.
