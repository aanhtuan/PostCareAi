# F03 – Quản lý giường, bệnh nhân, camera

| Thuộc tính | Giá trị |
|---|---|
| Mã | F03 |
| Trạng thái | In progress <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 3 phiên |
| Phụ thuộc | F02 |
| Nhánh code | B+C |
| Nguồn | PDF §4.2 (tr.5), §9.1 (tr.11), §10.1 (tr.12–13); HS §6.3; QA#13, QA#15, QA#18, QA#36; Yêu cầu người dùng (2026-11-17); PRD US11 |

## 1. Mục tiêu

Cho quản trị viên khai báo giường, bệnh nhân (chỉ mã thử nghiệm) và camera bằng form tối giản (QA#15), xóa (mềm) và khôi phục khi cần (QA#36). Bệnh nhân được gắn với hệ thống qua giường, không qua nhận diện khuôn mặt (PDF §4.2). Màn hình "Quản lý giường" cho nhân viên xem giường nào có camera nào và đang theo dõi bệnh nhân nào (PDF §9.1). Bản ghi đã xóa vẫn giữ lịch sử, timeline và audit (QA#36).

## 2. Phạm vi

**Trong phạm vi**
- API CRUD cho `beds`, `patients`, `cameras` (tạo, xem danh sách, xem chi tiết, sửa).
- Thao tác "Xóa" (xóa mềm, `is_active = false`) và "Khôi phục" trên API và UI *(QA#36)*.
- Chặn xóa giường/bệnh nhân đang có phiên mở và camera đang gắn với phiên đang mở.
- Kiểm tra trùng mã, mỗi giường tối đa 1 camera.
- Audit log cho mọi thao tác ghi.
- Màn hình "Quản lý giường" với 3 nhóm: Giường, Bệnh nhân, Camera.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Mở/đóng phiên theo dõi, chuyển giường (→ F04). F03 chỉ **hiển thị** bệnh nhân hiện tại nếu có phiên đang mở.
- Vẽ Bed ROI, sửa ngưỡng (→ F08); đổi chế độ hiển thị (→ F28).
- Trạng thái camera thật từ worker (→ F06).
- Quản lý tài khoản người dùng (→ F35).
- Danh mục khu vực có bảng riêng (→ F37). F03 vẫn dùng `beds.area` dạng chuỗi; F37 chuyển sang `beds.area_id`.
- "Xóa cứng" bản ghi *(QA#36; data-model.md: chỉ xóa mềm)*.

## 3. Yêu cầu chi tiết

- **R1.** Endpoint `GET/POST /api/v1/beds`, `GET/PATCH /api/v1/beds/{id}`; tương tự cho `/patients` và `/cameras` *(api-conventions.md)*. Danh sách có phân trang `limit`/`offset` và trả `{items, total}` *(api-conventions.md)*.
- **R2.** Quyền *(api-conventions.md, bảng phân quyền; QA#18)*:
  - ghi (POST/PATCH): chỉ `ADMIN`, vai trò khác → 403 `FORBIDDEN`;
  - đọc (GET): mọi vai trò nhân viên (NURSE, CHARGE_NURSE, DOCTOR, ADMIN); `FAMILY` → 403 *(giả định: NURSE/CHARGE_NURSE cần danh sách giường và bệnh nhân để mở phiên ở F04; QA#31, F35 R2: người nhà không xem danh mục)*.
- **R3.** Giường: `code` (bắt buộc, duy nhất, ví dụ `A01`), `area` (bắt buộc), `is_active` *(PDF §10.1; data-model.md)*. Từ F37, `area` được thay bằng `area_id` chọn từ danh mục khu vực.
- **R4.** Bệnh nhân: `code` (mã thử nghiệm, bắt buộc, duy nhất, ví dụ `BN-001`), `note` (tùy chọn), `is_active`. **Không** có họ tên hay ảnh. Schema request đặt `extra="forbid"`: gửi thêm trường như `full_name` hoặc `photo` → 400 `VALIDATION_ERROR` *(PDF §10.1; HS §6.3)*.
- **R5.** Camera: `name`, `source_type` (`WEBCAM`/`URL`/`FILE`), `source`, `bed_id` (tùy chọn), `is_active` *(data-model.md)*. Kiểm tra `source` theo loại *(giả định)*:
  - `WEBCAM`: số nguyên không âm (index);
  - `URL`: bắt đầu bằng `http://`, `https://` hoặc `rtsp://`;
  - `FILE`: chuỗi đường dẫn không rỗng (không kiểm tra file tồn tại vì worker có thể chạy ở máy khác).
- **R6.** Trùng `code` của giường hoặc bệnh nhân → 409 `DUPLICATE_CODE` *(api-conventions.md)*. So sánh mã sau khi bỏ khoảng trắng đầu/cuối *(giả định)*.
- **R7.** Mỗi giường tối đa 1 camera *(QA#13; data-model.md `cameras.bed_id` unique)*. Gán camera vào giường đã có camera → 409 `BED_ALREADY_HAS_CAMERA` *(giả định mã lỗi mới; thêm vào api-conventions.md cùng PR)*.
- **R8.** Sửa `source_type`, `source` hoặc `bed_id` của camera → tăng `cameras.config_version` *(data-model.md: "Tăng mỗi lần sửa cấu hình (worker poll)")*.
- **R9.** Xóa bằng `DELETE /api/v1/{beds|patients|cameras}/{id}` → 200 bản ghi với `is_active = false` (xóa mềm); khôi phục bằng `POST /api/v1/{beds|patients|cameras}/{id}/restore` → 200 với `is_active = true` *(QA#36; data-model.md "Quy ước")*. `PATCH` không nhận trường `is_active` (gửi lên → 400 `VALIDATION_ERROR`) *(giả định: một đường duy nhất để chặn và audit)*. Danh sách mặc định chỉ trả bản ghi đang dùng; `?include_inactive=true` trả cả bản ghi đã xóa *(giả định)*.
- **R10.** Mọi thao tác ghi gọi `record_audit()` với `before`/`after` *(api-conventions.md "Quy ước code backend"; data-model.md audit_logs)*. Action: `bed.create`, `bed.update`, `bed.delete`, `bed.restore`, `patient.create`, `patient.update`, `patient.delete`, `patient.restore`, `camera.create`, `camera.update`, `camera.delete`, `camera.restore` *(giả định tên action)*.
- **R11.** `GET /api/v1/beds` trả kèm mỗi giường: camera gắn với giường (id, name, status) và bệnh nhân hiện tại (mã thử nghiệm) lấy từ phiên đang mở trong `monitoring_sessions`, `null` nếu không có *(PDF §9.1 "Quản lý giường: … bệnh nhân hiện tại")*.
- **R12.** Màn hình "Quản lý giường" (`/management`) *(PDF §9.1; QA#15)*:
  - bảng giường: mã giường, khu vực, camera, bệnh nhân hiện tại, trạng thái dùng;
  - bảng bệnh nhân: mã thử nghiệm, ghi chú, trạng thái dùng;
  - bảng camera: tên, loại nguồn, địa chỉ nguồn, giường;
  - ADMIN thấy nút "Thêm", "Sửa", "Xóa" (có hộp thoại xác nhận nói rõ lịch sử vẫn được giữ) và, với bản ghi đã xóa, "Khôi phục"; vai trò khác chỉ xem *(QA#36; giả định)*;
  - công tắc "Hiện mục đã xóa"; bản ghi đã xóa có nhãn "Đã xóa" *(giả định)*;
  - lỗi 409 hiện thông báo tiếng Việt lấy từ `message` của API.
- **R13.** Text giao diện nằm trong `web/src/i18n/vi.ts` *(ADR-0005)*. Nhãn loại nguồn: "Webcam", "Địa chỉ stream (URL)", "File video" *(giả định nhãn)*.

**Xóa mềm và khôi phục** *(QA#36; Yêu cầu người dùng 2026-11-17)*

- **R14.** Chặn xóa khi đang dùng trong phiên mở *(QA#36; giả định mã lỗi mới, thêm vào api-conventions.md cùng PR)*:
  - giường có phiên mở → 409 `BED_HAS_OPEN_SESSION`;
  - bệnh nhân có phiên mở → 409 `PATIENT_HAS_OPEN_SESSION`;
  - camera là `camera_id` của một phiên đang mở → 409 `CAMERA_IN_ACTIVE_SESSION`.

  `details.session_id` cho biết phiên đang vướng. Phải kết thúc phiên (F04) trước. Kiểm tra trong cùng transaction với thao tác xóa *(giả định: tránh tranh chấp với F04 mở phiên đồng thời)*.
- **R15.** Hệ quả của xóa *(giả định)*:
  - giường hoặc bệnh nhân đã xóa không mở được phiên mới (F04 R5) và không hiện trên Tổng quan;
  - xóa camera đặt `bed_id = null` (giá trị cũ nằm trong audit `before`) để giường gắn được camera khác; khôi phục camera **không** tự gắn lại giường;
  - xóa giường giữ nguyên liên kết camera; khôi phục giường trả lại đúng trạng thái trước.
- **R16.** Xóa bản ghi đã xóa hoặc khôi phục bản ghi đang dùng: trả 200, không đổi gì, không ghi audit *(giả định: thao tác lặp là vô hại)*. Tạo mới với mã trùng mã của bản ghi đã xóa → 409 `DUPLICATE_CODE`, `message` gợi ý dùng "Khôi phục" *(giả định: mã duy nhất kể cả đã xóa)*.
- **R17.** Bản ghi đã xóa vẫn truy cập được: `GET /api/v1/{beds|patients|cameras}/{id}` trả bản ghi (kèm `is_active = false`); phiên, sự kiện, cảnh báo, timeline (F22) và audit liên quan không bị ẩn hay sửa *(QA#36)*.
- **R18.** "Xóa cứng" không có endpoint và không có nút *(QA#36)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/v1/beds.py`, `api/v1/patients.py`, `api/v1/cameras.py`.
  - `server/src/postcare/domain/beds.py`, `domain/patients.py`, `domain/cameras.py`.
  - Schema request/response: `BedCreate`, `BedUpdate`, `BedOut`, `PatientCreate`, `PatientUpdate`, `PatientOut`, `CameraCreate`, `CameraUpdate`, `CameraOut` *(api-conventions.md)*.
  - `server/tests/api/test_beds.py`, `test_patients.py`, `test_cameras.py`.
  - `web/src/pages/Management/ManagementPage.tsx`, `BedForm.tsx`, `PatientForm.tsx`, `CameraForm.tsx`, `ManagementPage.test.tsx`.
  - `web/src/api/` hooks TanStack Query: `useBeds`, `usePatients`, `useCameras`.
- **Dữ liệu:** `beds`, `patients`, `cameras`, đọc `monitoring_sessions`, ghi `audit_logs` (xem [data-model.md](../02-architecture/data-model.md)). Không có migration mới.
- **API:** `GET/POST /api/v1/beds`, `GET/PATCH/DELETE /api/v1/beds/{id}`, `POST /api/v1/beds/{id}/restore`; tương tự cho `/patients`, `/cameras` (xem [api-conventions.md](../02-architecture/api-conventions.md#danh-sách-endpoint-dự-kiến)). Chạy `make gen-api-types`.
- **UI:** màn hình "Quản lý giường". Text cần thêm vào `vi.ts`: `management.title` ("Quản lý giường"), `management.beds`, `management.patients`, `management.cameras`, `management.add` ("Thêm"), `management.edit` ("Sửa"), `management.delete` ("Xóa"), `management.restore` ("Khôi phục"), `management.deleted` ("Đã xóa"), `management.showDeleted` ("Hiện mục đã xóa"), `management.confirmDelete` ("Xóa mục này? Lịch sử theo dõi vẫn được giữ và có thể khôi phục."), `bed.code` ("Mã giường"), `bed.area` ("Khu vực"), `patient.code` ("Mã thử nghiệm"), `patient.note` ("Ghi chú"), `patient.current` ("Bệnh nhân hiện tại"), `camera.name`, `camera.sourceType`, `camera.source`, `camera.bed`.
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [ ] **AC1.** ADMIN thêm, sửa được giường (mã, khu vực), bệnh nhân (mã thử nghiệm, ghi chú), camera (tên, loại nguồn, địa chỉ nguồn, giường). Mỗi thao tác ghi audit log. Vai trò khác gọi API ghi → 403. *(QA#15, QA#18)* — *Kiểm chứng:* test `test_admin_crud_beds`, `test_admin_crud_patients`, `test_admin_crud_cameras`, `test_write_requires_admin` (tham số hóa NURSE, CHARGE_NURSE, DOCTOR), `test_writes_record_audit`.
- [ ] **AC2.** Trùng mã giường hoặc mã bệnh nhân → 409 `DUPLICATE_CODE`. Gán camera thứ hai vào cùng giường → 409. Sửa nguồn hoặc giường của camera làm tăng `config_version`. *(QA#13)* — *Kiểm chứng:* test `test_duplicate_bed_code_409`, `test_duplicate_patient_code_409`, `test_second_camera_same_bed_409`, `test_camera_update_bumps_config_version`.
- [ ] **AC3.** Màn hình "Quản lý giường" liệt kê giường kèm camera và bệnh nhân hiện tại (từ phiên đang mở). *(PDF §9.1)* — *Kiểm chứng:* test API `test_beds_list_includes_camera_and_current_patient` (chèn phiên mở trực tiếp vào DB); component test `ManagementPage lists beds with camera and current patient`, `non-admin sees no edit buttons`.
- [ ] **AC4.** Bệnh nhân không có trường họ tên hay ảnh: gửi `full_name` hoặc `photo` → 400 `VALIDATION_ERROR`; response không có các trường này. *(PDF §10.1; HS §6.3)* — *Kiểm chứng:* test `test_patient_rejects_name_and_photo_fields`, `test_patient_out_has_no_name_field`.
- [ ] **AC5.** ADMIN "Xóa" (mềm) và "Khôi phục" được giường, bệnh nhân, camera; mỗi thao tác ghi audit `*.delete` / `*.restore`; bản ghi đã xóa ẩn khỏi danh sách mặc định nhưng vẫn xem được chi tiết, phiên và timeline cũ; không có đường xóa cứng. Vai trò khác → 403. *(QA#36)* — *Kiểm chứng:* test `test_soft_delete_and_restore` (tham số hóa 3 tài nguyên), `test_delete_restore_audited`, `test_deleted_hidden_from_default_list`, `test_deleted_bed_history_still_accessible` (timeline của phiên cũ vẫn trả sự kiện), `test_delete_requires_admin`, `test_patch_rejects_is_active`; component test `ManagementPage delete asks for confirmation`, `ManagementPage shows restore for deleted items`.
- [ ] **AC6.** Không xóa được giường hoặc bệnh nhân đang có phiên mở (409 `BED_HAS_OPEN_SESSION` / `PATIENT_HAS_OPEN_SESSION`) và camera của phiên đang mở (409 `CAMERA_IN_ACTIVE_SESSION`); sau khi kết thúc phiên thì xóa được. Xóa camera giải phóng giường để gắn camera khác. *(QA#36; giả định)* — *Kiểm chứng:* test `test_delete_bed_with_open_session_409`, `test_delete_patient_with_open_session_409`, `test_delete_camera_in_active_session_409`, `test_delete_allowed_after_session_end`, `test_delete_camera_frees_bed`, `test_deleted_bed_cannot_start_session`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | CRUD theo từng tài nguyên; `test_writes_record_audit` | NURSE/CHARGE_NURSE/DOCTOR ghi → 403; `source` sai theo `source_type` → 400 |
| AC1 | API | `test_deleted_hidden_from_default_list` | `?include_inactive=true` vẫn thấy bản ghi đã xóa; `FAMILY` đọc danh sách → 403 |
| AC2 | API | `test_duplicate_bed_code_409`, `test_second_camera_same_bed_409` | Mã có khoảng trắng đầu/cuối vẫn bị coi là trùng |
| AC2 | API | `test_camera_update_bumps_config_version` | Sửa chỉ `name` không tăng `config_version` *(giả định)* |
| AC3 | API + component | `test_beds_list_includes_camera_and_current_patient`; `ManagementPage.test.tsx` | Giường không có phiên mở → bệnh nhân hiện tại hiển thị "—" |
| AC4 | API | `test_patient_rejects_name_and_photo_fields` | — |
| AC5 | API + component | `test_soft_delete_and_restore`, `test_deleted_bed_history_still_accessible`; `ManagementPage.test.tsx` | Xóa lặp lại / khôi phục bản ghi đang dùng → 200, không thêm audit; tạo mới trùng mã bản ghi đã xóa → 409 `DUPLICATE_CODE`; `DELETE` bởi NURSE → 403 |
| AC6 | API | `test_delete_bed_with_open_session_409`, `test_delete_camera_in_active_session_409` | Camera gắn giường nhưng không có phiên mở → xóa được |

## 7. Giả định

- *(giả định)* Mọi vai trò nhân viên đọc được danh sách giường, bệnh nhân, camera; `FAMILY` thì không. Ca âm tính với `FAMILY` thêm khi F35 đã đưa vai trò này vào enum (dùng guard `require_staff` của F35).
- *(giả định)* Mã lỗi mới `BED_ALREADY_HAS_CAMERA` (409); cập nhật api-conventions.md cùng PR.
- *(giả định)* Quy tắc kiểm tra `source` theo `source_type` ở R5.
- *(giả định)* Chỉ sửa `source_type`, `source`, `bed_id` mới tăng `config_version`; sửa `name` thì không.
- *(giả định)* Tên action audit ở R10.
- *(giả định)* Tham số `include_inactive` cho danh sách.
- *(giả định)* Xóa/khôi phục qua `DELETE` và `POST .../restore`; `PATCH` không nhận `is_active`.
- *(giả định)* Mã lỗi mới `BED_HAS_OPEN_SESSION`, `PATIENT_HAS_OPEN_SESSION`, `CAMERA_IN_ACTIVE_SESSION` (409); cập nhật api-conventions.md cùng PR.
- *(giả định)* Xóa camera đặt `bed_id = null`; khôi phục không tự gắn lại giường. Xóa giường giữ liên kết camera.
- *(giả định)* Xóa/khôi phục lặp lại trả 200, không audit; mã duy nhất kể cả bản ghi đã xóa.

## 8. Câu hỏi mở

- (Đã chốt) Xóa giường hoặc bệnh nhân đang có phiên mở: chặn bằng 409, yêu cầu kết thúc phiên trước (R14; QA#36).
- Giường đã xóa nhưng camera vẫn gắn: worker của camera đó có nên dừng hẳn không? Mặc định: worker vẫn chạy nhưng không có phiên nên không sinh sự kiện engine (409 `NO_ACTIVE_SESSION`). **Không chặn.**
- (Ghi chú từ F01 review) `seed_base` (`server/src/postcare/domain/seed.py`, `make db-seed`) tìm camera của A01 theo `cameras.bed_id`. Xóa mềm camera ở F03 đặt `bed_id` về null, nên chạy lại `db-seed` sẽ tạo thêm một "Camera A01". F03 phải xử lý (ví dụ seed bỏ qua khi đã có camera tên "Camera A01") và thêm test. **Không chặn.**

## 9. Kế hoạch triển khai

> Lập ngày 2026-11-18 (builder F03). Không có migration mới: bảng `beds`, `patients`, `cameras` đã đủ cột (F01).

1. **Test trước** (`server/tests/api/test_beds.py`, `test_patients.py`, `test_cameras.py`, `test_catalog_delete.py`; `server/tests/domain/test_seed.py`; `web/src/pages/Management/ManagementPage.test.tsx`), xác nhận đỏ đúng lý do, commit `test(F03): ...`.
2. **Schema** trong `postcare/domain/dto.py`: `BedCreate/BedUpdate`, `PatientCreate/PatientUpdate`, `CameraCreate/CameraUpdate` (`StrictIn`, `extra="forbid"` nên `is_active`, `full_name`, `photo` bị từ chối). `code` được `strip()` và không rỗng.
3. **Domain** `postcare/domain/catalog.py` (giữ một module thay vì tách 3 file như §4: logic ngắn, dùng chung hàm lỗi/audit):
   - `create_*`, `update_*`, `delete_*`, `restore_*`, `get_*`, `list_*` trả `Page`.
   - Trùng mã: kiểm tra trước (kể cả bản ghi đã xóa) → 409 `DUPLICATE_CODE` (`details.field`, `details.inactive` + gợi ý "Khôi phục"); vẫn bắt `IntegrityError` phòng tranh chấp.
   - Camera: kiểm tra `source` theo `source_type` (R5) → 400 `VALIDATION_ERROR`; giường đích phải tồn tại và đang dùng; giường đã có camera khác → 409 `BED_ALREADY_HAS_CAMERA`; đổi `source_type`/`source`/`bed_id` → `config_version += 1`.
   - Xóa: khóa hàng (`SELECT ... FOR UPDATE`) rồi kiểm tra phiên mở trong cùng transaction → 409 `BED_HAS_OPEN_SESSION` / `PATIENT_HAS_OPEN_SESSION` / `CAMERA_IN_ACTIVE_SESSION` với `details.session_id`. Xóa camera đặt `bed_id = null` (và tăng `config_version` để worker tải lại). Lặp lại → 200, không audit.
   - Audit `bed|patient|camera.create|update|delete|restore` với `before`/`after`.
4. **Router** `postcare/api/v1/beds.py`, `patients.py`, `cameras.py` (đọc: mọi vai trò nhân viên; ghi: `require_roles(ADMIN)`); `catalog.py` chỉ còn `/shifts`. Danh sách nhận `limit` (≤ 200, mặc định 50), `offset`, `include_inactive`, trả `{items, total}`.
5. **Seed**: `seed_base`/`seed_demo` không tạo camera mới khi đã có camera cùng tên (`Camera A01`…), kể cả đã xóa (§8).
6. `make gen-api-types`; web: `client.ts` thêm `PATCH`/`DELETE`; hook `useBeds/usePatients/useCameras` nhận `includeInactive`, đọc `items`; mutation tạo/sửa/xóa/khôi phục.
7. **UI** `ManagementPage.tsx` + `BedForm.tsx`, `PatientForm.tsx`, `CameraForm.tsx`, `ConfirmDeleteDialog`: ADMIN thấy Thêm/Sửa/Xóa/Khôi phục; công tắc "Hiện mục đã xóa"; nhãn "Đã xóa"; lỗi 409 hiện `message`. Text mới nằm trong khối `catalog` riêng của `vi.ts` (tránh xung đột khi gộp với F35).
8. Docs: `api-conventions.md` (endpoint, mã lỗi, mã 400/422), `data-model.md` nếu cần. `make check`, `scripts\dev.ps1 check`, kiểm chứng thủ công bằng curl; ghi §10, trạng thái In review.

**Ghi chú lệch nhỏ so với spec (không chặn):** lỗi schema (trường thừa, sai kiểu) do FastAPI bắt trả HTTP **422** với `code = VALIDATION_ERROR` theo api-conventions.md "422: Bọc lại thành VALIDATION_ERROR"; lỗi nghiệp vụ (nguồn sai theo loại) trả 400. Test kiểm `code` và đúng mã HTTP tương ứng. Ca âm tính `FAMILY` để F35 thêm khi có vai trò này.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
