# F07 – Theo dõi trực tiếp cơ bản

| Thuộc tính | Giá trị |
|---|---|
| Mã | F07 |
| Trạng thái | Done <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
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
  - chỉ **vai trò nhân viên** được xem (`require_staff_query`, cùng tập vai trò với `require_staff`); `FAMILY` → 403 `FORBIDDEN` *(api-conventions.md, bảng phân quyền; F35 R2; F36 AC2)*;
  - camera không tồn tại, chưa có khung hoặc khung đã cũ lúc mở → 404, không gửi byte ảnh *(giả định)*;
  - trong lúc phát, kiểm tra lại người xem mỗi `stream_revalidate_s` *(giả định 5 s)*: bị khóa / đặt lại mật khẩu / đổi vai trò → đóng stream *(F35)*;
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
- **R5.** Trạng thái camera và phiên được làm mới bằng polling mỗi 2 giây: `GET /api/v1/overview` (phiên đang mở, mã bệnh nhân, giờ bắt đầu, trạng thái camera, `bed.state`) và `GET /api/v1/cameras/{id}` (trạng thái camera mới nhất, `roi_polygon`) *(giả định; F21 bỏ polling khi có WebSocket)*. Lỗi tải ảnh (`onError` của `<img>`) cũng chuyển sang khối "Mất kết nối camera".
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

- [x] **AC1.** `GET /api/v1/cameras/{id}/stream.mjpeg?token=` (cần token hợp lệ) phát khung mới nhất trong bộ đệm; thiếu hoặc sai token → 401. *(ADR-0002)* — *Kiểm chứng:* test `test_mjpeg_requires_token`, `test_mjpeg_streams_latest_frame` (đặt 2 khung vào bộ đệm, đọc phần đầu stream thấy khung mới nhất), `test_mjpeg_closes_when_frame_stale`.
- [x] **AC2.** Màn hình "Theo dõi trực tiếp" hiện video, trạng thái kết nối camera, mã giường và phiên (mã bệnh nhân, giờ bắt đầu hoặc "Không theo dõi"). *(PDF §9.1)* — *Kiểm chứng:* component test `LiveViewPage shows bed, session and camera status`, `LiveViewPage shows no-session label`; kiểm tra tay với webcam thật, ghi vào mục 10.
- [x] **AC3.** Camera offline → hiện "Mất kết nối camera", không còn ảnh đứng yên trên màn hình. *(PDF §4.3)* — *Kiểm chứng:* component test `LiveViewPage hides stream when camera offline`, `LiveViewPage hides stream on image error`; thủ công: dừng worker, trong ≤5 s + chu kỳ polling màn hình chuyển sang thông báo.
- [x] **AC4.** Bed ROI được vẽ đè lên khung hình nếu đã cấu hình; không có ROI thì hiện "Chưa cấu hình vùng giường". *(PDF §7.2 (tr.9), §16 (tr.17); QA#15)* — *Kiểm chứng:* component test `RoiOverlay scales normalized points to image size`, `RoiOverlay renders nothing without polygon`.

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
- *(giả định)* `stream_revalidate_s = 5`: chu kỳ kiểm tra lại người xem trong lúc stream.
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

**2026-11-18 – triển khai (nhánh `feat/F07-live-view`), trạng thái In review.**

Bằng chứng theo AC:

| AC | Bằng chứng |
|---|---|
| AC1 | `server/tests/api/test_stream_mjpeg.py`: `test_mjpeg_requires_token` (thiếu / sai / hết hạn → 401), `test_mjpeg_header_token_not_enough`, `test_mjpeg_family_forbidden` (403, không có byte JPEG), `test_mjpeg_all_staff_roles_allowed` (×4), `test_mjpeg_no_frame_404`, `test_mjpeg_stale_frame_at_connect_404`, `test_mjpeg_unknown_camera_404`, `test_mjpeg_streams_latest_frame` (2 khung → chỉ khung mới, `multipart/x-mixed-replace; boundary=frame`, `no-store`), `test_mjpeg_closes_when_frame_stale`, `test_mjpeg_parts_sends_each_new_frame_once` / `..._no_frame_yields_nothing` (đồng hồ giả), `test_mjpeg_does_not_write_disk` (R2), `test_default_stale_frame_is_3s` |
| AC2 | `web/src/pages/LiveView/LiveViewPage.test.tsx`: `shows bed, session and camera status`, `shows no-session label`, `shows "Chưa gắn camera" and no image without a camera`, `shows no internal codes`; thủ công (dưới) |
| AC3 | `LiveViewPage hides stream when camera offline`, `LiveViewPage hides stream on image error`; `web/src/components/CameraStream.test.tsx` (`reopens the stream when the camera comes back online`, `image error → offline block, then retries with a new URL`); thủ công (dưới) |
| AC4 | `web/src/components/RoiOverlay.test.tsx` (`scales normalized points to image size`, `follows a new display size`, `renders nothing without polygon`); `LiveViewPage notes when the bed region is not configured`; `server/tests/api/test_cameras.py::test_camera_detail_includes_roi_polygon` |

Chạy tay end-to-end (2026-11-18): DB `postcare_f07` (`alembic upgrade head` + `postcare seed`), camera 1 (A01) nguồn FILE `data/external/pexels/pexels-8090735.mp4`, ROI từ `config/cameras/pexels-8090735.yaml` đặt bằng SQL (F08 chưa có); bệnh nhân BN-F07, mở phiên; API cổng 8017, web `npm --prefix web run dev -- --port 5177` (`VITE_API_TARGET=http://127.0.0.1:8017`); `postcare worker --camera-id 1` chạy lặp 8 lần × 14 s (clip dài 7,7 s).

- `curl` qua proxy Vite: `200`, `cache-control: no-store`, 10 khung JPEG trong 2 s (≈ 5 fps). `GET /cameras/1` có `roi_polygon` và `runtime`.
- Trình duyệt (đăng nhập `nurse`), `/beds/1/live`: tiêu đề "Giường A01", nhãn "Camera hoạt động", "Đang theo dõi · Bệnh nhân BN-F07 · bắt đầu 04:24:50", **ảnh thật** từ clip, khung ROI nét đứt vẽ đúng mặt nệm. Ở viewport 768 px: ảnh 483×272, polygon `149.7,87 483,87 483,168.6 149.7,168.6` (= ROI × kích thước ảnh), không cuộn ngang.
- Hết clip → worker báo nguồn `OFFLINE` → trong ≤ 2 s (một chu kỳ polling) ảnh biến mất, hiện khối "Mất kết nối camera"; worker chạy lại → ảnh tự hiện lại sau ~5 s (bước nhịp lấy mẫu 1 s: `IMG ×9 → OFF ×5 → IMG ×10 → OFF`). Log API: `stream.mjpeg` 200 khi có khung, 404 khi không có khung mới.

Điều người sau cần biết:
- **Lệch spec có chủ đích** (§9): MJPEG chỉ cho vai trò nhân viên (`require_staff_query`), `FAMILY` → 403 theo bảng phân quyền mới; chưa có khung / khung cũ lúc mở → 404; polling dùng `GET /overview` + `GET /cameras/{id}` thay cho `GET /sessions?active=true`.
- `require_staff_query` tự mở/đóng DB session, không giữ kết nối DB suốt stream.
- `SkeletonView.tsx` (hình người que cố định theo trạng thái, thời giả lập) đã xóa cùng text `live.simulatedMode/simulatedHint`. Skeleton thật là việc của F28 (render trong worker, API/UI F07 không đổi; F28 chỉ thêm nhãn chế độ R10) và F36 (`target_keypoints` cho người nhà).
- Giới hạn đã biết: nếu camera vẫn `ONLINE` nhưng ngừng gửi khung (ví dụ tạm dừng thu hình, F36), server đóng stream sau 3 s nhưng trình duyệt có thể giữ khung cuối trên `<img>`; F36 hiển thị nhãn "Đang tạm dừng thu hình" cho trường hợp này.
- Uvicorn access log ghi URL có `?token=` (đã chấp nhận trong api-conventions cho WS/MJPEG). Nếu cần, F30 có thể tắt access log hoặc lọc query khi demo.
- Settings mới: `STREAM_STALE_FRAME_S` (3), `stream_poll_interval_s` (0,05), `STREAM_REVALIDATE_S` (5); `.env.example` đã thêm.

**2026-11-18 – review: Đạt**, kèm các điểm sửa (test trước, commit `test(F07): review fixes …` rồi `fix(F07): …`; đã merge `main` cục bộ (F06, F25) trước khi sửa):

1. Access log không lộ JWT: `postcare.api.log_redaction` (`redact()`, `RedactQueryTokenFilter`, `install_access_log_redaction()` idempotent, gắn vào `uvicorn.access` trong `create_app`; dùng lại được cho WS F18). Test `server/tests/api/test_log_redaction.py` (record kiểu uvicorn, chuỗi thường, idempotent, `create_app` cài filter). api-conventions.md mục xác thực đã ghi.
2. Spec R1 (chỉ vai trò nhân viên, `FAMILY` 403, 404 khi chưa có khung) và R5 (nguồn polling thực tế: `/overview` + `/cameras/{id}`) sửa theo code.
3. `mjpeg_parts(still_valid=…, revalidate_s=…)`: mỗi `stream_revalidate_s` (5 s) kiểm tra lại token + `is_active` + `token_version` + vai trò (`deps.staff_from_token`, chạy trong thread, mở/đóng session mỗi lần); không hợp lệ → đóng stream. Test `test_mjpeg_parts_ends_when_viewer_no_longer_valid` (đồng hồ giả: 2 lần kiểm tra, dừng trong ≤ 10,5 s), `test_mjpeg_stream_ends_when_user_locked_mid_stream` (`real_commit`, khóa `nurse` từ luồng khác sau 0,5 s → stream đóng < 10 s dù `stale_frame_s = 30`).

Trạng thái: **Done**.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).

## 12. Mở rộng hai khung theo yêu cầu người dùng (2026-11-19)

Nguồn: yêu cầu trực tiếp của người dùng muốn sản phẩm giống demo hai khung và xác nhận giữ chế độ riêng tư ở trái, thêm skeleton ở phải. Đây là mở rộng *(giả định theo yêu cầu người dùng)* của F07/F28, không thay đổi rule engine.

### Kế hoạch triển khai

1. Worker vẽ thêm JPEG skeleton trên nền mới từ cùng observation và khung hình với luồng hiện tại. Không đổi display_mode, không gửi thêm pixel gốc.
2. Thêm tham số `view=display|skeleton` cho POST frame và GET MJPEG; mặc định display tương thích client cũ. Hai bộ đệm RAM riêng; áp dụng cùng xác thực, giới hạn kích thước, hết hạn, kiểm tra lại tài khoản. Không DB migration, không lưu ảnh.
3. UI hai khung cạnh nhau từ 768 px, xếp dọc trên màn hình nhỏ; trạng thái/sự kiện hiện phía dưới. Mọi nhãn trong vi.ts.
4. Chưa có ROI: vẫn chạy pose cho phần hiển thị, không chạy engine và không phát state/event; UI nói rõ cần vùng giường để theo dõi sự kiện. Skeleton là các người quan sát được, chưa phải xác nhận mục tiêu bệnh nhân.
5. Test bảo vệ luồng riêng tư, tách bộ đệm, quyền/stale ở cả hai view, không chạy engine khi thiếu ROI, UI hai luồng và offline. Chạy make check + test-vision; kiểm chứng browser và worker thật.

### Acceptance criteria bổ sung

- [x] AC5: Hai khung display và skeleton xuất phát từ cùng frame/observation; trái giữ display_mode hiện tại; skeleton không chứa pixel gốc. Hai kết nối MJPEG có thể lệch thời gian truyền, không cam kết đồng bộ từng pixel trên trình duyệt.
- [x] AC6: Cả hai luồng yêu cầu quyền nhân viên và cùng cơ chế hết hạn; không fallback từ skeleton sang ảnh display.
- [x] AC7: Thiếu ROI vẫn thấy pose khi model quan sát được người, không phát state/event, có hướng dẫn cấu hình.
- [x] AC8: Hai khung có nhãn tiếng Việt, responsive, ẩn khi camera offline; trạng thái/sự kiện hiện có tiếp tục cập nhật.


### Review xuất bản (2026-11-19) – Codex: Đạt

- AC5: `test_worker_sends_separate_skeleton_without_changing_display_mode` kiểm tra ảnh skeleton tách biệt và giữ display_mode; kiểm chứng hai stream thật ghi trong session-log ngày 19/11.
- AC6: `test_skeleton_stream_isolated_and_requires_auth`, `test_skeleton_frame_ingest_keeps_views_separate`; generator dùng chung kiểm tra tài khoản và stale cho từng view, không fallback ảnh display.
- AC7: `test_no_roi_observes_pose_for_display_without_engine_or_events`; LiveView giữ hướng dẫn cấu hình ROI.
- AC8: `shows a separate skeleton stream while preserving the privacy mode`, các test offline hiện có; layout SimpleGrid responsive, text trong vi.ts.
- Rà soát phạm vi: không đổi engine, DB hoặc dependency; không thêm ảnh/video/model/cấu hình local vào Git. Chỉ hợp nhất code F07 và tài liệu đi cùng.
- `make test-vision` trong clone fresh: 5 passed, 1 skipped (thiếu clip cận mặt), 1364 deselected, 7.89 s. `make check` đầy đủ chạy qua hook trước khi push bản merge; kết quả cuối trong bàn giao xuất bản.

## 13. Kết nối camera từ Theo dõi trực tiếp (2026-11-20)

Nguồn: yêu cầu người dùng trong phiên 20/11, F03 R2/R7/R14, F05 R2, QA#24. Phụ thuộc F03, F05, F06 và F07 hiện có đều Done.

### Kế hoạch triển khai

1. Dùng lại biểu mẫu camera F03 từ thẻ giường. Chỉ quản trị viên được thêm hoặc sửa nguồn, giường điền sẵn theo màn hình và khóa trong biểu mẫu. Giữ điều kiện bảo vệ phiên đang mở.
2. Worker gửi phiên bản cấu hình trên khung JPEG. Chi tiết camera báo cả hai khung mới thuộc cấu hình hiện tại và có heartbeat gần đây. Sau khi lưu, live view đợi ảnh mới, kể cả khi WebSocket đang mở. Nếu thiếu heartbeat thì hướng dẫn chạy worker cho đúng ID *(giả định)*. Không thêm migration, phụ thuộc hay điều khiển tiến trình qua web.
3. Sinh lại API types, thêm ca kiểm tra quyền, thêm/sửa nguồn, trạng thái chờ và khung cũ. Giữ tương thích worker gửi frame không kèm phiên bản và hai luồng MJPEG hiện có. Worker phát clip với `--video` không xác nhận nguồn camera đã lưu.
4. Bổ sung hướng dẫn iPhone qua Wi-Fi và USB trên Fedora vào `docs/04-guides/dev-setup.md`.

### Acceptance criteria bổ sung

- [x] AC9: Quản trị viên mở biểu mẫu trên live view để thêm hoặc đổi nguồn cho giường hiện tại. Vai trò khác không thấy nút và phiên mở không cho đổi nguồn. Kiểm tra bằng `LiveViewPage.test.tsx` với quản trị viên, điều dưỡng và phiên đang mở.
- [x] AC10: Sau khi lưu, luồng hình cũ ẩn đi, giao diện báo chờ hoặc hướng dẫn chạy worker nếu chưa có heartbeat. Chỉ báo camera hoạt động khi nhận được cả hai khung mới thuộc cấu hình hiện tại. Kiểm tra bằng `test_camera_detail_confirms_only_fresh_frames_from_current_config` và `test_worker_online_then_offline`, cùng kiểm tra UI tự làm mới khi WebSocket mở.
- [x] AC11: [Hướng dẫn iPhone qua Wi-Fi và cáp USB](../04-guides/dev-setup.md#5-dùng-điện-thoại-làm-camera) có bước thiết lập nguồn, kiểm tra và kết nối từ giao diện. Playwright trên bản build xác nhận cấu hình URL RTSP và Webcam theo index, với API và hình ảnh giả lập. Còn bước thử trên iPhone thật.

### Review (2026-11-20) – Codex: Đạt

- `make check` xanh với PostgreSQL test riêng. Pytest: 1368 đạt, 6 test vision không được chọn. Vitest: 257 đạt. Web build thành công.
- Đối chiếu quyền ghi và audit với F03. Giao diện chờ cả hai khung của cấu hình đã lưu, worker phát clip ghi đè không xác nhận kết nối. Dùng lại các ngưỡng heartbeat và giới hạn tuổi khung của API.

## 14. Lối vào vùng giường và bố cục hai khung trên laptop (2026-11-20)

Trạng thái mở rộng: **Done**. Nguồn: yêu cầu người dùng 20/11, F07 R6–R7 và F08 R8 (QA#15, QA#26). F07 và F08 nền đã Done.

### Kế hoạch triển khai

1. Trong `web/src/pages/LiveView/LiveViewPage.tsx`, khi giường có camera, cho quản trị viên mở **Vẽ vùng giường** hoặc **Sửa vùng giường** theo cấu hình đã lưu. Mở đúng camera và vùng vẽ F08. Trong `CameraConfigPage.tsx`, cho phép quay lại Theo dõi trực tiếp của đúng giường khi đi từ lối này. Vai trò xem có hướng dẫn liên hệ quản trị viên khi vùng giường còn thiếu. Mọi nhãn trong `vi.ts`.
2. Dùng lại `RoiEditor` và `useSaveRoi`. Hướng dẫn chờ hình trực tiếp, bấm các góc mặt nệm theo vòng quanh, kéo chỉnh điểm, bấm **Lưu vùng giường**. Khi mất hình, giải thích cần kết nối lại để canh vùng đầu tiên trên hình, giữ khả năng sửa vùng đã lưu theo F08. Sau khi lưu, kiểm tra vùng xuất hiện đúng trên live view. ROI được lưu thủ công theo camera (QA#15); luồng đề xuất dùng lại xác thực và audit F08, giữ API và DB hiện tại.
3. Cho cụm hai khung dùng toàn bộ chiều rộng vùng nội dung. Hai khung cân nhau trên laptop, giữ tỷ lệ và hiển thị đủ ảnh; xếp dọc nếu vùng nội dung hẹp. Chuyển chi tiết trạng thái và sự kiện gần nhất xuống dưới, giữ trạng thái kết nối và thao tác camera cạnh mã giường *(giả định về bố cục)*.
4. Kiểm tra `LiveViewPage.test.tsx` và `CameraConfigPage.test.tsx` cho lối vào đúng camera, quyền, nhãn theo ROI và đường quay lại đúng giường. Kiểm tra trình duyệt ở 1280×720, 1366×768 và viewport hẹp; thao tác lưu vùng, so overlay với mặt nệm và xác nhận không cuộn ngang. Dùng iPhone A01 qua DroidCam với giường mô phỏng, kiểm tra lại vùng khi đổi góc. Chạy `make check` sau khi triển khai.

### Kiểm chứng

- [x] Quản trị viên thấy **Vẽ vùng giường** cạnh thông báo thiếu vùng và **Sửa vùng giường** sau khi lưu. Điều dưỡng chỉ thấy hướng dẫn. Trang cấu hình giữ đường quay lại đúng giường theo camera; lối vào từ Quản lý giường vẫn quay lại Quản lý giường.
- [x] Khi camera chưa có hình, không tạo vùng đầu tiên trên nền trống. Vùng đã lưu vẫn sửa được theo F08. Trình vẽ nhắc chuyển sang **Làm mờ khuôn mặt** để thấy mặt nệm nếu camera đang chỉ hiển thị skeleton.
- [x] Playwright trên bản build với camera giả lập vẽ bốn góc, lưu, quay lại đúng giường và kiểm tra overlay theo kích thước ảnh sau resize. Mỗi khung đo được 491 px ở 1280×720 và 534 px ở 1366×768; hai khung xếp dọc ở 640 px và 390 px, không cuộn ngang. Còn nghiệm thu lưu vùng giường với iPhone thật trên giường mô phỏng.
- [x] Review Codex đạt. `make check` xanh với 1368 test Python, 261 test web và build. Thao tác lưu dùng lại API F08 và quyền quản trị hiện có.

## 15. Trạng thái gọn và nhật ký cạnh khung quan sát (2026-11-20)

Trạng thái mở rộng: **Done**. Nguồn: yêu cầu người dùng, F07, F17/F20/F22 và QA#29. Giữ nguyên kho metadata vận hành của F17 và cách trình bày riêng tư F28.

### Hiện trạng đã đối chiếu

- PostgreSQL lưu sự kiện theo giường, camera và phiên nếu có, thời điểm, loại, ưu tiên, chất lượng, độ tin cậy và lý do kỹ thuật. Cảnh báo liên kết sự kiện và có trạng thái, người/thời điểm tiếp nhận, kết quả, ghi chú, người/thời điểm xử lý. Lịch sử ghép sự kiện và thao tác từ audit. Khung live và trạng thái hiện tại chỉ ở RAM; QA#29 quy định không lưu ảnh hoặc video vận hành.
- **Cảnh báo → Xem chi tiết** hiển thị metadata và liên kết theo dõi/lịch sử. Toast không có thao tác mở chi tiết. Live view chỉ lấy một sự kiện gần nhất và hiển thị dưới dạng văn bản. DB A01 tại lúc rà soát có 2 sự kiện, 1 cảnh báo. Sự kiện camera hoạt động lại 23:26:28 là nhật ký, cảnh báo mất kết nối trước đó đang chờ tiếp nhận.

### Kế hoạch triển khai

1. Trong `LiveViewPage.tsx`, gom **trạng thái camera**, **trạng thái quan sát + lý do** và **giờ cập nhật quan sát** thành dải ngắn cạnh video. Sắp gọn phần đầu trang để hai khung vẫn giữ chiều rộng hiện tại và thấy được trạng thái chính trong cùng viewport laptop. Khi không đủ dữ liệu quan sát, chỉ hiện lý do cụ thể một lần. Dùng chi tiết thu gọn cho vận động, nghỉ/hoạt động và khuôn mặt; giữ riêng các giá trị hoặc tín hiệu đang có. Phân biệt mất kết nối, chưa có vùng giường, chưa có dữ liệu và không thấy người trong vùng bằng tín hiệu hiện có, không đổi rule engine.
2. Ngay dưới hai khung chia hai cột theo chiều rộng vùng nội dung. Trái **Quan sát hiện tại**, phải **Nhật ký gần đây**. Dùng `useEvents` cho khoảng 4 sự kiện mới theo giường *(giả định)*, mỗi dòng có giờ, tên và mức/nhãn trạng thái nếu có. Giới hạn chiều cao danh sách desktop để cập nhật không đẩy video khỏi tầm nhìn; xếp dọc khi hẹp. Giữ link **Lịch sử theo dõi** đã lọc đúng giường/phiên. Thời gian sự kiện tách khỏi giờ cập nhật trạng thái.
3. Cho bấm dòng nhật ký để xem tóm tắt sự kiện tại chỗ. Dòng có cảnh báo tải chi tiết từ API F19 và dùng lại `AlertDetailModal`. Thêm thao tác **Xem chi tiết** vào toast để mở đúng cảnh báo theo ID; quyền và quy trình tiếp nhận hiện có theo F19/F20. Dùng lại nhãn và màu mức độ, không thêm API hay bảng dữ liệu. Mọi nhãn trong `vi.ts`.
4. Dùng màu theo ý nghĩa: trung tính cho trạng thái chưa có/nhật ký, xanh cho kết nối hoạt động, hổ phách cho thiếu quan sát/cần chú ý, đỏ mang tính vận hành khi mất kết nối hoặc cảnh báo ưu tiên cao. Luôn kèm nhãn chữ. Chỉ làm nổi chuyển trạng thái có ý nghĩa, tránh nháy màu theo nhịp cập nhật giờ. Màu và độ tương phản kiểm tra cùng UI sau khi triển khai.
5. Test live view với dữ liệu đủ/thiếu, camera offline, không có sự kiện, sự kiện chỉ thuộc nhật ký và sự kiện có cảnh báo; test mở đúng cảnh báo từ toast, không mở nhầm giường khi đổi lựa chọn. Kiểm tra ở 1280×720, 1366×768 và màn hình hẹp, cuộn danh sách và xem chi tiết, kiểm chứng hai video và thông tin chính cùng tầm nhìn khi bắt đầu. Chạy `make check` sau khi triển khai.

### Kiểm chứng triển khai

- [x] `LiveViewPage.test.tsx` kiểm tra trạng thái thay đổi, lý do quan sát xuất hiện một lần, chi tiết thu gọn, trạng thái cũ được ẩn khi camera offline, và mở đúng sự kiện/cảnh báo.
- [x] `AlertsPage.test.tsx` kiểm tra mở từ toast theo đúng ID khi cảnh báo chưa nằm trong danh sách. Playwright kiểm tra lại luồng toast và nhật ký trên bản build với dữ liệu giả lập, kể cả sau khi đổi giường.
- [x] Playwright đo mỗi video rộng 491 px ở 1280×720, 534 px ở 1366×768. Hai video và phần đầu nhật ký cùng trong viewport; nhật ký cuộn độc lập. Ở 390 px các cột xếp dọc. Nhãn thiếu quan sát dùng chữ rõ trên nền hổ phách (đo tương phản 18,76:1 với giao diện sáng).
- [x] Review Codex đạt. `make check` xanh (1368 test Python, 265 test web và build); lặp kiểm tra format, lint, typecheck, import và API types sau lần chỉnh màu cuối.

## 16. Một khung camera và cột thông tin (2026-11-21)

Nguồn: yêu cầu người dùng 21/11 sau khi thử bố cục mục 15. Bố cục này thay cách xếp các khung trên màn hình ở các mục trước.

### Kế hoạch và kiểm chứng

- Dùng một khung video bên trái. Bộ chọn chế độ nằm dưới khung, chuyển giữa video gốc, làm mờ và skeleton theo quyền F28. Khi chọn skeleton, dùng luồng skeleton sẵn có và vùng đã render trong khung. Các chế độ hình còn lại dùng khung theo quyền riêng tư và lớp phủ vùng giường của F07.
- Gom trạng thái kết nối, phiên, lý do quan sát, nút cấu hình vùng giường, chi tiết và nhật ký trong một cột bên phải. Nhật ký vẫn cuộn riêng, mở được cảnh báo theo ID; màn hình hẹp xếp khung camera trước thông tin.
- `LiveViewPage.test.tsx` kiểm tra chế độ làm mờ và skeleton chỉ hiện một luồng. Playwright với dữ liệu giả lập xác nhận chuyển chế độ thay hình trong cùng chỗ, mở chi tiết và đổi giường. Khung quan sát đo 647 px ở 1280×720 và 705 px ở 1366×768, thông tin nằm cạnh video; 390 px xếp dọc.
