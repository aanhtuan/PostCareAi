# F26 – Tín hiệu khuôn mặt và FACE_ATTENTION

| Thuộc tính | Giá trị |
|---|---|
| Mã | F26 |
| Trạng thái | In progress |
| Ưu tiên | MVP |
| Milestone | M3 |
| Ước lượng | 3 phiên |
| Phụ thuộc | F25, F23 |
| Nhánh code | A (vision/engine) + C (frontend/test) |
| Nguồn | HS §5.1, §5.3, §9.1; PDF §6.2 (tr.7–8), §7.4 (tr.9); conflicts C05 |

## 1. Mục tiêu

Biến các hệ số blendshape (F25) thành **tín hiệu quan sát theo thời gian**: mắt đóng/mở, nhắm mắt kéo dài, hạ lông mày, nheo mắt, thay đổi vùng mũi-miệng. Khi nhiều tín hiệu cùng duy trì đủ lâu, engine tạo sự kiện `FACE_ATTENTION` ("Phát hiện biểu hiện khuôn mặt cần kiểm tra"). Mức ưu tiên tăng khi tín hiệu mặt đi kèm thay đổi vận động (HS §5.3; PDF §7.4; conflicts C05). Đây là thông tin bổ sung để nhân viên y tế kiểm tra. Hệ thống **không** gán nhãn đau, mất ý thức hay ngủ (PDF §6.2). Thiếu dữ liệu mặt không được suy ra là bình thường (HS §9.1).

## 2. Phạm vi

**Trong phạm vi**
- `engine/face.py`: làm mượt blendshape, tính tín hiệu bật/tắt và thời gian duy trì; `face_status`, `face_signals` trong `BodyStateSnapshot`.
- `engine/rules/face.py`: rule `FACE_ATTENTION`, nâng ưu tiên lên HIGH khi kèm vận động HIGH hoặc đổi trạng thái cơ thể.
- Hiển thị trạng thái mặt và tín hiệu đang bật trên màn hình "Theo dõi trực tiếp".
- Text tiếng Việt trong `vi.ts` và test từ cấm.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Adapter, cổng chất lượng, cắt vùng đầu (→ F25).
- Trạng thái "Đang nghỉ - dữ liệu tham khảo" (→ F27, dùng lại tín hiệu mắt của F26).
- Lưu, phát WS và màn hình cảnh báo cho `FACE_ATTENTION` (đã có sẵn từ F17–F20 theo catalog).
- Ước lượng mức đau, cảm xúc, Action Units, Py-Feat (không làm; PDF §4.2, §6.2).

## 3. Yêu cầu chi tiết

- **R1.** Mỗi tín hiệu trong `face.signals` (`eyes_closed`, `brow_down`, `eye_squint`, `nose_sneer`, `mouth_change`) có giá trị = **lớn nhất** trong các khóa blendshape của nó, sau khi làm mượt bằng `smoothing.ema_alpha`. Tín hiệu "bật" khi giá trị ≥ `threshold` của tín hiệu đó. *(HS §5.1, §5.3; PDF §6.2; giả định: cách gộp trái/phải bằng max và dùng lại `smoothing.ema_alpha`)*
- **R2.** "Nhắm mắt kéo dài" (`eyes_closed_prolonged`) bật khi `eyes_closed` bật liên tục ≥ `face.eyes_closed_prolonged_s`. Đây là tín hiệu hiển thị, **không** được đếm thêm một lần khi tính FACE_ATTENTION (nhóm mắt chỉ tính một tín hiệu). *(HS §5.3; PDF §6.2; giả định cho cách đếm)*
- **R3.** Ở frame `face = None` (không chạy face theo chu kỳ N frame), engine giữ giá trị tín hiệu gần nhất. Khi `face_status ≠ OK`: xóa mọi tín hiệu, đặt lại mọi bộ đếm thời gian, `face_signals` rỗng, UI hiện "Không đủ dữ liệu khuôn mặt". **Không** coi là "bình thường". *(HS §9.1; event-engine.md mục 8; giả định cho việc giữ giá trị ở frame bỏ qua)*
- **R4.** `FACE_ATTENTION` được tạo khi số tín hiệu (R1, R2) cùng bật ≥ `face.attention_min_signals` và giữ liên tục ≥ `face.attention_hold_s`, trong suốt thời gian đó `face_status = OK` và có người mục tiêu (`body_state ≠ NO_OBSERVATION`). *(HS §5.3; PDF §6.2, §7.4; event-engine.md mục 5)*
- **R5.** Mức ưu tiên mặc định `MEDIUM`. Nâng lên `HIGH` khi trong cửa sổ `face.attention_hold_s` ngay trước lúc phát sự kiện có `activity_level = HIGH` hoặc `body_state` đổi (không tính chuyển vào/ra `NO_OBSERVATION`). `explanation` ghi `escalated_by` (`activity_high` / `state_change`). *(HS §5.3; PDF §7.4; conflicts C05; giả định: dùng lại `face.attention_hold_s` làm cửa sổ "đi kèm", không thêm khóa)*
- **R6.** Hạ lông mày ngắn (dưới `face.attention_hold_s`) khi đang nằm yên **không** tạo sự kiện. Một tín hiệu đơn lẻ kéo dài cũng không tạo sự kiện. *(PDF §7.4; testing.md mục 2)*
- **R7.** Debounce theo `debounce.same_code_same_session_s` như các sự kiện khác. Mức ưu tiên chốt tại thời điểm phát; không phát lại sự kiện chỉ để nâng ưu tiên trong cửa sổ debounce. *(A01; giả định cho phần nâng ưu tiên)*
- **R8.** `explanation` của `FACE_ATTENTION` gồm `rule_id`, danh sách tín hiệu đang bật, thời gian giữ, `activity_level`, `escalated_by` (nếu có). *(HS §6.2; event-engine.md mục 1)*
- **R9.** Màn hình "Theo dõi trực tiếp" hiển thị trạng thái khuôn mặt và các tín hiệu đang bật, lấy từ WS `bed.state` (`face_status`, `face_signals`). *(HS §5.3; PDF §16 (tr.17))*
- **R10.** Mọi text mới nằm trong `web/src/i18n/vi.ts`, không chứa từ cấm. Gợi ý *(giả định)*: "Mắt đóng", "Nhắm mắt kéo dài", "Hạ lông mày", "Nheo mắt", "Nhăn vùng mũi", "Thay đổi vùng miệng", "Không đủ dữ liệu khuôn mặt", "Mặt quá nhỏ trong khung hình", "Không thấy khuôn mặt". *(PDF §9.2 (tr.11); glossary.md)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/engine/face.py`: tín hiệu, làm mượt, thời gian duy trì.
  - `server/src/postcare/engine/rules/face.py`: rule `FACE_ATTENTION` + nâng ưu tiên.
  - `server/src/postcare/schemas/`: `FaceSignals` (danh sách tín hiệu đang bật, `eyes_closed_prolonged`) trong `BodyStateSnapshot`.
  - `server/src/postcare/engine/engine.py`: ghép bước 8 (event-engine.md mục 3).
  - `web/src/pages/LiveView/FaceSignalsPanel.tsx`, `web/src/i18n/vi.ts`.
- **Dữ liệu:** không có bảng mới. Sự kiện lưu vào `events` (F17); `explanation` JSONB ([data-model.md](../02-architecture/data-model.md)).
- **API:** không có endpoint mới. Dùng `POST /internal/v1/events`, `POST /internal/v1/cameras/{id}/state`, WS `bed.state` ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** "Theo dõi trực tiếp": khối "Tín hiệu khuôn mặt". Text cảnh báo "Phát hiện biểu hiện khuôn mặt cần kiểm tra" theo catalog.
- **Cấu hình** ([event-engine.md](../02-architecture/event-engine.md) mục 6): `face.signals.*` (`keys`, `threshold`), `face.eyes_closed_prolonged_s`, `face.attention_min_signals`, `face.attention_hold_s`, `smoothing.ema_alpha`, `debounce.same_code_same_session_s`. Không thêm khóa mới.

## 5. Acceptance criteria

- [ ] **AC1.** Engine tính các tín hiệu mắt đóng/mở, nhắm kéo dài, hạ lông mày, nheo mắt, thay đổi vùng mũi-miệng theo thời gian. "Theo dõi trực tiếp" hiển thị chúng bằng tiếng Việt. *(HS §5.1, §5.3)* — *Kiểm chứng:* test `test_face_signals_on_off_with_threshold`, `test_eyes_closed_prolonged`; component test `FaceSignalsPanel.test.tsx` với payload `bed.state` mẫu.
- [ ] **AC2.** `FACE_ATTENTION` chỉ tạo khi ≥ `face.attention_min_signals` tín hiệu cùng duy trì ≥ `face.attention_hold_s`. Hạ lông mày ngắn khi đang nằm yên **không** tạo sự kiện. *(HS §5.3; PDF §7.4)* — *Kiểm chứng:* test `test_face_attention_two_signals_held` (dương tính); `test_short_brow_down_while_lying_no_event`, `test_single_signal_long_no_event` (âm tính); dùng builder `face(signals={…}, seconds=…)`.
- [ ] **AC3.** Tín hiệu mặt kèm `activity_level = HIGH` hoặc đổi `body_state` trong cửa sổ giữ → `priority = HIGH`, có `escalated_by` trong `explanation`; không kèm → `MEDIUM`. *(HS §5.3; PDF §7.4; C05)* — *Kiểm chứng:* test `test_face_attention_escalates_with_high_activity`, `test_face_attention_escalates_with_state_change`, `test_face_attention_medium_when_still`.
- [ ] **AC4.** `face_status ≠ OK` → không có tín hiệu, không có `FACE_ATTENTION`, UI hiện "Không đủ dữ liệu khuôn mặt", không hiện câu nào hàm ý bình thường. *(HS §9.1)* — *Kiểm chứng:* test `test_face_not_ok_clears_signals_and_no_event` (mặt quay đi giữa chừng → bộ đếm reset); component test trạng thái `NOT_VISIBLE`.
- [ ] **AC5.** Text mới trong `vi.ts` qua test từ cấm (không có "đau", "chẩn đoán", "bất tỉnh", "ngủ"…). *(glossary.md; PDF §9.2)* — *Kiểm chứng:* `web/src/i18n/vi.test.ts` trong `make check`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit (engine) | `test_face_signals_on_off_with_threshold`, `test_face_signals_hold_on_skipped_frames`, `test_eyes_closed_prolonged` | Giá trị dao động dưới ngưỡng → không bật |
| AC1 | component | `FaceSignalsPanel.test.tsx` | `face_signals` rỗng → không liệt kê tín hiệu |
| AC2 | unit (engine) | `test_face_attention_two_signals_held` | `test_short_brow_down_while_lying_no_event`; `test_single_signal_long_no_event`; `test_eyes_closed_and_prolonged_count_once` |
| AC3 | unit (engine) | `test_face_attention_escalates_with_high_activity`, `..._with_state_change` | `test_face_attention_medium_when_still`; chuyển vào `NO_OBSERVATION` không tính là đổi trạng thái |
| AC4 | unit + component | `test_face_not_ok_clears_signals_and_no_event` | Mặt quay đi (S12 trong evaluation.md) → không FACE_ATTENTION |
| AC5 | unit (vitest) | `vi.test.ts` quét từ cấm | — |
| — | replay (thủ công) | Chạy replay trên video S12, S13, S14 của tập dev; S14 có FACE_ATTENTION, S12/S13 không | — |

## 7. Giả định

- *(giả định)* Gộp nhiều khóa blendshape của một tín hiệu bằng giá trị lớn nhất; làm mượt bằng `smoothing.ema_alpha`.
- *(giả định)* `eyes_closed` và `eyes_closed_prolonged` chỉ tính là một tín hiệu khi đếm cho FACE_ATTENTION.
- *(giả định)* Cửa sổ "đi kèm" để nâng ưu tiên = `face.attention_hold_s`; "đổi trạng thái" không tính chuyển vào/ra `NO_OBSERVATION`.
- *(giả định)* Không phát lại FACE_ATTENTION để nâng ưu tiên trong cửa sổ debounce.
- *(giả định)* Câu chữ tiếng Việt cho từng tín hiệu (R10); có thể chỉnh khi review UI.

## 8. Câu hỏi mở

- `eyes_closed` có nên dùng giá trị nhỏ nhất của hai mắt (cả hai mắt cùng đóng) thay vì lớn nhất không? Nếu cần thì phải thêm khóa gộp theo từng tín hiệu vào config. **Không chặn**; mặc định dùng max, xem lại sau khi đo tập dev.
- Có cần phát thêm một FACE_ATTENTION mức HIGH khi vận động tăng **sau** khi đã phát mức MEDIUM (trong cửa sổ debounce) không? **Không chặn**; mặc định là không.

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

Phụ thuộc F25, F23 đã `Done`. Không có câu hỏi mở mức chặn. Không có migration, endpoint hay thư viện mới; `FaceSignalsIn` (API nội bộ) và `FaceSignals` (snapshot) đã có sẵn nên không cần `make gen-api-types`.

Code dùng lại: `FaceObservation` (`schemas/observation.py`, F25), `FaceSignals`/`BodyStateSnapshot` (`schemas/state.py`), `FaceConfig` (`schemas/engine_config.py`), `EventDraft`/`VisibilityBuffer` (`engine/rules/common.py`), `Debouncer` (`engine/debounce.py`), `RuleSet` (`engine/rules/__init__.py`), worker đã gửi `face_signals` từ snapshot (`worker/loop.py`).

1. **Test trước (engine)**: `server/tests/engine/face_builders.py` (builder `face(signals={…}, seconds=…)` gắn `FaceObservation` tổng hợp vào chuỗi `PoseSequence`), `server/tests/engine/test_face_signals.py` (AC1, AC4), `server/tests/engine/test_rules_face.py` (AC2, AC3, debounce, cô lập).
   - AC1: `test_face_signals_on_off_with_threshold`, `test_face_signals_below_threshold_stay_off` (âm tính), `test_face_signal_single_frame_spike_smoothed` (âm tính), `test_face_signals_hold_on_skipped_frames`, `test_eyes_closed_prolonged`, `test_signal_uses_max_of_keys`.
   - AC2: `test_face_attention_two_signals_held`; âm tính `test_short_brow_down_while_lying_no_event`, `test_single_signal_long_no_event`, `test_eyes_closed_and_prolonged_count_once`, `test_signals_shorter_than_hold_no_event`, `test_face_attention_requires_target`.
   - AC3: `test_face_attention_escalates_with_high_activity`, `test_face_attention_escalates_with_state_change`, `test_face_attention_medium_when_still`, `test_no_observation_transition_not_state_change` (âm tính).
   - AC4: `test_face_not_ok_clears_signals_and_no_event` (mặt quay đi giữa chừng → reset), `test_face_too_small_no_signals`.
   - R7: `test_face_attention_debounced`. Cô lập: `test_face_does_not_change_body_events` (cùng chuỗi pose có/không có face → cùng sự kiện cơ thể).
2. **`engine/face.py`**: `FaceTracker` (EMA `smoothing.ema_alpha` trên giá trị max của các khóa, ngưỡng `face.signals.*.threshold`, `eyes_closed_prolonged_s`, giữ giá trị khi `face = None`, reset khi `status ≠ OK`, mất quan sát hoặc đổi mục tiêu) → `FaceReading` (status, `FaceSignals`, giá trị đã làm mượt, số tín hiệu đếm cho FACE_ATTENTION).
3. **`engine/rules/face.py`**: `FaceRules` (đoạn giữ ≥ `attention_min_signals` tín hiệu trong `attention_hold_s`, phát một lần mỗi đoạn; ưu tiên `MEDIUM`, nâng `HIGH` theo R5). `EventDraft` thêm `priority` tùy chọn; `RuleSet` dùng nó (kiểm tra theo catalog ở `EngineEvent`).
4. **`engine/engine.py`**: ghép `FaceTracker` + `face_status`/`face_signals` vào snapshot; truyền `FaceReading` vào `RuleSet`.
5. **Web**: `web/src/pages/LiveView/FaceSignalsPanel.tsx` + `FaceSignalsPanel.test.tsx`; text trong `vi.ts` (`faceSignal`, `live.faceSignals…`); chèn khối vào `LiveViewPage.tsx` (thay dòng "Khuôn mặt").
6. **Kiểm chứng thật**: `postcare replay` bật face trên clip cận mặt `data/external` (pexels); thống kê tần suất từng tín hiệu và FACE_ATTENTION. S12–S14 chưa có trong tập dev: ghi rõ.
7. **Doc**: `event-engine.md` mục 3 (bước 8), mục 5 (FACE_ATTENTION nâng ưu tiên), mục 8 (cách tính tín hiệu); spec §10.
8. `make check` + `make test-vision`.

Rủi ro: ngưỡng mặc định chưa hiệu chỉnh trên người bệnh thật (chỉ clip stock); mặt nằm xoay ngang thường `NOT_VISIBLE` (F25) nên ít tín hiệu, đúng tinh thần "không biết".

Giả định thêm khi lập kế hoạch *(giả định)*:
- Khóa của tín hiệu không có trong `blendshapes` ở frame `OK` → tín hiệu đó tắt và bỏ giá trị làm mượt cũ.
- Đổi người mục tiêu → reset tín hiệu mặt như `face_status ≠ OK`. Mất quan sát cơ thể (`NO_OBSERVATION`) **không** reset tín hiệu (clip cận mặt thật: hông ngoài khung nhưng mặt `OK`); chỉ chặn FACE_ATTENTION (R4). *(Đổi sau bước kiểm chứng thật; bản kế hoạch đầu reset cả khi `NO_OBSERVATION`.)*
- Mỗi đoạn giữ liên tục chỉ phát FACE_ATTENTION tối đa một lần (giống `ACTIVITY_*`, F23); đoạn mới cần tín hiệu tụt dưới `attention_min_signals` rồi bật lại.
- `confidence` của FACE_ATTENTION = visibility trung bình keypoint bắt buộc trong đoạn (như các rule khác).
- "Đổi `body_state`" = trong cửa sổ có ≥ 2 trạng thái ổn định khác nhau, không tính `NO_OBSERVATION`.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
