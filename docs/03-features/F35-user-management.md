# F35 – Quản lý người dùng trên UI

| Thuộc tính | Giá trị |
|---|---|
| Mã | F35 |
| Trạng thái | Todo |
| Ưu tiên | Sau MVP |
| Milestone | Sau MVP |
| Ước lượng | 1 phiên |
| Phụ thuộc | F02 |
| Nhánh code | B (backend) + C (frontend/test) |
| Nguồn | *(giả định)*; PDF §10 (tr.12), §10.1 (tr.12–13); QA#18 |

> Spec ngắn, ở mức định hướng. **Sẽ chi tiết hóa khi bắt đầu.** Toàn bộ feature là *(giả định)*: nguồn không yêu cầu màn hình này; PDF §10 chỉ nêu backend quản lý người dùng.

## 1. Mục tiêu

Cho ADMIN tạo, sửa, ngừng dùng tài khoản và đặt lại mật khẩu trên giao diện, thay vì chỉ tạo bằng seed như trong MVP (QA#18). PDF §10 và §10.1 có thực thể người dùng và nhật ký thao tác do backend quản lý.

## 2. Phạm vi

**Trong phạm vi**
- Danh sách người dùng; tạo, sửa họ tên và vai trò, ngừng dùng (`is_active = false`), đặt lại mật khẩu.
- Audit cho mọi thao tác.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Tự đăng ký, quên mật khẩu qua email, SSO.
- Phân quyền chi tiết hơn 4 vai trò.
- Xóa cứng tài khoản (data-model.md: xóa mềm).

## 3. Yêu cầu chi tiết

- **R1.** Chỉ ADMIN được quản lý người dùng; vai trò khác → 403. *(api-conventions.md; giả định QA#18)*
- **R2.** `username` duy nhất (409 `DUPLICATE_CODE` hoặc mã lỗi tương tự); mật khẩu lưu dạng hash. *(data-model.md; PRD NFR06)*
- **R3.** Mọi thao tác ghi `record_audit()`, không ghi mật khẩu vào `before`/`after`. *(PDF §10.1; api-conventions.md)*
- **R4.** Không cho ngừng dùng tài khoản ADMIN cuối cùng đang hoạt động. *(giả định: tránh khóa hệ thống)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:** `server/src/postcare/domain/users.py`, `server/src/postcare/api/v1/users.py`, `web/src/pages/Management/Users/`.
- **Dữ liệu:** bảng `users` (đã có từ F01) ([data-model.md](../02-architecture/data-model.md)).
- **API:** `GET/POST/PATCH /api/v1/users`, `POST /api/v1/users/{id}/reset-password` *(giả định)* ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** mục "Người dùng" trong "Quản lý" (text trong `vi.ts`).
- **Cấu hình:** không có.

## 5. Acceptance criteria

Định hướng, sẽ chi tiết hóa khi bắt đầu.

- [ ] **AC1.** ADMIN tạo, sửa, ngừng dùng, đặt lại mật khẩu; NURSE/CHARGE_NURSE/DOCTOR → 403. *(QA#18)* — *Kiểm chứng:* API test theo vai trò.
- [ ] **AC2.** Trùng `username` → 409; tài khoản ngừng dùng không đăng nhập được. *(data-model.md)* — *Kiểm chứng:* API test.
- [ ] **AC3.** Mọi thao tác có audit, không chứa mật khẩu hay hash. *(PDF §10.1)* — *Kiểm chứng:* API test kiểm tra `audit_logs`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | Phân quyền | DOCTOR tạo người dùng → 403 |
| AC2 | API | Trùng tên, ngừng dùng | Đăng nhập tài khoản ngừng dùng → 401 |
| AC3 | API | Audit | Ngừng dùng ADMIN cuối cùng → 409 |

## 7. Giả định

- *(giả định)* Toàn bộ feature; endpoint và quy tắc ADMIN cuối cùng.

## 8. Câu hỏi mở

- Có thực sự cần màn hình này trước buổi demo, hay seed tài khoản là đủ? **Chặn** khi bắt đầu chi tiết hóa.

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
