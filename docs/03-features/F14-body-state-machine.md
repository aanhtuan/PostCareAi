# F14 – State machine tư thế và vị trí

| Thuộc tính | Giá trị |
|---|---|
| Mã | F14 |
| Trạng thái | In progress |
| Ưu tiên | MVP |
| Milestone | M1 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F13 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §5 (tr.6), §7 (tr.8), §7.1 (tr.8–9), §7.2 (tr.9); HS §5.1, §5.2, §5.4 |

## 1. Mục tiêu

Feature này biến đặc trưng đã làm mượt (F13) thành **trạng thái cơ thể ổn định**, gồm một trong 7 trạng thái: Nằm, Đang nâng thân, Ngồi, Ở mép giường, Đứng, Ngoài giường, Không đủ dữ liệu quan sát (PDF §7 (tr.8); HS §5.1). Nguyên tắc là "không tin một frame đơn lẻ" (PDF §7 (tr.8)): trạng thái chỉ đổi khi điều kiện giữ đủ lâu, có hysteresis để không dao động quanh ngưỡng (HS §5.4). Đây là bước 4–5 của pipeline ([event-engine.md](../02-architecture/event-engine.md) mục 3). F15 dựa vào chuỗi trạng thái này để sinh sự kiện.

## 2. Phạm vi

**Trong phạm vi**
- Phân loại tư thế thô (`LYING` / `RAISING` / `SITTING` / `STANDING` / `UNKNOWN`) và vị trí thô (`IN_BED` / `EDGE` / `OUT`) trong `engine/posture.py`.
- State machine 7 trạng thái có min duration và hysteresis trong `engine/state_machine.py`.
- `explanation` cho mỗi lần chuyển trạng thái.
- Lịch sử ngắn các trạng thái ổn định, để F15 kiểm tra chuỗi hợp lệ.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Đặc trưng, người mục tiêu, cổng chất lượng (đã có ở F13).
- Sinh sự kiện SIT_UP, BED_EXIT… và debounce (→ F15).
- Mức vận động, chuyển động bất thường (→ F23).
- Gửi trạng thái lên API, hiển thị trên dashboard (→ F17, F21).

## 3. Yêu cầu chi tiết

- **R1.** Engine thuần Python, xác định, không đọc đồng hồ hệ thống; thời gian giữ trạng thái tính bằng `ts_ms` *(event-engine.md mục 1)*.
- **R2.** Đủ 7 trạng thái `LYING`, `RAISING`, `SITTING`, `AT_EDGE`, `STANDING`, `OUT_OF_BED`, `NO_OBSERVATION` (enum `BodyState` trong `postcare.schemas`) *(PDF §7 (tr.8); HS §5.1; event-engine.md mục 4)*. Engine mới khởi động ở `NO_OBSERVATION` cho tới khi xác lập được trạng thái đầu tiên *(F10: observation rỗng → `NO_OBSERVATION`)*.
- **R3.** Phân loại tư thế thô theo `trunk_angle_deg`, có hysteresis phụ thuộc trạng thái hiện tại *(PDF §7 (tr.8); event-engine.md mục 4, mục 6)*:
  - Đang `LYING`: chỉ rời `LYING` khi góc > `posture.lying_exit_deg`. Chưa `LYING`: chỉ thành ứng viên `LYING` khi góc < `posture.lying_enter_deg`.
  - Đang `SITTING`: chỉ rời `SITTING` khi góc < `posture.sitting_exit_deg`. Chưa `SITTING`: chỉ thành ứng viên `SITTING` khi góc > `posture.sitting_enter_deg`. Điều kiện phụ: vai cao hơn hông, hông trong ROI *(event-engine.md mục 4)*.
  - `RAISING`: góc nằm giữa vùng nằm và vùng ngồi, đi lên từ `LYING` *(PDF §7.1 (tr.8–9))*.
  - `STANDING`: thân thẳng, hông cao, chân duỗi, dùng `posture.standing_hip_above_knee_ratio` *(HS §5.1; event-engine.md mục 4)*.
  - Khi góc 2D không đủ phân biệt (camera nhìn dọc trục giường), dùng thêm tỷ lệ `torso_length` hiện tại so với `torso_length` tham chiếu lúc nằm, ngưỡng `posture.torso_length_ratio_sitting`. State machine lưu `torso_length` tham chiếu khi đang `LYING` *(event-engine.md mục 6, ghi chú góc nhìn)*.
- **R4.** Phân loại vị trí thô *(PDF §7.2 (tr.9); HS §5.2; event-engine.md mục 4, mục 6)*:
  - `OUT`: `hip_center` ở ngoài ROI xa hơn `location.out_of_roi_margin_torso` × `torso_length` (tức `dist_to_roi_edge < −out_of_roi_margin_torso`).
  - `EDGE`: chưa tới mức `OUT`, và `dist_to_roi_edge < location.edge_distance_torso` hoặc có cổ chân ra ngoài ROI (`ankles_outside_roi ≥ 1`).
  - `IN_BED`: các trường hợp còn lại.
  - Biên `out_of_roi_margin_torso` đóng vai trò hysteresis cho vị trí: ra ngoài phải vượt biên một đoạn, nhưng quay lại chỉ cần `hip_center` vào trong ROI *(giả định: tránh nhảy qua lại ở đúng biên)*.
- **R5.** Ánh xạ sang trạng thái ứng viên, xét theo thứ tự *(giả định: event-engine.md mục 4 cho AT_EDGE gồm cả "ngồi/đứng" nên trùng với STANDING; thứ tự này khớp ví dụ ở testing.md mục 2, nơi đứng ở mép giường sinh STAND_UP)*:
  1. Cổng chất lượng của F13 báo kém kéo dài → `NO_OBSERVATION`.
  2. Vị trí `OUT` → `OUT_OF_BED`.
  3. Tư thế `STANDING` → `STANDING`.
  4. Tư thế `SITTING` (hoặc `RAISING`) + vị trí `EDGE` → `AT_EDGE`.
  5. Tư thế `SITTING` / `RAISING` / `LYING` → trạng thái cùng tên.
  6. Tư thế `UNKNOWN` khi chất lượng vẫn `GOOD` → giữ trạng thái hiện tại *(giả định)*.
- **R6.** Min duration: ứng viên phải giữ **liên tục** ≥ `min_duration_s.<TRẠNG_THÁI_ĐÍCH>` (`RAISING`, `SITTING`, `AT_EDGE`, `STANDING`, `OUT_OF_BED`, `LYING`) mới được xác lập. Ứng viên đổi giữa chừng thì đếm lại từ đầu. Nhiễu 1–3 frame không làm đổi trạng thái *(PDF §5 (tr.6), §7 (tr.8); HS §5.4)*.
- **R7.** Từ `NO_OBSERVATION` sang trạng thái khác: phải qua cổng phục hồi `quality.restore_duration_s` của F13, **rồi** thêm min duration của trạng thái đích *(event-engine.md mục 4; giả định: áp dụng cả hai để chắc chắn)*.
- **R8.** Mất landmark hoặc bị che **không bao giờ** dẫn tới `OUT_OF_BED`. Trường hợp này luôn dẫn tới `NO_OBSERVATION`. `OUT_OF_BED` chỉ được xác lập khi người mục tiêu được quan sát tốt ở ngoài ROI trong suốt min duration *(HS §5.2; event-engine.md mục 4)*.
- **R9.** Đi thẳng từ `LYING` (không qua `AT_EDGE`) sang `OUT_OF_BED` vẫn được phép ở mức trạng thái, nhưng ghi `explanation.anomaly = "skipped_edge"` để F15 không sinh BED_EXIT *(event-engine.md mục 4)*.
- **R10.** Mỗi lần chuyển trạng thái có `explanation` gồm: `rule_id`, `from_state`, `to_state`, `held_ms`, và giá trị đặc trưng chính lúc xác lập (`trunk_angle_deg`, `dist_to_roi_edge`, `ankles_outside_roi`, `observation_quality`…) *(PDF §7 (tr.8): rule dễ giải thích; HS §6.2: căn cứ ngắn gọn; event-engine.md mục 1)*.
- **R11.** `EngineOutput.state.body_state` là trạng thái ổn định; `state_changed = true` đúng ở frame xác lập trạng thái mới. State machine giữ lịch sử các trạng thái ổn định gần nhất (trạng thái, thời điểm bắt đầu, `explanation`) cho F15 *(giả định: F15 cần chuỗi trạng thái để kiểm tra PDF §7.1–7.2)*.
- **R12.** Mọi ngưỡng lấy từ `EngineConfig`, override được theo camera *(QA#22)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/engine/posture.py`: phân loại tư thế và vị trí thô.
  - `server/src/postcare/engine/state_machine.py`: `BodyStateMachine` (ứng viên, bộ đếm thời gian, hysteresis, lịch sử).
  - `server/src/postcare/engine/engine.py`: nối bước 4–5 sau F13.
  - Test: `server/tests/engine/test_posture.py`, `test_state_machine.py` (dùng `builders.py` của F13).
- **Dữ liệu:** không có bảng mới. Trạng thái hiện tại không lưu DB ([data-model.md](../02-architecture/data-model.md), mục "Dữ liệu không lưu trong DB").
- **API:** không có.
- **UI:** nhãn 7 trạng thái theo [glossary.md](../01-product/glossary.md) (thêm vào `vi.ts` ở F21).
- **Cấu hình:** `posture.lying_enter_deg`, `posture.lying_exit_deg`, `posture.sitting_enter_deg`, `posture.sitting_exit_deg`, `posture.torso_length_ratio_sitting`, `posture.standing_hip_above_knee_ratio`, `location.edge_distance_torso`, `location.out_of_roi_margin_torso`, `min_duration_s.RAISING`, `min_duration_s.SITTING`, `min_duration_s.AT_EDGE`, `min_duration_s.STANDING`, `min_duration_s.OUT_OF_BED`, `min_duration_s.LYING`, `quality.restore_duration_s`. Không cần khóa mới.

## 5. Acceptance criteria

- [ ] **AC1.** Đạt được đủ 7 trạng thái `LYING`, `RAISING`, `SITTING`, `AT_EDGE`, `STANDING`, `OUT_OF_BED`, `NO_OBSERVATION` bằng chuỗi tổng hợp nằm → ngồi → mép → đứng → ra ngoài → mất quan sát *(PDF §7 (tr.8); HS §5.1)*. — *Kiểm chứng:* `server/tests/engine/test_state_machine.py::test_full_sequence_reaches_all_seven_states`.
- [ ] **AC2.** Chỉ chuyển trạng thái khi ứng viên giữ đủ `min_duration_s.<STATE>`. Nhiễu 1–3 frame không làm đổi trạng thái *(PDF §5 (tr.6), §7 (tr.8); HS §5.4)*. — *Kiểm chứng:* `test_transition_only_after_min_duration`, `test_noise_1_to_3_frames_no_transition`.
- [ ] **AC3.** Hysteresis: góc thân dao động quanh `posture.lying_exit_deg` / `posture.sitting_enter_deg` không làm trạng thái nhảy qua lại *(PDF §7 (tr.8))*. — *Kiểm chứng:* `test_trunk_angle_oscillating_near_threshold_no_flapping` (góc dao động ± vài độ quanh ngưỡng trong nhiều giây, đếm số lần `state_changed` ≤ 1).
- [ ] **AC4.** Mỗi lần chuyển trạng thái có `explanation` gồm `rule_id`, `from_state`, `to_state`, `held_ms` và giá trị đặc trưng chính *(HS §6.2; event-engine.md mục 1)*. — *Kiểm chứng:* `test_every_transition_has_explanation`.
- [ ] **AC5.** Mất landmark hoặc bị che khi đang ở mép giường dẫn tới `NO_OBSERVATION`, **không** dẫn tới `OUT_OF_BED`. Đi thẳng từ `LYING` ra ngoài được đánh dấu `anomaly = "skipped_edge"` *(HS §5.2; event-engine.md mục 4)*. — *Kiểm chứng:* `test_landmark_loss_at_edge_goes_no_observation_not_out_of_bed`, `test_lying_to_out_of_bed_marks_skipped_edge`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit (builder) | `.lying().raise_to_sitting().sitting().move_to_edge().standing().walk_out().drop_landmarks()`; so sánh danh sách trạng thái đã xác lập | — |
| AC2 | unit (builder) | Ứng viên giữ ngắn hơn / dài hơn min duration 1 frame | `.noise(frames=1..3)` kiểu "ngồi" khi đang nằm |
| AC3 | unit | Chuỗi góc hình sin quanh ngưỡng | Không đổi trạng thái liên tục |
| AC4 | unit | Duyệt mọi `state_changed=true`, kiểm tra khóa trong `explanation` | — |
| AC5 | unit (builder) | `.move_to_edge().drop_landmarks(seconds=…)`; `.lying().walk_out()` | Bị che ở mép giường không thành `OUT_OF_BED` |
| R4 | unit | Hip ở đúng biên ROI, dao động trong `out_of_roi_margin_torso` | Không nhảy `EDGE`↔`OUT` |
| R5 | unit | Đứng ở mép giường → `STANDING`; ngồi ở mép → `AT_EDGE` | — |

**Ca âm tính bắt buộc** ([testing.md](../04-guides/testing.md) mục 2) thuộc F14:

| Tình huống | Kỳ vọng ở F14 | Test |
|---|---|---|
| Ngồi dậy rồi nằm lại | Chuỗi `LYING → RAISING → SITTING → … → LYING`; không có `AT_EDGE`, `OUT_OF_BED` | `test_sit_up_then_lie_back_never_edge_or_out` |
| Nhiễu "ngồi" 1–3 frame | Không đổi trạng thái | `test_noise_1_to_3_frames_no_transition` |
| Góc thân dao động quanh ngưỡng | Không đổi trạng thái liên tục (hysteresis) | `test_trunk_angle_oscillating_near_threshold_no_flapping` |
| Mất landmark / bị che khi đang ở mép giường | `NO_OBSERVATION`, không `OUT_OF_BED` | `test_landmark_loss_at_edge_goes_no_observation_not_out_of_bed` |
| Điều dưỡng đứng cạnh giường (ngoài ROI) | Trạng thái của bệnh nhân không đổi | `test_nurse_outside_roi_does_not_change_state` |
| Hai người trong ROI | `NO_OBSERVATION` (`MULTIPLE_PEOPLE`) | `test_two_people_in_roi_state_no_observation` |

Các ca trở mình, debounce, khuôn mặt được kiểm ở F15, F23, F26, F27.

## 7. Giả định

- *(giả định)* Thứ tự ánh xạ ở R5: tư thế `STANDING` được ưu tiên hơn `AT_EDGE`, nên đứng ở mép giường là `STANDING`.
- *(giả định)* Hysteresis vị trí: ra ngoài phải vượt `out_of_roi_margin_torso`; quay vào chỉ cần hông trong ROI (R4).
- *(giả định)* Tư thế `UNKNOWN` khi chất lượng tốt thì giữ trạng thái hiện tại (R5).
- *(giả định)* Từ `NO_OBSERVATION` phải qua cả cổng phục hồi lẫn min duration của trạng thái đích (R7).
- *(giả định)* State machine lưu lịch sử trạng thái ổn định cho F15 (R11).
- *(giả định)* Rời `LYING` luôn qua `RAISING`; góc vùng giữa chỉ là `RAISING` khi đi lên từ nằm (hoặc từ `NO_OBSERVATION`).
- *(giả định)* Hysteresis góc "thân thẳng" áp dụng cho mọi trạng thái thân thẳng (`SITTING`, `AT_EDGE`, `STANDING`, `OUT_OF_BED`), không chỉ `SITTING`.
- *(giả định)* Đứng cần thêm vector hông → cổ chân thẳng theo cùng ngưỡng góc của thân.
- *(giả định)* Tỷ lệ `torso_length` chỉ dùng khi góc báo vùng nằm.
- *(giả định)* Frame kém (cổng chưa đóng) xen giữa làm ứng viên đếm lại từ đầu.
- *(giả định)* `skipped_edge` đánh dấu mọi lần ra ngoài từ `LYING`/`RAISING`/`SITTING` không qua `AT_EDGE` (bỏ qua `NO_OBSERVATION`, `STANDING`).

## 8. Câu hỏi mở

- **Không chặn:** event-engine.md chưa định nghĩa công thức chính xác cho `posture.standing_hip_above_knee_ratio` và chiều so sánh của `posture.torso_length_ratio_sitting` (thân ngắn lại hay dài ra khi ngồi). Planner chốt công thức, ghi vào event-engine.md cùng PR, sau đó hiệu chỉnh trên tập dev (F16).

## 9. Kế hoạch triển khai

**Khảo sát:** `engine/pipeline.py` có `StateMachine` rỗng (F10) và `FrameAssessment`; `engine/engine.py` chỉ gọi `StateMachine.update` khi cổng chất lượng mở và frame `GOOD` (F13); `BodyFeatures` (`engine/features.py`) đã có `trunk_angle_deg`, `torso_length`, `dist_to_roi_edge`, `ankles_outside_roi`, `knees`, `ankles`, `hip_center`, `shoulder_center`. Builder `tests/engine/builders.py` (F13).

**Thiết kế chốt:**
- `engine/posture.py`: enum `Posture` (`LYING/RAISING/SITTING/STANDING/UNKNOWN`), `Location` (`IN_BED/EDGE/OUT`); hàm thuần `classify_posture(features, current, ref_torso, config)`, `classify_location(features, current, config)`, `candidate_state(posture, location)`.
  - Thân "thẳng" theo góc: đang ở trạng thái thân thẳng (`SITTING/AT_EDGE/STANDING/OUT_OF_BED`) cần góc ≥ `sitting_exit_deg`, ngược lại cần góc > `sitting_enter_deg` *(giả định: mở rộng hysteresis của SITTING cho mọi trạng thái thân thẳng)*.
  - Vùng nằm: đang `LYING` cần góc ≤ `lying_exit_deg`, ngược lại < `lying_enter_deg`.
  - Tỷ lệ `torso_length` chỉ dùng khi góc nằm trong vùng nằm (góc 2D không phân biệt được): `|torso/ref − 1| ≥ 1 − torso_length_ratio_sitting` → coi là thân thẳng. `ref` cập nhật khi trạng thái ổn định `LYING` và tư thế nằm; xóa khi vào `NO_OBSERVATION` *(giả định)*.
  - Thân thẳng nhưng vai không cao hơn hông → `UNKNOWN`.
  - Vùng giữa: `RAISING` nếu trạng thái hiện tại là `LYING`, `RAISING` hoặc `NO_OBSERVATION` ("đi lên từ nằm"); ngược lại `UNKNOWN` (giữ trạng thái) *(giả định)*. Vì vậy nằm lại từ `SITTING` đi thẳng `SITTING → LYING`.
  - Đang `LYING` thì mọi góc ngoài vùng nằm (kể cả đã thẳng) là `RAISING`: rời nằm luôn qua `RAISING` (`LYING → RAISING → SITTING`, PDF §7.1) *(giả định; bổ sung khi cài đặt: với góc tăng đều, vùng 35°–55° quá ngắn so với `min_duration_s.RAISING`)*.
  - `STANDING`: thân thẳng + có gối và cổ chân nhìn thấy, gối thấp hơn hông, cổ chân thấp hơn gối, `(knee_y − hip_y) ≥ standing_hip_above_knee_ratio × (ankle_y − knee_y)` **và** vector hông → cổ chân cũng thẳng theo cùng ngưỡng góc của thân (chân duỗi, không nằm ngang) *(giả định: chặn ca suy biến khi chân nằm ngang trên giường, knee_y ≈ hip_y ≈ ankle_y)*. Thêm trường `BodyFeatures.leg_angle_deg`.
- `engine/state_machine.py`: `BodyStateMachine` với `update(assessment, ts_ms)` (frame GOOD), `interrupt(ts_ms)` (frame kém khi cổng còn mở: xóa ứng viên, giữ trạng thái), `lose_observation(quality, ts_ms)` (cổng đóng → `NO_OBSERVATION`). Ứng viên + mốc bắt đầu; xác lập khi `ts − start ≥ min_duration_s.<đích>`. `explanation` (dict JSON) và `history` (tối đa 32 bản ghi `StateRecord(state, since_ms, explanation)`, hằng số không phải ngưỡng).
  - `skipped_edge`: khi vào `OUT_OF_BED`, duyệt lùi lịch sử bỏ qua `NO_OBSERVATION`, `STANDING`; nếu gặp `LYING/RAISING/SITTING` trước `AT_EDGE` → `anomaly = "skipped_edge"` *(giả định: mở rộng R9 cho mọi đường ra từ trong giường không qua mép)*.
- `BodyStateSnapshot` thêm `explanation: dict[str, JsonValue] | None = None` (explanation của lần chuyển gần nhất; `None` ở trạng thái khởi tạo) — event-engine.md mục 4 yêu cầu ghi `anomaly` "vào state". `Engine.state_history` trả lịch sử cho F15.
- `pipeline.StateMachine` = `BodyStateMachine` (giữ tên để Engine/F13 test không đổi).

**Các bước:**
1. Commit plan (spec).
2. Test trước: `tests/engine/test_posture.py` (phân loại, hysteresis góc, tỷ lệ torso, đứng vs mép, vị trí EDGE/OUT + hysteresis), `tests/engine/test_state_machine.py` (AC1–AC5, ca âm tính mục 6 qua `PoseSequence` + `run_engine`; ca min-duration chính xác từng frame bằng `BodyFeatures` tổng hợp). Builder: `raise_to_sitting` nội suy vector vai theo góc (giữ chiều dài thân, giống camera nhìn ngang), `AT_EDGE` đùi gần nằm ngang (ngồi thật). Xác nhận test fail vì chưa có module.
3. Cài `posture.py`, `state_machine.py`, nối `engine.py`; cập nhật `FakeStateMachine` (F13) thêm `interrupt`/`lose_observation`; sửa `test_persons_without_f14_stay_no_observation`.
4. Doc: event-engine.md mục 2 (snapshot có `explanation`), mục 4/6 (công thức đứng, tỷ lệ torso, RAISING chỉ khi đi lên). Không thêm khóa config.
5. `make check`, `scripts\dev.ps1 check`; ghi bằng chứng mục 10.

**Rủi ro:** ngưỡng góc/tỷ lệ phụ thuộc vị trí camera, hiệu chỉnh ở F16; F11/F17 nhận thêm trường `explanation` trong snapshot (tùy chọn, mặc định `None`).

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
