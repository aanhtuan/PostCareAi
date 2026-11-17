# F13 – Đặc trưng cơ thể, người mục tiêu, chất lượng quan sát

| Thuộc tính | Giá trị |
|---|---|
| Mã | F13 |
| Trạng thái | In review |
| Ưu tiên | MVP |
| Milestone | M1 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F10 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §6.1 (tr.7), §13.4 (tr.15), §17 (tr.17); HS §5.2, §8.1; QA#20 |

## 1. Mục tiêu

Feature này làm bước 1–3 của pipeline engine ([event-engine.md](../02-architecture/event-engine.md) mục 3). Đầu vào là danh sách `PersonPose` trong mỗi `FrameObservation`. Đầu ra là đặc trưng cơ thể đã làm mượt của **một người mục tiêu** (người được coi là bệnh nhân), kèm mức chất lượng quan sát. Mọi bước sau (F14, F15, F23) chỉ dùng đầu ra này.

Hai điều phải bảo đảm:
- Người đứng ngoài vùng giường (điều dưỡng, người đi ngang) không bị nhận nhầm là bệnh nhân (PDF §13.1 (tr.14); HS §8.1, §8.3).
- Hệ thống biết khi nào **không nên đoán**. Chất lượng kém kéo dài thì chuyển sang "Không đủ dữ liệu quan sát" (PDF §4.3 (tr.6), §13.4 (tr.15); HS §5.2).

## 2. Phạm vi

**Trong phạm vi**
- Chọn người mục tiêu và đếm số người có tâm hông trong Bed ROI (`engine/target.py`).
- Tính đặc trưng hình học (`engine/features.py`).
- Làm mượt (`engine/smoothing.py`) và đánh giá chất lượng quan sát từng frame (`engine/quality.py`).
- Cổng chất lượng trong `Engine.process`: chất lượng kém kéo dài thì trạng thái là `NO_OBSERVATION`.
- Builder chuỗi pose tổng hợp `server/tests/engine/builders.py` ([testing.md](../04-guides/testing.md) mục 2 ghi builder được tạo ở F13).

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Phân loại tư thế/vị trí, 6 trạng thái còn lại, hysteresis, min duration (→ F14).
- Sự kiện cơ thể và debounce (→ F15). Sự kiện OBSERVATION_LOST / OBSERVATION_RESTORED (→ F17).
- Chỉ số vận động, chuyển động bất thường (→ F23).
- Cắt vùng đầu cho Face Landmarker (→ F25). Làm mờ khi hiển thị (→ F28).
- Gọi MediaPipe (→ F11). F13 chỉ làm việc với schema chung.

## 3. Yêu cầu chi tiết

- **R1.** Code nằm trong `postcare.engine`: Python thuần, không import cv2/mediapipe/fastapi/sqlalchemy/httpx, không đọc đồng hồ hệ thống (chỉ dùng `obs.ts_ms`), xác định (cùng chuỗi + cùng cấu hình → cùng kết quả) *(event-engine.md mục 1)*.
- **R2.** Keypoint và ROI được chuẩn hóa về [0,1] theo chiều rộng và chiều cao riêng. Vì vậy mọi góc và khoảng cách phải tính trong hệ toạ độ pixel (nhân với `image_size`) *(giả định: nếu tính trực tiếp trên toạ độ chuẩn hóa thì góc bị méo theo tỷ lệ khung hình, ví dụ 16:9)*.
- **R3.** Đặc trưng tính cho mỗi frame *(PDF §6.1 (tr.7); HS §5.2; event-engine.md mục 3, bước 2)*:
  - `hip_center`, `shoulder_center`: trung điểm hai hông, hai vai.
  - `torso_length`: khoảng cách `shoulder_center`–`hip_center` (pixel).
  - `trunk_angle_deg`: góc giữa vector hông→vai và **trục dài của giường**, gập về [0°, 90°] (không phân biệt hướng đầu/chân) *(event-engine.md mục 6, ghi chú về góc nhìn)*. Trục dài lấy từ polygon ROI *(giả định: trục chính tính bằng PCA trên các đỉnh polygon)*.
  - `inside_roi`: `hip_center` nằm trong polygon ROI.
  - `dist_to_roi_edge`: khoảng cách **có dấu** từ `hip_center` tới biên ROI, dương khi ở trong, chia cho `torso_length` *(event-engine.md mục 6: khoảng cách chuẩn hóa theo torso_length)*.
  - `ankles_outside_roi`: số cổ chân nằm ngoài ROI. Chỉ tính cổ chân có visibility ≥ `pose.min_keypoint_visibility`.
  - Vị trí gối và cổ chân, để F14 phân biệt đứng *(event-engine.md mục 4: STANDING dùng quan hệ hông–gối–cổ chân)*.
  - `shoulder_line_angle_deg`: hướng của đường nối hai vai, để F15 nhận biết thay đổi tư thế *(event-engine.md mục 5: POSTURE_CHANGE dùng "góc vai")*.
  - `velocity`: vận tốc của `hip_center`, đơn vị torso_length/giây, tính từ chênh lệch `ts_ms` giữa hai frame.
- **R4.** Làm mượt bằng EMA với hệ số `smoothing.ema_alpha`. Vận tốc tính trên vị trí đã làm mượt *(PDF §5 (tr.6): Temporal Processing làm smoothing; event-engine.md mục 3, bước 3)*. Bộ làm mượt được reset khi đổi người mục tiêu hoặc khi thoát `NO_OBSERVATION` *(giả định: tránh kéo giá trị của người khác hoặc của đoạn bị mất)*.
- **R5.** Chọn người mục tiêu *(QA#20; HS §5.2; event-engine.md mục 3, bước 1)*:
  1. Nếu frame trước đã có mục tiêu: chọn người có `hip_center` gần vị trí cũ nhất, với điều kiện quãng dịch chuyển ≤ `target.max_jump_torso_lengths` × `torso_length`. Mục tiêu **vẫn được bám** khi đã ra ngoài ROI *(giả định: HS §5.2 yêu cầu "người mục tiêu được quan sát ra ngoài vùng giường" mới tính là rời giường, nên phải theo được người đó ngoài ROI)*.
  2. Nếu chưa có mục tiêu (lúc khởi động hoặc sau khi mất): chỉ nhận người có `hip_center` nằm trong ROI. Người ngoài ROI **không bao giờ** trở thành mục tiêu mới *(PDF §13.1 (tr.14); HS §8.1)*.
  3. Dịch chuyển vượt `target.max_jump_torso_lengths` thì coi là người khác. Khi đó không nối tiếp với mục tiêu cũ *(event-engine.md mục 6, chú thích của khóa)*.
  4. Số người tối đa trong một frame bằng `pose.num_poses` *(A04)*.
- **R6.** Chất lượng quan sát của từng frame (`observation_quality`, enum của bảng `events` trong [data-model.md](../02-architecture/data-model.md)). Khi nhiều điều kiện cùng đúng, lấy điều kiện đứng trước *(giả định: thứ tự ưu tiên)*:
  1. `CAMERA_ISSUE`: `obs.source_ok = false`.
  2. `MULTIPLE_PEOPLE`: có ≥ 2 người có `hip_center` trong ROI *(QA#20)*.
  3. `NO_PERSON`: không có người mục tiêu.
  4. `LOW_CONFIDENCE`: có keypoint trong `pose.required_keypoints` với visibility < `pose.min_keypoint_visibility`, hoặc `torso_length = 0` *(PDF §17 (tr.17): kiểm tra confidence khi bị che)*.
  5. `GOOD`: các trường hợp còn lại.
- **R7.** Cổng chất lượng *(PDF §4.3 (tr.6), §13.4 (tr.15); event-engine.md mục 4)*:
  - Chất lượng khác `GOOD` liên tục ≥ `quality.low_quality_to_no_observation_s` → `body_state = NO_OBSERVATION`. Khi đó không phân loại tư thế.
  - Thoát `NO_OBSERVATION` khi `GOOD` liên tục ≥ `quality.restore_duration_s`.
  - Chất lượng kém nhưng **chưa đủ lâu**: giữ nguyên trạng thái trước đó. Đặc trưng của frame kém không được đưa sang bước phân loại *(giả định: không kết luận từ frame xấu, theo PDF §4.3 (tr.6))*.
- **R8.** Mất landmark hoặc bị che dẫn tới `LOW_CONFIDENCE`/`NO_PERSON` rồi `NO_OBSERVATION`. Trường hợp này **không bao giờ** được hiểu là "ra ngoài ROI". Với frame có chất lượng khác `GOOD`, không tính `inside_roi` và vị trí để phân loại *(HS §5.2)*.
- **R9.** `observation_quality` được ghi vào `BodyStateSnapshot` của `EngineOutput`. Đặc trưng chính được đưa vào `explanation` khi bước sau cần *(event-engine.md mục 1, mục 2)*.
- **R10.** Builder `PoseSequence` hỗ trợ ít nhất: `lying`, `raise_to_sitting`, `sitting`, `move_to_edge`, `standing`, `walk_out`, `noise`, `drop_landmarks`, `add_person_outside_roi`, `add_second_person_in_roi` *(testing.md mục 2)*. Các thao tác `turn_over`, `fast_drop`, `face` được thêm ở feature cần tới (F15, F23, F26) *(giả định: chia việc theo feature)*.
- **R11.** Mọi ngưỡng đọc từ `EngineConfig`, không viết cứng số trong code *(event-engine.md mục 1; QA#22)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/engine/target.py`, `features.py`, `smoothing.py`, `quality.py`.
  - `server/src/postcare/engine/geometry.py`: hàm điểm-trong-polygon, khoảng cách có dấu tới biên, trục chính ROI *(giả định: module phụ trợ, không có trong bảng mục 3 của event-engine.md)*.
  - `server/src/postcare/engine/engine.py` (tạo ở F10): ghép bước 1–3 và cổng chất lượng.
  - Test: `server/tests/engine/builders.py`, `test_features.py`, `test_target.py`, `test_quality.py`, `test_engine_quality_gate.py`.
- **Dữ liệu:** không có bảng mới. Dùng enum `observation_quality` (cần khớp với `postcare.schemas`).
- **API:** không có.
- **UI:** không có.
- **Cấu hình** (`config/engine.default.yaml`): `pose.num_poses`, `pose.min_keypoint_visibility`, `pose.required_keypoints`, `quality.low_quality_to_no_observation_s`, `quality.restore_duration_s`, `target.max_jump_torso_lengths`, `smoothing.ema_alpha`. Không cần khóa mới.

## 5. Acceptance criteria

- [x] **AC1.** Đặc trưng tính đúng trên toạ độ tổng hợp: `hip_center`, `shoulder_center`, `trunk_angle_deg` (so với trục dài của giường, có tính tỷ lệ khung hình), `torso_length`, `dist_to_roi_edge` (đúng dấu trong/ngoài), `ankles_outside_roi`, `velocity` đã làm mượt *(PDF §6.1 (tr.7); HS §5.2)*. — *Kiểm chứng:* `server/tests/engine/test_features.py` (`test_centers_and_torso_length`, `test_trunk_angle_relative_to_bed_axis`, `test_trunk_angle_uses_pixel_aspect_ratio`, `test_dist_to_roi_edge_sign`, `test_ankles_outside_roi_ignores_low_visibility`, `test_velocity_smoothed_from_ts_ms`).
- [x] **AC2.** Người mục tiêu là người có tâm hông trong ROI và liên tục với vị trí trước. Người đứng ngoài ROI (điều dưỡng, người đi ngang) không trở thành mục tiêu. Nhảy xa hơn `target.max_jump_torso_lengths` thì coi là người khác *(QA#20; PDF §13.1 (tr.14); HS §8.1)*. — *Kiểm chứng:* `server/tests/engine/test_target.py` (`test_person_outside_roi_never_becomes_target`, `test_target_tracked_by_continuity_outside_roi`, `test_jump_over_threshold_is_new_person`).
- [x] **AC3.** Có ≥ 2 người trong ROI → `MULTIPLE_PEOPLE`. Keypoint chính có visibility thấp → `LOW_CONFIDENCE`. `source_ok = false` → `CAMERA_ISSUE` *(QA#20; PDF §17 (tr.17))*. — *Kiểm chứng:* `server/tests/engine/test_quality.py` (`test_two_people_in_roi_is_multiple_people`, `test_low_visibility_required_keypoint_is_low_confidence`, `test_source_not_ok_is_camera_issue`).
- [x] **AC4.** Chất lượng kém liên tục ≥ `quality.low_quality_to_no_observation_s` → `Engine.process` trả `NO_OBSERVATION` và không kết luận tư thế. Chất lượng kém ngắn hơn ngưỡng không đổi trạng thái. Muốn thoát phải `GOOD` liên tục ≥ `quality.restore_duration_s` *(PDF §4.3 (tr.6), §13.4 (tr.15); HS §5.2)*. — *Kiểm chứng:* `server/tests/engine/test_engine_quality_gate.py` (`test_prolonged_low_quality_goes_no_observation`, `test_short_low_quality_keeps_state`, `test_restore_requires_restore_duration`).
- [x] **AC5.** Engine xác định và thuần: chạy hai lần trên cùng chuỗi với cùng cấu hình cho output giống hệt; không import thư viện bị cấm *(event-engine.md mục 1)*. — *Kiểm chứng:* `test_engine_deterministic_same_sequence_same_output`; `make lint-imports`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit | Toạ độ tổng hợp có đáp án tính tay: thân song song / vuông góc trục giường, ROI xoay 30°, khung 16:9 | Cổ chân visibility thấp không được tính là ngoài ROI |
| AC2 | unit (builder) | `PoseSequence.lying(...)`, `.add_person_outside_roi(...)`, mục tiêu đi ra khỏi ROI | Điều dưỡng ngoài ROI; người đi ngang sát mép giường không "cướp" mục tiêu |
| AC3 | unit | Hai người trong ROI; ẩn visibility vai/hông; `source_ok=false` | Người thứ hai **ngoài** ROI không gây `MULTIPLE_PEOPLE` |
| AC4 | unit (builder) | `.drop_landmarks(seconds=…)` dài và ngắn hơn ngưỡng | `.noise(frames=1..3)` không gây `NO_OBSERVATION` |
| AC5 | unit + lệnh | Chạy `run_engine` hai lần, so sánh output; `make lint-imports` | — |

**Ca âm tính bắt buộc** ([testing.md](../04-guides/testing.md) mục 2) thuộc F13:

| Tình huống | Kỳ vọng ở F13 | Test |
|---|---|---|
| Nhiễu 1–3 frame (visibility tụt hoặc keypoint nhảy) | Không vào `NO_OBSERVATION`, đặc trưng đã làm mượt không nhảy | `test_noise_1_to_3_frames_no_quality_transition` |
| Mất landmark / bị che khi đang ở mép giường | `LOW_CONFIDENCE` → `NO_OBSERVATION`; không tính vị trí "ngoài ROI" từ frame bị che | `test_landmark_loss_at_edge_is_not_out_of_roi` |
| Điều dưỡng đứng cạnh giường (ngoài ROI) | Không trở thành mục tiêu; đặc trưng của bệnh nhân không đổi | `test_nurse_outside_roi_ignored` |
| Hai người trong ROI | `MULTIPLE_PEOPLE` → `NO_OBSERVATION` | `test_two_people_in_roi_goes_no_observation` |

Các ca còn lại của bảng (ngồi dậy rồi nằm lại, dao động quanh ngưỡng, trở mình, debounce, khuôn mặt) được kiểm ở F14, F15, F23, F26, F27.

## 7. Giả định

- *(giả định)* Góc và khoảng cách tính trong hệ pixel (R2).
- *(giả định)* Trục dài của giường tính bằng PCA trên các đỉnh polygon ROI (R3).
- *(giả định)* Mục tiêu được bám liên tục cả khi ra ngoài ROI. Chỉ khi nhận mục tiêu mới mới bắt buộc tâm hông nằm trong ROI (R5).
- *(giả định)* Thứ tự ưu tiên khi nhiều điều kiện chất lượng cùng đúng (R6).
- *(giả định)* Khi chất lượng kém chưa đủ lâu thì giữ trạng thái cũ và bỏ đặc trưng của frame kém (R7).
- *(giả định)* Reset bộ làm mượt khi đổi mục tiêu hoặc thoát `NO_OBSERVATION` (R4).
- *(giả định)* Module phụ trợ `engine/geometry.py`.
- *(giả định)* `hip_center` cần đủ hai hông, không xét visibility (dùng để định vị và đếm người trong ROI). Keypoint bắt buộc bị thiếu coi như visibility = 0.
- *(giả định)* Frame không khớp ai thì vẫn nhớ vị trí mục tiêu và không nhận người mới, cho tới khi cổng chất lượng đóng và frame không có mục tiêu. Nhận mục tiêu mới khi có nhiều người trong ROI: người sâu nhất trong ROI.
- *(giả định)* Cổng chất lượng khởi động ở trạng thái đóng (`NO_OBSERVATION`), nên lúc bắt đầu cũng cần `GOOD` liên tục ≥ `quality.restore_duration_s`.
- *(giả định)* Bộ làm mượt chỉ cập nhật ở frame `GOOD`; keypoint tùy chọn (gối, cổ chân) không thấy ở một frame thì bỏ giá trị làm mượt cũ của điểm đó.

## 8. Câu hỏi mở

- Không có câu hỏi chặn. Hiệu quả của PCA với ROI gần vuông (giường nhìn chéo) sẽ được kiểm tra khi có video dev (F16). Nếu kém thì đổi sang cách lấy cạnh dài nhất và cập nhật event-engine.md (không chặn).

## 9. Kế hoạch triển khai

Code hiện có dùng lại: `postcare/engine/pipeline.py` (khung F10: `TargetSelector`, `QualityAssessor`, `StateMachine`, `FrameAssessment`), `postcare/engine/engine.py`, `postcare/schemas/{observation,roi,engine_config,enums}.py`. Không thêm thư viện, không migration, không API, không sinh lại type.

1. **Kế hoạch** (commit `docs(F13): plan`).
2. **Test trước** (commit `test(F13): …`), chạy để thấy fail vì thiếu module/hành vi:
   - `server/tests/engine/builders.py`: `PoseSequence` (R10) dựng `FrameObservation` từ mô hình thân tổng hợp (tâm hông, góc thân, chiều dài thân theo pixel; chân), không có ảnh. Kèm `run_engine`, `default_config`.
   - `test_geometry.py` (điểm trong polygon, khoảng cách có dấu, trục PCA).
   - `test_features.py` (AC1), `test_target.py` (AC2), `test_quality.py` (AC3), `test_engine_quality_gate.py` (AC4, AC5 và 4 ca âm tính của mục 6), `test_engine_static_guards.py` (AST: `postcare.engine` không import `time`/`datetime`).
3. **`engine/geometry.py`**: `BedGeometry` (đỉnh ROI theo pixel, góc trục dài PCA), `point_in_polygon`, `signed_distance_to_edge`, `angle_to_axis_deg`.
4. **`engine/features.py` + `engine/smoothing.py`**: `BodyFeatures` (frozen dataclass), `FeatureExtractor.update(person, obs)`, `reset()`. EMA từng keypoint dùng tới (vai, hông, gối, cổ chân; theo pixel), đặc trưng suy ra từ điểm đã làm mượt; `velocity` = (vx, vy) của `hip_center` đã làm mượt, đơn vị torso_length/giây, 0 ở frame đầu sau reset.
5. **`engine/target.py`**: `TargetSelector.select(obs) -> TargetSelection(target, persons_in_roi, changed)`, `forget()`.
6. **`engine/quality.py`**: `assess_frame_quality` (R6) và `QualityGate` (R7, hysteresis theo `obs.ts_ms`).
7. **`engine/engine.py`**: ghép bước 1–3 + cổng chất lượng; xóa phần tương ứng khỏi `pipeline.py`. `FrameAssessment` thêm `features` (chỉ có khi frame `GOOD`) và `observable`.
8. **Static guard**: test AST trong `test_engine_static_guards.py` (import-linter không chặn được module stdlib một cách tin cậy; nếu chặn được thì thêm contract).
9. **Doc**: `event-engine.md` mục 2–3 (cổng chất lượng, giữ mục tiêu); không đổi khóa cấu hình. `make check`, `scripts\dev.ps1 check`, ghi mục 10.

**Quyết định thiết kế** *(giả định, ghi thêm ở mục 7)*:
- Người có đủ hai hông (bất kể visibility) mới có `hip_center`; dùng cho chọn mục tiêu và đếm người trong ROI. Chỉ xét `obs.persons[:pose.num_poses]`.
- Keypoint bắt buộc bị thiếu coi như visibility = 0 → `LOW_CONFIDENCE`.
- Ngưỡng nhảy = `max_jump_torso_lengths × torso_length` của mục tiêu ở frame trước (nếu chưa biết thì dùng của ứng viên).
- Nhớ vị trí mục tiêu qua frame không khớp ai, cho tới khi cổng chất lượng đóng (`NO_OBSERVATION`). Trong lúc còn nhớ, người không khớp **không** được nhận làm mục tiêu mới, kể cả khi ở trong ROI: nhiễu nhảy keypoint 1–3 frame chỉ cho `NO_PERSON` ngắn, đặc trưng không nhảy; người khác thật sự thay chỗ thì đi qua `NO_OBSERVATION`.
- Nhiều người trong ROI lúc nhận mục tiêu mới: chọn người nằm sâu nhất trong ROI (khoảng cách tới biên lớn nhất), hòa thì người đứng trước trong danh sách.
- Bộ làm mượt chỉ cập nhật ở frame `GOOD`.
- Chưa có F14: khi cổng mở, trạng thái do `StateMachine` (khung F10, luôn `NO_OBSERVATION`) quyết định. Test AC4 ở mức `Engine` thay `StateMachine` bằng bản giả (trả `LYING`) để kiểm cổng chất lượng.

**Test theo AC:** như cột "Kiểm chứng" ở mục 5 và bảng ca âm tính ở mục 6.

**Rủi ro:** PCA với ROI gần vuông (mục 8); chưa có video thật nên ngưỡng chưa hiệu chỉnh (F16).

## 10. Ghi chú bàn giao

**Kiểm chứng (2026-11-17, nhánh `feat/F13-body-features`):** `make check` exit 0 (pytest 251 passed, vitest 30 passed, import-linter 9 contract kept); `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check` exit 0. Không phải feature vision (không gọi MediaPipe), không cần `make test-vision`.

| AC | Bằng chứng |
|---|---|
| AC1 | `server/tests/engine/test_features.py` (6 test theo tên ở mục 5 + `test_shoulder_line_angle`, `test_static_pose_stable_and_reset`); hình học ở `test_geometry.py` (ROI xoay 0/30/90/135°, trục PCA theo pixel) |
| AC2 | `server/tests/engine/test_target.py`: 3 test theo tên ở mục 5 + `test_nurse_outside_roi_does_not_replace_patient`, `test_walker_passing_near_edge_does_not_steal_target`, `test_nearest_person_wins_continuity`, `test_only_num_poses_persons_considered` |
| AC3 | `server/tests/engine/test_quality.py`: 3 test theo tên ở mục 5 + ca âm tính `test_second_person_outside_roi_is_not_multiple_people`, `test_low_visibility_optional_keypoint_is_still_good`; thứ tự ưu tiên; 4 test `QualityGate` |
| AC4 | `server/tests/engine/test_engine_quality_gate.py`: 3 test theo tên ở mục 5 (+ `test_startup_requires_restore_duration`); ca âm tính mục 6: `test_noise_1_to_3_frames_no_quality_transition` (1–3 frame, visibility và nhảy keypoint), `test_landmark_loss_at_edge_is_not_out_of_roi`, `test_nurse_outside_roi_ignored`, `test_two_people_in_roi_goes_no_observation` |
| AC5 | `test_engine_deterministic_same_sequence_same_output` (+ bản có state machine giả); `make lint-imports` gồm contract mới `engine-no-clock` (cấm `time`, `datetime`, `random`, đã thử thêm `import time` thì contract BROKEN); `test_engine_static_guards.py` quét AST (bắt cả `__import__`) |

**Điều người sau cần biết:**
- Chưa có F14 nên `StateMachine` (khung F10) vẫn luôn trả `NO_OBSERVATION`: output thật của engine chưa đổi. Test AC4 thay `StateMachine` bằng bản giả qua `monkeypatch` (`postcare.engine.engine.StateMachine`). F14 thay khung này: `update(assessment, ts_ms)` chỉ được gọi khi cổng mở và frame `GOOD`, `assessment.features` luôn có; vào/ra `NO_OBSERVATION` do `Engine` xử lý.
- `FrameAssessment` giờ có `quality`, `target`, `features: BodyFeatures | None`, `observable`, `persons_in_roi`. `TargetSelector`/`QualityAssessor` đã chuyển khỏi `pipeline.py` sang `target.py`/`quality.py`.
- R9: `observation_quality` đã nằm trong `BodyStateSnapshot`. `BodyStateSnapshot` chưa có trường `explanation`; đặc trưng sẽ đưa vào `explanation` của sự kiện khi F14/F15 cần.
- Builder `server/tests/engine/builders.py`: `PoseSequence` (đủ các thao tác R10, thêm `hold`, `pose`, `move_to`, `camera_issue`, `remove_extra_people`), `person_from_px`, `frame`, `run_engine`, `default_config`, tư thế mẫu `LYING`/`SITTING`/`AT_EDGE`/`STANDING`/`OUTSIDE`/`NURSE`.
- Không thêm khóa cấu hình, không thêm thư viện.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
