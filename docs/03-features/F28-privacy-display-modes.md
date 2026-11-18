# F28 – Chế độ riêng tư khi hiển thị

| Thuộc tính | Giá trị |
|---|---|
| Mã | F28 |
| Trạng thái | Done |
| Ưu tiên | MVP |
| Milestone | M4 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F07, F11 |
| Nhánh code | A (vision/engine) + C (frontend/test) |
| Nguồn | PDF §11 (tr.13), §14 (tr.16), §16 (tr.17), bảng tr.10; HS §6.3, §7.3; QA#29; A08 |

## 1. Mục tiêu

Giảm lượng hình ảnh nhận dạng mà người dùng phải xem trên dashboard, nhưng vẫn giữ nguyên khả năng phát hiện sự kiện (PDF §11, §16; HS §6.3). Mỗi camera có một trong ba chế độ hiển thị: **Video gốc** (`RAW`, chỉ dùng trong môi trường thử nghiệm), **Làm mờ khuôn mặt** (`BLUR`, mặc định) và **Chỉ skeleton + ROI** (`SKELETON`). Khung hình được render theo chế độ **ngay trong worker**, trước khi gửi lên API. Nhờ vậy ở chế độ `SKELETON`, ảnh gốc không rời khỏi tiến trình worker. HS §7.3 đặt "privacy mode" trong đầu ra tuần 9–10.

## 2. Phạm vi

**Trong phạm vi**
- `vision.render`: ba hàm render `RAW` / `BLUR` / `SKELETON`.
- Làm mờ dựa trên vùng đầu ước lượng từ pose (dùng chung hàm với F25).
- `PUT /api/v1/cameras/{id}/display-mode`, phân quyền, audit, tăng `config_version`.
- Worker áp dụng chế độ mới qua cơ chế poll cấu hình (F06).
- UI "Theo dõi trực tiếp": hiển thị chế độ hiện tại; ADMIN và CHARGE_NURSE đổi được.
- Replay có tùy chọn chế độ hiển thị cho video preview.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Lưu video hoặc ảnh (không làm; QA#29).
- Chế độ riêng tư theo từng người dùng hoặc theo phiên (không có trong nguồn).
- Kịch bản demo privacy (tùy chọn trong runbook → F30).
- Nhận diện danh tính, che mặt dựa trên nhận diện (không làm; PDF §4.2).

## 3. Yêu cầu chi tiết

- **R1.** Ba chế độ theo camera, lưu ở `cameras.display_mode` (`RAW`, `BLUR`, `SKELETON`). Mặc định `BLUR`. Giá trị thiếu hoặc không hợp lệ phía worker → dùng `BLUR`. *(PDF §11; HS §6.3; A08; giả định cho phần dự phòng)*
- **R2.** Chỉ ADMIN và CHARGE_NURSE đổi được chế độ; NURSE và DOCTOR nhận 403 `FORBIDDEN`. Mỗi lần đổi ghi audit `camera.update_display_mode` (before/after) và tăng `config_version`. *(api-conventions.md ma trận quyền; giả định QA#18)*
- **R3.** Worker nhận chế độ mới qua `GET /internal/v1/cameras/{id}/config` và áp dụng trong ≤ 5 giây. *(A02; F06 AC3)*
- **R4.** Render diễn ra trong worker (`vision.render`) trước `POST /internal/v1/cameras/{id}/frame`. API và MJPEG chỉ chuyển tiếp JPEG đã render. *(overview.md mục 2, 7)*
- **R5.** `SKELETON`: khung gửi đi được vẽ trên nền trơn mới tạo, chỉ gồm Bed ROI và skeleton của các người pose phát hiện. **Không** chứa pixel nào lấy từ ảnh gốc. *(PDF §11, §16)*
- **R6.** `BLUR`: làm mờ (pixelate) vùng đầu của **mọi** người pose phát hiện (tối đa `pose.num_poses`). Vùng đầu lấy từ keypoint pose (hàm của F25), nới theo `privacy.head_box_scale`. Làm mờ **không** phụ thuộc Face Landmarker: mặt quay đi hay `face_status ≠ OK` vẫn mờ. *(PDF bảng tr.10 "OpenCV + landmarks"; giả định: khóa mới `privacy.head_box_scale`, `privacy.pixelate_blocks`)*
- **R7.** Dự phòng khi không ước lượng được vùng đầu trong frame hiện tại: dùng vùng đầu gần nhất nếu chưa quá `privacy.head_hold_s`; quá thời gian đó thì làm mờ **toàn khung**. *(giả định: ưu tiên riêng tư khi pose mất người; khóa mới `privacy.head_hold_s`)*
- **R8.** Chế độ hiển thị **không** ảnh hưởng engine: cùng input cho cùng danh sách sự kiện ở cả ba chế độ. *(PDF §11, §16)*
- **R9.** `postcare replay` có tùy chọn `--display-mode RAW|BLUR|SKELETON` cho video `--preview` (mặc định `BLUR`). *(giả định: để kiểm chứng R8 và chuẩn bị demo)*
- **R10.** UI "Theo dõi trực tiếp" hiện tên chế độ: "Video gốc" / "Làm mờ khuôn mặt" / "Chỉ skeleton + ROI" (glossary.md). Chỉ ADMIN và CHARGE_NURSE thấy nút đổi. Text nằm trong `vi.ts`. *(PDF §9.1 (tr.11); glossary.md)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/vision/render.py` (hoặc gói `vision/render/`): `render_raw`, `render_blur`, `render_skeleton`.
  - `server/src/postcare/vision/inference/head_region.py`: dùng chung với F25 (feature nào làm trước thì tạo).
  - `server/src/postcare/worker/`: chọn hàm render theo `display_mode` của cấu hình.
  - `server/src/postcare/api/v1/cameras.py`, `server/src/postcare/domain/cameras.py`: endpoint đổi chế độ, audit.
  - `server/src/postcare/replay/`: tùy chọn `--display-mode`.
  - `web/src/pages/LiveView/DisplayModeControl.tsx`, `web/src/i18n/vi.ts`.
- **Dữ liệu:** `cameras.display_mode` (enum `display_mode`, mặc định `BLUR`), `cameras.config_version`, `audit_logs` ([data-model.md](../02-architecture/data-model.md)). Không cần migration nếu F01 đã tạo cột.
- **API:** `PUT /api/v1/cameras/{id}/display-mode` `{display_mode}` → camera; `GET /internal/v1/cameras/{id}/config` trả `display_mode` ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** "Theo dõi trực tiếp": nhãn chế độ và nút đổi theo vai trò.
- **Cấu hình:** khóa mới *(giả định)* trong mục `privacy` của `config/engine.default.yaml`: `privacy.head_box_scale`, `privacy.pixelate_blocks`, `privacy.head_hold_s`. Dùng lại `pose.num_poses`, `pose.min_keypoint_visibility`.

## 5. Acceptance criteria

- [x] **AC1.** Mỗi camera có 3 chế độ, mặc định `BLUR`. ADMIN và CHARGE_NURSE đổi được (ghi audit, tăng `config_version`, worker áp dụng ≤ 5 giây); NURSE và DOCTOR → 403. *(PDF §11; A08; api-conventions.md)* — *Kiểm chứng:* API test `test_put_display_mode_by_role` (4 vai trò), `test_display_mode_change_writes_audit_and_bumps_version`; test tích hợp worker với `FakeFrameSource` nhận chế độ mới sau một chu kỳ poll.
- [x] **AC2.** Chế độ `SKELETON`: khung gửi đi không chứa pixel ảnh gốc. *(PDF §11, §16)* — *Kiểm chứng:* test `test_skeleton_render_independent_of_source_pixels`: render cùng pose trên hai ảnh nhiễu ngẫu nhiên khác nhau → hai output giống hệt từng byte.
- [x] **AC3.** Chế độ `BLUR` làm mờ vùng đầu lấy từ pose, kể cả khi Face Landmarker không thấy mặt; không ước lượng được vùng đầu quá `privacy.head_hold_s` → mờ toàn khung. *(PDF bảng tr.10; HS §6.3)* — *Kiểm chứng:* test `test_blur_uses_pose_head_region_without_face` (vùng đầu khác ảnh gốc, vùng ngoài giữ nguyên), `test_blur_falls_back_to_full_frame`.
- [x] **AC4.** Replay cùng một video ở 3 chế độ cho cùng danh sách sự kiện. *(PDF §11, §16)* — *Kiểm chứng:* test `test_display_mode_does_not_change_events` (replay từ fixture observation với 3 giá trị `--display-mode`, so sánh `events.jsonl`).
- [x] **AC5.** "Theo dõi trực tiếp" hiện tên chế độ hiện tại bằng tiếng Việt; chỉ ADMIN và CHARGE_NURSE thấy nút đổi. *(PDF §9.1; glossary.md)* — *Kiểm chứng:* component test `DisplayModeControl.test.tsx` cho 4 vai trò; `vi.test.ts` quét từ cấm.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API + tích hợp | `test_put_display_mode_by_role`, `test_display_mode_change_writes_audit_and_bumps_version`, `test_worker_applies_new_display_mode` | NURSE/DOCTOR/FAMILY → 403; giá trị `"FOO"` → 422 `VALIDATION_ERROR` (cách xử lý body sai chung của API) |
| AC2 | unit (render) | `test_skeleton_render_independent_of_source_pixels` | — |
| AC3 | unit (render) | `test_blur_uses_pose_head_region_without_face`, `test_blur_two_people`, `test_blur_falls_back_to_full_frame` | Không có người quá `privacy.head_hold_s` → mờ toàn khung, không trả ảnh gốc |
| AC4 | tích hợp (replay) | `test_display_mode_does_not_change_events` | — |
| AC5 | component | `DisplayModeControl.test.tsx` | DOCTOR không thấy nút đổi |
| — | thủ công | Xem MJPEG ở 3 chế độ với camera thật; quay mặt đi khi ở `BLUR` → vẫn mờ | — |

## 7. Giả định

- *(giả định A08)* Chế độ mặc định là "Làm mờ khuôn mặt".
- *(giả định QA#18)* ADMIN và CHARGE_NURSE được đổi chế độ.
- *(giả định)* Làm mờ bằng pixelate; khóa mới `privacy.head_box_scale`, `privacy.pixelate_blocks`, `privacy.head_hold_s`.
- *(giả định)* Mất vùng đầu quá `privacy.head_hold_s` → mờ toàn khung.
- *(giả định, quyết định của điều phối, ưu tiên riêng tư)* `privacy.head_box_scale = 2.4` (trước là 1.8): keypoint đầu của pose lệch so với mặt thật khi mặt nghiêng cận cảnh, nên nới rộng vùng mờ. Khóa này không tính vào `config_hash`, không đổi sự kiện.
- *(giả định)* Tùy chọn `--display-mode` của replay.
- *(giả định)* Giới hạn: pose chỉ phát hiện tối đa `pose.num_poses` người; người thứ ba trở đi có thể không được làm mờ. Ghi vào runbook (F30): dùng `SKELETON` khi có nhiều người trong khung.

## 8. Câu hỏi mở

- Khóa `privacy.*` nằm trong `config/engine.default.yaml` nên sẽ làm đổi `config_hash` dù không ảnh hưởng sự kiện. Sau khi chốt ngưỡng (F29), sửa các khóa này sẽ làm `--frozen` từ chối chạy. Có nên loại mục `privacy` khỏi phép tính hash hoặc tách ra file riêng không? **Không chặn**; mặc định giữ trong file và chốt giá trị trước F29.

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

Khảo sát (2026-11-18): cột `cameras.display_mode` (mặc định `BLUR`), `PrivacyConfig` (`head_box_scale`, `pixelate_blocks`, `head_hold_s`) trong `config/engine.default.yaml` và việc loại `privacy.*` khỏi `config_hash` đã có (F01, F10), nên câu hỏi mở mục 8 đã được giải quyết: đổi `privacy.*` không đổi hash. `head_region.estimate_head_box` (F25) dùng lại được. Override theo camera không cho `privacy.*` (F08), nên mọi camera dùng cùng một bộ `privacy.*` của file mặc định.

1. **Render (R4–R7).** `vision/render.py` (đã có `encode_jpeg`, `draw_debug_overlay`):
   - `resolve_display_mode(value) -> DisplayMode`: thiếu/không hợp lệ → `BLUR` (R1).
   - `pixelate(region, blocks)`; `render_raw(image)` (bản sao); `render_blur(image, boxes, blocks)` (`boxes=None` → mờ toàn khung); `render_skeleton(shape, persons, roi)` chỉ nhận kích thước khung, vẽ trên nền trơn mới (R5: không thể dùng pixel gốc).
   - `PrivacyRenderer(privacy, min_visibility)` có trạng thái giữ vùng đầu: mọi người phát hiện đều có vùng đầu → dùng và nhớ (`ts_ms`); có người thiếu vùng đầu hoặc không có người → hợp với vùng đầu đã nhớ nếu chưa quá `head_hold_s` (tính bằng `ts_ms` của khung, không đọc đồng hồ), quá thì mờ toàn khung (R7). `ts_ms` lùi (nguồn mở lại) → coi như hết hạn. `render(image, persons, ts_ms, mode, roi)`.
2. **Worker (R1, R3, R4, R8).** `WorkerConfig.display_mode`: validator trước khi parse, giá trị thiếu/lạ → `BLUR` + WARNING. Worker giữ `persons` của khung vừa xử lý (không có engine vì chưa có ROI → không người, BLUR mờ toàn khung, SKELETON nền trơn) và gọi `PrivacyRenderer.render` trước `encode_jpeg`. Tham số `renderer` (mặc định đọc `config/engine.default.yaml`). `engine_key` bỏ `config_version` (ROI, ngưỡng, phiên, giường đã nằm trong khóa), để đổi chế độ hiển thị không tạo lại engine (R8) *(giả định)*.
3. **API (R2).** `PUT /api/v1/cameras/{id}/display-mode` `{display_mode}` → `CameraOut`; guard `require_roles(ADMIN, CHARGE_NURSE)`; `camera_config.update_display_mode`: khóa dòng, đổi → `config_version += 1` + audit `camera.update_display_mode` `{display_mode, config_version}` cùng transaction; giá trị y hệt → không tăng, không audit (như ROI). Camera không tồn tại → 404. Giá trị lạ → 422 `VALIDATION_ERROR` (cách mọi endpoint xử lý body sai; mục 6 ghi 400 là lệch với `api/errors.py`, sửa theo code). `make gen-api-types`.
4. **Replay (R8, R9).** `replay_video(..., display_mode=BLUR)`: `_Preview` render privacy rồi vẽ lớp debug; `run.json` thêm `display_mode`. CLI `--display-mode RAW|BLUR|SKELETON` (mặc định `BLUR`; giá trị lạ → lỗi typer).
5. **Web (R10).** `web/src/pages/LiveView/DisplayModeControl.tsx`: nhãn chế độ hiện tại (từ `useCameraDetail`), ADMIN/CHARGE_NURSE thấy `SegmentedControl` đổi chế độ (`useSaveDisplayMode`, invalidate `cameras`); lỗi → thông báo chung. Text `vi.displayMode.*`, `vi.live.displayMode*` trong `vi.ts`.
6. **Test trước:**
   - `tests/vision/…` không cần model → đặt ở `tests/render/test_privacy_render.py`: `test_skeleton_render_independent_of_source_pixels` (hai ảnh nhiễu khác nhau → output giống từng byte; màu đánh dấu duy nhất của nguồn không xuất hiện; cả JPEG), `test_blur_uses_pose_head_region_without_face` (không keypoint mắt/mũi, chỉ tai → vẫn mờ; vùng ngoài giữ nguyên), `test_blur_two_people`, `test_blur_holds_last_head_box`, `test_blur_falls_back_to_full_frame` (không người quá `head_hold_s` → khác ảnh gốc ở mọi khối), `test_invalid_display_mode_defaults_to_blur`, `test_raw_render_is_copy`.
   - `tests/api/test_camera_display_mode.py`: `test_put_display_mode_by_role` (ADMIN, CHARGE_NURSE 200; NURSE, DOCTOR, FAMILY 403), `test_display_mode_change_writes_audit_and_bumps_version`, giá trị y hệt không audit, `"FOO"` → 422, camera không tồn tại → 404, config nội bộ trả chế độ mới.
   - `tests/worker/test_worker_display_mode.py`: `test_worker_applies_new_display_mode` (khung SKELETON trong ≤ 5 s sau khi đổi; engine không tạo lại), `test_worker_invalid_display_mode_uses_blur`, khung SKELETON không chứa màu nguồn.
   - `tests/replay/test_display_mode_events.py`: `test_display_mode_does_not_change_events` (3 chế độ, `events.jsonl`/`frames.jsonl` giống nhau), CLI nhận `--display-mode`, giá trị lạ bị từ chối.
   - `web/src/pages/LiveView/DisplayModeControl.test.tsx` (4 vai trò; DOCTOR/NURSE không thấy nút; đổi gọi PUT).
7. **Doc.** `api-conventions.md` (endpoint, ma trận, audit), `event-engine.md` (ý nghĩa khóa `privacy.*`), F06/F07/F12 §10 nếu cần, `README.md` (bỏ ghi chú RAW tạm), `overview.md` nếu cần, spec §10.

Rủi ro: pixelate 12 khối trên vùng đầu lớn vẫn có thể nhận ra hình dáng → kiểm bằng mắt khi replay; chi phí render ở 5 fps nhỏ (chỉ khung gửi đi mới render).

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-18, builder (trạng thái In review).** Nhánh `feat/F28-privacy-modes`.

Đã làm:
- `vision/render.py`: `resolve_display_mode` (thiếu/lạ → `BLUR`), `pixelate`, `render_raw`, `render_blur`, `render_skeleton(shape, persons, roi)` (chỉ nhận kích thước khung), `PrivacyRenderer` (giữ vùng đầu theo `ts_ms`, `privacy.head_hold_s`; có người thiếu vùng đầu hoặc không có người → hợp với vùng đã nhớ, hết hạn → mờ toàn khung; `ts_ms` lùi → hết hạn).
- Worker: `WorkerConfig.display_mode` dự phòng `BLUR` + WARNING; render trước `encode_jpeg`; `Worker(renderer=…)`, `default_renderer(engine_config)` trong `postcare worker`. Chưa có ROI → không chạy pose → BLUR mờ toàn khung, SKELETON nền trơn. `engine_key` bỏ `config_version`: đổi chế độ hiển thị không tạo lại engine (giả định; ROI/ngưỡng/phiên/giường vẫn trong khóa).
- API `PUT /api/v1/cameras/{id}/display-mode` (`require_roles(ADMIN, CHARGE_NURSE)`, `camera_config.update_display_mode`, khóa dòng, audit `camera.update_display_mode`, giá trị y hệt → không tăng version/không audit, camera ngừng dùng → 404). `make gen-api-types`.
- Replay `--display-mode RAW|BLUR|SKELETON` (mặc định `BLUR`; với `--from-observations` → lỗi), `run.json.display_mode`.
- Web: `DisplayModeControl.tsx` trong "Theo dõi trực tiếp" (nhãn cho mọi vai trò; `SegmentedControl` cho ADMIN/CHARGE_NURSE; nhắc "Video gốc chỉ dùng trong môi trường thử nghiệm"), `useSaveDisplayMode`, text `vi.displayMode`, `vi.live.displayMode*`.
- Doc: `api-conventions.md`, `event-engine.md` (ý nghĩa khóa `privacy.*`), `dev-setup.md`, `README.md`.

Bằng chứng AC:
- AC1: `tests/api/test_camera_display_mode.py` (`test_put_display_mode_by_role` 4 vai trò, FAMILY 403, 401, `test_display_mode_change_writes_audit_and_bumps_version` + config nội bộ trả chế độ mới, giá trị lạ 422, 404, mặc định `BLUR`); `tests/worker/test_worker_display_mode.py::test_worker_applies_new_display_mode` (áp dụng ≤ 5 s, engine không tạo lại), `test_worker_invalid_or_missing_display_mode_uses_blur`.
- AC2: `tests/render/test_privacy_render.py::test_skeleton_render_independent_of_source_pixels` (hai ảnh nhiễu + ảnh màu đánh dấu → output và JPEG giống từng byte, không có màu nguồn), `test_skeleton_only_needs_frame_shape`; `test_skeleton_frames_do_not_depend_on_source_pixels` (worker: mọi JPEG SKELETON giống hệt dù khung nguồn khác nhau).
- AC3: `test_blur_uses_pose_head_region_without_face` (chỉ thấy tai, không Face Landmarker; ≤ blocks² màu trong vùng đầu, ngoài vùng giữ nguyên), `test_blur_two_people`, `test_blur_holds_last_head_box_within_hold`, `test_blur_falls_back_to_full_frame` (không người / không thấy đầu), `test_blur_partial_head_detection_without_memory_is_full_frame`, `test_blur_timestamp_going_back_expires_hold`.
- AC4: `tests/replay/test_display_mode_events.py::test_display_mode_does_not_change_events` (3 chế độ, `events.jsonl` và `frames.jsonl` giống nhau); CLI nhận/ từ chối `--display-mode`.
- AC5: `web/src/pages/LiveView/DisplayModeControl.test.tsx` (3 nhãn tiếng Việt, không hiện mã; ADMIN/CHARGE_NURSE thấy nút; NURSE/DOCTOR không; đổi gửi PUT); `vi.test.ts` xanh.

Kiểm tra: `make check` exit 0 (pytest 1269 passed, vitest 203 passed), `make test-vision` 6 passed (`POSTCARE_MODELS_DIR` trỏ checkout chính).

Thủ công (replay `--preview`, model lite mặc định, `runs/` không commit):
- pexels-6130032 (nằm nghiêng, cận mặt; 137 khung, 0 sự kiện) và pexels-8090735 (ngồi mép giường; 115 khung, 1 sự kiện `BED_EDGE`): `events.jsonl` và `frames.jsonl` cùng md5 ở cả 3 chế độ.
- Khung xem: RAW giữ nguyên ảnh; BLUR pixelate thành khối vùng đầu, phần còn lại giữ nguyên; SKELETON nền xám đậm chỉ có ROI vàng, skeleton xanh và bảng debug, không thấy giường, người hay đồ vật.
- Giới hạn thấy được: ở pexels-6130032 (mặt nghiêng cận cảnh), keypoint đầu của pose lệch so với mặt thật, nên ô mờ phủ phần lớn mặt nhưng mép mũi/cằm có lúc lộ ở rìa. Có thể tăng `privacy.head_box_scale` (1.8 → khoảng 2.2–2.5) sau khi xem thêm clip (khóa này không tính vào `config_hash`). Review đã chốt 2.4 (xem đoạn dưới).
- Chưa thử MJPEG với camera thật (ca thủ công của mục 6).

Lệch với spec: giá trị lạ → 422 (không phải 400) theo `api/errors.py`; `engine_key` bỏ `config_version` (giả định, để R8 giữ cả khi đổi chế độ lúc đang chạy).


**2026-11-18, review: Đạt.** Sửa theo review (cùng nhánh, đã merge `main` trước; xung đột import ở `LiveViewPage.tsx` với F26 `FaceSignalsPanel`, giữ cả hai):
1. `worker/loop.py` `_maybe_send_frame`: render + `encode_jpeg` bọc `try/except Exception`. Lỗi → WARNING, bỏ khung đó, **không bao giờ** gửi ảnh gốc thay thế; `step()` chạy tiếp. Test trước: `tests/worker/test_worker_display_mode.py::test_render_error_drops_frame_and_keeps_running` (renderer luôn raise → không có `POST /frame`; engine vẫn xử lý khung, state và heartbeat vẫn gửi).
2. `privacy.head_box_scale` 1.8 → 2.4 (`config/engine.default.yaml`, `event-engine.md`, mục 7). Chạy lại pexels-6130032 (mặt nghiêng cận cảnh), `BLUR`: ở khung 60 và 110, ô mờ phủ hết mặt (mắt, mũi, miệng, cằm). Ở khung 20 (đầu ngửa), mép môi/đầu mũi nằm sát rìa trái ô mờ, lộ một phần nhỏ. Với `head_box_scale` 1.8 và 2.4, `config_hash` (886768c0eef0…), `events.jsonl` và `frames.jsonl` giống hệt nhau. `frames.jsonl` khác lần chạy trước review vì code engine mới merge từ `main`, không phải vì khóa privacy.

## 11. Definition of Done

- [x] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [x] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [x] Doc liên quan đã cập nhật cùng PR.
- [x] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
