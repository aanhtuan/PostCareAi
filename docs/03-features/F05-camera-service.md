# F05 – Nguồn video (Camera Service)

| Thuộc tính | Giá trị |
|---|---|
| Mã | F05 |
| Trạng thái | In review <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F00 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §10 (tr.12), bảng §8 (tr.10), §12 (tr.13–14); HS §4.2, §6.1; QA#24; A03, A14; ADR-0003 |

## 1. Mục tiêu

Cung cấp Camera Service: nhận luồng hình ảnh từ smartphone (DroidCam / IP Webcam), webcam hoặc file video, gắn timestamp cho từng khung và theo dõi trạng thái kết nối (PDF §10; HS §4.2, §6.1; QA#24). Đây là đầu vào chung của worker realtime (F06, F17) và replay offline (F12). PDF §12 gợi ý dựng engine trên file video trước rồi mới chuyển sang camera realtime, nên file video được hỗ trợ ngang hàng với camera.

## 2. Phạm vi

**Trong phạm vi**
- Interface `FrameSource` và 3 cài đặt: webcam (index), URL HTTP/RTSP, file video.
- Timestamp đơn điệu (ms) và `frame_index` cho mỗi khung.
- Tự kết nối lại có backoff khi mất nguồn; báo trạng thái `ONLINE`/`OFFLINE`.
- Giới hạn FPS xử lý; bỏ khung cũ, không xếp hàng; đếm số khung bỏ.
- Lệnh `postcare probe --source …`.
- `FakeFrameSource` cho test.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Gửi heartbeat, khung hình lên API (→ F06).
- Phát lại file với tốc độ thời gian thực như một camera (`--source file --realtime`) (→ F30).
- Chạy pose trong `probe` để đo FPS (→ F11).
- Làm mờ, vẽ skeleton (→ F12 preview, F28).
- Nhiều camera đồng thời (→ F31).
- Lưu video hay ảnh *(QA#29: không lưu ảnh/video trong vận hành)*.

## 3. Yêu cầu chi tiết

- **R1.** `FrameSource` (Protocol) có `open()`, `read() -> Frame | None`, `close()` và thuộc tính `status` (`ONLINE`/`OFFLINE`) *(PDF §10: Camera Service "nhận stream, lấy frame và theo dõi trạng thái kết nối")*. `Frame` gồm `image` (numpy BGR), `ts_ms`, `frame_index`, kích thước.
- **R2.** Ba cài đặt *(PDF bảng §8 (tr.10) "OpenCV/RTSP"; HS §4.2; QA#24)*:
  - `WebcamSource(index)`;
  - `UrlSource(url)`: HTTP MJPEG (DroidCam `http://<ip>:4747/video`, IP Webcam `http://<ip>:8080/video`, theo A14) và RTSP;
  - `FileSource(path)`.
  - Hàm `open_source(source_type, source)` tạo đúng loại từ `CameraSourceType` (enum ở `postcare.schemas`, F01) *(giả định: nếu F01 chưa xong thì F05 tạo enum này và F01 dùng lại)*.
- **R3.** Timestamp *(ADR-0003: MediaPipe chế độ VIDEO cần timestamp đơn điệu)*:
  - `ts_ms` tăng **ngặt** qua các khung của một lần chạy;
  - webcam/URL: lấy từ đồng hồ đơn điệu của máy (`time.monotonic_ns`) tính từ lúc mở nguồn;
  - file: lấy thời gian của chính video (vị trí khung trong video), không dùng đồng hồ máy, để replay cho kết quả lặp lại được;
  - nếu hai khung liên tiếp có cùng `ts_ms` thì khung sau được cộng thêm 1 ms *(giả định)*;
  - `frame_index` tăng 1 cho mỗi khung được trả về.
- **R4.** Mất nguồn (không mở được, đọc lỗi liên tiếp) với webcam/URL → chuyển `OFFLINE`, tự kết nối lại theo backoff tăng dần 1 s, 2 s, 4 s… tối đa 10 s; kết nối lại được → `ONLINE` *(PRD NFR03; giả định giá trị backoff)*. Khi trạng thái đổi, gọi callback `on_status_change` *(giả định)* để F06 báo lên API.
- **R5.** File video hết khung → `read()` trả `None` (kết thúc), **không** coi là `OFFLINE` và không kết nối lại *(giả định)*.
- **R6.** Giới hạn FPS xử lý, mặc định 15 *(A03)*, chỉnh được bằng tham số (`max_fps`):
  - webcam/URL: một luồng đọc giữ **khung mới nhất**; người dùng lấy khung mới nhất, không có hàng đợi tích lũy;
  - file: chọn khung theo thời gian video sao cho không vượt `max_fps` (xác định, lặp lại được) *(giả định)*;
  - mọi khung đã đọc từ nguồn nhưng không được trả cho người dùng được đếm vào `dropped_frames`.
- **R7.** Thống kê đọc được: FPS thực tế (trung bình trượt), độ phân giải, `dropped_frames` *(HS §8.2: FPS, frame bỏ)*.
- **R8.** Lệnh `postcare probe --source <index|url|path> [--seconds N] [--max-fps N]` *(dev-setup.md §5; camera-setup.md §3)*:
  - đoán loại nguồn: số nguyên → webcam; bắt đầu bằng `http://`, `https://`, `rtsp://` → URL; còn lại → file *(giả định)*;
  - chạy N giây (mặc định 10 *(giả định)*), in FPS thực, độ phân giải, số khung bỏ, số lần mất kết nối;
  - không mở được nguồn → thông báo rõ và exit khác 0.
- **R9.** Dùng `opencv-contrib-python` (không cài `opencv-python`) *(tech-stack.md)*. Module chỉ import `schemas`, `cv2`, `numpy` *(overview.md §3 hàng `vision`)*.
- **R10.** Không ghi khung hình ra đĩa *(QA#29)*.
- **R11.** `FakeFrameSource` (sinh khung tổng hợp có `ts_ms` điều khiển được, giả lập mất nguồn) dùng cho test của F05, F06 và test tích hợp *(testing.md §1)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/vision/camera.py` (`Frame`, `FrameSource`, `WebcamSource`, `UrlSource`, `FileSource`, `open_source`, `SourceStats`) *(overview.md: `vision.camera`)*.
  - `server/src/postcare/vision/fake.py` (`FakeFrameSource`) *(giả định vị trí; hoặc trong `server/tests/`)*.
  - `server/src/postcare/cli.py`: lệnh `probe`.
  - `server/tests/camera/test_file_source.py`, `test_reconnect.py`, `test_fps_limit.py`, `server/tests/test_cli_probe.py`. Không đặt ở `server/tests/vision/` vì thư mục đó dành cho test marker `vision` cần model thật (testing.md §1); test của F05 chạy trong `make check`.
- **Dữ liệu:** không có.
- **API:** không có.
- **UI:** không có (lệnh CLI in tiếng Việt hoặc tiếng Anh đều được vì là công cụ dev *(giả định)*).
- **Cấu hình:** `max_fps` mặc định 15 (A03) là tham số của Camera Service, không nằm trong `engine.default.yaml` *(giả định: đây là cấu hình vận hành worker, không phải ngưỡng của engine)*.

## 5. Acceptance criteria

- [ ] **AC1.** `FrameSource` hỗ trợ webcam (index), URL HTTP/RTSP (DroidCam, IP Webcam) và file video qua `open_source(source_type, source)`. *(HS §4.2; QA#24)* — *Kiểm chứng:* test `test_open_source_dispatch` (3 loại); test `test_file_source_reads_all_frames` trên video tổng hợp tạo bằng `cv2.VideoWriter` trong `tmp_path` (không commit media); kiểm chứng tay với webcam và điện thoại (DroidCam hoặc IP Webcam), ghi vào mục 10.
- [x] **AC2.** Mỗi khung có `ts_ms` tăng ngặt và `frame_index`. File video dùng thời gian của chính video: hai lần đọc cùng file cho cùng dãy `ts_ms`. *(ADR-0003)* — *Kiểm chứng:* test `test_timestamps_strictly_increasing`, `test_file_source_uses_video_time`, `test_file_source_deterministic`.
- [ ] **AC3.** Mất nguồn → `OFFLINE`, tự kết nối lại theo backoff; có lại nguồn → `ONLINE`; callback trạng thái được gọi đúng thứ tự. *(PRD NFR03)* — *Kiểm chứng:* test `test_reconnect_with_backoff` (capture giả lập lỗi rồi phục hồi; đồng hồ và hàm chờ được inject, không `sleep` thật); tắt app điện thoại khi đang `probe`, ghi kết quả vào mục 10.
- [ ] **AC4.** `postcare probe --source …` in FPS thực, độ phân giải, số khung bỏ; nguồn không mở được → exit khác 0. *(dev-setup.md §5; camera-setup.md §3; HS §8.2)* — *Kiểm chứng:* test `test_probe_on_file_prints_stats` (CliRunner của Typer), `test_probe_bad_source_exits_nonzero`; chạy tay với URL điện thoại.
- [x] **AC5.** Giới hạn FPS xử lý (mặc định 15): không có hàng đợi khung cũ; khung bị bỏ được đếm. *(A03)* — *Kiểm chứng:* test `test_fps_limit_file_source` (video tổng hợp 30 fps → ≤15 khung/giây video, `dropped_frames` ≈ một nửa), `test_live_source_returns_latest_frame` (`FakeFrameSource` sinh nhanh hơn tốc độ đọc → nhận khung mới nhất, đếm khung bỏ).

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit | `test_open_source_dispatch`, `test_file_source_reads_all_frames` | `source_type` không hợp lệ → lỗi rõ ràng; file không tồn tại → không mở được |
| AC1 | thủ công | Webcam laptop; DroidCam/IP Webcam qua Wi-Fi | — |
| AC2 | unit | `test_timestamps_strictly_increasing`, `test_file_source_uses_video_time`, `test_file_source_deterministic` | Hai khung cùng `ts_ms` → khung sau +1 ms |
| AC3 | unit | `test_reconnect_with_backoff`, `test_status_callback_order` | `test_file_eof_is_not_offline` |
| AC4 | CLI | `test_probe_on_file_prints_stats` | `test_probe_bad_source_exits_nonzero` |
| AC5 | unit | `test_fps_limit_file_source`, `test_live_source_returns_latest_frame` | Nguồn chậm hơn `max_fps` → `dropped_frames = 0` |

## 7. Giả định

- *(giả định)* Backoff kết nối lại 1 s, 2 s, 4 s…, tối đa 10 s.
- *(giả định)* Hai khung cùng `ts_ms` thì khung sau +1 ms.
- *(giả định)* File hết khung là kết thúc, không phải `OFFLINE`.
- *(giả định)* Với file, giới hạn FPS chọn khung theo thời gian video (xác định).
- *(giả định)* `max_fps` là tham số của Camera Service, không nằm trong `engine.default.yaml`.
- *(giả định)* `probe` mặc định chạy 10 giây; quy tắc đoán loại nguồn ở R8.
- *(giả định)* Callback `on_status_change` để báo trạng thái cho worker.
- *(giả định)* Enum `CameraSourceType` dùng chung ở `postcare.schemas`; feature nào làm trước thì tạo.
- *(giả định)* "Đọc lỗi liên tiếp" = 5 lần `read()` lỗi liên tiếp (tham số `max_read_failures`).
- *(giả định)* Webcam/URL mở lần đầu lỗi: mặc định báo lỗi ngay (`SourceOpenError`, cho `probe`); `fail_fast=False` thì chuyển `OFFLINE` và tự kết nối lại (cho worker).
- *(giả định)* URL mở bằng backend FFMPEG, timeout mở/đọc 5 s.
- *(giả định)* File: `ts_ms` = chỉ số khung trong video × 1000 / FPS của file; nếu file không báo FPS thì dùng `CAP_PROP_POS_MSEC`.

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

Điều kiện bắt đầu: F00 `Done`; không còn câu hỏi mở. `CameraSourceType` và `CameraStatus` đã có sẵn ở `server/src/postcare/schemas/enums.py` (F00), F05 dùng lại, không sửa `schemas/`.

1. **Phụ thuộc OpenCV.** Thêm `opencv-contrib-python` (4.x) vào `dependencies` của `server/pyproject.toml` bằng `uv add`, khóa trong `uv.lock`. Lý do: F05 cần đọc webcam/URL/file (R9, PDF bảng §8); chọn bản `contrib` vì mediapipe (F11) kéo theo đúng gói này, tránh xung đột với `opencv-python`. Cập nhật cột "Phiên bản đã khóa" ở `tech-stack.md`. Commit `build(F05): add opencv-contrib-python`.
2. **Test trước** (`server/tests/camera/`, chạy trong `make check`, không cần camera/mạng; video tổng hợp hình khối bằng `cv2.VideoWriter` trong `tmp_path`, codec MJPG/AVI):
   - `test_file_source.py`: `test_open_source_dispatch` (3 loại + `source_type` sai → `ValueError`), `test_file_source_reads_all_frames`, `test_file_missing_cannot_open`, `test_timestamps_strictly_increasing`, `test_equal_timestamps_bumped_by_1ms`, `test_file_source_uses_video_time`, `test_file_source_deterministic`, `test_file_eof_is_not_offline`, `test_guess_source_type`.
   - `test_reconnect.py`: `test_reconnect_with_backoff` (capture giả: mở lỗi n lần rồi phục hồi; `sleep` và đồng hồ inject, kiểm dãy chờ 1, 2, 4, 8, 10, 10 s), `test_status_callback_order` (ONLINE → OFFLINE → ONLINE), `test_read_failures_trigger_offline`, `test_initial_open_failure_raises`.
   - `test_fps_limit.py`: `test_fps_limit_file_source` (30 fps → 15, `dropped_frames` = một nửa), `test_slow_file_source_drops_nothing`, `test_latest_frame_buffer_keeps_newest`, `test_live_source_returns_latest_frame` (luồng đọc thật + capture giả nhanh), `test_slow_live_source_drops_nothing`.
   - `test_cli_probe.py` (ở `server/tests/`): `test_probe_on_file_prints_stats`, `test_probe_bad_source_exits_nonzero`.
   - `FakeFrameSource` có test riêng ngắn (`test_fake_source.py`) vì F06 sẽ dùng.
   Chạy, xác nhận fail vì thiếu module `postcare.vision.camera`. Commit `test(F05): …`.
3. **`server/src/postcare/vision/camera.py`:** `Frame` (dataclass frozen: `image`, `ts_ms`, `frame_index`, `width`, `height`), `FrameSource` (Protocol: `open`, `read`, `close`, `status`, `stats`, `ended`), `SourceStats`, `SourceOpenError`, `Capture` (Protocol tối thiểu của `cv2.VideoCapture` để inject capture giả), `FileSource`, `WebcamSource`, `UrlSource` (chung lớp `_LiveSource`), `LatestFrameBuffer`, `guess_source_type`, `open_source`.
   - File: `ts_ms` = vị trí khung / FPS của video (không dùng đồng hồ máy); chọn khung theo "ô thời gian" `floor(i · max_fps / video_fps)` → xác định; khung bỏ đếm vào `dropped_frames`; hết khung → `read()` trả `None`, `ended = True`, trạng thái vẫn `ONLINE`.
   - Webcam/URL: luồng đọc nền giữ khung mới nhất (ghi đè khung chưa lấy → `dropped_frames += 1`); `read(timeout_s)` chờ khung mới và giãn cách ≥ 1/`max_fps`; `ts_ms` từ `time.monotonic_ns` tính từ lúc mở; mất nguồn (≥ `max_read_failures` lần đọc lỗi liên tiếp, mặc định 5 *(giả định)*) → `OFFLINE`, kết nối lại theo backoff 1, 2, 4… tối đa 10 s; `on_status_change(status)` gọi khi trạng thái đổi. Mở lần đầu lỗi → `SourceOpenError` (để `probe` báo lỗi ngay); `fail_fast=False` thì chuyển `OFFLINE` và để luồng nền tự kết nối lại (cho worker F06) *(giả định)*.
   - URL: backend FFMPEG với timeout mở/đọc 5 s *(giả định)* để mất mạng được phát hiện.
   - `ts_ms` luôn tăng ngặt: `ts = max(ts, ts_trước + 1)` (R3).
   - `server/src/postcare/vision/fake.py`: `FakeCapture` (giống `cv2.VideoCapture`, kịch bản mở lỗi / đọc lỗi) và `FakeFrameSource` (dãy `ts_ms` cho trước, giả lập `OFFLINE`).
   - Không ghi khung ra đĩa (R10). Module chỉ import `schemas`, `cv2`, `numpy`, stdlib (R9); `lint-imports` giữ xanh.
   Commit `feat(F05): …`.
4. **Lệnh `postcare probe`** trong `server/src/postcare/cli/main.py` (spec §4 ghi `cli.py`; repo hiện dùng gói `cli/`): `--source`, `--seconds` (10), `--max-fps` (15); đoán loại nguồn theo R8; in loại nguồn, độ phân giải, số khung, FPS (theo `ts_ms` và theo đồng hồ), số khung bỏ, số lần mất kết nối; `SourceOpenError` → thông báo rõ, exit 1. Commit `feat(F05): add probe command`.
5. **Tài liệu:** `tech-stack.md` (phiên bản khóa + lý do), `dev-setup.md` §5 và `camera-setup.md` §3 (cú pháp `probe` cho webcam, URL, file), `docs/02-architecture/overview.md` nếu tên file khác. Commit `docs(F05): …`.
6. **Kiểm chứng:** `make check` và `scripts\dev.ps1 check` exit 0; chạy tay `postcare probe` trên file ở `data/external/pexels/` (đường dẫn tuyệt đối, không chép media vào repo) và webcam index 0. Điện thoại (DroidCam/IP Webcam) và thử tắt app giữa chừng (AC3) cần người làm với thiết bị thật, ghi vào mục 10.

Ngoài phạm vi, không làm ở F05: phát lại file với tốc độ thực `--realtime` (§2 → F30), heartbeat (F06), đo FPS pose (F11).

Rủi ro: codec `VideoWriter` khác nhau giữa Windows/Linux → test dùng MJPG/AVI (có sẵn trong wheel OpenCV); `CAP_PROP_FPS` của một số file trả 0 → dùng `CAP_PROP_POS_MSEC` dự phòng; luồng đọc nền phải dừng sạch khi `close()` (join có timeout).

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

### Kết quả triển khai (2026-11-17)

- Code: `server/src/postcare/vision/camera.py` (`Frame`, `FrameSource`, `SourceStats`, `SourceOpenError`, `Capture`, `FileSource`, `LiveSource` → `WebcamSource` / `UrlSource`, `LatestFrameBuffer`, `guess_source_type`, `open_source`), `server/src/postcare/vision/fake.py` (`FakeCapture`, `FakeFrameSource`), lệnh `probe` trong `server/src/postcare/cli/main.py`.
- Phụ thuộc mới: `opencv-contrib-python` 4.14.0.94 (kéo theo numpy 2.5.5), ghi ở `tech-stack.md`.
- Test (chạy trong `make check`, không cần camera/mạng; video tổng hợp MJPG/AVI trong `tmp_path`): `server/tests/camera/` (`test_file_source.py`, `test_reconnect.py`, `test_fps_limit.py`, `test_fake_source.py`) và `server/tests/test_cli_probe.py`: 28 test, xanh. Thêm ngoài kế hoạch: `test_single_read_failure_keeps_online`, `test_initial_open_failure_retries_when_not_fail_fast`, `test_url_source_uses_same_reconnect_logic`, `test_live_fps_limit_uses_injected_clock`, `test_default_max_fps_is_15`, `test_probe_respects_max_fps`.
- `make check` và `scripts\dev.ps1 check`: exit 0; import-linter 8 contract kept.

### Bằng chứng theo AC

- **AC1** — tự động: `test_open_source_dispatch` (WEBCAM/URL DroidCam, IP Webcam, RTSP/FILE), `test_open_source_rejects_invalid_type`, `test_file_source_reads_all_frames`, `test_file_missing_cannot_open`. Thủ công: webcam laptop index 0 và file Pexels đạt (dưới). **Chưa làm:** điện thoại DroidCam / IP Webcam (cần thiết bị thật trong cùng Wi-Fi).
- **AC2** — `test_timestamps_strictly_increasing`, `test_file_source_uses_video_time` (10 fps → 0, 100, 200… ms), `test_file_source_deterministic`, `test_equal_timestamps_bumped_by_1ms` (ca âm tính).
- **AC3** — tự động: `test_reconnect_with_backoff` (dãy chờ 1, 2, 4, 8, 10, 10 s; đồng hồ và hàm chờ inject), `test_status_callback_order`, `test_single_read_failure_keeps_online`, `test_file_eof_is_not_offline` (ca âm tính). **Chưa làm:** tắt app điện thoại khi đang `probe`.
- **AC4** — tự động: `test_probe_on_file_prints_stats`, `test_probe_bad_source_exits_nonzero`. Thủ công: file, webcam, URL sai và webcam index không có (dưới). **Chưa làm:** `probe` với URL điện thoại.
- **AC5** — `test_fps_limit_file_source` (60 khung 30 fps → 30 khung, `dropped_frames` = 30, ≤ 15 khung mỗi giây video), `test_slow_file_source_drops_nothing`, `test_latest_frame_buffer_keeps_newest`, `test_live_source_returns_latest_frame` (luồng đọc thật, `FakeCapture` nhanh hơn tốc độ đọc), `test_slow_live_source_drops_nothing`.

### Kiểm chứng thủ công (máy dev Windows 11, 2026-11-17)

| Lệnh `uv run postcare probe …` | Kết quả |
|---|---|
| `--source D:/PostCareAi/data/external/pexels/pexels-6010961.mp4 --seconds 10` | 1280x720, 243 khung xử lý, 162 khung bỏ, FPS theo `ts_ms` 14,8, hết file sau 0,8 s, exit 0 |
| `--source D:/PostCareAi/data/external/pexels/pexels-3753707.mp4 --seconds 3` | 1280x720, 322 khung, 749 khung bỏ, FPS theo `ts_ms` 15,1, exit 0 |
| `--source D:/PostCareAi/data/external/pexels/khong-co.mp4` | "Không mở được nguồn: Không tìm thấy file video…", exit 1 |
| `--source 0 --seconds 5` (webcam laptop) | `ONLINE`, 640x480, 69 khung trong 5,0 s, FPS 14,0 (theo `ts_ms`) / 13,7 (đồng hồ), 50 khung bỏ, 0 lần mất kết nối, exit 0 |
| `--source 7 --seconds 2` (không có webcam 7) | `OFFLINE`, "Không mở được nguồn…", exit 1 |
| `--source http://127.0.0.1:9/video --seconds 3` | timeout FFMPEG 5 s, `OFFLINE`, exit 1 |

Video Pexels chỉ đọc theo đường dẫn tuyệt đối (gitignored), không chép vào repo; `probe` không ghi khung ra đĩa.

### Việc còn lại trước khi `Done`

- Kiểm chứng tay với điện thoại (AC1, AC3, AC4): `uv run postcare probe --source http://<ip>:4747/video --seconds 60`, giữa chừng tắt app DroidCam rồi mở lại; kỳ vọng `Trạng thái: OFFLINE` rồi `ONLINE`, "Số lần mất kết nối: 1".
- Review theo `review.md`.

### Ghi chú cho người sau

- `--source file --realtime` (phát file theo tốc độ thực) **không** làm ở F05 theo mục 2 (→ F30); `probe` trên file đọc nhanh hết mức.
- `on_status_change` được gọi từ luồng đọc nền với webcam/URL; `close()` chuyển `OFFLINE` (có gọi callback) nhưng không tính là mất kết nối.
- `read()` của webcam/URL trả `None` khi chưa có khung trong `timeout_s` (mất nguồn hoặc nguồn chậm); chỉ `ended = True` mới là kết thúc. Worker F06 nên dùng `fail_fast=False` để camera chưa bật lúc khởi động vẫn được kết nối lại.
- mypy strict chưa bao gồm `postcare.vision` (theo cấu hình F00 chỉ `schemas`, `engine`).

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
