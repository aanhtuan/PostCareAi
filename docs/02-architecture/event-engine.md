# Event Detection Engine

Nguồn: PDF §5, §6, §7; HS §5. Engine là **phần lõi** của sản phẩm (PDF §7). Engine biến output AI thành trạng thái và sự kiện có ý nghĩa theo nguyên tắc **"không tin một frame đơn lẻ"**.

## 1. Ràng buộc thiết kế

- `postcare.engine` là **Python thuần**: chỉ phụ thuộc `postcare.schemas`, stdlib, pydantic, numpy. Không import cv2, mediapipe, fastapi, sqlalchemy, httpx (import-linter kiểm tra).
- Engine **xác định** (deterministic): cùng chuỗi `FrameObservation` + cùng cấu hình → cùng output. Engine không đọc đồng hồ hệ thống; chỉ dùng `obs.ts_ms`.
- Mọi ngưỡng nằm trong `EngineConfig` (mặc định ở `config/engine.default.yaml`, override theo camera qua `cameras.thresholds`). **Không viết cứng số trong code rule.**
- Mỗi trạng thái và sự kiện kèm `explanation` gồm `rule_id` và giá trị đặc trưng chính, để giải thích được với giám khảo (PDF §7) và lưu "căn cứ ngắn gọn" (HS §6.2).
- Engine không biết về DB, giường hay người dùng. Engine chỉ nhận observation và trả `EngineOutput`.

## 2. Schema vào/ra (`postcare.schemas`)

```text
FrameObservation
  camera_id: int
  frame_index: int
  ts_ms: int                      # đơn điệu, theo đồng hồ khung hình
  image_size: (width, height)
  persons: list[PersonPose]       # 0..num_poses
  face: FaceObservation | None    # chỉ có khi adapter face chạy (F25)
  source_ok: bool

PersonPose
  keypoints: dict[KeypointName, Keypoint]   # tên trung lập với model: nose, left_shoulder, right_hip, left_ankle…
  Keypoint: x, y ∈ [0,1] (chuẩn hóa theo khung hình), visibility ∈ [0,1]

FaceObservation                   # OUTPUT của adapter face (F25)
  status: OK | NOT_VISIBLE | TOO_SMALL | LOW_CONFIDENCE
  head_box_px: int
  blendshapes: dict[str, float]   # chỉ các khóa trong face.signals, xem mục 8

FaceSignals                       # do ENGINE suy ra theo thời gian (F26)
  eyes_closed, eyes_closed_prolonged, brow_down, eye_squint, nose_sneer, mouth_change: bool

EngineContext                     # truyền khi tạo Engine(config, context), không nằm trong từng frame
  camera_id: int
  roi_polygon: RoiPolygon         # points: list[(x, y)] chuẩn hóa 0–1, ≥3 điểm; đổi ROI → worker tạo Engine mới

EngineOutput
  state: BodyStateSnapshot        # body_state, observation_quality, activity_level, rest_status, face_status, face_signals, explanation (lần chuyển body_state gần nhất; F14)
  state_changed: bool
  events: list[EngineEvent]       # code, priority, occurred_at_ms, detected_at_ms, confidence, observation_quality, explanation, config_hash (F15)
```

- `face = None` nghĩa là frame này không chạy face (do `face.run_every_n_frames`). Engine giữ tín hiệu mặt gần nhất trong tối đa `face.run_every_n_frames` frame, sau đó coi là `NOT_VISIBLE` *(giả định)*.
- Nhánh face (F25, `vision/inference/face_gate.py`) chạy **trước** engine, trên người mục tiêu mà engine sắp chọn (`Engine.peek_target(obs)`, chỉ đọc). Ở frame chạy face, `status` gán theo thứ tự: không có mục tiêu → `NOT_VISIBLE`; dưới 2 keypoint đầu (`nose`, mắt, tai) đạt `pose.min_keypoint_visibility` → `LOW_CONFIDENCE`; `head_box_px < face.min_head_box_px` → `TOO_SMALL` (ba trường hợp này không gọi Face Landmarker); thiếu model, ảnh cắt rỗng hoặc adapter lỗi → `NOT_VISIBLE` (đếm lỗi, ghi WARNING); không thấy mặt trong ảnh cắt → `NOT_VISIBLE`; còn lại `OK`. `head_box_px` là cạnh hình vuông quanh keypoint đầu, nới theo `face.head_crop_scale` (`vision/inference/head_region.py`, dùng chung với F28). `face.enabled = false` → không chạy nhánh face, `face` luôn `None`. Lỗi face không bao giờ đổi trạng thái hay sự kiện cơ thể.
- Vòng đời một instance `Engine` = một phiên theo dõi. Worker tạo `Engine` mới khi phiên đổi hoặc ROI/ngưỡng đổi *(giả định)*.

`KeypointName` là danh sách tên trung lập. Adapter MediaPipe ánh xạ 33 landmark sang các tên này. Adapter khác (ví dụ RTMPose) ánh xạ tập keypoint của nó sang cùng tên (PDF §10).

Quy ước của code (F10, file trong `postcare/schemas/`: `observation.py`, `state.py`, `events.py`, `context.py`, `roi.py`, `engine_config.py`):
- `KeypointName` gồm 21 tên viết thường: `nose`, `left_/right_` + `eye`, `ear`, `shoulder`, `elbow`, `wrist`, `hip`, `knee`, `ankle`, `heel`, `foot_index` *(giả định F10 R3)*. Tên lạ hoặc toạ độ, visibility ngoài [0, 1] → lỗi validate; adapter phải kẹp giá trị trước khi tạo.
- Mọi schema là Pydantic frozen và JSON round-trip được (định dạng `observations.jsonl`).
- `EngineEvent` kiểm tra `explanation.rule_id` không rỗng, `priority` thuộc các mức cho phép của mã trong catalog, `occurred_at_ms ≤ detected_at_ms` *(giả định)*.
- `Engine.process(obs)`: `obs.ts_ms` phải tăng ngặt so với frame trước, `obs.camera_id` phải bằng `context.camera_id`; sai → `ValueError` *(giả định)*. `state_changed` là `true` ở output đầu tiên và khi `BodyStateSnapshot` khác lần trước.
- Chưa có nghỉ, khuôn mặt (trước F26, F27): `rest_status = UNKNOWN`, `face_status = NOT_VISIBLE`. `activity_level` do F23 điền (mục 5); `UNKNOWN` khi chưa đủ dữ liệu hoặc mất quan sát. `Engine.activity_index` trả chỉ số vận động hiện tại (None khi `UNKNOWN`).

## 3. Pipeline (mỗi bước là một module, có test riêng)

| # | Bước | Module | Feature | Output |
|---|---|---|---|---|
| 1 | Chọn người mục tiêu | `engine/target.py` | F13 | Người có tâm hông trong ROI, liên tục với vị trí trước; đếm số người trong ROI |
| 2 | Tính đặc trưng | `engine/features.py` | F13 | hip_center, shoulder_center, trunk_angle_deg, torso_length, inside_roi, dist_to_roi_edge, ankles_outside_roi, velocity |
| 3 | Làm mượt + chất lượng | `engine/quality.py`, `engine/smoothing.py` | F13 | Đặc trưng đã làm mượt (EMA/median); `observation_quality` |
| 4 | Phân loại tư thế/vị trí thô | `engine/posture.py` | F14 | posture thô (LYING/RAISING/SITTING/STANDING/UNKNOWN), location (IN_BED/EDGE/OUT) |
| 5 | State machine | `engine/state_machine.py` | F14 | `BodyState` ổn định (hysteresis + min duration) |
| 6 | Rule sự kiện cơ thể | `engine/rules/body.py` | F15 | SIT_UP, STAND_UP, POSTURE_CHANGE, BED_EDGE, BED_EXIT, RETURN_TO_BED |
| 7 | Vận động | `engine/activity.py`, `engine/rules/movement.py` | F23 | activity_level; ACTIVITY_*, ABNORMAL_MOVEMENT |
| 8 | Khuôn mặt + kết hợp | `engine/face.py`, `engine/rules/face.py`, `engine/rest.py` | F26, F27 | face_signals; FACE_ATTENTION (có nâng ưu tiên); rest_status |
| 9 | Debounce + quan sát | `engine/debounce.py`, `engine/rules/observation.py` | F15 (engine); F17 chỉ lưu | Lọc lặp; OBSERVATION_LOST / RESTORED |

`engine/engine.py` có lớp `Engine` ghép các bước trên. Khung các bước (chữ ký sẵn, chưa có logic) nằm ở `engine/pipeline.py` (F10): `TargetSelector`, `QualityAssessor`, `StateMachine`, `RuleSet`; feature sau tách ra module riêng như bảng trên. `RuleSet` (bước 6–9) nằm ở `engine/rules/__init__.py` từ F15: gọi các rule rồi lọc bằng `Debouncer`, gắn `priority` từ catalog và `config_hash`. Method `Engine.process(obs) -> EngineOutput` là API duy nhất mà worker và replay gọi (F10).

Quy ước bước 1–3 (F13; `engine/target.py`, `features.py`, `smoothing.py`, `quality.py`, `geometry.py`):
- Góc và khoảng cách tính theo **pixel** (toạ độ chuẩn hóa × `image_size`). Trục dài giường = trục chính (PCA) của các đỉnh ROI *(giả định)*.
- `hip_center` cần đủ hai hông (không xét visibility). Chỉ xét `pose.num_poses` người đầu của frame. "Người trong ROI" = `hip_center` nằm trong polygon.
- Mục tiêu: đã có thì bám người gần nhất trong `target.max_jump_torso_lengths × torso_length`, kể cả ngoài ROI; chưa có thì chỉ nhận người trong ROI (sâu nhất trong ROI). Vị trí nhớ chỉ cập nhật khi hai hông có visibility ≥ `pose.min_keypoint_visibility`. Frame không khớp ai: vẫn nhớ vị trí cũ và không nhận người mới, cho tới khi cổng chất lượng đóng *(giả định)*.
- `observation_quality` mỗi frame, điều kiện trước thắng: `CAMERA_ISSUE` (`source_ok = false`) → `MULTIPLE_PEOPLE` (≥ 2 người trong ROI) → `NO_PERSON` (không có mục tiêu) → `LOW_CONFIDENCE` (keypoint trong `pose.required_keypoints` thiếu hoặc visibility < `pose.min_keypoint_visibility`, hoặc `torso_length = 0`) → `GOOD`.
- Cổng chất lượng (theo `ts_ms`): khác `GOOD` liên tục ≥ `quality.low_quality_to_no_observation_s` → `NO_OBSERVATION`; thoát khi `GOOD` liên tục ≥ `quality.restore_duration_s`; engine khởi động với cổng đóng. Frame kém chưa đủ lâu: giữ trạng thái cũ, `StateMachine` không nhận frame đó.
- Đặc trưng (`BodyFeatures`) chỉ có ở frame `GOOD`, tính từ keypoint đã làm mượt EMA (`smoothing.ema_alpha`): `hip_center`, `shoulder_center`, `torso_length` (px), `trunk_angle_deg` (gập [0°, 90°]), `inside_roi`, `dist_to_roi_edge` (có dấu, đơn vị torso), `ankles_outside_roi`, `knees`, `ankles`, `shoulder_line_angle_deg`, `velocity` (vx, vy; torso/giây). Bộ làm mượt reset khi nhận mục tiêu mới hoặc khi thoát `NO_OBSERVATION` *(giả định)*.
- `postcare.engine` không import `time`, `datetime`, `random`, `importlib` (contract import-linter `engine-no-clock` + test AST).

## 4. Trạng thái cơ thể

| Code | UI | Điều kiện vào (tóm tắt) | Nguồn |
|---|---|---|---|
| `LYING` | Nằm | Thân gần song song trục dài của giường; hông trong ROI | PDF §7; HS §5.1 |
| `RAISING` | Đang nâng thân | Góc thân so với trục giường tăng dần từ nằm, chưa đạt ngưỡng ngồi | PDF §7.1 |
| `SITTING` | Ngồi | Góc thân lớn so với trục giường (hoặc tỷ lệ torso_length đổi rõ), vai cao hơn hông, hông trong ROI | PDF §7.1 |
| `AT_EDGE` | Ở mép giường | Ngồi + hông gần biên ROI hoặc cổ chân ra ngoài ROI (đứng thì là `STANDING`) | PDF §7.2; HS §5.2 |
| `STANDING` | Đứng | Thân thẳng, hông cao, chân duỗi (gối–cổ chân thẳng hàng) | HS §5.1 |
| `OUT_OF_BED` | Ngoài giường | Người mục tiêu **được quan sát** ra ngoài ROI đủ lâu | PDF §7.2; HS §5.2 |
| `NO_OBSERVATION` | Không đủ dữ liệu quan sát | Chất lượng kém kéo dài (không có người, visibility thấp, ≥2 người trong ROI, mất nguồn) | PDF §4.3, §13.4; HS §7.1 |

**Quy tắc chuyển trạng thái:**
- Chỉ chuyển khi posture/location mới giữ liên tục ≥ `min_duration` của trạng thái đích.
- Có **hysteresis**: ngưỡng vào ≠ ngưỡng ra (PDF §7).
- Từ `NO_OBSERVATION` quay lại một trạng thái khác phải giữ ≥ `restore_duration`.
- **Mất landmark hoặc bị che không bao giờ dẫn tới `OUT_OF_BED`**. Trường hợp này luôn dẫn tới `NO_OBSERVATION` (HS §5.2).
- Chuỗi hợp lệ để có BED_EXIT: `… → AT_EDGE → (STANDING) → OUT_OF_BED` hoặc `… → STANDING → OUT_OF_BED` (PDF §7.2). **Điều kiện trước cho BED_EXIT (F15): trạng thái ổn định ngay trước `OUT_OF_BED` là `AT_EDGE` hoặc `STANDING`**, bỏ qua đoạn `NO_OBSERVATION` xen giữa. Lý do: đứng ở mép giường luôn là `STANDING`, nên người ngồi mép chưa đủ `min_duration_s.AT_EDGE` rồi đứng dậy đi ra vẫn là lần rời giường thật, không được bỏ sót. Đi thẳng từ `LYING`/`RAISING`/`SITTING` sang `OUT_OF_BED` không sinh BED_EXIT; engine chỉ ghi `explanation.anomaly = "skipped_edge"` vào state *(giả định)*.
- **Ưu tiên khi chồng lấn:** tư thế đứng → `STANDING`, kể cả khi ở gần biên ROI. `AT_EDGE` chỉ dành cho **ngồi** gần biên hoặc ngồi có cổ chân ra ngoài ROI *(giả định; khớp ví dụ trong testing.md)*.

**Cách phân loại cụ thể (F14, `engine/posture.py`, `engine/state_machine.py`)** *(giả định; hiệu chỉnh ở F16)*:
- Thứ tự ứng viên: cổng chất lượng đóng → `NO_OBSERVATION`; vị trí `OUT` → `OUT_OF_BED`; tư thế đứng → `STANDING`; ngồi/nâng thân + vị trí `EDGE` → `AT_EDGE`; còn lại theo tư thế (`LYING`/`RAISING`/`SITTING`). Tư thế không xác định khi chất lượng tốt → giữ trạng thái.
- Thân "thẳng": góc > `sitting_enter_deg`; đang ở trạng thái thân thẳng (`SITTING`, `AT_EDGE`, `STANDING`, `OUT_OF_BED`) thì chỉ cần ≥ `sitting_exit_deg`. Vùng nằm: < `lying_enter_deg`; đang `LYING` thì ≤ `lying_exit_deg`. Thân thẳng mà vai không cao hơn hông → không xác định.
- Rời `LYING` luôn qua `RAISING` (mọi góc ngoài vùng nằm khi đang `LYING` là `RAISING`, kể cả khi thân đã thẳng và chân đã duỗi). **Ngoại lệ của quy tắc "đứng thắng mép"**: từ `LYING`, tư thế đứng được xếp là `RAISING`, nên nếu hông ở mép giường thì ứng viên là `AT_EDGE` (`RAISING` + `EDGE`); chỉ sau khi đã rời `LYING` mới phân loại được `STANDING`.
- Góc ở vùng giữa chỉ là `RAISING` khi đang `LYING`/`RAISING`/`NO_OBSERVATION`. Từ trạng thái thân thẳng (`SITTING`, `AT_EDGE`…) ngả lưng về góc giữa `lying_enter_deg` và `sitting_exit_deg` (mặc định 25°–45°) là tư thế không xác định → **giữ nguyên trạng thái** (ví dụ vẫn `SITTING` khi nửa nằm) cho tới khi vào vùng nằm (`SITTING → LYING`). Hành vi giữ trạng thái này là **mục hiệu chỉnh của F16** (đo trên tập dev xem có làm trễ `LYING` hay che `SIT_UP` lần sau không).
- Tỷ lệ `torso_length` chỉ dùng khi góc báo vùng nằm (góc 2D không phân biệt được); tham chiếu là `torso_length` lúc `LYING` ổn định, xóa khi vào `NO_OBSERVATION`.
- Đứng: thân thẳng, thấy gối và cổ chân, gối thấp hơn hông, cổ chân thấp hơn gối, `(knee_y − hip_y) ≥ standing_hip_above_knee_ratio × (ankle_y − knee_y)`, **và** vector hông → cổ chân cũng thẳng theo cùng ngưỡng góc của thân (loại ca chân nằm ngang trên giường).
- Vị trí: `OUT` khi `dist_to_roi_edge < −out_of_roi_margin_torso` (đang `OUT_OF_BED` thì `OUT` tới khi hông vào trong ROI); `EDGE` khi `dist_to_roi_edge < edge_distance_torso` hoặc có cổ chân ra ngoài ROI; còn lại `IN_BED`.
- Ứng viên phải giữ liên tục (không bị ứng viên khác, tư thế không xác định hay frame kém xen vào) ≥ `min_duration_s.<đích>`. Sau `NO_OBSERVATION`: cổng phục hồi `restore_duration_s` rồi mới bắt đầu đếm min_duration.
- `explanation` của mỗi lần chuyển: `rule_id` (`state.<đích>`), `from_state`, `to_state`, `held_ms`, `observation_quality`, và với trạng thái quan sát được: `posture`, `location`, `trunk_angle_deg`, `dist_to_roi_edge`, `ankles_outside_roi`, `torso_length_ratio`. `anomaly = "skipped_edge"` khi vào `OUT_OF_BED` mà trạng thái gần nhất trước đó (bỏ qua `NO_OBSERVATION`) là `LYING`/`RAISING`/`SITTING`, tức không qua `AT_EDGE` hay `STANDING`. `Engine.state_history` giữ tối đa 32 trạng thái ổn định gần nhất cho F15.

## 5. Catalog sự kiện

Nguồn sự thật trong code là `postcare/schemas/events.py`. Bảng dưới phải khớp với file đó; F10 có test kiểm tra.

| Code | UI (`vi.ts`) | Priority | Tạo cảnh báo? | Rule (tóm tắt) | Feature | Nguồn |
|---|---|---|---|---|---|---|
| `POSTURE_CHANGE` | Bệnh nhân thay đổi tư thế | LOG | Không | Đang LYING, hướng thân (góc vai) đổi > ngưỡng và giữ ổn định | F15 | HS §5.2, §5.4 |
| `SIT_UP` | Bệnh nhân ngồi dậy | INFO | Không | LYING → RAISING → SITTING; SITTING giữ đủ lâu | F15 | PDF §7.1; HS §5.4 |
| `STAND_UP` | Bệnh nhân đứng dậy | INFO *(giả định A11)* | Không | SITTING/AT_EDGE → STANDING giữ đủ lâu | F15 | HS §5.1 |
| `BED_EDGE` | Bệnh nhân đang ở mép giường | MEDIUM | **Có** | Vào AT_EDGE giữ đủ lâu | F15 | PDF §7.2; HS §5.4 |
| `BED_EXIT` | Bệnh nhân rời khỏi vùng giường | HIGH | **Có** | Vào OUT_OF_BED qua chuỗi hợp lệ, giữ đủ lâu | F15 | PDF §7.2; HS §5.2, §5.4 |
| `RETURN_TO_BED` | Bệnh nhân quay lại giường | INFO *(giả định A11)* | Không | OUT_OF_BED → trong ROI (SITTING/LYING) giữ đủ lâu | F15 | HS §5.2 |
| `ACTIVITY_INCREASED` | Mức vận động tăng | LOG *(giả định A11)* | Không | activity_level chuyển lên HIGH giữ đủ lâu | F23 | HS §5.1 |
| `ACTIVITY_LOW_PROLONGED` | Ít vận động kéo dài | LOG *(giả định A11)* | Không | activity_level LOW liên tục ≥ ngưỡng | F23 | HS §5.1 |
| `ABNORMAL_MOVEMENT` | Phát hiện chuyển động bất thường - đề nghị kiểm tra | HIGH | **Có** | ≥ N trong số các điều kiện cùng xảy ra trong cửa sổ ngắn: hông hạ nhanh, dịch chuyển mạnh, đổi hướng thân đột ngột, vị trí cuối thấp, giữ nguyên sau đó | F23 | HS §5.2, §5.4; PDF §7.3 |
| `FACE_ATTENTION` | Phát hiện biểu hiện khuôn mặt cần kiểm tra | MEDIUM; **HIGH** khi kèm vận động HIGH hoặc đổi trạng thái | **Có** | ≥2 tín hiệu mặt cùng duy trì ≥ ngưỡng, face_status = OK | F26 | HS §5.3; PDF §6.2, §7.4 |
| `OBSERVATION_LOST` | Không đủ dữ liệu quan sát | INFO *(giả định A11)* | Không | NO_OBSERVATION kéo dài ≥ ngưỡng | F17 | PDF §4.3; HS §7.1 |
| `OBSERVATION_RESTORED` | Đã quan sát lại được | LOG | Không | Thoát NO_OBSERVATION | F17 | — *(giả định)* |
| `CAMERA_OFFLINE` | Mất kết nối camera | MEDIUM *(giả định A11)* | **Có** | **API** sinh khi không nhận heartbeat quá ngưỡng (không phải engine) | F17 | PDF §10 |
| `CAMERA_ONLINE` | Camera hoạt động lại | LOG | Không | API sinh khi nhận heartbeat lại | F17 | — *(giả định)* |

**Cách sinh sự kiện cơ thể (F15, `engine/rules/body.py`)** *(giả định; hiệu chỉnh ở F16)*:
- Rule chỉ đọc chuỗi trạng thái ổn định (`Engine.state_history`), explanation của state và đặc trưng đã làm mượt. Sự kiện chỉ phát ở frame trạng thái đích được xác lập (khi **vào**), không phát lặp khi ở yên. Không phát khi đang `NO_OBSERVATION`.
- `SIT_UP`: vào `SITTING`, hai trạng thái ổn định ngay trước là `RAISING` rồi `LYING`. `STAND_UP`: vào `STANDING`, ngay trước là `SITTING` hoặc `AT_EDGE`.
- `BED_EDGE`: vào `AT_EDGE` khi trạng thái quan sát gần nhất trước đó (bỏ qua `NO_OBSERVATION`) là `LYING`/`RAISING`/`SITTING`; cũng phát khi đây là trạng thái ổn định đầu tiên, chưa có trạng thái quan sát nào trước đó (bắt đầu theo dõi hoặc worker khởi động lại khi người bệnh đã ở mép) *(giả định, chốt 18/11/2026 theo hướng an toàn)*; quay về qua mép (từ `STANDING`/`OUT_OF_BED`) thì không phát.
- `BED_EXIT`: vào `OUT_OF_BED` khi trạng thái quan sát gần nhất trước đó là `AT_EDGE` hoặc `STANDING` (mục 4); `explanation.state_chain` = chuỗi trạng thái từ sau lần `OUT_OF_BED` trước.
- `RETURN_TO_BED`: sau `OUT_OF_BED`, trạng thái ổn định là `SITTING` hoặc `LYING` liên tục (tính từ đầu khoảng min_duration của trạng thái đó; `SITTING ↔ LYING` không đếm lại) ≥ `min_duration_s.RETURN_TO_BED`, phát ở frame chất lượng `GOOD`. Mỗi lần ra ngoài phát tối đa một lần. Chỉ cần đã `OUT_OF_BED`, nên `RETURN_TO_BED` có thể xuất hiện **không có `BED_EXIT` trước đó** (lần ra ngoài có `skipped_edge`, hoặc lần ra ngoài bị chặn bởi debounce) *(giả định)*.
- `POSTURE_CHANGE`: đang `LYING`, tham chiếu = `shoulder_line_angle_deg` ở frame đầu sau khi vào `LYING` và sau mỗi lần phát; lệch (0°–180°) > `posture_change.shoulder_angle_delta_deg` liên tục ≥ `posture_change.stable_s`.
- Trường: `occurred_at_ms` = đầu khoảng giữ (min_duration hoặc stable), `detected_at_ms` = `ts_ms` lúc phát; `confidence` = trung bình visibility của `pose.required_keypoints` trên các frame trong khoảng đó; `explanation` có `rule_id` (`body.<mã viết thường>`), `from_state`, `to_state`, `held_ms` và đặc trưng chính; `config_hash` = `Engine.config_hash`.

**Mức vận động và sự kiện vận động (F23, `engine/activity.py`, `engine/rules/movement.py`)** *(giả định; hiệu chỉnh ở F16)*:
- Chỉ số vận động (torso_length/giây): keypoint vai, khuỷu, cổ tay, hông, gối, cổ chân của người mục tiêu có visibility ≥ `pose.min_keypoint_visibility`, làm mượt EMA. Mỗi frame `GOOD`: tốc độ mẫu = trung bình trên các keypoint của `|Δp| / torso_length / Δt`, với `Δ` là bước ≥ `activity.sample_interval_s` (không đo giữa hai frame liền nhau: nhiễu keypoint 1–2 px mỗi frame cộng dồn làm người ngồi yên đã vượt `high_threshold`). Chỉ số = **trung vị** các mẫu trong `activity.window_s` (keypoint lệch 1–3 frame không kéo chỉ số lên).
- `activity_level`: `LOW` < `low_threshold` ≤ `NORMAL` ≤ `high_threshold` < `HIGH`. `UNKNOWN` khi mẫu chưa phủ đủ `window_s` (khoảng `sample_interval_s + window_s` sau khi quan sát được), khi `NO_OBSERVATION` và ngay sau khi đổi người mục tiêu (bộ đếm reset). Frame kém trong lúc cổng còn mở: giữ mức.
- `ACTIVITY_INCREASED`: mức vào `HIGH` và giữ ≥ `activity.increased_hold_s`. `ACTIVITY_LOW_PROLONGED`: `LOW` liên tục ≥ `activity.low_prolonged_s`. Mỗi đoạn mức liên tục phát tối đa một lần; `occurred_at_ms` = đầu đoạn; `explanation`: `rule_id` (`movement.<mã>`), `activity_level`, `activity_index`, `threshold`, `held_ms`, `window_s`.
- `ABNORMAL_MOVEMENT`: chỉ xét chuỗi frame `GOOD` liên tục của cùng người mục tiêu; frame không `GOOD`, `NO_OBSERVATION` hoặc đổi mục tiêu → hủy (không xét ROI: mục tiêu đã ra khỏi giường vẫn được xét).
  1. Frame `t` có mốc `ref` = mẫu cách ≥ `abnormal_movement.window_s` về trước. Dấu hiệu nhanh: vận tốc đi xuống lớn nhất của `hip_center` trong cửa sổ ≥ `hip_drop_speed_torso_per_s` (chia torso lớn hơn giữa frame và mốc); `|hip(t) − hip(ref)| / torso(ref)` ≥ `displacement_torso`; `|trunk(t) − trunk(ref)|` ≥ `trunk_angle_change_deg`.
  2. Có dấu hiệu → một "chuyển động"; mẫu "trước" = `ref` của frame có nhiều dấu hiệu nhất. Hết dấu hiệu liên tục `hold_after_s` → chấm C1–C5 với vị trí **cuối**: C1 vận tốc đi xuống lớn nhất; C2, C3 so vị trí/góc thân cuối với mẫu "trước" (nhiễu nhảy rồi quay về không tính); C4 `hip_y / chiều cao khung hình` ≥ `final_low_position_ratio`; C5 trung vị tốc độ mẫu vận động trong khoảng giữ < `activity.low_threshold`. Đủ `min_conditions` **và** có ít nhất một điều kiện hạ thấp (C1 hoặc C4) → phát *(giả định, chốt 18/11/2026)*; `explanation.lowering_required = true`.
  3. `occurred_at_ms` = mẫu đầu trong cửa sổ có tốc độ hông ≥ `hip_drop_speed_torso_per_s` (không có thì frame đầu có dấu hiệu); `detected_at_ms` = lúc chấm (≈ `window_s + hold_after_s` sau khi hết chuyển động). Chuyển động còn đang chờ (chưa đủ `hold_after_s`) khi luồng kết thúc thì **không** được chấm, không phát sự kiện. `explanation`: `conditions_met` (`hip_drop_speed`, `displacement`, `trunk_angle_change`, `final_low_position`, `still_after`), giá trị đo từng điều kiện, `min_conditions`, `window_s`, `hold_after_s`, `held_ms`.
  4. Điều kiện hạ thấp bắt buộc để đứng dậy nhanh từ sàn rồi đứng yên (C2 + C3 + C5) hoặc đi rồi dừng không cảnh báo (HS §8.1 "chuyển động nhanh xuống nệm"; ADR-0009). Giới hạn còn lại: C4 là vị trí tuyệt đối trong khung, nên đi rồi dừng khi hông đã ở thấp trong khung (≥ `final_low_position_ratio`) vẫn có thể đủ điều kiện; ngưỡng C4 cần đặt theo góc camera. Trên clip thật C5 hiếm khi thỏa với `low_threshold = 0,02` (nhiễu tĩnh ~0,02–0,07): xem F23 mục 10. Từ hiệu chỉnh dev 18/11/2026 (`window_s` 1,0, `hold_after_s` 1,0, C4 0,75; [calibration-2026-11-18.md](../04-guides/calibration-2026-11-18.md)), khoảng giữ bằng `activity.sample_interval_s` nên C5 còn thấy đuôi chuyển động và càng khó thỏa.
- Mọi mã vận động qua cùng `Debouncer` với rule cơ thể.

**Sự kiện quan sát (F17, `engine/rules/observation.py`)** *(giả định)*:
- Chuỗi mất quan sát: từ frame đầu có `body_state = NO_OBSERVATION` (kể cả lúc engine khởi động với cổng đóng) tới frame đầu không còn `NO_OBSERVATION` (cổng mở **và** state machine đã xác lập lại trạng thái ổn định).
- `OBSERVATION_LOST`: chuỗi giữ ≥ `quality.observation_lost_event_s` → phát một lần mỗi chuỗi; `occurred_at_ms` = đầu chuỗi, `detected_at_ms` = frame đạt ngưỡng; `confidence = 1.0`; `explanation`: `rule_id = observation.observation_lost`, `held_ms`, `threshold_s`, `observation_quality`.
- `OBSERVATION_RESTORED`: phát ở frame thoát chuỗi, **chỉ khi** `OBSERVATION_LOST` của chính chuỗi đó đã qua debounce (mất quan sát ngắn, hoặc LOST bị debounce chặn → không RESTORED); `occurred_at_ms = detected_at_ms`; `explanation`: `rule_id = observation.observation_restored`, `lost_ms`, `body_state`.
- `OBSERVATION_LOST` đi qua cùng `Debouncer` với các rule khác. `OBSERVATION_RESTORED` **không** qua debounce: nó chỉ sinh khi LOST của cùng chuỗi đã phát, nên luôn đi cặp với một LOST (ví dụ LOST 10 s, RESTORED 55 s, LOST 70 s, RESTORED 75 s: cả bốn đều phát) *(review F17)*. Mất quan sát không bao giờ sinh `BED_EXIT`.

Các sự kiện mức LOG/INFO chỉ vào timeline. MEDIUM/HIGH tạo cảnh báo PENDING *(giả định QA#17)*. Mức ưu tiên là ưu tiên **workflow**, không phải phân tầng nguy cơ lâm sàng (PDF §7).

**Trạng thái hiển thị (không phải sự kiện):**
- `activity_level`: LOW / NORMAL / HIGH / UNKNOWN. UNKNOWN khi NO_OBSERVATION, khi cửa sổ chưa đủ dữ liệu hoặc vừa đổi người mục tiêu, để mất quan sát không bị tính là "ít vận động" *(giả định)*.
- `rest_status`: RESTING ("Đang nghỉ - dữ liệu tham khảo") / ACTIVE ("Đang hoạt động") / UNKNOWN. Xem HS §5.3, PDF §6.3, F27.
- `face_status` và `face_signals`.

`rest_status` chỉ hiển thị trên Tổng quan và Theo dõi trực tiếp. Nó **không** được ghi vào timeline *(giả định; F27)*.

**Nâng ưu tiên FACE_ATTENTION:** từ MEDIUM lên HIGH khi, trong cửa sổ `face.attention_hold_s`, có `activity_level = HIGH` **hoặc** có chuyển trạng thái cơ thể (không tính vào/ra NO_OBSERVATION). Đây là diễn giải gộp của HS §5.3 và PDF §7.4.

## 6. Cấu hình và ngưỡng mặc định

Override theo camera (F08) chỉ được chỉnh các khóa và trong giới hạn của `config/camera_overrides.yaml` để không vô hiệu hóa quy tắc an toàn. File `config/engine.default.yaml`. Mọi giá trị dưới đây là ***giả định khởi điểm***: hiệu chỉnh trên tập dev (F16), **chốt** bằng `config_hash` trước khi chạy tập test (F29; HS §8.2). Lần hiệu chỉnh dev 18/11/2026 chỉ đổi `abnormal_movement.window_s`, `hold_after_s`, `final_low_position_ratio`; các ngưỡng tư thế/vị trí/thời gian giữ vẫn là giá trị khởi điểm vì chưa có video rời giường quay theo camera-setup.md ([calibration-2026-11-18.md](../04-guides/calibration-2026-11-18.md)). Thời gian tính bằng giây, khoảng cách chuẩn hóa theo chiều dài thân (`torso_length`) trừ khi ghi khác.

```yaml
version: 1
pose:
  num_poses: 2                    # A04
  min_keypoint_visibility: 0.5
  required_keypoints: [left_shoulder, right_shoulder, left_hip, right_hip]
quality:
  low_quality_to_no_observation_s: 2.0
  restore_duration_s: 1.0
  observation_lost_event_s: 10.0
target:
  max_jump_torso_lengths: 1.5      # nhảy xa hơn → coi là người khác
smoothing:
  ema_alpha: 0.4
posture:                           # góc giữa thân (hông→vai) và trục dài của giường (lấy từ ROI), độ
  lying_enter_deg: 25              # thân gần song song trục giường
  lying_exit_deg: 35               # hysteresis
  sitting_enter_deg: 55
  sitting_exit_deg: 45
  torso_length_ratio_sitting: 0.8  # coi là ngồi khi |torso_length / torso_length_lúc_nằm − 1| ≥ (1 − 0.8); phối cảnh có thể làm thân ngắn hoặc dài ra
  standing_hip_above_knee_ratio: 0.8  # đứng khi (knee_y − hip_y) ≥ 0.8 × (ankle_y − knee_y), tính theo pixel ảnh (y hướng xuống)
location:
  edge_distance_torso: 0.3         # hip_center cách biên ROI < 0.3 × torso_length
  out_of_roi_margin_torso: 0.2
min_duration_s:
  RAISING: 0.5
  SITTING: 2.0
  AT_EDGE: 1.5
  STANDING: 1.0
  OUT_OF_BED: 1.0
  LYING: 2.0
  RETURN_TO_BED: 3.0
posture_change:
  shoulder_angle_delta_deg: 35
  stable_s: 3.0
debounce:
  same_code_same_session_s: 60     # A01
activity:
  window_s: 5.0
  sample_interval_s: 1.0           # tốc độ keypoint đo trên bước 1 s (giảm nhiễu từng frame; F23)
  low_threshold: 0.02
  high_threshold: 0.15
  low_prolonged_s: 300
  increased_hold_s: 3.0
abnormal_movement:
  window_s: 1.0                     # hiệu chỉnh dev 18/11/2026 (1,5 → 1,0)
  hip_drop_speed_torso_per_s: 1.5
  displacement_torso: 1.0
  trunk_angle_change_deg: 50
  final_low_position_ratio: 0.75    # hip_y ≥ 0.75 × chiều cao khung hình (hiệu chỉnh dev 18/11/2026, 0,8 → 0,75)
  hold_after_s: 1.0                 # hiệu chỉnh dev 18/11/2026 (2,0 → 1,0)
  min_conditions: 3
face:
  enabled: true                    # tắt để đo FPS hoặc khi thu hẹp M3 (F25)
  min_head_box_px: 80              # A05
  run_every_n_frames: 2            # A05
  head_crop_scale: 2.2             # nới vùng đầu khi cắt (F25)
  # Gộp nhiều khóa của một tín hiệu (trái/phải, mouth*) bằng max (F26)
  signals:                         # ngưỡng blendshape 0..1
    eyes_closed: {keys: [eyeBlinkLeft, eyeBlinkRight], threshold: 0.6}
    brow_down: {keys: [browDownLeft, browDownRight], threshold: 0.5}
    eye_squint: {keys: [eyeSquintLeft, eyeSquintRight], threshold: 0.5}
    nose_sneer: {keys: [noseSneerLeft, noseSneerRight], threshold: 0.4}
    mouth_change: {keys: [mouthPressLeft, mouthPressRight, mouthStretchLeft, mouthStretchRight], threshold: 0.5}
  eyes_closed_prolonged_s: 10.0
  attention_min_signals: 2
  attention_hold_s: 5.0
rest:
  low_activity_s: 60.0
  eyes_closed_s: 30.0
  active_hold_s: 2.0               # giữ trước khi RESTING → ACTIVE (F27)
privacy:                           # chỉ ảnh hưởng hiển thị, KHÔNG tính vào config_hash (F28)
  head_box_scale: 1.8
  pixelate_blocks: 12
  head_hold_s: 1.0
```

`EngineConfig.load(path, overrides)` (`postcare/schemas/engine_config.py`) đọc file này, hợp nhất sâu override (dict từ `cameras.thresholds` hoặc file `config/cameras/<setup>.yaml`) rồi validate ở chế độ strict. Khóa lạ, sai kiểu, thiếu khóa → `EngineConfigError` nêu đường dẫn khóa (ví dụ `posture.sitting_enter_deg`).

Engine tính `config_hash` (sha256 của cấu hình đã hợp nhất, dạng JSON chuẩn: khóa sắp xếp, không khoảng trắng) và gắn vào mọi sự kiện. **Hash tính trên mọi khóa trừ `privacy.*`**, vì đổi cách hiển thị không làm đổi kết quả phát hiện. Mỗi cấu hình camera (default + override) có một hash. Tập test dùng một cấu hình camera *(giả định)*.

> **Lưu ý về góc nhìn *(giả định)*:** Góc thân 2D phụ thuộc vào vị trí camera.
> - Đo **so với trục dài của giường** (trục chính của polygon ROI) thì không phụ thuộc hướng giường trong khung hình.
> - Khi camera nhìn gần dọc theo trục giường (đặt ở đầu hoặc chân giường), góc 2D kém tin cậy. Khi đó dùng thêm tỷ lệ `torso_length` so với lúc nằm (phối cảnh làm thân ngắn hoặc dài ra khi ngồi dậy).
> - Vị trí camera chốt qua thử nghiệm (HS §4.1). Ngưỡng posture được override theo từng camera.

## 7. Debounce và chống trùng

- Engine (`engine/debounce.py`, `Debouncer(window_s).allow(key, ts_ms)`, F15): không phát lại cùng `code` trong `same_code_same_session_s` giây, tính từ lần **phát** trước (lần bị chặn không dời mốc). "Session" ở đây là vòng đời một instance `Engine` (mục 2).
- Worker: mỗi sự kiện có `event_uid` (UUID v4). Khi gửi lại do lỗi mạng, dùng lại uid cũ.
- API: chống trùng theo `event_uid` (F17).

## 8. Tín hiệu khuôn mặt

- Face Landmarker trả 52 blendshape (PDF §6.2). Engine chỉ dùng tập con trong `face.signals`.
- Ánh xạ tên blendshape chỉ khai báo ở `config/engine.default.yaml`. Adapter lọc đúng các khóa này (F25).
- **Không** gán nhãn "đau", "ngủ", "mất ý thức" (PDF §6.2; HS §5.3).
- `face_status != OK` thì không tạo tín hiệu hay sự kiện mặt, và **không** coi là bình thường (HS §9.1).

## 9. Kiểm thử engine

Xem [testing.md](../04-guides/testing.md#2-engine):
- Builder tạo chuỗi pose tổng hợp (nằm → ngồi → mép → đứng → ra ngoài).
- Fixture JSONL ghi từ video thật (chỉ toạ độ).
- Mỗi rule có cả ca dương tính và **ca âm tính**:
  - ngồi dậy rồi nằm lại;
  - nhiễu 1–3 frame;
  - mất landmark;
  - người đi ngang ngoài ROI;
  - trở mình.
