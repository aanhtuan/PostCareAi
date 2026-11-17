# F22 – Timeline / Lịch sử theo dõi

| Thuộc tính | Giá trị |
|---|---|
| Mã | F22 |
| Trạng thái | Todo |
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

- [ ] **AC1.** API timeline của phiên trả cả sự kiện và thao tác cảnh báo (tiếp nhận, ghi kết quả, xử lý), sắp theo thời gian tăng dần *(PDF §9.3 (tr.12); HS §6.2; ADR-0007)*. — *Kiểm chứng:* `server/tests/api/test_timeline.py` (`test_session_timeline_merges_events_and_alert_actions_sorted`, `test_outcome_rewrite_shows_two_actions`, `test_alert_create_not_listed`).
- [ ] **AC2.** Hiển thị dạng "14:38:12 - Bệnh nhân ngồi dậy" theo giờ Asia/Ho_Chi_Minh; không hiện mã nội bộ *(PDF §9.3 (tr.12))*. — *Kiểm chứng:* `web/src/pages/Timeline/TimelinePage.test.tsx` (`formats line as HH:mm:ss - text in Asia/Ho_Chi_Minh`, `does not render internal codes`).
- [ ] **AC3.** Lọc theo giường, phiên, khoảng thời gian, mức ưu tiên *(PDF §9.1 (tr.11); HS Hình 3)*. — *Kiểm chứng:* `test_timeline.py` (`test_bed_timeline_filters_by_time_range`, `test_filter_by_priority_keeps_related_actions`, `test_bed_timeline_includes_camera_events_without_session`); `TimelinePage.test.tsx::sends filter params`.
- [ ] **AC4.** Xem người tiếp nhận và ghi kết quả kiểm tra ngay từ timeline; DOCTOR chỉ xem *(HS Hình 3; QA#18)*. — *Kiểm chứng:* `TimelinePage.test.tsx` (`shows acknowledger name`, `records outcome from timeline row`, `doctor sees no action buttons`).

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

## 8. Câu hỏi mở

- (Không)

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
