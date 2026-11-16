# F20 – Màn hình Cảnh báo

| Thuộc tính | Giá trị |
|---|---|
| Mã | F20 |
| Trạng thái | Todo |
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

- **Module / file dự kiến:**
  - `web/src/pages/Alerts/AlertsPage.tsx`, `AlertFilters.tsx`, `AlertCard.tsx`, `AlertDetail.tsx`.
  - `web/src/components/AlertActions.tsx`: nhóm nút thao tác, dùng chung với F21, F22 *(giả định: đặt ở `components/` để tái sử dụng)*.
  - `web/src/api/alerts.ts`: hook TanStack Query (`useAlerts`, `useAlert`, `useAcknowledgeAlert`, `useAlertOutcome`, `useResolveAlert`).
  - `web/src/utils/alertSound.ts`; `web/src/utils/time.ts` (đã có hoặc tạo: định dạng `HH:mm:ss`, Asia/Ho_Chi_Minh).
  - `web/src/i18n/vi.ts`, `web/src/i18n/vi.test.ts`.
  - Test: `web/src/pages/Alerts/AlertsPage.test.tsx`, `web/src/components/AlertActions.test.tsx`.
- **Dữ liệu:** không có.
- **API:** `GET /api/v1/alerts`, `GET /api/v1/alerts/{id}`, `POST /api/v1/alerts/{id}/acknowledge|outcome|resolve` (F19); WS `alert.created`, `alert.updated` (F18). Type sinh bằng `make gen-api-types`.
- **UI:** màn hình "Cảnh báo". Text cần thêm vào `vi.ts`: tiêu đề màn hình, nhãn bộ lọc, nhãn nút, nhãn trạng thái/kết quả/mức ưu tiên, mẫu câu "{mô tả} lúc {giờ}.", "Giường {mã} - Cảnh báo {mức}", "Chưa ghi kết quả", thông báo lỗi chung.
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [ ] **AC1.** Danh sách hiển thị thời gian, giường, mức ưu tiên, trạng thái; lọc được theo trạng thái, giường, mức ưu tiên, khoảng thời gian; cảnh báo chưa xử lý nằm đầu *(PDF §9.1 (tr.11))*. — *Kiểm chứng:* `web/src/pages/Alerts/AlertsPage.test.tsx` (`renders alerts with bed, priority, status`, `sends filter params to API`, `keeps unresolved alerts on top`).
- [ ] **AC2.** Nút đúng PDF §9.2: [Đã tiếp nhận] [Xem chi tiết] khi chờ; sau khi tiếp nhận có [Xác nhận đúng] [Cảnh báo sai] [Bệnh nhân an toàn] [Đã xử lý] và ô ghi chú; đã xử lý mà chưa có kết quả thì hiển thị "Chưa ghi kết quả" *(PDF §9.2 (tr.11); ADR-0007)*. — *Kiểm chứng:* `AlertActions.test.tsx` (`pending shows acknowledge and detail`, `acknowledged shows three outcomes, resolve and note`, `resolved without outcome shows Chưa ghi kết quả`, `buttons call correct endpoints`).
- [ ] **AC3.** Cảnh báo mới tự hiện, không cần tải lại trang. Mức Ưu tiên cao có màu nổi bật và âm thanh *(HS §4.2; QA#17, giả định)*. — *Kiểm chứng:* `AlertsPage.test.tsx` (`new alert appears after alert.created message`, `high priority plays sound once`, `medium priority does not play sound`); kiểm thủ công với worker thật, ghi ở mục 10.
- [ ] **AC4.** Mọi text nằm trong `web/src/i18n/vi.ts`; có test quét từ cấm và test đủ text cho `EventCode`, `Priority`, `AlertStatus`, `AlertOutcome`; UI không hiện mã nội bộ *(PDF §9.2 (tr.11), §9.3 (tr.12); glossary.md)*. — *Kiểm chứng:* `web/src/i18n/vi.test.ts` (`contains no forbidden words`, `has text for every enum value`); `AlertsPage.test.tsx::does not render internal codes`.
- [ ] **AC5.** DOCTOR không thấy nút thao tác. Lỗi 409 khi người khác đã tiếp nhận hiển thị `message` có tên người đó *(QA#18; ADR-0007)*. — *Kiểm chứng:* `AlertActions.test.tsx` (`doctor sees only detail button`, `shows 409 message with acknowledger name`).

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

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
