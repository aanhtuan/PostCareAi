# F25 – Face adapter và cổng chất lượng khuôn mặt

| Thuộc tính | Giá trị |
|---|---|
| Mã | F25 |
| Trạng thái | Done |
| Ưu tiên | MVP |
| Milestone | M3 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F11, F13 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §6.2 (tr.7–8), §17 (tr.17); HS §4.1, §5.3, §9.1; A05; ADR-0003 |

## 1. Mục tiêu

Đưa MediaPipe Face Landmarker vào pipeline như một nhánh **phụ, có điều kiện**. Face chỉ chạy khi vùng đầu của người mục tiêu đủ lớn và rõ. Kết quả được chuẩn hóa thành `FaceObservation` (schema chung) chứa một tập con blendshape nhỏ. Góc quay toàn thân làm mặt nhỏ hoặc nghiêng, nên Pose vẫn là nhánh chính; mất tín hiệu mặt hoặc lỗi face **không** được làm gián đoạn theo dõi cơ thể (HS §4.1; PDF §6.2, §17). Feature này phục vụ F26 (tín hiệu mặt, FACE_ATTENTION) và F27 (trạng thái nghỉ/hoạt động).

## 2. Phạm vi

**Trong phạm vi**
- Tải model `face_landmarker.task` bằng `make models` (kèm checksum).
- Adapter Face Landmarker chế độ `VIDEO`, bật blendshapes, chạy trên ảnh cắt vùng đầu.
- Ước lượng vùng đầu (head box) từ keypoint đầu của pose; cổng chất lượng (`OK` / `NOT_VISIBLE` / `TOO_SMALL` / `LOW_CONFIDENCE`).
- Lọc blendshape theo danh sách khóa khai báo trong `config/engine.default.yaml` (một chỗ duy nhất).
- Cô lập lỗi: face lỗi thì pose và engine vẫn chạy.
- Chạy face mỗi N frame; đo FPS khi bật và tắt face.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Tính tín hiệu theo thời gian (mắt đóng, hạ lông mày…), FACE_ATTENTION, hiển thị trên UI (→ F26).
- Trạng thái nghỉ/hoạt động (→ F27).
- Làm mờ khuôn mặt khi hiển thị (→ F28; F28 dùng lại hàm ước lượng vùng đầu).
- Nhận diện danh tính bằng khuôn mặt; Py-Feat; head pose chi tiết (không làm; PDF §4.2, §6.2).

## 3. Yêu cầu chi tiết

- **R1.** Dùng MediaPipe Tasks `FaceLandmarker`, chế độ `VIDEO`, `output_face_blendshapes=True`, timestamp đơn điệu lấy từ `ts_ms` của frame. Model `.task` tải bằng `make models` vào `models/` (không commit) và kiểm tra checksum như model pose. *(ADR-0003; PDF §6.2)*
- **R2.** Face chỉ chạy khi có người mục tiêu (F13) **và** vùng đầu ≥ `face.min_head_box_px`. *(HS §4.1; PDF §17; A05)*
- **R3.** Vùng đầu tính từ keypoint đầu của pose (`nose`, mắt, tai) có visibility ≥ `pose.min_keypoint_visibility`: lấy bounding box, nới theo `face.head_crop_scale`, làm vuông. `head_box_px` là cạnh hình vuông này tính bằng pixel của khung gốc. Face Landmarker chạy trên **ảnh cắt** vùng này. *(A05; giả định: hệ số nới là khóa mới `face.head_crop_scale`)*
- **R4.** Hàm ước lượng vùng đầu đặt trong `vision` và dùng chung với F28 (làm mờ). *(giả định: tránh hai cách tính vùng đầu khác nhau)*
- **R5.** Cổng chất lượng gán `FaceObservation.status`: *(HS §9.1; PDF §17; giả định cho cách phân loại)*
  - `LOW_CONFIDENCE`: không đủ keypoint đầu đạt visibility để ước lượng vùng đầu.
  - `TOO_SMALL`: `head_box_px < face.min_head_box_px` (không gọi Face Landmarker).
  - `NOT_VISIBLE`: không có người mục tiêu, hoặc Face Landmarker không tìm thấy mặt trong ảnh cắt (ví dụ mặt quay đi), hoặc adapter face lỗi.
  - `OK`: tìm thấy mặt; có `blendshapes`.
- **R6.** `FaceObservation.blendshapes` chỉ chứa các khóa xuất hiện trong `face.signals.*.keys`. Tên blendshape **không** được viết cứng trong code Python; worker/replay đọc danh sách khóa từ cấu hình và truyền vào adapter. *(event-engine.md mục 8)*
- **R7.** Face chạy mỗi `face.run_every_n_frames` frame. Ở frame không chạy, `FrameObservation.face = None` (nghĩa là "không chạy ở frame này", khác với "không thấy mặt"). *(A05; event-engine.md mục 2)*
- **R8.** Lỗi trong nhánh face (exception, model thiếu, ảnh cắt rỗng) được bắt trong adapter: ghi log mức WARNING, đếm số lần lỗi, trả `status = NOT_VISIBLE`. Pose, engine, heartbeat và gửi frame vẫn chạy bình thường. *(HS §4.1; PDF §14 (tr.15))*
- **R9.** Có khóa `face.enabled` (mặc định `true`) để tắt hẳn nhánh face: dùng khi đo FPS so sánh và khi phải thu hẹp M3. *(giả định: HS §7.3 cho phép giới hạn face theo chất lượng; bảng đo hiệu năng trong tech-stack.md có cột "Face bật?")*
- **R10.** Kiểu dữ liệu của MediaPipe không lộ ra ngoài `vision.inference`. Engine chỉ thấy `FaceObservation`. *(ADR-0003; PDF §10 (tr.12))*
- **R11.** Đo FPS xử lý khi bật face và khi tắt face trên cùng video, ghi vào bảng "Kết quả đo hiệu năng" của `tech-stack.md`. *(HS §8.2; PDF §13.3 (tr.14–15))*

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/vision/inference/face_landmarker.py`: adapter Face Landmarker (VIDEO, blendshapes) → `FaceObservation`.
  - `server/src/postcare/vision/inference/head_region.py`: ước lượng vùng đầu từ `PersonPose` (dùng chung với F28).
  - `server/src/postcare/schemas/`: `FaceObservation`, enum `FaceStatus` (đã khai báo ở F10; bổ sung nếu thiếu).
  - Vòng lặp chung của worker và replay (F11/F12): gọi face theo cổng chất lượng và chu kỳ N frame, bọc lỗi.
  - `Makefile` (`make models`): thêm model face và checksum.
- **Dữ liệu:** không có bảng mới. `face_status` đi theo `POST /internal/v1/cameras/{id}/state` (xem [data-model.md](../02-architecture/data-model.md), mục "Dữ liệu không lưu trong DB").
- **API:** không đổi. Payload state đã có `face_status` ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** không có (hiển thị ở F26).
- **Cấu hình** ([event-engine.md](../02-architecture/event-engine.md) mục 6, 8):
  - Dùng: `face.min_head_box_px`, `face.run_every_n_frames`, `face.signals.*.keys`, `pose.min_keypoint_visibility`.
  - Khóa mới *(giả định)*: `face.enabled` (bool, mặc định `true`), `face.head_crop_scale` (hệ số nới vùng đầu, giá trị khởi điểm chọn khi đo ở buổi thử camera).

## 5. Acceptance criteria

- [x] **AC1.** Face Landmarker (VIDEO, có blendshapes) chỉ được gọi khi có người mục tiêu và `head_box_px ≥ face.min_head_box_px`, trên ảnh cắt vùng đầu lấy từ keypoint pose, mỗi `face.run_every_n_frames` frame. *(HS §4.1; A05)* — *Kiểm chứng:* test `test_face_gate_calls_landmarker_only_when_head_large_enough` (landmarker giả đếm số lần gọi và kiểm tra kích thước ảnh cắt); test `@pytest.mark.vision` `test_face_adapter_real_model` trên video trong `data/` (`make test-vision`).
- [x] **AC2.** Không đủ điều kiện → `NOT_VISIBLE` / `TOO_SMALL` / `LOW_CONFIDENCE` đúng theo R5. Adapter face ném lỗi thì pose và engine vẫn cho cùng chuỗi trạng thái/sự kiện cơ thể như khi tắt face. *(HS §4.1, §9.1)* — *Kiểm chứng:* test `test_face_status_classification`; test `test_face_error_does_not_stop_body` (landmarker giả luôn raise; so sánh `events.jsonl` với lần chạy `face.enabled=false`).
- [x] **AC3.** `FaceObservation.blendshapes` chỉ chứa khóa khai báo trong `face.signals.*.keys` (eyeBlink, browDown, eyeSquint, noseSneer trái/phải và các khóa mouth* đã chọn). Ánh xạ chỉ nằm trong `config/engine.default.yaml`. *(event-engine.md mục 8)* — *Kiểm chứng:* test `test_adapter_filters_keys_from_config` (đổi danh sách khóa trong config test → output đổi theo, không sửa code); test `test_no_blendshape_names_hardcoded` quét `server/src/postcare/` không có chuỗi tên blendshape.
- [x] **AC4.** Đã đo FPS xử lý khi bật và tắt face (cùng video, cùng máy), ghi vào bảng hiệu năng của `tech-stack.md`. *(HS §8.2; A05)* — *Kiểm chứng:* chạy `postcare replay` hai lần (`face.enabled` true/false), đọc FPS từ `frames.jsonl`; reviewer xem bảng đã điền.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit (landmarker giả) | `test_face_gate_calls_landmarker_only_when_head_large_enough`, `test_face_runs_every_n_frames` | Vùng đầu 79 px với ngưỡng 80 → không gọi; không có người mục tiêu → không gọi |
| AC1 | vision (`make test-vision`) | `test_face_adapter_real_model`: video có mặt rõ → có frame `OK` và đủ khóa blendshape | Bỏ qua nếu thiếu model/video |
| AC2 | unit | `test_face_status_classification` (4 trạng thái) | Keypoint đầu visibility thấp → `LOW_CONFIDENCE`, không gọi landmarker |
| AC2 | tích hợp (replay với fake) | `test_face_error_does_not_stop_body` | Landmarker raise ở mọi frame → body events giữ nguyên |
| AC3 | unit | `test_adapter_filters_keys_from_config`, `test_no_blendshape_names_hardcoded` | Khóa không có trong config không xuất hiện trong output |
| AC4 | thủ công | Đo FPS bật/tắt face, ghi `tech-stack.md` | — |

## 7. Giả định

- *(giả định A05)* Ngưỡng vùng đầu 80 px, cắt vùng đầu trước khi chạy, face chạy mỗi 2 frame (giá trị nằm trong config).
- *(giả định)* Khóa mới `face.enabled` và `face.head_crop_scale`.
- *(giả định)* Cách phân loại `NOT_VISIBLE` / `TOO_SMALL` / `LOW_CONFIDENCE` theo R5; lỗi adapter được quy về `NOT_VISIBLE` và đếm riêng trong log.
- *(giả định)* `face = None` nghĩa là frame đó không chạy face; F26 giữ giá trị gần nhất cho tới lần chạy kế tiếp.
- *(giả định)* `num_faces = 1` vì chỉ phân tích ảnh cắt vùng đầu của người mục tiêu.
- *(giả định)* Cần ≥ 2 keypoint đầu đạt visibility mới ước lượng được vùng đầu (một điểm không cho kích thước). `head_box_px` là cạnh **sau khi** nới theo `face.head_crop_scale`, so với `face.min_head_box_px`.
- *(giả định)* Người mục tiêu cho nhánh face lấy bằng `Engine.peek_target(obs)` (chỉ đọc, trùng người mà `process(obs)` chọn); không dựng bộ chọn mục tiêu thứ hai.
- *(giả định)* Chu kỳ `run_every_n_frames` đếm theo khung đã xử lý (kể cả khung không có người), không theo `frame_index` (worker có thể bỏ khung).
- *(giả định)* `face.head_crop_scale = 2.2`: đo 2026-11-18 trên 8 clip stock (mục 10), 2.2 cho nhiều khung `OK` hơn 1.6 và 3.0. Chốt lại ở buổi thử camera.
- *(giả định)* `postcare eval` chỉ chạy pose + engine (sự kiện cơ thể không phụ thuộc face, AC2); face chạy trong `postcare replay`.

## 8. Câu hỏi mở

- ~~Chế độ `VIDEO` hay `IMAGE` cho ảnh cắt?~~ Đã đo 2026-11-18 (6 clip, 40 khung chạy face mỗi clip, scale 2.2): số khung `OK` của `IMAGE` chỉ nhỉnh hơn `VIDEO` một chút (77 so với 71 trên 240 khung), chênh chủ yếu ở một clip. Giữ `VIDEO` theo R1.
- Giá trị khởi điểm của `face.head_crop_scale` chốt ở buổi thử camera (camera-setup.md mục 3 có ghi kích thước vùng đầu). **Không chặn.**

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

Khảo sát (2026-11-18): `FaceObservation`, `FaceStatus`, `FaceConfig` (gồm `enabled`, `head_crop_scale`) và khóa `face.*` trong `config/engine.default.yaml` đã có từ F10. Người mục tiêu do `TargetSelector` (F13) chọn **bên trong** `Engine.process`, nhưng face phải chạy **trước** khi đưa `FrameObservation` vào engine. Cách làm: tách phần tính của `TargetSelector.select` thành hàm không đổi trạng thái và cho `Engine` thêm `peek_target(obs)` (chỉ đọc). Kết quả `peek_target(obs)` trùng `select(obs).target` của lần `process(obs)` ngay sau đó, vì cùng trạng thái và cùng input *(giả định: không tách bộ chọn mục tiêu thứ hai để tránh lệch)*.

1. **Manifest model.** `config/models.yaml` thêm khối `face` (một mục: URL bản `float16/1`, `face_landmarker.task`, sha256 `64184e22…c9ff`). `vision/models.py`: `ModelManifest.face: ModelEntry`. `postcare models` tải pose + face. Test: `tests/inference/test_models_download.py` (manifest có face, sha256 hợp lệ).
2. **Vùng đầu (R3, R4).** `vision/inference/head_region.py`: `HeadBox(cx, cy, side)` + `estimate_head_box(person, image_size, min_visibility, scale) -> HeadBox | None` (cần ≥ 2 keypoint đầu đạt visibility và bbox khác 0) + `crop_box(image, box)` (kẹp vào khung). Không import mediapipe/cv2 để F28 dùng lại. Test: `tests/inference/test_head_region.py`.
3. **Adapter + cổng (R1, R2, R5–R8, R10).** `vision/inference/face_landmarker.py`:
   - `FaceLandmarkerProtocol` + `create_mediapipe_face_landmarker(model_path)` (VIDEO, `output_face_blendshapes=True`, `num_faces=1`).
   - `MediaPipeFaceAdapter(model_path | None, blendshape_keys, landmarker_factory=…)`: `detect(crop, ts_ms) -> dict[str, float] | None`; model thiếu/lỗi mở → ghi WARNING, adapter ở trạng thái "hỏng" (mọi lần gọi trả lỗi).
   - `FaceRunner(adapter, config)`: đếm frame, chạy mỗi `run_every_n_frames`; trả `None` ở frame không chạy; thứ tự cổng: không mục tiêu → `NOT_VISIBLE`; không ước lượng được vùng đầu → `LOW_CONFIDENCE`; `head_box_px < min_head_box_px` → `TOO_SMALL`; adapter raise / ảnh cắt rỗng → `NOT_VISIBLE` + `error_count`; không thấy mặt → `NOT_VISIBLE`; có mặt → `OK` + blendshape đã lọc.
   - `blendshape_keys_from_config(config)`: hợp các `face.signals.*.keys`.
   - `vision/inference/fake.py`: `FakeFaceAdapter` cho test.
4. **Pipeline (R7, R9).** `pipeline.process_frame(frame, adapter, engine, face=None)`: khi có `FaceRunner` thì `face_obs = face.observe(frame, engine.peek_target(obs))`, gắn vào `obs.face`. `engine/target.py` + `engine/engine.py`: `peek_target`. `replay_video(..., face=None)`; CLI `replay` (và `eval` qua factory) tạo `FaceRunner` khi `face.enabled`. Worker (F06/F17) chưa có vòng lặp dùng `process_frame` có face: nơi gọi truyền `face` khi nối.
5. **Test trước (AC1–AC3)** trong `tests/inference/test_face_gate.py`, `tests/replay/test_face_isolation.py`, `tests/inference/test_face_no_hardcode.py`:
   - `test_face_gate_calls_landmarker_only_when_head_large_enough` (79 px với ngưỡng 80 → không gọi; không mục tiêu → không gọi; kích thước ảnh cắt đúng);
   - `test_face_runs_every_n_frames`; `test_face_status_classification` (4 trạng thái, visibility thấp → `LOW_CONFIDENCE`);
   - `test_face_error_does_not_stop_body` (adapter luôn raise; so `events.jsonl` và chuỗi trạng thái với `face.enabled=false`);
   - `test_adapter_filters_keys_from_config`, `test_no_blendshape_names_hardcoded` (quét `server/src/postcare/`);
   - `test_peek_target_matches_select` (engine);
   - vision: `tests/vision/test_face_adapter.py::test_face_adapter_real_model` (clip có mặt rõ; thiếu model/video → skip).
6. **Đo thật (AC4).** `postcare replay` trên vài clip Pexels/Mixkit cận mặt, `face.enabled` true/false: phân bố `face.status`, FPS từ `run.json`; ghi `tech-stack.md`.
7. **Doc.** `tech-stack.md` (bảng hiệu năng), `event-engine.md` mục 2/6 (ý nghĩa `face=None`, thứ tự cổng), `overview.md`/F12 nếu chữ ký `process_frame` đổi, `camera-setup.md` nếu cần, spec §10.

Rủi ro: VIDEO mode trên ảnh cắt thay đổi (câu hỏi mở 1) → đo ở bước 6; vùng đầu từ pose có thể nhỏ hơn mặt thật khi chỉ thấy mắt + mũi → chỉnh `face.head_crop_scale` theo kết quả đo (chỉ sửa khóa `face.*`).

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-18, builder (trạng thái In review).** Nhánh `feat/F25-face-adapter`.

Đã làm:
- `vision/inference/head_region.py` (`HeadBox`, `estimate_head_box`, `crop_head`; F28 dùng lại với `privacy.head_box_scale`), `vision/inference/face_gate.py` (`FaceGate`, `blendshape_keys_from_config`), `vision/inference/face_landmarker.py` (`MediaPipeFaceAdapter`, VIDEO, blendshapes, `num_faces=1`; `open_face_adapter` trả `None` + WARNING khi thiếu model), `FaceDetector` trong `vision/inference/base.py`.
- `Engine.peek_target` / `TargetSelector.peek` (chỉ đọc). `pipeline.process_frame(frame, adapter, engine, face=None)`. `replay_video(..., face=)`; `run.json` thêm `face_enabled`, `face_errors`. CLI `replay` tạo `FaceGate` khi `face.enabled`.
- `config/models.yaml`: khối `face` (URL `.../face_landmarker/float16/1/face_landmarker.task`, sha256 `64184e22…bc9ff`); `postcare models` tải cả face.
- `face.head_crop_scale` 1.6 → 2.2 (chỉ khóa `face.*`).

Bằng chứng AC:
- AC1: `tests/face/test_face_gate.py::test_face_gate_calls_landmarker_only_when_head_large_enough` (79 px → không gọi; không mục tiêu → không gọi; ảnh cắt 160×160), `test_face_runs_every_n_frames`, `test_face_gate_threshold_is_inclusive`; `tests/vision/test_face_adapter.py::test_face_adapter_real_model` (pexels-6130032, `make test-vision`: 6 passed).
- AC2: `test_face_status_classification`, `test_face_adapter_error_is_not_visible_and_counted`, `test_face_missing_detector_is_not_visible`, `tests/face/test_face_isolation.py::test_face_error_does_not_stop_body` (adapter luôn raise; `events.jsonl` bỏ `config_hash` và `frames.jsonl` trùng lần `face.enabled=false`). Trên video thật: 3 clip bật/tắt face cho `events.jsonl` và `frames.jsonl` giống hệt.
- AC3: `tests/face/test_face_adapter_unit.py::test_adapter_filters_keys_from_config`, `tests/face/test_face_no_hardcode.py::test_no_blendshape_names_hardcoded`, `test_gate_filters_unknown_blendshape_keys`.
- AC4: bảng "Kết quả đo hiệu năng" trong `tech-stack.md` (2026-11-18): face làm chậm khoảng 15 % (22.3 → 18.8 FPS; 26.7 → 22.6 FPS), RAM +30 MB.

Phân bố `face.status` trên clip thật (80 khung đầu, 10 FPS, 40 khung chạy face, ROI cả khung, scale 1.6 ban đầu): clip cận mặt ngồi/đứng (pexels-9902443, 6130032, 6944081, 6010961) đa số `OK`; người nằm nghiêng mặt 90° (mixkit-5457, pexels-6130226) gần như toàn `NOT_VISIBLE` dù vùng đầu > 130 px (bộ phát hiện mặt kém với mặt xoay ngang); clip toàn thân xa (pexels-8860232, mixkit-48202) chủ yếu `TOO_SMALL`. Không có lỗi face ở clip nào.

So sánh `face.head_crop_scale` (căn cứ cho giả định mục 7): số khung `OK` trên 40 khung chạy face (80 khung đầu, 10 FPS, ROI cả khung, chế độ VIDEO), cùng clip, cùng máy.

| Clip | 1.6 | 2.2 | 3.0 |
|---|---|---|---|
| pexels-3753707 | 15 | 16 | 16 |
| pexels-4052924 | 6 | 9 | 3 |
| pexels-6010768 | 0 | 0 | 0 |
| pexels-6130226 (nằm, mặt xoay ngang) | 0 | 0 | 0 |
| pexels-6130032 | 24 | 33 | 35 |
| pexels-6010961 | 24 | 28 | 28 |
| mixkit-5457 (nằm, mặt xoay ngang) | 0 | 4 | 1 |
| mixkit-5568 | 9 | 9 | 9 |
| **Tổng** | **78** | **99** | **92** |

Ở 1.6, khung không `OK` của pexels-6010768 phần lớn là `NOT_VISIBLE` (28) và `TOO_SMALL` (12); ở 2.2 và 3.0 vùng đầu lớn hơn nên gần như hết `TOO_SMALL` nhưng mặt vẫn không được tìm thấy.

Kiểm tra: `make check` exit 0, `scripts/dev.ps1 check` exit 0 (lần đầu MemoryError lúc import do máy hết RAM khi nhiều tác vụ song song; chạy lại xanh), `make test-vision` 6 passed (POSTCARE_MODELS_DIR, POSTCARE_DATA_DIR trỏ về checkout chính).

Người sau cần biết:
- Worker (F06/F17) chưa truyền `face` vào `process_frame`: khi nối, tạo `FaceGate.from_config(config, open_face_adapter(models_dir / manifest.face.filename, config))` nếu `config.face.enabled`, đóng bằng `gate.close()`.
- Engine chưa đọc `obs.face` (`face_status` trong snapshot vẫn `NOT_VISIBLE`): F26 làm.
- Mặt nằm xoay ngang hay bị bỏ lỡ: F26/F27 cần coi `NOT_VISIBLE` là "không biết", không phải "bình thường" (đã đúng theo event-engine.md mục 8).

**2026-11-18, review: Đạt.** Sửa theo review (cùng nhánh): (1) thêm bảng so sánh `head_crop_scale` ở trên; (2) `cli/main.py`: tạo `FaceGate` bên trong `try/finally`, nên adapter pose luôn được đóng khi tạo cổng face lỗi (`tests/face/test_face_cli.py::test_replay_closes_pose_adapter_when_face_gate_fails`); (3) `FaceGate.observe` bọc toàn bộ phần xử lý người mục tiêu (cả `estimate_head_box`, `side_px`), keypoint NaN → `NOT_VISIBLE` + đếm lỗi thay vì raise (`test_face_gate_nan_keypoints_do_not_raise`); (4) sửa chú thích cũ "× 1.6" trong `test_face_isolation.py`. Trạng thái Done. Còn lại khi F06 vào `main`: thêm `peek_target` vào protocol `FrameEngine`, worker truyền `face` vào `process_frame`.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
