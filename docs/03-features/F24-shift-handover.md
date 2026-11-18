# F24 – Bàn giao ca

| Thuộc tính | Giá trị |
|---|---|
| Mã | F24 |
| Trạng thái | In progress |
| Ưu tiên | MVP |
| Milestone | M2 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F19, F22 |
| Nhánh code | B+C (backend + frontend) |
| Nguồn | PDF §5 (tr.6), §9.1 (tr.11), bảng tr.10, §15.1 (tr.16); HS §2.2, §4.2, §6.2, Hình 3; QA#19; A15 |

## 1. Mục tiêu

Người phụ trách ca cần xem cảnh báo còn tồn đọng và lịch sử xử lý để bàn giao (HS §2.2). Feature này làm màn hình "Bàn giao ca" (PDF §9.1 (tr.11)): chọn một ca trực hoặc một khoảng thời gian, rồi xem tổng hợp theo từng giường gồm:
- số sự kiện theo loại;
- cảnh báo đã xử lý / chưa xử lý;
- số lần đổi trạng thái.

Cảnh báo tồn đọng nằm đầu trang. Số liệu tính bằng **SQL aggregation** (PDF bảng tr.10). Ca lấy từ `shift_definitions` (QA#19). Trang in được (A15). Dashboard thống kê dài hạn là phần sau MVP (F34; [conflicts.md](../00-source/conflicts.md) C17).

## 2. Phạm vi

**Trong phạm vi**
- `GET /api/v1/shifts` và `GET /api/v1/handover?shift_id&date` hoặc `?from&to`.
- Truy vấn tổng hợp theo giường và danh sách cảnh báo tồn đọng.
- Màn hình `web/src/pages/Handover/` có chọn ca/khoảng thời gian và print CSS.
- Test số liệu trên dữ liệu mẫu.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Thống kê dài hạn, biểu đồ theo ca (→ F34, sau MVP).
- Sửa danh sách ca trên UI *(QA#19: cấu hình trong DB; seed ở F01)*.
- Xuất PDF/Excel phía server *(không có trong nguồn; in bằng trình duyệt theo A15)*.
- Ghi nhận "đã bàn giao" hay chữ ký *(không có trong nguồn)*.

## 3. Yêu cầu chi tiết

**Backend**

- **R1.** `GET /api/v1/shifts` trả các ca trong `shift_definitions` (`id`, `name`, `start_time`, `end_time`) *(QA#19; data-model.md)*.
- **R2.** `GET /api/v1/handover` nhận một trong hai dạng tham số *(QA#19: chọn ca hoặc khoảng thời gian tùy ý; api-conventions.md)*:
  - `shift_id` + `date`: khoảng = `[date + start_time, date + end_time)` theo giờ Asia/Ho_Chi_Minh, đổi sang UTC để truy vấn. Ca vắt qua nửa đêm (22:00–06:00) có `end` là ngày hôm sau; `date` là **ngày bắt đầu ca** *(data-model.md: ca đêm vắt qua nửa đêm; giả định: quy ước `date`)*.
  - `from` + `to` (ISO 8601): khoảng tùy ý. `from ≥ to` → 400 `VALIDATION_ERROR`.
  - Khoảng là nửa mở `[from, to)` *(giả định: tránh đếm trùng ở biên giữa hai ca liền nhau)*.
  - `to` ở tương lai (ca đang diễn ra) thì các số liệu "tại cuối khoảng" tính tới thời điểm hiện tại *(giả định)*.
- **R3.** Tổng hợp theo **mọi giường đang dùng** (giường không có sự kiện vẫn hiện số 0) *(PDF §9.1 (tr.11); giả định: hiện đủ giường để bàn giao không sót)*. Với mỗi giường:
  - `event_counts`: số sự kiện theo `code` có `occurred_at` trong khoảng, mọi mức ưu tiên *(PDF §9.1 (tr.11): "tổng hợp sự kiện theo ca")*.
  - `alerts_resolved` / `alerts_unresolved`: trong các cảnh báo có sự kiện thuộc khoảng, đếm số đã `RESOLVED` trước cuối khoảng và số chưa *(PDF §9.1 (tr.11): "cảnh báo đã/chưa xử lý")*.
  - `state_change_count`: số lần đổi trạng thái *(PDF §9.1 (tr.11))*. Data model không lưu từng lần đổi trạng thái cơ thể (trạng thái chỉ nằm trong RAM, theo data-model.md). Vì vậy giá trị này = số sự kiện tư thế/vị trí `POSTURE_CHANGE`, `SIT_UP`, `STAND_UP`, `BED_EDGE`, `BED_EXIT`, `RETURN_TO_BED` trong khoảng *(giả định: dùng sự kiện làm đại diện)*.
- **R4.** `outstanding_alerts`: cảnh báo **tồn đọng tại cuối khoảng**, tức tạo trước `to` và chưa xử lý tại `to` (`resolved_at` null hoặc ≥ `to`), kể cả cảnh báo tạo trước `from`. Sắp ưu tiên cao trước, rồi cũ trước *(HS §2.2: "cảnh báo còn tồn đọng"; giả định: định nghĩa và thứ tự sắp)*. Mỗi mục có giường, mã sự kiện, mức, `occurred_at`, `status`, người tiếp nhận.
- **R5.** Số liệu tính bằng SQL aggregation (`COUNT … GROUP BY bed_id, code`, `FILTER (WHERE …)`) trong `domain/handover.py`. Không lặp từng bản ghi bằng Python *(PDF bảng tr.10: "Bàn giao ca / thống kê sự kiện: SQL aggregation")*.
- **R6.** Mọi vai trò xem được *(api-conventions.md)*. `shift_id` không tồn tại → 404.

**Frontend**

- **R7.** Màn hình "Bàn giao ca" *(PDF §9.1 (tr.11))*:
  - Chọn ca + ngày. Mặc định là ca hiện tại theo giờ Asia/Ho_Chi_Minh, như header của F09.
  - Hoặc chọn khoảng thời gian tùy ý *(QA#19)*.
- **R8.** Thứ tự trên trang:
  1. **Cảnh báo tồn đọng** ở đầu trang *(HS §2.2)*.
  2. Bảng theo giường: số sự kiện theo loại (câu tiếng Việt từ `vi.ts`, không hiện mã nội bộ), cảnh báo đã/chưa xử lý, số lần đổi trạng thái.
  
  Tiêu đề ghi rõ khoảng thời gian, ví dụ "Ca chiều 14:00–22:00, 12/10/2026" *(HS Hình 3: "Ca trực: 14:00–22:00")*.
- **R9.** In được *(A15)*:
  - Nút "In" gọi `window.print()`.
  - `@media print`: ẩn thanh điều hướng, bộ lọc và nút; nền trắng; bảng không cắt ngang giữa dòng; in tiêu đề khoảng thời gian và thời điểm in.
- **R10.** Text trong `vi.ts`, qua test từ cấm *(ADR-0005)*. Giờ hiển thị Asia/Ho_Chi_Minh *(data-model.md, mục Quy ước)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/domain/handover.py`: tính khoảng từ ca, các truy vấn tổng hợp.
  - `server/src/postcare/api/v1/handover.py`, `server/src/postcare/api/v1/shifts.py`.
  - `web/src/pages/Handover/HandoverPage.tsx`, `HandoverFilters.tsx`, `OutstandingAlerts.tsx`, `BedSummaryTable.tsx`, `handover.print.css`; `web/src/api/handover.ts`.
  - Test: `server/tests/domain/test_handover.py`, `server/tests/api/test_handover_api.py`; `web/src/pages/Handover/HandoverPage.test.tsx`.
- **Dữ liệu:** đọc `events`, `alerts`, `beds`, `users`, `shift_definitions`. Không có migration.
- **API:** `GET /api/v1/shifts`, `GET /api/v1/handover` ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** màn hình "Bàn giao ca". Text thêm vào `vi.ts`: tiêu đề, "Cảnh báo tồn đọng", "Đã xử lý", "Chưa xử lý", "Số lần đổi trạng thái", "In", nhãn chọn ca/khoảng thời gian, câu khi không có tồn đọng.
- **Cấu hình:** không có khóa engine. Ca lấy từ bảng `shift_definitions`.

## 5. Acceptance criteria

- [ ] **AC1.** Chọn ca hoặc khoảng thời gian; tổng hợp theo giường gồm số sự kiện theo loại, cảnh báo đã/chưa xử lý, số lần đổi trạng thái *(PDF §9.1 (tr.11); HS §2.2; QA#19)*. — *Kiểm chứng:* `server/tests/api/test_handover_api.py` (`test_handover_by_shift_and_date`, `test_handover_by_custom_range`, `test_beds_without_events_show_zero`, `test_invalid_range_400`); `HandoverPage.test.tsx::renders per-bed summary`.
- [ ] **AC2.** Cảnh báo tồn đọng (chưa xử lý tại cuối khoảng, kể cả tạo trước khoảng) hiện ở đầu trang *(HS §2.2)*. — *Kiểm chứng:* `server/tests/domain/test_handover.py::test_outstanding_includes_older_unresolved_excludes_resolved_before_end`; `HandoverPage.test.tsx::outstanding alerts rendered first`.
- [ ] **AC3.** Số liệu tính bằng SQL aggregation và đúng trên dữ liệu mẫu, gồm ca đêm vắt qua nửa đêm và sự kiện đúng tại biên ca *(PDF bảng tr.10; QA#19)*. — *Kiểm chứng:* `test_handover.py` (`test_counts_match_seed_data`, `test_night_shift_crosses_midnight`, `test_event_at_boundary_counted_once`, `test_local_time_to_utc_conversion`).
- [ ] **AC4.** Trang in được bằng print CSS *(A15)*. — *Kiểm chứng:* `HandoverPage.test.tsx::print button calls window.print`; kiểm thủ công "Xem trước khi in" trên Chrome (ẩn điều hướng/nút, bảng không vỡ), ghi ở mục 10.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API (DB test) | Seed 3 giường, sự kiện nhiều loại, cảnh báo ở đủ trạng thái | `from ≥ to` → 400; `shift_id` lạ → 404 |
| AC2 | domain | Cảnh báo tạo trước `from` chưa xử lý; xử lý sau `to`; xử lý trước `to` | Cảnh báo đã xử lý trước `to` không nằm trong tồn đọng |
| AC3 | domain | Ca 22:00–06:00 ngày 12/10 = `[12/10 15:00Z, 12/10 23:00Z)`; sự kiện đúng lúc `14:00` local thuộc ca chiều, không thuộc ca sáng | Sự kiện của ca liền trước/sau không bị đếm |
| AC4 | component + thủ công | Mock `window.print` | — |
| R3 | domain | `state_change_count` chỉ đếm 6 code tư thế/vị trí | `ACTIVITY_*`, `CAMERA_*` không được đếm |
| R10 | unit | Test từ cấm của F20 bao phủ text mới | — |

## 7. Giả định

- *(giả định)* `date` là ngày bắt đầu ca; khoảng nửa mở `[from, to)`; ca đang diễn ra tính tới thời điểm hiện tại (R2).
- *(giả định)* Hiện mọi giường đang dùng, kể cả giường không có sự kiện (R3).
- *(giả định)* "Số lần đổi trạng thái" đếm bằng sự kiện tư thế/vị trí (R3).
- *(giả định)* Định nghĩa và thứ tự sắp của cảnh báo tồn đọng (R4).
- 3 ca mặc định, cấu hình trong DB (QA#19, giả định). Print CSS (A15).

## 8. Câu hỏi mở

- **Không chặn:** PDF §9.1 ghi "số lần thay đổi trạng thái" nhưng không nói rõ là trạng thái cơ thể hay trạng thái xử lý cảnh báo. Spec chọn trạng thái cơ thể, đếm qua sự kiện (R3). Nếu người dùng muốn đếm đúng từng lần đổi trạng thái cơ thể thì phải lưu thêm dữ liệu (thay đổi data-model).

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

**Khảo sát (2026-11-18).** Prototype đã có:
- `server/src/postcare/domain/handover.py`: `resolve_window` (ca + ngày theo Asia/Ho_Chi_Minh → UTC, ca qua đêm, `from ≥ to` → 400, ca lạ → 404, ca đã xóa vẫn dùng được qua `db.get`, F37 R9), `build_handover` (SQL `COUNT … GROUP BY bed_id, code`; `SUM(CASE …)` đã/chưa xử lý; đếm 6 code `STATE_CHANGE_CODES`; tồn đọng sắp `PRIORITY_RANK_SQL DESC, occurred_at ASC`; `cutoff = min(to, now)`).
- Route `GET /api/v1/handover` trong `api/v1/monitoring.py` (router `require_staff`: mọi vai trò nhân viên, FAMILY 403); `GET /api/v1/shifts` trong `api/v1/catalog.py` (F37, mặc định chỉ ca đang dùng).
- Test: `tests/test_timeline_handover.py` (`test_handover_counts`, `test_handover_by_shift`, `test_current_shift`, `test_shift_window_crosses_midnight`); `tests/api/test_shifts_admin.py::test_handover_works_for_deleted_shift`, `test_current_shift_ignores_deleted`; `tests/api/test_family_role_default_deny.py` (FAMILY 403 `/handover`).
- `web/src/pages/Handover/HandoverPage.tsx` (một file: chọn ca/ngày mặc định ca hiện tại qua `utils/shift.ts`, khoảng tùy chọn, tồn đọng trước bảng theo giường, nút In, text `vi.handover`), print CSS trong `web/src/styles.css` (`.no-print`, ẩn header/navbar, nền trắng, `tr` không cắt). Chưa có component test.

**AC đã đạt một phần (code có, thiếu test theo tên AC):** AC1 (API), AC3 (cửa sổ ca qua đêm), AC4 (print CSS, nút In). AC2 chưa có test domain cho cảnh báo tạo trước `from` / xử lý sau `to`.

**Thiếu (sẽ làm):**
1. *Test server* `server/tests/api/test_handover_api.py`: `test_handover_by_shift_and_date`, `test_handover_by_custom_range` (offset `+07:00` → UTC), `test_beds_without_events_show_zero`, `test_invalid_range_400` (`from > to`, `from = to`, thiếu tham số, thiếu `date`), `test_unknown_shift_404`, `test_doctor_can_read_handover`, `test_family_forbidden_handover`. `server/tests/domain/test_handover.py`: `test_outstanding_includes_older_unresolved_excludes_resolved_before_end`, `test_outstanding_order_high_first_then_oldest`, `test_counts_match_seed_data`, `test_night_shift_crosses_midnight`, `test_event_at_boundary_counted_once`, `test_local_time_to_utc_conversion`, `test_state_change_count_only_posture_codes` (ca âm: `ACTIVITY_*`, `CAMERA_*`, `OBSERVATION_LOST`), `test_outcome_counts`, `test_transferred_patient_events_stay_on_old_bed` (F04: sự kiện tính theo `events.bed_id` lúc xảy ra), `test_deleted_bed_with_events_listed`.
2. *Sửa:* tồn đọng lọc theo `alerts.created_at < to`; với khoảng trong quá khứ mà sự kiện gửi trễ (hoặc dữ liệu seed lịch sử) thì cảnh báo được đếm "chưa xử lý" ở bảng giường nhưng không vào danh sách tồn đọng. Đổi sang `events.occurred_at < to` cho thống nhất với bảng theo giường *(giả định)*. Thêm `alerts.id` làm khóa phụ khi sắp để thứ tự ổn định.
3. *Giường đã xóa:* hiện mọi giường đang dùng **và** giường đã xóa có sự kiện trong khoảng (để bàn giao không sót), thêm `is_active` vào `HandoverBedOut`; UI ghi "(đã xóa)" *(giả định; F03 xóa mềm)*.
4. *Tóm tắt kết quả kiểm tra:* thêm `outcome_counts` theo giường (cảnh báo có sự kiện trong khoảng, đã ghi kết quả trước cuối khoảng, theo `CONFIRMED|FALSE_ALARM|PATIENT_SAFE`) *(giả định; HS §3: "kết quả xác nhận và lịch sử để phục vụ tra cứu và bàn giao ca")*; cột "Kết quả kiểm tra" trên UI dùng `vi.outcome`. `event_counts` sắp theo `code` để in ổn định.
5. `make gen-api-types` sau khi đổi DTO.
6. *Component test* `web/src/pages/Handover/HandoverPage.test.tsx`: `renders per-bed summary`, `outstanding alerts rendered first`, `print button calls window.print`, `does not render internal codes`, `title shows shift period in Asia/Ho_Chi_Minh`, `defaults to current shift`, `sends custom range as ISO with +07:00`, `shows deleted bed label`.
7. Docs: `api-conventions.md` (định nghĩa tồn đọng, giường đã xóa, `outcome_counts`), `data-model.md` nếu cần, spec §7, §10.

**Lệch so với §4:** UI giữ một file `HandoverPage.tsx` (không tách `HandoverFilters`/`OutstandingAlerts`/`BedSummaryTable`), print CSS nằm trong `web/src/styles.css` dùng chung, route nằm trong `api/v1/monitoring.py`/`catalog.py` thay vì `handover.py`/`shifts.py` *(không đổi hành vi)*.

**Câu hỏi mở:** không có điểm chặn.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
