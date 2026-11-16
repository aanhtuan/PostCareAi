# F33 – Thông báo di động cho điều dưỡng

| Thuộc tính | Giá trị |
|---|---|
| Mã | F33 |
| Trạng thái | Todo |
| Ưu tiên | Sau MVP |
| Milestone | Sau MVP |
| Ước lượng | 3 phiên |
| Phụ thuộc | F18 |
| Nhánh code | B (backend) + C (frontend/test) |
| Nguồn | HS §9.2; PDF §18 (tr.18), bảng tr.10 ("WebSocket / FCM"); QA#11 |

> Spec ngắn, ở mức định hướng. **Sẽ chi tiết hóa khi bắt đầu.**

## 1. Mục tiêu

Gửi cảnh báo tới điện thoại của điều dưỡng, để họ không phải đứng trước màn hình dashboard (HS §9.2; PDF §18 "mobile app cho điều dưỡng"). PDF bảng tr.10 nêu FCM là một kênh cảnh báo thời gian thực. MVP chỉ dùng WebSocket (QA#11).

## 2. Phạm vi

**Trong phạm vi**
- Gửi thông báo khi có cảnh báo mới mức "Cần chú ý" / "Ưu tiên cao".
- Nội dung chỉ gồm mã giường, câu mô tả tiếng Việt và thời điểm; **không** có ảnh (QA#29).
- Mở thông báo → vào màn hình chi tiết cảnh báo.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Ứng dụng di động native đầy đủ tính năng.
- Chuyển tiếp cảnh báo (→ F32).
- Gửi ảnh hoặc video.

## 3. Yêu cầu chi tiết

- **R1.** Thông báo chỉ gửi **sau khi** cảnh báo đã lưu DB (cùng quy tắc với WS). *(HS §4.2)*
- **R2.** Nội dung theo câu chữ trong `vi.ts`, không chứa từ cấm, không chứa mã nội bộ. *(PDF §9.2 (tr.11); glossary.md)*
- **R3.** Chọn kênh (FCM, Web Push/PWA hoặc kênh khác) khi chi tiết hóa, có xét yêu cầu chạy trong LAN. *(PDF bảng tr.10; QA#25; giả định)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:** `server/src/postcare/domain/notifications.py`, `server/src/postcare/api/v1/` (đăng ký thiết bị), `web/` (nếu dùng PWA).
- **Dữ liệu:** có thể cần bảng đăng ký thiết bị theo người dùng *(giả định)* ([data-model.md](../02-architecture/data-model.md)).
- **API:** endpoint đăng ký/hủy thiết bị *(giả định)* ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** cài đặt nhận thông báo.
- **Cấu hình:** khóa dịch vụ đẩy trong `.env` *(giả định)*.

## 5. Acceptance criteria

Định hướng, sẽ chi tiết hóa khi bắt đầu.

- [ ] **AC1.** Cảnh báo mới mức MEDIUM/HIGH → thiết bị đã đăng ký nhận thông báo; LOG/INFO không gửi. *(HS §9.2; QA#17)* — *Kiểm chứng:* test domain với kênh gửi giả.
- [ ] **AC2.** Thông báo chỉ gửi sau commit và không chứa ảnh, từ cấm hay mã nội bộ. *(HS §4.2; QA#29)* — *Kiểm chứng:* test domain + test quét nội dung.
- [ ] **AC3.** Mở thông báo → vào đúng chi tiết cảnh báo. *(giả định)* — *Kiểm chứng:* thủ công trên điện thoại.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | domain | Lọc theo mức ưu tiên | Sự kiện INFO không gửi |
| AC2 | domain | Thứ tự commit → gửi; quét nội dung | Commit lỗi → không gửi |
| AC3 | thủ công | Mở thông báo | — |

## 7. Giả định

- *(giả định)* Bảng đăng ký thiết bị, endpoint đăng ký, khóa dịch vụ trong `.env`.

## 8. Câu hỏi mở

- FCM cần Internet và dịch vụ cloud của Google; Web Push thường cần HTTPS. Cả hai mâu thuẫn với "chạy local trong LAN, không cloud" (QA#25) và "không HTTPS" (A09). Chọn kênh nào? **Chặn** khi bắt đầu chi tiết hóa.

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
