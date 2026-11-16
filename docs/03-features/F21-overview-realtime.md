# F21 – Dashboard Tổng quan realtime

| Thuộc tính | Giá trị |
|---|---|
| Mã | F21 |
| Trạng thái | Todo |
| Ưu tiên | MVP |
| Milestone | M2 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F09, F18 |
| Nhánh code | B+C (cần mở rộng `GET /api/v1/overview`) |
| Nguồn | PDF §9.1 (tr.11), §16 (tr.17); HS §2.2, §4.3, Hình 3; A12 |

## 1. Mục tiêu

Người phụ trách ca cần nhìn một màn hình là biết giường nào cần ưu tiên (HS §2.2). Theo HS §4.3, dashboard tập trung vào ba nhóm thông tin:
- trạng thái từng giường;
- sự kiện đang cần chú ý;
- diễn biến gần đây.

Feature này nâng màn hình "Tổng quan" khung của F09 thành bản realtime theo phác thảo Hình 3 của HS. Mỗi thẻ giường hiện trạng thái *Đang theo dõi / Cần kiểm tra / Cảnh báo mới*, kèm trạng thái cơ thể, chất lượng quan sát, số cảnh báo đang chờ và mức ưu tiên cao nhất (PDF §9.1 (tr.11)). Dữ liệu cập nhật qua WebSocket (F18), không còn polling.

## 2. Phạm vi

**Trong phạm vi**
- Thẻ giường: trạng thái tổng hợp theo A12, trạng thái cơ thể, chất lượng quan sát, số cảnh báo chờ, mức ưu tiên cao nhất.
- Khối "Sự kiện cần chú ý" và khối "Diễn biến gần đây".
- Mở rộng `GET /api/v1/overview` (F09) với các trường cần cho thẻ.
- Bỏ polling của F09; chỉ refetch khi kết nối lại.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Màn hình Cảnh báo đầy đủ, âm thanh (→ F20). Timeline (→ F22). Bàn giao ca (→ F24).
- Trạng thái nghỉ/hoạt động trên thẻ (→ F27). Tín hiệu khuôn mặt (→ F26).
- Dashboard thống kê dài hạn (→ F34, sau MVP).

## 3. Yêu cầu chi tiết

- **R1.** Thẻ cho mọi giường đang dùng (đã có ở F09: mã giường, phiên, trạng thái camera, ca trực trên header) *(PDF §9.1 (tr.11); HS Hình 3)*.
- **R2.** Trạng thái tổng hợp của thẻ, ánh xạ theo **A12**, xét theo thứ tự:
  1. Có cảnh báo `PENDING` → **"Cảnh báo mới"**.
  2. Có cảnh báo `ACKNOWLEDGED` chưa xử lý, hoặc `body_state = NO_OBSERVATION` → **"Cần kiểm tra"**.
  3. Còn lại → **"Đang theo dõi"**.
  
  Giường không có phiên mở hiển thị "Không theo dõi" như F09 và không áp dụng ánh xạ trên *(giả định: A12 chỉ nói về giường đang theo dõi)*. Logic ánh xạ là một hàm thuần để test riêng *(HS Hình 3; A12)*.
- **R3.** Thẻ hiển thị *(PDF §9.1 (tr.11); HS §4.3 Hình 3)*:
  - trạng thái cơ thể hiện tại (nhãn 7 trạng thái theo glossary.md);
  - chất lượng quan sát;
  - số cảnh báo đang chờ (`PENDING`);
  - mức ưu tiên cao nhất trong các cảnh báo chưa xử lý.
  
  Màu thẻ theo trạng thái tổng hợp *(giả định)*.
- **R4.** Nhãn chất lượng quan sát (thêm vào `vi.ts` nếu F07 chưa có) *(giả định nội dung)*:
  - `GOOD`: "Quan sát tốt";
  - `LOW_CONFIDENCE`: "Độ tin cậy thấp";
  - `MULTIPLE_PEOPLE`: "Có nhiều người trong vùng giường";
  - `NO_PERSON`: "Không thấy người trong vùng giường";
  - `CAMERA_ISSUE`: "Sự cố camera".
- **R5.** Khối **"Sự kiện cần chú ý"**: các cảnh báo chưa xử lý (`PENDING`, `ACKNOWLEDGED`) của mọi giường, mới nhất trước. Mỗi dòng có giờ `HH:mm`, giường, câu mô tả, trạng thái *(HS §4.3, Hình 3: "14:38 - … ra khỏi vùng giường; Trạng thái: Chờ tiếp nhận / Đã tiếp nhận")*. Có nút **[Đã tiếp nhận]** dùng lại component của F20, và liên kết sang màn hình Cảnh báo *(giả định: Hình 3 vẽ luồng tiếp nhận ngay trên Tổng quan)*.
- **R6.** Khối **"Diễn biến gần đây"**: các sự kiện mới nhất (mọi mức ưu tiên) từ `GET /api/v1/events`, dạng "14:37 · Ngồi dậy" *(HS Hình 3)*. Giới hạn 10 dòng *(giả định: hằng số UI)*. Câu mô tả lấy từ `vi.ts`, không hiện mã nội bộ *(PDF §9.3 (tr.12))*.
- **R7.** Realtime *(HS §4.2; api-conventions.md)*:
  - `bed.state` cập nhật trạng thái cơ thể và chất lượng trên thẻ.
  - `alert.created` / `alert.updated` cập nhật trạng thái tổng hợp, số cảnh báo, khối "Sự kiện cần chú ý".
  - `event.created` cập nhật "Diễn biến gần đây".
  - `camera.status`, `session.updated` cập nhật thẻ.
  
  Mọi cập nhật chỉ đi qua cache TanStack Query *(coding-standards.md mục 3)*.
- **R8.** Bỏ polling ≤ 5 giây của F09. Chỉ refetch khi WebSocket kết nối lại (F18) *(giả định: WebSocket F18 thay cho polling)*.
- **R9.** `GET /api/v1/overview` trả thêm cho mỗi giường *(api-conventions.md: endpoint của F09, F21)*:
  - `pending_alert_count`, `acknowledged_alert_count`, `max_open_priority`;
  - `body_state`, `observation_quality`, `updated_at` (từ trạng thái trong RAM của F17).
  
  Số liệu cảnh báo tính bằng SQL `GROUP BY bed_id` *(giả định: cách tính)*.
- **R10.** Bấm thẻ → mở "Theo dõi trực tiếp" như F09. Layout dùng được ở ≥ 768px *(QA#26, giả định)*. Text trong `vi.ts`, qua test từ cấm *(ADR-0005)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `web/src/pages/Overview/OverviewPage.tsx` (F09), `BedCard.tsx`, `AttentionEvents.tsx`, `RecentActivity.tsx`, `bedCardStatus.ts` (hàm ánh xạ A12).
  - `web/src/realtime/invalidation.ts` (F18): thêm xử lý cho query overview, events.
  - Backend: `server/src/postcare/domain/overview.py`, `server/src/postcare/api/v1/overview.py` (F09) — thêm trường.
  - Test: `web/src/pages/Overview/bedCardStatus.test.ts`, `OverviewPage.test.tsx`; `server/tests/api/test_overview.py`.
- **Dữ liệu:** đọc `alerts`, `events`, `monitoring_sessions`, `cameras`, trạng thái giường trong RAM. Không có migration.
- **API:** `GET /api/v1/overview` (mở rộng), `GET /api/v1/events?limit=…`, `GET /api/v1/alerts?status=…` (F19). WS: `bed.state`, `alert.created`, `alert.updated`, `event.created`, `camera.status`, `session.updated`.
- **UI:** màn hình "Tổng quan". Text thêm vào `vi.ts`: "Đang theo dõi", "Cần kiểm tra", "Cảnh báo mới", "Sự kiện cần chú ý", "Diễn biến gần đây", "Cảnh báo đang chờ", nhãn chất lượng quan sát, nhãn 7 trạng thái cơ thể.
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [ ] **AC1.** Thẻ giường hiện một trong ba trạng thái *Đang theo dõi / Cần kiểm tra / Cảnh báo mới* theo quy tắc A12, kèm trạng thái cơ thể và chất lượng quan sát *(HS Hình 3; A12)*. — *Kiểm chứng:* `web/src/pages/Overview/bedCardStatus.test.ts` (`pending alert gives Cảnh báo mới`, `acknowledged open alert gives Cần kiểm tra`, `no observation gives Cần kiểm tra`, `otherwise Đang theo dõi`, `pending wins over acknowledged`); `OverviewPage.test.tsx::renders body state and observation quality`.
- [ ] **AC2.** Mỗi thẻ hiện số cảnh báo đang chờ và mức ưu tiên cao nhất của giường *(PDF §9.1 (tr.11))*. — *Kiểm chứng:* `server/tests/api/test_overview.py::test_overview_alert_counts_and_max_priority`; `OverviewPage.test.tsx::shows pending count and max priority`.
- [ ] **AC3.** Hai khối "Sự kiện cần chú ý" và "Diễn biến gần đây" cập nhật realtime, không hiện mã nội bộ *(HS §4.3, Hình 3)*. — *Kiểm chứng:* `OverviewPage.test.tsx` (`attention block updates on alert.created`, `recent activity updates on event.created`, `does not render internal codes`).
- [ ] **AC4.** Không còn polling; chỉ refetch khi WebSocket kết nối lại *(F18)*. — *Kiểm chứng:* `OverviewPage.test.tsx::no refetch interval` (fake timers: không có request mới sau 30 giây); `refetches after reconnect`.
- [ ] **AC5.** Màn hình "Theo dõi trực tiếp" (F07) hiển thị realtime **trạng thái cơ thể hiện tại, chất lượng quan sát và sự kiện gần nhất** của giường, cập nhật từ WS `bed.state` và `event.created` *(PDF §9.1 (tr.11))*. — *Kiểm chứng:* `LiveViewPage.test.tsx` (`shows body state from bed.state`, `shows observation quality label`, `shows latest event text from vi.ts`).

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit (hàm thuần) + component | Bảng đầu vào → kết quả ánh xạ | Giường không có phiên → "Không theo dõi", không phải "Đang theo dõi"; chỉ có cảnh báo `RESOLVED` → "Đang theo dõi" |
| AC2 | API + component | DB có cảnh báo nhiều mức, nhiều giường | Cảnh báo `RESOLVED` không được đếm |
| AC3 | component (WS giả) | Đẩy `alert.created`, `event.created`, `bed.state` | Sự kiện mức LOG xuất hiện ở "Diễn biến gần đây" nhưng không ở "Sự kiện cần chú ý" |
| AC4 | component (fake timers) | Không có `refetchInterval` | — |
| AC5 | component | `LiveViewPage.test.tsx`: trạng thái cơ thể, chất lượng, sự kiện gần nhất cập nhật theo WS | Không có `bed.state` → hiện "Không đủ dữ liệu quan sát", không hiện trạng thái cũ |
| R10 | unit | Test từ cấm của F20 bao phủ text mới | — |

## 7. Giả định

- *(giả định)* Giường không có phiên hiển thị "Không theo dõi" (R2).
- *(giả định)* Màu thẻ theo trạng thái tổng hợp (R3).
- *(giả định)* Nội dung nhãn chất lượng quan sát (R4).
- *(giả định)* Nút [Đã tiếp nhận] ngay trong khối "Sự kiện cần chú ý" (R5).
- *(giả định)* "Diễn biến gần đây" giới hạn 10 dòng (R6).
- *(giả định)* Số cảnh báo tính bằng SQL `GROUP BY` (R9).
- Quy tắc ánh xạ thẻ theo A12.

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
