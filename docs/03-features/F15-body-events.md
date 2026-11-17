# F15 – Sự kiện cơ thể và vị trí

| Thuộc tính | Giá trị |
|---|---|
| Mã | F15 |
| Trạng thái | In progress |
| Ưu tiên | MVP |
| Milestone | M1 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F14 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §7 (tr.8), §7.1 (tr.8–9), §7.2 (tr.9); HS §5.1, §5.2, §5.4; A01, A11 |

## 1. Mục tiêu

Feature này sinh **sự kiện** từ chuỗi trạng thái ổn định của F14: ngồi dậy, đứng dậy, thay đổi tư thế, ở mép giường, rời giường, quay lại giường (HS §5.1, §5.2). Mỗi sự kiện có mức ưu tiên, confidence, chất lượng quan sát và căn cứ (HS §5.4, §6.2). Debounce chặn lặp lại (HS §5.4; PDF §7 (tr.8)). Đây là bước 6 và phần debounce của bước 9 trong pipeline ([event-engine.md](../02-architecture/event-engine.md) mục 3). Hai điểm bắt buộc: ngồi dậy rồi nằm lại **không** sinh cảnh báo rời giường (PDF §7.2 (tr.9)); mất landmark hoặc bị che **không** được coi là rời giường (HS §5.2).

## 2. Phạm vi

**Trong phạm vi**
- Rule sự kiện cơ thể `engine/rules/body.py`: `SIT_UP`, `STAND_UP`, `POSTURE_CHANGE`, `BED_EDGE`, `BED_EXIT`, `RETURN_TO_BED`.
- Module debounce dùng chung `engine/debounce.py` (F23, F26 dùng lại).
- Điền đủ trường của `EngineEvent`.
- Thêm thao tác `turn_over(...)` vào builder (F13).

**Ngoài phạm vi** (để feature khác hoặc không làm)
- `OBSERVATION_LOST` / `OBSERVATION_RESTORED`, `CAMERA_OFFLINE` / `CAMERA_ONLINE` (→ F17).
- `ACTIVITY_*`, `ABNORMAL_MOVEMENT` (→ F23). `FACE_ATTENTION` (→ F26).
- Lưu sự kiện, tạo cảnh báo, gắn phiên (→ F17).
- Text tiếng Việt của sự kiện (→ `vi.ts`, F20–F22).

## 3. Yêu cầu chi tiết

- **R1.** Rule chỉ đọc chuỗi trạng thái ổn định, `explanation` và đặc trưng do F13–F14 cung cấp. Engine thuần, xác định *(event-engine.md mục 1)*.
- **R2.** `SIT_UP` (INFO): `SITTING` được xác lập, và các trạng thái ổn định ngay trước đó là `RAISING` rồi `LYING` *(PDF §7.1 (tr.8–9); HS §5.2, §5.4)*.
- **R3.** `STAND_UP` (INFO, A11): `STANDING` được xác lập, trạng thái ổn định trước đó là `SITTING` hoặc `AT_EDGE` *(HS §5.1; event-engine.md mục 5)*.
- **R4.** `BED_EDGE` (MEDIUM): `AT_EDGE` được xác lập (đã giữ `min_duration_s.AT_EDGE`) *(PDF §7.2 (tr.9); HS §5.2, §5.4)*. Chỉ sinh khi đi ra mép từ trạng thái trong giường (`LYING`, `RAISING`, `SITTING`). Không sinh khi `AT_EDGE` đến từ `STANDING` hoặc `OUT_OF_BED` (đang quay về giường) *(giả định: cảnh báo mép giường nhằm báo người bệnh sắp rời giường, HS §2.1; tránh cảnh báo sai khi người bệnh trở lại giường)*.
- **R5.** `BED_EXIT` (HIGH): `OUT_OF_BED` được xác lập (đã giữ `min_duration_s.OUT_OF_BED`) **qua chuỗi hợp lệ** `… → AT_EDGE → (STANDING) → OUT_OF_BED` *(PDF §7.2 (tr.9); HS §5.2; event-engine.md mục 4)*:
  - Chuỗi được xét trên các trạng thái ổn định, **bỏ qua** đoạn `NO_OBSERVATION` xen giữa *(giả định: nếu bị che ở mép giường rồi sau đó được quan sát rõ ở ngoài ROI đủ lâu thì vẫn là "được quan sát ra ngoài vùng giường", HS §5.2)*.
  - Điều kiện trước (event-engine.md mục 4, chốt sau review F14): trạng thái ổn định gần nhất trước `OUT_OF_BED` (bỏ qua `NO_OBSERVATION`) là `AT_EDGE` **hoặc** `STANDING`. Đứng ở mép giường luôn là `STANDING`, nên `SITTING → STANDING → OUT_OF_BED` là lần rời giường thật.
  - Đi thẳng từ `LYING`/`RAISING`/`SITTING` (state có `anomaly = "skipped_edge"`) hoặc chưa có trạng thái quan sát nào trước đó thì không sinh `BED_EXIT`.
- **R6.** `RETURN_TO_BED` (INFO, A11): sau `OUT_OF_BED`, người mục tiêu về lại trong ROI ở trạng thái `SITTING` hoặc `LYING` và giữ ≥ `min_duration_s.RETURN_TO_BED` *(HS §5.2: "trạng thái được xác lập đủ chắc chắn"; event-engine.md mục 5)*. Có thể đi qua `STANDING`, `AT_EDGE` hoặc `NO_OBSERVATION` ở giữa *(giả định)*.
- **R7.** `POSTURE_CHANGE` (LOG): đang `LYING`, `shoulder_line_angle_deg` đổi so với hướng tham chiếu > `posture_change.shoulder_angle_delta_deg`, và hướng mới giữ ổn định ≥ `posture_change.stable_s` *(HS §5.2, §5.4; event-engine.md mục 5)*. Hướng tham chiếu được đặt lại sau mỗi lần sinh sự kiện và mỗi khi vào `LYING` *(giả định)*.
- **R8.** Debounce *(A01; HS §5.4; event-engine.md mục 7)*:
  - Cùng `code` không phát lại trong `debounce.same_code_same_session_s` kể từ lần phát gần nhất.
  - Sự kiện chỉ phát khi **vào** trạng thái hoặc điều kiện, không phát lặp khi vẫn ở yên trong trạng thái đó.
  - Phạm vi "cùng phiên" = vòng đời của một instance `Engine`. Engine không biết phiên *(event-engine.md mục 1)*; worker tạo `Engine` mới khi phiên theo dõi đổi (F17) *(giả định)*.
  - Debounce là module riêng, F23 và F26 dùng lại.
- **R9.** Trường của mỗi `EngineEvent` *(HS §5.4, §6.2; PDF §10.1 (tr.12); data-model.md bảng `events`)*:
  - `code`, `priority` lấy từ catalog `postcare/schemas/events.py` (không viết lại ở rule).
  - `occurred_at_ms`: `ts_ms` lúc điều kiện bắt đầu được thỏa (đầu khoảng min duration). `detected_at_ms`: `ts_ms` lúc engine xác lập và phát sự kiện. Luôn có `occurred_at_ms ≤ detected_at_ms`.
  - `confidence` ∈ [0,1] *(giả định: trung bình visibility của `pose.required_keypoints` trong khoảng giữ trạng thái)*.
  - `observation_quality` tại thời điểm phát.
  - `explanation`: `rule_id`, `from_state`, `to_state`, `held_ms`, giá trị đặc trưng chính, chuỗi trạng thái đã dùng (với `BED_EXIT`).
  - `config_hash` (F10 tính).
- **R10.** Không sinh sự kiện cơ thể nào khi đang `NO_OBSERVATION`. Mất landmark hoặc bị che không sinh `BED_EXIT` *(HS §5.2)*.
- **R11.** Ngưỡng lấy từ `EngineConfig` *(QA#22)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/engine/rules/body.py`: các rule ở R2–R7.
  - `server/src/postcare/engine/debounce.py`: `Debouncer` theo `code`, dùng `ts_ms`.
  - `server/src/postcare/engine/engine.py`: nối bước 6 và debounce.
  - `server/src/postcare/schemas/events.py` (F10): chỉ đọc catalog.
  - Test: `server/tests/engine/test_rules_body.py`, `test_debounce.py`; thêm `turn_over` vào `server/tests/engine/builders.py`.
- **Dữ liệu:** không có bảng mới. Trường sự kiện khớp bảng `events` ([data-model.md](../02-architecture/data-model.md)) để F17 lưu được.
- **API:** không có.
- **UI:** không có (text sự kiện nằm trong `vi.ts`, F20–F22).
- **Cấu hình:** `min_duration_s.SITTING`, `min_duration_s.STANDING`, `min_duration_s.AT_EDGE`, `min_duration_s.OUT_OF_BED`, `min_duration_s.RETURN_TO_BED`, `posture_change.shoulder_angle_delta_deg`, `posture_change.stable_s`, `debounce.same_code_same_session_s`, `pose.required_keypoints`. Không cần khóa mới.

## 5. Acceptance criteria

- [ ] **AC1.** `SIT_UP` sinh theo chuỗi `LYING → RAISING → SITTING`. Ngồi dậy rồi nằm lại **không** sinh `BED_EXIT` hay `BED_EDGE` *(PDF §7.1 (tr.8–9), §7.2 (tr.9))*. — *Kiểm chứng:* `server/tests/engine/test_rules_body.py` (`test_sit_up_sequence_emits_sit_up`, `test_sit_up_then_lie_back_no_bed_exit`).
- [ ] **AC2.** `STAND_UP`, `BED_EDGE`, `BED_EXIT`, `RETURN_TO_BED` sinh theo chuỗi trạng thái. Chuỗi nằm → ngồi → mép → đứng → ra ngoài cho đúng `["SIT_UP", "BED_EDGE", "STAND_UP", "BED_EXIT"]` ([testing.md](../04-guides/testing.md) mục 2). Mất landmark hoặc bị che **không** sinh `BED_EXIT` *(HS §5.1, §5.2; PDF §7.2 (tr.9))*. — *Kiểm chứng:* `test_full_exit_sequence_codes`, `test_return_to_bed_after_exit`, `test_landmark_loss_at_edge_no_bed_exit`, `test_lying_straight_out_no_bed_exit`.
- [ ] **AC3.** Trở mình khi nằm sinh `POSTURE_CHANGE` mức LOG, không sinh `SIT_UP` hay `BED_EDGE` *(HS §5.2, §5.4)*. — *Kiểm chứng:* `test_turn_over_emits_posture_change_log`.
- [ ] **AC4.** Debounce: cùng code không lặp trong `debounce.same_code_same_session_s` *(A01)*. — *Kiểm chứng:* `test_debounce.py::test_same_code_within_window_emitted_once`, `test_same_code_after_window_and_reentry_emitted_again`.
- [ ] **AC5.** Mỗi sự kiện có `priority` đúng catalog, `confidence` ∈ [0,1], `observation_quality`, `explanation.rule_id`, `config_hash`, và `occurred_at_ms ≤ detected_at_ms` *(HS §5.4, §6.2; PDF §10.1 (tr.12))*. — *Kiểm chứng:* `test_every_body_event_has_required_fields` (duyệt mọi sự kiện của các chuỗi trong file test).

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit (builder) | `.lying().raise_to_sitting().sitting()`; `.lying().raise_to_sitting().sitting().lying()` | Ngồi dậy rồi nằm lại: không `BED_EXIT`, `BED_EDGE` |
| AC2 | unit (builder) | Chuỗi đầy đủ của testing.md; ra ngoài rồi quay về nằm | Bị che ở mép giường; đi thẳng từ nằm ra ngoài; bị che ở mép rồi không quan sát lại được |
| AC3 | unit (builder) | `.lying().turn_over().lying()` | Không `SIT_UP`, `BED_EDGE` |
| AC4 | unit | Vào/ra `AT_EDGE` hai lần trong cửa sổ debounce; lần ba sau cửa sổ | Chỉ một `BED_EDGE` trong cửa sổ |
| AC5 | unit | Kiểm tra trường của mọi sự kiện | — |
| R4 | unit (builder) | Ra ngoài → đứng → ngồi ở mép → nằm | Quay lại qua mép giường không sinh `BED_EDGE` |
| R5 | unit (builder) | Mép → bị che → quan sát rõ ở ngoài ROI đủ lâu | Sinh `BED_EXIT` (dương tính); nếu không quan sát lại thì không |

Nếu F12 đã có fixture `server/tests/fixtures/*.jsonl` thì thêm test regression so với `.expected.json` (testing.md mục 2).

**Ca âm tính bắt buộc** ([testing.md](../04-guides/testing.md) mục 2) thuộc F15:

| Tình huống | Kỳ vọng ở F15 | Test |
|---|---|---|
| Ngồi dậy rồi nằm lại | Không `BED_EXIT`, `BED_EDGE` | `test_sit_up_then_lie_back_no_bed_exit` |
| Nhiễu "ngồi" 1–3 frame | Không `SIT_UP` | `test_noise_1_to_3_frames_no_sit_up` |
| Mất landmark / bị che khi đang ở mép giường | Không `BED_EXIT` | `test_landmark_loss_at_edge_no_bed_exit` |
| Điều dưỡng đứng cạnh giường (ngoài ROI) | Không có sự kiện nào từ người đó | `test_nurse_outside_roi_no_events` |
| Hai người trong ROI | Không sinh sự kiện cơ thể (đang `NO_OBSERVATION`) | `test_two_people_in_roi_no_body_events` |
| Trở mình | `POSTURE_CHANGE` (LOG), không sự kiện khác | `test_turn_over_emits_posture_change_log` |
| Lặp sự kiện trong cửa sổ debounce | Chỉ 1 sự kiện | `test_same_code_within_window_emitted_once` |

Trở mình **không** sinh `ABNORMAL_MOVEMENT` được kiểm ở F23. Các ca khuôn mặt được kiểm ở F26, F27.

## 7. Giả định

- *(giả định)* `BED_EDGE` chỉ sinh khi ra mép từ trạng thái trong giường (R4).
- *(giả định)* Chuỗi `BED_EXIT` và `RETURN_TO_BED` bỏ qua đoạn `NO_OBSERVATION` xen giữa (R5, R6).
- *(giả định)* Hướng tham chiếu của `POSTURE_CHANGE` đặt lại sau mỗi sự kiện và khi vào `LYING` (R7).
- *(giả định)* "Cùng phiên" của debounce là vòng đời một instance `Engine`; worker tạo Engine mới khi phiên đổi (R8, F17).
- *(giả định)* Công thức `confidence` (R9).
- Mức ưu tiên STAND_UP, RETURN_TO_BED là INFO (A11). Debounce 60 giây (A01).

## 8. Câu hỏi mở

- **Không chặn:** nếu ngồi dậy quá nhanh, `RAISING` có thể không giữ đủ `min_duration_s.RAISING`, và khi đó `SIT_UP` không được sinh vì chuỗi bắt buộc có `RAISING` (PDF §7.1). Cần xem trên tập dev (F16). Nếu recall thấp thì hỏi người dùng có cho phép `LYING → SITTING` trực tiếp hay không.
- **Không chặn:** đứng dậy nhanh ở mép giường có thể làm `AT_EDGE` không được xác lập, và khi đó không có `BED_EXIT` (chuỗi bắt buộc qua `AT_EDGE`). Cũng kiểm trên tập dev.

## 9. Kế hoạch triển khai

**Khảo sát:** `RuleSet.evaluate` (`engine/pipeline.py`) đang trả `[]`. `BodyStateMachine` (F14) ghi `history` (`StateRecord(state, since_ms, explanation)`, `explanation.held_ms` = thời gian giữ ứng viên) và đã đánh dấu `anomaly = "skipped_edge"`. `BodyFeatures.shoulder_line_angle_deg` có sẵn (F13). `EngineEvent` (F10) **chưa có** trường `config_hash`, nhưng R9/AC5 và payload `POST /internal/v1/events` cần nó.

**Thiết kế chốt:**
- `engine/debounce.py`: `Debouncer(window_s)`, `allow(key, ts_ms) -> bool`: cho phát khi chưa phát `key` hoặc `ts_ms − lần_phát_gần_nhất ≥ window`; chỉ lần được phát mới cập nhật mốc. Khóa là `str` để F23/F26 dùng lại.
- `engine/rules/body.py`: `BodyRules(config)` với `evaluate(obs, assessment, history, ts_ms) -> list[BodyEventDraft]` (chưa debounce). Phát hiện lần chuyển mới bằng bản ghi cuối của `history` (so định danh).
  - `SIT_UP`: vào `SITTING`, hai bản ghi ngay trước là `RAISING` rồi `LYING` (liền kề, không bỏ qua `NO_OBSERVATION`).
  - `STAND_UP`: vào `STANDING`, bản ghi ngay trước là `SITTING` hoặc `AT_EDGE`.
  - `BED_EDGE`: vào `AT_EDGE`, trạng thái quan sát gần nhất trước đó (bỏ qua `NO_OBSERVATION`) ∈ {`LYING`, `RAISING`, `SITTING`} (R4).
  - `BED_EXIT`: vào `OUT_OF_BED`, trạng thái quan sát gần nhất trước đó ∈ {`AT_EDGE`, `STANDING`}; `explanation.state_chain` = các trạng thái ổn định đã xét (R5).
  - `RETURN_TO_BED`: sau khi vào `OUT_OF_BED` thì "chờ quay về"; khi trạng thái ổn định ∈ {`SITTING`, `LYING`} thì tính mốc bắt đầu = đầu khoảng min_duration của trạng thái đó; rời khỏi tập này (kể cả `NO_OBSERVATION`) thì xóa mốc, vẫn chờ. Phát khi `ts − mốc ≥ min_duration_s.RETURN_TO_BED`, rồi thôi chờ (R6).
  - `POSTURE_CHANGE`: chỉ khi trạng thái `LYING` và frame có đặc trưng. Hướng tham chiếu = `shoulder_line_angle_deg` ở frame đầu tiên có đặc trưng sau khi vào `LYING`. Lệch (gập về [0°, 180°]) > `shoulder_angle_delta_deg` liên tục ≥ `stable_s` → phát, đặt lại tham chiếu = hướng hiện tại. Frame không có đặc trưng hoặc lệch ≤ ngưỡng → xóa ứng viên. Rời `LYING` → xóa tham chiếu (R7).
  - Trường: `occurred_at_ms = since_ms − held_ms` của bản ghi (state rule) hoặc mốc bắt đầu ứng viên; `detected_at_ms = ts_ms` hiện tại; `confidence` = trung bình visibility của `pose.required_keypoints` của người mục tiêu trên các frame trong [occurred, detected] (bộ đệm theo thời gian, không frame nào → 0.0); `observation_quality` = chất lượng frame hiện tại; `explanation` = `rule_id` (`body.<code_thường>`), `from_state`, `to_state`, `held_ms`, đặc trưng chính lấy từ explanation của state (`trunk_angle_deg`, `dist_to_roi_edge`, `ankles_outside_roi`), thêm `state_chain` cho BED_EXIT, `shoulder_angle_delta_deg`/`reference_angle_deg` cho POSTURE_CHANGE. `priority` = `default_priority(code)` từ catalog.
- `RuleSet` (pipeline): giữ `BodyRules` + một `Debouncer(debounce.same_code_same_session_s)`, nhận thêm `history`; trả `EngineEvent` sau debounce. Phạm vi debounce = vòng đời instance `Engine`.
- `schemas/events.py`: thêm `EngineEvent.config_hash: str = ""` *(giả định: mặc định rỗng để không phá F12/simulator đang làm song song; Engine luôn điền `Engine.config_hash`)*. Cập nhật event-engine.md mục 2.
- Builder: `PoseSequence.turn_over(seconds, degrees=60)` xoay đường vai (half_width) quanh tâm vai, giữ thân nằm.

**Các bước:**
1. Commit plan (spec).
2. Test trước: `tests/engine/test_debounce.py` (unit + qua engine), `tests/engine/test_rules_body.py` (AC1–AC5, ca âm tính mục 6, R4, R5, R6). Xác nhận đỏ vì thiếu module/sự kiện. Commit `test(F15): …`.
3. Cài `debounce.py`, `rules/body.py`, nối `RuleSet`/`Engine`, `config_hash` vào `EngineEvent`. Commit nhỏ.
4. Doc: event-engine.md mục 2 (`config_hash` trong `EngineEvent`), mục 5/7 nếu khác.
5. `make check`, `scripts\dev.ps1 check`; bằng chứng ở mục 10; trạng thái "In review".

**Rủi ro:** F12 (worker/replay) đọc `EngineEvent`: thêm trường có mặc định nên tương thích. Nhiễu tư thế ngoài ROI (điều dưỡng) không vào được rule vì rule chỉ đọc trạng thái của người mục tiêu.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
