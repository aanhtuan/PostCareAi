# F23 – Mức vận động và chuyển động bất thường

| Thuộc tính | Giá trị |
|---|---|
| Mã | F23 |
| Trạng thái | Todo |
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

- [ ] **AC1.** Chỉ số vận động tính trên cửa sổ trượt, chuẩn hóa theo `torso_length`, cho ra `LOW` / `NORMAL` / `HIGH`. Mất quan sát cho ra "chưa xác định", không phải `LOW` *(HS §5.1; PDF §7 (tr.8))*. — *Kiểm chứng:* `server/tests/engine/test_activity.py` (`test_still_body_is_low`, `test_moderate_motion_is_normal`, `test_vigorous_motion_is_high`, `test_index_invariant_to_body_scale`, `test_no_observation_gives_unknown_not_low`).
- [ ] **AC2.** `ACTIVITY_INCREASED` và `ACTIVITY_LOW_PROLONGED` sinh ở mức LOG *(HS §5.1; A11)*. — *Kiểm chứng:* `test_rules_movement.py` (`test_activity_increased_after_hold`, `test_activity_low_prolonged_after_threshold`, `test_activity_events_are_log`).
- [ ] **AC3.** `ABNORMAL_MOVEMENT` (HIGH) sinh khi hạ thấp nhanh, dịch chuyển mạnh hoặc đổi hướng thân đột ngột, với ≥ `abnormal_movement.min_conditions` điều kiện thỏa trong cửa sổ ngắn; `explanation` ghi điều kiện nào thỏa *(HS §5.2, §5.4; PDF §7.3 (tr.9); ADR-0009)*. — *Kiểm chứng:* `test_rules_movement.py` (`test_fast_drop_emits_abnormal_movement_high`, `test_below_min_conditions_no_event`, `test_explanation_lists_conditions`).
- [ ] **AC4.** Trở mình bình thường không sinh `ABNORMAL_MOVEMENT` *(HS §5.2)*. — *Kiểm chứng:* `test_turn_over_no_abnormal_movement`.
- [ ] **AC5.** Có kết quả đánh giá trên tập dev (F16) cho `ABNORMAL_MOVEMENT`, `ACTIVITY_INCREASED`, `ACTIVITY_LOW_PROLONGED` *(HS §8.2; ADR-0008)*. — *Kiểm chứng:* lệnh `postcare eval --split dev` → `reports/eval-dev-<date>.md` có các dòng này; ghi đường dẫn báo cáo ở mục 10.

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

## 8. Câu hỏi mở

- **Không chặn:** C4 (`final_low_position_ratio`) chỉ có nghĩa khi camera nhìn thấy sàn cạnh giường. Nếu vị trí camera chốt ở tuần 1–2 không thấy sàn, C4 có thể luôn sai, và khi đó cần hạ `abnormal_movement.min_conditions` qua override camera. Kiểm bằng S15 trên tập dev.
- **Không chặn (phụ thuộc ngoài code):** AC5 cần video dev của S02, S15, S16 và ground truth.

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
