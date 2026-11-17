# F06 – Kết nối worker với backend

| Thuộc tính | Giá trị |
|---|---|
| Mã | F06 |
| Trạng thái | In review <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 3 phiên |
| Phụ thuộc | F04, F05 |
| Nhánh code | B (backend) |
| Nguồn | PDF §10 (tr.12); HS §4.2, §6.1; QA#10, QA#29; A02, A03; ADR-0001, ADR-0002 |

## 1. Mục tiêu

Nối tiến trình worker (đọc camera, sau này chạy AI và engine) với tiến trình API qua HTTP nội bộ (ADR-0001, ADR-0002; HS §6.1). Worker lấy cấu hình camera, gửi heartbeat để API biết camera đang hoạt động hay mất kết nối, và gửi khung hình JPEG để dashboard xem trực tiếp. API chỉ giữ khung mới nhất trong RAM, không lưu ảnh (QA#29). Đây là bước đầu của luồng "nguồn video → máy tính xử lý → dashboard" (HS §4.2).

## 2. Phạm vi

**Trong phạm vi**
- API nội bộ `/internal/v1/*` xác thực bằng `X-Worker-Token`: `GET config`, `POST heartbeat`, `POST frame`.
- Cập nhật `cameras.status`, `cameras.last_seen_at`; phát hiện camera offline khi mất heartbeat.
- Lưu số liệu runtime của camera (FPS, độ sáng, số khung bỏ, trạng thái nguồn) trong RAM của API và trả qua `GET /api/v1/cameras/{id}`.
- Bộ đệm khung hình mới nhất trong RAM.
- Lệnh `postcare worker --camera-id N` và target `make worker CAMERA=N` (thay target giữ chỗ của F00).
- Worker áp dụng cấu hình mới trong ≤5 giây.
- Test tích hợp worker ↔ API với file video tổng hợp.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- `POST /internal/v1/cameras/{id}/state` và `POST /internal/v1/events`; chạy engine trong worker (→ F17).
- Sinh sự kiện `CAMERA_OFFLINE` / `CAMERA_ONLINE` (→ F17). F06 chỉ cập nhật trạng thái camera.
- Phát WebSocket `camera.status` (→ F18).
- Endpoint MJPEG cho trình duyệt (→ F07).
- Chế độ làm mờ / chỉ skeleton khi render khung (→ F28).
- Nhiều worker chạy đồng thời (→ F31).

## 3. Yêu cầu chi tiết

- **R1.** Mọi endpoint `/internal/v1/*` yêu cầu header `X-Worker-Token` bằng biến môi trường `WORKER_TOKEN`; thiếu hoặc sai → 401 `UNAUTHORIZED` *(api-conventions.md "API nội bộ cho worker")*. So sánh token bằng hàm so sánh thời gian hằng (`hmac.compare_digest`) *(giả định)*.
- **R2.** `GET /internal/v1/cameras/{id}/config` → `{camera_id, bed_id, source_type, source, roi_polygon, thresholds, display_mode, config_version, active_session_id}` *(api-conventions.md)*. `active_session_id` là phiên đang mở của giường gắn camera (F04), `null` nếu không có. Camera không tồn tại hoặc đã ngừng dùng → 404 *(giả định)*.
- **R3.** Worker gửi `POST /internal/v1/cameras/{id}/heartbeat` mỗi 2 giây với `{fps, brightness, dropped_frames, source_status}`; API trả `{config_version}` *(A02; api-conventions.md)*. `brightness` là độ sáng trung bình (0–255, ảnh xám) của khung mới nhất *(giả định cách tính; phục vụ chỉ báo ở F08, PDF §9.1)*.
- **R4.** API khi nhận heartbeat *(A02)*:
  - cập nhật `cameras.last_seen_at = now()`;
  - `cameras.status = ONLINE` nếu `source_status = ONLINE`, ngược lại `OFFLINE` *(giả định: worker còn sống nhưng mất nguồn video thì camera vẫn coi là mất kết nối)*;
  - lưu `fps`, `brightness`, `dropped_frames`, `source_status`, thời điểm nhận vào bộ nhớ runtime trong RAM (không có cột DB).
- **R5.** Quá 5 giây không nhận heartbeat → API đặt `cameras.status = OFFLINE` *(A02)*. Một tác vụ nền trong API kiểm tra định kỳ mỗi 1 giây *(giả định)*. Hàm kiểm tra nhận thời điểm `now` làm tham số để test không cần chờ thật.
- **R6.** Worker áp dụng cấu hình mới trong ≤5 giây kể từ khi cấu hình đổi trên API *(ADR-0002)*:
  - so `config_version` trong mỗi phản hồi heartbeat (2 giây) với bản đang dùng; khác thì gọi lại `GET config`;
  - đồng thời poll `GET config` mỗi 5 giây để phòng mất heartbeat *(overview.md §7)*;
  - đổi `source_type`/`source` → đóng nguồn cũ, mở nguồn mới (F05).
- **R7.** Worker gửi `POST /internal/v1/cameras/{id}/frame` (body `image/jpeg`) khoảng 5 fps → 204 *(A03)*. Khung được thu nhỏ và nén trước khi gửi *(giả định: cạnh dài tối đa 960 px, chất lượng JPEG 70)*. Ở F06 chỉ có chế độ hiển thị RAW; F28 thêm BLUR và SKELETON.
- **R8.** API giữ **duy nhất khung mới nhất** của mỗi camera trong RAM (bytes + thời điểm nhận), **không ghi đĩa** *(QA#29; ADR-0002)*. Body lớn hơn giới hạn (ví dụ 2 MB) → 400 `VALIDATION_ERROR` *(giả định)*.
- **R9.** `GET /api/v1/cameras/{id}` (F03) trả thêm khối `runtime: {fps, brightness, dropped_frames, source_status, updated_at}` lấy từ RAM, `null` nếu chưa có heartbeat *(giả định: chưa có endpoint riêng trong api-conventions.md; F07, F08 cần số liệu này trước khi có WebSocket ở F18)*.
- **R10.** Worker bền với lỗi *(PRD NFR03; giả định cách làm)*:
  - API không phản hồi → thử lại với backoff, worker không thoát;
  - nguồn video mất → F05 tự kết nối lại; heartbeat vẫn gửi với `source_status = OFFLINE`;
  - dừng bằng Ctrl+C → đóng nguồn gọn gàng, exit 0.
- **R11.** `postcare worker --camera-id N` đọc `API_BASE_URL` và `WORKER_TOKEN` từ môi trường *(.env.example)*. `make worker CAMERA=N` gọi lệnh này *(overview.md §1)*.
- **R12.** Module `postcare.worker` chỉ import `vision`, `engine`, `schemas`, httpx; không import `api`, `db` *(overview.md §3)*. HTTP client của worker nhận một `httpx.Client` được inject để test dùng được `TestClient` của FastAPI *(giả định)*.
- **R13.** Đồng hồ và hàm chờ của vòng lặp worker được inject để test chạy nhanh, không `sleep` thật *(testing.md §2 tinh thần "không dùng đồng hồ thật"; giả định áp dụng cho worker)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/internal/__init__.py`, `api/internal/cameras.py` (config, heartbeat, frame), `api/internal/auth.py` (`require_worker_token`).
  - `server/src/postcare/api/frame_buffer.py` (khung mới nhất trong RAM), `api/camera_runtime.py` (số liệu runtime trong RAM), `api/tasks.py` (tác vụ nền kiểm tra offline) *(giả định tên file)*.
  - `server/src/postcare/domain/cameras.py`: `get_worker_config`, `record_heartbeat`, `mark_stale_cameras_offline(now)`.
  - `server/src/postcare/worker/client.py` (HTTP tới API), `worker/loop.py` (vòng lặp), `worker/config.py` (theo dõi `config_version`).
  - `server/src/postcare/vision/image_stats.py` (`mean_brightness`), `vision/render.py` (`encode_jpeg`, chế độ RAW) *(giả định tên file)*.
  - `server/src/postcare/cli.py`: lệnh `worker`. `Makefile`: target `worker`.
  - `server/tests/api/test_internal_auth.py`, `test_internal_config.py`, `test_heartbeat.py`, `test_frame_buffer.py`; `server/tests/integration/test_worker_api.py`.
- **Dữ liệu:** cập nhật `cameras.status`, `cameras.last_seen_at`; đọc `cameras`, `monitoring_sessions` (xem [data-model.md](../02-architecture/data-model.md#cameras-f01)). Không có migration mới.
- **API:** `GET /internal/v1/cameras/{id}/config`, `POST /internal/v1/cameras/{id}/heartbeat`, `POST /internal/v1/cameras/{id}/frame` (xem [api-conventions.md](../02-architecture/api-conventions.md#api-nội-bộ-cho-worker)); bổ sung khối `runtime` trong `GET /api/v1/cameras/{id}`. Chạy `make gen-api-types`.
- **UI:** không có.
- **Cấu hình:** `API_BASE_URL`, `WORKER_TOKEN`. Chu kỳ heartbeat 2 s, ngưỡng offline 5 s, poll cấu hình 5 s, JPEG ~5 fps (A02, A03) đặt trong settings, không viết cứng *(giả định)*.

## 5. Acceptance criteria

- [x] **AC1.** `postcare worker --camera-id N` lấy cấu hình qua `GET /internal/v1/cameras/{id}/config`; sai hoặc thiếu `X-Worker-Token` → 401. *(ADR-0002)* — *Kiểm chứng:* test `test_internal_config_returns_camera_config`, `test_internal_config_includes_active_session`, `test_internal_endpoints_require_worker_token` (tham số hóa 3 endpoint).
- [x] **AC2.** Heartbeat mỗi 2 giây cập nhật `cameras.status` và `last_seen_at`; quá 5 giây không có heartbeat → `OFFLINE`. *(A02)* — *Kiểm chứng:* test `test_heartbeat_sets_online_and_last_seen`, `test_heartbeat_source_offline_sets_offline`, `test_stale_camera_marked_offline` (gọi `mark_stale_cameras_offline(now = last_seen + 6 s)`), `test_runtime_exposed_on_camera_detail`.
- [x] **AC3.** Đổi cấu hình camera trên API thì worker áp dụng trong ≤5 giây. *(ADR-0002)* — *Kiểm chứng:* test tích hợp `test_worker_reloads_config_within_5s` (đồng hồ giả lập: sửa camera → tăng `config_version` → trong ≤5 s giả lập worker đang dùng cấu hình mới).
- [x] **AC4.** Worker gửi JPEG khoảng 5 fps; API giữ khung mới nhất trong RAM và **không ghi đĩa**. *(A03; QA#29)* — *Kiểm chứng:* test `test_frame_buffer_keeps_latest_only`, `test_frame_post_does_not_write_disk` (đếm file trong thư mục làm việc tạm trước/sau), `test_worker_frame_rate_about_5fps` (đồng hồ giả lập, 10 s → 45–55 khung).
- [x] **AC5.** Test tích hợp với file video: chạy worker → camera `ONLINE`; dừng worker → sau >5 giây camera `OFFLINE`. *(testing.md §1 "Tích hợp worker ↔ API"; A02)* — *Kiểm chứng:* test `test_worker_online_then_offline` (`FileSource` trên video tổng hợp trong `tmp_path`, worker dùng `TestClient` làm HTTP client); chạy tay `make dev-api` + `make worker CAMERA=1` với webcam, ghi vào mục 10.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | `test_internal_config_returns_camera_config`, `test_internal_config_includes_active_session` | Thiếu/sai token → 401; camera không tồn tại hoặc ngừng dùng → 404 |
| AC2 | API + domain | `test_heartbeat_sets_online_and_last_seen`, `test_stale_camera_marked_offline` | Heartbeat cách 4 s → vẫn `ONLINE`; `source_status = OFFLINE` → `OFFLINE` |
| AC3 | tích hợp | `test_worker_reloads_config_within_5s` | Không đổi cấu hình → worker không gọi lại `GET config` ngoài lịch poll |
| AC4 | API + unit | `test_frame_buffer_keeps_latest_only`, `test_frame_post_does_not_write_disk`, `test_worker_frame_rate_about_5fps` | Body quá lớn → 400; content-type sai → 400 *(giả định)* |
| AC5 | tích hợp | `test_worker_online_then_offline` | API tạm không phản hồi → worker không thoát, thử lại |

## 7. Giả định

- *(giả định)* Camera coi là `OFFLINE` khi worker còn sống nhưng `source_status = OFFLINE`.
- *(giả định)* Tác vụ nền kiểm tra offline mỗi 1 giây.
- *(giả định)* `brightness` là trung bình mức xám 0–255 của khung mới nhất.
- *(giả định)* JPEG thu nhỏ cạnh dài ≤960 px, chất lượng 70; giới hạn body 2 MB.
- *(giả định)* Số liệu runtime trả trong khối `runtime` của `GET /api/v1/cameras/{id}`; cập nhật api-conventions.md cùng PR.
- *(giả định)* Camera ngừng dùng → `GET config` trả 404 và worker dừng với thông báo rõ.
- *(giả định)* HTTP client của worker được inject; test dùng `TestClient`.
- *(giả định)* Chu kỳ và ngưỡng (A02, A03) đặt trong settings.

## 8. Câu hỏi mở

- Trước F28, worker gửi khung RAW (chưa làm mờ) dù `display_mode` mặc định là `BLUR` (A08). Trong M0–M3 chỉ dùng người tham gia mô phỏng đã đồng ý (HS §6.3). Có chấp nhận tạm như vậy không, hay cần làm mờ sớm hơn? Mặc định: chấp nhận RAW tạm thời, ghi rõ trong README. **Không chặn.**

## 9. Kế hoạch triển khai

> Lập ngày 2026-11-18 (nhánh `feat/F06-worker-link`). Prototype đã có sẵn phần lớn API nội bộ (`api/internal/cameras.py`: config, heartbeat, state, events; `domain/cameras.py`: `mark_offline_cameras(now=…)`; `require_worker` đã dùng `secrets.compare_digest`). F06 bổ sung phần còn thiếu và viết worker thật thay `postcare simulate`.

**Kéo trước theo yêu cầu người giao việc (ghi rõ để F17/F36/F30 không làm lại):**

- F17 R3–R7 **phía worker**: chạy `postcare.pipeline.process_frame` (adapter pose F11 + `Engine` F10–F15/F23) cho mỗi khung; `state_changed` → `POST …/state`; mỗi `EngineEvent` → `POST /internal/v1/events` (`event_uid` uuid4, gửi lại khi lỗi mạng/5xx với **cùng** `event_uid`, hàng đợi RAM giới hạn 200); 409 (`NO_ACTIVE_SESSION`, `CAPTURE_PAUSED`) → bỏ sự kiện, không gửi lại; `active_session_id = null` → không gửi sự kiện engine, vẫn gửi state; đổi `active_session_id` → `Engine` mới; `occurred_at = t0_utc + (ts_ms − ts0_ms)`. Phía API của F17 (lưu sự kiện, alert, sự kiện camera) đã có từ prototype; F17 vẫn phải kiểm AC của mình.
- F36 R18 **phía worker**: `capture_paused = true` → đóng nguồn, dừng engine, chỉ gửi heartbeat với `source_status = PAUSED`. Phần API bỏ `frame`/`state` khi tạm dừng vẫn để F36.
- F30 R4 tối thiểu: nguồn `FILE` (từ cấu hình camera hoặc `--video <path>`) phát theo **nhịp thời gian thực** (một camera không chạy nhanh hơn thời gian thật); hết file → `source_status = OFFLINE`, worker vẫn heartbeat. `--loop` để F30.

**Các bước:**

1. **API** (`api/internal/cameras.py`, `domain/cameras.py`, `domain/runtime.py`, `api/frame_buffer.py`, `api/v1/cameras.py`, `settings.py`):
   - Heartbeat: `source_status ∈ {ONLINE, PAUSED}` hoặc không gửi → `ONLINE`; giá trị khác (`OFFLINE`, `UNKNOWN`) → `OFFLINE` *(giả định: PAUSED = worker còn sống, tạm dừng có chủ đích, không phải mất kết nối; thiếu trường = client cũ)*. `ONLINE → OFFLINE` do nguồn mất đi chung đường với `mark_offline_cameras` (sinh `CAMERA_OFFLINE` `reason = source_offline`, trạng thái giường `NO_OBSERVATION`). Runtime lưu thêm `updated_at`.
   - `GET /api/v1/cameras/{id}` thêm `runtime: {fps, brightness, dropped_frames, source_status, updated_at} | null` (danh sách không có). `make gen-api-types`.
   - `POST /internal/v1/cameras/{id}/frame`: `Content-Type: image/jpeg`, ≤ `FRAME_MAX_BYTES` (2 MB) → 204; sai loại, quá lớn, rỗng → 400 `VALIDATION_ERROR`; camera không tồn tại hoặc ngừng dùng → 404. `LatestFrameStore` trong RAM (bytes + thời điểm), không ghi đĩa.
   - Hàm R5 giữ tên đã có `mark_offline_cameras(now=…)` (spec ghi `mark_stale_cameras_offline`).
2. **Vision**: `vision/image_stats.py` `mean_brightness(image)` (xám 0–255); `vision/render.py` `encode_jpeg(image, max_side=960, quality=70)`.
3. **Worker** (`worker/config.py`, `worker/client.py`, `worker/loop.py`): một luồng, chạy theo `step()`; đồng hồ đơn điệu, đồng hồ UTC, `sleep`, `httpx.Client`, nhà máy nguồn và nhà máy adapter đều inject (R12, R13). Lịch: heartbeat 2 s, poll config 5 s, khung JPEG 5 fps (hạn cố định), state gửi khi `state_changed` và làm mới mỗi 5 s *(giả định: API khởi động lại vẫn có trạng thái)*. API không phản hồi → log, backoff 1→10 s, không thoát. Config 404 → dừng, exit 1 (camera ngừng dùng); 401 → exit 1 (sai `WORKER_TOKEN`). Nguồn mở lỗi → `OFFLINE`, thử lại mỗi 2 s; webcam/URL dùng `fail_fast=False` (F05 tự kết nối lại). Đổi `source_type/source` → đóng nguồn, tạo adapter mới (MediaPipe VIDEO cần `ts_ms` tăng ngặt). ROI chưa cấu hình → chỉ heartbeat + khung, không chạy engine (log cảnh báo).
4. **CLI**: `postcare worker --camera-id N` (bí danh `--camera`), `--video PATH` (ghi đè nguồn bằng file), `--model`, `--models-dir`, `--api`; Ctrl+C → đóng gọn, exit 0. `make worker CAMERA=N`, `scripts\dev.ps1 worker -Camera N`. Giả lập gửi `source_status = ONLINE`.
5. **Docs**: api-conventions.md (frame, runtime, PAUSED), dev-setup.md, README (chạy worker thay giả lập).

**Test trước (fake API bằng `httpx.MockTransport`, `FakeFrameSource`, `FakePoseAdapter`, đồng hồ giả):**

- `server/tests/api/test_internal_cameras.py`: AC1 (`test_internal_config_returns_camera_config`, `test_internal_config_includes_active_session`, `test_internal_endpoints_require_worker_token` ×3, 404), AC2 (`test_heartbeat_sets_online_and_last_seen`, `test_heartbeat_source_offline_sets_offline`, `test_heartbeat_4s_apart_stays_online`, `test_stale_camera_marked_offline`, `test_runtime_exposed_on_camera_detail`), AC4 (`test_frame_buffer_keeps_latest_only`, `test_frame_post_does_not_write_disk`, quá lớn / sai content-type → 400).
- `server/tests/worker/test_worker_loop.py`: nhịp heartbeat, `test_worker_reloads_config_within_5s` (+ ca âm: không đổi → chỉ poll theo lịch), `test_worker_frame_rate_about_5fps`, gửi lại sự kiện cùng `event_uid`, 409 bỏ, API sập không crash, nguồn OFFLINE báo lên, state chỉ gửi khi đổi, tạm dừng không đọc khung, config 404 dừng.
- `server/tests/worker/test_worker_api.py` (tích hợp, `TestClient` làm `httpx.Client`): `test_worker_online_then_offline` (FileSource video tổng hợp trong `tmp_path`), `test_worker_reloads_config_within_5s_api`.

Commit: `docs(F06): plan` → `test(F06): …` → `feat(F06): …` → `docs(F06): …`.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-18 – triển khai (nhánh `feat/F06-worker-link`), trạng thái In review.**

Bằng chứng theo AC (test tự động):

| AC | Test |
|---|---|
| AC1 | `server/tests/api/test_internal_cameras.py`: `test_internal_config_returns_camera_config`, `test_internal_config_includes_active_session`, `test_internal_config_unknown_or_inactive_camera_404`, `test_internal_endpoints_require_worker_token` (3 endpoint × thiếu/sai token); `server/tests/worker/test_worker_loop.py`: `test_worker_fetches_config_on_start`, `test_config_404_stops_worker`, `test_config_401_stops_worker`; `tests/test_cli.py::test_worker_command_help_lists_camera_id` |
| AC2 | `test_heartbeat_sets_online_and_last_seen`, `test_heartbeat_source_offline_sets_offline` (+ `CAMERA_OFFLINE` `reason = source_offline`, giường `NO_OBSERVATION`), `test_heartbeat_paused_keeps_online`, `test_heartbeat_4s_apart_stays_online` (ca âm), `test_stale_camera_marked_offline` (`mark_offline_cameras(now = last_seen + 6 s)`), `test_runtime_exposed_on_camera_detail`; worker: `test_heartbeat_every_2s_with_stats`, `test_source_offline_reported_in_heartbeat` |
| AC3 | `test_worker_reloads_config_within_5s` (đồng hồ giả, ROI mới → engine mới), `test_unchanged_config_fetched_only_on_poll_schedule` (ca âm: chỉ poll 5 s), `test_source_reopened_when_source_changes`, `test_session_change_creates_new_engine`; tích hợp `server/tests/worker/test_worker_api.py::test_worker_reloads_config_within_5s_api` (PATCH camera qua API thật) |
| AC4 | `test_frame_buffer_keeps_latest_only`, `test_frame_buffer_unit`, `test_frame_post_does_not_write_disk`, `test_frame_too_large_or_wrong_type_400`, `test_frame_unknown_camera_404`; `test_worker_frame_rate_about_5fps` (10 s giả lập → 45–55 khung); `tests/vision/test_image_stats.py` (JPEG thu nhỏ ≤960, độ sáng 0–255) |
| AC5 | `test_worker_online_then_offline` (FileSource video tổng hợp trong `tmp_path`, `TestClient` làm `httpx.Client`, engine thật: camera `ONLINE`, trạng thái giường trong RAM, khung trong RAM, `runtime`; dừng → sau 6 s `OFFLINE`); `test_api_down_worker_keeps_running_and_recovers`, `test_api_down_midway_then_recovers` (ca âm) |

Phần kéo trước (F17 R3–R7 phía worker, F36 R18 phía worker): `test_state_posted_only_on_change_and_refresh`, `test_event_posted_with_utc_times_and_config_hash`, `test_event_retried_with_same_uid_on_5xx_and_network_error` (503, 500, API sập rồi 201; một `event_uid`), `test_event_409_dropped_not_retried`, `test_no_active_session_sends_state_but_no_events`, `test_capture_paused_stops_reading_and_engine`, `test_no_roi_sends_frames_but_no_engine`, `test_close_releases_source_and_adapter`.

Chạy tay end-to-end (2026-11-18, DB `postcare_f06`, `alembic upgrade head` + `postcare seed`, uvicorn cổng 8016; camera 1 của A01; ROI từ `config/cameras/pexels-8090735.yaml` đặt bằng SQL vì F08 chưa có; bệnh nhân BN-F06, mở phiên):

| Lần chạy | Kết quả |
|---|---|
| `postcare worker --camera-id 1 --api http://127.0.0.1:8016`, nguồn FILE `data/external/pexels/pexels-8090735.mp4` (7,7 s, pose mặc định) | API nhận 3 lần GET config, 6 heartbeat, 9 state, 38 khung (≈ 4,9 fps), 1 sự kiện 201. Sự kiện engine thật **`BED_EDGE` (MEDIUM)**, `rule_id = body.bed_edge`, `config_hash 209d60d22e16…`, `detected_at − occurred_at = 1,5 s` → cảnh báo `PENDING`. Hết file → heartbeat `source_status = OFFLINE` → camera `OFFLINE`, `CAMERA_OFFLINE` (cảnh báo PENDING), `/overview` A01 `NO_OBSERVATION / CAMERA_ISSUE`. `runtime`: fps 14,79, brightness 90,4, dropped 69 |
| Đóng phiên, PATCH camera → WEBCAM 0, mở phiên mới, chạy worker 15 s (webcam laptop) | `ONLINE`, `runtime` fps 15,09, brightness 3,5 (ống kính bị che/tối), 32 khung trong ~7 s; dừng worker → `mark_offline_cameras` đặt `OFFLINE` + `CAMERA_OFFLINE` sau >5 s |

Kiểm tra (2026-11-18): `make check` exit 0 (server 842 passed, web 77 passed, build OK); `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check` exit 0.

Điều người sau cần biết:
- **Lệch phạm vi có chủ đích** (theo yêu cầu người giao việc, §9): worker đã chạy engine và gửi state/sự kiện (F17 R3–R7 phía worker), tôn trọng `capture_paused` (F36 R18 phía worker), phát file theo nhịp thời gian thực (một phần F30 R4; chưa có `--loop`, `ts_ms` vẫn theo video, worker quy đổi sang UTC). F17/F36/F30 chỉ cần kiểm AC và làm phần còn lại.
- `source_status` hợp lệ: `ONLINE`, `OFFLINE`, `PAUSED`; thiếu trường → coi như `ONLINE` (giả lập cũ). Giả lập nay gửi `ONLINE`, brightness 150.
- Hàm R5 giữ tên `mark_offline_cameras(now=…)` (spec ghi `mark_stale_cameras_offline`).
- `GET /api/v1/cameras/{id}` trả `CameraDetailOut` (có `runtime`); danh sách vẫn `CameraOut`. Đã `make gen-api-types`.
- `pipeline.process_frame` nhận `Engine | FrameEngine` (Protocol) để test worker dùng engine giả; hành vi không đổi.
- Khung gửi đi là RAW cho tới F28 (câu hỏi mở §8, mặc định chấp nhận; README đã ghi).
- ROI camera chưa đặt → worker chỉ gửi heartbeat + khung, log cảnh báo (cần F08 để đặt ROI trên UI).

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
