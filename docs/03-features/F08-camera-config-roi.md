# F08 – Cấu hình camera và Bed ROI

| Thuộc tính | Giá trị |
|---|---|
| Mã | F08 |
| Trạng thái | Done <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 3 phiên |
| Phụ thuộc | F07 |
| Nhánh code | B+C |
| Nguồn | PDF §7.2 (tr.9), §9.1 (tr.11); HS §4.1, §5.5; QA#15, QA#22; A02 |

## 1. Mục tiêu

Cho quản trị viên vẽ vùng giường (Bed ROI) dạng polygon bằng cách click lên khung hình camera (PDF §7.2: "Bed ROI được cấu hình dưới dạng polygon khi cài camera"; QA#15), chỉnh các ngưỡng quan sát chính của camera và kiểm tra chất lượng hình ảnh (PDF §9.1: màn hình "Cấu hình camera"). Vị trí camera được chốt qua thử nghiệm và khác nhau giữa các giường (HS §4.1), nên ROI và ngưỡng được lưu theo từng camera. Ngưỡng nằm trong cấu hình, không viết cứng (QA#22). Worker nhận cấu hình mới trong ≤5 giây (A02).

## 2. Phạm vi

**Trong phạm vi**
- API lưu ROI, API đọc/lưu override ngưỡng theo camera.
- Kiểm tra polygon ở backend: ≥3 điểm, toạ độ 0–1, không tự cắt.
- Màn hình "Cấu hình camera": vẽ, sửa, xóa điểm polygon trên khung hình; form ngưỡng chính; nút "Khôi phục mặc định"; chỉ báo độ sáng trung bình và FPS.
- Tăng `config_version` và ghi audit mỗi lần lưu.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Engine dùng ROI và ngưỡng để tính trạng thái (→ F13–F15, F17).
- Đổi chế độ hiển thị (→ F28).
- Chốt ngưỡng bằng hash cho đánh giá chính thức (→ F29).
- Hiệu chỉnh ngưỡng tự động *(không có trong nguồn; hiệu chỉnh là việc thủ công trên tập dev, HS §5.5)*.
- Đánh giá "tốt/kém" cho độ sáng/FPS *(nguồn không có ngưỡng; chỉ hiển thị số liệu)*.

## 3. Yêu cầu chi tiết

- **R1.** `PUT /api/v1/cameras/{id}/roi` `{roi_polygon: [[x, y], …]}` *(api-conventions.md; data-model.md `cameras.roi_polygon`)*. Chỉ ADMIN; vai trò khác → 403 *(api-conventions.md, bảng phân quyền)*.
- **R2.** Backend kiểm tra polygon; vi phạm → 400 `INVALID_ROI_POLYGON`, `details.reason` cho biết lý do *(api-conventions.md; data-model.md)*:
  - ≥3 điểm *(data-model.md `cameras.roi_polygon`)*;
  - mọi toạ độ là số trong [0, 1] *(glossary.md "Vùng giường")*;
  - không tự cắt: không có hai cạnh không kề nhau giao nhau, kể cả chồng lên nhau *(data-model.md `cameras.roi_polygon`)*;
  - không có hai điểm liên tiếp trùng nhau và diện tích khác 0 (không phải các điểm thẳng hàng) *(giả định: polygon suy biến cũng không dùng được)*;
  - tối đa 20 điểm *(giả định: đủ cho một giường, chặn dữ liệu bất thường)*.
- **R3.** Hàm kiểm tra polygon là hàm hình học thuần, đặt ở `postcare/schemas/roi.py` để API (F08) và replay (F12) dùng chung *(giả định vị trí; `schemas` chỉ dùng stdlib + pydantic)*. Web có bản kiểm tra tương đương để báo lỗi ngay khi vẽ; backend vẫn là nơi quyết định *(giả định)*.
- **R4.** `GET /api/v1/cameras/{id}/thresholds` → `{defaults, overrides, effective}` cho các ngưỡng chính; `PUT /api/v1/cameras/{id}/thresholds` `{thresholds: {…}}` thay toàn bộ override của camera *(api-conventions.md có PUT; GET là giả định để UI hiện giá trị mặc định)*:
  - `thresholds = {}` nghĩa là "Khôi phục mặc định" *(giả định cách biểu diễn)*;
  - override chỉ chấp nhận khóa có trong `config/engine.default.yaml` và giá trị cùng kiểu với giá trị mặc định; số phải ≥0; khóa lạ hoặc sai kiểu → 400 `VALIDATION_ERROR`, `details` chỉ rõ khóa *(giả định; QA#22)*;
  - khi F10 đã xong, kiểm tra bằng `EngineConfig` sau khi hợp nhất mặc định + override *(F10 AC2)*.
  - **an toàn (review F08; AGENTS.md quy tắc 6):** quy tắc nằm ở `config/camera_overrides.yaml`, không viết cứng *(giả định giá trị)*:
    - chỉ khóa trong `allowed` được override: `min_duration_s.*`, `pose.min_keypoint_visibility`, `quality.{low_quality_to_no_observation_s, restore_duration_s, observation_lost_event_s}`, `location.{edge_distance_torso, out_of_roi_margin_torso}`, `activity.{low_threshold, high_threshold}`, `posture.{lying_enter_deg, lying_exit_deg, sitting_enter_deg, sitting_exit_deg}`, `abnormal_movement.min_conditions`. Khóa khác (`privacy.*`, `face.*`, `pose.required_keypoints`, `pose.num_poses`, `debounce`, ngưỡng điều kiện của `abnormal_movement`…) → 400 "không được chỉnh theo camera";
    - giới hạn an toàn trên giá trị đang áp dụng (`limits`): `min_duration_s.*` 0,3–30 s; `pose.min_keypoint_visibility` 0,3–0,95; thời gian `quality.*` có sàn > 0; `location.edge_distance_torso` ≥ 0,05; `abnormal_movement.min_conditions` 2–5 (điều kiện hạ thấp C1/C4 vẫn bắt buộc trong engine và ngưỡng của nó không override được);
    - quan hệ (`relations`, theo `engine/posture.py`): `lying_enter_deg ≤ lying_exit_deg < sitting_exit_deg ≤ sitting_enter_deg`; `activity.low_threshold < activity.high_threshold`. Vi phạm → 400, `details.errors[].path` nêu cả hai khóa;
    - `GET /thresholds` trả thêm `rules` để web kiểm tra giống backend (ThresholdsForm).
- **R5.** Ngưỡng chính hiển thị trên form, chọn theo HS §5.5 ("thời gian duy trì, ngưỡng chất lượng, khoảng cách tới biên giường và mức thay đổi vận động") và ghi chú ở event-engine.md §6 ("ngưỡng posture được override theo từng camera"):
  - thời gian duy trì: các khóa `min_duration_s.*`;
  - chất lượng: `pose.min_keypoint_visibility`, `quality.low_quality_to_no_observation_s`;
  - khoảng cách tới biên giường: `location.edge_distance_torso`, `location.out_of_roi_margin_torso`;
  - mức vận động: `activity.low_threshold`, `activity.high_threshold`;
  - góc thân: `posture.lying_enter_deg`, `posture.lying_exit_deg`, `posture.sitting_enter_deg`, `posture.sitting_exit_deg`.
  - Danh sách khóa hiển thị đặt ở một chỗ duy nhất phía web *(giả định)*; nhãn tiếng Việt trong `vi.ts`.
- **R6.** Mỗi lần lưu ROI hoặc ngưỡng: tăng `cameras.config_version` và gọi `record_audit()` (`camera.update_roi`, `camera.update_thresholds`) với `before`/`after` *(data-model.md; api-conventions.md "Quy ước code backend")*.
- **R7.** Worker nhận ROI và ngưỡng mới trong ≤5 giây nhờ cơ chế `config_version` của F06 *(A02; ADR-0002)*.
- **R8.** Màn hình "Cấu hình camera" tại `/cameras/:id/config`, chỉ ADMIN *(PDF §9.1; api-conventions.md)*:
  - nền là khung hình trực tiếp (MJPEG của F07);
  - click lên ảnh → thêm điểm; kéo điểm → sửa vị trí; chọn điểm rồi bấm "Xóa điểm" → xóa; "Xóa tất cả" để vẽ lại *(QA#15)*;
  - toạ độ lưu là toạ độ chuẩn hóa 0–1 theo kích thước ảnh đang hiển thị (`x = px / width`, `y = py / height`) *(glossary.md "Vùng giường")*;
  - nút "Lưu vùng giường" bị khóa khi polygon chưa hợp lệ (<3 điểm hoặc tự cắt), kèm lý do tiếng Việt;
  - camera offline → vẫn hiện và sửa được polygon đã lưu trên nền trống, kèm cảnh báo "Mất kết nối camera" *(giả định)*.
- **R9.** Form ngưỡng hiện giá trị đang áp dụng, giá trị mặc định bên cạnh; nút "Lưu ngưỡng" và "Khôi phục mặc định" (có hộp thoại xác nhận) *(giả định hộp thoại)*.
- **R10.** Chỉ báo chất lượng hình ảnh: "Độ sáng trung bình" (0–255) và "FPS", lấy từ khối `runtime` của `GET /api/v1/cameras/{id}` (F06), làm mới mỗi 2 giây *(PDF §9.1 "kiểm tra chất lượng hình ảnh"; giả định chu kỳ)*. Chưa có heartbeat → "Chưa có dữ liệu".
- **R11.** Text giao diện nằm trong `web/src/i18n/vi.ts` *(ADR-0005; glossary.md)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/schemas/roi.py` (`RoiPolygon`, `validate_roi_polygon`, `segments_intersect`).
  - `server/src/postcare/domain/camera_config.py` (`update_roi`, `get_thresholds`, `update_thresholds`); đọc `config/engine.default.yaml` qua PyYAML.
  - `server/src/postcare/api/v1/cameras.py`: thêm `PUT /roi`, `GET/PUT /thresholds`.
  - `server/tests/schemas/test_roi.py`, `server/tests/api/test_camera_roi.py`, `test_camera_thresholds.py`, `server/tests/integration/test_worker_receives_roi.py`.
  - `web/src/pages/CameraConfig/CameraConfigPage.tsx`, `RoiEditor.tsx`, `ThresholdsForm.tsx`, `ImageQualityIndicator.tsx`.
  - `web/src/utils/polygon.ts` (kiểm tra tự cắt phía web), `web/src/pages/CameraConfig/thresholdKeys.ts`.
  - Test: `RoiEditor.test.tsx`, `ThresholdsForm.test.tsx`, `polygon.test.ts`.
- **Dữ liệu:** `cameras.roi_polygon`, `cameras.thresholds`, `cameras.config_version`; ghi `audit_logs` (xem [data-model.md](../02-architecture/data-model.md#cameras-f01)). Không có migration mới.
- **API:** `PUT /api/v1/cameras/{id}/roi`, `PUT /api/v1/cameras/{id}/thresholds` (xem [api-conventions.md](../02-architecture/api-conventions.md#danh-sách-endpoint-dự-kiến)); thêm `GET /api/v1/cameras/{id}/thresholds` *(giả định)*. Chạy `make gen-api-types`.
- **UI:** màn hình "Cấu hình camera". Text cần thêm vào `vi.ts`: `cameraConfig.title` ("Cấu hình camera"), `roi.title` ("Vùng giường"), `roi.hint` ("Click lên khung hình để thêm điểm"), `roi.deletePoint` ("Xóa điểm"), `roi.clear` ("Xóa tất cả"), `roi.save` ("Lưu vùng giường"), `roi.tooFewPoints` ("Cần ít nhất 3 điểm"), `roi.selfIntersect` ("Các cạnh của vùng giường không được cắt nhau"), `thresholds.title` ("Ngưỡng quan sát"), `thresholds.save` ("Lưu ngưỡng"), `thresholds.reset` ("Khôi phục mặc định"), `thresholds.default` ("Mặc định"), nhãn từng ngưỡng ở R5, `quality.brightness` ("Độ sáng trung bình"), `quality.fps` ("FPS"), `quality.noData` ("Chưa có dữ liệu").
- **Cấu hình:** đọc `config/engine.default.yaml`; override lưu ở `cameras.thresholds` (xem [event-engine.md §6](../02-architecture/event-engine.md#6-cấu-hình-và-ngưỡng-mặc-định)).

## 5. Acceptance criteria

- [x] **AC1.** ADMIN click lên khung hình để vẽ polygon (≥3 điểm), kéo để sửa điểm, xóa điểm; polygon lưu với toạ độ chuẩn hóa 0–1. Vai trò khác không vào được màn hình và API trả 403. *(PDF §7.2; QA#15)* — *Kiểm chứng:* component test `RoiEditor adds point on click with normalized coords`, `RoiEditor drags and deletes points`, `RoiEditor disables save with fewer than 3 points`; API test `test_put_roi_saves_normalized_polygon`, `test_put_roi_requires_admin`.
- [x] **AC2.** Backend từ chối polygon tự cắt nhau (400 `INVALID_ROI_POLYGON`), cũng như polygon <3 điểm, toạ độ ngoài [0, 1] hoặc suy biến. *(data-model.md `cameras.roi_polygon`; api-conventions.md)* — *Kiểm chứng:* unit test `test_validate_roi_rejects_self_intersection` (hình "nơ"), `test_validate_roi_accepts_convex_and_concave`, `test_validate_roi_rejects_out_of_range`, `test_validate_roi_rejects_collinear`; API test `test_put_roi_self_intersecting_400`.
- [x] **AC3.** Sửa được các ngưỡng chính ở R5; "Khôi phục mặc định" xóa override và form hiện lại giá trị mặc định; khóa lạ hoặc sai kiểu → 400. Mỗi lần lưu tăng `config_version` và ghi audit. *(HS §5.5; QA#22)* — *Kiểm chứng:* API test `test_put_thresholds_override`, `test_reset_thresholds_with_empty_object`, `test_thresholds_unknown_key_400`, `test_thresholds_wrong_type_400`, `test_camera_config_changes_bump_version_and_audit`; component test `ThresholdsForm resets to defaults`.
- [x] **AC4.** Worker nhận ROI mới trong ≤5 giây sau khi lưu. *(A02)* — *Kiểm chứng:* test tích hợp `test_worker_receives_roi_within_5s` (đồng hồ giả lập, dùng worker của F06); kiểm tra tay: lưu ROI rồi xem log worker, ghi vào mục 10.
- [x] **AC5.** Màn hình hiện chỉ báo "Độ sáng trung bình" và "FPS" của camera; chưa có heartbeat thì hiện "Chưa có dữ liệu". *(PDF §9.1)* — *Kiểm chứng:* component test `ImageQualityIndicator shows brightness and fps`, `ImageQualityIndicator shows no data`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | component + API | `RoiEditor.test.tsx`; `test_put_roi_saves_normalized_polygon` | NURSE/CHARGE_NURSE/DOCTOR → 403; <3 điểm → nút lưu bị khóa |
| AC2 | unit + API | `test_roi.py` (lồi, lõm, "nơ", cạnh chồng nhau, thẳng hàng, trùng điểm, ngoài [0,1], >20 điểm); `polygon.test.ts` cùng bộ ca | Polygon lõm hợp lệ **không** bị từ chối |
| AC3 | API + component | `test_camera_thresholds.py`; `ThresholdsForm.test.tsx` | Khóa lạ, sai kiểu, số âm → 400; lưu thất bại không tăng `config_version` |
| AC4 | tích hợp + thủ công | `test_worker_receives_roi_within_5s` | Không lưu gì → worker giữ nguyên cấu hình |
| AC5 | component | `ImageQualityIndicator.test.tsx` | `runtime = null` → "Chưa có dữ liệu" |

## 7. Giả định

- *(giả định)* Polygon tối đa 20 điểm; polygon suy biến (thẳng hàng, trùng điểm liên tiếp) bị từ chối.
- *(giả định)* Hàm kiểm tra polygon đặt ở `postcare/schemas/roi.py`, dùng chung cho API và replay; web có bản tương đương.
- *(giả định)* Có thêm `GET /api/v1/cameras/{id}/thresholds` trả `defaults`, `overrides`, `effective`; cập nhật api-conventions.md cùng PR.
- *(giả định)* Trước khi có `EngineConfig` (F10), override được kiểm tra theo cấu trúc của `config/engine.default.yaml` (khóa có tồn tại, cùng kiểu, số ≥0).
- *(giả định)* Danh sách ngưỡng chính ở R5.
- *(giả định)* Camera offline vẫn sửa được polygon đã lưu.
- *(giả định)* Lưu lại ROI/ngưỡng y hệt giá trị đang có → 200, không tăng `config_version`, không audit (như F03 R16).
- *(giả định)* Sửa ROI/ngưỡng được cả khi phiên đang mở (khác đổi nguồn/giường ở F03 R14); worker tạo engine mới.
- *(giả định)* `GET /thresholds` cũng chỉ ADMIN (chỉ màn hình cấu hình dùng).
- *(giả định)* Chỉ báo chất lượng chỉ hiển thị số liệu, không kết luận "tốt/kém"; làm mới mỗi 2 giây.

## 8. Câu hỏi mở

- ~~F08 có thể xong trước F10, nên chưa có `EngineConfig` để kiểm tra override.~~ **Đã giải quyết:** F10 đã Done khi làm F08; override được validate bằng `EngineConfig` sau khi hợp nhất với mặc định (R4).

## 9. Kế hoạch triển khai

Khảo sát: `validate_roi_polygon` đã có (F12, `schemas/roi.py`); `EngineConfig.load(default, overrides)` đã có (F10) nên override được kiểm tra bằng `EngineConfig` (giải quyết câu hỏi mở mục 8); worker đã tải lại cấu hình khi `config_version` đổi và tạo engine mới theo `engine_key` (F06); `CameraStream`, `RoiOverlay`, `useCameraDetail` có từ F07; pattern ghi ADMIN + `_audit` + `_locked` ở `domain/catalog.py` (F03).

1. **Hình học** (`schemas/roi.py`): thêm `RoiPolygonError(ValueError)` có `reason` (mã máy: `TOO_FEW_POINTS`, `TOO_MANY_POINTS`, `INVALID_POINT`, `OUT_OF_RANGE`, `DUPLICATE_POINT`, `SELF_INTERSECTION`, `ZERO_AREA`), giới hạn 20 điểm, từ chối giá trị không phải số (kể cả bool). Không đổi hành vi với F12 (vẫn là `ValueError`, thông điệp cũ). Test: `server/tests/schemas/test_roi.py`.
2. **Domain** `server/src/postcare/domain/camera_config.py`: `update_roi`, `get_thresholds`, `update_thresholds`. Khóa hàng camera, so sánh trước/sau; có thay đổi → `config_version += 1` + `record_audit` (`camera.update_roi`, `camera.update_thresholds`, `before`/`after`) trong cùng transaction; không đổi gì → 200, không tăng version, không audit *(giả định, như F03 R16)*. Ngưỡng: hợp nhất `config/engine.default.yaml` + override rồi `EngineConfig.from_mapping`; lỗi → 400 `VALIDATION_ERROR`, `details.errors[{path, msg}]` với `path` dạng `thresholds.posture.lying_enter_deg`.
3. **API** `api/v1/cameras.py`: `PUT /cameras/{id}/roi` → `{camera_id, roi_polygon, config_version}`; `GET/PUT /cameras/{id}/thresholds` → `{defaults, overrides, effective, config_version}`. Cả ba chỉ ADMIN (`require_admin`; GET cũng chỉ ADMIN vì chỉ màn hình cấu hình dùng). DTO trong `domain/dto.py`. `make gen-api-types`.
4. **Test API** `server/tests/api/test_camera_roi.py`, `test_camera_thresholds.py`: lưu ROI chuẩn hóa; 403 cho NURSE, CHARGE_NURSE, DOCTOR, FAMILY; 400 `INVALID_ROI_POLYGON` + `details.reason` cho tự cắt, <3, ngoài [0,1], thẳng hàng, >20 điểm, không phải số; 404 camera lạ; override, reset `{}`, khóa lạ / sai kiểu / số âm → 400 kèm đường dẫn khóa; lưu lỗi không tăng `config_version`; audit before/after.
5. **Tích hợp** `server/tests/integration/test_worker_receives_roi.py`: worker thật (F06) ↔ API thật qua `TestClient`, đồng hồ giả; ADMIN lưu ROI → worker có ROI mới và engine mới ≤5 s; không lưu → giữ cấu hình.
6. **Web**: `client.ts` thêm `PUT`; `utils/polygon.ts` (cùng bộ kiểm tra, cùng mã lý do); `pages/CameraConfig/{CameraConfigPage,RoiEditor,ThresholdsForm,ImageQualityIndicator,thresholdKeys}.tsx/ts`; route `/cameras/:id/config` bọc `RequireRole ADMIN`; nút "Cấu hình" ở bảng camera màn hình Quản lý (chỉ ADMIN); hook `useCameraThresholds`, `useSaveRoi`, `useSaveThresholds`. RoiEditor: nền là MJPEG (URL như `CameraStream`), lớp phủ nhận click/kéo, toạ độ = vị trí / kích thước khung đang hiển thị; offline → nền trống + "Mất kết nối camera", vẫn sửa được. Text trong `vi.ts`.
7. **Test web**: `polygon.test.ts`, `RoiEditor.test.tsx`, `ThresholdsForm.test.tsx`, `ImageQualityIndicator.test.tsx`, `CameraConfigPage.test.tsx` (vai trò khác bị chuyển về Tổng quan).
8. **Doc**: api-conventions.md (endpoint, body, lỗi, quyền), data-model.md (`roi_polygon` ≤20 điểm, audit action), spec mục 10.
9. **Kiểm chứng**: `make check` một lần; thủ công DB `postcare_f08`, API cổng 8018, worker trên clip Pexels, lưu ROI qua API/UI, xem log worker tải lại và trạng thái giường đổi.

Rủi ro: jsdom không có kích thước layout → test RoiEditor giả `getBoundingClientRect`. ROI sửa khi phiên đang mở là được phép (khác với đổi nguồn/giường, F03 R14) *(giả định: hiệu chỉnh ROI là việc khi lắp camera, không làm mất dữ liệu phiên)*.

## 10. Ghi chú bàn giao

**2026-11-18 – builder (Claude Code), nhánh `feat/F08-camera-roi`.**

Bằng chứng theo AC:
- **AC1:** `RoiEditor.test.tsx` (`adds point on click with normalized coords`, `drags and deletes points`, `disables save with fewer than 3 points`, offline vẫn sửa được); `CameraConfigPage.test.tsx` (PUT đúng body; NURSE/CHARGE_NURSE/DOCTOR bị chuyển về Tổng quan); `test_camera_roi.py` (`test_put_roi_saves_normalized_polygon`, `test_put_roi_requires_admin` ×3, `test_put_roi_family_forbidden`, 401 khi chưa đăng nhập).
- **AC2:** `tests/schemas/test_roi.py` (nơ, cạnh chồng, lồi/lõm, ngoài [0,1], thẳng hàng, trùng điểm, >20, không phải số/bool/NaN); `polygon.test.ts` cùng bộ ca; `test_put_roi_invalid_polygon_400` (8 ca, kiểm `details.reason`, không tăng version, không audit).
- **AC3:** `test_camera_thresholds.py` (`test_put_thresholds_override`, `test_reset_thresholds_with_empty_object`, `test_thresholds_unknown_key_400`, `test_thresholds_wrong_type_400`, `test_thresholds_out_of_range_400`, `test_camera_config_changes_bump_version_and_audit`); `ThresholdsForm.test.tsx` (`resets to defaults`, chỉ lưu giá trị khác mặc định, giữ override ngoài form).
- **AC4:** `tests/integration/test_worker_receives_roi.py` (worker F06 thật ↔ API thật, đồng hồ giả: ROI và ngưỡng mới ≤5 s; không lưu gì → giữ engine). Kiểm tra tay bên dưới.
- **AC5:** `ImageQualityIndicator.test.tsx` (số liệu; `runtime = null` → "Chưa có dữ liệu").

`make check` xanh (1134 passed, 10 contracts kept, web 147 passed, build OK).

Kiểm tra tay (DB `postcare_f08`, `postcare seed`, API cổng 8018, worker `--video pexels-3753707.mp4`, model full):
- Camera A01 chưa có ROI → worker log "Camera chưa có ROI giường", `state = null`.
- 13:15:37.7 ADMIN `PUT /roi` → `config_version 2`; 13:15:38 worker log "Cấu hình mới (config_version 2…): tạo engine mới"; vài giây sau `GET /overview` có `body_state SITTING`, `observation_quality GOOD`.
- `PUT /thresholds {posture.sitting_enter_deg: 70}` lúc 13:15:53 → worker tạo engine mới 13:15:54; `{}` → khôi phục, `config_version 4`.
- NURSE `PUT /roi` → 403; nơ → 400 `INVALID_ROI_POLYGON` `reason SELF_INTERSECTION`; khóa gõ sai → 400 có `thresholds.posture.lying_entr_deg`. `audit_logs`: `camera.update_roi` 1→2, `camera.update_thresholds` 2→3, 3→4.
- Chưa mở màn hình web trên trình duyệt thật (máy hạn chế bộ nhớ); UI được kiểm bằng component test. Người review nên thử `/cameras/1/config` với `make dev`.

**Review lần 1 (2026-11-18): Chưa đạt (an toàn).** Override theo camera có thể vô hiệu hóa quy tắc an toàn (ví dụ `min_duration_s.OUT_OF_BED = 0`, `face.enabled`, `privacy.*`, `abnormal_movement.min_conditions = 1`), chưa kiểm tra quan hệ hysteresis, `web/tsconfig.tsbuildinfo` bị commit. Đã sửa (test trước):
- `config/camera_overrides.yaml` (khóa được phép, giới hạn, quan hệ) + `load_override_rules`, `rule_violations` trong `domain/camera_config.py`; thứ tự kiểm tra: khóa được phép → `EngineConfig` → giới hạn/quan hệ.
- Test: `test_thresholds_safety_limits_400` (gồm `{"min_duration_s":{"OUT_OF_BED":0}}`), `test_thresholds_key_not_overridable_400`, `test_thresholds_relations_400`, `test_thresholds_at_floor_accepted`, `test_get_thresholds_returns_rules_for_web`, `tests/domain/test_camera_override_rules.py` (mặc định thỏa mọi quy tắc); web `ThresholdsForm` chặn lưu dưới sàn/trên trần và sai quan hệ.
- `*.tsbuildinfo` vào `.gitignore`, gỡ khỏi git.
- Thêm (tùy chọn của review): phím mũi tên dịch điểm ROI đang chọn (Shift: bước lớn), test `arrow keys move the selected point`.
- `make check` xanh sau khi sửa. **Kết luận: Đạt** → Done.

Ghi chú cho người sau:
- `validate_roi_polygon` giờ ném `RoiPolygonError(ValueError)` có `reason`; thêm giới hạn 20 điểm và từ chối giá trị không phải số (ảnh hưởng nhẹ tới file cấu hình replay F12: vẫn là `ValueError`).
- `streamUrl` tách ra `web/src/api/stream.ts`, dùng chung cho `CameraStream` (F07) và `RoiEditor`.
- Nút "Cấu hình" ở bảng camera màn hình Quản lý (chỉ ADMIN, camera đang dùng).

## 11. Definition of Done

- [x] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [x] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [x] Doc liên quan đã cập nhật cùng PR.
- [x] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
