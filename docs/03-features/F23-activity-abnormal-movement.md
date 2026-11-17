# F23 – Mức vận động và chuyển động bất thường

| Thuộc tính | Giá trị |
|---|---|
| Mã | F23 |
| Trạng thái | Done |
| Ưu tiên | MVP |
| Milestone | M2 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F15 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §7 (tr.8), §7.3 (tr.9), bảng tr.10, §13.1 (tr.14); HS §5.1, §5.2, §5.4, §8.1; ADR-0009; A11 |

## 1. Mục tiêu

Feature này theo dõi **mức vận động** theo thời gian (ít / bình thường / nhiều) và phát hiện **chuyển động bất thường cần kiểm tra**, như hạ thấp nhanh, dịch chuyển mạnh, đổi hướng thân đột ngột (HS §5.1, §5.2). Đây là bước 7 của pipeline ([event-engine.md](../02-architecture/event-engine.md) mục 3). Sự kiện dùng mã `ABNORMAL_MOVEMENT`, text "Phát hiện chuyển động bất thường - đề nghị kiểm tra" ([ADR-0009](../02-architecture/decisions/ADR-0009-abnormal-movement-code.md)). Thiết kế phải thận trọng (PDF §7.3 (tr.9)): chỉ sinh sự kiện khi **nhiều điều kiện cùng xảy ra** trong cửa sổ ngắn; trở mình bình thường chỉ được lưu nhật ký (HS §5.2). `activity_level` còn là đầu vào cho F26 (nâng ưu tiên tín hiệu mặt) và F27 (trạng thái nghỉ/hoạt động).

## 2. Phạm vi

**Trong phạm vi**
- Chỉ số vận động trên cửa sổ trượt và `activity_level` (`engine/activity.py`).
- Sự kiện `ACTIVITY_INCREASED`, `ACTIVITY_LOW_PROLONGED`, `ABNORMAL_MOVEMENT` (`engine/rules/movement.py`).
- Thao tác `fast_drop(...)` trong builder (F13).
- Chạy đánh giá trên tập dev bằng F16 cho các code trên.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Kết luận "té ngã", nguyên nhân hay hậu quả y khoa của chuyển động *(HS §9.1; PDF §7.3 (tr.9); glossary.md: từ cấm)*.
- Nâng ưu tiên `FACE_ATTENTION` khi vận động cao (→ F26). Trạng thái nghỉ/hoạt động (→ F27).
- Hiển thị `activity_level` trên dashboard *(chưa có AC; F26 hiển thị tín hiệu trên Theo dõi trực tiếp)*.
- Classifier học máy cho hành vi *(HS §5.5: hướng mở rộng)*.

## 3. Yêu cầu chi tiết

- **R1.** Engine thuần, xác định, chỉ dùng `ts_ms`; mọi ngưỡng lấy từ `EngineConfig` *(event-engine.md mục 1)*.
- **R2.** Chỉ số vận động: trung bình trên cửa sổ `activity.window_s` của tốc độ dịch chuyển các keypoint của người mục tiêu có visibility ≥ `pose.min_keypoint_visibility`, chia `torso_length` (đơn vị torso_length/giây) *(PDF §7 (tr.8), bảng tr.10: "Pose delta theo thời gian"; HS §5.1: "độ dịch chuyển theo thời gian, tốc độ thay đổi"; giả định: công thức cụ thể và tập keypoint, ghi vào event-engine.md khi chốt)*.
- **R3.** `activity_level` *(event-engine.md mục 5, trạng thái hiển thị)*:
  - `LOW` khi chỉ số < `activity.low_threshold`;
  - `HIGH` khi chỉ số > `activity.high_threshold`;
  - `NORMAL` khi ở giữa.
- **R4.** Khi `NO_OBSERVATION`, hoặc khi cửa sổ chưa đủ dữ liệu, hoặc ngay sau khi đổi người mục tiêu: `activity_level` là **chưa xác định** và các bộ đếm thời gian được reset. Mất quan sát **không** được tính là "ít vận động" *(HS §5.2, §9.1: thiếu dữ liệu không được suy diễn; giả định: cần thêm giá trị `UNKNOWN` cho `activity_level` trong schema, event-engine.md và `bed.state` của api-conventions.md)*.
- **R5.** `ACTIVITY_INCREASED` (LOG, A11): `activity_level` chuyển lên `HIGH` và giữ ≥ `activity.increased_hold_s` *(HS §5.1; event-engine.md mục 5)*.
- **R6.** `ACTIVITY_LOW_PROLONGED` (LOG, A11): `activity_level = LOW` liên tục ≥ `activity.low_prolonged_s` *(HS §5.1; event-engine.md mục 5)*. Phát một lần cho mỗi đoạn LOW liên tục, rồi qua debounce *(giả định)*.
- **R7.** `ABNORMAL_MOVEMENT` (HIGH, tạo cảnh báo) *(HS §5.2, §5.4; PDF §7.3 (tr.9); ADR-0009; event-engine.md mục 5, mục 6)*. Điều kiện xét trong cửa sổ `abnormal_movement.window_s`:
  - **C1. Hông hạ nhanh:** tốc độ đi xuống (theo trục dọc ảnh) của `hip_center` ≥ `abnormal_movement.hip_drop_speed_torso_per_s`.
  - **C2. Dịch chuyển mạnh:** quãng dịch chuyển của `hip_center` ≥ `abnormal_movement.displacement_torso`.
  - **C3. Đổi hướng thân đột ngột:** thay đổi `trunk_angle_deg` ≥ `abnormal_movement.trunk_angle_change_deg`.
  - **C4. Vị trí cuối thấp:** vị trí dọc của `hip_center` sau chuyển động ≥ `abnormal_movement.final_low_position_ratio` *(giả định: tỷ lệ theo chiều cao khung hình; comment trong YAML ghi "khung/ROI")*.
  - **C5. Giữ nguyên sau đó:** sau chuyển động, `hip_center` gần như đứng yên trong ≥ `abnormal_movement.hold_after_s` *(giả định: "gần như đứng yên" = chỉ số vận động < `activity.low_threshold`)*.
  
  Sinh sự kiện khi số điều kiện thỏa ≥ `abnormal_movement.min_conditions`. `occurred_at_ms` là lúc bắt đầu chuyển động nhanh; `detected_at_ms` là lúc đủ điều kiện (sau `hold_after_s` nếu C5 được dùng).
- **R8.** Không sinh `ABNORMAL_MOVEMENT` khi *(HS §5.2; PDF §7.3 (tr.9))*:
  - một phần cửa sổ nằm trong `NO_OBSERVATION` hoặc có chất lượng khác `GOOD`;
  - người mục tiêu vừa đổi (nhảy vượt `target.max_jump_torso_lengths`, F13). Bước nhảy do đổi người không phải chuyển động *(giả định)*.
- **R9.** `explanation` của `ABNORMAL_MOVEMENT` ghi điều kiện nào thỏa (C1–C5) kèm giá trị đo được. Các sự kiện vận động ghi chỉ số vận động và khoảng thời gian *(event-engine.md mục 1; HS §6.2)*.
- **R10.** Mọi code của feature đi qua debounce chung `engine/debounce.py` của F15 (`debounce.same_code_same_session_s`) *(A01)*.
- **R11.** `activity_level` được đưa vào `BodyStateSnapshot` để worker gửi trong `state` (F17) *(event-engine.md mục 2)*.
- **R12.** Chạy `postcare eval --split dev` (F16) trên các video có kịch bản S02 (trở mình), S15 (chuyển động nhanh xuống nệm an toàn), S16 (ít vận động kéo dài) ở [evaluation.md](../04-guides/evaluation.md). Ghi P/R/F1 và FP/giờ cho `ABNORMAL_MOVEMENT`, `ACTIVITY_*` *(HS §8.1, §8.2; ADR-0008)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/engine/activity.py`: chỉ số vận động, `activity_level`.
  - `server/src/postcare/engine/rules/movement.py`: `ACTIVITY_INCREASED`, `ACTIVITY_LOW_PROLONGED`, `ABNORMAL_MOVEMENT`.
  - `server/src/postcare/engine/engine.py`: nối bước 7.
  - `server/src/postcare/schemas/`: thêm giá trị chưa xác định cho `activity_level` (R4).
  - Test: `server/tests/engine/test_activity.py`, `test_rules_movement.py`; thêm `fast_drop` vào `builders.py`.
- **Dữ liệu:** không có bảng mới. Code `ACTIVITY_INCREASED`, `ACTIVITY_LOW_PROLONGED`, `ABNORMAL_MOVEMENT` đã có trong enum `event_code` (F10, F17).
- **API:** không có endpoint mới. `bed.state.activity_level` có thêm giá trị chưa xác định (R4).
- **UI:** không có.
- **Cấu hình:** `activity.window_s`, `activity.low_threshold`, `activity.high_threshold`, `activity.low_prolonged_s`, `activity.increased_hold_s`, `abnormal_movement.window_s`, `abnormal_movement.hip_drop_speed_torso_per_s`, `abnormal_movement.displacement_torso`, `abnormal_movement.trunk_angle_change_deg`, `abnormal_movement.final_low_position_ratio`, `abnormal_movement.hold_after_s`, `abnormal_movement.min_conditions`, `pose.min_keypoint_visibility`, `debounce.same_code_same_session_s`. Không cần khóa mới.

## 5. Acceptance criteria

- [x] **AC1.** Chỉ số vận động tính trên cửa sổ trượt, chuẩn hóa theo `torso_length`, cho ra `LOW` / `NORMAL` / `HIGH`. Mất quan sát cho ra "chưa xác định", không phải `LOW` *(HS §5.1; PDF §7 (tr.8))*. — *Kiểm chứng:* `server/tests/engine/test_activity.py` (`test_still_body_is_low`, `test_moderate_motion_is_normal`, `test_vigorous_motion_is_high`, `test_index_invariant_to_body_scale`, `test_no_observation_gives_unknown_not_low`).
- [x] **AC2.** `ACTIVITY_INCREASED` và `ACTIVITY_LOW_PROLONGED` sinh ở mức LOG *(HS §5.1; A11)*. — *Kiểm chứng:* `test_rules_movement.py` (`test_activity_increased_after_hold`, `test_activity_low_prolonged_after_threshold`, `test_activity_events_are_log`).
- [x] **AC3.** `ABNORMAL_MOVEMENT` (HIGH) sinh khi hạ thấp nhanh, dịch chuyển mạnh hoặc đổi hướng thân đột ngột, với ≥ `abnormal_movement.min_conditions` điều kiện thỏa trong cửa sổ ngắn; `explanation` ghi điều kiện nào thỏa *(HS §5.2, §5.4; PDF §7.3 (tr.9); ADR-0009)*. — *Kiểm chứng:* `test_rules_movement.py` (`test_fast_drop_emits_abnormal_movement_high`, `test_below_min_conditions_no_event`, `test_explanation_lists_conditions`).
- [x] **AC4.** Trở mình bình thường không sinh `ABNORMAL_MOVEMENT` *(HS §5.2)*. — *Kiểm chứng:* `test_turn_over_no_abnormal_movement`.
- [x] **AC5.** Có kết quả đánh giá trên tập dev (F16) cho `ABNORMAL_MOVEMENT`, `ACTIVITY_INCREASED`, `ACTIVITY_LOW_PROLONGED` *(HS §8.2; ADR-0008)*. — *Kiểm chứng:* lệnh `postcare eval --split dev` → `reports/eval-dev-<date>.md` có các dòng này; ghi đường dẫn báo cáo ở mục 10.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit (builder) | Nằm yên; cử động tay vừa phải; vận động mạnh; cùng chuyển động ở hai kích thước người khác nhau | `drop_landmarks` dài không cho `LOW` |
| AC2 | unit (builder) | Vận động mạnh giữ dài/ngắn hơn `increased_hold_s`; nằm yên dài/ngắn hơn `low_prolonged_s` | Nằm yên xen đoạn mất quan sát → bộ đếm reset, không sinh `ACTIVITY_LOW_PROLONGED` |
| AC3 | unit (builder) | `.standing().fast_drop()` + nằm yên sau đó; tổ hợp từng điều kiện C1–C5 | Chỉ 1–2 điều kiện thỏa → không có sự kiện |
| AC4 | unit (builder) | `.lying().turn_over().lying()` | Có `POSTURE_CHANGE`, không `ABNORMAL_MOVEMENT` |
| AC5 | lệnh / thủ công | Chạy eval trên video dev S02, S15, S16 | S02 không có `ABNORMAL_MOVEMENT` |

**Ca âm tính bắt buộc** ([testing.md](../04-guides/testing.md) mục 2) thuộc F23:

| Tình huống | Kỳ vọng ở F23 | Test |
|---|---|---|
| Trở mình | `POSTURE_CHANGE` (LOG), **không** `ABNORMAL_MOVEMENT` | `test_turn_over_no_abnormal_movement` |
| Nhiễu 1–3 frame (keypoint nhảy) | Không `ABNORMAL_MOVEMENT`, không `ACTIVITY_INCREASED` | `test_keypoint_jump_1_to_3_frames_no_movement_event` |
| Mất landmark / bị che | Không `ABNORMAL_MOVEMENT`; không tính là ít vận động | `test_occlusion_no_abnormal_movement_no_low_activity` |
| Điều dưỡng / người đi ngang ngoài ROI di chuyển nhanh | Không sự kiện vận động (không phải người mục tiêu) | `test_fast_passerby_outside_roi_no_event` |
| Hai người trong ROI | Không sự kiện vận động (đang `NO_OBSERVATION`) | `test_two_people_in_roi_no_movement_event` |
| Lặp sự kiện trong cửa sổ debounce | Chỉ 1 sự kiện | `test_abnormal_movement_debounced` |

Thêm ca âm tính riêng: nằm xuống chậm từ tư thế ngồi không sinh `ABNORMAL_MOVEMENT` (`test_slow_lie_down_no_abnormal_movement`); đổi người mục tiêu không sinh sự kiện (`test_target_switch_no_abnormal_movement`).

## 7. Giả định

- *(giả định)* Công thức chỉ số vận động và tập keypoint (R2).
- *(giả định)* `activity_level` có giá trị "chưa xác định" khi mất quan sát; cần thêm vào schema và tài liệu (R4).
- *(giả định)* `ACTIVITY_LOW_PROLONGED` phát một lần mỗi đoạn LOW liên tục (R6).
- *(giả định)* C4 tính theo chiều cao khung hình; C5 dùng `activity.low_threshold` (R7).
- *(giả định)* Đổi người mục tiêu thì không xét chuyển động bất thường (R8).
- Mức ưu tiên `ACTIVITY_*` là LOG (A11).
- *(giả định, đổi khi làm)* Tốc độ keypoint đo trên bước `activity.sample_interval_s` (khóa mới, 1 s) chứ không giữa hai frame liền nhau, và chỉ số là **trung vị** (không phải trung bình) các mẫu trong cửa sổ. Lý do ở mục 10 (nhiễu MediaPipe; nhiễu 1–3 frame).
- *(giả định)* C1–C5 chấm với vị trí **cuối** sau `hold_after_s` (C2, C3 so với mẫu trước chuyển động), để keypoint nhảy rồi quay về không được tính; chi tiết ở event-engine.md mục 5.
- *(giả định, chốt 18/11/2026)* `ABNORMAL_MOVEMENT` cần **thêm** ít nhất một điều kiện hạ thấp (C1 hông hạ nhanh hoặc C4 vị trí cuối thấp) ngoài `min_conditions` (HS §8.1 "chuyển động nhanh xuống nệm"; ADR-0009). Đứng dậy nhanh từ sàn rồi đứng yên, đi rồi dừng không cảnh báo. Giới hạn: C4 là vị trí tuyệt đối, đi rồi dừng khi hông đã ở thấp trong khung vẫn có thể đủ.
- *(giả định)* `occurred_at_ms` = mẫu đầu tiên có tốc độ hông ≥ `hip_drop_speed_torso_per_s`; vận tốc hông chia torso lớn hơn giữa frame và mốc.

## 8. Câu hỏi mở

- **Đã chốt (18/11/2026):** bắt buộc một điều kiện hạ thấp (C1 hoặc C4), xem mục 7.
- **Không chặn (mới, F23):** `activity.low_threshold = 0,02` thấp hơn nhiễu tĩnh của MediaPipe đo được (~0,02–0,07 torso/s ở 720p, cao hơn ở 320×240), nên `ACTIVITY_LOW_PROLONGED` và C5 hiếm khi thỏa trên video thật. Giữ mặc định 0,02; điều phối hiệu chỉnh sau khi có kết quả eval F16.

- **Không chặn:** C4 (`final_low_position_ratio`) chỉ có nghĩa khi camera nhìn thấy sàn cạnh giường. Nếu vị trí camera chốt ở tuần 1–2 không thấy sàn, C4 có thể luôn sai, và khi đó cần hạ `abnormal_movement.min_conditions` qua override camera. Kiểm bằng S15 trên tập dev.
- **Không chặn (phụ thuộc ngoài code):** AC5 cần video dev của S02, S15, S16 và ground truth.

## 9. Kế hoạch triển khai

**Khảo sát:** `ActivityLevel.UNKNOWN` đã có trong `schemas/enums.py`, event-engine.md mục 2/5 và api-conventions.md (`bed.state`), nên R4 không cần sửa schema. `Engine._snapshot` đang luôn trả `UNKNOWN`. `BodyFeatures` (F13) có `hip_center`, `torso_length`, `trunk_angle_deg` (so với trục giường, [0°, 90°]), `velocity` (torso/s, từ hông đã làm mượt), `image_size`. `TargetSelector` báo `is_new` nhưng `FrameAssessment` chưa mang cờ này. `RuleSet` (F15) chỉ có `BodyRules`; `Debouncer` dùng chung. `BodyRules` có bộ đệm visibility cho `confidence`.

**Thiết kế chốt:**
- `FrameAssessment.target_is_new: bool = False` (engine điền từ `TargetSelection.is_new`).
- `engine/activity.py` `ActivityMeter(config)`: tập keypoint *(giả định)* = vai, khuỷu, cổ tay, hông, gối, cổ chân (12 điểm) có visibility ≥ `pose.min_keypoint_visibility`, làm mượt EMA (`smoothing.ema_alpha`, `PointSmoother` của F13). Mỗi frame có đặc trưng: tốc độ frame = trung bình trên các keypoint thấy ở cả frame trước và frame này của `|Δp| / torso_length / Δt`. Chỉ số = trung bình có trọng số thời gian của tốc độ frame trong `activity.window_s` cuối. `activity_level = UNKNOWN` khi cửa sổ chưa phủ đủ `window_s` kể từ mẫu đầu. Reset (về `UNKNOWN`) khi cổng chất lượng đóng (`NO_OBSERVATION`) hoặc nhận mục tiêu mới. Frame kém nhưng cổng còn mở: không thêm mẫu, giữ mức hiện tại.
- `engine/rules/movement.py` `MovementRules(config)`:
  - `ACTIVITY_INCREASED`: mức chuyển sang `HIGH` (từ mức khác) và giữ liên tục ≥ `activity.increased_hold_s`; một lần mỗi đoạn HIGH. `ACTIVITY_LOW_PROLONGED`: `LOW` liên tục ≥ `activity.low_prolonged_s`; một lần mỗi đoạn LOW. Mức `UNKNOWN` cắt đoạn. `occurred_at_ms` = đầu đoạn.
  - `ABNORMAL_MOVEMENT`: bộ đệm mẫu `(ts, hip_center, torso, trunk_angle, vy)` các frame `GOOD` liên tục của cùng mục tiêu; frame không có đặc trưng, `NO_OBSERVATION` hoặc mục tiêu mới → xóa bộ đệm và hủy ứng viên (R8). Ở mỗi frame, cửa sổ `W = [t − window_s, t]`, mẫu tham chiếu = mẫu đầu của `W`: C1 = max `vy` (xuống) trong `W` ≥ ngưỡng; C2 = `|hip(t) − hip(ref)| / torso(ref)` ≥ ngưỡng; C3 = `|trunk(t) − trunk(ref)|` ≥ ngưỡng; C4 = `hip_y(t) / chiều cao ảnh` ≥ ngưỡng. Chỉ xét khi `W` phủ đủ `window_s`. Khi số điều kiện C1–C4 ≥ `min_conditions − 1` → mở / cập nhật ứng viên (mốc `t*` = frame gần nhất có số điều kiện ≥ của ứng viên). `occurred_at_ms` = mẫu đầu tiên trong `W` có tốc độ hông ≥ `hip_drop_speed_torso_per_s`, không có thì mẫu tham chiếu *(giả định)*. Sau `t*` đủ `hold_after_s`: C5 = chỉ số vận động trung bình trên `(t*, t* + hold_after_s]` < `activity.low_threshold`; tổng C1–C5 ≥ `min_conditions` → phát, không thì hủy. `explanation`: `rule_id`, `conditions_met`, giá trị đo và ngưỡng từng điều kiện, `min_conditions`, `window_ms`. Không xét ROI: chuyển động ngoài giường vẫn được xét khi mục tiêu còn được bám.
  - `confidence` dùng chung cách tính của F15 (tách bộ đệm visibility và `EventDraft` sang `engine/rules/common.py`).
- `RuleSet` ghép `BodyRules` + `MovementRules`, cùng một `Debouncer`. `Engine` đưa `activity_level` vào `BodyStateSnapshot` (R11), có thuộc tính `activity_index` (float | None) cho test/replay.
- Builder: `UPRIGHT` (đứng, hông giữa khung), `FLOOR` (nằm sàn cạnh giường, hông thấp trong khung, ngoài ROI), `CHAIR_SEATED`; `fast_drop(seconds, to=FLOOR)`, `limb_motion(seconds, speed_torso_per_s, …)` (dao động gối/cổ chân hoặc cả thân).

**Các bước:**
1. Commit plan (spec).
2. Test trước: `tests/engine/test_activity.py` (AC1 + R4), `tests/engine/test_rules_movement.py` (AC2–AC4, ca âm tính mục 6: trở mình, nhiễu 1–3 frame, che khuất, người đi ngang ngoài ROI, hai người trong ROI, debounce; thêm ngồi nhanh xuống ghế, cúi người, nằm xuống chậm, đổi mục tiêu, chưa đủ `min_conditions`). Xác nhận đỏ đúng lý do. Commit `test(F23): …`.
3. Cài `activity.py`, `rules/common.py`, `rules/movement.py`, nối `RuleSet`/`Engine`. Commit nhỏ.
4. Kiểm trên clip thật: `postcare replay --video` URFD cam0 (fall + ADL), CAUCAFall Subject 1–2, GMDCSA24 Subject 1 (cấu hình camera `config/cameras/urfd-cam0.yaml`, `caucafall.yaml`, ROI *(giả định)*). Ghi trúng/trượt ở mục 10. Cắt 1–2 fixture toạ độ (ngã + ADL âm tính) vào `server/tests/fixtures/`.
5. Doc: event-engine.md (công thức chỉ số vận động, cách xét C1–C5, mục 5/6 nếu khác).
6. `make check`, `scripts\dev.ps1 check`, `make test-vision`; bằng chứng mục 10; trạng thái "In review".

**Rủi ro:** nhiễu keypoint MediaPipe có thể làm chỉ số vận động của người nằm yên vượt `activity.low_threshold` (0,02 torso/s): đo trên clip thật, nếu cần đề xuất chỉnh ngưỡng mặc định (ghi ở mục 10, doc mục 6). AC5 cần F16 (`postcare eval`, đang làm song song) và video dev S02/S15/S16: chưa làm được trong nhánh này; thay bằng replay trên dữ liệu ngoài.

## 10. Ghi chú bàn giao

**Bằng chứng (2026-11-18, nhánh `feat/F23-activity-movement`):**
- AC1: `server/tests/engine/test_activity.py` (`test_still_body_is_low`, `test_moderate_motion_is_normal`, `test_vigorous_motion_is_high`, `test_leg_motion_only_counts_partially`, `test_index_invariant_to_body_scale[0.5/1.5]`, `test_window_not_filled_is_unknown`, `test_no_observation_gives_unknown_not_low[low_visibility/missing]`, `test_activity_resets_after_no_observation`, `test_activity_level_in_snapshot_changes_state` (R11), `test_activity_deterministic`).
- AC2: `test_rules_movement.py`: `test_activity_increased_after_hold`, `test_brief_high_activity_no_activity_increased`, `test_activity_low_prolonged_after_threshold`, `test_activity_low_prolonged_default_threshold` (300 s, 3 fps), `test_low_shorter_than_threshold_no_event`, `test_low_prolonged_emitted_once_per_segment`, `test_occlusion_resets_low_prolonged_counter[…]`, `test_activity_events_are_log`.
- AC3: `test_fast_drop_emits_abnormal_movement_high` (HIGH, `occurred_at_ms` trong lúc hạ, `detected_at_ms` ≥ cuối + `hold_after_s`, `config_hash`), `test_explanation_lists_conditions`, `test_each_condition_counted[5 điều kiện]` (tắt từng điều kiện: còn 4 → phát khi `min_conditions=4`, không phát khi 5), `test_below_min_conditions_no_event`, `test_abnormal_movement_outside_roi`, `test_abnormal_movement_debounced`, `test_abnormal_movement_after_debounce_window_emitted_again`, `test_abnormal_movement_deterministic`.
- Điều kiện hạ thấp bắt buộc (chốt 18/11/2026): `test_quick_get_up_from_floor_then_standing_no_abnormal_movement`, `test_walk_then_stop_no_abnormal_movement`, `test_no_lowering_condition_no_event_even_if_min_conditions_met`, `test_lowering_by_final_position_alone_is_enough` (đỏ trước khi sửa, commit `test(F23)` thứ hai). Kết quả replay thật bên dưới không đổi.
- AC4 và ca âm tính mục 6: `test_turn_over_no_abnormal_movement`, `test_keypoint_jump_1_to_3_frames_no_movement_event[1-3]`, `test_spike_to_floor_1_to_3_frames_no_abnormal_movement[1-3]` (nhiễu gần, vẫn bám mục tiêu), `test_occlusion_no_abnormal_movement_no_low_activity[…]`, `test_fast_passerby_outside_roi_no_event`, `test_two_people_in_roi_no_movement_event`, `test_target_switch_no_abnormal_movement`, `test_slow_lie_down_no_abnormal_movement`, `test_sitting_down_quickly_on_chair_no_abnormal_movement`, `test_sitting_down_quickly_on_bed_edge_no_abnormal_movement`, `test_bending_forward_no_abnormal_movement`.
- Test viết trước, đỏ vì `Engine` chưa có `activity_index`/sự kiện vận động (commit `test(F23)`, 24 test đỏ, test cũ xanh).
- Fixture từ clip thật (`server/tests/fixtures/`, regression `test_fixtures_regression.py`): `gmd_s1_fall12_abnormal_movement` (GMDCSA24 S1 Fall/12, ngã ngửa từ đứng, nhãn Falling 1,9–6 s → `BED_EXIT`@2,49 s, `ABNORMAL_MOVEMENT`@2,56 s) và `gmd_s1_adl06_sit_read_negative` (ADL/06 ngồi đọc sách → không sự kiện).
- Sau merge `main` (F16): `make check` exit 0 (738 passed, 5 deselected; web 66 passed); `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check` exit 0; `make test-vision` exit 0 (5 passed).
- **AC5 (2026-11-18, sau khi merge `main` có F16, commit `79b92b7`):** `uv run postcare eval --split dev --from-observations <runs/eval-dev của F16> --runs-dir ../runs/eval-dev-f23 --report ../reports/eval-dev-f23.local.md` (POSTCARE_DATA_DIR=D:\PostCareAi\data; chỉ engine trên observation đã cache, 189 video dev, 22,4 phút; `config_hash` `209d60d2…`). Báo cáo `reports/eval-dev-f23.local.md` (+ `.local.json`, gitignore).

  | Mã | TP | FP | FN | P | R | F1 | Latency trung vị |
  |---|---|---|---|---|---|---|---|
  | `ABNORMAL_MOVEMENT` (tổng) | 2 | 2 | 99 | 0,50 | 0,02 | 0,04 | 4,27 s |
  | – GMDCSA24 S1–S2 (41 ngã) | 2 | 1 | 39 | 0,67 | 0,05 | 0,09 | |
  | – URFD cam0 (30 ngã, camera ngang) | 0 | 1 | 30 | 0,00 | 0,00 | — | |
  | – URFD cam1 (30 ngã, camera trần, coverage 3,5 %) | 0 | 0 | 30 | — | 0,00 | — | |
  | `ABNORMAL_MOVEMENT` bỏ URFD cam1 (71 ngã) | 2 | 2 | 69 | 0,50 | 0,03 | 0,05 | |
  | `ACTIVITY_INCREASED` | — | — | — | — | — | — | 18 dự đoán, không có truth |
  | `ACTIVITY_LOW_PROLONGED` | — | — | — | — | — | — | 0 dự đoán (mọi clip < 300 s), không có truth |

  - FP/giờ trên clip ADL (kịch bản NEG, 78 video, 647,6 s): **11,1** (2 FP `ABNORMAL_MOVEMENT`: `urfd_adl11_cam0` @4,27 s, `gmd_s2_adl_09` @3,89 s). Toàn tập: 10,7 false alerts/giờ (thêm 2 FP `BED_EDGE` của F15 trên Pexels).
  - `ACTIVITY_*` không có P/R/F1: tập dev chưa có video S02/S16 và ground truth cho các mã này (truth chỉ có trong `eval_codes`; 43 dự đoán ngoài `eval_codes` bị bỏ qua, gồm 18 `ACTIVITY_INCREASED`). Cần video dev của nhóm (mục 8).
  - Manifest không có cột `camera_config` cho URFD nên eval dùng `example.yaml`. Chạy lại 70 video URFD cam0 với `--camera-config config/cameras/urfd-cam0.yaml`: vẫn 0/30 TP, 1 FP (`reports/eval-dev-f23-urfdroi.local.md`). URFD cam1 (camera trần) có coverage 3,5 %.
  - URFD cam1 (camera trần) gần như không có quan sát (coverage 3,5 %): góc nhìn ngoài phạm vi camera-setup.md, nên ghi riêng; recall có ý nghĩa nên tính trên 71 ngã còn lại.
  - Lý do recall thấp giống phần replay bên dưới: clip dừng 1–3 s sau khi ngã (rule chấm ≈ `window_s + hold_after_s` sau chuyển động; latency trung vị 4,27 s), frame không `GOOD` lúc ngã hủy cửa sổ (R8), C5 hiếm thỏa với `low_threshold = 0,02`. Ngưỡng giữ nguyên; điều phối hiệu chỉnh sau eval (mục 8).

**Kiểm trên clip thật (`postcare replay --video`, model full, 15 fps; cấu hình `config/cameras/urfd-cam0.yaml`, `caucafall.yaml` (ROI gần trọn khung, giả định), `gmdcsa24-subject1.yaml`):**

| Tập | Clip | `ABNORMAL_MOVEMENT` như clip gốc | Kéo dài khung cuối 5 s *(xấp xỉ "nằm yên sau đó")* |
|---|---|---|---|
| GMDCSA24 S1 Fall 01–16 | 16 ngã | 2/16 (11, 12; đúng khoảng Falling) | 8/16 (03, 04, 06, 11, 12, 15, 16 đúng khoảng; 10 trễ, sau khung cuối) |
| GMDCSA24 S1 ADL 01–08 | 8 ADL | 0 | 0 |
| URFD cam0 fall 01–08 | 8 ngã | 0/8 | 3/8 (03 đúng khoảng; 07, 08 trễ hơn mốc nằm) |
| URFD cam0 ADL 01–08 | 8 ADL | 0 | 2 (adl01; adl03 do keypoint lỗi: torso co còn 4–12 px) |
| CAUCAFall S1–S2 Fall* | 10 ngã | 0/10 | 1/10 |
| CAUCAFall S1–S2 ADL (SitDown, Pickupobject, Kneel, Walk, Hop) | 10 ADL | 0 | 0 |

Nguyên nhân trượt, theo thứ tự:
1. Clip kết thúc 1–3 s sau khi ngã, trong khi rule chấm sau khi hết dấu hiệu nhanh và giữ `hold_after_s` (≈ 3,5 s sau chuyển động): nhiều ca còn đang chờ ở cuối clip với 3 dấu hiệu nhanh (GMDCSA 03–08, 15, 16). Trên camera thật người nằm lại sàn nên không bị cắt; bảng "kéo dài" ước lượng phần này nhưng lạc quan với C5.
2. R8 nghiêm: frame `LOW_CONFIDENCE` ngay lúc ngã (URFD 01, 04, 05, 07; CAUCA FallForward, FallSitting; GMDCSA 01, 02, 13, 14 có phần thân ngoài khung) hủy cửa sổ.
3. C5 hiếm thỏa: trung vị tốc độ sau ngã thật 0,03–0,14 torso/s > `low_threshold` 0,02 (mục 8).
4. C4 phụ thuộc góc camera: CAUCAFall (camera cao nhìn chéo) có hông sau ngã ở ~0,55–0,6 chiều cao khung.

Chỉ số vận động: với tốc độ đo giữa hai frame liền nhau, người ngồi đọc sách yên (GMDCSA ADL/07) có 0,16–0,21 torso/s (> `high_threshold`). Đo trên bước 1 s: 0,02–0,07; đi lại 0,8–1,0; ngồi dậy 0,3–0,6. Vì vậy thêm `activity.sample_interval_s` và dùng trung vị (`activity.py`).

**Cho người sau:**
- `RuleSet.evaluate(ts_ms, assessment, body_state, history, activity)` có thêm `activity` (`ActivityReading`); `FrameAssessment.target_is_new`; `Engine.activity_index`. `EventDraft` và `VisibilityBuffer` dùng chung ở `engine/rules/common.py` (`BodyEventDraft` là tên cũ).
- Sự kiện vận động LOG xuất hiện song song với chuỗi cơ thể khi người bệnh cử động (ví dụ đi ra khỏi giường → `ACTIVITY_INCREASED`). Test F15 lọc theo mã F15. `snapshot.state_changed` cũng đổi khi `activity_level` đổi (worker gửi `state` nhiều hơn).
- Khóa mới `activity.sample_interval_s` làm đổi `config_hash`.
- Kịch bản dựng lại kết quả bảng trên: replay từng clip vào `runs/f23/<tên>/` rồi chạy engine trên `observations.jsonl` (`--from-observations`); script phân tích tạm không commit.

**Review (2026-11-18): Đạt.** Sửa theo review: tách URFD cam1 khỏi mẫu số recall (bảng AC5), ghi nguồn/giấy phép fixture GMDCSA24 (`server/tests/fixtures/SOURCES.md`), ghi rõ chuyển động còn đang chờ ở cuối luồng không được chấm (event-engine.md mục 5, `rules/movement.py`), cập nhật số test. Sau sửa: `make check` exit 0 (738 passed, 5 deselected; web 66 passed), `scripts\dev.ps1 check` exit 0.

**Giả thuyết hiệu chỉnh của reviewer (đầu vào cho việc hiệu chỉnh sau, chưa đổi ngưỡng):**
- **H1 – độ trễ quyết định so với cuối clip:** rule chấm ≈ `window_s + hold_after_s` (≈ 3,5 s; latency trung vị 4,27 s) sau chuyển động, trong khi clip dữ liệu ngoài dừng 1–3 s sau khi ngã; chuyển động còn chờ ở cuối luồng không được chấm. Thử: rút `hold_after_s` hoặc đánh giá trên clip dài/được kéo dài.
- **H2 – một frame `LOW_CONFIDENCE` reset cửa sổ:** R8 hủy cả chuyển động khi có một frame không `GOOD` lúc ngã (URFD 01, 04, 05, 07; GMDCSA 01, 02, 13, 14). Thử: cho phép gián đoạn ngắn (≤ vài frame) trong cửa sổ.
- **H3 – ngưỡng yên 0,02 so với 0,03–0,14 đo được:** C5 (và `ACTIVITY_LOW_PROLONGED`) hiếm khi thỏa vì nhiễu tĩnh MediaPipe; hiệu chỉnh `activity.low_threshold` trên tập dev.
- **H4 – vị trí thấp theo camera:** C4 là vị trí tuyệt đối trong khung; với camera cao nhìn chéo (CAUCAFall) hông sau ngã ở ~0,55–0,6 chiều cao khung. Đặt `final_low_position_ratio` theo từng camera (override `thresholds`).

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
