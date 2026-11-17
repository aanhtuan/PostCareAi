# F12 – Replay CLI và fixture

| Thuộc tính | Giá trị |
|---|---|
| Mã | F12 |
| Trạng thái | In review <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M1 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F11 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §12 (tr.13–14), §13 (tr.14), §13.1 (tr.14); HS §5.5, §8.1, §8.2; QA#27, QA#29; ADR-0003, ADR-0008 |

## 1. Mục tiêu

Cung cấp lệnh `postcare replay` chạy **cùng pipeline** với worker (Camera Service → pose adapter → engine) trên file video và ghi kết quả ra JSONL, không gọi API. PDF §12 đề xuất "dùng file video để xây và kiểm thử Event Engine trước, sau đó mới chuyển sang camera realtime". Replay là đầu vào của công cụ đánh giá trên tập phát triển (F16; HS §8.1–8.2; ADR-0008), giúp hiệu chỉnh ngưỡng có số liệu (HS §5.5). Từ kết quả replay, nhóm cắt các đoạn observation thành fixture test chỉ chứa toạ độ (testing.md §2), để test engine chạy xác định mà không cần video hay model.

## 2. Phạm vi

**Trong phạm vi**
- `postcare replay --video … --camera-config … --out runs/<id>/` → `observations.jsonl`, `events.jsonl`, `frames.jsonl`, cộng `run.json` (thông tin lần chạy).
- Chế độ `--from-observations`: chạy lại chỉ engine, không cần MediaPipe, kết quả giống hệt giữa các lần chạy.
- `--preview`: ghi video mp4 có vẽ skeleton, ROI, trạng thái vào `runs/<id>/`.
- Cắt đoạn observation làm fixture `server/tests/fixtures/<scenario>.jsonl`, kèm file kỳ vọng `.expected.json`.
- Định dạng file cấu hình camera dùng khi quay (`config/cameras/<setup>.yaml`).
- Khung test regression chạy engine trên mọi fixture.
- Hàm pipeline dùng chung giữa replay và worker.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Manifest, ground truth, tính metric (→ F16).
- Đánh giá chính thức với ngưỡng đã chốt (→ F29).
- Phát lại video như một camera realtime cho worker (→ F30).
- Chế độ hiển thị làm mờ / chỉ skeleton cho dashboard (→ F28). Preview ở đây chỉ là công cụ dev.
- Face trong replay (→ F25 bổ sung khi có face adapter).

## 3. Yêu cầu chi tiết

- **R1.** `postcare replay --video <path> --camera-config <yaml> --out runs/<id>/` *(PDF §12; overview.md §6)*:
  - đọc video bằng `FileSource` (F05, dùng thời gian của video);
  - chạy `MediaPipePoseAdapter` (F11) rồi `Engine.process()` (F10) cho từng khung;
  - ghi `observations.jsonl` (mỗi dòng một `FrameObservation`), `events.jsonl` (mỗi dòng một `EngineEvent` kèm `config_hash`), `frames.jsonl` (mỗi khung một dòng: `frame_index`, `ts_ms`, `body_state`, `observation_quality`, `activity_level`, `rest_status`, `face_status`, số người) *(giả định nội dung `frames.jsonl`; F16 dùng để tính coverage)*;
  - ghi `run.json`: đường dẫn video, `config_hash`, phiên bản code (commit nếu có), thời lượng video, số khung, FPS xử lý, số khung bỏ, CPU %/RAM MB *(giả định; HS §8.2: FPS, CPU/RAM, frame bỏ)*;
  - thư mục `--out` đã có dữ liệu → báo lỗi, trừ khi có `--overwrite` *(giả định)*.
- **R2.** Replay dùng **chung** code pipeline với worker: hàm `process_frame(frame, adapter, engine) -> (FrameObservation, EngineOutput)` đặt ở module dùng chung *(overview.md §6: "`replay` dùng **chung** pipeline `vision` + `engine` với worker")*. Vị trí đề xuất `postcare/pipeline.py` *(giả định: `vision` không được import `engine` nên không đặt trong `vision`; cập nhật bảng module của overview.md cùng PR)*.
- **R3.** File cấu hình camera `config/cameras/<setup>.yaml` gồm `roi_polygon` (toạ độ chuẩn hóa 0–1) và `thresholds` (override, có thể rỗng) *(evaluation.md §4)*. ROI kiểm tra bằng `validate_roi_polygon` (`postcare/schemas/roi.py`, F08) *(giả định: feature nào làm trước thì tạo hàm này)*; ngưỡng hợp nhất bằng `EngineConfig.load()` (F10). Sai định dạng → lỗi rõ, exit khác 0.
- **R4.** `postcare replay --from-observations runs/<id>/observations.jsonl --camera-config <yaml> --out runs/<id2>/` chạy lại chỉ engine, **không** import hay khởi tạo MediaPipe *(ADR-0008; overview.md §6 "nhanh, xác định")*.
- **R5.** Tính xác định: hai lần chạy `--from-observations` với cùng input và cùng cấu hình cho `events.jsonl` và `frames.jsonl` **giống hệt từng byte** *(event-engine.md §1 "Engine xác định")*. Muốn vậy:
  - không ghi thời gian thực (đồng hồ máy) vào hai file này; thời gian chỉ lấy từ `ts_ms`;
  - số liệu phụ thuộc máy (FPS xử lý, CPU, RAM, thời điểm chạy) chỉ ghi vào `run.json` *(giả định)*;
  - JSON ghi theo thứ tự trường cố định, mã hóa UTF-8, xuống dòng LF.
- **R6.** `--preview` ghi `runs/<id>/preview.mp4`: khung gốc có vẽ skeleton của mọi người, polygon ROI, `body_state` và `observation_quality` hiện tại, và nhãn sự kiện vừa phát *(PDF §12; giả định nội dung vẽ)*. Thư mục `runs/` đã nằm trong `.gitignore`. Hàm vẽ ở `postcare/vision/render.py` *(overview.md: `vision.render`)*. Đây là công cụ dev, không phải UI người dùng cuối; nhãn vẽ dùng mã nội bộ được *(giả định)*.
- **R7.** Cắt fixture *(testing.md §2)*:
  - `postcare replay --from-observations <file> --start-s <a> --end-s <b> --save-observations server/tests/fixtures/<scenario>.jsonl` ghi các observation trong khoảng [a, b] *(giả định tên tham số)*;
  - `--save-expected` ghi thêm `server/tests/fixtures/<scenario>.expected.json` là danh sách sự kiện (`code`, `occurred_at_ms`) engine phát ra trên đoạn đó; người làm feature xem lại file này so với ground truth trước khi commit *(giả định)*;
  - fixture **chỉ chứa toạ độ** và các trường của `FrameObservation`, không chứa ảnh, pixel hay đường dẫn tới video *(testing.md §2; QA#29)*.
- **R8.** Test regression `server/tests/engine/test_fixtures_regression.py`: với mỗi `*.jsonl` trong `server/tests/fixtures/` có file `.expected.json` đi kèm, chạy engine và so danh sách sự kiện *(testing.md §2)*. Chưa có fixture nào → test này không thu ca nào và không làm đỏ `make check`.
- **R9.** Replay không gọi API và không cần DB *(overview.md §3: `replay` không import `api`, `db`)*.
- **R10.** Video nguồn nằm ngoài git (`data/`); không ghi khung hình nào ra file ngoài `preview.mp4` khi người dùng yêu cầu *(QA#27, QA#29)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/replay/__init__.py`, `replay/runner.py` (chạy video hoặc từ observations), `replay/writers.py` (JSONL, `run.json`), `replay/fixtures.py` (cắt đoạn, ghi expected).
  - `server/src/postcare/replay/camera_config.py` (đọc `config/cameras/<setup>.yaml`) *(giả định tên file)*.
  - `server/src/postcare/pipeline.py` (`process_frame`) *(giả định vị trí)*.
  - `server/src/postcare/vision/render.py`: `draw_debug_overlay()`.
  - `server/src/postcare/cli.py`: lệnh `replay`.
  - `config/cameras/example.yaml` (ROI mẫu, không có dữ liệu người).
  - Test: `server/tests/replay/test_from_observations_deterministic.py`, `test_replay_outputs.py` (dùng `FakeFrameSource` + `FakePoseAdapter`), `test_fixture_cut.py`, `server/tests/engine/test_fixtures_regression.py`; test vision `server/tests/vision/test_replay_video.py` (marker `vision`).
- **Dữ liệu:** không có bảng. Đầu ra trong `runs/` (gitignore); fixture trong `server/tests/fixtures/` (commit, chỉ toạ độ).
- **API:** không có.
- **UI:** không có.
- **Cấu hình:** `config/cameras/<setup>.yaml`; `config/engine.default.yaml` (xem [event-engine.md §6](../02-architecture/event-engine.md#6-cấu-hình-và-ngưỡng-mặc-định), [evaluation.md §4](../04-guides/evaluation.md#4-định-dạng-file)).

## 5. Acceptance criteria

- [x] **AC1.** `postcare replay --video X --camera-config cam.yaml --out runs/<id>/` xuất `observations.jsonl`, `events.jsonl`, `frames.jsonl` và `run.json`; mỗi dòng JSONL parse được bằng schema tương ứng. *(PDF §12; overview.md §6)* — *Kiểm chứng:* test `test_replay_writes_all_outputs` (`FakeFrameSource` + `FakePoseAdapter`, chạy trong `make check`); test vision `test_replay_real_video` trên video trong `data/` (`make test-vision`).
- [x] **AC2.** `--from-observations` chạy lại engine không cần MediaPipe; 2 lần chạy cho `events.jsonl` và `frames.jsonl` giống hệt từng byte. *(ADR-0008; event-engine.md §1)* — *Kiểm chứng:* test `test_from_observations_deterministic` (so sánh byte), `test_from_observations_does_not_import_mediapipe` (kiểm tra `sys.modules`).
- [x] **AC3.** `--preview` ghi `runs/<id>/preview.mp4` có vẽ skeleton, ROI và trạng thái; `runs/` nằm trong `.gitignore`. *(PDF §12)* — *Kiểm chứng:* test `test_preview_writes_mp4` (đọc lại bằng OpenCV: đúng số khung, kích thước); xem tay một preview trên video thật, ghi vào mục 10.
- [x] **AC4.** Lệnh cắt đoạn observation tạo fixture `server/tests/fixtures/<scenario>.jsonl` chỉ chứa toạ độ (không ảnh), kèm `.expected.json`; test regression chạy engine trên mọi fixture. *(testing.md §2; HS §8.1; QA#29)* — *Kiểm chứng:* test `test_fixture_cut_range`, `test_fixture_contains_only_observation_fields`, `test_fixtures_regression` (với một fixture tổng hợp nhỏ tạo bằng builder hoặc tay).

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit + vision | `test_replay_writes_all_outputs`; `test_replay_real_video` (marker `vision`) | `--out` đã có dữ liệu, không có `--overwrite` → lỗi; `camera-config` sai ROI → exit khác 0 |
| AC2 | unit | `test_from_observations_deterministic`, `test_from_observations_does_not_import_mediapipe` | `observations.jsonl` hỏng một dòng → lỗi nêu số dòng *(giả định)* |
| AC3 | unit + thủ công | `test_preview_writes_mp4` | Không có `--preview` → không tạo file mp4 |
| AC4 | unit | `test_fixture_cut_range`, `test_fixture_contains_only_observation_fields`, `test_fixtures_regression` | Khoảng `--start-s` > `--end-s` → lỗi; fixture không có `.expected.json` → bị bỏ qua có thông báo |

## 7. Giả định

- *(giả định)* Nội dung `frames.jsonl` và `run.json` ở R1.
- *(giả định)* `--out` đã có dữ liệu → lỗi trừ khi `--overwrite`.
- *(giả định)* Hàm pipeline dùng chung đặt ở `postcare/pipeline.py`; cập nhật bảng module của overview.md cùng PR.
- *(giả định)* Số liệu phụ thuộc máy chỉ ghi vào `run.json` để giữ hai file kết quả xác định.
- *(giả định)* Tên tham số `--start-s`, `--end-s`, `--save-observations`, `--save-expected`.
- *(giả định)* File `.expected.json` do lệnh sinh ra và được người xem lại trước khi commit.
- *(giả định)* Preview dùng mã nội bộ trong nhãn vẽ (công cụ dev).
- *(giả định)* `validate_roi_polygon` dùng chung với F08; feature nào làm trước thì tạo. F12 đã tạo trong `schemas/roi.py`; `RoiPolygon` giữ nguyên kiểm tra của F10.
- *(giả định)* Gói `postcare.pipeline` đã có sẵn từ F00, nên `process_frame` đặt ở `postcare/pipeline/__init__.py` thay vì `postcare/pipeline.py`.
- *(giả định)* `frames.jsonl` ghi `persons` = số người adapter thấy (kể cả ngoài ROI).
- *(giả định)* File cấu hình camera có `version: 1`, `camera_id` tuỳ chọn (mặc định 0), `notes` tuỳ chọn; khóa lạ là lỗi. `--from-observations` dùng `camera_id` của observation đầu tiên.
- *(giả định)* `.expected.json` lưu kèm `camera` (ROI, `thresholds`) để test regression chạy không cần file cấu hình ngoài; `config_hash` chỉ để tham khảo, không so.
- *(giả định)* `--start-s`/`--end-s` lọc theo `ts_ms` trong đoạn đóng [a, b]; fixture giữ nguyên `ts_ms`, `frame_index` gốc.
- *(giả định)* Nhãn sự kiện trên preview giữ 2 s sau `detected_at_ms` (chỉ để xem, không phải ngưỡng engine).
- *(giả định)* ROI của các cấu hình camera cho clip ngoài (`config/cameras/pexels-8090735.yaml`, `mixkit-29966.yaml`, `gmdcsa24-subject1.yaml`) ước lượng bằng mắt từ một khung.

## 8. Câu hỏi mở

- Chưa quay tập dev (task không phải code, tuần 3 theo ADR-0008) thì AC1 phần video thật và AC3 phần xem tay chỉ kiểm chứng được trên video thử của nhóm. **Không chặn** code; chặn việc tick phần kiểm chứng thủ công.

## 9. Kế hoạch triển khai

Lập ngày 2026-11-18 (builder F12). Xây trên API engine hiện tại `Engine(config, EngineContext).process(obs)`; không sửa `engine/` (F14 đang sửa state machine).

1. **Docs plan** (commit `docs(F12): plan`): mục này, trạng thái In progress.
2. **Test trước** (commit `test(F12): ...`), chạy và xác nhận đỏ vì thiếu module. Không có media trong test: `FakeFrameSource` (F05) + `FakePoseAdapter` (F11) + builder `PoseSequence` (F13).
   - `server/tests/replay/test_replay_outputs.py` (AC1): `test_replay_writes_all_outputs` (4 file, mỗi dòng parse bằng `FrameObservation` / `EventRecord` / `FrameRecord`, `run.json` đủ khóa); `--out` có dữ liệu mà không `--overwrite` → lỗi; `--overwrite` → ghi lại; pipeline dùng chung `process_frame`.
   - `server/tests/replay/test_camera_config.py` (R3): đọc YAML hợp lệ; ROI sai (ít điểm, ngoài [0, 1], tự cắt, diện tích 0), khóa lạ, ngưỡng override sai → `CameraConfigError` có đường dẫn khóa; CLI exit ≠ 0; mọi `config/cameras/*.yaml` trong repo hợp lệ.
   - `server/tests/schemas/test_roi_validate.py`: `validate_roi_polygon` (polygon lồi, lõm hợp lệ; tự cắt, trùng điểm, thẳng hàng → lỗi).
   - `server/tests/replay/test_from_observations_deterministic.py` (AC2): `test_from_observations_deterministic` (2 lần chạy, so byte `events.jsonl`, `frames.jsonl`; LF, UTF-8); `test_from_observations_does_not_import_mediapipe` (subprocess, kiểm `sys.modules`); dòng JSONL hỏng → lỗi nêu số dòng; writer giữ thứ tự trường cố định.
   - `server/tests/replay/test_preview.py` (AC3): `test_preview_writes_mp4` (đọc lại bằng OpenCV: số khung, kích thước); không `--preview` → không có mp4; `--preview` cùng `--from-observations` → lỗi (không có ảnh); `draw_debug_overlay` không sửa ảnh gốc.
   - `server/tests/replay/test_fixture_cut.py` (AC4): `test_fixture_cut_range` (chỉ giữ `start_s ≤ ts ≤ end_s`), `test_fixture_contains_only_observation_fields` (chỉ khóa của `FrameObservation`, không đường dẫn video), `.expected.json` đúng định dạng; `--start-s > --end-s` → lỗi; fixture không có `.expected.json` → bị bỏ qua có lý do.
   - `server/tests/engine/test_fixtures_regression.py` (R8): mỗi `server/tests/fixtures/*.jsonl` có `.expected.json` → chạy engine, so danh sách `(code, occurred_at_ms)`; thiếu expected → skip có lý do; không có fixture → 0 ca.
   - `server/tests/vision/test_replay_video.py` (marker `vision`): `test_replay_real_video` trên clip trong `data/` với model thật; thiếu model/video → skip.
3. **ROI:** `validate_roi_polygon` trong `postcare/schemas/roi.py` *(giả định của spec: feature nào làm trước thì tạo; F08 dùng lại)*.
4. **Pipeline dùng chung:** `postcare/pipeline/__init__.py` (gói đã có sẵn từ F00) với `process_frame(frame, adapter, engine) -> (FrameObservation, EngineOutput)`; `camera_id` lấy từ `engine.context`. Chỉ phụ thuộc interface `PoseAdapter`, không import mediapipe.
5. **Replay:** `postcare/replay/`:
   - `camera_config.py`: `CameraConfig` (`version: 1`, `camera_id` mặc định 0, `roi_polygon`, `thresholds`, `notes`), `load_camera_config()`, `engine_config()` hợp nhất bằng `EngineConfig.load(default, overrides)`.
   - `writers.py`: JSONL thứ tự trường cố định, UTF-8, LF; `EventRecord` (= `EngineEvent` + `config_hash`), `FrameRecord`; `run.json` (số liệu phụ thuộc máy chỉ ở đây).
   - `runner.py`: `replay_video(source, adapter, …)` và `replay_observations(path, …)`; đo FPS xử lý, CPU %, RAM MB bằng psutil (đã có từ F11); `--out` có dữ liệu → `OutputExistsError` trừ khi `overwrite`.
   - `fixtures.py`: đọc observation JSONL (lỗi nêu số dòng), cắt khoảng, ghi fixture + `.expected.json` (`camera` gồm `camera_id`, `roi_polygon`, `thresholds`; `events` gồm `code`, `occurred_at_ms`; không ghi đường dẫn video), khám phá fixture cho test regression.
6. **Render:** `postcare/vision/render.py` `draw_debug_overlay(image, obs, roi, state, events)` vẽ skeleton mọi người, ROI, `body_state`/`observation_quality`, nhãn sự kiện gần nhất (giữ 2 s theo `ts_ms`, *(giả định)*). Ghi mp4 bằng `cv2.VideoWriter` (`mp4v`).
7. **CLI:** `postcare replay` trong `cli/main.py` (`--video | --from-observations`, `--camera-config`, `--out`, `--overwrite`, `--preview`, `--engine-config`, `--model`, `--models-dir` (mặc định `POSTCARE_MODELS_DIR` hoặc `models/`), `--max-fps` (mặc định 15, A03), `--start-s`, `--end-s`, `--save-observations`, `--save-expected`). Import adapter MediaPipe chỉ trong nhánh `--video`.
8. **Cấu hình camera:** `config/cameras/example.yaml` (ROI mẫu) và cấu hình cho vài clip ngoài (Pexels giường, GMDCSA24, CAUCAFall), ROI ước lượng từ một khung *(giả định)*.
9. **Fixture tổng hợp:** `server/tests/fixtures/synthetic_lying_occluded.jsonl` + `.expected.json` sinh bằng builder qua chính hàm ghi fixture (chỉ toạ độ).
10. **Docs:** overview.md (pipeline, replay), dev-setup.md và evaluation.md (cách chạy replay, cắt fixture), testing.md (fixture, regression, test vision F12).
11. **Kiểm tra:** `make check`, `scripts\dev.ps1 check`, `make test-vision`; replay thủ công 2–3 clip trong `D:\PostCareAi\data\external` (đường dẫn tuyệt đối, model qua `POSTCARE_MODELS_DIR`); ghi kết quả mục 10, trạng thái In review.

Rủi ro: codec `mp4v` có thể thiếu trên Linux → test preview kiểm tra file đọc lại được; engine chưa có rule (F15) nên `events.jsonl` trên video thật hiện rỗng, kiểm chứng sự kiện để F15.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

Ngày 2026-11-18, nhánh `feat/F12-replay-cli`, Windows 11, i5-10300H, model pose `full` (CPU).

**AC1:**
- `tests/replay/test_replay_outputs.py` xanh: `test_replay_writes_all_outputs` (`FakeFrameSource` + `FakePoseAdapter`; 4 file, mỗi dòng parse bằng `FrameObservation` / `EventRecord` / `FrameRecord`, `run.json` đủ khóa); `--out` có dữ liệu mà không `--overwrite` → exit ≠ 0, có `--overwrite` → ghi lại; ROI tự cắt → exit ≠ 0, không ghi file; thiếu model → exit ≠ 0 kèm gợi ý `make models`; `test_process_frame_is_shared_pipeline`.
- `tests/replay/test_camera_config.py`: ROI sai (ít điểm, ngoài [0, 1], tự cắt, thẳng hàng), `version` sai, khóa lạ, ngưỡng sai kiểu/khối lạ → `CameraConfigError` nêu đường dẫn khóa; mọi `config/cameras/*.yaml` hợp lệ. `tests/schemas/test_roi_validate.py` cho `validate_roi_polygon`.
- Vision `test_replay_real_video` (`make test-vision`, `POSTCARE_DATA_DIR=D:/PostCareAi/data`, `POSTCARE_MODELS_DIR=D:/PostCareAi/models`): 5 passed (4 của F11 + 1 của F12).

**AC2:** `test_from_observations_deterministic` (so byte `events.jsonl`, `frames.jsonl`, `observations.jsonl`; không có CRLF), chạy lại từ `observations.jsonl` của một lần chạy cho cùng `frames.jsonl`; `test_from_observations_does_not_import_mediapipe` (subprocess, `sys.modules` không có `mediapipe`); dòng hỏng → lỗi "dòng 3"; `test_event_line_has_fixed_field_order`.

**AC3:** `test_preview_writes_mp4` (OpenCV đọc lại: đủ 180 khung, 320×180); không `--preview` → không có mp4; `--preview` cùng `--from-observations` → exit ≠ 0. Xem tay `preview.mp4` của `pexels-8090735`: skeleton khớp người, ROI vàng quanh giường, góc trái hiện `NO_OBSERVATION | GOOD`, `t=…s #… persons=1`. `runs/` có trong `.gitignore`.

**AC4:** `test_fixture_cut_range`, `test_fixture_contains_only_observation_fields`, khoảng ngược / rỗng → exit ≠ 0, `--save-expected` thiếu `--save-observations` → exit ≠ 0, fixture thiếu `.expected.json` → skip có lý do, `test_cut_fixture_passes_regression`. `tests/engine/test_fixtures_regression.py` chạy trên fixture tổng hợp `synthetic_sit_occluded` (150 khung, 10 fps, ~100 KB). Cắt thử trên clip thật: `pexels-8090735` 2–6 s → 60 khung, file không chứa đường dẫn video.

**Replay thủ công** (đường dẫn tuyệt đối tới `D:\PostCareAi\data\external`, kết quả trong scratchpad, không commit; `--max-fps 15`, `--preview`):

| Clip | Cấu hình camera | Thời lượng | Khung xử lý / bỏ | `observation_quality` | Sự kiện | FPS xử lý | CPU | RAM đỉnh |
|---|---|---|---|---|---|---|---|---|
| `pexels/pexels-8090735.mp4` | `pexels-8090735.yaml` | 7,7 s | 115 / 69 | GOOD 92, NO_PERSON 22, LOW_CONFIDENCE 1 | 0 | 17,7 | 125 % | 294 MB |
| `gmdcsa24/…/Subject 1/ADL/04.mp4` | `gmdcsa24-subject1.yaml` | 5,8 s | 87 / 83 | GOOD 87 | 0 | 17,5 | 122 % | 286 MB |
| `mixkit/mixkit-29966.mp4` | `mixkit-29966.yaml` | 25,1 s | 377 / 225 | GOOD 354, NO_PERSON 20, MULTIPLE_PEOPLE 2, LOW_CONFIDENCE 1 | 0 | 13,0 | 107 % | 290 MB |

- Lần chạy video (trước khi merge F14): `body_state` luôn `NO_OBSERVATION`, đúng với engine lúc đó.
- Sau khi merge `main` có F14, chạy lại `--from-observations` trên cùng `observations.jsonl` (không cần MediaPipe): `pexels-8090735` NO_OBSERVATION 50 / AT_EDGE 65; `gmdcsa24` ADL/04 NO_OBSERVATION 35 / RAISING 29 / AT_EDGE 23; `mixkit-29966` NO_OBSERVATION 45 / LYING 87 / AT_EDGE 245 khung. Vẫn 0 sự kiện vì rule F15 chưa có. ROI của các clip này là ước lượng, nên trạng thái chưa dùng để kết luận độ chính xác (để F15/F16).
- `--from-observations` trên `observations.jsonl` của `pexels-8090735`: `frames.jsonl`, `events.jsonl` giống hệt từng byte bản chạy video (`cmp`).

**Kiểm tra cuối:** `make check` xanh (387 passed trước merge; 446 passed sau khi merge `main` có F14; 10 contract KEPT, web build xong); `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check` exit 0; `make test-vision` 5 passed. Hai lệnh check chạy với `TEST_DATABASE_URL=.../postcare_f11_test` (DB test riêng của builder).

**Người sau cần biết:**
- Worker (F17) gọi `postcare.pipeline.process_frame(frame, adapter, engine)`, không tự ghép adapter + engine.
- Khi F15 thêm rule: cắt fixture từ clip thật bằng lệnh ở dev-setup.md §7, xem lại `.expected.json` so với ground truth rồi commit; `synthetic_sit_occluded.expected.json` có thể cần sinh lại nếu rule phát sự kiện trên chuỗi đó.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
