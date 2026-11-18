# F28 – Chế độ riêng tư khi hiển thị

| Thuộc tính | Giá trị |
|---|---|
| Mã | F28 |
| Trạng thái | In progress |
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

- [ ] **AC1.** Mỗi camera có 3 chế độ, mặc định `BLUR`. ADMIN và CHARGE_NURSE đổi được (ghi audit, tăng `config_version`, worker áp dụng ≤ 5 giây); NURSE và DOCTOR → 403. *(PDF §11; A08; api-conventions.md)* — *Kiểm chứng:* API test `test_put_display_mode_by_role` (4 vai trò), `test_display_mode_change_writes_audit_and_bumps_version`; test tích hợp worker với `FakeFrameSource` nhận chế độ mới sau một chu kỳ poll.
- [ ] **AC2.** Chế độ `SKELETON`: khung gửi đi không chứa pixel ảnh gốc. *(PDF §11, §16)* — *Kiểm chứng:* test `test_skeleton_render_independent_of_source_pixels`: render cùng pose trên hai ảnh nhiễu ngẫu nhiên khác nhau → hai output giống hệt từng byte.
- [ ] **AC3.** Chế độ `BLUR` làm mờ vùng đầu lấy từ pose, kể cả khi Face Landmarker không thấy mặt; không ước lượng được vùng đầu quá `privacy.head_hold_s` → mờ toàn khung. *(PDF bảng tr.10; HS §6.3)* — *Kiểm chứng:* test `test_blur_uses_pose_head_region_without_face` (vùng đầu khác ảnh gốc, vùng ngoài giữ nguyên), `test_blur_falls_back_to_full_frame`.
- [ ] **AC4.** Replay cùng một video ở 3 chế độ cho cùng danh sách sự kiện. *(PDF §11, §16)* — *Kiểm chứng:* test `test_display_mode_does_not_change_events` (replay từ fixture observation với 3 giá trị `--display-mode`, so sánh `events.jsonl`).
- [ ] **AC5.** "Theo dõi trực tiếp" hiện tên chế độ hiện tại bằng tiếng Việt; chỉ ADMIN và CHARGE_NURSE thấy nút đổi. *(PDF §9.1; glossary.md)* — *Kiểm chứng:* component test `DisplayModeControl.test.tsx` cho 4 vai trò; `vi.test.ts` quét từ cấm.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API + tích hợp | `test_put_display_mode_by_role`, `test_display_mode_change_writes_audit_and_bumps_version`, `test_worker_applies_new_display_mode` | NURSE/DOCTOR → 403; giá trị `"FOO"` → 400 `VALIDATION_ERROR` |
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

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
