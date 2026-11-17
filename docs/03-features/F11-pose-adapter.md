# F11 – Pose adapter MediaPipe

| Thuộc tính | Giá trị |
|---|---|
| Mã | F11 |
| Trạng thái | In progress <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M1 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F05, F10 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §6.1 (tr.7), §10 (tr.12), §17 (tr.17–18); HS §5.2, §5.5, §8.2; QA#20, QA#23; A04, A07; ADR-0003 |

## 1. Mục tiêu

Tích hợp MediaPipe Pose Landmarker đã huấn luyện sẵn (không train, không đổi trọng số: HS §5.5; PDF §6.1) qua một adapter chuyển output về schema chung `FrameObservation` (F10). Nhờ vậy engine và giao diện không phụ thuộc MediaPipe; đổi model sau này chỉ cần viết adapter mới (PDF §10; HS §6.1; ADR-0003). Feature này cũng đo FPS thực tế trên CPU để chứng minh prototype chạy ổn định trên phần cứng được công bố (HS §8.2) và để phát hiện sớm rủi ro "pose kém hoặc chậm" (ADR-0003 "Hệ quả").

## 2. Phạm vi

**Trong phạm vi**
- `make models`: tải file model pose `.task` vào `models/` và kiểm tra checksum (thay target giữ chỗ của F00).
- Interface `PoseAdapter` và cài đặt `MediaPipePoseAdapter` (Tasks API, chế độ VIDEO).
- Ánh xạ 33 landmark của MediaPipe sang `KeypointName` trung lập.
- `FakePoseAdapter` cho test không cần model.
- Test marker `vision` chạy bằng `make test-vision`.
- Đo FPS ở 720p trên CPU máy dev, ghi vào tech-stack.md.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Face Landmarker (→ F25).
- Chọn người mục tiêu, đặc trưng, chất lượng quan sát (→ F13). Adapter trả mọi người model thấy.
- Replay và ghi JSONL (→ F12).
- Chạy pose trong worker realtime (→ F17).
- MMPose/RTMPose, GPU *(PDF §6.1, §17: chỉ là phương án dự phòng; QA#23: chỉ CPU)*.
- Tự train hoặc fine-tune *(PRD §5.3)*.

## 3. Yêu cầu chi tiết

- **R1.** `make models` gọi lệnh Python `postcare models` (chạy được trên Windows và Linux, không dùng `curl`/`wget`) *(coding-standards.md §1 "Đa nền tảng")*:
  - đọc danh sách model từ một file manifest (URL, tên file, sha256) *(giả định: `config/models.yaml`)*;
  - tải vào `models/` (đã có trong `.gitignore`); file đã có và đúng checksum → bỏ qua;
  - sai checksum → xóa file tải dở, báo lỗi, exit khác 0;
  - URL trỏ tới bản có số phiên bản cố định, không dùng `latest`, để checksum không đổi *(giả định)*.
- **R2.** Biến thể model mặc định là `pose_landmarker_full` *(giả định)*; bản `lite` cũng có trong manifest để so sánh FPS *(giả định: phương án giảm tải khi FPS thấp)*. Chọn biến thể bằng tham số, không viết cứng.
- **R3.** `PoseAdapter` (Protocol) ở `postcare/vision/inference/base.py`: `observe(frame: Frame, camera_id: int) -> FrameObservation` và `close()` *(ADR-0003: "Adapter chuyển output sang `FrameObservation`")*.
- **R4.** `MediaPipePoseAdapter` *(ADR-0003; A04)*:
  - dùng `mediapipe.tasks.vision.PoseLandmarker`, `running_mode = VIDEO`, gọi `detect_for_video(image, ts_ms)` với `ts_ms` của khung (F05 đảm bảo tăng ngặt);
  - `num_poses` lấy từ `EngineConfig.pose.num_poses` (mặc định 2, A04; QA#20);
  - chuyển BGR → RGB trước khi đưa vào model;
  - mỗi người → một `PersonPose`; mỗi `KeypointName` lấy từ landmark tương ứng; `x`, `y` đã chuẩn hóa được kẹp vào [0, 1], `visibility` lấy từ model *(giả định kẹp toạ độ; F13 dùng visibility để đánh giá chất lượng)*;
  - `persons` rỗng khi model không thấy ai; `source_ok = true`; `face = None`.
- **R5.** Kiểu dữ liệu MediaPipe **không lộ ra ngoài adapter** *(PDF §10)*:
  - output chỉ gồm kiểu của `postcare.schemas`;
  - thêm contract import-linter: chỉ `postcare.vision.inference` được import `mediapipe` *(giả định: siết thêm so với overview.md §3, nơi cả `vision` được import mediapipe)*.
- **R6.** Hàm ánh xạ landmark → `PersonPose` tách riêng, nhận dữ liệu dạng danh sách (x, y, visibility) theo chỉ số MediaPipe, để unit test chạy được **không cần** model *(giả định; testing.md: test engine không gọi MediaPipe)*. Bảng ánh xạ chỉ số MediaPipe → `KeypointName` đặt ở một chỗ duy nhất.
- **R7.** Model không có hoặc không mở được → lỗi rõ ràng gợi ý chạy `make models` *(giả định)*.
- **R8.** `FakePoseAdapter` trả `FrameObservation` dựng sẵn theo `frame_index`, dùng cho test tích hợp worker/replay *(testing.md §1)*.
- **R9.** Test marker `vision` ở `server/tests/vision/`, chạy bằng `make test-vision` *(testing.md §1)*:
  - dùng model trong `models/` và ảnh hoặc video trong `data/vision/` *(giả định thư mục con)*;
  - thiếu model hoặc thiếu file → `pytest.skip` với lý do rõ;
  - `make check` và CI **không** chạy các test này.
- **R10.** Đo hiệu năng: `postcare probe --source <file|webcam|url> --pose [--model full|lite]` in FPS xử lý (khung đã chạy pose / giây), CPU % và RAM MB (psutil) *(HS §8.2; giả định: mở rộng lệnh `probe` của F05)*. Kết quả 720p trên CPU máy dev ghi vào bảng "Kết quả đo hiệu năng" của tech-stack.md; so với mục tiêu ≥10 FPS *(A07)*.
- **R11.** Không lưu ảnh hay khung hình nào khi chạy adapter *(QA#29)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/vision/inference/__init__.py`, `inference/base.py` (`PoseAdapter`), `inference/pose_mediapipe.py` (`MediaPipePoseAdapter`), `inference/mapping.py` (bảng chỉ số MediaPipe → `KeypointName`, hàm ánh xạ), `inference/fake.py` (`FakePoseAdapter`).
  - `server/src/postcare/vision/models.py` (tải và kiểm tra checksum) *(giả định tên file)*; `config/models.yaml`.
  - `server/src/postcare/cli.py`: lệnh `models`; thêm `--pose`, `--model` cho `probe`.
  - `server/.importlinter`: contract mới cho `mediapipe`.
  - `Makefile`: target `models` thật.
  - Test: `server/tests/inference/test_mapping.py`, `test_models_download.py` (không cần mạng: dùng file và checksum giả trong `tmp_path`), `server/tests/vision/test_pose_adapter.py` (marker `vision`).
- **Dữ liệu:** không có bảng. File model trong `models/`, dữ liệu thử trong `data/` (không commit).
- **API:** không có.
- **UI:** không có.
- **Cấu hình:** `pose.num_poses` trong `config/engine.default.yaml` (A04); `config/models.yaml` *(giả định)*.

## 5. Acceptance criteria

- [ ] **AC1.** `make models` tải model pose `.task` vào `models/` (gitignore) và kiểm tra checksum; chạy lại không tải lại; sai checksum → lỗi và exit khác 0. *(ADR-0003)* — *Kiểm chứng:* test `test_models_skip_when_checksum_ok`, `test_models_checksum_mismatch_fails` (không cần mạng); chạy tay `make models` trên Windows và Linux.
- [ ] **AC2.** Adapter dùng chế độ VIDEO, `num_poses = 2` (lấy từ cấu hình), trả `FrameObservation` theo schema chung; kiểu dữ liệu MediaPipe không lộ ra ngoài adapter. *(A04; PDF §10)* — *Kiểm chứng:* unit test `test_mapping_mediapipe_to_keypoint_names`, `test_mapping_clamps_coordinates`; `make lint-imports` có contract "chỉ `vision.inference` import `mediapipe`"; test vision `test_adapter_returns_schema_types_only`.
- [ ] **AC3.** Có test `@pytest.mark.vision` chạy bằng `make test-vision` trên ảnh hoặc video trong `data/`; thiếu file thì skip; CI không chạy. *(testing.md §1)* — *Kiểm chứng:* `make test-vision` trên máy có model và dữ liệu (ghi kết quả vào mục 10); trên máy không có model, `make test-vision` báo skip và exit 0; `make check` không thu test `vision`.
- [ ] **AC4.** Đo FPS ở 720p trên CPU máy dev (biến thể `full` và `lite`), ghi vào bảng "Kết quả đo hiệu năng" của tech-stack.md, kèm CPU % và RAM MB. *(HS §8.2; A07)* — *Kiểm chứng:* chạy `postcare probe --source <video 720p> --pose`; tech-stack.md có ít nhất một dòng đo của F11.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit | `test_models_download.py` (file giả, checksum giả) | Sai checksum → xóa file, exit khác 0 |
| AC1 | thủ công | `make models` trên Windows và Linux | — |
| AC2 | unit | `test_mapping.py` | Landmark ngoài khung (x < 0 hoặc > 1) → kẹp vào [0, 1]; thiếu landmark → lỗi rõ |
| AC2 | lệnh | `make lint-imports` | Thêm tạm `import mediapipe` vào `postcare.vision.camera` → lỗi |
| AC3 | vision | `test_pose_adapter.py`: ảnh có 1 người → 1 `PersonPose`; khung trống → `persons = []` | Thiếu model hoặc dữ liệu → skip |
| AC3 | vision | `test_adapter_rejects_non_increasing_ts` | `ts_ms` không tăng → lỗi rõ (không để MediaPipe báo lỗi khó hiểu) |
| AC4 | thủ công | `postcare probe --pose` trên video 720p | — |

## 7. Giả định

- *(giả định)* Manifest model ở `config/models.yaml`, URL có số phiên bản cố định.
- *(giả định)* Biến thể mặc định `pose_landmarker_full`; có thêm `lite` để so sánh.
- *(giả định)* Toạ độ landmark được kẹp vào [0, 1]; visibility giữ nguyên giá trị model.
- *(giả định)* Contract import-linter mới: chỉ `postcare.vision.inference` import `mediapipe`.
- *(giả định)* Dữ liệu thử cho test vision ở `data/vision/`.
- *(giả định)* Đo hiệu năng bằng cờ `--pose` của lệnh `probe`.

## 8. Câu hỏi mở

- Nhóm cần cung cấp ít nhất một ảnh hoặc video 720p có người (đã đồng ý quay, HS §6.3) đặt ở `data/vision/` để chạy AC3, AC4. Chưa có dữ liệu thì AC3 chỉ kiểm chứng được nhánh skip. **Chặn** việc tick AC3 và AC4, không chặn code.

## 9. Kế hoạch triển khai

Lập ngày 2026-11-17 (builder F11). Bổ sung so với mục 3: QA#35 yêu cầu so cả `heavy`, và chọn biến thể mặc định bằng benchmark (thay giả định "mặc định `full`" của R2 nếu số đo khác).

1. **Docs plan** (commit `docs(F11): plan`): mục này, trạng thái In progress.
2. **Test trước** (commit `test(F11): ...`), chạy và xác nhận đỏ vì thiếu module:
   - `server/tests/inference/test_mapping.py`: đủ 21 `KeypointName` lấy đúng chỉ số MediaPipe (0 mũi, 2/5 mắt, 7/8 tai, 11–16 vai/khuỷu/cổ tay, 23–28 hông/gối/cổ chân, 29/30 gót, 31/32 mũi bàn chân); kẹp x, y, visibility ngoài [0, 1]; thiếu landmark (≠ 33) → `ValueError` rõ; output chỉ là kiểu `postcare.schemas`.
   - `server/tests/inference/test_fake_adapter.py`: `FakePoseAdapter` trả quan sát dựng sẵn theo `frame_index`, khung không có → `persons = []`.
   - `server/tests/inference/test_adapter_unit.py`: `MediaPipePoseAdapter` với landmarker giả (inject) — BGR→RGB, `detect_for_video` nhận đúng `ts_ms`, `num_poses` từ `EngineConfig`, `ts_ms` không tăng → `ValueError` trước khi gọi model; thiếu file model → lỗi gợi ý `make models`.
   - `server/tests/inference/test_models_download.py`: manifest giả + URL `file://` trong `tmp_path` (không cần mạng): `test_models_skip_when_checksum_ok`, `test_models_checksum_mismatch_fails` (xóa file, exit ≠ 0), tải mới khi thiếu; manifest thật `config/models.yaml` hợp lệ (URL có số phiên bản, không `latest`, sha256 64 hex, `default` là một biến thể có trong danh sách).
   - `server/tests/vision/test_pose_adapter.py` (marker `vision`, thay `test_placeholder.py`): model thật trên clip trong `data/` → có `PersonPose`; khung đen → `persons = []`; `test_adapter_returns_schema_types_only`; `test_adapter_rejects_non_increasing_ts`. Thiếu model/dữ liệu → `pytest.skip`.
   - `test_tooling.py`: bỏ `models` khỏi target giữ chỗ; `models` gọi `postcare models` (Makefile và dev.ps1); contract import-linter mới.
3. **Phụ thuộc:** `uv add mediapipe psutil` (khóa trong `uv.lock`; ghi lý do vào tech-stack.md, quy tắc 12). mediapipe kéo `opencv-contrib-python` đã có (F05).
4. **Tải model:** `config/models.yaml` (manifest: `pose.default`, danh sách `lite`/`full`/`heavy` với URL `storage.googleapis.com/mediapipe-models/pose_landmarker/<tên>/float16/1/<tên>.task`, file, sha256). `postcare/vision/models.py`: đọc manifest (Pydantic), tải bằng `urllib` (thư viện chuẩn, đa nền tảng), ghi file tạm rồi đổi tên, kiểm sha256. Lệnh `postcare models [--variant ...]`; target `make models` và `dev.ps1 models` gọi lệnh này.
5. **Adapter:** `postcare/vision/inference/{__init__,base,mapping,fake,pose_mediapipe}.py` như mục 4. `MediaPipePoseAdapter.from_config(...)` lấy `num_poses` từ `EngineConfig.pose.num_poses`; landmarker tạo qua factory để test inject được; `mediapipe` chỉ import trong `pose_mediapipe.py`.
6. **Import-linter:** contract `forbidden` mới: `postcare` không import trực tiếp `mediapipe`, trừ `postcare.vision.inference.**` (`allow_indirect_imports = True`, vì `cli` gọi adapter).
7. **Probe:** `postcare probe --pose [--model lite|full|heavy] [--no-max-fps]`: chạy adapter trên từng khung, in FPS xử lý (khung đã chạy pose / giây đồng hồ), CPU % và RAM MB của tiến trình (psutil), tỉ lệ khung có người và có đủ 4 keypoint thân (`pose.required_keypoints`, visibility ≥ `pose.min_keypoint_visibility`). Không lưu khung (R11).
8. **Benchmark (QA#35, AC4):** chạy `lite`/`full`/`heavy` trên ≥ 3 clip ~720p trong `data/external` (Pexels giường, GMDCSA24, CAUCAFall; đọc theo đường dẫn tuyệt đối, không chép vào repo), ghi bảng "Kết quả đo hiệu năng". Chọn biến thể chính xác nhất đạt ≥ 10 FPS ở 720p làm `pose.default` trong `config/models.yaml`. Không biến thể nào đạt → ghi nhận, báo người dùng (không dựng WSL/CUDA).
9. **Docs:** tech-stack.md (khóa mediapipe, psutil, kết quả đo), dev-setup.md (`make models`), overview.md §3 (contract mediapipe), testing.md (test vision của F11), spec mục 10.
10. **Kiểm tra:** `make check`, `scripts\dev.ps1 check`, `make test-vision`; ghi bằng chứng mục 10, tick AC, trạng thái In review.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
