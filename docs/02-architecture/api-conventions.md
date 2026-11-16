# Quy ước API

## Chung

| Mục | Quy ước |
|---|---|
| Tiền tố | API công khai: `/api/v1/...`. API nội bộ cho worker: `/internal/v1/...` |
| Định dạng | JSON, khóa `snake_case`, UTF-8 |
| Thời gian | ISO 8601 có múi giờ, lưu và trả về UTC (ví dụ `2026-10-12T07:38:34Z`) |
| ID | Số nguyên (`id`). Riêng `event_uid` là UUID |
| Enum | Chuỗi IN HOA, khớp `postcare.schemas` (ví dụ `"BED_EXIT"`, `"HIGH"`) |
| Phân trang | `?limit=50&offset=0`; trả `{ "items": [...], "total": n }`. `limit` tối đa 200 |
| Lọc thời gian | `?from=...&to=...` (ISO 8601) |
| Text hiển thị | API **không** trả câu tiếng Việt cho sự kiện. Frontend ánh xạ mã → câu bằng `web/src/i18n/vi.ts` |
| OpenAPI | FastAPI tự sinh tại `/api/openapi.json`. Frontend sinh type bằng `make gen-api-types` → `web/src/api/schema.d.ts` (không sửa tay) |

## Xác thực và phân quyền

- `POST /api/v1/auth/login` `{username, password}` → `{access_token, token_type: "bearer", user: {...}}`.
- Gửi header `Authorization: Bearer <token>`. Token hết hạn sau 8 giờ *(giả định A10)*.
- WebSocket và MJPEG (không gửi được header): `?token=<jwt>`.
- Phân quyền theo vai trò:

| Hành động | NURSE | CHARGE_NURSE | DOCTOR | ADMIN |
|---|---|---|---|---|
| Xem tổng quan, cảnh báo, timeline, bàn giao ca, theo dõi trực tiếp | ✓ | ✓ | ✓ | ✓ |
| Tiếp nhận, ghi kết quả, xử lý cảnh báo | ✓ | ✓ | ✗ | ✓ |
| Mở/đóng phiên theo dõi | ✓ | ✓ | ✗ | ✓ |
| Đổi chế độ hiển thị | ✗ | ✓ | ✗ | ✓ |
| Quản lý giường, bệnh nhân, camera, ROI, ngưỡng | ✗ | ✗ | ✗ | ✓ |

Vai trò và ma trận quyền là *(giả định QA#18)*.

## Lỗi

Mọi lỗi trả về:

```json
{ "error": { "code": "ALERT_ALREADY_ACKNOWLEDGED", "message": "Cảnh báo đã được tiếp nhận bởi Nguyễn Văn A", "details": {} } }
```

| HTTP | Khi nào | Ví dụ `code` |
|---|---|---|
| 400 | Dữ liệu sai định dạng hoặc vi phạm rule nghiệp vụ đơn giản | `VALIDATION_ERROR`, `INVALID_ROI_POLYGON` |
| 401 | Chưa đăng nhập, token sai hoặc hết hạn, worker token sai | `INVALID_CREDENTIALS`, `UNAUTHORIZED` |
| 403 | Không đủ quyền | `FORBIDDEN` |
| 404 | Không tìm thấy | `NOT_FOUND` |
| 409 | Xung đột trạng thái | `DUPLICATE_CODE`, `BED_ALREADY_HAS_CAMERA`, `SESSION_ALREADY_OPEN`, `SESSION_ALREADY_ENDED`, `NO_ACTIVE_SESSION`, `ALERT_ALREADY_ACKNOWLEDGED`, `INVALID_ALERT_TRANSITION` |
| 422 | Lỗi validation của FastAPI | Bọc lại thành `VALIDATION_ERROR` |

`message` viết tiếng Việt, dùng được để hiển thị. `code` dùng cho logic frontend.

## Danh sách endpoint dự kiến

| Method + path | Feature | Mô tả |
|---|---|---|
| `GET /api/v1/health` | F00 | `{"status":"ok"}` |
| `POST /api/v1/auth/login`, `GET /api/v1/auth/me` | F02 | Đăng nhập, thông tin người dùng hiện tại |
| `GET/POST/PATCH /api/v1/beds`, `/patients`, `/cameras` | F03 | CRUD; ngừng dùng bằng `PATCH {is_active:false}` |
| `GET /api/v1/cameras/{id}` | F03, F06 | Có khối `runtime` (`status`, `fps`, `brightness`, `last_seen_at`) cho màn hình trước khi có WebSocket |
| `PUT /api/v1/cameras/{id}/roi`, `GET/PUT /api/v1/cameras/{id}/thresholds` (GET trả cả mặc định và override), `PUT /api/v1/cameras/{id}/display-mode` | F08, F28 | Cấu hình camera |
| `POST /api/v1/sessions`, `POST /api/v1/sessions/{id}/end`, `GET /api/v1/sessions?active=true` | F04 | Phiên theo dõi |
| `GET /api/v1/cameras/{id}/stream.mjpeg?token=` | F07 | Xem trực tiếp |
| `GET /api/v1/overview` | F09, F21 | Dữ liệu thẻ giường + ca hiện tại |
| `GET /api/v1/events` | F17 | Lọc theo giường, phiên, thời gian, mức ưu tiên |
| `GET /api/v1/alerts`, `GET /api/v1/alerts/{id}` | F19, F20 | Danh sách / chi tiết |
| `POST /api/v1/alerts/{id}/acknowledge`, `.../outcome` `{outcome, note}`, `.../resolve` `{note?}` | F19 | Vòng đời cảnh báo |
| `GET /api/v1/sessions/{id}/timeline`, `GET /api/v1/timeline?bed_id&from&to` | F22 | Timeline |
| `GET /api/v1/shifts`, `GET /api/v1/handover?shift_id&date` hoặc `?from&to` | F24 | Bàn giao ca |
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
| `session.updated` | session | Khi mở/đóng phiên |

**Quy tắc:**
- Chỉ phát **sau khi commit DB** (HS §4.2).
- Khi kết nối lại, frontend refetch dữ liệu thay vì giả định không bỏ lỡ gì.
- Token sai hoặc hết hạn: server đóng kết nối với mã **4401**. Client không thử lại mà chuyển về trang đăng nhập *(giả định; F18)*.

## API nội bộ cho worker

- Xác thực bằng header `X-Worker-Token: <WORKER_TOKEN>` (biến môi trường). Sai token → 401.
- Không mở các endpoint này ra ngoài LAN.

| Method + path | Body / trả về |
|---|---|
| `GET /internal/v1/cameras/{id}/config` | → `{camera_id, bed_id, source_type, source, roi_polygon, thresholds, display_mode, config_version, active_session_id}` |
| `POST /internal/v1/cameras/{id}/heartbeat` | `{fps, brightness, dropped_frames, source_status}` → `{config_version}` (worker so sánh để tải lại cấu hình) |
| `POST /internal/v1/cameras/{id}/state` | `{body_state, observation_quality, activity_level, rest_status, face_status, face_signals, ts}` |
| `POST /internal/v1/events` | `{event_uid, camera_id, code, priority, occurred_at, detected_at, confidence, observation_quality, explanation, config_hash}` → `{id, created: bool}`; **201** khi tạo mới, **200** khi `event_uid` đã có (idempotent). Sự kiện engine mà không có phiên mở → 409 `NO_ACTIVE_SESSION` |
| `POST /internal/v1/cameras/{id}/frame` | body `image/jpeg` (đã render theo `display_mode`) → 204 |

## Quy ước code backend

- Mỗi nhóm endpoint là một router trong `postcare/api/v1/<resource>.py`. Logic nghiệp vụ nằm trong `postcare/domain/`, **không** viết trong router.
- Schema request/response đặt tên `<Resource>Create`, `<Resource>Update`, `<Resource>Out`.
- Mọi thao tác ghi có tác động nghiệp vụ (phiên, cảnh báo, cấu hình camera) đều gọi `record_audit()`.
