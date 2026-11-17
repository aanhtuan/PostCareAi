# F09 – Dashboard khung (Tổng quan)

| Thuộc tính | Giá trị |
|---|---|
| Mã | F09 |
| Trạng thái | In progress <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F04, F06 |
| Nhánh code | B+C (tạo endpoint `GET /api/v1/overview`) |
| Nguồn | PDF §9.1 (tr.11); HS §2.2, §4.3, Hình 3; QA#13, QA#19, QA#26 |

## 1. Mục tiêu

Dựng màn hình "Tổng quan" (PDF §9.1) dạng nhiều thẻ giường, để người trực và phụ trách ca thấy ngay giường nào đang được theo dõi và camera nào đang hoạt động (HS §2.2). MVP chạy 1 giường nhưng dashboard được thiết kế cho nhiều giường (QA#13; HS §2.2). Header hiện ca trực hiện tại như phác thảo Hình 3 của HS (QA#19). Đây là bản khung; trạng thái cảnh báo và cập nhật realtime thêm ở F21.

## 2. Phạm vi

**Trong phạm vi**
- Endpoint `GET /api/v1/overview`: danh sách giường đang dùng kèm phiên và trạng thái camera, cộng ca trực hiện tại.
- Tính ca trực hiện tại từ `shift_definitions` theo giờ Asia/Ho_Chi_Minh, xử lý ca vắt qua nửa đêm.
- Màn hình "Tổng quan" tại `/`: header ca trực, lưới thẻ giường, bấm thẻ mở "Theo dõi trực tiếp".
- Làm mới bằng polling ≤5 giây.
- Thanh điều hướng giữa các màn hình đã có (Tổng quan, Quản lý giường…) *(giả định: F02 tạo khung, F09 bổ sung mục)*.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Ba trạng thái thẻ *Đang theo dõi / Cần kiểm tra / Cảnh báo mới*, trạng thái cơ thể, chất lượng quan sát (→ F21).
- Số cảnh báo đang chờ, mức ưu tiên cao nhất (→ F21; PDF §9.1).
- Khối "Sự kiện cần chú ý" và "Diễn biến gần đây" (→ F21).
- WebSocket, bỏ polling (→ F18, F21).
- Sửa ca trực trên UI *(QA#19: cấu hình trong DB; không có yêu cầu UI)*.

## 3. Yêu cầu chi tiết

- **R1.** `GET /api/v1/overview` → *(api-conventions.md)*:
  - `current_shift: {id, name, start_time, end_time} | null`;
  - `beds: [{bed_id, code, area, session: {id, patient_code, started_at} | null, camera: {id, name, status} | null}]`, sắp theo `code`.
  - Chỉ giường `is_active = true`. Mọi vai trò đã đăng nhập được xem *(api-conventions.md, bảng phân quyền)*.
- **R2.** Ca trực hiện tại là ca có `start_time ≤ giờ hiện tại < end_time` theo Asia/Ho_Chi_Minh; ca có `end_time ≤ start_time` vắt qua nửa đêm *(QA#19; data-model.md shift_definitions)*. Hàm tính ca nhận thời điểm làm tham số để test được *(giả định)*. Không khớp ca nào → `null`.
- **R3.** Header hiện "Ca trực: HH:mm–HH:mm" (ví dụ "Ca trực: 14:00–22:00") *(HS Hình 3; QA#19)*; không có ca → "Ca trực: —".
- **R4.** Thẻ giường hiện *(PDF §9.1)*:
  - mã giường (ví dụ "Giường A01");
  - phiên: "Đang theo dõi" kèm mã bệnh nhân, hoặc "Không theo dõi";
  - trạng thái camera: "Camera hoạt động" / "Mất kết nối camera" / "Chưa rõ trạng thái" / "Chưa gắn camera".
- **R5.** Bấm thẻ → mở `/beds/:bedId/live` (F07) *(PDF §9.1 (tr.11))*. Thẻ dùng được bằng bàn phím (Enter) *(giả định)*.
- **R6.** Làm mới bằng polling `GET /api/v1/overview` mỗi 5 giây (TanStack Query `refetchInterval`) *(F21 thay bằng realtime)*.
- **R7.** Layout dùng được ở màn hình ≥768px: lưới thẻ tự xuống dòng; ở 768px hiện ít nhất 2 thẻ mỗi hàng *(QA#26; giả định số cột)*.
- **R8.** Text giao diện nằm trong `web/src/i18n/vi.ts`; không hiện mã nội bộ *(ADR-0005; glossary.md)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/v1/overview.py`; `server/src/postcare/domain/overview.py`; `server/src/postcare/domain/shifts.py` (`current_shift(now)`).
  - Schema: `OverviewOut`, `BedCardOut`, `ShiftOut`.
  - `server/tests/domain/test_shifts.py`, `server/tests/api/test_overview.py`.
  - `web/src/pages/Overview/OverviewPage.tsx`, `BedCard.tsx`, `web/src/components/ShiftBadge.tsx`.
  - `web/src/pages/Overview/OverviewPage.test.tsx`, `BedCard.test.tsx`.
- **Dữ liệu:** đọc `beds`, `cameras`, `monitoring_sessions`, `patients`, `shift_definitions` (xem [data-model.md](../02-architecture/data-model.md)). Không có migration mới.
- **API:** `GET /api/v1/overview` (xem [api-conventions.md](../02-architecture/api-conventions.md#danh-sách-endpoint-dự-kiến)). Chạy `make gen-api-types`.
- **UI:** màn hình "Tổng quan". Text cần thêm vào `vi.ts`: `overview.title` ("Tổng quan"), `shift.label` ("Ca trực: {start}–{end}"), `shift.none` ("Ca trực: —"), `bed.title` ("Giường {code}"), `session.active` ("Đang theo dõi"), `session.none` ("Không theo dõi"), các nhãn trạng thái camera (dùng lại từ F07), `nav.overview`, `nav.management`.
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [ ] **AC1.** Màn hình "Tổng quan" có thẻ cho mọi giường đang dùng: mã giường, phiên (Đang theo dõi / Không theo dõi), trạng thái camera. *(PDF §9.1; QA#13)* — *Kiểm chứng:* API test `test_overview_lists_active_beds_with_session_and_camera`; component test `OverviewPage renders a card per bed`, `BedCard shows session and camera labels`.
- [ ] **AC2.** Header hiện ca trực hiện tại (ví dụ "Ca trực: 14:00–22:00"), tính đúng cả ca vắt qua nửa đêm. *(HS Hình 3; QA#19)* — *Kiểm chứng:* unit test `test_current_shift` tham số hóa (06:00 → Ca sáng, 13:59 → Ca sáng, 14:00 → Ca chiều, 23:30 → Ca đêm, 05:59 → Ca đêm); component test `header shows current shift`.
- [ ] **AC3.** Bấm thẻ giường → mở màn hình "Theo dõi trực tiếp" của giường đó. *(PDF §9.1 (tr.11))* — *Kiểm chứng:* component test `clicking a bed card navigates to live view`.
- [ ] **AC4.** Dữ liệu làm mới bằng polling ≤5 giây; layout dùng được ở chiều rộng ≥768px. *(QA#26)* — *Kiểm chứng:* component test `OverviewPage refetches within 5 s` (fake timers + msw đổi dữ liệu); kiểm tra tay ở 768px và 1366px, ghi vào mục 10.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API + component | `test_overview_lists_active_beds_with_session_and_camera`; `OverviewPage.test.tsx` | Giường ngừng dùng không xuất hiện; giường không có camera → "Chưa gắn camera" |
| AC2 | unit + component | `test_current_shift` (tham số hóa biên ca) | Không có ca nào trong DB → `null` → "Ca trực: —" |
| AC3 | component | `clicking a bed card navigates to live view` | — |
| AC4 | component + thủ công | `OverviewPage refetches within 5 s`; xem ở 768px | API lỗi tạm thời → giữ dữ liệu cũ, không trắng màn hình *(giả định)* |

## 7. Giả định

- *(giả định)* Định dạng dữ liệu trả về của `GET /api/v1/overview` ở R1; F21 mở rộng thêm trường.
- *(giả định)* Hàm tính ca nhận thời điểm làm tham số; ranh giới `start_time ≤ t < end_time`.
- *(giả định)* Ở 768px hiện ít nhất 2 thẻ mỗi hàng.
- *(giả định)* API lỗi tạm thời thì giữ dữ liệu cũ (hành vi mặc định của TanStack Query).
- *(giả định)* F09 bổ sung mục điều hướng vào khung ứng dụng của F02.
- *(giả định)* Thẻ của phiên đang tạm dừng thu hình hiện "Đang tạm dừng thu hình" thay cho "Đang theo dõi"/"Cần kiểm tra" và không hiện trạng thái cơ thể cũ; cảnh báo đang chờ vẫn hiện "Cảnh báo mới" (ghi chú F21; F04 R19–R22; PRD US07).
- *(giả định)* `OverviewSessionOut` có thêm `paused_at` (null = không tạm dừng).

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

> Lập 18/11/2026. Prototype đã có sẵn phần lớn màn hình (làm cùng F21/F37); F09 kiểm lại từng AC với code + test và chỉ lấp chỗ thiếu.

**Đã có (bằng chứng trong code hiện tại)**

| Yêu cầu | Đã có | Bằng chứng |
|---|---|---|
| R1 endpoint | `GET /api/v1/overview` (`server/src/postcare/api/v1/monitoring.py`, `domain/overview.py`), chỉ giường `is_active`, sắp theo `code`, `area` là tên khu vực (F37), `camera {id,name,status}`, `current_shift`; router `require_staff` | `test_overview_alert_counts_and_max_priority` (test_timeline_handover.py); `test_family_role_default_deny.py` (FAMILY 403); `test_auth.py` (401) |
| R2 ca hiện tại | `domain/shifts.py::current_shift(now, shifts)` nhận thời điểm, xử lý ca qua đêm, bỏ ca đã xóa (F37) | `test_current_shift` tham số hóa (06:00, 13:59, 14:00, 21:59, 23:30, 05:59; danh sách rỗng → `None`); `test_current_shift_ignores_deleted` |
| R3 header | `OverviewPage.tsx::shiftLabel` | `header shows current shift` |
| R4 thẻ | `BedCard.tsx`: "Giường {code}", mã bệnh nhân, nhãn camera (`vi.cameraStatus`, `vi.camera.notAssigned`), trạng thái A12 (`bedCardStatus.ts`, F21) | `bedCardStatus.test.ts`; `renders a card per bed with A12 status…` |
| R5 bấm thẻ | `navigate('/beds/:id/live')`, `role=button`, Enter | **chưa có test** |
| R6 polling | — | **thiếu**: `useOverview` không có `refetchInterval` (chỉ có invalidation WebSocket) |
| R7 layout | `SimpleGrid cols={{base:1, xs:2, lg:3}}` (≥576px: 2 cột) | kiểm tra tay |
| R8 text | `vi.ts` (`overview`, `bedCard`, `shift`, `cameraStatus`) | test kiểm tra không có mã nội bộ trong DOM |

**Chỗ thiếu sẽ làm**

1. API: thêm `paused_at` vào `OverviewSessionOut` để thẻ hiện "Đang tạm dừng thu hình" (ghi chú F21, F04 R19–R22) *(giả định: chỉ thêm trường, không đổi trường cũ)*. Test mới `server/tests/api/test_overview.py`:
   - `test_overview_lists_active_beds_with_session_and_camera` (giường ngừng dùng không xuất hiện; giường không camera → `camera: null`; `camera.status` theo DB; sắp theo `code`; `area` là chuỗi);
   - `test_overview_current_shift_shape` (`{id, name, start_time, end_time}`); `test_overview_no_shift_is_null` (ca đều đã xóa → `null`);
   - `test_overview_session_paused_at` (tạm dừng → `paused_at` khác null; tiếp tục → null);
   - `test_overview_requires_staff` (FAMILY 403, chưa đăng nhập 401, mọi vai trò nhân viên 200).
   `make gen-api-types`.
2. Web, test trước (`BedCard.test.tsx`, `OverviewPage.test.tsx`, `bedCardStatus.test.ts`):
   - `BedCard shows session and camera labels`: "Đang theo dõi" + mã bệnh nhân; "Không theo dõi"; "Camera hoạt động" / "Mất kết nối camera" / "Chưa rõ trạng thái camera" / "Chưa gắn camera";
   - không đủ dữ liệu quan sát → "Cần kiểm tra"; tạm dừng → "Đang tạm dừng thu hình", không hiện trạng thái cơ thể cũ;
   - `clicking a bed card navigates to live view` (click và Enter);
   - `header shows no shift` → "Ca trực: —"; `shows empty state when no beds`;
   - `OverviewPage refetches within 5 s` (fake timers, đổi dữ liệu mock).
3. Web, cài đặt: `OVERVIEW_POLL_MS = 5000` + `refetchInterval` trong `useOverview`; `bedCardStatus` thêm `paused` → `PAUSED` (sau `NEW_ALERT`: cảnh báo chờ vẫn ưu tiên) *(giả định)*; nhãn `vi.bedCard.PAUSED`; `vi.overview.noBeds`. Không thêm thư viện, không migration.
4. Doc: `api-conventions.md` (dòng `/overview`: hình dạng + `paused_at`), spec §7/§10.
5. `make check`, `scripts\dev.ps1 check`; chạy tay DB `postcare_f09`, seed, API cổng 8019, curl `/api/v1/overview` (nurse 200, family 403, tạm dừng → `paused_at`).

Rủi ro: fake timers + TanStack Query dễ treo → dùng `vi.useFakeTimers({ shouldAdvanceTime: true })`.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
