# F27 – Trạng thái nghỉ/hoạt động (tham khảo)

| Thuộc tính | Giá trị |
|---|---|
| Mã | F27 |
| Trạng thái | Todo |
| Ưu tiên | MVP (theo HS, conflicts C02) |
| Milestone | M3 |
| Ước lượng | 1 phiên |
| Phụ thuộc | F23, F26 |
| Nhánh code | A (vision/engine) + C (frontend/test) |
| Nguồn | HS §5.3, §7.3, §9.1; PDF §6.3 (tr.8), §4.2 (tr.5); conflicts C02 |

## 1. Mục tiêu

Hiển thị một **trạng thái tham khảo** về mức hoạt động quan sát được, dựa trên mức vận động (F23) và trạng thái mắt (F26). Cơ thể ít chuyển động kéo dài và mắt đóng khi mặt đủ rõ → "Đang nghỉ - dữ liệu tham khảo"; vận động tăng hoặc mắt mở lại → "Đang hoạt động" (HS §5.3; PDF §6.3). Đây **không** phải phân loại giấc ngủ, không thay phương pháp đánh giá y khoa, và **không** tạo cảnh báo. PDF xếp chức năng này là "Mở rộng"; HS đưa vào lộ trình tuần 7–8 nên dự án áp dụng HS (conflicts C02).

## 2. Phạm vi

**Trong phạm vi**
- `engine/rest.py`: tính `rest_status` (`RESTING` / `ACTIVE` / `UNKNOWN`) trong `BodyStateSnapshot`.
- Gửi `rest_status` qua `POST /internal/v1/cameras/{id}/state` và WS `bed.state` (trường đã có).
- Hiển thị trên "Theo dõi trực tiếp" và thẻ giường ở "Tổng quan".
- Text trong `vi.ts`, test từ cấm.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Phân loại ngủ/tỉnh theo nghĩa y khoa (không làm; PDF §4.2; HS §9.1).
- Sự kiện hoặc cảnh báo khi đổi trạng thái nghỉ/hoạt động (không làm; event-engine.md mục 5).
- Tính mức vận động (→ F23) và tín hiệu mắt (→ F26).
- Thống kê thời gian nghỉ theo ca (→ F34 nếu cần).

## 3. Yêu cầu chi tiết

- **R1.** `RESTING` khi đồng thời: `activity_level = LOW` liên tục ≥ `rest.low_activity_s`; tín hiệu `eyes_closed` bật liên tục ≥ `rest.eyes_closed_s`; `face_status = OK` trong suốt khoảng đó. *(HS §5.3; PDF §6.3)*
- **R2.** Đang `RESTING`, chuyển sang `ACTIVE` khi `activity_level` rời `LOW` hoặc mắt mở (`eyes_closed` tắt với `face_status = OK`), và điều kiện mới giữ ≥ `rest.active_hold_s`. *(HS §5.3; AGENTS.md quy tắc 6 "không tin một frame"; giả định: khóa mới `rest.active_hold_s`)*
- **R3.** `ACTIVE` cũng là trạng thái khi có người mục tiêu và: `activity_level ≠ LOW`, hoặc mặt rõ và mắt mở. *(HS §5.3; giả định cho trạng thái ban đầu)*
- **R4.** `UNKNOWN` khi `body_state = NO_OBSERVATION`, hoặc `activity_level = LOW` mà mặt không rõ (`face_status ≠ OK`). Đang `RESTING` mà mất mặt → `UNKNOWN`, **không** giữ "Đang nghỉ". Mặt không rõ thì không bao giờ kết luận "Đang nghỉ". *(HS §9.1; PDF §17 (tr.17))*
- **R5.** `rest_status` là **trạng thái hiển thị**: không sinh `EngineEvent`, không tạo cảnh báo. Mỗi lần chuyển đổi, engine ghi một entry mức LOG vào `explanation` của state (rule_id, `activity_level`, thời gian mắt đóng). *(HS §5.3; event-engine.md mục 5, nơi việc ghi entry LOG đã được đánh dấu là giả định)*
- **R6.** UI hiển thị đúng câu "Đang nghỉ - dữ liệu tham khảo" / "Đang hoạt động"; `UNKNOWN` hiển thị "Mức hoạt động: không đủ dữ liệu" *(giả định câu chữ)*. Không dùng "ngủ", "tỉnh" hay từ cấm khác. *(HS §5.3; glossary.md)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/engine/rest.py`; ghép vào `engine/engine.py` (bước 8, event-engine.md mục 3).
  - `server/src/postcare/schemas/`: enum `RestStatus` (`RESTING`, `ACTIVE`, `UNKNOWN`).
  - `web/src/pages/LiveView/` (khối trạng thái), `web/src/pages/Overview/` (nhãn phụ trên thẻ giường), `web/src/i18n/vi.ts`.
- **Dữ liệu:** không có bảng mới. Trạng thái hiện tại chỉ ở RAM của API ([data-model.md](../02-architecture/data-model.md), "Dữ liệu không lưu trong DB").
- **API:** dùng trường `rest_status` có sẵn trong `POST /internal/v1/cameras/{id}/state` và WS `bed.state` ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** "Theo dõi trực tiếp", thẻ giường "Tổng quan".
- **Cấu hình** ([event-engine.md](../02-architecture/event-engine.md) mục 6): `rest.low_activity_s`, `rest.eyes_closed_s`; dùng tín hiệu `face.signals.eyes_closed` của F26. Khóa mới *(giả định)*: `rest.active_hold_s`.

## 5. Acceptance criteria

- [ ] **AC1.** Ít vận động kéo dài + mắt đóng (mặt rõ) → `RESTING` ("Đang nghỉ - dữ liệu tham khảo"). Vận động tăng hoặc mắt mở giữ ≥ `rest.active_hold_s` → `ACTIVE` ("Đang hoạt động"). *(HS §5.3; PDF §6.3)* — *Kiểm chứng:* test `test_rest_enters_when_low_activity_and_eyes_closed`, `test_rest_exits_on_activity_or_eyes_open`; mở mắt 1–3 frame không làm đổi trạng thái.
- [ ] **AC2.** Mặt không rõ → không bao giờ `RESTING`; đang `RESTING` mà mất mặt → `UNKNOWN`. *(HS §9.1)* — *Kiểm chứng:* test `test_no_resting_without_clear_face`, `test_resting_to_unknown_when_face_lost`.
- [ ] **AC3.** Chuyển đổi trạng thái nghỉ/hoạt động không tạo sự kiện hay cảnh báo; chỉ có entry LOG trong `explanation` của state. *(HS §5.3; event-engine.md mục 5)* — *Kiểm chứng:* test engine `test_rest_transitions_emit_no_events` (chuỗi nghỉ → hoạt động → nghỉ, `EngineOutput.events` không có mã nào do rest); test API `test_state_with_rest_status_creates_no_alert`.
- [ ] **AC4.** UI hiển thị đúng câu và không có từ "ngủ" / "tỉnh". *(glossary.md; PDF §6.3)* — *Kiểm chứng:* component test cho 3 giá trị `rest_status`; `vi.test.ts` quét từ cấm.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit (engine) | `test_rest_enters_when_low_activity_and_eyes_closed`, `test_rest_exits_on_activity_or_eyes_open` | Ít vận động nhưng mắt mở → không `RESTING`; mở mắt 2 frame → vẫn `RESTING` |
| AC2 | unit (engine) | `test_no_resting_without_clear_face`, `test_resting_to_unknown_when_face_lost` | Mặt `TOO_SMALL` + ít vận động 10 phút → `UNKNOWN` |
| AC3 | unit (engine) + API | `test_rest_transitions_emit_no_events`, `test_state_with_rest_status_creates_no_alert` | — |
| AC4 | component + vitest | `RestStatusBadge.test.tsx`, `vi.test.ts` | — |
| — | replay (thủ công) | Video S12, S13, S16 (evaluation.md): S13 có thể "Đang nghỉ"; S12 (mặt quay đi) không bao giờ "Đang nghỉ"; S16 không có sự kiện do rest | — |

## 7. Giả định

- *(giả định)* Khóa mới `rest.active_hold_s` để tránh đổi trạng thái theo một frame.
- *(giả định)* Trạng thái ban đầu và quy tắc `UNKNOWN` theo R3–R4.
- *(giả định)* Câu hiển thị cho `UNKNOWN`: "Mức hoạt động: không đủ dữ liệu".
- *(giả định)* Hiển thị thêm nhãn phụ trên thẻ giường ở "Tổng quan" (ngoài "Theo dõi trực tiếp").

## 8. Câu hỏi mở

- Entry LOG khi đổi trạng thái chỉ nằm trong `explanation` của state, mà state không được lưu DB. Vì vậy timeline sẽ **không** có dòng "Đang nghỉ / Đang hoạt động". Có cần hiện trên timeline không? Nếu có thì phải thêm mã sự kiện mức LOG vào catalog (sửa event-engine.md). **Không chặn**; mặc định là không hiện.

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
