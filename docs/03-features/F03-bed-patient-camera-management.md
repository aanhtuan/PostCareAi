# F03 – Quản lý giường, bệnh nhân, camera

| Thuộc tính | Giá trị |
|---|---|
| Mã | F03 |
| Trạng thái | Todo <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F02 |
| Nhánh code | B+C |
| Nguồn | PDF §4.2 (tr.5), §9.1 (tr.11), §10.1 (tr.12–13); HS §6.3; QA#13, QA#15, QA#18 |

## 1. Mục tiêu

Cho quản trị viên khai báo giường, bệnh nhân (chỉ mã thử nghiệm) và camera bằng form tối giản (QA#15). Bệnh nhân được gắn với hệ thống qua giường, không qua nhận diện khuôn mặt (PDF §4.2). Màn hình "Quản lý giường" cho mọi người xem giường nào có camera nào và đang theo dõi bệnh nhân nào (PDF §9.1).

## 2. Phạm vi

**Trong phạm vi**
- API CRUD cho `beds`, `patients`, `cameras` (tạo, xem danh sách, xem chi tiết, sửa, ngừng dùng bằng `is_active = false`).
- Kiểm tra trùng mã, mỗi giường tối đa 1 camera.
- Audit log cho mọi thao tác ghi.
- Màn hình "Quản lý giường" với 3 nhóm: Giường, Bệnh nhân, Camera.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Mở/đóng phiên theo dõi (→ F04). F03 chỉ **hiển thị** bệnh nhân hiện tại nếu có phiên đang mở.
- Vẽ Bed ROI, sửa ngưỡng (→ F08); đổi chế độ hiển thị (→ F28).
- Trạng thái camera thật từ worker (→ F06).
- Quản lý tài khoản người dùng (→ F35).
- Xóa cứng bản ghi *(data-model.md: chỉ xóa mềm)*.

## 3. Yêu cầu chi tiết

- **R1.** Endpoint `GET/POST /api/v1/beds`, `GET/PATCH /api/v1/beds/{id}`; tương tự cho `/patients` và `/cameras` *(api-conventions.md)*. Danh sách có phân trang `limit`/`offset` và trả `{items, total}` *(api-conventions.md)*.
- **R2.** Quyền *(api-conventions.md, bảng phân quyền; QA#18)*:
  - ghi (POST/PATCH): chỉ `ADMIN`, vai trò khác → 403 `FORBIDDEN`;
  - đọc (GET): mọi vai trò đã đăng nhập *(giả định: NURSE/CHARGE_NURSE cần danh sách giường và bệnh nhân để mở phiên ở F04)*.
- **R3.** Giường: `code` (bắt buộc, duy nhất, ví dụ `A01`), `area` (bắt buộc), `is_active` *(PDF §10.1; data-model.md)*.
- **R4.** Bệnh nhân: `code` (mã thử nghiệm, bắt buộc, duy nhất, ví dụ `BN-001`), `note` (tùy chọn), `is_active`. **Không** có họ tên hay ảnh. Schema request đặt `extra="forbid"`: gửi thêm trường như `full_name` hoặc `photo` → 400 `VALIDATION_ERROR` *(PDF §10.1; HS §6.3)*.
- **R5.** Camera: `name`, `source_type` (`WEBCAM`/`URL`/`FILE`), `source`, `bed_id` (tùy chọn), `is_active` *(data-model.md)*. Kiểm tra `source` theo loại *(giả định)*:
  - `WEBCAM`: số nguyên không âm (index);
  - `URL`: bắt đầu bằng `http://`, `https://` hoặc `rtsp://`;
  - `FILE`: chuỗi đường dẫn không rỗng (không kiểm tra file tồn tại vì worker có thể chạy ở máy khác).
- **R6.** Trùng `code` của giường hoặc bệnh nhân → 409 `DUPLICATE_CODE` *(api-conventions.md)*. So sánh mã sau khi bỏ khoảng trắng đầu/cuối *(giả định)*.
- **R7.** Mỗi giường tối đa 1 camera *(QA#13; data-model.md `cameras.bed_id` unique)*. Gán camera vào giường đã có camera → 409 `BED_ALREADY_HAS_CAMERA` *(giả định mã lỗi mới; thêm vào api-conventions.md cùng PR)*.
- **R8.** Sửa `source_type`, `source` hoặc `bed_id` của camera → tăng `cameras.config_version` *(data-model.md: "Tăng mỗi lần sửa cấu hình (worker poll)")*.
- **R9.** Ngừng dùng bằng `PATCH {is_active: false}` *(api-conventions.md; data-model.md "Quy ước")*. Danh sách mặc định chỉ trả bản ghi đang dùng; `?include_inactive=true` trả cả bản ghi đã ngừng *(giả định)*.
- **R10.** Mọi thao tác ghi gọi `record_audit()` với `before`/`after` *(api-conventions.md "Quy ước code backend"; data-model.md audit_logs)*. Action: `bed.create`, `bed.update`, `patient.create`, `patient.update`, `camera.create`, `camera.update` *(giả định tên action)*.
- **R11.** `GET /api/v1/beds` trả kèm mỗi giường: camera gắn với giường (id, name, status) và bệnh nhân hiện tại (mã thử nghiệm) lấy từ phiên đang mở trong `monitoring_sessions`, `null` nếu không có *(PDF §9.1 "Quản lý giường: … bệnh nhân hiện tại")*.
- **R12.** Màn hình "Quản lý giường" (`/management`) *(PDF §9.1; QA#15)*:
  - bảng giường: mã giường, khu vực, camera, bệnh nhân hiện tại, trạng thái dùng;
  - bảng bệnh nhân: mã thử nghiệm, ghi chú, trạng thái dùng;
  - bảng camera: tên, loại nguồn, địa chỉ nguồn, giường;
  - ADMIN thấy nút "Thêm", "Sửa", "Ngừng dùng"; vai trò khác chỉ xem *(giả định)*;
  - lỗi 409 hiện thông báo tiếng Việt lấy từ `message` của API.
- **R13.** Text giao diện nằm trong `web/src/i18n/vi.ts` *(ADR-0005)*. Nhãn loại nguồn: "Webcam", "Địa chỉ stream (URL)", "File video" *(giả định nhãn)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/v1/beds.py`, `api/v1/patients.py`, `api/v1/cameras.py`.
  - `server/src/postcare/domain/beds.py`, `domain/patients.py`, `domain/cameras.py`.
  - Schema request/response: `BedCreate`, `BedUpdate`, `BedOut`, `PatientCreate`, `PatientUpdate`, `PatientOut`, `CameraCreate`, `CameraUpdate`, `CameraOut` *(api-conventions.md)*.
  - `server/tests/api/test_beds.py`, `test_patients.py`, `test_cameras.py`.
  - `web/src/pages/Management/ManagementPage.tsx`, `BedForm.tsx`, `PatientForm.tsx`, `CameraForm.tsx`, `ManagementPage.test.tsx`.
  - `web/src/api/` hooks TanStack Query: `useBeds`, `usePatients`, `useCameras`.
- **Dữ liệu:** `beds`, `patients`, `cameras`, đọc `monitoring_sessions`, ghi `audit_logs` (xem [data-model.md](../02-architecture/data-model.md)). Không có migration mới.
- **API:** `GET/POST/PATCH /api/v1/beds`, `/patients`, `/cameras` (xem [api-conventions.md](../02-architecture/api-conventions.md#danh-sách-endpoint-dự-kiến)). Chạy `make gen-api-types`.
- **UI:** màn hình "Quản lý giường". Text cần thêm vào `vi.ts`: `management.title` ("Quản lý giường"), `management.beds`, `management.patients`, `management.cameras`, `management.add` ("Thêm"), `management.edit` ("Sửa"), `management.deactivate` ("Ngừng dùng"), `bed.code` ("Mã giường"), `bed.area` ("Khu vực"), `patient.code` ("Mã thử nghiệm"), `patient.note` ("Ghi chú"), `patient.current` ("Bệnh nhân hiện tại"), `camera.name`, `camera.sourceType`, `camera.source`, `camera.bed`.
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [ ] **AC1.** ADMIN thêm, sửa, ngừng dùng được giường (mã, khu vực), bệnh nhân (mã thử nghiệm, ghi chú), camera (tên, loại nguồn, địa chỉ nguồn, giường). Mỗi thao tác ghi audit log. Vai trò khác gọi API ghi → 403. *(QA#15, QA#18)* — *Kiểm chứng:* test `test_admin_crud_beds`, `test_admin_crud_patients`, `test_admin_crud_cameras`, `test_write_requires_admin` (tham số hóa NURSE, CHARGE_NURSE, DOCTOR), `test_writes_record_audit`.
- [ ] **AC2.** Trùng mã giường hoặc mã bệnh nhân → 409 `DUPLICATE_CODE`. Gán camera thứ hai vào cùng giường → 409. Sửa nguồn hoặc giường của camera làm tăng `config_version`. *(QA#13)* — *Kiểm chứng:* test `test_duplicate_bed_code_409`, `test_duplicate_patient_code_409`, `test_second_camera_same_bed_409`, `test_camera_update_bumps_config_version`.
- [ ] **AC3.** Màn hình "Quản lý giường" liệt kê giường kèm camera và bệnh nhân hiện tại (từ phiên đang mở). *(PDF §9.1)* — *Kiểm chứng:* test API `test_beds_list_includes_camera_and_current_patient` (chèn phiên mở trực tiếp vào DB); component test `ManagementPage lists beds with camera and current patient`, `non-admin sees no edit buttons`.
- [ ] **AC4.** Bệnh nhân không có trường họ tên hay ảnh: gửi `full_name` hoặc `photo` → 400 `VALIDATION_ERROR`; response không có các trường này. *(PDF §10.1; HS §6.3)* — *Kiểm chứng:* test `test_patient_rejects_name_and_photo_fields`, `test_patient_out_has_no_name_field`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | CRUD theo từng tài nguyên; `test_writes_record_audit` | NURSE/CHARGE_NURSE/DOCTOR ghi → 403; `source` sai theo `source_type` → 400 |
| AC1 | API | `test_deactivate_hides_from_default_list` | `?include_inactive=true` vẫn thấy bản ghi đã ngừng |
| AC2 | API | `test_duplicate_bed_code_409`, `test_second_camera_same_bed_409` | Mã có khoảng trắng đầu/cuối vẫn bị coi là trùng |
| AC2 | API | `test_camera_update_bumps_config_version` | Sửa chỉ `name` không tăng `config_version` *(giả định)* |
| AC3 | API + component | `test_beds_list_includes_camera_and_current_patient`; `ManagementPage.test.tsx` | Giường không có phiên mở → bệnh nhân hiện tại hiển thị "—" |
| AC4 | API | `test_patient_rejects_name_and_photo_fields` | — |

## 7. Giả định

- *(giả định)* Mọi vai trò đã đăng nhập đọc được danh sách giường, bệnh nhân, camera.
- *(giả định)* Mã lỗi mới `BED_ALREADY_HAS_CAMERA` (409); cập nhật api-conventions.md cùng PR.
- *(giả định)* Quy tắc kiểm tra `source` theo `source_type` ở R5.
- *(giả định)* Chỉ sửa `source_type`, `source`, `bed_id` mới tăng `config_version`; sửa `name` thì không.
- *(giả định)* Tên action audit ở R10.
- *(giả định)* Tham số `include_inactive` cho danh sách.

## 8. Câu hỏi mở

- Ngừng dùng một giường hoặc bệnh nhân đang có phiên mở thì xử lý thế nào: chặn (409) hay tự đóng phiên? Mặc định đề xuất: chặn với 409 và yêu cầu kết thúc phiên trước (kiểm tra thêm ở F04 khi có logic phiên). **Không chặn** F03.

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
