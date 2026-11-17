# F04 – Phiên theo dõi

| Thuộc tính | Giá trị |
|---|---|
| Mã | F04 |
| Trạng thái | In review <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 3 phiên |
| Phụ thuộc | F03 |
| Nhánh code | B+C |
| Nguồn | PDF §4.2 (tr.5), §10.1 (tr.12–13); HS §6.2; QA#18, QA#36; Yêu cầu người dùng (2026-11-17); PRD NFR08, US12 |

## 1. Mục tiêu

Gắn một bệnh nhân (mã thử nghiệm) với một giường và camera trong một khoảng thời gian. Mọi sự kiện sau này thuộc về phiên đó (PDF §4.2; HS §6.2: "Mỗi phiên theo dõi gắn một người thử nghiệm với một giường và camera trong một khoảng thời gian"). Điều dưỡng bắt đầu và kết thúc phiên trên giao diện; hệ thống ghi lại ai làm và lúc nào. Điều dưỡng chuyển được bệnh nhân sang giường khác trong một thao tác mà diễn biến của bệnh nhân không bị đứt (QA#36; PRD US12).

## 2. Phạm vi

**Trong phạm vi**
- API bắt đầu phiên, kết thúc phiên, liệt kê phiên (lọc phiên đang mở).
- "Chuyển giường": một thao tác kết thúc phiên hiện tại và mở phiên mới ở giường đích cho cùng bệnh nhân, liên kết hai phiên *(QA#36)*.
- Ràng buộc 1 phiên mở / giường và 1 phiên mở / bệnh nhân, ở mức API (409) và mức DB (partial unique index đã tạo ở F01).
- Audit log khi bắt đầu, kết thúc và chuyển giường.
- Nút "Bắt đầu theo dõi" / "Kết thúc theo dõi" / "Chuyển giường" trên màn hình "Quản lý giường".

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Phát WebSocket `session.updated` (→ F18).
- Đưa `active_session_id` vào cấu hình của worker (→ F06).
- Gắn sự kiện với phiên (→ F17); màn hình timeline (→ F22). F04 chỉ cung cấp liên kết giữa các phiên (`previous_session_id`, chuỗi phiên) để F22 hiển thị liền mạch.
- Ngắt quyền xem của người nhà khi phiên kết thúc hoặc chuyển giường (→ F36; F04 chỉ phát thông báo sau commit).
- Chuyển nhiều bệnh nhân một lúc, đổi chỗ hai bệnh nhân trong một thao tác *(không có trong yêu cầu)*.
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
- **R7.** `GET /api/v1/sessions?active=true` trả phiên đang mở; không có `active` thì trả mọi phiên, sắp theo `started_at` giảm dần, có phân trang và lọc `bed_id`, `patient_id` *(api-conventions.md; giả định tham số lọc)*. `GET /api/v1/sessions/{id}` trả chi tiết. Mọi vai trò nhân viên được xem; `FAMILY` → 403 (người nhà xem qua F36) *(QA#31; F35 R2)*.
- **R8.** Bắt đầu và kết thúc đều gọi `record_audit()` với action `session.start` và `session.end` *(data-model.md ví dụ action; PRD NFR08)*. Audit nằm trong cùng transaction với thay đổi phiên.
- **R9.** UI trên màn hình "Quản lý giường" *(PDF §9.1)*:
  - giường không có phiên: nút "Bắt đầu theo dõi" mở hộp thoại chọn bệnh nhân. Danh sách chỉ gồm bệnh nhân đang dùng và chưa có phiên mở;
  - giường có phiên: hiện mã bệnh nhân, giờ bắt đầu (`HH:mm:ss`, Asia/Ho_Chi_Minh) và nút "Kết thúc theo dõi", có hộp thoại xác nhận *(giả định)*;
  - DOCTOR không thấy hai nút này;
  - lỗi 409 hiện `message` tiếng Việt của API.
- **R10.** Giường chưa gắn camera vẫn mở phiên được, `camera_id = null`; UI hiện ghi chú "Chưa gắn camera" *(giả định: data-model.md cho `camera_id` null)*.
- **R11.** Text giao diện nằm trong `web/src/i18n/vi.ts` *(ADR-0005; glossary.md)*.

**Chuyển giường** *(QA#36; Yêu cầu người dùng 2026-11-17; PRD US12)*

- **R12.** `POST /api/v1/sessions/{id}/transfer` `{target_bed_id, reason}` → 201 `SessionOut` của phiên mới. Quyền như mở/đóng phiên (NURSE, CHARGE_NURSE, ADMIN); DOCTOR, FAMILY → 403 *(R2)*. `reason` bắt buộc, không rỗng *(Yêu cầu người dùng 2026-11-17: chuyển có lý do)*.
- **R13.** Một transaction duy nhất *(Yêu cầu người dùng 2026-11-17: "một thao tác")*:
  - kết thúc phiên cũ: `ended_at = now`, `ended_by` = người thực hiện;
  - mở phiên mới cho **cùng bệnh nhân** ở giường đích: `camera_id` theo camera của giường đích (R1, R10), `started_at` = cùng thời điểm `ended_at` của phiên cũ, `started_by` = người thực hiện, `previous_session_id` = id phiên cũ, `transfer_reason` = `reason`;
  - phiên cũ phải được đóng (flush) trước khi chèn phiên mới để không vi phạm `UNIQUE (patient_id) WHERE ended_at IS NULL`;
  - lỗi ở bất kỳ bước nào → rollback toàn bộ, phiên cũ vẫn mở *(giả định)*.
- **R14.** Kiểm tra *(giả định mã lỗi)*:
  - phiên cũ đã kết thúc → 409 `SESSION_ALREADY_ENDED`;
  - giường đích trùng giường hiện tại → 400 `VALIDATION_ERROR`;
  - giường đích không tồn tại → 404 `NOT_FOUND`; đã xóa (`is_active = false`) → 400 `VALIDATION_ERROR` (như R5);
  - giường đích đã có phiên mở → 409 `SESSION_ALREADY_OPEN` (`details.bed_id`), kể cả khi hai yêu cầu chuyển đồng thời vào cùng giường (bắt `IntegrityError` như R4).
- **R15.** Audit một bản ghi `session.transfer` cho phiên mới (`entity_type = "session"`, `entity_id` = phiên mới), `before` `{session_id, bed_id}` của phiên cũ, `after` `{session_id, bed_id, reason}` của phiên mới, cùng transaction *(Yêu cầu người dùng 2026-11-17; giả định: không ghi thêm `session.end`/`session.start` riêng để timeline không lặp)*.
- **R16.** Liên kết và timeline liền mạch theo bệnh nhân *(Yêu cầu người dùng 2026-11-17; PRD US12)*:
  - `monitoring_sessions.previous_session_id` (FK, unique, null) — mỗi phiên có tối đa một phiên trước và một phiên sau;
  - `SessionOut` có `previous_session_id` và `next_session_id`;
  - `GET /api/v1/sessions/{id}/chain` trả các phiên cùng chuỗi chuyển giường, sắp theo `started_at` (mỗi phiên: `id`, `bed` mã giường, `started_at`, `ended_at`, `transfer_reason`), để F22 ghép timeline của cả chuỗi và chèn mục "Chuyển từ giường A01 sang A02" từ audit `session.transfer` *(giả định: F22 dùng endpoint này)*;
  - sự kiện cũ giữ nguyên `session_id` và `bed_id` của phiên cũ; không chuyển sự kiện sang phiên mới *(data-model.md: không sửa sự kiện)*.
- **R17.** Sau commit phát `session.updated` cho cả hai phiên (F18) và báo cho hub để quyền xem của người nhà trên phiên cũ kết thúc (F36 R5, R14). Phiên mới **không** kế thừa quyền xem của người nhà *(giả định; F36)*. Phiên cũ đang "tạm dừng thu hình" (F36) thì phiên mới bắt đầu ở trạng thái **không** tạm dừng *(giả định; cần xác nhận lại ở F36)*.
- **R18.** UI: giường có phiên hiện nút "Chuyển giường" (NURSE, CHARGE_NURSE, ADMIN), mở hộp thoại chọn giường đích (chỉ giường đang dùng, chưa có phiên mở) và nhập lý do; hộp thoại xác nhận ghi rõ "Kết thúc theo dõi ở giường A01 và bắt đầu ở giường A02" *(giả định)*. Chi tiết phiên hiện "Chuyển từ giường …" khi có `previous_session_id`.

**Tạm dừng thu hình (phần phiên)** *(MS §3; F36 R15–R17; người giao việc chuyển phần mức phiên sang F04 ngày 2026-11-18)*

- **R19.** Cột `monitoring_sessions.paused_at`, `paused_by` (F36 R15; data-model.md). `SessionOut` có `paused_at`, `paused_by`. `POST /api/v1/sessions/{id}/pause` `{reason?}` và `POST /api/v1/sessions/{id}/resume` → 200 `SessionOut`. Quyền như mở/đóng phiên; `DOCTOR`, `FAMILY` → 403 (F36 R16).
- **R20.** Đang tạm dừng mà gọi pause → 409 `SESSION_ALREADY_PAUSED`; không tạm dừng mà gọi resume → 409 `SESSION_NOT_PAUSED`; phiên đã kết thúc → 409 `SESSION_ALREADY_ENDED` (F36 R16). Kết thúc phiên hoặc chuyển giường khi đang tạm dừng là hợp lệ; khi đó `paused_at`/`paused_by` của phiên cũ được xóa (giá trị cũ nằm trong `before` của audit) *(giả định)*, phiên mới không tạm dừng (R17).
- **R21.** Audit `session.pause` (`after` `{paused_at, reason}`) / `session.resume` (`before` `{paused_at}`), cùng transaction; sau commit phát `session.updated` (F36 R17, phần nhân viên).
- **R22.** `GET /internal/v1/cameras/{id}/config` trả `capture_paused` (phiên đang mở của giường đang tạm dừng); `POST /internal/v1/events` cho phiên đang tạm dừng (sự kiện xảy ra từ lúc `paused_at`) → 409 `CAPTURE_PAUSED` (F36 R18). UI "Quản lý giường": nút "Tạm dừng thu hình" / "Tiếp tục thu hình" cho vai trò được ghi, nhãn "Đang tạm dừng thu hình – hệ thống không quan sát trong lúc này" (F36 R18, R21).
- Vẫn thuộc F36: `family.state`/`capture_paused` cho người nhà, worker dừng đọc khung, API bỏ `state`/`frame` khi tạm dừng, mục tạm dừng trên timeline.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/v1/sessions.py`; `server/src/postcare/domain/sessions.py` (`start_session`, `end_session`, `transfer_session`, `session_chain`, `list_sessions`).
  - Schema: `SessionCreate`, `SessionTransfer`, `SessionOut`, `SessionChainItem`.
  - `server/tests/api/test_sessions.py`, `server/tests/api/test_session_transfer.py`, `server/tests/domain/test_sessions_constraints.py`.
  - `web/src/pages/Management/StartSessionDialog.tsx`, `EndSessionButton.tsx`, `TransferSessionDialog.tsx`; hooks `useSessions`, `useStartSession`, `useEndSession`, `useTransferSession`; test `StartSessionDialog.test.tsx`, `TransferSessionDialog.test.tsx`.
  - `web/src/utils/time.ts`: hàm định dạng `HH:mm:ss` theo Asia/Ho_Chi_Minh *(coding-standards.md §3; giả định: tạo ở feature đầu tiên cần hiển thị giờ)*.
- **Dữ liệu:** `monitoring_sessions` (đã tạo ở F01), đọc `beds`, `patients`, `cameras`, ghi `audit_logs` (xem [data-model.md](../02-architecture/data-model.md#monitoring_sessions-f01-logic-ở-f04)). Migration mới thêm cột `previous_session_id` (FK → `monitoring_sessions`, unique, null) và `transfer_reason` (text, null).
- **API:** `POST /api/v1/sessions`, `POST /api/v1/sessions/{id}/end`, `POST /api/v1/sessions/{id}/transfer`, `GET /api/v1/sessions?active=true`, `GET /api/v1/sessions/{id}`, `GET /api/v1/sessions/{id}/chain` (xem [api-conventions.md](../02-architecture/api-conventions.md#danh-sách-endpoint-dự-kiến)). Chạy `make gen-api-types`.
- **UI:** nút và hộp thoại trên "Quản lý giường". Text cần thêm vào `vi.ts`: `session.start` ("Bắt đầu theo dõi"), `session.end` ("Kết thúc theo dõi"), `session.choosePatient` ("Chọn bệnh nhân"), `session.confirmEnd` ("Kết thúc phiên theo dõi của giường này?"), `session.active` ("Đang theo dõi"), `session.none` ("Không theo dõi"), `session.startedAt` ("Bắt đầu lúc"), `camera.notAssigned` ("Chưa gắn camera"), `session.transfer` ("Chuyển giường"), `session.transferTarget` ("Giường chuyển đến"), `session.transferReason` ("Lý do chuyển"), `session.confirmTransfer` ("Kết thúc theo dõi ở giường {from} và bắt đầu ở giường {to}?"), `session.transferredFrom` ("Chuyển từ giường {bed}").
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [x] **AC1.** Bắt đầu phiên bằng cách chọn giường và bệnh nhân; camera lấy theo giường; ghi `started_by` và `started_at`. DOCTOR → 403. *(HS §6.2)* — *Kiểm chứng:* test `test_start_session_uses_bed_camera`, `test_start_session_records_actor_and_time`, `test_doctor_cannot_start_session`.
- [x] **AC2.** Mỗi giường và mỗi bệnh nhân chỉ có 1 phiên mở; vi phạm → 409 `SESSION_ALREADY_OPEN`. Có test cả ở mức DB constraint. *(data-model.md)* — *Kiểm chứng:* test `test_second_open_session_same_bed_409`, `test_second_open_session_same_patient_409`, `test_db_partial_unique_blocks_duplicate_open_session` (chèn thẳng bằng SQLAlchemy → `IntegrityError`).
- [x] **AC3.** Kết thúc phiên ghi `ended_at` và `ended_by`; phiên đã đóng chỉ đọc (kết thúc lần nữa → 409). Sau khi đóng, giường và bệnh nhân mở được phiên mới. *(PDF §10.1 (tr.12); data-model.md)* — *Kiểm chứng:* test `test_end_session_records_actor_and_time`, `test_end_closed_session_409`, `test_can_reopen_after_end`.
- [x] **AC4.** Bắt đầu và kết thúc đều ghi audit log (`session.start`, `session.end`). UI có nút "Bắt đầu theo dõi" / "Kết thúc theo dõi". *(PRD NFR08)* — *Kiểm chứng:* test `test_session_start_end_audited`; component test `StartSessionDialog starts session`, `EndSessionButton asks for confirmation`, `doctor sees no session buttons`.
- [x] **AC5.** "Chuyển giường" trong một thao tác: phiên cũ có `ended_at`/`ended_by`, phiên mới cùng bệnh nhân ở giường đích có `previous_session_id` = phiên cũ, `transfer_reason`, camera của giường đích; một bản ghi audit `session.transfer`; `GET /sessions/{id}/chain` trả cả hai phiên theo thứ tự. *(QA#36; PRD US12)* — *Kiểm chứng:* test `test_transfer_ends_old_and_opens_new`, `test_transfer_links_sessions`, `test_transfer_uses_target_bed_camera`, `test_transfer_audited_once`, `test_session_chain_ordered`; component test `TransferSessionDialog transfers patient`, `doctor sees no transfer button`.
- [x] **AC6.** Chuyển giường không để lại trạng thái dở dang: giường đích có phiên mở → 409 `SESSION_ALREADY_OPEN` và phiên cũ **vẫn mở**, không có audit; giường đích trùng giường hiện tại hoặc đã xóa → 400; phiên đã kết thúc → 409 `SESSION_ALREADY_ENDED`; hai yêu cầu chuyển đồng thời vào cùng giường chỉ một thành công; sự kiện của phiên cũ không đổi `session_id`. *(QA#36; data-model.md)* — *Kiểm chứng:* test `test_transfer_target_busy_409_keeps_old_open`, `test_transfer_same_bed_400`, `test_transfer_to_deleted_bed_400`, `test_transfer_closed_session_409`, `test_concurrent_transfer_same_target_one_wins`, `test_transfer_keeps_old_events_on_old_session`, `test_transfer_requires_reason`.
- [x] **AC7.** Tạm dừng / tiếp tục thu hình theo phiên: audit `session.pause`/`session.resume`; tạm dừng hai lần → 409 `SESSION_ALREADY_PAUSED`; tiếp tục khi không tạm dừng → 409 `SESSION_NOT_PAUSED`; phiên đã kết thúc → 409 `SESSION_ALREADY_ENDED`; config nội bộ có `capture_paused`; sự kiện engine khi tạm dừng → 409 `CAPTURE_PAUSED`; `DOCTOR`/`FAMILY` → 403. *(R19–R22; F36 AC6 phần phiên)* — *Kiểm chứng:* `server/tests/api/test_session_pause.py`; component test `PauseCaptureButton pauses and resumes`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | `test_start_session_uses_bed_camera`, `test_start_session_records_actor_and_time` | DOCTOR → 403; giường ngừng dùng → 400; giường không tồn tại → 404 |
| AC1 | API | `test_start_session_bed_without_camera` | `camera_id` null, không lỗi |
| AC2 | API + DB | `test_second_open_session_same_bed_409`, `..._same_patient_409`, `test_db_partial_unique_blocks_duplicate_open_session` | Phiên đã đóng không chặn phiên mới |
| AC3 | API | `test_end_session_records_actor_and_time`, `test_can_reopen_after_end` | `test_end_closed_session_409`; DOCTOR kết thúc → 403 |
| AC4 | API + component | `test_session_start_end_audited`; `StartSessionDialog.test.tsx` | Bắt đầu thất bại (409) → không có bản ghi audit |
| AC5 | API + component | `test_session_transfer.py`; `TransferSessionDialog.test.tsx` | DOCTOR/FAMILY chuyển → 403; thiếu `reason` → 400 |
| AC6 | API + DB | Giường đích bận, trùng, đã xóa; hai request đồng thời | Lỗi giữa transaction → phiên cũ vẫn mở, không có phiên mới, không có audit |

## 7. Giả định

- *(giả định)* Mã lỗi mới `SESSION_ALREADY_ENDED` (409); cập nhật api-conventions.md cùng PR.
- *(giả định)* Giường/bệnh nhân ngừng dùng → 400 `VALIDATION_ERROR`; không tồn tại → 404.
- *(giả định)* Giường chưa có camera vẫn mở được phiên (`camera_id = null`).
- *(giả định)* Có hộp thoại xác nhận trước khi kết thúc phiên.
- *(giả định)* Tham số lọc `bed_id`, `patient_id` cho `GET /api/v1/sessions`.
- *(giả định)* Hàm định dạng giờ `web/src/utils/time.ts` tạo ở feature này nếu chưa có.
- *(giả định)* Chuyển giường: `reason` bắt buộc; phiên mới bắt đầu đúng thời điểm phiên cũ kết thúc; một bản ghi audit `session.transfer` (không thêm `session.end`/`session.start`).
- *(giả định)* `previous_session_id` unique: chuỗi chuyển giường là tuyến tính; endpoint `GET /sessions/{id}/chain` cho F22.
- *(giả định)* Phiên mới không kế thừa quyền xem của người nhà và không kế thừa trạng thái tạm dừng thu hình (F36).

## 8. Câu hỏi mở

- Nếu camera của giường bị gỡ hoặc đổi trong lúc phiên đang mở thì phiên giữ `camera_id` cũ hay cập nhật? Mặc định: giữ giá trị lúc mở phiên. **Không chặn.**
- Khi chuyển giường, phiên mới có nên tự kế thừa quyền xem của người nhà (cùng mức chia sẻ) để người nhà không phải chờ cấp lại không? Mặc định: không, vì chấp thuận chia sẻ gắn với phiên (F36). **Không chặn.**
- F22 cần thêm chế độ xem timeline theo chuỗi phiên (dùng `GET /sessions/{id}/chain`) và mục "Chuyển giường"; cập nhật spec F22 khi làm. **Không chặn** F04.

## 9. Kế hoạch triển khai

Khảo sát (2026-11-18): đã có `domain/sessions.py` (`start_session` khóa hàng giường/bệnh nhân, bắt `IntegrityError`; `end_session`; `list_sessions`; `session_at`), `api/v1/sessions.py` (start/end/list/get/timeline với `require_writer`/`require_staff`), `tests/test_sessions.py`, test partial unique ở `tests/db/test_migrations.py`, UI mở/kết thúc phiên viết liền trong `ManagementPage.tsx`, `utils/time.ts`. Thiếu: chuyển giường, chuỗi phiên, tạm dừng, khóa hàng phiên khi kết thúc, test theo tên AC, component test, `details.bed_id`/`patient_id` trong 409.

1. **Test trước (server):** `server/tests/api/test_sessions.py` (AC1–AC4, chuyển từ `tests/test_sessions.py`), `server/tests/api/test_session_transfer.py` (AC5, AC6), `server/tests/api/test_session_pause.py` (AC7), `server/tests/domain/test_sessions_constraints.py` (partial unique, `previous_session_id` unique, đồng thời bằng `real_commit` + 2 luồng), test "phát sau commit" (`real_commit`, publisher đọc lại bằng kết nối khác). Thêm endpoint mới vào danh sách FAMILY bị chặn. Xác nhận đỏ đúng lý do, commit `test(F04): …`.
2. **Migration `0005_f04`** (`0005_f04_session_transfer_pause.py`, `down_revision = "0004"`): `previous_session_id` (FK `monitoring_sessions.id`, unique `uq_monitoring_sessions_previous_session_id`), `transfer_reason` text, `paused_at` timestamptz, `paused_by` (FK `users.id`). Cập nhật `db/models.py` (quan hệ `previous_session`/`next_session`), `tests/db/test_migrations.py`. Nếu F37 vào `main` trước: đổi `down_revision` sang revision của F37 khi merge.
3. **Domain** `domain/sessions.py`: khóa hàng phiên `FOR UPDATE` ở end/transfer/pause/resume; `transfer_session` (khóa phiên cũ → kiểm tra R14 → khóa giường đích → kết thúc + flush → chèn phiên mới → audit `session.transfer` → commit → phát `session.updated` phiên cũ rồi phiên mới; `IntegrityError` → rollback, 409); `session_chain`; `pause_session`/`resume_session`; xóa `paused_*` khi kết thúc. `domain/dto.py`: `SessionTransfer`, `SessionPause`, `SessionChainItem`, trường mới của `SessionOut`. `domain/cameras.py` `capture_paused`; `domain/events.py` `CAPTURE_PAUSED`.
4. **API** `api/v1/sessions.py`: `/transfer` (201), `/chain`, `/pause`, `/resume`. `make gen-api-types`.
5. **Web:** tách `pages/Management/StartSessionDialog.tsx`, `EndSessionButton.tsx`; thêm `TransferSessionDialog.tsx`, `PauseCaptureButton.tsx`; hook `useTransferSession`, `usePauseCapture`, `useResumeCapture` trong `api/hooks.ts`; text trong `i18n/vi.ts` (`session.*`, `capture.*`); giờ bắt đầu `HH:mm:ss` (`formatTime`). Component test `StartSessionDialog.test.tsx`, `TransferSessionDialog.test.tsx`, `PauseCaptureButton` trong `ManagementPage.test.tsx`.
6. **Docs:** `api-conventions.md` (mã lỗi pause chuyển sang F04, endpoint pause là F04, `capture_paused`), `data-model.md` (cột ghi F04, migration 0005), spec F36 (ghi chú phần đã làm ở F04).
7. **Kiểm chứng:** `make check`, `scripts/dev.ps1 check`; chạy tay bằng curl trên DB `postcare_f04`, cổng 8014; ghi bằng chứng vào §10, trạng thái "In review".

Quyết định nhỏ *(giả định)*: `reason` thiếu/rỗng (sau khi bỏ khoảng trắng) → 422 `VALIDATION_ERROR` như mọi lỗi schema (api-conventions.md), không phải 400; `SessionChainItem` dùng `bed_id`, `bed_code` (thay vì `bed`) cho khớp `SessionOut`; `/chain` trả `{items, total}`.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-18 – triển khai (nhánh `feat/F04-monitoring-sessions`), trạng thái In review.**

Bằng chứng theo AC (test tự động):

| AC | Test |
|---|---|
| AC1 | `server/tests/api/test_sessions.py`: `test_start_session_uses_bed_camera`, `test_start_session_records_actor_and_time`, `test_start_session_bed_without_camera`, `test_doctor_cannot_start_session`, `test_start_session_unknown_bed_or_patient_404`, `test_start_session_inactive_bed_or_patient_400` |
| AC2 | `test_second_open_session_same_bed_409`, `test_second_open_session_same_patient_409` (`details` có `conflict` + `bed_id`/`patient_id`); `server/tests/domain/test_sessions_constraints.py`: `test_db_partial_unique_blocks_duplicate_open_session`, `test_db_closed_session_does_not_block`, `test_concurrent_start_same_bed_one_wins` (`real_commit`, 2 luồng) |
| AC3 | `test_end_session_records_actor_and_time`, `test_end_closed_session_409`, `test_can_reopen_after_end`, `test_doctor_cannot_end_session` |
| AC4 | `test_session_start_end_audited` (409 không ghi audit); `test_session_updates_published_after_commit` (`real_commit`: publisher đọc lại được dữ liệu từ kết nối khác); `test_family_forbidden_on_session_endpoints`; web `StartSessionDialog.test.tsx`: `StartSessionDialog starts session`, `EndSessionButton asks for confirmation`, `doctor sees no session buttons`, giờ `HH:mm:ss` giờ VN |
| AC5 | `server/tests/api/test_session_transfer.py`: `test_transfer_ends_old_and_opens_new`, `test_transfer_links_sessions`, `test_transfer_uses_target_bed_camera`, `test_transfer_to_bed_without_camera`, `test_transfer_audited_once`, `test_session_chain_ordered`; web `TransferSessionDialog.test.tsx`: `TransferSessionDialog transfers patient`, `doctor sees no transfer button`, "Chuyển từ giường A01" |
| AC6 | `test_transfer_target_busy_409_keeps_old_open`, `test_transfer_same_bed_400`, `test_transfer_to_deleted_bed_400`, `test_transfer_to_unknown_bed_404`, `test_transfer_closed_session_409`, `test_transfer_twice_from_same_session_409`, `test_transfer_requires_reason`, `test_transfer_keeps_old_events_on_old_session`; `test_concurrent_transfer_same_target_one_wins` (`real_commit`); `test_db_previous_session_id_unique` |
| AC7 | `server/tests/api/test_session_pause.py` (pause/resume + audit, hai lần → 409, resume khi không tạm dừng → 409, phiên đã kết thúc → 409, DOCTOR 403, config `capture_paused`, sự kiện engine → `CAPTURE_PAUSED`, kết thúc/chuyển khi đang tạm dừng); web `PauseCaptureButton pauses and resumes`, `paused session shows label and resume button` |

Chạy tay (DB `postcare_f04`, `postcare seed --reset --no-history`, uvicorn cổng 8014, script urllib): mở phiên A01/BN-001 → 201, camera 1; trùng giường → 409 `SESSION_ALREADY_OPEN` `{conflict: bed, bed_id: 1}`; trùng bệnh nhân → 409; DOCTOR mở/chuyển → 403; tạm dừng → 200, lần hai → 409 `SESSION_ALREADY_PAUSED`; config nội bộ camera 1 `capture_paused: true`; lý do rỗng → 422 `VALIDATION_ERROR`; chuyển cùng giường → 400; chuyển sang A02 → 201, `previous_session_id = 1`, `previous_bed_code = A01`, `paused_at = null`, phiên cũ `ended_at` = `started_at` phiên mới; chuyển lại phiên cũ → 409 `SESSION_ALREADY_ENDED`; chuyển sang giường đang có phiên → 409 và phiên nguồn vẫn mở; `/sessions/1/chain` → `[(1, A01, null), (2, A02, "Đổi phòng")]`; resume khi không tạm dừng → 409 `SESSION_NOT_PAUSED`; kết thúc → 200, lần hai → 409.

Kiểm tra (2026-11-18): `make check` exit 0 (server 692 passed, web 77 passed, build OK); `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 check` exit 0.

Điều người sau cần biết:
- Migration `0005_f04` (`down_revision = "0004"`). Nếu F37 vào `main` trước với revision khác nối sau `0004`, đổi `down_revision` của `0005_f04` sang revision của F37 khi merge (hoặc ngược lại), để Alembic chỉ có một head.
- Phần tạm dừng mức phiên làm ở F04 theo yêu cầu người giao việc (R19–R22). F36 còn: `family.state`, worker dừng đọc khung, API bỏ `state`/`frame` khi tạm dừng, mục tạm dừng trên timeline.
- Lệch nhỏ so với spec *(giả định, ghi ở §9)*: `reason` rỗng → 422 (không phải 400); `SessionChainItem` dùng `bed_id`/`bed_code`; thêm `SessionOut.previous_bed_code` để UI hiện "Chuyển từ giường …" mà không cần gọi thêm API.
- R17 phần người nhà: F04 chỉ phát `session.updated` cho phiên cũ rồi phiên mới sau commit; ngắt quyền người nhà làm ở F36.
- Review: chưa.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
