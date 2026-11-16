# F04 – Phiên theo dõi

| Thuộc tính | Giá trị |
|---|---|
| Mã | F04 |
| Trạng thái | Todo <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F03 |
| Nhánh code | B+C |
| Nguồn | PDF §4.2 (tr.5), §10.1 (tr.12–13); HS §6.2; QA#18; PRD NFR08 |

## 1. Mục tiêu

Gắn một bệnh nhân (mã thử nghiệm) với một giường và camera trong một khoảng thời gian. Mọi sự kiện sau này thuộc về phiên đó (PDF §4.2; HS §6.2: "Mỗi phiên theo dõi gắn một người thử nghiệm với một giường và camera trong một khoảng thời gian"). Điều dưỡng bắt đầu và kết thúc phiên trên giao diện; hệ thống ghi lại ai làm và lúc nào.

## 2. Phạm vi

**Trong phạm vi**
- API bắt đầu phiên, kết thúc phiên, liệt kê phiên (lọc phiên đang mở).
- Ràng buộc 1 phiên mở / giường và 1 phiên mở / bệnh nhân, ở mức API (409) và mức DB (partial unique index đã tạo ở F01).
- Audit log khi bắt đầu và kết thúc.
- Nút "Bắt đầu theo dõi" / "Kết thúc theo dõi" trên màn hình "Quản lý giường".

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Phát WebSocket `session.updated` (→ F18).
- Đưa `active_session_id` vào cấu hình của worker (→ F06).
- Gắn sự kiện với phiên (→ F17); timeline của phiên (→ F22).
- Sửa thông tin phiên sau khi tạo *(không có trong nguồn)*.

## 3. Yêu cầu chi tiết

- **R1.** `POST /api/v1/sessions` `{bed_id, patient_id}` → 201 `SessionOut` *(api-conventions.md)*:
  - `camera_id` lấy theo camera đang gắn với giường *(data-model.md: "Lấy theo giường khi mở phiên")*;
  - `started_at` = thời điểm server (UTC), `started_by` = người dùng hiện tại.
- **R2.** Quyền: NURSE, CHARGE_NURSE, ADMIN được mở/đóng phiên; DOCTOR → 403 `FORBIDDEN` *(api-conventions.md, bảng phân quyền; QA#18)*.
- **R3.** Giường đã có phiên mở hoặc bệnh nhân đã có phiên mở → 409 `SESSION_ALREADY_OPEN`, `details` cho biết vướng ở giường hay bệnh nhân *(api-conventions.md)*.
- **R4.** Ràng buộc đúng ở mức DB: hai yêu cầu mở phiên đồng thời cho cùng giường chỉ một yêu cầu thành công. Domain bắt `IntegrityError` của partial unique index và trả 409 `SESSION_ALREADY_OPEN` *(data-model.md)*.
- **R5.** Giường hoặc bệnh nhân đã ngừng dùng (`is_active = false`) hoặc không tồn tại → lần lượt 400 `VALIDATION_ERROR` / 404 `NOT_FOUND` *(giả định)*.
- **R6.** `POST /api/v1/sessions/{id}/end` ghi `ended_at`, `ended_by` *(data-model.md)*. Phiên đã kết thúc là **chỉ đọc**: gọi kết thúc lần nữa → 409 `SESSION_ALREADY_ENDED` *(giả định mã lỗi mới; thêm vào api-conventions.md cùng PR)*. Không có endpoint sửa phiên.
- **R7.** `GET /api/v1/sessions?active=true` trả phiên đang mở; không có `active` thì trả mọi phiên, sắp theo `started_at` giảm dần, có phân trang và lọc `bed_id`, `patient_id` *(api-conventions.md; giả định tham số lọc)*. `GET /api/v1/sessions/{id}` trả chi tiết. Mọi vai trò đã đăng nhập được xem.
- **R8.** Bắt đầu và kết thúc đều gọi `record_audit()` với action `session.start` và `session.end` *(data-model.md ví dụ action; PRD NFR08)*. Audit nằm trong cùng transaction với thay đổi phiên.
- **R9.** UI trên màn hình "Quản lý giường" *(PDF §9.1)*:
  - giường không có phiên: nút "Bắt đầu theo dõi" mở hộp thoại chọn bệnh nhân. Danh sách chỉ gồm bệnh nhân đang dùng và chưa có phiên mở;
  - giường có phiên: hiện mã bệnh nhân, giờ bắt đầu (`HH:mm:ss`, Asia/Ho_Chi_Minh) và nút "Kết thúc theo dõi", có hộp thoại xác nhận *(giả định)*;
  - DOCTOR không thấy hai nút này;
  - lỗi 409 hiện `message` tiếng Việt của API.
- **R10.** Giường chưa gắn camera vẫn mở phiên được, `camera_id = null`; UI hiện ghi chú "Chưa gắn camera" *(giả định: data-model.md cho `camera_id` null)*.
- **R11.** Text giao diện nằm trong `web/src/i18n/vi.ts` *(ADR-0005; glossary.md)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/v1/sessions.py`; `server/src/postcare/domain/sessions.py` (`start_session`, `end_session`, `list_sessions`).
  - Schema: `SessionCreate`, `SessionOut`.
  - `server/tests/api/test_sessions.py`, `server/tests/domain/test_sessions_constraints.py`.
  - `web/src/pages/Management/StartSessionDialog.tsx`, `EndSessionButton.tsx`; hooks `useSessions`, `useStartSession`, `useEndSession`; test `StartSessionDialog.test.tsx`.
  - `web/src/utils/time.ts`: hàm định dạng `HH:mm:ss` theo Asia/Ho_Chi_Minh *(coding-standards.md §3; giả định: tạo ở feature đầu tiên cần hiển thị giờ)*.
- **Dữ liệu:** `monitoring_sessions` (đã tạo ở F01), đọc `beds`, `patients`, `cameras`, ghi `audit_logs` (xem [data-model.md](../02-architecture/data-model.md#monitoring_sessions-f01-logic-ở-f04)). Không có migration mới.
- **API:** `POST /api/v1/sessions`, `POST /api/v1/sessions/{id}/end`, `GET /api/v1/sessions?active=true`, `GET /api/v1/sessions/{id}` (xem [api-conventions.md](../02-architecture/api-conventions.md#danh-sách-endpoint-dự-kiến)). Chạy `make gen-api-types`.
- **UI:** nút và hộp thoại trên "Quản lý giường". Text cần thêm vào `vi.ts`: `session.start` ("Bắt đầu theo dõi"), `session.end` ("Kết thúc theo dõi"), `session.choosePatient` ("Chọn bệnh nhân"), `session.confirmEnd` ("Kết thúc phiên theo dõi của giường này?"), `session.active` ("Đang theo dõi"), `session.none` ("Không theo dõi"), `session.startedAt` ("Bắt đầu lúc"), `camera.notAssigned` ("Chưa gắn camera").
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [ ] **AC1.** Bắt đầu phiên bằng cách chọn giường và bệnh nhân; camera lấy theo giường; ghi `started_by` và `started_at`. DOCTOR → 403. *(HS §6.2)* — *Kiểm chứng:* test `test_start_session_uses_bed_camera`, `test_start_session_records_actor_and_time`, `test_doctor_cannot_start_session`.
- [ ] **AC2.** Mỗi giường và mỗi bệnh nhân chỉ có 1 phiên mở; vi phạm → 409 `SESSION_ALREADY_OPEN`. Có test cả ở mức DB constraint. *(data-model.md)* — *Kiểm chứng:* test `test_second_open_session_same_bed_409`, `test_second_open_session_same_patient_409`, `test_db_partial_unique_blocks_duplicate_open_session` (chèn thẳng bằng SQLAlchemy → `IntegrityError`).
- [ ] **AC3.** Kết thúc phiên ghi `ended_at` và `ended_by`; phiên đã đóng chỉ đọc (kết thúc lần nữa → 409). Sau khi đóng, giường và bệnh nhân mở được phiên mới. *(PDF §10.1 (tr.12); data-model.md)* — *Kiểm chứng:* test `test_end_session_records_actor_and_time`, `test_end_closed_session_409`, `test_can_reopen_after_end`.
- [ ] **AC4.** Bắt đầu và kết thúc đều ghi audit log (`session.start`, `session.end`). UI có nút "Bắt đầu theo dõi" / "Kết thúc theo dõi". *(PRD NFR08)* — *Kiểm chứng:* test `test_session_start_end_audited`; component test `StartSessionDialog starts session`, `EndSessionButton asks for confirmation`, `doctor sees no session buttons`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | `test_start_session_uses_bed_camera`, `test_start_session_records_actor_and_time` | DOCTOR → 403; giường ngừng dùng → 400; giường không tồn tại → 404 |
| AC1 | API | `test_start_session_bed_without_camera` | `camera_id` null, không lỗi |
| AC2 | API + DB | `test_second_open_session_same_bed_409`, `..._same_patient_409`, `test_db_partial_unique_blocks_duplicate_open_session` | Phiên đã đóng không chặn phiên mới |
| AC3 | API | `test_end_session_records_actor_and_time`, `test_can_reopen_after_end` | `test_end_closed_session_409`; DOCTOR kết thúc → 403 |
| AC4 | API + component | `test_session_start_end_audited`; `StartSessionDialog.test.tsx` | Bắt đầu thất bại (409) → không có bản ghi audit |

## 7. Giả định

- *(giả định)* Mã lỗi mới `SESSION_ALREADY_ENDED` (409); cập nhật api-conventions.md cùng PR.
- *(giả định)* Giường/bệnh nhân ngừng dùng → 400 `VALIDATION_ERROR`; không tồn tại → 404.
- *(giả định)* Giường chưa có camera vẫn mở được phiên (`camera_id = null`).
- *(giả định)* Có hộp thoại xác nhận trước khi kết thúc phiên.
- *(giả định)* Tham số lọc `bed_id`, `patient_id` cho `GET /api/v1/sessions`.
- *(giả định)* Hàm định dạng giờ `web/src/utils/time.ts` tạo ở feature này nếu chưa có.

## 8. Câu hỏi mở

- Nếu camera của giường bị gỡ hoặc đổi trong lúc phiên đang mở thì phiên giữ `camera_id` cũ hay cập nhật? Mặc định: giữ giá trị lúc mở phiên. **Không chặn.**

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

1. …

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
