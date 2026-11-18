# F36 – Quyền xem của người nhà theo phiên

| Thuộc tính | Giá trị |
|---|---|
| Mã | F36 |
| Trạng thái | In progress <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M4 |
| Ước lượng | 3 phiên |
| Phụ thuộc | F02, F04, F18, F22, F28, F35 |
| Nhánh code | B+C |
| Nguồn | Yêu cầu người dùng (2026-11-17); MS §3 (MS = Đề xuất nhóm (POSTCARE-AI-MASTER-SPEC, 17/11/2026)); QA#31, QA#36; QA#25; A09; PRD §3, US10 |

## 1. Mục tiêu

Người nhà muốn biết trạng thái và diễn biến của đúng người thân khi không ở cạnh giường (PRD US10; QA#31). Feature này thêm vai trò `FAMILY` vào phạm vi chính: nhân viên cấp quyền xem **theo từng phiên theo dõi**, ở một mức chia sẻ đã được đồng ý (chỉ thông tin, hoặc thông tin + skeleton), có thể thu hồi, và mọi thao tác đều có audit. Chấp thuận cho nhân viên quan sát **khác** chấp thuận chia sẻ cho người nhà (MS §3; QA#31; PRD §3). Feature cũng thêm thao tác "Tạm dừng thu hình" theo phiên để tôn trọng riêng tư (MS §3), hiển thị rõ là đang tạm dừng cho cả nhân viên lẫn người nhà. Người nhà xem trên điện thoại qua LAN (QA#25; A09).

## 2. Phạm vi

**Trong phạm vi**
- Bảng `family_access_grants`; cấp, liệt kê, thu hồi quyền xem theo phiên; audit `family_access.grant` / `family_access.revoke` / `family_access.view`.
- Hai mức chia sẻ `INFO` (mặc định) và `SKELETON`.
- API riêng cho `FAMILY` (`/api/v1/family/...`) chỉ trả dữ liệu của phiên được cấp quyền.
- Lọc WebSocket theo từng kết nối của `FAMILY`; ngắt luồng khi quyền hết hiệu lực.
- Tạm dừng / tiếp tục thu hình theo phiên (cờ ở mức phiên), worker dừng đọc khung khi tạm dừng.
- Màn hình `/family` tối ưu cho điện thoại; phần cấp/thu hồi quyền trên màn hình chi tiết phiên của nhân viên.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Truy cập từ ngoài LAN, Internet, app di động riêng (QA#25; A09; → F33 nếu sau này cần thông báo di động).
- Xác minh pháp lý người đại diện, chữ ký số cho chấp thuận *(Yêu cầu người dùng 2026-11-17)*. Hệ thống chỉ ghi `consent_note`.
- Tạo tài khoản `FAMILY` (→ F35).
- Người nhà thao tác cảnh báo, xem giường khác, bàn giao ca, quản lý *(QA#31)*.
- Gửi ảnh hoặc video cho người nhà ở bất kỳ mức nào (QA#29; MS §3).
- Chế độ hiển thị của camera cho nhân viên (→ F28; F36 không đổi `cameras.display_mode`).

## 3. Yêu cầu chi tiết

**Cấp và thu hồi quyền**

- **R1.** Bảng `family_access_grants` *(Yêu cầu người dùng 2026-11-17; data-model.md)*: `id`, `session_id` (FK `monitoring_sessions`), `user_id` (FK `users`), `share_level` (`INFO` | `SKELETON`), `consent_note`, `granted_by`, `granted_at`, `expires_at` (null = đến khi phiên kết thúc), `revoked_at`, `revoked_by`. Partial unique index `(session_id, user_id) WHERE revoked_at IS NULL` *(giả định: tránh hai quyền đang hiệu lực cho cùng người, cùng phiên)*.
- **R2.** `POST /api/v1/sessions/{id}/family-grants` `{user_id, share_level?, consent_note, expires_at?}` → 201. Chỉ `CHARGE_NURSE` và `ADMIN`; vai trò khác → 403 `FORBIDDEN` *(giả định: người chịu trách nhiệm khu vực xác nhận chấp thuận chia sẻ)*. `share_level` mặc định `INFO` *(MS §3)*.
- **R3.** Kiểm tra khi cấp *(giả định)*:
  - `user_id` phải là tài khoản đang dùng có vai trò `FAMILY`, nếu không → 400 `VALIDATION_ERROR`;
  - `consent_note` bắt buộc, không rỗng (ghi ai đồng ý chia sẻ, lúc nào, mức nào) *(MS §3: chấp thuận chia sẻ là bước riêng)*;
  - phiên đã kết thúc → 409 `SESSION_ALREADY_ENDED`;
  - `expires_at` ở quá khứ → 400 `VALIDATION_ERROR`;
  - đã có quyền đang hiệu lực cho cùng `(session_id, user_id)` → 409 `FAMILY_GRANT_ALREADY_ACTIVE`.
- **R4.** `POST /api/v1/family-grants/{id}/revoke` `{reason?}` ghi `revoked_at`, `revoked_by`. Chỉ `CHARGE_NURSE` và `ADMIN` *(giả định)*. Quyền đã thu hồi hoặc đã hết hiệu lực → 409 `FAMILY_GRANT_NOT_ACTIVE`. `GET /api/v1/sessions/{id}/family-grants` cho nhân viên (không gồm `FAMILY`) xem danh sách, kể cả quyền đã hết *(giả định)*.
- **R5.** Quyền **có hiệu lực** khi và chỉ khi *(Yêu cầu người dùng 2026-11-17)*: `revoked_at IS NULL` **và** (`expires_at IS NULL` hoặc `expires_at > now`) **và** phiên còn mở (`ended_at IS NULL`) **và** tài khoản còn `is_active` với vai trò `FAMILY` (F35). Kết thúc phiên hoặc chuyển giường (F04 R12–R16) làm quyền của phiên cũ hết hiệu lực; phiên mới **không** tự nhận quyền, phải cấp lại *(giả định: chấp thuận chia sẻ gắn với phiên)*. Hiệu lực được tính lúc truy vấn bằng đồng hồ được inject (không gọi thẳng đồng hồ hệ thống trong domain) *(giả định: test được bằng đồng hồ giả)*.
- **R6.** Audit *(Yêu cầu người dùng 2026-11-17; PRD NFR08)*, `entity_type = "family_access_grant"`:
  - `family_access.grant` (after: `session_id`, `user_id`, `share_level`, `consent_note`, `expires_at`);
  - `family_access.revoke` (before/after `revoked_at`, `reason`);
  - `family_access.view`: ghi mỗi lần `FAMILY` gọi `GET /api/v1/family/grants/{id}/view` và mỗi lần mở kết nối WebSocket thành công; **không** ghi cho từng message *(giả định: đủ truy vết mà không làm phình audit)*.

**Người nhà xem gì**

- **R7.** `FAMILY` chỉ gọi được *(QA#31; Yêu cầu người dùng 2026-11-17)*:
  - `GET /api/v1/auth/me`;
  - `GET /api/v1/family/grants`: quyền đang hiệu lực của chính mình;
  - `GET /api/v1/family/grants/{id}/view`: mã giường, giờ bắt đầu phiên, `share_level`, `capture_paused`, trạng thái hiện tại đã lọc (R9);
  - `GET /api/v1/family/grants/{id}/timeline`: timeline đã lọc (R10).

  Mọi endpoint khác (tổng quan, cảnh báo, thao tác cảnh báo, timeline của nhân viên, bàn giao ca, quản lý, MJPEG `stream.mjpeg`) → 403 `FORBIDDEN`. Grant của người khác hoặc của giường/phiên khác → 403 `FORBIDDEN`; grant của chính mình nhưng đã hết hiệu lực → 403 `FAMILY_ACCESS_ENDED` *(giả định: mã riêng để UI hiện "Quyền xem đã kết thúc")*.
- **R8.** Không trả mã bệnh nhân, ghi chú bệnh nhân, tên nhân viên hay `explanation` của sự kiện cho `FAMILY` *(giả định: tối thiểu hóa dữ liệu; người nhà biết người thân qua giường)*.
- **R9.** Trạng thái hiện tại cho `FAMILY` gồm `body_state`, `observation_quality`, `activity_level`, `rest_status`, `capture_paused`, `updated_at`. **Không** gồm `face_status`, `face_signals` *(giả định: tín hiệu khuôn mặt chỉ dành cho nhân viên)*.
- **R10.** Timeline cho `FAMILY` dùng truy vấn của F22 với bộ lọc phiên = phiên của grant:
  - chỉ mục `kind = "event"` có `priority` ≥ `INFO` (bỏ `LOG`) *(giả định)*;
  - tóm tắt cảnh báo chỉ có trạng thái (ví dụ "Nhân viên đã tiếp nhận", "Đã xử lý"), không có tên người, không có `note` *(giả định)*;
  - thêm mục tạm dừng / tiếp tục thu hình lấy từ audit `session.pause` / `session.resume` (R17).
- **R11.** Mức `SKELETON`: ngoài dữ liệu của `INFO`, người nhà nhận **chỉ** keypoint 2D chuẩn hóa `[0,1]` của **người mục tiêu** (F13) và polygon Bed ROI để vẽ hình người que *(Yêu cầu người dùng 2026-11-17; MS §3; giả định: ROI không phải dữ liệu cá nhân)*. Không bao giờ có pixel ảnh, JPEG, base64 hay đường dẫn MJPEG ở bất kỳ mức nào *(QA#29; PDF §11)*. Nhiều người trong ROI hoặc không có người mục tiêu → `keypoints = null` *(QA#20)*. Worker gửi keypoint người mục tiêu qua trường tùy chọn `target_keypoints` của `POST /internal/v1/cameras/{id}/state`; API chỉ giữ bản mới nhất trong RAM *(data-model.md: trạng thái giường nằm trong RAM)*.

**WebSocket**

- **R12.** `FAMILY` dùng cùng `GET /api/v1/ws?token=` (F18). Khi kết nối, hub xác định các grant đang hiệu lực của người dùng; không có grant nào → đóng với mã **4403**, không gửi dữ liệu *(giả định: mã riêng cho "hết quyền", khác 4401 của token sai)*.
- **R13.** Lọc theo từng kết nối *(Yêu cầu người dùng 2026-11-17)*: kết nối `FAMILY` **không bao giờ** nhận các loại message của nhân viên (`event.created`, `alert.*`, `camera.status`, `bed.state`, `session.updated`). Hub chỉ gửi bản chiếu riêng:
  - `family.state` `{grant_id, body_state, observation_quality, activity_level, rest_status, capture_paused, updated_at}`;
  - `family.event` `{grant_id, time, code, priority, alert_status}` (cùng bộ lọc như R10);
  - `family.skeleton` `{grant_id, keypoints, roi_polygon, ts}`, chỉ khi `share_level = SKELETON`, tối đa ~5 lần/giây *(giả định: như A03)*;
  - `family.access_ended` `{grant_id, reason: REVOKED | EXPIRED | SESSION_ENDED | ACCOUNT_LOCKED}`.

  Mọi message chỉ thuộc phiên của grant; giường khác không được gửi. Vẫn theo quy tắc "lưu trước, phát sau" *(AGENTS.md quy tắc 7)*.
- **R14.** Hết quyền giữa chừng (thu hồi, hết hạn, phiên kết thúc, chuyển giường, tài khoản bị khóa): hub gửi `family.access_ended` rồi ngừng luồng của grant đó trong **≤ 2 giây**; nếu người dùng không còn grant nào thì đóng kết nối mã 4403 *(giả định)*. Thu hồi / kết thúc phiên / chuyển giường được báo cho hub sau commit; hết hạn được kiểm tra định kỳ (chu kỳ ≤ 1 giây) *(giả định)*.

**Tạm dừng thu hình**

> **Đã làm ở F04 (18/11/2026):** cột `paused_at`/`paused_by` (migration 0005_f04), `POST /sessions/{id}/pause`, `/resume`, audit `session.pause`/`session.resume`, mã lỗi `SESSION_ALREADY_PAUSED`/`SESSION_NOT_PAUSED`/`CAPTURE_PAUSED`, `capture_paused` trong config nội bộ, nút trên "Quản lý giường". F36 còn: `family.state`, worker dừng đọc khung, API bỏ `state`/`frame` khi tạm dừng, lọc mục timeline cho người nhà (mục tạm dừng/tiếp tục trên timeline nhân viên đã làm ở F22), nút trên màn hình chi tiết phiên.

- **R15.** Quyết định: tạm dừng thu hình là **cờ ở mức phiên**, **không** phải chế độ hiển thị thứ tư của F28 *(giả định: F28 chỉ đổi cách render khung, camera vẫn đọc và engine vẫn chạy; tạm dừng thì camera dừng đọc khung và engine dừng, áp dụng cho cả nhân viên lẫn người nhà)*. Cột mới trong `monitoring_sessions`: `paused_at` (null = không tạm dừng), `paused_by`.
- **R16.** `POST /api/v1/sessions/{id}/pause` `{reason?}` và `POST /api/v1/sessions/{id}/resume`. Quyền: `NURSE`, `CHARGE_NURSE`, `ADMIN` *(giả định: như mở/đóng phiên)*; `DOCTOR`, `FAMILY` → 403. Đang tạm dừng mà gọi pause → 409 `SESSION_ALREADY_PAUSED`; không tạm dừng mà gọi resume → 409 `SESSION_NOT_PAUSED`; phiên đã kết thúc → 409 `SESSION_ALREADY_ENDED` *(giả định mã lỗi mới)*. Kết thúc phiên hoặc chuyển giường khi đang tạm dừng là hợp lệ *(giả định)*.
- **R17.** Audit `session.pause` / `session.resume` (entity `session`). Sau commit, phát `session.updated` (nhân viên) và `family.state` với `capture_paused` (người nhà).
- **R18.** Khi tạm dừng *(MS §3; giả định cách thực hiện)*:
  - `GET /internal/v1/cameras/{id}/config` trả `capture_paused: true`; worker dừng đọc khung, dừng engine, chỉ gửi heartbeat;
  - API bỏ qua `frame` và `state` nhận được cho camera của phiên đang tạm dừng; sự kiện engine gửi tới → 409 `CAPTURE_PAUSED`;
  - UI nhân viên và người nhà hiện "Đang tạm dừng thu hình" và nói rõ hệ thống **không** quan sát trong lúc này, không hiện như "an toàn" *(PRD US07)*.
- **R19.** Tiếp tục thu hình: engine khởi động lại từ trạng thái chưa quan sát, mọi chuyển trạng thái phải giữ đủ `min_duration`; khoảng tạm dừng **không** sinh sự kiện rời giường *(AGENTS.md quy tắc 6)*.

**Giao diện**

- **R20.** Route `/family` *(Yêu cầu người dùng 2026-11-17; QA#25)*:
  - `FAMILY` đăng nhập xong được chuyển thẳng tới `/family`; mọi route khác bị chặn *(F02 R12)*;
  - hiển thị tốt từ chiều rộng 360 px *(giả định)*;
  - nội dung: mã giường, trạng thái hiện tại (câu mô tả quan sát được), dòng thời gian, nhãn "Đang tạm dừng thu hình" khi tạm dừng, hình người que nếu mức `SKELETON`;
  - nhiều grant: cho chọn; không còn grant: hiện "Quyền xem đã kết thúc";
  - mất kết nối realtime: hiện chỉ báo như F18 R13.
- **R21.** Màn hình chi tiết phiên của nhân viên: mục "Chia sẻ với người nhà" (danh sách quyền, nút "Cấp quyền xem", "Thu hồi") cho `CHARGE_NURSE`, `ADMIN`; nút "Tạm dừng thu hình" / "Tiếp tục thu hình" cho `NURSE`, `CHARGE_NURSE`, `ADMIN` *(giả định)*.
- **R22.** Text chỉ nằm trong `web/src/i18n/vi.ts`, không có từ cấm, không hiện mã nội bộ (`INFO`, `SKELETON`, `BED_EXIT`…) *(AGENTS.md quy tắc 3; glossary.md)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/schemas/enums.py`: `ShareLevel` (`INFO`, `SKELETON`); `FamilyAccessEndReason`. (`UserRole.FAMILY` có từ F35.)
  - `server/src/postcare/db/models.py` + migration: `FamilyAccessGrant`; cột `paused_at`, `paused_by` của `MonitoringSession`.
  - `server/src/postcare/domain/family_access.py` (`grant_access`, `revoke_access`, `active_grants_for_user`, `is_grant_active(grant, now)`); `domain/sessions.py` (`pause_session`, `resume_session`).
  - `server/src/postcare/api/v1/family.py`, `api/v1/family_grants.py`, `api/v1/sessions.py` (pause/resume).
  - `server/src/postcare/api/realtime.py`: bộ lọc theo kết nối (`FamilyProjection`), kiểm tra hết hạn định kỳ.
  - `server/src/postcare/worker/`: tôn trọng `capture_paused`; gửi `target_keypoints`.
  - Test: `server/tests/api/test_family_grants.py`, `test_family_access.py`, `test_family_realtime.py`, `test_session_pause.py`; `server/tests/domain/test_family_access_validity.py`.
  - Web: `web/src/pages/Family/FamilyPage.tsx`, `FamilySkeleton.tsx`, `web/src/pages/Sessions/FamilyGrantsPanel.tsx`, `PauseCaptureButton.tsx`; test `FamilyPage.test.tsx`, `FamilyGrantsPanel.test.tsx`.
- **Dữ liệu:** bảng mới `family_access_grants`; cột mới `monitoring_sessions.paused_at`, `paused_by`; ghi `audit_logs` (xem [data-model.md](../02-architecture/data-model.md#family_access_grants-f36)).
- **API:** `POST/GET /api/v1/sessions/{id}/family-grants`, `POST /api/v1/family-grants/{id}/revoke`, `GET /api/v1/family/grants`, `GET /api/v1/family/grants/{id}/view`, `GET /api/v1/family/grants/{id}/timeline`, `POST /api/v1/sessions/{id}/pause`, `.../resume`; WS `family.*`; trường `capture_paused` (config nội bộ) và `target_keypoints` (state nội bộ) (xem [api-conventions.md](../02-architecture/api-conventions.md)). Chạy `make gen-api-types`.
- **UI:** `/family`; mục "Chia sẻ với người nhà". Text cần thêm vào `vi.ts`: `family.title` ("Theo dõi người thân"), `family.bed` ("Giường"), `family.currentState` ("Trạng thái hiện tại"), `family.timeline` ("Diễn biến"), `family.accessEnded` ("Quyền xem đã kết thúc"), `family.chooseGrant` ("Chọn phiên theo dõi"), `share.title` ("Chia sẻ với người nhà"), `share.grant` ("Cấp quyền xem"), `share.revoke` ("Thu hồi"), `share.level.INFO` ("Chỉ thông tin"), `share.level.SKELETON` ("Thông tin và hình người que"), `share.consentNote` ("Ghi chú chấp thuận chia sẻ"), `share.expiresAt` ("Hết hạn lúc"), `capture.pause` ("Tạm dừng thu hình"), `capture.resume` ("Tiếp tục thu hình"), `capture.paused` ("Đang tạm dừng thu hình – hệ thống không quan sát trong lúc này"), `alertStatus.family.ACKNOWLEDGED` ("Nhân viên đã tiếp nhận"), `alertStatus.family.RESOLVED` ("Đã xử lý").
- **Cấu hình:** không có khóa engine. Chu kỳ kiểm tra hết hạn và giới hạn tần suất `family.skeleton` là hằng số của API *(giả định: không phải ngưỡng engine)*.

## 5. Acceptance criteria

- [ ] **AC1.** `CHARGE_NURSE`/`ADMIN` cấp được quyền `INFO` (mặc định) hoặc `SKELETON` cho tài khoản `FAMILY` trên phiên đang mở, có `consent_note`; thu hồi được; mỗi thao tác ghi audit `family_access.grant` / `family_access.revoke`; mỗi lần xem ghi `family_access.view`. `NURSE`, `DOCTOR`, `FAMILY` cấp/thu hồi → 403; cấp cho tài khoản không phải `FAMILY` → 400; cấp trùng → 409 `FAMILY_GRANT_ALREADY_ACTIVE`. *(QA#31; MS §3)* — *Kiểm chứng:* test `test_grant_default_level_info`, `test_grant_and_revoke_audited`, `test_grant_requires_charge_nurse_or_admin` (tham số hóa vai trò), `test_grant_to_non_family_user_400`, `test_duplicate_active_grant_409`, `test_family_view_audited_once_per_request`.
- [ ] **AC2.** `FAMILY` chỉ thấy phiên được cấp: endpoint nhân viên và grant/giường khác → 403; khi có sự kiện ở giường khác, kết nối WS của `FAMILY` **không** nhận message nào về giường đó và không nhận loại message của nhân viên. *(QA#31)* — *Kiểm chứng:* test `test_family_forbidden_on_staff_endpoints` (tham số hóa `/overview`, `/alerts`, `/alerts/{id}/acknowledge`, `/timeline`, `/handover`, `/beds`, `/cameras/{id}/stream.mjpeg`), `test_family_other_grant_403`, `test_family_ws_not_delivered_other_bed`, `test_family_ws_receives_only_family_types`.
- [ ] **AC3.** Thu hồi giữa chừng: kết nối WS đang nhận luồng nhận `family.access_ended` (`REVOKED`) và bị đóng mã 4403 trong ≤ 2 giây; quyền hết hạn (đồng hồ giả) cũng vậy với `EXPIRED`; sau đó `GET /family/grants/{id}/view` → 403 `FAMILY_ACCESS_ENDED`. *(Yêu cầu người dùng 2026-11-17)* — *Kiểm chứng:* test `test_family_ws_revoked_mid_stream_closes_within_2s`, `test_family_ws_expired_grant_closes`, `test_family_view_after_revoke_403`.
- [ ] **AC4.** Kết thúc phiên hoặc chuyển giường (F04) làm quyền của phiên cũ hết hiệu lực: luồng WS nhận `SESSION_ENDED`; phiên mới sau khi chuyển **không** xem được nếu chưa cấp lại. *(Yêu cầu người dùng 2026-11-17)* — *Kiểm chứng:* test `test_grant_ends_when_session_ends`, `test_old_session_grant_invalid_after_transfer`, `test_new_session_after_transfer_requires_new_grant`.
- [ ] **AC5.** Mức `SKELETON` chỉ có keypoint của người mục tiêu và ROI, không có ảnh: mọi message WS và response REST gửi cho `FAMILY` (cả hai mức) không chứa JPEG, base64 hay URL MJPEG; mức `INFO` không nhận `family.skeleton`; nhiều người trong ROI → `keypoints = null`. *(QA#29; MS §3)* — *Kiểm chứng:* test `test_family_skeleton_has_no_jpeg` (kiểm tra payload chỉ gồm số và khóa cho phép, không có byte `FF D8`, không có chuỗi `data:image`/`stream.mjpeg`), `test_info_level_gets_no_skeleton`, `test_skeleton_null_when_multiple_people`.
- [ ] **AC6.** Tạm dừng thu hình: `NURSE`/`CHARGE_NURSE`/`ADMIN` tạm dừng và tiếp tục được (audit `session.pause`/`session.resume`); config nội bộ trả `capture_paused: true`; sự kiện engine trong lúc tạm dừng → 409 `CAPTURE_PAUSED`; người nhà và nhân viên thấy "Đang tạm dừng thu hình"; tạm dừng hai lần → 409 `SESSION_ALREADY_PAUSED`; `DOCTOR`/`FAMILY` → 403. *(MS §3; PRD US07)* — *Kiểm chứng:* test `test_pause_resume_audited`, `test_internal_config_reports_capture_paused`, `test_engine_event_rejected_while_paused`, `test_pause_twice_409`, `test_pause_forbidden_for_doctor_and_family`; component test `FamilyPage shows paused state`, `FamilyPage shows access ended`; `vi.test.ts` quét từ cấm.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | Cấp/thu hồi theo vai trò; audit grant/revoke/view | NURSE/DOCTOR/FAMILY → 403; user không phải FAMILY → 400; cấp trùng → 409; phiên đã đóng → 409 `SESSION_ALREADY_ENDED`; thu hồi lần hai → 409 `FAMILY_GRANT_NOT_ACTIVE` |
| AC1 | domain | `test_family_access_validity.py`: bảng chân trị R5 với đồng hồ giả | `expires_at` = now → không hiệu lực; tài khoản bị khóa → không hiệu lực |
| AC2 | API + WS | Hai giường, hai phiên; FAMILY có grant ở A01; phát sự kiện ở A02 | FAMILY không nhận gì về A02; endpoint nhân viên → 403 |
| AC3 | WS (TestClient, đồng hồ giả) | Thu hồi bằng request khác khi đang nhận luồng; đo tới lúc đóng | Thu hồi grant A không ngắt grant B còn hiệu lực của cùng người |
| AC4 | API + WS | Kết thúc phiên; gọi chuyển giường của F04 | Grant phiên cũ không chuyển sang phiên mới |
| AC5 | API + WS | Quét payload gửi cho FAMILY | INFO không có `family.skeleton`; MJPEG → 403 |
| AC6 | API + component | Pause/resume, config nội bộ, sự kiện bị từ chối; `FamilyPage.test.tsx` | Resume khi không tạm dừng → 409 `SESSION_NOT_PAUSED`; tạm dừng không sinh sự kiện rời giường |
| — | thủ công | Mở `/family` trên điện thoại qua LAN (360 px); thu hồi từ laptop, điện thoại báo hết quyền | — |

## 7. Giả định

- *(giả định)* `CHARGE_NURSE` và `ADMIN` cấp/thu hồi quyền; `NURSE`, `CHARGE_NURSE`, `ADMIN` tạm dừng/tiếp tục thu hình.
- *(giả định)* Unique `(session_id, user_id) WHERE revoked_at IS NULL`; `consent_note` bắt buộc.
- *(giả định)* Quyền gắn với phiên; chuyển giường phải cấp lại cho phiên mới.
- *(giả định)* Mã đóng WS 4403; ngắt luồng ≤ 2 giây; kiểm tra hết hạn chu kỳ ≤ 1 giây.
- *(giả định)* Mã lỗi mới: `FAMILY_GRANT_ALREADY_ACTIVE`, `FAMILY_GRANT_NOT_ACTIVE` (409), `FAMILY_ACCESS_ENDED` (403), `SESSION_ALREADY_PAUSED`, `SESSION_NOT_PAUSED`, `CAPTURE_PAUSED` (409).
- *(giả định)* Người nhà không thấy mã bệnh nhân, tên nhân viên, `note`, `explanation`, tín hiệu khuôn mặt; timeline chỉ sự kiện ≥ `INFO`.
- *(giả định)* Tạm dừng là cờ ở mức phiên (`paused_at`, `paused_by`), không phải chế độ hiển thị F28; lịch sử tạm dừng lấy từ audit.
- *(giả định)* Mức `SKELETON` có thêm polygon Bed ROI; tần suất ~5 lần/giây.
- *(giả định)* `family_access.view` ghi theo request `view` và theo lần kết nối WS, không theo message.
- *(giả định)* `/family` hiển thị tốt từ 360 px.

## 8. Câu hỏi mở

- Người nhà có nên thấy sự kiện "biểu hiện khuôn mặt cần kiểm tra" và "chuyển động bất thường - đề nghị kiểm tra" không, hay chỉ sự kiện tư thế/vị trí? Mặc định: mọi sự kiện ≥ `INFO`. **Không chặn.**
- Người nhà có được tự yêu cầu tạm dừng trên `/family` không? Mặc định: không, nhân viên thao tác theo yêu cầu. **Không chặn.**
- F21 (thẻ giường) cần hiển thị trạng thái "Đang tạm dừng thu hình" (F22 đã có mục tạm dừng/tiếp tục trên timeline nhân viên, 18/11/2026); F18 R2 ("mọi vai trò nhận cùng luồng") cần sửa thành "mọi vai trò nhân viên". Cập nhật các spec đó khi triển khai F36 hoặc trước. **Không chặn.**
- Có giới hạn thời lượng tạm dừng tối đa hoặc nhắc tiếp tục không? Mặc định: không. **Không chặn.**

## 9. Kế hoạch triển khai

> Lập 18/11/2026. Pause/resume, `paused_at`, `capture_paused`, audit `session.pause/resume`, nút trên "Quản lý giường" và worker dừng đọc khung đã có (F04, worker F06). F36 làm phần còn lại.

**Code dùng lại:** `api/realtime.py` (`WsHub`, `Connection`, `close_where`, `disconnect_user`), `api/deps.py` (`require_roles`, `STAFF_ROLES`), `domain/sessions.py` (phát `session.updated` sau commit; chuyển giường phát phiên cũ trước), `domain/timeline.py` (`_query`, `_build`), `domain/cameras.py::update_bed_state`, `domain/runtime.py` (`RuntimeStore`), `worker/loop.py` (`capture_paused`, `PAUSED`), `Engine.peek_target`, MJPEG `staff_from_token` (FAMILY đã 403).

**Thiết kế chính**

- *Hiệu lực quyền (R5):* hàm thuần `grant_end_reason(grant, now)` trong `domain/family_access.py`, trả `None` khi còn hiệu lực, nếu không trả lý do theo thứ tự `REVOKED`, `SESSION_ENDED`, `ACCOUNT_LOCKED` (tài khoản khóa hoặc không còn vai trò `FAMILY`), `EXPIRED` (`expires_at <= now`). `now` lấy từ `app.state.clock` (mặc định `utcnow`; test thay bằng đồng hồ giả).
- *Cấp lại khi quyền cũ đã hết hạn nhưng chưa thu hồi:* partial unique chặn insert, nên lúc cấp hệ thống đóng quyền đã hết hạn (`revoked_at = now`, `revoked_by = null`, audit `family_access.revoke` actor hệ thống, `reason = "EXPIRED"`) rồi mới tạo quyền mới *(giả định)*.
- *WebSocket:* `Connection` thêm `project(message) -> list[message]` (bản chiếu theo kết nối). Kết nối `FAMILY` dùng `FamilyProjection` (`api/family_stream.py`) giữ các grant đang hiệu lực (grant_id, session_id, bed_id, share_level, expires_at, trạng thái gần nhất, `capture_paused`, ROI). Bản chiếu dịch message nhân viên thành `family.*`:
  - `event.created` / `alert.updated` → `family.event` (bỏ `LOG`);
  - `bed.state` → `family.state` (bỏ `face_*`);
  - `session.updated` → `family.state` (tạm dừng/tiếp tục) hoặc `family.access_ended` `SESSION_ENDED` (kết thúc, chuyển giường);
  - message nội bộ `bed.skeleton` → `family.skeleton` (chỉ mức `SKELETON`, ≤ 5 lần/giây);
  - message nội bộ `family.grant_ended` (phát sau commit thu hồi) → `family.access_ended` `REVOKED`.

  Hết grant cuối → đóng 4403 (message `access_ended` được gửi trước lệnh đóng). Kết nối nhân viên có bộ lọc bỏ `bed.skeleton`, `family.*`. Mỗi kết nối `FAMILY` có task kiểm tra hết hạn mỗi 0,5 s. `disconnect_user` với kết nối `FAMILY` gửi `access_ended` `ACCOUNT_LOCKED` trước khi đóng. Đổi vai trò khỏi `FAMILY` cũng đóng kết nối (4403).
- *Keypoint:* `BedStateIn.target_keypoints: dict[KeypointName, [x, y, visibility]] | None` (tùy chọn). API giữ bản mới nhất trong `RuntimeStore`, phát `bed.skeleton` nội bộ khi request có trường này. Request có `target_keypoints`: `bed.state` cho nhân viên chỉ phát khi trạng thái đổi hoặc đã ≥ 4 s từ lần phát trước (request không có trường này giữ hành vi cũ). Worker gửi state kèm keypoint của người mục tiêu (`Engine.peek_target`) theo nhịp khung (~5 lần/giây); `MULTIPLE_PEOPLE` / `NO_OBSERVATION` → `null`.
- *Tạm dừng (R18):* API bỏ `state` và `frame` khi phiên của camera đang tạm dừng (không lưu, không phát).
- *Timeline người nhà:* `timeline.family_session_timeline` dùng `_query` của F22 (`session_ids=[grant.session_id]`, không nối chuỗi, priority ≥ `INFO`), chỉ giữ `kind = event` và `session.pause` / `session.resume`; domain chiếu sang `FamilyTimelineItemOut {time, kind: event|capture_paused|capture_resumed, event_id, code, priority, alert_status}`.
- *Chọn tài khoản người nhà:* `/users` chỉ ADMIN nên thêm `GET /api/v1/family-grants/accounts` (CHARGE_NURSE, ADMIN) trả `{id, username, full_name}` của tài khoản `FAMILY` đang dùng *(giả định: Phụ trách ca cần chọn người nhận quyền)*.
- `family.event` có thêm `event_id` để web cập nhật trạng thái cảnh báo của cùng mục *(giả định)*.

**Các bước**

1. Spec plan, trạng thái In progress (commit `docs(F36): plan`).
2. Test trước (đỏ đúng lý do), commit `test(F36): ...`:
   - `server/tests/domain/test_family_access_validity.py`: bảng chân trị R5 (đồng hồ giả; `expires_at == now` hết hiệu lực; khóa tài khoản; đổi vai trò).
   - `server/tests/api/test_family_grants.py` (AC1): `test_grant_default_level_info`, `test_grant_and_revoke_audited`, `test_grant_requires_charge_nurse_or_admin[nurse|doctor|family]`, `test_revoke_requires_charge_nurse_or_admin`, `test_grant_to_non_family_user_400`, `test_grant_requires_consent_note`, `test_grant_expires_in_past_400`, `test_grant_on_ended_session_409`, `test_duplicate_active_grant_409`, `test_revoke_twice_409`, `test_regrant_after_expiry`, `test_list_grants_staff_only`, `test_family_accounts_list`.
   - `server/tests/api/test_family_access.py` (AC2–AC6, REST): `test_family_forbidden_on_staff_endpoints` (tham số hóa), `test_family_other_grant_403`, `test_family_view_audited_once_per_request`, `test_family_view_after_revoke_403`, `test_family_view_expired_403`, `test_grant_ends_when_session_ends`, `test_old_session_grant_invalid_after_transfer`, `test_new_session_after_transfer_requires_new_grant`, `test_family_view_has_no_patient_or_face`, `test_family_timeline_filtered`, `test_family_view_shows_paused`, `test_state_and_frame_ignored_while_paused`, `test_skeleton_level_view_has_keypoints_info_does_not`, `test_family_rest_payloads_have_no_image`.
   - `server/tests/api/test_family_realtime.py`: `test_family_ws_without_grant_closes_4403`, `test_family_ws_not_delivered_other_bed`, `test_family_ws_receives_only_family_types`, `test_family_ws_revoked_mid_stream_closes_within_2s`, `test_revoke_one_grant_keeps_other`, `test_family_ws_expired_grant_closes`, `test_family_ws_session_end_sends_session_ended`, `test_family_ws_transfer_ends_grant`, `test_family_skeleton_has_no_jpeg`, `test_info_level_gets_no_skeleton`, `test_skeleton_null_when_multiple_people`, `test_family_ws_paused_state`, `test_family_ws_account_locked`, `test_staff_ws_never_gets_family_messages`, `test_family_ws_view_audited_on_connect`.
   - `server/tests/worker/test_worker_family_keypoints.py`: worker gửi `target_keypoints` của người mục tiêu; nhiều người → `null`.
3. Enum `ShareLevel`, `FamilyAccessEndReason` (`schemas/enums.py`); model `FamilyAccessGrant`; migration `0007_f36` (enum `share_level`, bảng, partial unique) nối sau `0006`; cập nhật `test_enums_match.py`.
4. Domain `domain/family_access.py` + DTO; router `api/v1/family_grants.py` (nhân viên), `api/v1/family.py` (người nhà, guard `require_family`); `app.state.clock`.
5. Hub: `project` trên `Connection`, `api/family_stream.py`, nhánh `FAMILY` trong `websocket_endpoint`, kiểm tra hết hạn; `api/v1/users.py` đóng kết nối khi vai trò rời `FAMILY`.
6. Keypoint: `BedStateIn.target_keypoints`, skeleton trong `RuntimeStore`, `bed.skeleton`; bỏ state/frame khi tạm dừng; worker gửi keypoint.
7. Web: `make gen-api-types`; hook người nhà trong `api/family.ts`; `pages/Family/FamilyPage.tsx`, `FamilySkeleton.tsx` (canvas trống, chỉ vẽ từ keypoint + ROI), luồng realtime riêng (dùng `wsClient`, 4403 → "Quyền xem đã kết thúc"); `pages/Management/FamilyGrantsPanel.tsx` (modal từ "Quản lý giường", chỉ CHARGE_NURSE/ADMIN); text trong `vi.ts`; test `FamilyPage.test.tsx` (`shows paused state`, `shows access ended`, `draws skeleton only at skeleton level`), `FamilyGrantsPanel.test.tsx`; bỏ `FamilyPlaceholder.tsx`.
8. Docs: `api-conventions.md` (endpoint accounts, `event_id` trong `family.event`), `data-model.md` (migration `0007_f36`), spec §10.
9. `make check`; kiểm chứng thủ công (DB `postcare_f36`, API cổng 8036, `postcare simulate`, client websockets Python).

**Rủi ro:** test WS có giới hạn thời gian (≤ 2 s) → dùng hub thật trong TestClient, đo bằng `time.monotonic`. Worker gửi state ~5 lần/giây tăng tải API → `bed.state` cho nhân viên vẫn chỉ phát khi đổi.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
