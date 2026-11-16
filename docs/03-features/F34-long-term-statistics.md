# F34 – Dashboard thống kê dài hạn theo ca

| Thuộc tính | Giá trị |
|---|---|
| Mã | F34 |
| Trạng thái | Todo |
| Ưu tiên | Sau MVP |
| Milestone | Sau MVP |
| Ước lượng | 2 phiên |
| Phụ thuộc | F24 |
| Nhánh code | B (backend) + C (frontend/test) |
| Nguồn | HS §9.2, §6.2; PDF §18 (tr.18), bảng tr.10; conflicts C17 |

> Spec ngắn, ở mức định hướng. **Sẽ chi tiết hóa khi bắt đầu.**

## 1. Mục tiêu

Tổng hợp sự kiện và cảnh báo qua nhiều ca, nhiều ngày, để phụ trách ca và nhóm phát triển thấy xu hướng: loại sự kiện nào nhiều, tỷ lệ "Cảnh báo sai", thời gian tiếp nhận (HS §9.2 "dashboard thống kê theo ca"; PDF §18 "dashboard thống kê dài hạn"). Bàn giao ca cơ bản đã có ở MVP (F24; conflicts C17).

## 2. Phạm vi

**Trong phạm vi**
- Thống kê theo ca/ngày/tuần, theo giường: số sự kiện theo loại, số cảnh báo theo kết quả, thời gian tiếp nhận và xử lý.
- Màn hình thống kê có lọc khoảng thời gian.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Báo cáo đánh giá trên video (→ F16, F29).
- Phân tích lâm sàng hay xu hướng sức khỏe của bệnh nhân (không làm; HS §9.1).
- Xuất dữ liệu sang hệ thống khác.

## 3. Yêu cầu chi tiết

- **R1.** Số liệu tính bằng SQL aggregation trên `events`, `alerts`, `shift_definitions`; không có bảng tổng hợp riêng. *(PDF bảng tr.10 "SQL aggregation"; data-model.md)*
- **R2.** Hiển thị bằng tiếng Việt, không có mã nội bộ, không có từ cấm. *(PDF §9.2–9.3; glossary.md)*
- **R3.** Dùng lại cách tính thời gian tiếp nhận/xử lý của F29 nếu đã có. *(giả định: tránh hai công thức khác nhau)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:** `server/src/postcare/domain/statistics.py`, `server/src/postcare/api/v1/statistics.py`, `web/src/pages/Statistics/`.
- **Dữ liệu:** đọc `events`, `alerts`, `shift_definitions` ([data-model.md](../02-architecture/data-model.md)); có thể thêm index nếu chậm.
- **API:** `GET /api/v1/statistics?from&to&bed_id&group_by=shift|day` *(giả định)* ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** màn hình "Thống kê" (text trong `vi.ts`).
- **Cấu hình:** không có.

## 5. Acceptance criteria

Định hướng, sẽ chi tiết hóa khi bắt đầu.

- [ ] **AC1.** API trả số sự kiện theo loại và số cảnh báo theo kết quả, nhóm theo ca hoặc ngày, đúng trên dữ liệu mẫu. *(HS §9.2)* — *Kiểm chứng:* test domain với dữ liệu mẫu nhiều ca (gồm ca đêm vắt qua nửa đêm).
- [ ] **AC2.** Có thời gian tiếp nhận và xử lý trung vị theo ca. *(HS §6.2, §8.2)* — *Kiểm chứng:* test domain.
- [ ] **AC3.** Màn hình "Thống kê" lọc được theo khoảng thời gian và giường, không có từ cấm. *(PDF §18)* — *Kiểm chứng:* component test + `vi.test.ts`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | domain | Thống kê nhiều ca | Sự kiện 23:30 và 01:00 cùng thuộc ca đêm |
| AC2 | domain | Thời gian trung vị | Cảnh báo chưa tiếp nhận không tính |
| AC3 | component | Lọc và hiển thị | — |

## 7. Giả định

- *(giả định)* Endpoint `GET /api/v1/statistics` và tham số `group_by`.

## 8. Câu hỏi mở

- Cần những biểu đồ và chỉ số nào, ai là người xem chính? **Chặn** khi bắt đầu chi tiết hóa.

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
