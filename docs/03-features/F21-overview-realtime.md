# F21 – Dashboard Tổng quan realtime

| Thuộc tính | Giá trị |
|---|---|
| Mã | F21 |
| Trạng thái | Done |
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

Feature này nâng màn hình "Tổng quan" khung của F09 thành bản realtime theo phác thảo Hình 3 của HS. Mỗi thẻ giường hiện trạng thái *Đang theo dõi / Cần kiểm tra / Cảnh báo mới*, kèm trạng thái cơ thể, chất lượng quan sát, số cảnh báo đang chờ và mức ưu tiên cao nhất (PDF §9.1 (tr.11)). Dữ liệu cập nhật qua WebSocket (F18); polling chỉ còn là đường dự phòng khi WebSocket không mở.

> **Liên quan F04/F36 (bổ sung 17/11/2026):** thẻ giường cần hiển thị trạng thái "tạm dừng thu hình" của phiên ([F04](F04-monitoring-sessions.md)) để người xem hiểu lý do không có dữ liệu. Tài khoản `FAMILY` không vào được Tổng quan ([F35](F35-user-management.md) `require_staff`).

## 2. Phạm vi

**Trong phạm vi**
- Thẻ giường: trạng thái tổng hợp theo A12, trạng thái cơ thể, chất lượng quan sát, số cảnh báo chờ, mức ưu tiên cao nhất.
- Khối "Sự kiện cần chú ý" và khối "Diễn biến gần đây".
- Mở rộng `GET /api/v1/overview` (F09) với các trường cần cho thẻ.
- Khi WebSocket mở thì không polling; polling 5 giây của F09 chỉ chạy khi WebSocket không mở; refetch khi kết nối lại.

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
- **R8.** Khi WebSocket mở: không polling, chỉ cập nhật theo message và refetch khi WebSocket kết nối lại (F18). Khi WebSocket không mở (đang kết nối / đang kết nối lại): giữ polling ≤ 5 giây của F09 để dữ liệu vẫn mới *(F09 R6; quyết định điều phối 18/11/2026)*.
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

- [x] **AC1.** Thẻ giường hiện một trong ba trạng thái *Đang theo dõi / Cần kiểm tra / Cảnh báo mới* theo quy tắc A12, kèm trạng thái cơ thể và chất lượng quan sát *(HS Hình 3; A12)*. — *Kiểm chứng:* `web/src/pages/Overview/bedCardStatus.test.ts` (`pending alert gives Cảnh báo mới`, `acknowledged open alert gives Cần kiểm tra`, `no observation gives Cần kiểm tra`, `otherwise Đang theo dõi`, `pending wins over acknowledged`); `OverviewPage.test.tsx::renders body state and observation quality`.
- [x] **AC2.** Mỗi thẻ hiện số cảnh báo đang chờ và mức ưu tiên cao nhất của giường *(PDF §9.1 (tr.11))*. — *Kiểm chứng:* `server/tests/api/test_overview.py::test_overview_alert_counts_and_max_priority`; `OverviewPage.test.tsx::shows pending count and max priority`.
- [x] **AC3.** Hai khối "Sự kiện cần chú ý" và "Diễn biến gần đây" cập nhật realtime, không hiện mã nội bộ *(HS §4.3, Hình 3)*. — *Kiểm chứng:* `OverviewPage.test.tsx` (`attention block updates on alert.created`, `recent activity updates on event.created`, `does not render internal codes`).
- [x] **AC4.** Khi WebSocket mở thì không polling; refetch khi WebSocket kết nối lại; khi WebSocket không mở thì polling 5 giây làm dự phòng *(F18; F09 R6)*. — *Kiểm chứng:* `OverviewPage.test.tsx::no refetch interval while WebSocket open` (fake timers: không có request mới sau 30 giây), `polls as fallback while WebSocket disconnected`, `refetches after reconnect` (qua `RealtimeProvider` → `onReconnected`).
- [x] **AC5.** Màn hình "Theo dõi trực tiếp" (F07) hiển thị realtime **trạng thái cơ thể hiện tại, chất lượng quan sát và sự kiện gần nhất** của giường, cập nhật từ WS `bed.state` và `event.created` *(PDF §9.1 (tr.11))*. — *Kiểm chứng:* `LiveViewPage.test.tsx` (`shows body state from bed.state`, `shows observation quality label`, `shows latest event text from vi.ts`).

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
- Polling 5 s chỉ còn là đường dự phòng khi WebSocket không mở (R8; F09 R6; quyết định điều phối 18/11/2026).
- *(giả định, 18/11)* Invalidate từ WebSocket được gộp trong 200 ms (hằng số UI) để chuỗi message liên tiếp chỉ gây một lần refetch mỗi query; vẫn trong mục tiêu ≤ 1–2 s.

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

> Lập 18/11/2026. Prototype đã có phần lớn màn hình (làm cùng F09/F18/F37). F21 kiểm lại từng AC với code + test, chỉ lấp chỗ thiếu.

**Đã đáp ứng (bằng chứng hiện có):**

| Mục | Code | Test |
|---|---|---|
| R2/AC1 ánh xạ A12 (kèm tạm dừng thu hình, camera mất kết nối) | `web/src/pages/Overview/bedCardStatus.ts` | `bedCardStatus.test.ts`; `OverviewPage.test.tsx::renders a card per bed with A12 status…`; `BedCard.test.tsx` |
| R3/R4 trạng thái cơ thể, chất lượng, số chờ, ưu tiên cao nhất | `BedCard.tsx`, `vi.quality`, `vi.bodyState` | `BedCard.test.tsx`, `OverviewPage.test.tsx` |
| R5/R6 hai khối, nút [Đã tiếp nhận], không hiện mã | `OverviewPage.tsx` (`AttentionEvents`, `RecentActivity`, `AlertActions`) | `OverviewPage.test.tsx::shows attention and recent activity blocks…`, `doctor sees no action buttons` |
| R9 trường mở rộng của `GET /overview` (SQL `GROUP BY`) | `server/src/postcare/domain/overview.py` | `test_timeline_handover.py`, `test_realtime_seed.py` (chưa có trong `test_overview.py`) |
| R7 `bed.state`/`camera.status` → `setQueryData`; còn lại → invalidate | `web/src/realtime/invalidation.ts` | `invalidation.test.ts` |
| Ghi chú 17/11: thẻ "tạm dừng thu hình"; FAMILY không vào Tổng quan | `bedCardStatus.ts` (`PAUSED`), `App.tsx::Protected` | `bedCardStatus.test.ts`, `App.test.tsx`, `test_overview_requires_staff` |

**Còn thiếu → bước làm:**

1. Test trước (commit `test(F21): …`):
   - `test_overview.py::test_overview_alert_counts_and_max_priority` (ca âm: `RESOLVED` không đếm).
   - `invalidation.test.ts`: `alert.created bumps the bed card immediately`; `bursts of messages coalesce into one invalidation per key` (không "bão refetch").
   - `alertNotifier.test.ts`: `HIGH alert shows toast and sound once`, `MEDIUM alert toast without sound`, `duplicate alert.created is ignored`.
   - `OverviewPage.test.tsx`: `card updates from bed.state without refetch`, `attention block updates on alert.created`, `recent activity updates on event.created` (ca âm: sự kiện LOG không vào khối chú ý), `no refetch interval while WebSocket open` (fake timers 30 s), `polls as fallback while WebSocket disconnected`, `refetches after reconnect`, `does not render internal codes`.
   - `LiveViewPage.test.tsx`: `shows body state from bed.state`, `shows observation quality label`, `shows latest event text from vi.ts`, `no bed.state shows Không đủ dữ liệu quan sát`, `no polling while WebSocket open`.
   - Hạ tầng test: `renderWithProviders` nhận `{ ws, qc }` để giả trạng thái WebSocket và đẩy message qua `applyMessage`.
2. `web/src/realtime/useRealtimeStatus.ts` (đọc `RealtimeContext`). `useOverview`/`useCameraDetail` chỉ polling khi WebSocket không ở trạng thái `open`; bỏ `useLiveOverview`, LiveView dùng chung `useOverview`.
3. `invalidation.ts`: gộp invalidate theo khóa trong cửa sổ ngắn (`INVALIDATE_COALESCE_MS = 200`, hằng số UI) để chuỗi message không gây bão refetch; `alert.created` cập nhật ngay thẻ (`pending_alert_count`, `max_open_priority`) bằng `setQueryData`.
4. `web/src/realtime/alertNotifier.ts`: toast cho mỗi `alert.created` đúng một lần theo `alert.id`; âm thanh chỉ khi `HIGH` (QA#17). `RealtimeProvider` dùng notifier này.
5. Doc: F21 §10, `api-conventions.md` (mục WebSocket: gộp invalidate, polling dự phòng), `coding-standards.md` nếu cần.
6. `make check` một lần; kiểm chứng thủ công: DB `postcare_f21`, API :8021, web :5181, `postcare simulate --bed A01`.

Không có migration, không đổi OpenAPI, không thêm thư viện.

## 10. Ghi chú bàn giao

**18/11/2026 — Done.** Nhánh `feat/F21-overview-realtime`.

**Bằng chứng theo AC:**

| AC | Test |
|---|---|
| AC1 | `bedCardStatus.test.ts` (F09/F21, có ca tạm dừng, camera mất kết nối); `OverviewPage.test.tsx::renders body state and observation quality`, `card updates from bed.state without refetch` (không gọi lại `/overview`) |
| AC2 | `test_timeline_handover.py::test_overview_alert_counts_and_max_priority`; ca âm mới `server/tests/api/test_overview.py::test_overview_resolved_alerts_not_counted`; `OverviewPage.test.tsx::shows pending count and max priority`, `card turns to Cảnh báo mới immediately on alert.created`; `invalidation.test.ts::alert.created bumps the bed card immediately` |
| AC3 | `OverviewPage.test.tsx::attention block updates on alert.created`, `recent activity updates on event.created` (ca âm: sự kiện LOG không vào khối chú ý), `does not render internal codes` |
| AC4 | `OverviewPage.test.tsx::no refetch interval while WebSocket open` (fake timers 30 s, không request mới), `polls as fallback while WebSocket disconnected`, `refetches after reconnect`; `invalidation.test.ts::bursts of messages coalesce into one invalidation per key` |
| AC5 | `LiveViewPage.test.tsx` (`shows body state from bed.state`, `shows observation quality label`, `shows latest event text from vi.ts`, `no bed.state shows Không đủ dữ liệu quan sát`, `no polling while WebSocket open`) |
| Toast/âm thanh | `alertNotifier.test.ts` (`HIGH alert shows toast and sound once`, `MEDIUM alert toast without sound`, `duplicate alert.created is ignored`) |

**Thay đổi chính:**
- `web/src/realtime/status.ts`: `RealtimeContext`, `useRealtimeStatus`, `fallbackInterval`. `useOverview` và `useCameraDetail` chỉ polling khi WebSocket không mở; bỏ `useLiveOverview` (LiveView dùng chung `useOverview`, nên polling dự phòng của LiveView là 5 s thay vì 2 s; chi tiết camera vẫn 2 s).
- `web/src/realtime/invalidation.ts`: invalidate gộp 200 ms (`INVALIDATE_COALESCE_MS`, `flushInvalidations`); `alert.created` tăng `pending_alert_count`, nâng `max_open_priority` của thẻ ngay bằng `setQueryData`; kết nối lại hủy hàng chờ rồi invalidate toàn bộ.
- `web/src/realtime/alertNotifier.ts`: toast một lần mỗi `alert.id` (id notification `alert-<id>`), âm thanh chỉ `HIGH`; `RealtimeProvider` giữ một notifier suốt vòng đời.
- `web/src/test/render.tsx`: `renderWithProviders(..., { ws, qc })`, `testQueryClient()`.
- Doc: `api-conventions.md` mục WebSocket.

**`make check`:** xanh (1096 pytest, 163 vitest, lint-imports 10 kept, build web).

**Kiểm chứng thủ công (18/11/2026):** DB `postcare_f21` (migrate + `postcare seed`, thêm bệnh nhân BN-001 và mở phiên A01 qua API), API cổng 8021, Vite cổng 5181 (`VITE_API_TARGET=http://127.0.0.1:8021`), `postcare simulate --bed A01 --scenario bed-exit --speed 2 --away 4`.
- Probe WebSocket qua proxy Vite: 9 `bed.state` trễ tối đa 2 ms, `alert.created` tối đa 16 ms, `event.created` tối đa 22 ms; `GET /overview` ngay sau mỗi `bed.state` khớp trạng thái, `pending_alert_count` tăng 0 → 1 → 2 theo BED_EDGE/BED_EXIT.
- Trình duyệt (đăng nhập `nurse`, Tổng quan): theo dõi chữ trên thẻ A01 mỗi 50 ms; thẻ đổi Nằm → Đang nâng thân → Ngồi → Ở mép giường → Đứng → Ngoài giường → Ngồi → Nằm trong vòng < 1 s sau mỗi bước của simulator; khi hết heartbeat chuyển "Không đủ dữ liệu quan sát / Sự cố camera". Trong ~40 s chỉ có 4 request `/overview` (lần tải đầu + refetch gộp do `alert.*`/`session.updated`), không có chu kỳ 5 s. Không thấy mã nội bộ trên trang.

**Review (18/11/2026): Cần sửa (nhỏ) → đã sửa, Đạt.**
1. `web/tsconfig.tsbuildinfo` lỡ commit: bỏ theo dõi (`*.tsbuildinfo` đã có trong `.gitignore` từ main).
2. R8/AC4 viết lại theo hành vi polling dự phòng (F09 R6; quyết định điều phối).
3. `bed.state` cũ hơn `updated_at` đang giữ bị bỏ qua; kết quả refetch `/overview` cũ hơn cũng không ghi đè (`keepNewerStates` trong `useOverview`). Test: `invalidation.test.ts::bed.state older than the cached state is ignored`, `OverviewPage.test.tsx::refetch result older than a bed.state already applied is ignored`.
4. `alert.created` lặp lại cùng `alert.id` chỉ tăng số trên thẻ một lần. Test: `invalidation.test.ts::repeated alert.created for the same alert bumps the card once`.
5. `refetches after reconnect` đi qua `RealtimeProvider` thật (RealtimeClient giả, gọi `onReconnected`).

**Người sau cần biết:** chưa kiểm chứng toast/âm thanh trên trình duyệt thật (chỉ unit test; trình duyệt có thể chặn âm thanh trước thao tác đầu tiên). `postcare seed` (không `--reset`) không tạo bệnh nhân và phiên mẫu; dùng `make seed` hoặc mở phiên thủ công.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
