# F32 – Chuyển tiếp cảnh báo chưa được tiếp nhận

| Thuộc tính | Giá trị |
|---|---|
| Mã | F32 |
| Trạng thái | Todo |
| Ưu tiên | Sau MVP |
| Milestone | Sau MVP |
| Ước lượng | 2 phiên |
| Phụ thuộc | F19 |
| Nhánh code | B (backend) |
| Nguồn | HS §9.2; PDF §18 (tr.18); QA#16 |

> Spec ngắn, ở mức định hướng. **Sẽ chi tiết hóa khi bắt đầu.**

## 1. Mục tiêu

Khi một cảnh báo ở trạng thái "Chờ tiếp nhận" quá lâu, hệ thống **chuyển tiếp** để người khác (ví dụ phụ trách ca) biết và xử lý, tránh cảnh báo bị bỏ sót (HS §9.2; PDF §18). Trong MVP không có timeout hay chuyển tiếp (QA#16).

## 2. Phạm vi

**Trong phạm vi**
- Phát hiện cảnh báo `PENDING` quá thời gian cấu hình.
- Đánh dấu "đã chuyển tiếp", phát WS, hiển thị nổi bật cho CHARGE_NURSE.
- Ghi audit cho thao tác chuyển tiếp do hệ thống thực hiện.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Gửi thông báo ra điện thoại (→ F33).
- Thay đổi vòng đời `status`/`outcome` của ADR-0007.
- Chuyển tiếp nhiều cấp, lịch phân công người trực.

## 3. Yêu cầu chi tiết

- **R1.** Cảnh báo `PENDING` quá `escalation.pending_timeout_s` thì được chuyển tiếp một lần. *(HS §9.2; giả định: tên khóa và nơi lưu cấu hình phía backend)*
- **R2.** Chuyển tiếp không đổi `status`; chỉ thêm dấu thời gian chuyển tiếp (cần migration, ví dụ `alerts.escalated_at`). *(giả định: giữ ADR-0007)*
- **R3.** Ghi audit với `actor_user_id = null` (hệ thống) và phát WS `alert.updated` sau commit. *(data-model.md; api-conventions.md; HS §4.2)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:** `server/src/postcare/domain/alerts.py`, tác vụ định kỳ trong tiến trình API.
- **Dữ liệu:** cột mới trên `alerts` *(giả định)* ([data-model.md](../02-architecture/data-model.md)).
- **API:** payload `alert.updated` thêm trường chuyển tiếp ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** nhãn "Đã chuyển tiếp" trên màn hình "Cảnh báo" (text trong `vi.ts`).
- **Cấu hình:** `escalation.pending_timeout_s` *(giả định)*.

## 5. Acceptance criteria

Định hướng, sẽ chi tiết hóa khi bắt đầu.

- [ ] **AC1.** Cảnh báo `PENDING` quá thời gian → được đánh dấu chuyển tiếp đúng một lần, có audit. *(HS §9.2)* — *Kiểm chứng:* test domain với đồng hồ giả.
- [ ] **AC2.** Cảnh báo đã tiếp nhận trước thời hạn → không chuyển tiếp. *(HS §9.2)* — *Kiểm chứng:* test domain (ca âm tính).
- [ ] **AC3.** Dashboard nhận `alert.updated` sau commit và hiển thị nhãn chuyển tiếp. *(HS §4.2)* — *Kiểm chứng:* test WS + component test.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | domain | Chuyển tiếp khi quá hạn | Chạy tác vụ hai lần → chỉ một lần chuyển tiếp |
| AC2 | domain | Đã tiếp nhận trước hạn | Không có audit chuyển tiếp |
| AC3 | API (WS) + component | Phát sau commit | — |

## 7. Giả định

- *(giả định)* Khóa `escalation.pending_timeout_s`, cột `alerts.escalated_at`, chuyển tiếp tới vai trò CHARGE_NURSE.

## 8. Câu hỏi mở

- Thời hạn chờ là bao lâu, có khác nhau theo mức ưu tiên không, và chuyển tiếp cho ai? **Chặn** khi bắt đầu chi tiết hóa.

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
