# F07 – Theo dõi trực tiếp cơ bản

| Thuộc tính | Giá trị |
|---|---|
| Mã | F07 |
| Trạng thái | In progress <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
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

> Lập ngày 2026-11-18 (nhánh `feat/F07-live-view`). F06 đã có `LatestFrameStore` (RAM), worker gửi JPEG ~5 fps (RAW tới F28). Màn hình `LiveViewPage` hiện vẽ hình người que **cố định** theo `body_state` (`SkeletonView`, thời giả lập): F07 thay bằng ảnh thật từ MJPEG.

**Quyết định khi lập kế hoạch:**

- **Phân quyền R1:** theo bảng phân quyền mới của api-conventions.md (F35/F36) thì MJPEG chỉ cho **vai trò nhân viên** (`require_staff`); `FAMILY` → 403 `FORBIDDEN` (F36 AC2 đã liệt kê `stream.mjpeg`). Câu "mọi vai trò đã đăng nhập" ở R1 viết trước khi có `FAMILY`.
- **Chưa có khung / khung cũ lúc mở stream** → 404 `NOT_FOUND` (không gửi byte ảnh nào), để `<img onError>` chuyển sang "Mất kết nối camera" và thử lại.
- **ROI:** `GET /api/v1/cameras/{id}` (`CameraDetailOut`) thêm `roi_polygon` (danh sách không đổi). `make gen-api-types`.
- **Polling R5:** dùng `GET /overview` (đã có phiên + mã bệnh nhân + trạng thái camera + `bed.state`) và `GET /cameras/{id}` mỗi 2 s, thay cho `GET /sessions?active=true` (cùng dữ liệu, ít request hơn).
- **Không** thêm keypoint vào trạng thái giường: skeleton/làm mờ là việc của F28 (render trong worker), skeleton cho người nhà là F36 (`target_keypoints`). F07 chỉ chuyển tiếp JPEG nên F28 cắm vào được mà không đổi API/UI (chỉ thêm nhãn chế độ).
- Khối thông tin bên phải (trạng thái cơ thể, chất lượng, sự kiện gần nhất) đã có từ prototype: giữ nguyên, không mở rộng (ngoài phạm vi, §8).

**Các bước:**

1. **API:** `settings.stream_stale_frame_s = 3.0`, `stream_poll_interval_s = 0.05`. `api/deps.py::require_staff_query(token)`: tự mở/đóng DB session (không giữ kết nối DB suốt stream), 401 thiếu/sai/hết hạn, 403 `FAMILY`. `api/v1/stream.py`: `mjpeg_parts(frames, camera_id, stale_after_s, poll_s, now, sleep)` (async generator, đồng hồ inject) gửi khung khi có khung **mới** (so đối tượng), dừng khi khung cũ hơn `stale_frame_s`; route `GET /cameras/{id}/stream.mjpeg` → `StreamingResponse` `multipart/x-mixed-replace; boundary=frame`, `Cache-Control: no-store`; camera không tồn tại → 404.
2. **Web:** `hooks.ts` thêm `useCameraDetail(id)` (poll 2 s); `components/CameraStream.tsx` (`<img>` MJPEG + token query; offline hoặc lỗi ảnh → khối "Mất kết nối camera", thử lại sau 3 s; camera online lại → mở lại stream); `components/RoiOverlay.tsx` (SVG `viewBox 0 0 1 1`, `preserveAspectRatio="none"` phủ đúng khung ảnh nên tự co giãn theo cửa sổ); `LiveViewPage.tsx` dùng hai component trên, bỏ `SkeletonView.tsx` và text "mô phỏng"; text mới trong khối `live`/`camera` của `vi.ts`.
3. **Docs:** api-conventions.md (MJPEG: quyền, 404, đóng khi khung cũ; `roi_polygon` ở `GET /cameras/{id}`), dev-setup/README nếu nhắc màn hình mô phỏng.

**Test trước:**

- `server/tests/api/test_stream_mjpeg.py`: `test_mjpeg_requires_token` (thiếu/sai/hết hạn → 401), `test_mjpeg_family_forbidden`, `test_mjpeg_all_staff_roles_allowed`, `test_mjpeg_no_frame_404`, `test_mjpeg_unknown_camera_404`, `test_mjpeg_streams_latest_frame` (2 khung → phần đầu là khung mới, content-type multipart), `test_mjpeg_closes_when_frame_stale`, `test_mjpeg_parts_skips_unchanged_frame` (đồng hồ giả), `test_mjpeg_does_not_write_disk`; `test_cameras.py`: `roi_polygon` trong chi tiết camera.
- Web: `LiveViewPage.test.tsx` (`shows bed, session and camera status`, `shows no-session label`, `no camera → "Chưa gắn camera", không có <img>`, `hides stream when camera offline`, `hides stream on image error`, `stream comes back when camera online again`, không có mã nội bộ), `RoiOverlay.test.tsx` (`scales normalized points to image size`, `renders nothing without polygon`).

Commit: `docs(F07): plan` → `test(F07): …` → `feat(F07): …` → `docs(F07): …`.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
