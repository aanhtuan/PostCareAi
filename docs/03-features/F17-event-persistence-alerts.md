# F17 – Lưu sự kiện và tạo cảnh báo

| Thuộc tính | Giá trị |
|---|---|
| Mã | F17 |
| Trạng thái | Done |
| Ưu tiên | MVP |
| Milestone | M2 |
| Ước lượng | 3 phiên |
| Phụ thuộc | F06, F15 |
| Nhánh code | B (backend) |
| Nguồn | PDF §5 (tr.6), §10 (tr.12), §10.1 (tr.12–13); HS §4.2, §6.2, §7.1; QA#17, QA#21; A02, A11 |

## 1. Mục tiêu

Feature này nối engine với nghiệp vụ. Worker chạy engine realtime và gửi sự kiện lên API. API **lưu sự kiện trước** (gắn phiên, giường, camera), tạo cảnh báo "Chờ tiếp nhận" cho sự kiện mức Cần chú ý / Ưu tiên cao, **rồi mới** phát cập nhật realtime (HS §4.2, §6.2; PDF §5 (tr.6)). Feature cũng sinh các sự kiện về quan sát và camera, để người dùng biết khi hệ thống không quan sát đủ (HS §7.1; QA#21). Hết feature này, sự kiện đã nằm trong DB và sẵn sàng cho realtime (F18), vòng đời cảnh báo (F19) và timeline (F22).

## 2. Phạm vi

**Trong phạm vi**
- Migration tạo bảng `events` và `alerts` theo [data-model.md](../02-architecture/data-model.md).
- Worker: chạy `Engine.process` cho mỗi frame, gửi `POST /internal/v1/events` (có `event_uid`, gửi lại an toàn) và `POST /internal/v1/cameras/{id}/state` khi trạng thái đổi.
- API nội bộ nhận sự kiện (idempotent theo `event_uid`) và nhận trạng thái (giữ bản mới nhất trong RAM).
- Domain: lưu sự kiện, gắn phiên, tạo alert `PENDING` cho MEDIUM/HIGH, gọi publisher **sau khi commit**.
- Rule engine `OBSERVATION_LOST` / `OBSERVATION_RESTORED` (`engine/rules/observation.py`, event-engine.md mục 3 bước 9 ghi ở F17).
- API sinh `CAMERA_OFFLINE` / `CAMERA_ONLINE` khi trạng thái camera đổi.
- `GET /api/v1/events` có lọc.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- WebSocket gateway và phát thật tới trình duyệt (→ F18). F17 chỉ định nghĩa interface publisher và gọi đúng thời điểm.
- Tiếp nhận, ghi kết quả, xử lý cảnh báo; `GET /api/v1/alerts` (→ F19).
- Phát hiện heartbeat quá hạn và cập nhật `cameras.status` (đã có ở F06). F17 chỉ phản ứng khi trạng thái đổi.
- Giao diện (→ F20–F22).

## 3. Yêu cầu chi tiết

**Bảng và dữ liệu**

- **R1.** Migration Alembic tạo `events`, `alerts` với cột, enum, ràng buộc, index đúng [data-model.md](../02-architecture/data-model.md): `event_uid` unique; `alerts.event_id` unique; index `(session_id, occurred_at)`, `(bed_id, occurred_at)`, `(status, created_at)`. Có `downgrade` *(PDF §10.1 (tr.12–13); HS §6.2; coding-standards.md mục 2)*.
- **R2.** Enum `event_code`, `priority`, `observation_quality`, `alert_status`, `alert_outcome` trong DB khớp enum trong `postcare.schemas` (có test so sánh) *(data-model.md, mục Quy ước)*.

**Worker**

- **R3.** Worker gọi `Engine.process(obs)` cho mỗi frame *(PDF §10 (tr.12); HS §4.2)*:
  - `state_changed = true` → `POST /internal/v1/cameras/{id}/state` *(overview.md mục 7; api-conventions.md)*.
  - Mỗi `EngineEvent` → `POST /internal/v1/events` với payload của api-conventions.md (`event_uid` UUID v4, `camera_id`, `code`, `priority`, `occurred_at`, `detected_at`, `confidence`, `observation_quality`, `explanation`, `config_hash`).
- **R4.** Đổi `ts_ms` sang thời gian UTC: worker ghi mốc đồng hồ hệ thống lúc nhận frame đầu, rồi `occurred_at = t0_utc + (ts_ms − ts0_ms)` *(giả định: engine không đọc đồng hồ, event-engine.md mục 1, nên việc quy đổi do worker làm)*.
- **R5.** Gửi lại khi lỗi mạng hoặc API trả 5xx: dùng **lại** `event_uid` cũ *(event-engine.md mục 7)*. Hàng đợi gửi lại nằm trong RAM, có giới hạn, không ghi đĩa *(giả định: kích thước hàng đợi do planner chọn; mất sự kiện khi worker tắt là chấp nhận được với prototype)*.
- **R6.** Giường **không có phiên mở** (`active_session_id = null` trong cấu hình worker): worker không gửi sự kiện của engine (tư thế, vị trí, vận động, quan sát). Chỉ có sự kiện camera do API sinh *(data-model.md: `session_id` null chỉ với sự kiện camera)*. Worker vẫn gửi `state` để màn hình Theo dõi trực tiếp hiển thị được *(giả định)*.
- **R7.** Khi `active_session_id` đổi (mở phiên mới hoặc đóng phiên), worker tạo instance `Engine` mới, để trạng thái và debounce bắt đầu lại theo phiên *(giả định: engine không biết phiên; xem F15 R8)*.

**API nội bộ**

- **R8.** `POST /internal/v1/events` yêu cầu `X-Worker-Token`. Sai token → 401 *(api-conventions.md; ADR-0002)*.
- **R9.** Idempotent theo `event_uid` *(ADR-0002; event-engine.md mục 7)*:
  - Lần đầu: lưu, trả `{id, created: true}`.
  - Gửi lại cùng `event_uid`: không tạo bản ghi, alert hay thông báo mới, trả `{id, created: false}`.
  - Dùng `INSERT … ON CONFLICT (event_uid) DO NOTHING` để an toàn cả khi hai request đến cùng lúc *(giả định: cách cài đặt)*. Mã HTTP: 201 khi tạo mới, 200 khi đã có *(giả định)*.
- **R10.** Kiểm tra payload *(api-conventions.md, mục Lỗi)*:
  - `code` thuộc catalog.
  - `priority` hợp lệ với `code` theo catalog `postcare/schemas/events.py`: `FACE_ATTENTION` nhận `MEDIUM` hoặc `HIGH`, các code khác đúng một mức *(event-engine.md mục 5)*.
  - `CAMERA_OFFLINE` / `CAMERA_ONLINE` không được nhận từ worker vì chỉ API sinh *(event-engine.md mục 5)*.
  - `camera_id` tồn tại và đã gắn giường.
  - Sai → 400 `VALIDATION_ERROR`.
- **R11.** Gắn phiên: `bed_id` lấy từ camera. `session_id` là phiên của giường đó đang mở tại `occurred_at` (`started_at ≤ occurred_at` và `ended_at` null hoặc `> occurred_at`) *(giả định: dùng thời điểm xảy ra chứ không phải thời điểm nhận, để sự kiện đến trễ vẫn gắn đúng phiên)*. Sự kiện engine không tìm được phiên → 409 `NO_ACTIVE_SESSION`; worker bỏ sự kiện đó, không gửi lại *(giả định: mã lỗi mới, cần thêm vào api-conventions.md)*.
- **R12.** `POST /internal/v1/cameras/{id}/state`: API giữ trạng thái mới nhất của giường trong RAM (`body_state`, `observation_quality`, `activity_level`, `rest_status`, `face_status`, `face_signals`, `updated_at`). Không ghi DB *(data-model.md, mục "Dữ liệu không lưu trong DB")*. Sau khi cập nhật thì gọi publisher với `bed.state` (F18 phát).

**Domain**

- **R13.** Trong **một transaction**: insert `events`; nếu `priority ∈ {MEDIUM, HIGH}` thì insert `alerts` với `status = PENDING`, `outcome = null`. LOG và INFO chỉ vào timeline, không tạo alert *(QA#17; HS §5.4; event-engine.md mục 5)*.
- **R14.** Ghi audit `alert.create` với `actor_user_id = null` (hệ thống) khi tạo alert *(PDF §10.1 (tr.13); giả định: NFR08 yêu cầu ghi mọi thay đổi trạng thái cảnh báo, kể cả lúc tạo)*.
- **R15.** **Commit xong mới** gọi publisher với `event.created`, và `alert.created` nếu có alert *(HS §4.2; ADR-0002)*. Publisher là interface trong `domain` (domain không import `api`, overview.md mục 3). F17 cài bản ghi nhận trong RAM để test; F18 cài bản WebSocket. Publisher lỗi không được làm rollback dữ liệu đã lưu *(giả định)*.

**Sự kiện quan sát và camera**

- **R16.** `OBSERVATION_LOST` (INFO, A11): engine phát khi `NO_OBSERVATION` kéo dài ≥ `quality.observation_lost_event_s`. `OBSERVATION_RESTORED` (LOG): phát khi thoát `NO_OBSERVATION`, **chỉ khi** trước đó đã phát `OBSERVATION_LOST` *(PDF §4.3 (tr.6); HS §7.1; QA#21; event-engine.md mục 5; giả định: không phát RESTORED cho những lần mất quan sát ngắn, để giảm nhiễu timeline)*. Hai code này đi qua debounce của F15.
- **R17.** `CAMERA_OFFLINE` (MEDIUM, A11, tạo alert) do **API** sinh khi `cameras.status` chuyển `ONLINE → OFFLINE`. Lý do chuyển (heartbeat quá hạn theo A02, hoặc worker báo nguồn mất) do F06 xác định. `CAMERA_ONLINE` (LOG) sinh khi chuyển `OFFLINE → ONLINE` *(PDF §10 (tr.12); QA#21; event-engine.md mục 5)*. Lần đầu `UNKNOWN → ONLINE` không sinh sự kiện *(giả định)*.
- **R18.** Sự kiện do API sinh: `event_uid` sinh ở server; `session_id` là phiên đang mở của giường hoặc null; `occurred_at` = `last_seen_at` (với OFFLINE) hoặc thời điểm nhận heartbeat (với ONLINE); `confidence = 1.0`; `observation_quality = CAMERA_ISSUE` (OFFLINE) / `GOOD` (ONLINE); `explanation = {rule_id, reason, last_seen_at}`; `config_hash` = hash gần nhất worker đã gửi cho camera, hoặc chuỗi rỗng nếu chưa có *(giả định: data-model.md yêu cầu `config_hash` not null nhưng sự kiện do API sinh không qua engine)*. Camera chưa gắn giường thì không sinh sự kiện camera *(giả định: `events.bed_id` not null)*.
- **R19.** Quy tắc tạo alert ở R13 áp dụng cho mọi sự kiện, kể cả `CAMERA_OFFLINE` khi giường không có phiên mở *(QA#17, QA#21; giả định: áp dụng đồng nhất)*.

**API công khai**

- **R20.** `GET /api/v1/events?bed_id&session_id&from&to&priority&code&limit&offset` trả `{items, total}`, sắp `occurred_at` giảm dần. Mọi vai trò xem được *(api-conventions.md; giả định: thứ tự sắp)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/db/models/event.py`, `alert.py`; migration mới trong thư mục Alembic của F01.
  - `server/src/postcare/domain/events.py` (`ingest_event`, `create_camera_event`), `domain/alerts.py` (`create_alert_for_event`), `domain/notifications.py` (`Publisher` protocol, `InMemoryPublisher`), `domain/bed_state.py` (kho RAM).
  - `server/src/postcare/api/internal/events.py`, `api/internal/state.py`, `api/v1/events.py`.
  - `server/src/postcare/engine/rules/observation.py`.
  - `server/src/postcare/worker/runner.py` (vòng lặp engine), `worker/client.py` (gửi kèm gửi lại).
  - Test: `server/tests/api/test_internal_events.py`, `test_events_list.py`, `server/tests/domain/test_ingest_event.py`, `test_camera_events.py`, `server/tests/engine/test_rules_observation.py`, `server/tests/integration/test_worker_events.py`, `server/tests/db/test_enum_sync.py`.
- **Dữ liệu:** bảng `events`, `alerts` (tạo mới); đọc `cameras`, `monitoring_sessions`; ghi `audit_logs`.
- **API:** `POST /internal/v1/events`, `POST /internal/v1/cameras/{id}/state`, `GET /api/v1/events`. Thêm mã lỗi `NO_ACTIVE_SESSION` (409) vào [api-conventions.md](../02-architecture/api-conventions.md) cùng PR.
- **UI:** không có.
- **Cấu hình:** `quality.observation_lost_event_s`, `debounce.same_code_same_session_s`. Ngưỡng offline của camera thuộc F06 (A02), không nằm trong YAML engine.

## 5. Acceptance criteria

- [x] **AC1.** Migration tạo `events` và `alerts` đúng data-model (`upgrade`/`downgrade` hai chiều). Worker chạy engine realtime và gửi `POST /internal/v1/events`. API lưu sự kiện gắn đúng phiên, giường, camera *(PDF §10 (tr.12); HS §4.2, §6.2)*. — *Kiểm chứng:* `alembic downgrade -1 && alembic upgrade head`; `server/tests/integration/test_worker_events.py::test_worker_fake_exit_sequence_persists_events` (worker với `FakeFrameSource` / `FakePoseAdapter` phát chuỗi rời giường); `test_ingest_event.py::test_event_attached_to_open_session_at_occurred_at`.
- [x] **AC2.** Sự kiện MEDIUM hoặc HIGH tạo alert `PENDING` ("Chờ tiếp nhận") trong cùng transaction. LOG và INFO chỉ có sự kiện, không có alert. Publisher chỉ được gọi sau commit *(QA#17; HS §4.2)*. — *Kiểm chứng:* `test_ingest_event.py` (`test_high_event_creates_pending_alert`, `test_log_info_event_no_alert`, `test_publisher_called_after_commit`).
- [x] **AC3.** Giường không có phiên mở: worker không gửi sự kiện của engine; chỉ có sự kiện camera. API từ chối sự kiện engine không có phiên với 409 `NO_ACTIVE_SESSION` *(data-model.md; api-conventions.md)*. — *Kiểm chứng:* `test_worker_events.py::test_no_active_session_sends_no_engine_events`; `test_internal_events.py::test_engine_event_without_session_rejected`.
- [x] **AC4.** `CAMERA_OFFLINE` (MEDIUM, có alert) và `CAMERA_ONLINE` (LOG) do API sinh khi trạng thái camera đổi. `OBSERVATION_LOST` (INFO) và `OBSERVATION_RESTORED` (LOG) do engine sinh đúng mức *(QA#21; A11; event-engine.md mục 5)*. — *Kiểm chứng:* `test_camera_events.py` (`test_online_to_offline_creates_camera_offline_alert`, `test_offline_to_online_creates_camera_online_log`, `test_first_online_no_event`); `test_rules_observation.py` (`test_prolonged_no_observation_emits_observation_lost_info`, `test_restored_only_after_lost`).
- [x] **AC5.** Gửi lại cùng `event_uid` không tạo bản ghi, alert hay thông báo trùng *(ADR-0002)*. — *Kiểm chứng:* `test_internal_events.py::test_same_event_uid_twice_single_row` (kiểm tra số dòng `events`, `alerts`, và số lần publisher được gọi).

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | lệnh + tích hợp + domain | Migration hai chiều; worker giả gửi chuỗi `SIT_UP, BED_EDGE, STAND_UP, BED_EXIT`; sự kiện đến sau khi phiên đóng nhưng `occurred_at` nằm trong phiên | Sai `X-Worker-Token` → 401; `priority` không khớp `code` → 400; worker gửi `CAMERA_OFFLINE` → 400 |
| AC2 | domain | Một sự kiện mỗi mức LOG/INFO/MEDIUM/HIGH; publisher giả ghi thứ tự "commit → publish" | LOG/INFO không có alert; lỗi DB thì publisher không được gọi |
| AC3 | tích hợp + API | Cấu hình worker `active_session_id = null`; POST trực tiếp sự kiện engine khi không có phiên | Không có dòng `events` nào của engine |
| AC4 | domain + unit engine | Giả lập chuyển trạng thái camera; chuỗi `drop_landmarks` dài/ngắn hơn `quality.observation_lost_event_s` | Mất quan sát ngắn → không `OBSERVATION_LOST`/`RESTORED`; `UNKNOWN → ONLINE` không sinh sự kiện |
| AC5 | API | POST hai lần cùng `event_uid` | Không có bản ghi thứ hai |
| R2 | unit | So sánh enum DB với enum `postcare.schemas` | — |
| R20 | API | Lọc theo `bed_id`, `session_id`, `from/to`, `priority`, phân trang | `limit > 200` → 400 |

**Ca âm tính của engine** ([testing.md](../04-guides/testing.md) mục 2) liên quan rule quan sát:

| Tình huống | Kỳ vọng | Test |
|---|---|---|
| Mất landmark / bị che khi ở mép giường (ngắn hơn `observation_lost_event_s`) | `NO_OBSERVATION`, không `OBSERVATION_LOST`, không `BED_EXIT` | `test_short_occlusion_no_observation_lost` |
| Lặp mất quan sát trong cửa sổ debounce | Chỉ 1 `OBSERVATION_LOST` | `test_observation_lost_debounced` |

## 7. Giả định

- *(giả định)* Worker quy đổi `ts_ms` sang UTC theo mốc frame đầu (R4).
- *(giả định)* Hàng đợi gửi lại trong RAM, có giới hạn (R5).
- *(giả định)* Không có phiên thì worker vẫn gửi `state` nhưng không gửi sự kiện (R6).
- *(giả định)* Worker tạo `Engine` mới khi phiên đổi (R7).
- *(giả định)* Mã HTTP 201/200 và cách chống trùng bằng `ON CONFLICT` (R9).
- *(giả định)* Gắn phiên theo `occurred_at`; mã lỗi mới 409 `NO_ACTIVE_SESSION` (R11).
- *(giả định)* Ghi audit `alert.create` với actor là hệ thống (R14).
- *(giả định)* Publisher lỗi không rollback dữ liệu (R15).
- *(giả định)* `OBSERVATION_RESTORED` chỉ phát sau `OBSERVATION_LOST`; `UNKNOWN → ONLINE` không sinh sự kiện (R16, R17).
- *(giả định)* Giá trị các trường của sự kiện do API sinh, nhất là `config_hash` (R18).
- *(giả định)* `CAMERA_OFFLINE` tạo alert cả khi giường không có phiên (R19).
- Mức ưu tiên theo A11; ngưỡng offline theo A02.

## 8. Câu hỏi mở

- **Không chặn:** khi giường không có phiên mở, `CAMERA_OFFLINE` có nên tạo cảnh báo không? Mặc định là có (R19). Nếu người dùng thấy nhiễu thì đổi thành chỉ ghi timeline.

## 9. Kế hoạch triển khai

> Lập ngày 2026-11-18 (nhánh `feat/F17-events-alerts`).

**Khảo sát:** prototype và F06 đã làm phần lớn F17.

| Yêu cầu | Đã có | Bằng chứng / chỗ thiếu |
|---|---|---|
| R1, R2 | Migration `0002` (ADR-0010) tạo `events`, `alerts`, enum, unique `event_uid`, `alerts.event_id`, 3 index, có `downgrade`; khớp data-model.md | `tests/db/test_migrations.py::test_migrations_roundtrip`, `test_models_match_migrations`; `tests/db/test_enums_match.py::test_enums_match_schemas`. **Không cần migration mới** (cột không đổi; head vẫn `0006`) |
| R3–R7 (worker) | F06 (spec F06 §9–10) | `tests/worker/test_worker_loop.py` (state khi đổi, `event_uid` giữ khi gửi lại, 409 bỏ, không phiên → không gửi sự kiện, phiên đổi → engine mới, UTC). Thiếu: tích hợp worker ↔ API thật với engine thật phát chuỗi rời giường (AC1, AC3) |
| R8–R11 | `api/internal/cameras.py`, `domain/events.py` (catalog kiểm `priority`, chặn `CAMERA_*` từ worker, gắn phiên theo `occurred_at`, 409 `NO_ACTIVE_SESSION`, `CAPTURE_PAUSED` của F04) | `tests/test_events.py`. Chống trùng đồng thời dùng bắt `IntegrityError` của unique `event_uid` rồi đọc lại (tương đương `ON CONFLICT DO NOTHING`, giữ nguyên *(lệch cách cài đặt, cùng hành vi)*). Thiếu test: 401, đồng thời thật, sự kiện tới sau khi phiên đóng, `explanation`/`config_hash` lưu đúng, sự kiện ngoài cửa sổ phiên |
| R12 | `POST …/state` giữ RAM, phát `bed.state` | `test_events.py::test_bed_state_kept_in_memory_and_published` |
| R13–R15 | `_insert` cùng transaction, audit `alert.create` actor null, `publish_created` sau commit, `safe_publish` | `test_high_event_creates_pending_alert`, `test_publish_happens_after_commit`. Thiếu test: audit, publisher lỗi không rollback, lỗi DB không phát |
| R16 | **Chưa có** `engine/rules/observation.py` | Làm mới |
| R17–R19 | `domain/cameras.py` + `create_camera_event` | `test_camera_offline_creates_medium_alert_then_online`. Thiếu test: `UNKNOWN → ONLINE` không sinh, trường R18, giường không phiên vẫn có alert |
| R20 | `GET /api/v1/events` (`api/v1/monitoring.py`, `require_staff`) | Thiếu test lọc/phân trang/`limit > 200`, DOCTOR đọc được, FAMILY 403 (F35 đã chặn, `test_family_role_default_deny.py`) |

**Các bước:**

1. **Test trước** (commit `test(F17): …`):
   - `server/tests/engine/test_rules_observation.py`: `test_prolonged_no_observation_emits_observation_lost_info`, `test_restored_only_after_lost`, `test_short_occlusion_no_observation_lost` (mép giường, không `BED_EXIT`), `test_observation_lost_debounced`, mức ưu tiên từ catalog, `explanation.rule_id`, `config_hash`.
   - `server/tests/domain/test_ingest_event.py`: `test_event_attached_to_open_session_at_occurred_at` (đến sau khi đóng phiên nhưng `occurred_at` trong phiên), sự kiện ngoài cửa sổ phiên → 409, `test_high_event_creates_pending_alert`, `test_log_info_event_no_alert`, `test_publisher_called_after_commit`, lỗi DB → không phát, publisher lỗi → dữ liệu còn, audit `alert.create`, `explanation`/`config_hash` lưu đúng.
   - `server/tests/api/test_internal_events.py`: `test_same_event_uid_twice_single_row`, đồng thời (`real_commit`, 2 luồng), `test_engine_event_without_session_rejected`, 401, `priority` sai mã → 400, `CAMERA_OFFLINE` từ worker → 400, camera chưa gắn giường → 400.
   - `server/tests/domain/test_camera_events.py`: `test_online_to_offline_creates_camera_offline_alert`, `test_offline_to_online_creates_camera_online_log`, `test_first_online_no_event`, giường không phiên vẫn có alert (R19), trường R18.
   - `server/tests/api/test_events_list.py`: lọc `bed_id`, `session_id`, `from/to`, `priority`, `code`, phân trang, sắp giảm dần, `limit > 200` → 400, DOCTOR 200, FAMILY 403.
   - `server/tests/integration/test_worker_events.py`: `test_worker_fake_exit_sequence_persists_events` (worker + `TestClient` + engine thật + `FakePoseAdapter` theo chuỗi rời giường), `test_no_active_session_sends_no_engine_events`.
2. **Engine** `engine/rules/observation.py` (`ObservationRules`), ghép vào `RuleSet` qua debounce chung. Chuỗi `NO_OBSERVATION` tính từ frame đầu có `body_state = NO_OBSERVATION` (kể cả lúc engine khởi động *(giả định)*); phát một `OBSERVATION_LOST` mỗi chuỗi khi giữ ≥ `quality.observation_lost_event_s`; `occurred_at_ms` = đầu chuỗi; `confidence = 1.0` *(giả định: hệ thống chắc chắn là không quan sát được)*; `RESTORED` ở frame đầu thoát `NO_OBSERVATION` chỉ khi `LOST` của chuỗi đó đã **qua** debounce. Sinh lại expected fixture nếu lệch (xem lại).
3. **API/domain:** sửa chỗ test chỉ ra (dự kiến nhỏ).
4. **Docs:** event-engine.md (rule quan sát), api-conventions.md nếu đổi, spec §10.
5. `make check`, `scripts\dev.ps1 check`; trạng thái In review.

Không có câu hỏi chặn.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-18 – triển khai (nhánh `feat/F17-events-alerts`), trạng thái In review.**

| AC | Bằng chứng |
|---|---|
| AC1 | Migration: không đổi (`0002` của prototype đã đúng data-model; head vẫn `0006`), `tests/db/test_migrations.py::test_migrations_roundtrip` (downgrade base → upgrade head), `test_models_match_migrations`, `tests/db/test_enums_match.py` (R2). `server/tests/integration/test_worker_events.py::test_worker_fake_exit_sequence_persists_events` (worker thật + engine thật + `FakeFrameSource`/`FakePoseAdapter`, API thật qua `TestClient`: `SIT_UP, BED_EDGE, STAND_UP, BED_EXIT` lưu với đúng phiên/giường/camera, `config_hash`, `explanation.rule_id`; cảnh báo PENDING cho BED_EDGE, BED_EXIT). `server/tests/domain/test_ingest_event.py::test_event_attached_to_open_session_at_occurred_at` (đến sau khi đóng phiên), `test_event_outside_session_window_rejected`, `test_explanation_and_config_hash_stored` |
| AC2 | `test_ingest_event.py`: `test_high_event_creates_pending_alert`, `test_medium_event_creates_pending_alert`, `test_log_info_event_no_alert` (×4 mã), `test_publisher_called_after_commit` (`real_commit`, đọc bằng kết nối khác), `test_db_error_publishes_nothing`, `test_publisher_failure_keeps_saved_data`, `test_alert_creation_audited_as_system` (R14), `test_priority_from_catalog_not_client` |
| AC3 | `test_worker_events.py::test_no_active_session_sends_no_engine_events`; `server/tests/api/test_internal_events.py::test_engine_event_without_session_rejected` (409 `NO_ACTIVE_SESSION`); 401 thiếu/sai token; 400 sai mức, `CAMERA_*` từ worker, camera lạ/chưa gắn giường, `event_uid` không phải UUID; 422 mã ngoài enum |
| AC4 | `server/tests/domain/test_camera_events.py`: `test_online_to_offline_creates_camera_offline_alert` (trường R18, audit), `test_offline_to_online_creates_camera_online_log`, `test_first_online_no_event`, `test_camera_offline_without_session_still_alerts` (R19), `test_camera_without_bed_no_event`. `server/tests/engine/test_rules_observation.py`: `test_prolonged_no_observation_emits_observation_lost_info`, `test_restored_only_after_lost`, `test_short_occlusion_no_observation_lost`, `test_observation_lost_debounced`, `test_missing_person_prolonged_never_bed_exit`, `test_startup_without_observation_counts_as_lost`, `test_new_engine_starts_fresh` |
| AC5 | `test_internal_events.py::test_same_event_uid_twice_single_row` (1 dòng events, 1 alert, phát 1 lần), `test_concurrent_same_event_uid_single_row` (`real_commit`, 2 luồng) |
| R20 | `server/tests/api/test_events_list.py` (sắp giảm dần, lọc giường/phiên/from–to/priority/code, phân trang, `limit > 200` → 422, NURSE/CHARGE/DOCTOR/ADMIN đọc được, FAMILY 403, chưa đăng nhập 401) |

Thay đổi code: `engine/rules/observation.py` (mới, R16) ghép vào `RuleSet`; `domain/events.py` kiểm `event_uid` là UUID **trước** khi truy vấn (trước đây chuỗi lạ gây 500). Fixture regression không đổi (không clip nào mất quan sát ≥ 10 s).

Lệch so với spec (ghi lại, không chặn):
- R9: chống trùng đồng thời dùng unique `event_uid` + bắt `IntegrityError` rồi đọc lại (có từ prototype), không dùng `ON CONFLICT DO NOTHING`; hành vi như nhau, có test đồng thời.
- Kế hoạch test ghi `limit > 200` → 400; theo api-conventions.md lỗi schema của FastAPI là **422** `VALIDATION_ERROR`, test theo 422.
- R16: chuỗi mất quan sát tính cả lúc engine khởi động không thấy ai *(giả định)*; `OBSERVATION_RESTORED` phát khi state machine xác lập lại trạng thái (sau `restore_duration_s` + `min_duration_s` của trạng thái), `confidence = 1.0` *(giả định)*. Ghi ở event-engine.md mục 5.
- F04/F36: sự kiện tới muộn của khoảng đã tạm dừng vẫn nhận (giữ giả định F04 §7).

Kiểm tra (2026-11-18, sau khi merge `main` có F25): `make check` exit 0 (server 1039 passed, web 87 passed, build OK; lần chạy trước merge có một lần vitest hết bộ nhớ, chạy lại đạt). `scripts\dev.ps1 check` không chạy vì máy thiếu bộ nhớ; job Windows trên CI kiểm thay.

**2026-11-18 – review: Đạt**, kèm 2 điểm sửa (test trước, commit `test(F17): review fixes …` rồi `fix(F17): …`):

1. `OBSERVATION_RESTORED` không qua debounce khi LOST của cùng chuỗi đã phát (luôn đi cặp): `test_rules_observation.py::test_restored_not_debounced_when_its_lost_was_emitted` (kịch bản 0/10/55/60/70/75 s → cả hai RESTORED đều phát). Ghi ở event-engine.md mục 5.
2. Nhánh `IntegrityError` của `ingest_event` (request khác lưu cùng `event_uid` giữa lúc kiểm tra và lúc insert) được kiểm chứng xác định: `test_ingest_event.py::test_integrity_error_branch_returns_existing` (`_existing` lần đầu trả None → rollback, trả bản đã có, `created = false`, không phát).

Bằng chứng AC ở bảng trên (mục 5 đã tick). Sau sửa: MAKECHECK. Trạng thái: **Done**.

## 11. Definition of Done

- [x] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [x] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [x] Doc liên quan đã cập nhật cùng PR.
- [x] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
