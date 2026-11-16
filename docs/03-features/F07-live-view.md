# F07 – Theo dõi trực tiếp cơ bản

| Thuộc tính | Giá trị |
|---|---|
| Mã | F07 |
| Trạng thái | Todo <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F06 |
| Nhánh code | C (frontend/test) |
| Nguồn | PDF §9.1 (tr.11), §4.3 (tr.5–6); HS §4.3; QA#29; A02; ADR-0002, ADR-0005 |

## 1. Mục tiêu

Cho người dùng xem hình ảnh camera của một giường trên màn hình "Theo dõi trực tiếp" (PDF §9.1), kèm trạng thái kết nối, giường và phiên theo dõi. Khi camera mất kết nối, giao diện phải nói rõ "Mất kết nối camera" thay vì để một khung hình đứng yên khiến người xem tưởng vẫn đang quan sát (PDF §4.3: thể hiện rõ khi hệ thống không đủ dữ liệu). Vùng giường (Bed ROI) được vẽ đè lên hình nếu đã cấu hình.

## 2. Phạm vi

**Trong phạm vi**
- Endpoint `GET /api/v1/cameras/{id}/stream.mjpeg?token=` phát khung mới nhất từ bộ đệm RAM (F06).
- Màn hình "Theo dõi trực tiếp" theo giường: video, trạng thái kết nối camera, mã giường, phiên đang mở.
- Xử lý camera offline: ẩn ảnh, hiện thông báo.
- Vẽ đè Bed ROI (lớp SVG phía trình duyệt).
- Làm mới trạng thái bằng polling cho tới khi có WebSocket.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Trạng thái cơ thể, chất lượng quan sát, sự kiện gần nhất trên màn hình này (PDF §9.1). Dữ liệu `bed.state` có từ F17/F18; tín hiệu khuôn mặt hiển thị ở F26.
- Vẽ, sửa ROI (→ F08). F07 chỉ hiển thị.
- Chế độ chỉ skeleton / làm mờ và chuyển chế độ (→ F28).
- Cập nhật realtime qua WebSocket (→ F18, F21).
- Bắt đầu/kết thúc phiên từ màn hình này *(F04 đặt nút ở "Quản lý giường")*.

## 3. Yêu cầu chi tiết

- **R1.** `GET /api/v1/cameras/{id}/stream.mjpeg?token=<jwt>` trả `multipart/x-mixed-replace` *(api-conventions.md)*:
  - token qua query vì thẻ `<img>` không gửi được header *(api-conventions.md)*; thiếu/sai/hết hạn → 401;
  - mọi vai trò đã đăng nhập được xem *(api-conventions.md, bảng phân quyền)*;
  - mỗi khi bộ đệm có khung mới thì gửi khung đó; không có khung mới thì không gửi lại khung cũ;
  - khung trong bộ đệm cũ hơn `stale_frame_s` *(giả định 3 s)* thì ngừng gửi và đóng stream, để trình duyệt không giữ ảnh đứng yên;
  - module `api` không import `vision` *(overview.md §3)*: API chỉ chuyển tiếp bytes JPEG worker đã gửi.
- **R2.** Không ghi khung hình ra đĩa hay log *(QA#29)*.
- **R3.** Màn hình "Theo dõi trực tiếp" tại `/beds/:bedId/live` *(PDF §9.1; giả định đường dẫn; F09 mở màn hình này khi bấm thẻ giường)*:
  - tiêu đề: mã giường (ví dụ "Giường A01");
  - phiên: "Đang theo dõi" kèm mã bệnh nhân và giờ bắt đầu (`HH:mm:ss`), hoặc "Không theo dõi";
  - trạng thái camera: "Camera hoạt động" / "Mất kết nối camera" / "Chưa rõ trạng thái" / "Chưa gắn camera";
  - video từ thẻ `<img src="…/stream.mjpeg?token=…">` *(ADR-0005)*.
- **R4.** Camera offline (`cameras.status = OFFLINE`) hoặc stream đóng → ẩn ảnh, hiện khối "Mất kết nối camera" *(tên theo catalog `CAMERA_OFFLINE` trong event-engine.md)*. Camera online lại → tự mở lại stream *(giả định)*.
- **R5.** Trạng thái camera và phiên được làm mới bằng polling `GET /api/v1/cameras/{id}` và `GET /api/v1/sessions?active=true&bed_id=…` mỗi 2 giây *(giả định; F21 bỏ polling khi có WebSocket)*. Lỗi tải ảnh (`onError` của `<img>`) cũng chuyển sang khối "Mất kết nối camera".
- **R6.** Vẽ đè Bed ROI nếu `cameras.roi_polygon` có giá trị *(PDF §16 (tr.17) kịch bản privacy nhắc "skeleton, Bed ROI")*:
  - lớp SVG nằm trên ảnh, toạ độ chuẩn hóa 0–1 nhân với kích thước ảnh đang hiển thị;
  - giữ đúng vị trí khi cửa sổ đổi kích thước;
  - chưa có ROI → không vẽ, hiện ghi chú "Chưa cấu hình vùng giường".
- **R7.** Layout dùng được ở màn hình ≥768px *(QA#26)*.
- **R8.** Text giao diện nằm trong `web/src/i18n/vi.ts`; không hiện mã nội bộ *(ADR-0005; glossary.md)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/v1/stream.py` (MJPEG), dùng `api/frame_buffer.py` của F06; `api/auth.py` thêm hàm xác thực token từ query.
  - `server/tests/api/test_stream_mjpeg.py`.
  - `web/src/pages/LiveView/LiveViewPage.tsx`, `web/src/components/CameraStream.tsx`, `web/src/components/RoiOverlay.tsx`.
  - `web/src/pages/LiveView/LiveViewPage.test.tsx`, `web/src/components/RoiOverlay.test.tsx`.
- **Dữ liệu:** đọc `cameras` (`status`, `roi_polygon`), `monitoring_sessions`, `beds`, `patients`; khung hình chỉ trong RAM (xem [data-model.md](../02-architecture/data-model.md#dữ-liệu-không-lưu-trong-db)).
- **API:** `GET /api/v1/cameras/{id}/stream.mjpeg?token=` (xem [api-conventions.md](../02-architecture/api-conventions.md#danh-sách-endpoint-dự-kiến)); dùng lại `GET /api/v1/cameras/{id}`, `GET /api/v1/beds/{id}`, `GET /api/v1/sessions`.
- **UI:** màn hình "Theo dõi trực tiếp". Text cần thêm vào `vi.ts`: `live.title` ("Theo dõi trực tiếp"), `live.bed` ("Giường {code}"), `camera.online` ("Camera hoạt động"), `camera.offline` ("Mất kết nối camera"), `camera.unknown` ("Chưa rõ trạng thái"), `roi.notConfigured` ("Chưa cấu hình vùng giường").
- **Cấu hình:** `stale_frame_s` trong settings của API *(giả định 3 s)*.

## 5. Acceptance criteria

- [ ] **AC1.** `GET /api/v1/cameras/{id}/stream.mjpeg?token=` (cần token hợp lệ) phát khung mới nhất trong bộ đệm; thiếu hoặc sai token → 401. *(ADR-0002)* — *Kiểm chứng:* test `test_mjpeg_requires_token`, `test_mjpeg_streams_latest_frame` (đặt 2 khung vào bộ đệm, đọc phần đầu stream thấy khung mới nhất), `test_mjpeg_closes_when_frame_stale`.
- [ ] **AC2.** Màn hình "Theo dõi trực tiếp" hiện video, trạng thái kết nối camera, mã giường và phiên (mã bệnh nhân, giờ bắt đầu hoặc "Không theo dõi"). *(PDF §9.1)* — *Kiểm chứng:* component test `LiveViewPage shows bed, session and camera status`, `LiveViewPage shows no-session label`; kiểm tra tay với webcam thật, ghi vào mục 10.
- [ ] **AC3.** Camera offline → hiện "Mất kết nối camera", không còn ảnh đứng yên trên màn hình. *(PDF §4.3)* — *Kiểm chứng:* component test `LiveViewPage hides stream when camera offline`, `LiveViewPage hides stream on image error`; thủ công: dừng worker, trong ≤5 s + chu kỳ polling màn hình chuyển sang thông báo.
- [ ] **AC4.** Bed ROI được vẽ đè lên khung hình nếu đã cấu hình; không có ROI thì hiện "Chưa cấu hình vùng giường". *(PDF §7.2 (tr.9), §16 (tr.17); QA#15)* — *Kiểm chứng:* component test `RoiOverlay scales normalized points to image size`, `RoiOverlay renders nothing without polygon`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | `test_mjpeg_streams_latest_frame`, `test_mjpeg_closes_when_frame_stale` | Thiếu/sai/hết hạn token → 401; camera không có khung nào → không gửi dữ liệu ảnh |
| AC2 | component | `LiveViewPage.test.tsx` (msw) | Giường không có camera → "Chưa gắn camera", không có thẻ `<img>` |
| AC3 | component + thủ công | `LiveViewPage hides stream when camera offline`, `... on image error` | Camera online lại → ảnh hiện lại |
| AC4 | component | `RoiOverlay.test.tsx` | `roi_polygon = null` → không vẽ |

## 7. Giả định

- *(giả định)* Đường dẫn màn hình `/beds/:bedId/live`.
- *(giả định)* `stale_frame_s = 3`: khung cũ hơn thì đóng stream.
- *(giả định)* Polling trạng thái 2 giây cho tới F21.
- *(giả định)* ROI vẽ phía trình duyệt bằng SVG (không vẽ vào JPEG ở worker), để ROI hiển thị giống nhau ở mọi chế độ hiển thị.
- *(giả định)* Camera online lại thì tự mở lại stream.

## 8. Câu hỏi mở

- Trạng thái cơ thể, chất lượng quan sát và sự kiện gần nhất trên "Theo dõi trực tiếp" (PDF §9.1) chưa được gán rõ cho feature nào trong danh sách. Đề xuất: bổ sung khi làm F18 (có `bed.state`) hoặc F21. **Không chặn** F07.

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

1. …

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
