# Quy ước API

## Chung

| Mục | Quy ước |
|---|---|
| Tiền tố | API công khai: `/api/v1/...`. API nội bộ cho worker: `/internal/v1/...` |
| Định dạng | JSON, khóa `snake_case`, UTF-8 |
| Thời gian | ISO 8601 có múi giờ, lưu và trả về UTC (ví dụ `2026-10-12T07:38:34Z`) |
| ID | Số nguyên (`id`). Riêng `event_uid` là UUID |
| Enum | Chuỗi IN HOA, khớp `postcare.schemas` (ví dụ `"BED_EXIT"`, `"HIGH"`). Ngoại lệ: `KeypointName` viết thường (`left_shoulder`…) vì chỉ dùng trong schema quan sát và YAML, không đi qua REST |
| Phân trang | `?limit=50&offset=0`; trả `{ "items": [...], "total": n }`. `limit` tối đa 200 |
| Lọc thời gian | `?from=...&to=...` (ISO 8601) |
| Text hiển thị | API **không** trả câu tiếng Việt cho sự kiện. Frontend ánh xạ mã → câu bằng `web/src/i18n/vi.ts` |
| OpenAPI | FastAPI tự sinh tại `/api/openapi.json`. Frontend sinh type bằng `make gen-api-types` → `web/src/api/schema.d.ts` (không sửa tay) |

## Xác thực và phân quyền

- `POST /api/v1/auth/login` `{username, password}` → `{access_token, token_type: "bearer", user: {...}}`.
- Gửi header `Authorization: Bearer <token>`. Token hết hạn sau 8 giờ *(giả định A10)*.
- WebSocket và MJPEG (không gửi được header): `?token=<jwt>`.
  - Access log của uvicorn che giá trị này thành `token=***` (`postcare.api.log_redaction`, gắn trong `create_app`; dùng chung cho MJPEG F07 và WS F18). Code tự ghi log có URL kèm query cũng phải qua `redact()`.
  - Kết nối dài (MJPEG) kiểm tra lại người xem mỗi `STREAM_REVALIDATE_S` (5 s): tài khoản bị khóa, đặt lại mật khẩu (`token_version`) hoặc không còn là vai trò nhân viên → server đóng stream.
- Phân quyền theo vai trò:

| Hành động | NURSE | CHARGE_NURSE | DOCTOR | ADMIN | FAMILY |
|---|---|---|---|---|---|
| Xem tổng quan, cảnh báo, timeline, bàn giao ca, theo dõi trực tiếp (MJPEG), danh mục (giường, bệnh nhân, camera, khu vực, ca, phiên) | ✓ | ✓ | ✓ | ✓ | ✗ |
| Tiếp nhận, ghi kết quả, xử lý cảnh báo | ✓ | ✓ | ✗ | ✓ | ✗ |
| Mở/đóng phiên theo dõi, chuyển giường (F04) | ✓ | ✓ | ✗ | ✓ | ✗ |
| Tạm dừng / tiếp tục thu hình (F04, F36) | ✓ | ✓ | ✗ | ✓ | ✗ |
| Đổi chế độ hiển thị | ✗ | ✓ | ✗ | ✓ | ✗ |
| Cấp / thu hồi quyền xem của người nhà (F36) | ✗ | ✓ | ✗ | ✓ | ✗ |
| Quản lý (thêm, sửa, xóa mềm, khôi phục) giường, bệnh nhân, camera, ROI, ngưỡng (F03, F08) | ✗ | ✗ | ✗ | ✓ | ✗ |
| Quản lý khu vực, ca trực (F37) | ✗ | ✗ | ✗ | ✓ | ✗ |
| Quản lý người dùng: tạo, sửa, khóa/mở khóa, đặt lại mật khẩu (F35) | ✗ | ✗ | ✗ | ✓ | ✗ |
| Xem phiên được cấp quyền, ở mức chia sẻ đã đồng ý (`/api/v1/family/...`, WS `family.*`) (F36) | ✗ | ✗ | ✗ | ✗ | ✓ |

Vai trò và ma trận quyền là *(giả định QA#18)*; cột `FAMILY` theo QA#31 (F35, F36).

- "Vai trò nhân viên" = `NURSE`, `CHARGE_NURSE`, `DOCTOR`, `ADMIN`. Endpoint đọc của nhân viên dùng guard `require_staff` (F35); `FAMILY` gọi vào → 403 `FORBIDDEN`.
- `FAMILY` chỉ gọi được `POST /auth/login`, `GET /auth/me` và `/api/v1/family/...`.
- Vai trò và `is_active` đọc từ DB ở mỗi request, không tin `role` trong JWT (F35 R9). JWT mang `tv` = `users.token_version`; đặt lại mật khẩu tăng giá trị này nên mọi token cũ → 401 `UNAUTHORIZED` (F35).

## Lỗi

Mọi lỗi trả về:

```json
{ "error": { "code": "ALERT_ALREADY_ACKNOWLEDGED", "message": "Cảnh báo đã được tiếp nhận bởi Nguyễn Văn A", "details": {} } }
```

| HTTP | Khi nào | Ví dụ `code` |
|---|---|---|
| 400 | Dữ liệu sai định dạng hoặc vi phạm rule nghiệp vụ đơn giản | `VALIDATION_ERROR`, `INVALID_ROI_POLYGON` |
| 401 | Chưa đăng nhập, token sai hoặc hết hạn, worker token sai | `INVALID_CREDENTIALS`, `UNAUTHORIZED` |
| 403 | Không đủ quyền | `FORBIDDEN`, `FAMILY_ACCESS_ENDED` (F36: quyền xem của chính người nhà đã hết hiệu lực) |
| 404 | Không tìm thấy | `NOT_FOUND` |
| 409 | Xung đột trạng thái | `DUPLICATE_CODE`, `BED_ALREADY_HAS_CAMERA`, `SESSION_ALREADY_OPEN`, `SESSION_ALREADY_ENDED`, `NO_ACTIVE_SESSION`, `ALERT_ALREADY_ACKNOWLEDGED`, `INVALID_ALERT_TRANSITION`, và các mã bên dưới |
| 422 | Lỗi validation của FastAPI | Bọc lại thành `VALIDATION_ERROR` |

Mã 409 thêm ngày 17/11/2026 (đều *(giả định)*):

| `code` | Feature | Khi nào |
|---|---|---|
| `BED_HAS_OPEN_SESSION` | F03 | Xóa giường đang có phiên mở |
| `PATIENT_HAS_OPEN_SESSION` | F03 | Xóa bệnh nhân đang có phiên mở |
| `CAMERA_IN_ACTIVE_SESSION` | F03 | Xóa camera là `camera_id` của phiên đang mở |
| `AREA_IN_USE` | F37 | Xóa khu vực còn giường đang dùng; `details.bed_ids` |
| `SHIFT_OVERLAP` | F37 | Tạo/sửa/khôi phục ca làm chồng giờ ca đang dùng |
| `CANNOT_MODIFY_SELF` | F35 | ADMIN tự khóa hoặc tự hạ vai trò |
| `LAST_ADMIN` | F35 | Khóa hoặc hạ vai trò ADMIN cuối cùng đang hoạt động |
| `FAMILY_GRANT_ALREADY_ACTIVE` | F36 | Đã có quyền xem đang hiệu lực cho cùng người nhà, cùng phiên |
| `FAMILY_GRANT_NOT_ACTIVE` | F36 | Thu hồi quyền đã thu hồi hoặc đã hết hiệu lực |
| `SESSION_ALREADY_PAUSED` / `SESSION_NOT_PAUSED` | F04 | Tạm dừng khi đang tạm dừng / tiếp tục khi không tạm dừng |
| `CAPTURE_PAUSED` | F04 | Worker gửi sự kiện engine (xảy ra từ lúc `paused_at`) cho phiên đang tạm dừng thu hình |

Trùng `username` (F35) dùng lại `DUPLICATE_CODE` với `details.field = "username"`. Sai định dạng `username` (3–64 ký tự `[a-z0-9._-]` sau khi bỏ khoảng trắng và chuyển chữ thường), mật khẩu dưới 8 ký tự, vai trò lạ hoặc trường thừa → 422 `VALIDATION_ERROR`. Khi một thao tác vừa là tự khóa vừa là khóa ADMIN cuối cùng, trả `LAST_ADMIN`.

`message` viết tiếng Việt, dùng được để hiển thị. `code` dùng cho logic frontend.

## Danh sách endpoint dự kiến

| Method + path | Feature | Mô tả |
|---|---|---|
| `GET /api/v1/health` | F00 | `{"status":"ok"}` |
| `POST /api/v1/auth/login`, `GET /api/v1/auth/me` | F02 | Đăng nhập, thông tin người dùng hiện tại |
| `GET/POST /api/v1/beds`, `GET/PATCH/DELETE /api/v1/beds/{id}`, `POST /api/v1/beds/{id}/restore`; tương tự `/patients`, `/cameras` | F03 | CRUD; `DELETE` là xóa mềm (`is_active = false`), `restore` khôi phục (QA#36). `PATCH` không nhận `is_active`. Danh sách có `?include_inactive=true` |
| `GET/POST /api/v1/areas`, `GET/PATCH/DELETE /api/v1/areas/{id}`, `POST /api/v1/areas/{id}/restore` | F37 | Khu vực `{id, code, name, is_active, created_at, bed_count}`; xóa mềm, khôi phục; danh sách `{items,total}`, `?include_inactive&limit&offset`. Giường: `BedCreate`/`BedUpdate` nhận `area_id`, `BedOut.area = {id, code, name}`; khu vực đã xóa hoặc không tồn tại → 400 `VALIDATION_ERROR` (`details.field = "area_id"`). `OverviewBedOut.area` vẫn là tên khu vực (chuỗi) |
| `POST /api/v1/shifts` `{name, start_time, end_time}`, `PATCH/DELETE /api/v1/shifts/{id}`, `POST /api/v1/shifts/{id}/restore` | F37 | Ca trực; giờ `HH:mm` (giây ≠ 0 hoặc `start_time = end_time` → 400 `VALIDATION_ERROR`); chồng giờ ca đang dùng theo `[start, end)` trên vòng 24 giờ → 409 `SHIFT_OVERLAP` `details.conflicting_shift_ids`; trùng tên ca đang dùng → 409 `DUPLICATE_CODE` `details.field = "name"`. `ShiftOut` có `is_active` |
| `GET/POST /api/v1/users`, `GET/PATCH /api/v1/users/{id}`, `POST /api/v1/users/{id}/lock`, `.../unlock`, `.../reset-password` | F35 | Quản lý người dùng (chỉ ADMIN) |
| `GET /api/v1/cameras/{id}` | F03, F06, F07 | Có `roi_polygon` (Bed ROI chuẩn hóa 0–1 hoặc `null`; F07 vẽ đè trên ảnh) và khối `runtime: {fps, brightness, dropped_frames, source_status, updated_at}` từ heartbeat gần nhất (chỉ trong RAM; `null` khi chưa có heartbeat từ lúc API khởi động); `status`, `last_seen_at` ở cấp camera. Danh sách `GET /cameras` không có `runtime`, `roi_polygon` |
| `PUT /api/v1/cameras/{id}/roi`, `GET/PUT /api/v1/cameras/{id}/thresholds` (GET trả cả mặc định và override), `PUT /api/v1/cameras/{id}/display-mode` | F08, F28 | Cấu hình camera |
| `POST /api/v1/sessions`, `POST /api/v1/sessions/{id}/end`, `GET /api/v1/sessions?active=true`, `GET /api/v1/sessions/{id}` | F04 | Phiên theo dõi |
| `POST /api/v1/sessions/{id}/transfer` `{target_bed_id, reason}` → 201 phiên mới, `GET /api/v1/sessions/{id}/chain` → `{items:[{id, bed_id, bed_code, started_at, ended_at, previous_session_id, transfer_reason}], total}` | F04 | Chuyển giường trong một transaction; chuỗi phiên liên kết qua `previous_session_id`. `SessionOut` có `previous_session_id`, `previous_bed_code`, `next_session_id`, `transfer_reason`, `paused_at`, `paused_by` |
| `POST /api/v1/sessions/{id}/pause` `{reason?}`, `POST /api/v1/sessions/{id}/resume` | F04 | Tạm dừng / tiếp tục thu hình theo phiên (phần người nhà và worker ở F36) |
| `GET/POST /api/v1/sessions/{id}/family-grants`, `POST /api/v1/family-grants/{id}/revoke` | F36 | Cấp / thu hồi quyền xem của người nhà |
| `GET /api/v1/family/grants`, `GET /api/v1/family/grants/{id}/view`, `GET /api/v1/family/grants/{id}/timeline` | F36 | Chỉ `FAMILY`; dữ liệu đã lọc theo mức chia sẻ |
| `GET /api/v1/cameras/{id}/stream.mjpeg?token=` | F07 | Xem trực tiếp. `multipart/x-mixed-replace; boundary=frame`, `Cache-Control: no-store`. Token chỉ đọc từ query (header `Authorization` không dùng); thiếu/sai/hết hạn → 401; chỉ vai trò nhân viên, `FAMILY` → 403. Camera không tồn tại/ngừng dùng → 404; chưa có khung hoặc khung mới nhất cũ hơn `STREAM_STALE_FRAME_S` (3 s) → 404 `NOT_FOUND`, không gửi byte ảnh. Mỗi khung mới trong bộ đệm RAM (F06) gửi đúng một lần; không có khung mới quá `STREAM_STALE_FRAME_S` → server đóng stream. API chỉ chuyển tiếp JPEG worker gửi (đã render theo `display_mode` từ F28) |
| `GET /api/v1/overview` | F09, F21 | Dữ liệu thẻ giường + ca hiện tại |
| `GET /api/v1/events` | F17 | Lọc theo giường, phiên, thời gian, mức ưu tiên |
| `GET /api/v1/alerts`, `GET /api/v1/alerts/{id}` | F19, F20 | Danh sách / chi tiết |
| `POST /api/v1/alerts/{id}/acknowledge`, `.../outcome` `{outcome, note}`, `.../resolve` `{note?}` | F19 | Vòng đời cảnh báo |
| `GET /api/v1/sessions/{id}/timeline`, `GET /api/v1/timeline?bed_id&from&to` | F22 | Timeline |
| `GET /api/v1/shifts?include_inactive`, `GET /api/v1/handover?shift_id&date` hoặc `?from&to` | F24, F37 | `GET /shifts` trả mảng (không phân trang), mặc định chỉ ca đang dùng, sắp theo `start_time`. Bàn giao ca (ca đã xóa vẫn tra cứu được); "ca hiện tại" của tổng quan chỉ xét ca đang dùng |
| `GET /api/v1/ws?token=` | F18 | WebSocket |

## WebSocket

- Một kết nối cho mỗi tab. Server → client: `{ "type": "<loại>", "payload": {...}, "sent_at": "<ISO>" }`.
- Client → server: chỉ gửi `{"type":"ping"}` để giữ kết nối.

| `type` | Payload | Phát khi |
|---|---|---|
| `event.created` | event (như `GET /events`) | Sau khi commit event |
| `alert.created` | alert + event | Sau khi commit alert |
| `alert.updated` | alert | Sau mỗi thao tác vòng đời |
| `camera.status` | `{camera_id, bed_id, status, fps, brightness}` | Khi trạng thái camera đổi |
| `bed.state` | `{bed_id, body_state, observation_quality, activity_level (LOW/NORMAL/HIGH/UNKNOWN), rest_status, face_status, face_signals, updated_at}` | Khi worker báo trạng thái đổi |
| `session.updated` | session | Khi mở/đóng phiên, chuyển giường (cả hai phiên), tạm dừng/tiếp tục thu hình |

Các loại trên chỉ gửi cho kết nối của **vai trò nhân viên**. Kết nối của `FAMILY` (F36) chỉ nhận bản chiếu riêng, lọc theo quyền xem đang hiệu lực của chính người đó:

| `type` | Payload | Phát khi |
|---|---|---|
| `family.state` | `{grant_id, body_state, observation_quality, activity_level, rest_status, capture_paused, updated_at}` (không có `face_*`) | Trạng thái giường của phiên được cấp quyền đổi, hoặc tạm dừng/tiếp tục |
| `family.event` | `{grant_id, time, code, priority, alert_status}` (chỉ `priority` ≥ `INFO`, không tên người, không `note`/`explanation`) | Sau khi commit event của phiên được cấp quyền |
| `family.skeleton` | `{grant_id, keypoints, roi_polygon, ts}` (keypoint chuẩn hóa của người mục tiêu; `null` khi không xác định được) | Chỉ khi `share_level = SKELETON`; tối đa ~5 lần/giây. **Không bao giờ** có ảnh/JPEG |
| `family.access_ended` | `{grant_id, reason: REVOKED \| EXPIRED \| SESSION_ENDED \| ACCOUNT_LOCKED}` | Quyền hết hiệu lực; luồng của grant dừng trong ≤ 2 giây |

**Quy tắc:**
- Chỉ phát **sau khi commit DB** (HS §4.2).
- Khi kết nối lại, frontend refetch dữ liệu thay vì giả định không bỏ lỡ gì.
- Token sai hoặc hết hạn: server đóng kết nối với mã **4401**. Client không thử lại mà chuyển về trang đăng nhập *(giả định; F18)*. Tài khoản bị khóa hoặc được đặt lại mật khẩu (F35): đóng các kết nối đang mở với mã 4401. Đổi vai trò từ nhân viên sang vai trò khác (ví dụ `FAMILY`): đóng luồng nhân viên với mã 4403.
- Trước F36, mọi kết nối của `FAMILY` vào `/api/v1/ws` bị đóng mã **4403** ngay sau khi xác thực (F35 R2).
- `FAMILY` không còn quyền xem nào đang hiệu lực (lúc kết nối hoặc giữa chừng): đóng với mã **4403** *(giả định; F36)*. Lọc theo từng kết nối; không bao giờ gửi dữ liệu của giường/phiên khác cho `FAMILY`.

## API nội bộ cho worker

- Xác thực bằng header `X-Worker-Token: <WORKER_TOKEN>` (biến môi trường). Sai token → 401.
- Không mở các endpoint này ra ngoài LAN.

| Method + path | Body / trả về |
|---|---|
| `GET /internal/v1/cameras/{id}/config` | → `{camera_id, bed_id, source_type, source, roi_polygon, thresholds, display_mode, config_version, active_session_id, capture_paused}`. `capture_paused = true` (F04; worker xử lý ở F36): worker dừng đọc khung và dừng engine, chỉ gửi heartbeat |
| `POST /internal/v1/cameras/{id}/heartbeat` | `{fps, brightness, dropped_frames, source_status}` → `{config_version}` (worker so sánh để tải lại cấu hình). `brightness`: trung bình mức xám 0–255. `source_status`: `ONLINE`, `OFFLINE` hoặc `PAUSED` (tạm dừng thu hình); `ONLINE`/`PAUSED`/không gửi → camera `ONLINE`, giá trị khác → `OFFLINE` (F06 R4). Không có heartbeat quá `CAMERA_OFFLINE_AFTER_S` (5 s) → `OFFLINE` |
| `POST /internal/v1/cameras/{id}/state` | `{body_state, observation_quality, activity_level, rest_status, face_status, face_signals, ts, target_keypoints?}`. `target_keypoints` (F36): keypoint 2D chuẩn hóa của người mục tiêu hoặc `null`; API chỉ giữ bản mới nhất trong RAM. Khi phiên đang tạm dừng thu hình, API bỏ qua |
| `POST /internal/v1/events` | `{event_uid, camera_id, code, priority, occurred_at, detected_at, confidence, observation_quality, explanation, config_hash}` → `{id, created: bool}`; **201** khi tạo mới, **200** khi `event_uid` đã có (idempotent). `event_uid` không phải UUID, `code`/`priority` không khớp catalog, mã `CAMERA_*` (chỉ API sinh), camera không tồn tại hoặc chưa gắn giường → 400 `VALIDATION_ERROR`; `code` ngoài enum → 422 `VALIDATION_ERROR` (F17). Sự kiện engine mà không có phiên mở → 409 `NO_ACTIVE_SESSION`; phiên đang tạm dừng thu hình → 409 `CAPTURE_PAUSED` (F04) |
| `POST /internal/v1/cameras/{id}/frame` | body `image/jpeg` (đã render theo `display_mode`; trước F28 là RAW) → 204. Sai content-type, rỗng hoặc > `FRAME_MAX_BYTES` (2 MB) → 400 `VALIDATION_ERROR`; camera không tồn tại/ngừng dùng → 404. API chỉ giữ khung mới nhất mỗi camera trong RAM, không ghi đĩa (F06). Khi phiên đang tạm dừng thu hình, API bỏ khung (F36). Khung JPEG không bao giờ được gửi cho `FAMILY` |

## Quy ước code backend

- Mỗi nhóm endpoint là một router trong `postcare/api/v1/<resource>.py`. Logic nghiệp vụ nằm trong `postcare/domain/`, **không** viết trong router.
- Schema request/response đặt tên `<Resource>Create`, `<Resource>Update`, `<Resource>Out`.
- Mọi thao tác ghi có tác động nghiệp vụ (phiên, cảnh báo, cấu hình camera, danh mục, người dùng, quyền xem của người nhà) đều gọi `record_audit()`. `before`/`after` không bao giờ chứa mật khẩu hay hash.
- Xóa danh mục luôn là xóa mềm qua `DELETE` + khôi phục qua `POST .../restore` (QA#36). Xóa/khôi phục lặp lại trả 200, không đổi gì, không ghi audit *(giả định)*. Không có endpoint xóa cứng.

### Danh mục giường, bệnh nhân, camera (F03)

- Đọc (`GET` danh sách, chi tiết): mọi vai trò nhân viên. Ghi (`POST`, `PATCH`, `DELETE`, `POST .../restore`): chỉ `ADMIN` (guard `require_admin` trong `postcare/api/deps.py`), vai trò khác → 403 `FORBIDDEN`.
- Danh sách `GET /beds|/patients|/cameras?limit&offset&include_inactive` trả `{items, total}`; mặc định chỉ bản ghi đang dùng. Chi tiết `GET .../{id}` trả cả bản ghi đã xóa (`is_active = false`).
- Request đặt `extra="forbid"`: trường lạ (`is_active` trong `PATCH`, `full_name`/`photo` của bệnh nhân…), sai kiểu, mã rỗng → **422** `VALIDATION_ERROR` (lỗi schema của FastAPI). Lỗi nghiệp vụ → **400** `VALIDATION_ERROR` với `details.field`: `source` không hợp lệ theo `source_type` (`WEBCAM`: số nguyên ≥ 0; `URL`: `http://`, `https://`, `rtsp://`; `FILE`: không rỗng), gắn camera vào giường đã xóa, gắn giường cho camera đã xóa.
- `code` được bỏ khoảng trắng đầu/cuối rồi so trùng, kể cả với bản ghi đã xóa → 409 `DUPLICATE_CODE`, `details = {field: "code", existing_id, inactive}`; khi `inactive = true`, `message` gợi ý dùng "Khôi phục".
- Gắn camera vào giường đã có camera khác → 409 `BED_ALREADY_HAS_CAMERA`, `details.camera_id` là camera đang gắn.
- `PATCH` đổi `bed_id`, `source` hoặc `source_type` của camera là `camera_id` của phiên đang mở → 409 `CAMERA_IN_ACTIVE_SESSION` (`details.session_id`); đổi `name` vẫn được. Mở phiên (F04) khóa hàng giường và bệnh nhân (`FOR UPDATE`) nên không tranh chấp với xóa mềm.
- `DELETE` kiểm tra phiên mở trong cùng transaction (khóa hàng `FOR UPDATE`): 409 `BED_HAS_OPEN_SESSION` / `PATIENT_HAS_OPEN_SESSION` / `CAMERA_IN_ACTIVE_SESSION`, `details.session_id`. Xóa camera đặt `bed_id = null` và tăng `config_version`; khôi phục không tự gắn lại giường. Xóa giường giữ liên kết camera.
- Audit: `bed|patient|camera.create|update|delete|restore`, `before`/`after` là ảnh chụp các trường danh mục. `PATCH` không đổi gì thì không ghi audit.
