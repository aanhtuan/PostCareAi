# Workflow: Cập nhật tiến độ và bàn giao

Chạy **cuối mỗi phiên làm việc** (kể cả khi dừng giữa chừng) và khi một feature hoàn thành. Mục đích: AI hoặc người khác đọc `docs/progress/` là tiếp tục được ngay.

## Khi feature hoàn thành (review Đạt)

1. **Spec feature:**
   - Tick mọi acceptance criteria.
   - `Trạng thái: Done`.
   - Ghi ngày hoàn thành vào "Ghi chú bàn giao".
2. **`docs/progress/ROADMAP.md`:** đổi trạng thái feature thành `Done`. Nếu milestone đủ điều kiện kết thúc thì đánh dấu milestone.
3. **`docs/progress/TASKS.md`:** chuyển feature sang "Đã xong gần đây"; chọn feature kế tiếp theo ROADMAP (mọi phụ thuộc đã Done) và đặt vào "Tiếp theo".
4. **`docs/03-features/README.md`:** cập nhật cột trạng thái.
5. Thêm entry vào `session-log.md` (mẫu dưới).
6. Commit tài liệu cùng nhánh feature: `docs(Fxx): update progress`. Mở PR / merge theo quy ước.

## Khi dừng giữa chừng

1. Commit phần đang làm.
2. `TASKS.md`: tick các bước đã xong; ghi bước đang dở.
3. Thêm entry `session-log.md` với "Đang dở" và "Bước tiếp theo" cụ thể tới mức lệnh cần chạy.

## Mẫu entry `session-log.md`

Thêm vào **đầu** danh sách (mới nhất ở trên):

```markdown
## YYYY-MM-DD HH:MM – <tool/agent> – <Fxx>
- **Mục tiêu phiên:** …
- **Đã làm:** … (commit: abc1234)
- **Kết quả kiểm tra:** `make check` xanh/đỏ (lý do)
- **Đang dở:** … (hoặc "Không")
- **Bước tiếp theo:** … (lệnh / file cụ thể)
- **Blocker / câu hỏi cho người dùng:** … (hoặc "Không")
- **Giả định mới:** … (đã ghi vào spec?)
```

## Quy tắc

- Không xóa entry cũ trong `session-log.md`.
- Trạng thái hợp lệ của feature: `Todo` → `Planned` → `In progress` → `In review` → `Done` (hoặc `Blocked`, kèm lý do).
- `ROADMAP.md`, `TASKS.md` và các spec phải **khớp nhau**. Nếu lệch thì sửa trước khi kết thúc phiên.
