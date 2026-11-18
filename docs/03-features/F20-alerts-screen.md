# F20 – Màn hình Cảnh báo

| Thuộc tính | Giá trị |
|---|---|
| Mã | F20 |
| Trạng thái | Done |
| Ưu tiên | MVP |
| Milestone | M2 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F18, F19 |
| Nhánh code | C (frontend/test) |
| Nguồn | PDF §9 (tr.11), §9.1–9.2 (tr.11), §17 (tr.18); HS §4.2, §4.3, Hình 3; QA#17; ADR-0007 |

## 1. Mục tiêu

Điều dưỡng cần biết ngay giường nào có cảnh báo, mức ưu tiên ra sao, đã có ai tiếp nhận chưa, và thao tác được trong vài lần bấm (PDF §3 (tr.4); HS §2.2). Feature này làm màn hình "Cảnh báo" tiếng Việt (PDF §9.1 (tr.11)):
- Danh sách có lọc. Cảnh báo chưa xử lý nằm đầu.
- Đúng bộ nút của PDF §9.2 (tr.11).
- Cập nhật realtime qua F18.
- Câu chữ mô tả điều quan sát được, không dùng từ cấm (PDF §9.2 (tr.11); HS §4.3).

## 2. Phạm vi

**Trong phạm vi**
- Trang `web/src/pages/Alerts/`: danh sách, bộ lọc, thẻ cảnh báo, khung "Xem chi tiết".
- Nút thao tác gọi API của F19.
- Cập nhật realtime (dùng client F18). Âm thanh và màu nổi bật cho mức Ưu tiên cao.
- Text trong `web/src/i18n/vi.ts`. Test quét từ cấm và test đủ text cho các enum.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- API vòng đời cảnh báo (→ F19). WebSocket gateway (→ F18).
- Khối "Sự kiện cần chú ý" trên Tổng quan (→ F21). Timeline (→ F22).
- Chuyển tiếp, thông báo di động (→ F32, F33, sau MVP).
- Video hay ảnh minh chứng trong chi tiết cảnh báo *(QA#29: không lưu ảnh)*.

## 3. Yêu cầu chi tiết

- **R1.** Danh sách theo thời gian, giường, mức ưu tiên, trạng thái xử lý *(PDF §9.1 (tr.11))*:
  - Lọc theo trạng thái, giường, mức ưu tiên, khoảng thời gian. Lọc chạy phía server qua `GET /api/v1/alerts` (F19).
  - Thứ tự mặc định do API trả: chưa xử lý trước *(F19 R9)*.
- **R2.** Mỗi thẻ cảnh báo hiển thị *(PDF §9.2 (tr.11), ví dụ cảnh báo)*:
  - dòng tiêu đề "Giường A03 - Cảnh báo ưu tiên cao" (hoặc "… - Cảnh báo cần chú ý");
  - câu mô tả từ `vi.ts` kèm giờ `HH:mm:ss` (Asia/Ho_Chi_Minh), ví dụ "Phát hiện bệnh nhân rời khỏi vùng giường lúc 14:38:34.";
  - trạng thái (Chờ tiếp nhận / Đã tiếp nhận / Đã xử lý), người tiếp nhận nếu có, kết quả kiểm tra.
  
  **Không** hiển thị mã nội bộ (`BED_EXIT`…) *(PDF §9.3 (tr.12); glossary.md)*.
- **R3.** Nút đúng PDF §9.2 (tr.11) và ADR-0007:
  - Trạng thái `PENDING`: **[Đã tiếp nhận]** **[Xem chi tiết]**.
  - Trạng thái `ACKNOWLEDGED`: **[Xác nhận đúng]** **[Cảnh báo sai]** **[Bệnh nhân an toàn]** **[Đã xử lý]**, kèm ô ghi chú và **[Xem chi tiết]**. Ba nút kết quả gọi `POST …/outcome`; nút đang được chọn có dấu hiệu rõ, bấm nút khác thì ghi đè. "Đã xử lý" gọi `POST …/resolve`.
  - Trạng thái `RESOLVED`: chỉ **[Xem chi tiết]**. Kết quả `null` hiển thị "Chưa ghi kết quả" *(ADR-0007)*.
- **R4.** "Xem chi tiết" mở khung chi tiết gồm *(PDF §5 (tr.6): truy vết ai tiếp nhận, kết quả, xử lý khi nào; HS §6.2)*:
  - thời điểm sự kiện, giường, mã bệnh nhân của phiên, mức ưu tiên, chất lượng quan sát;
  - người và thời điểm của từng thao tác; kết quả; ghi chú;
  - liên kết sang "Theo dõi trực tiếp" (F07) và "Lịch sử theo dõi" (F22).
  
  Không hiển thị `rule_id` hay giá trị kỹ thuật *(giả định: tránh thuật ngữ kỹ thuật, PDF §9 (tr.11))*.
- **R5.** Cảnh báo mới tự hiện, thay đổi trạng thái tự cập nhật, không cần tải lại trang. Nhận `alert.created`/`alert.updated` (F18) thì làm mới cache của danh sách *(PDF §9.1 (tr.11); HS §4.2; coding-standards.md mục 3)*.
- **R6.** Mức Ưu tiên cao có màu nổi bật. Khi nhận `alert.created` mức HIGH thì phát âm thanh trên trình duyệt *(QA#17, giả định)*. Âm thanh tạo bằng Web Audio API, không cần file media *(giả định: không commit media, coding-standards.md mục 1)*. Trình duyệt chặn tự phát âm thanh trước khi người dùng tương tác với trang; trường hợp này chấp nhận được *(giả định)*.
- **R7.** Phân quyền trên UI *(QA#18; api-conventions.md)*:
  - DOCTOR không thấy nút thao tác, chỉ thấy "Xem chi tiết".
  - Lỗi 409 (ví dụ đã có người khác tiếp nhận): hiển thị `message` tiếng Việt từ API rồi làm mới thẻ.
  - Lỗi 403: hiển thị thông báo không đủ quyền.
- **R8.** Mọi text nằm trong `web/src/i18n/vi.ts` *(ADR-0005; coding-standards.md mục 1)*. `vi.ts` có đủ text cho mọi `EventCode`, `Priority`, `AlertStatus`, `AlertOutcome` *(testing.md mục 4)*. Nhãn theo [glossary.md](../01-product/glossary.md): Nhật ký / Thông tin / Cần chú ý / Ưu tiên cao; Chờ tiếp nhận / Đã tiếp nhận / Đã xử lý; Xác nhận đúng / Cảnh báo sai / Bệnh nhân an toàn / Chưa ghi kết quả.
- **R9.** Test từ cấm `web/src/i18n/vi.test.ts` quét toàn bộ giá trị trong `vi.ts` theo danh sách của glossary.md *(PDF §9.2 (tr.11), §17 (tr.18); HS §4.3, §9.1)*. Tạo file test nếu chưa có. So khớp theo **từ nguyên vẹn**, không phân biệt hoa thường, sau khi chuẩn hóa Unicode NFC *(giả định: tiếng Việt có nhiều cách mã hóa dấu; khớp theo từ để "đau" không khớp nhầm với chữ khác)*.
- **R10.** Layout dùng được ở chiều rộng ≥ 768px *(QA#26, giả định)*.

## 4. Thiết kế liên quan

- **Module / file (theo code thực tế):**
  - `web/src/pages/Alerts/AlertsPage.tsx` (gồm bộ lọc).
  - `web/src/components/AlertCard.tsx`, `AlertDetailModal.tsx`, `AlertActions.tsx`, `Badges.tsx`: dùng chung với F21, F22 *(giả định: đặt ở `components/` để tái sử dụng)*.
  - `web/src/api/hooks.ts`: `useAlerts`, `useAlertAction` (acknowledge/outcome/resolve).
  - `web/src/realtime/sound.ts` (Web Audio), `web/src/realtime/RealtimeProvider.tsx` (thông báo + âm thanh khi `alert.created` HIGH); `web/src/utils/time.ts` (`HH:mm:ss`, Asia/Ho_Chi_Minh).
  - `web/src/i18n/vi.ts`, `web/src/i18n/vi.test.ts`.
  - Test: `web/src/pages/Alerts/AlertsPage.test.tsx`, `web/src/components/AlertActions.test.tsx`; dữ liệu giả `web/src/test/alertFixtures.ts`.
- **Dữ liệu:** không có.
- **API:** `GET /api/v1/alerts`, `GET /api/v1/alerts/{id}`, `POST /api/v1/alerts/{id}/acknowledge|outcome|resolve` (F19); WS `alert.created`, `alert.updated` (F18). Type sinh bằng `make gen-api-types`.
- **UI:** màn hình "Cảnh báo". Text cần thêm vào `vi.ts`: tiêu đề màn hình, nhãn bộ lọc, nhãn nút, nhãn trạng thái/kết quả/mức ưu tiên, mẫu câu "{mô tả} lúc {giờ}.", "Giường {mã} - Cảnh báo {mức}", "Chưa ghi kết quả", thông báo lỗi chung.
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [x] **AC1.** Danh sách hiển thị thời gian, giường, mức ưu tiên, trạng thái; lọc được theo trạng thái, giường, mức ưu tiên, khoảng thời gian; cảnh báo chưa xử lý nằm đầu *(PDF §9.1 (tr.11))*. — *Kiểm chứng:* `web/src/pages/Alerts/AlertsPage.test.tsx` (`renders alerts with bed, priority, status`, `sends filter params to API`, `keeps unresolved alerts on top`, `shows empty text when no alert matches`); giường đã xóa trong bộ lọc: `web/src/pages/Timeline/deletedBeds.test.tsx`.
- [x] **AC2.** Nút đúng PDF §9.2: [Đã tiếp nhận] [Xem chi tiết] khi chờ; sau khi tiếp nhận có [Xác nhận đúng] [Cảnh báo sai] [Bệnh nhân an toàn] [Đã xử lý] và ô ghi chú; đã xử lý mà chưa có kết quả thì hiển thị "Chưa ghi kết quả" *(PDF §9.2 (tr.11); ADR-0007)*. — *Kiểm chứng:* `AlertActions.test.tsx` (`pending shows acknowledge and detail`, `acknowledged shows three outcomes, resolve and note`, `resolved shows only detail`, `buttons call correct endpoints`, `outcome and resolve send the note`); `AlertsPage.test.tsx::resolved without outcome shows Chưa ghi kết quả`, `detail dialog shows people, outcome and links without technical values`.
- [x] **AC3.** Cảnh báo mới tự hiện, không cần tải lại trang. Mức Ưu tiên cao có màu nổi bật và âm thanh *(HS §4.2; QA#17, giả định)*. — *Kiểm chứng:* `AlertsPage.test.tsx` (`new alert appears after alert.created message`, `alert.updated refreshes card status without reload`, `high priority card is highlighted`, `high priority plays sound once`, `medium priority does not play sound`). Kiểm thủ công với worker thật: chưa làm, xem mục 10.
- [x] **AC4.** Mọi text nằm trong `web/src/i18n/vi.ts`; có test quét từ cấm và test đủ text cho `EventCode`, `Priority`, `AlertStatus`, `AlertOutcome`; UI không hiện mã nội bộ *(PDF §9.2 (tr.11), §9.3 (tr.12); glossary.md)*. — *Kiểm chứng:* `web/src/i18n/vi.test.ts` (`does not contain forbidden word`, `forbidden-word scanner on …` (bảng ca), `has text for every enum value: EventCode|Priority|AlertStatus|AlertOutcome` (so với `openapi.json`), `does not contain internal codes such as BED_EXIT`); `AlertsPage.test.tsx::does not render internal codes`.
- [x] **AC5.** DOCTOR không thấy nút thao tác. Lỗi 409 khi người khác đã tiếp nhận hiển thị `message` có tên người đó *(QA#18; ADR-0007)*. — *Kiểm chứng:* `AlertActions.test.tsx` (`doctor sees only detail button`, `shows 409 message with acknowledger name`, `shows forbidden message on 403`); `AlertsPage.test.tsx::409 shows message and refreshes the card`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | component (Vitest + mock API) | Danh sách giả lẫn PENDING/ACKNOWLEDGED/RESOLVED; đổi bộ lọc | Danh sách rỗng hiện câu trống tiếng Việt, không lỗi |
| AC2 | component | Render theo từng `status`; bấm nút, kiểm request | `RESOLVED` không có nút thao tác |
| AC3 | component (WS giả) + thủ công | Đẩy message `alert.created`, kiểm danh sách và hàm âm thanh (mock) | Mức MEDIUM không phát âm thanh |
| AC4 | unit (Vitest) | Quét `vi.ts`; so danh sách enum từ type OpenAPI | Chèn thử chuỗi có từ cấm → test phải fail (test của test viết dạng bảng) |
| AC5 | component | Đăng nhập giả vai DOCTOR; mock API trả 409 | — |

## 7. Giả định

- *(giả định)* Chi tiết cảnh báo không hiển thị `rule_id` hay giá trị kỹ thuật (R4).
- *(giả định)* Âm thanh tạo bằng Web Audio API; chấp nhận trình duyệt chặn tự phát âm thanh (R6). Có âm thanh cho mức cao theo QA#17 *(giả định)*.
- *(giả định)* Test từ cấm khớp theo từ nguyên vẹn, sau khi chuẩn hóa NFC (R9).
- *(giả định)* Component thao tác đặt ở `components/` để F21, F22 dùng lại.
- Chiều rộng ≥ 768px (QA#26, giả định).

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

Prototype đã có màn hình Cảnh báo. Việc của F20 là đối chiếu từng AC với code, viết test còn thiếu, chỉ sửa code ở chỗ test chỉ ra lỗ hổng.

**Code hiện có (lệch nhẹ so với mục 4, giữ nguyên):**
- `web/src/pages/Alerts/AlertsPage.tsx`: bộ lọc (trạng thái, mức ưu tiên, giường gồm cả giường đã xóa qua `useBeds(true)`, khoảng thời gian), gửi lên `GET /api/v1/alerts`; hiển thị đúng thứ tự API trả (chưa xử lý trước, F19 R9).
- `web/src/components/AlertCard.tsx`, `AlertDetailModal.tsx`, `AlertActions.tsx`, `Badges.tsx` (đặt ở `components/` để F21, F22 dùng lại, thay cho `AlertFilters.tsx`/`AlertCard.tsx`/`AlertDetail.tsx` trong `pages/Alerts/`).
- `web/src/api/hooks.ts`: `useAlerts`, `useAlertAction` (acknowledge/outcome/resolve; `onSettled` làm mới cache nên 409 cũng làm mới thẻ).
- `web/src/realtime/RealtimeProvider.tsx` + `invalidation.ts`: `alert.created`/`alert.updated` làm mới query `alerts`; `alert.created` mức HIGH gọi `playAlertSound()` (`web/src/realtime/sound.ts`, Web Audio).
- `web/src/i18n/vi.test.ts`: đã quét từ cấm theo từ nguyên vẹn + NFC, có ca kiểm tra hàm so khớp.

**AC đã đạt một phần (bằng chứng hiện có):** AC4 phần từ cấm (`vi.test.ts::does not contain forbidden word`, `word matching is NFC-aware and whole-word only`); type `Record<EventCode|Priority|AlertStatus|AlertOutcome, string>` trong `vi.ts` buộc đủ text lúc typecheck. Bộ lọc giường gồm giường đã xóa: `web/src/pages/Timeline/deletedBeds.test.tsx`. Các AC còn lại có code nhưng **chưa có test**.

**Lỗ hổng cần làm (test trước):**
1. `web/src/components/AlertActions.test.tsx` (AC2, AC5): bộ nút theo `PENDING`/`ACKNOWLEDGED`/`RESOLVED`; nút kết quả đang chọn có `aria-pressed`; ô ghi chú có nhãn; bấm nút gửi đúng endpoint và body (gồm ghi chú); DOCTOR chỉ có "Xem chi tiết"; 409 hiện `message` có tên người tiếp nhận; 403 hiện thông báo không đủ quyền.
2. `web/src/pages/Alerts/AlertsPage.test.tsx` (AC1, AC3, AC4): hiển thị giường/mức/trạng thái/giờ; tham số lọc gửi lên API; giữ thứ tự API (chưa xử lý trên đầu); danh sách rỗng; thẻ HIGH nổi bật; khung chi tiết; không có mã nội bộ trong DOM; `alert.created` qua `RealtimeProvider` (WS giả) làm danh sách tự cập nhật; HIGH phát âm thanh một lần, MEDIUM không phát.
3. `web/src/i18n/vi.test.ts` (AC4): `has text for every enum value` so với enum trong `web/src/api/openapi.json`; bảng ca cho bộ quét từ cấm (chuỗi có từ cấm phải bị bắt).
4. Sửa code nếu test đỏ vì lỗi thật. Không đổi API nên không cần `make gen-api-types`, không có migration.

**Rủi ro:** test realtime phụ thuộc `RealtimeProvider`; mock `RealtimeClient` bằng `vi.mock('./wsClient')` để không mở WebSocket thật. Không đụng Overview/LiveView (F21) hay engine (F26).

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**Triển khai (2026-11-18), nhánh `feat/F20-alerts-screen`:**
- Màn hình đã có sẵn từ prototype. F20 thêm test cho mọi AC và một thay đổi nhỏ: `AlertCard` có `data-priority` để kiểm việc làm nổi bật mức Ưu tiên cao.
- Test mới: `web/src/components/AlertActions.test.tsx` (8 ca), `web/src/pages/Alerts/AlertsPage.test.tsx` (13 ca, WebSocket giả qua `vi.mock('../../realtime/wsClient')`, âm thanh giả qua `vi.mock('../../realtime/sound')`), `web/src/i18n/vi.test.ts` (thêm bảng ca cho bộ quét từ cấm và đối chiếu enum với `web/src/api/openapi.json`). Dữ liệu giả dùng chung: `web/src/test/alertFixtures.ts`.
- Đỏ trước khi sửa: chỉ `high priority card is highlighted` (thiếu `data-priority`). Các ca khác xanh ngay với code có sẵn, sau khi sửa hai kỳ vọng sai của chính test (bộ lọc giờ gửi `…+07:00`; "Chưa ghi kết quả" nằm chung dòng với nhãn "Kết quả kiểm tra").
- Không đổi API, không cần `make gen-api-types`, không có migration.
- Thứ tự danh sách: trang giữ đúng thứ tự API trả (F19 R9: chưa xử lý trước, rồi mới nhất trước). API **không** sắp HIGH lên trước trong cùng trạng thái; spec F20 không yêu cầu nên không làm.

**`make check` (2026-11-18):** format-check, lint, typecheck, lint-imports, check-api-types xanh; pytest `1134 passed, 6 deselected`. Bước vitest trong `make check` bị Node hết bộ nhớ trên máy dev (không phải lỗi test); chạy lại riêng `npx vitest run --maxWorkers=2` trong `web/`: `24 files, 175 tests passed`; `npm run build` xanh.

**Kiểm thủ công AC3 (2026-11-18):** DB dev riêng `postcare_f20` (`postcare seed --reset`), API cổng 8020, `postcare simulate --bed A01 --speed 4 --away 4`. Một client WebSocket (`/api/v1/ws`, tài khoản `nurse`) nhận `bed.state`, `camera.status`, `event.created`, `alert.created` (alert 5, giường A01, mức Cần chú ý, Chờ tiếp nhận). Cảnh báo có trong `GET /api/v1/alerts?bed_id=…`, nằm đầu danh sách. Vòng đời qua API: DOCTOR tiếp nhận → 403; `nurse` tiếp nhận → 200; `charge` tiếp nhận → 409 "Cảnh báo đã được tiếp nhận bởi Nguyễn Thị Hoa"; outcome `PATIENT_SAFE` + ghi chú → 200; resolve → 200 `RESOLVED`; client WS nhận đủ 3 `alert.updated` cho cảnh báo này. Âm thanh trên trình duyệt thật không kiểm (không có trình duyệt có loa trong phiên này); đã có test component `high priority plays sound once`.

**Review (2026-11-18): Đạt.** Sửa theo review:
- `AlertsPage.test.tsx::409 shows message and refreshes the card` render `<Notifications />` và kiểm toàn bộ câu "Cảnh báo đã được tiếp nhận bởi …".
- `AlertsPage.test.tsx::high priority plays sound once` đẩy cùng một `alert.created` hai lần: đỏ trước khi sửa (âm thanh phát 2 lần). Sửa `web/src/realtime/RealtimeProvider.tsx`: nhớ id cảnh báo đã báo (tối đa 500 id mỗi kết nối), `alert.created` lặp lại không hiện thông báo và không phát âm thanh lần nữa. Cache vẫn được làm mới bình thường. Merge `main` (chưa có F21) trước khi sửa; khi F21 merge, nếu F21 có bộ báo cảnh báo riêng thì giữ một chỗ khử trùng duy nhất.

**`make check` sau review (2026-11-18): xanh toàn bộ** (pytest `1223 passed, 6 deselected`; vitest `29 files, 204 tests passed`; build xanh).

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
