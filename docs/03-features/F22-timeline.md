# F22 – Timeline / Lịch sử theo dõi

| Thuộc tính | Giá trị |
|---|---|
| Mã | F22 |
| Trạng thái | Done |
| Ưu tiên | MVP |
| Milestone | M2 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F19 |
| Nhánh code | B+C (backend + frontend) |
| Nguồn | PDF §5 (tr.6), §9.1 (tr.11), §9.3 (tr.12), §16 (tr.17); HS §2.2, §4.3, Hình 3, §6.2, §8.3; ADR-0007 |

## 1. Mục tiêu

Người dùng cần tra cứu lại diễn biến của một phiên theo dõi mà không phải xem lại video (HS §6.2):
- sự kiện nào, lúc nào;
- ai tiếp nhận cảnh báo, kết quả kiểm tra ra sao.

Feature này làm API timeline gồm cả sự kiện lẫn thao tác cảnh báo, và màn hình "Lịch sử theo dõi" dạng "14:38:12 - Bệnh nhân ngồi dậy" (PDF §9.3 (tr.12)). Màn hình lọc được theo giường và thời gian, xem được người tiếp nhận, và ghi kết quả kiểm tra ngay tại đó (HS Hình 3). Đây là bước cuối của mốc tối thiểu Body AI → sự kiện → cảnh báo → xác nhận → timeline (HS §7.3; demo HS §8.3). Timeline không thay thế hồ sơ bệnh án (HS §2.2; PDF §3 (tr.5)).

> **Liên quan F04/F36 (bổ sung 17/11/2026):** sau khi chuyển giường, timeline của bệnh nhân nối các phiên qua `previous_session_id` ([F04](F04-monitoring-sessions.md)). Người nhà chỉ xem timeline của phiên được cấp quyền ([F36](F36-family-access.md)).

## 2. Phạm vi

**Trong phạm vi**
- `GET /api/v1/sessions/{id}/timeline` và `GET /api/v1/timeline?bed_id&from&to`, lọc thêm theo mức ưu tiên.
- Gộp sự kiện (`events`) và thao tác cảnh báo (`audit_logs` của alert), sắp theo thời gian.
- Màn hình `web/src/pages/Timeline/`: chọn giường/phiên, khoảng thời gian, mức ưu tiên; xem người tiếp nhận; ghi kết quả.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Tổng hợp theo ca (→ F24). Thống kê dài hạn (→ F34).
- Xuất file PDF/CSV *(không có trong nguồn)*.
- Phát lại video tại thời điểm sự kiện *(QA#29: không lưu video)*.
- Sửa hoặc xóa sự kiện *(data-model.md: không xóa cứng sự kiện)*.

## 3. Yêu cầu chi tiết

**Backend**

- **R1.** `GET /api/v1/sessions/{id}/timeline?priority&limit&offset` trả các mục của phiên. `GET /api/v1/timeline?bed_id&from&to&priority&limit&offset` trả các mục của một giường trong khoảng thời gian, qua mọi phiên, kể cả sự kiện camera có `session_id = null` *(api-conventions.md; PDF §9.1 (tr.11); HS Hình 3: "Lọc theo giường / thời gian")*. Bắt buộc có `bed_id`. Thiếu `from`/`to` thì lấy 24 giờ gần nhất *(giả định)*.
- **R2.** Mỗi mục có `kind`:
  - `kind = "event"`: `time = occurred_at`, `code`, `priority`, `observation_quality`, `event_id`, `alert` (tóm tắt nếu có: `id`, `status`, `outcome`, người tiếp nhận).
  - `kind = "alert_action"`: lấy từ `audit_logs` có `entity_type = "alert"` và `action ∈ {alert.acknowledge, alert.outcome, alert.resolve}`; `time = audit_logs.created_at`, `action`, `actor {id, full_name}`, `outcome` (với `alert.outcome`), `note`, `alert_id`, `event_code`.
  
  Mục `alert.create` không đưa vào vì đã có mục sự kiện tương ứng *(PDF §9.3 (tr.12); ADR-0007: "Timeline hiển thị riêng từng thao tác"; giả định: bỏ `alert.create`)*.
- **R3.** Sắp theo `time` tăng dần. Hai mục trùng thời điểm thì mục sự kiện đứng trước *(PDF §9.3 (tr.12), ví dụ theo thứ tự thời gian; giả định: quy tắc khi trùng)*.
- **R4.** Lọc `priority` (một hoặc nhiều mức): áp dụng cho mức của sự kiện; mục thao tác cảnh báo được giữ khi sự kiện gốc thỏa bộ lọc *(giả định)*. Phân trang `limit`/`offset`, `limit` tối đa 200 *(api-conventions.md)*.
- **R5.** Truy vấn bằng SQL (`UNION ALL` hai nguồn, `ORDER BY`), dùng index `(session_id, occurred_at)` và `(bed_id, occurred_at)` *(data-model.md)*. Không có bảng timeline riêng *(data-model.md: timeline tính bằng truy vấn)*.
- **R6.** Mọi vai trò xem được *(api-conventions.md)*. Phiên không tồn tại → 404.

**Frontend**

- **R7.** Màn hình "Lịch sử theo dõi" *(glossary.md; HS Hình 3; PDF §9.1 (tr.11) gọi là "Lịch sử bệnh nhân")*:
  - chọn giường và phiên (mặc định là phiên đang mở của giường), khoảng thời gian, mức ưu tiên;
  - truy cập từ "Xem chi tiết" của cảnh báo (F20) và từ thẻ giường.
- **R8.** Mỗi dòng có dạng `HH:mm:ss - <câu tiếng Việt>`, giờ Asia/Ho_Chi_Minh *(PDF §9.3 (tr.12); data-model.md, mục Quy ước)*:
  - Sự kiện: "14:38:12 - Bệnh nhân ngồi dậy".
  - Thao tác: "14:38:41 - Đã tiếp nhận cảnh báo (Nguyễn Văn A)", "… - Ghi kết quả: Bệnh nhân an toàn (Nguyễn Văn A)", "14:40:05 - Sự kiện đã xử lý (Nguyễn Văn A)" *(PDF §9.3 (tr.12); giả định: hiển thị tên người thực hiện trong ngoặc)*.
  - **Không** hiển thị mã nội bộ *(PDF §9.3 (tr.12))*.
  - Khi khoảng thời gian qua nhiều ngày thì chèn tiêu đề ngày `dd/MM/yyyy` *(giả định)*.
- **R9.** Mục sự kiện có cảnh báo hiện trạng thái, người tiếp nhận, kết quả ("Chưa ghi kết quả" nếu `null`). Người có quyền ghi thao tác được ngay trên dòng, dùng lại component `AlertActions` của F20 (hoặc bản tối giản nếu F20 chưa xong). DOCTOR chỉ xem *(HS Hình 3: "Xem người tiếp nhận + Ghi kết quả kiểm tra"; QA#18)*.
- **R10.** Khi nhận `event.created` hoặc `alert.updated` thuộc phiên hoặc giường đang xem thì làm mới cache timeline (F18) *(giả định: giữ timeline cập nhật trong demo HS §8.3)*.
- **R11.** Text trong `vi.ts`, qua test từ cấm *(ADR-0005)*. Layout ≥ 768px *(QA#26, giả định)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/domain/timeline.py`: truy vấn gộp.
  - `server/src/postcare/api/v1/timeline.py`: hai endpoint; schema `TimelineItemOut` (union theo `kind`).
  - `web/src/pages/Timeline/TimelinePage.tsx`, `TimelineFilters.tsx`, `TimelineItem.tsx`; `web/src/api/timeline.ts`.
  - Test: `server/tests/api/test_timeline.py`; `web/src/pages/Timeline/TimelinePage.test.tsx`.
- **Dữ liệu:** đọc `events`, `alerts`, `audit_logs`, `users`, `monitoring_sessions`. Không có migration.
- **API:** `GET /api/v1/sessions/{id}/timeline`, `GET /api/v1/timeline`. Ghi kết quả dùng endpoint của F19.
- **UI:** màn hình "Lịch sử theo dõi". Text thêm vào `vi.ts`: tiêu đề, nhãn bộ lọc, mẫu câu cho từng `action`, "Chưa ghi kết quả" (dùng chung F20), câu khi không có dữ liệu.
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [x] **AC1.** API timeline của phiên trả cả sự kiện và thao tác cảnh báo (tiếp nhận, ghi kết quả, xử lý), sắp theo thời gian tăng dần *(PDF §9.3 (tr.12); HS §6.2; ADR-0007)*. — *Kiểm chứng:* `server/tests/api/test_timeline.py` (`test_session_timeline_merges_events_and_alert_actions_sorted`, `test_outcome_rewrite_shows_two_actions`, `test_alert_create_not_listed`).
- [x] **AC2.** Hiển thị dạng "14:38:12 - Bệnh nhân ngồi dậy" theo giờ Asia/Ho_Chi_Minh; không hiện mã nội bộ *(PDF §9.3 (tr.12))*. — *Kiểm chứng:* `web/src/pages/Timeline/TimelinePage.test.tsx` (`formats line as HH:mm:ss - text in Asia/Ho_Chi_Minh`, `does not render internal codes`).
- [x] **AC3.** Lọc theo giường, phiên, khoảng thời gian, mức ưu tiên *(PDF §9.1 (tr.11); HS Hình 3)*. — *Kiểm chứng:* `test_timeline.py` (`test_bed_timeline_filters_by_time_range`, `test_filter_by_priority_keeps_related_actions`, `test_bed_timeline_includes_camera_events_without_session`); `TimelinePage.test.tsx::sends filter params`.
- [x] **AC4.** Xem người tiếp nhận và ghi kết quả kiểm tra ngay từ timeline; DOCTOR chỉ xem *(HS Hình 3; QA#18)*. — *Kiểm chứng:* `TimelinePage.test.tsx` (`shows acknowledger name`, `records outcome from timeline row`, `doctor sees no action buttons`).

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API (DB test) | Seed phiên có SIT_UP, BED_EDGE, BED_EXIT + alert đã tiếp nhận, ghi kết quả hai lần, xử lý | Sự kiện của phiên khác không xuất hiện; `alert.create` không xuất hiện |
| AC2 | component | Dữ liệu giả có `time` UTC `07:38:12Z` → hiển thị `14:38:12` | Không có chuỗi `BED_EXIT`, `SIT_UP` trên màn hình |
| AC3 | API + component | Sự kiện ngay tại biên `from`/`to`; lọc `priority=HIGH` | Sự kiện ngoài khoảng bị loại |
| AC4 | component | Vai NURSE ghi kết quả; vai DOCTOR | DOCTOR không có nút |
| R6 | API | Phiên không tồn tại | 404 |

## 7. Giả định

- *(giả định)* Thiếu `from`/`to` thì lấy 24 giờ gần nhất (R1).
- *(giả định)* Bỏ mục `alert.create` khỏi timeline (R2).
- *(giả định)* Khi trùng thời điểm thì sự kiện đứng trước (R3).
- *(giả định)* Lọc mức ưu tiên giữ cả thao tác của cảnh báo liên quan (R4).
- *(giả định)* Tên người thực hiện nằm trong ngoặc; có tiêu đề ngày khi khoảng qua nhiều ngày (R8).
- *(giả định)* Timeline tự làm mới khi có `event.created`/`alert.updated` (R10).
- *(giả định, 18/11)* `GET /sessions/{id}/timeline?chain=true` gộp chuỗi phiên chuyển giường; mặc định `chain=false` (một phiên) để F36 dùng đúng phiên được cấp. UI "Lịch sử theo dõi" luôn gửi `chain=true` khi xem theo phiên.
- *(giả định, 18/11)* Mục `kind = "session_action"` cho `session.transfer`/`pause`/`resume` (không đưa `session.start`/`end`); mục chuyển giường hiện ở cả giường cũ và giường mới; lọc mức ưu tiên luôn giữ mục thao tác phiên (không có mức).
- *(giả định, 18/11)* Khoảng thời gian theo giường là `[from, to)`. Tải tiếp bằng nút "Xem thêm" (`offset`) khi `total` lớn hơn số mục đã tải.

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

**Khảo sát (2026-11-18).** Prototype đã có:
- `server/src/postcare/domain/timeline.py`: `UNION ALL` sự kiện + audit `alert.acknowledge|outcome|resolve`, `ORDER BY time, ord, event_id, audit_id` (sự kiện trước khi trùng giờ, R3), lọc giường/phiên/khoảng `[from, to)`/mức ưu tiên (mục thao tác theo mức của sự kiện gốc, R4), mặc định 24 giờ, `from >= to` → 400, phiên không có → 404, `limit ≤ 200`.
- `GET /api/v1/sessions/{id}/timeline` (`require_staff`), `GET /api/v1/timeline` (router `require_staff`); FAMILY → 403 đã có trong `tests/api/test_family_role_default_deny.py`.
- `tests/test_timeline_handover.py::test_session_timeline_order` (thứ tự, actor, outcome, không có `alert.create`, lọc giường + khoảng); `test_timeline_unknown_session_404`; `tests/api/test_catalog_delete.py` (timeline giường đã xóa); `test_session_transfer.py::test_transfer_keeps_old_events_on_old_session`.
- `web/src/pages/Timeline/TimelinePage.tsx`: chọn giường (kể cả "Đã xóa", F03 R17)/phiên/khoảng/mức ưu tiên, dòng `{time} - {text}` từ `vi.ts`, tiêu đề ngày khi qua nhiều ngày, người tiếp nhận, kết quả, `AlertActions` (tự ẩn với DOCTOR), invalidation `timeline` khi có `event.created`/`alert.updated` (F18/F21); liên kết từ "Xem chi tiết" cảnh báo (`AlertDetailModal`). Test: chỉ `deletedBeds.test.tsx`.

**AC đã đạt một phần (chưa có test theo tên AC):** AC1 (gộp + thứ tự), AC3 (lọc, phía API), R6 (404, FAMILY 403). AC2, AC4 chưa có component test.

**Thiếu (sẽ làm):**
1. *Chuỗi phiên sau chuyển giường* (hộp 17/11; F04 R16): `GET /sessions/{id}/timeline?chain=true` gộp mọi phiên cùng chuỗi `previous_session_id` (dùng `session_chain` của F04). Mặc định `chain=false` để F36 dùng đúng một phiên được cấp *(giả định)*. UI luôn gửi `chain=true` khi xem theo phiên.
2. *Mục thao tác phiên* `kind = "session_action"` từ audit `session.transfer|pause|resume` (`entity_type = "session"`): "Chuyển từ giường A01 sang giường A02 (tên)", "Tạm dừng thu hình (tên)", "Tiếp tục thu hình (tên)" (F04 R16, F36 ghi chú). Theo giường: transfer hiện ở cả giường cũ và giường mới. Không có mức ưu tiên nên **luôn giữ** khi lọc mức ưu tiên *(giả định)*. `TimelineItemOut`: `event_id`, `code`, `priority` thành nullable; thêm `session_id`, `from_bed_code`; `action` mở rộng. Chạy `make gen-api-types`.
3. *Test server* `server/tests/api/test_timeline.py` theo tên AC: `test_session_timeline_merges_events_and_alert_actions_sorted`, `test_outcome_rewrite_shows_two_actions`, `test_alert_create_not_listed`, `test_same_time_ties_are_deterministic`, `test_bed_timeline_filters_by_time_range` (biên `from` gồm, `to` loại), `test_filter_by_priority_keeps_related_actions`, `test_bed_timeline_includes_camera_events_without_session`, `test_session_timeline_chain_after_transfer`, `test_pause_resume_and_transfer_entries`, `test_pagination`, `test_doctor_can_read_timeline`, `test_family_forbidden_timeline`, ca âm tính phiên khác không xuất hiện, 404.
4. *Component test* `web/src/pages/Timeline/TimelinePage.test.tsx`: `formats line as HH:mm:ss - text in Asia/Ho_Chi_Minh`, `does not render internal codes`, `sends filter params`, `shows acknowledger name`, `records outcome from timeline row`, `doctor sees no action buttons`, mục chuyển giường/tạm dừng, gửi `chain=true`.
5. *R7 truy cập từ thẻ giường:* thẻ giường mở "Theo dõi trực tiếp" (F21); thêm liên kết "Lịch sử theo dõi" trên trang đó tới `/timeline?bed=…&session=…`.
6. *Phân trang UI:* API trả `total`; khi `total > items.length` hiện nút "Xem thêm" (tăng `limit`… bằng `offset`) *(giả định)*.
7. Docs: `api-conventions.md` (tham số `chain`, `kind = session_action`), spec §10.

**Câu hỏi mở:** không có điểm chặn; các lựa chọn trên ghi là giả định.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-18 – triển khai (nhánh `feat/F22-timeline`), trạng thái In review.**

| AC | Bằng chứng |
|---|---|
| AC1 | `server/tests/api/test_timeline.py`: `test_session_timeline_merges_events_and_alert_actions_sorted` (actor, `event_code`, `alert` tóm tắt), `test_outcome_rewrite_shows_two_actions`, `test_alert_create_not_listed`, `test_other_session_not_listed`, `test_same_time_ties_are_deterministic` (trùng giờ: sự kiện trước, theo id, phân trang ổn định), `test_pagination`; `tests/test_timeline_handover.py::test_session_timeline_order` |
| AC2 | `web/src/pages/Timeline/TimelinePage.test.tsx`: `formats line as HH:mm:ss - text in Asia/Ho_Chi_Minh`, `does not render internal codes`, `shows session actions: pause, resume, transfer` |
| AC3 | `test_bed_timeline_filters_by_time_range` (biên `from` gồm, `to` loại, giường khác, `from >= to` → 400, thiếu `bed_id` → 422), `test_bed_timeline_defaults_to_last_24h`, `test_filter_by_priority_keeps_related_actions`, `test_bed_timeline_includes_camera_events_without_session`, `test_session_timeline_chain_after_transfer`, `test_pause_resume_and_transfer_entries`; web `sends filter params`, `loads more when total exceeds loaded items` |
| AC4 | web `shows acknowledger name and empty outcome text`, `records outcome from timeline row`, `doctor sees no action buttons`; server `test_doctor_can_read_timeline` |
| R6 | `test_family_forbidden_timeline`, `test_unknown_session_404`; `tests/api/test_family_role_default_deny.py` |
| R7 | Liên kết "Lịch sử theo dõi" trên "Theo dõi trực tiếp" (mở từ thẻ giường): `LiveViewPage links to the bed timeline (F22 R7)`; từ "Xem chi tiết" cảnh báo: `AlertDetailModal` (F20) |

Kiểm tra (2026-11-18): `make check` exit 0 (server 1269 passed, web 204 passed, build OK).

Thay đổi: `domain/timeline.py` (nhánh `UNION ALL` thứ ba cho audit phiên, `chain`), `TimelineItemOut` (`kind = session_action`, `event_id`/`code`/`priority` nullable, thêm `session_id`, `event_code`, `from_bed_code`), `make gen-api-types`; web `useTimeline` dùng `useInfiniteQuery`; `vi.timeline.transfer|pause|resume|reason|loadMore`; `api-conventions.md`. Sửa `test_session_transfer.py::test_transfer_keeps_old_events_on_old_session`: timeline phiên mới giờ có mục chuyển giường.

Điều người sau cần biết:
- F36: dùng `tl.session_timeline(..., chain=False)` và lọc thêm (bỏ tên nhân viên, `note`); mục tạm dừng/tiếp tục đã có ở timeline nhân viên.
- Không có migration.

**Review (2026-11-18): Đạt.** Đã sửa theo góp ý: (1) F04 §10 và F36 (R ghi chú, mục Câu hỏi/ghi chú) ghi mục tạm dừng/tiếp tục trên timeline nhân viên đã làm ở F22, F36 chỉ lọc cho người nhà; (2) quy tắc sắp khi trùng giờ ghi trong docstring `domain/timeline.py` và `api-conventions.md`; (3) `session_chain` có tập `seen` chặn chu trình `previous_session_id`, test `test_session_chain_stops_on_cycle`. Đã merge `main` vào nhánh. `make check` sau sửa: exit 0 (server 1269 passed, web 241 passed).

## 11. Definition of Done

- [x] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [x] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [x] Doc liên quan đã cập nhật cùng PR.
- [x] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
