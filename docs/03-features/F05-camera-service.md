# F05 – Nguồn video (Camera Service)

| Thuộc tính | Giá trị |
|---|---|
| Mã | F05 |
| Trạng thái | Todo <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
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
- [ ] **AC2.** Mỗi khung có `ts_ms` tăng ngặt và `frame_index`. File video dùng thời gian của chính video: hai lần đọc cùng file cho cùng dãy `ts_ms`. *(ADR-0003)* — *Kiểm chứng:* test `test_timestamps_strictly_increasing`, `test_file_source_uses_video_time`, `test_file_source_deterministic`.
- [ ] **AC3.** Mất nguồn → `OFFLINE`, tự kết nối lại theo backoff; có lại nguồn → `ONLINE`; callback trạng thái được gọi đúng thứ tự. *(PRD NFR03)* — *Kiểm chứng:* test `test_reconnect_with_backoff` (capture giả lập lỗi rồi phục hồi; đồng hồ và hàm chờ được inject, không `sleep` thật); tắt app điện thoại khi đang `probe`, ghi kết quả vào mục 10.
- [ ] **AC4.** `postcare probe --source …` in FPS thực, độ phân giải, số khung bỏ; nguồn không mở được → exit khác 0. *(dev-setup.md §5; camera-setup.md §3; HS §8.2)* — *Kiểm chứng:* test `test_probe_on_file_prints_stats` (CliRunner của Typer), `test_probe_bad_source_exits_nonzero`; chạy tay với URL điện thoại.
- [ ] **AC5.** Giới hạn FPS xử lý (mặc định 15): không có hàng đợi khung cũ; khung bị bỏ được đếm. *(A03)* — *Kiểm chứng:* test `test_fps_limit_file_source` (video tổng hợp 30 fps → ≤15 khung/giây video, `dropped_frames` ≈ một nửa), `test_live_source_returns_latest_frame` (`FakeFrameSource` sinh nhanh hơn tốc độ đọc → nhận khung mới nhất, đếm khung bỏ).

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

## 8. Câu hỏi mở

- (Không)

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
