# F37 – Quản lý khu vực và ca trực

| Thuộc tính | Giá trị |
|---|---|
| Mã | F37 |
| Trạng thái | Done <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F03 |
| Nhánh code | B+C |
| Nguồn | Yêu cầu người dùng (2026-11-17); QA#36; QA#19; PDF §10.1 (tr.12–13: giường thuộc khu vực); HS Hình 3 ("Ca trực: 14:00-22:00"); PRD §3, US11 |

## 1. Mục tiêu

Cho ADMIN quản lý danh mục **khu vực** và **ca trực** trên giao diện, có xóa mềm và khôi phục (QA#36; PRD US11). Hiện `beds.area` là chuỗi tự do (F01/F03), dễ gõ lệch và không lọc được; feature này tách thành bảng `areas` và chuyển dữ liệu bằng migration, giao diện vẫn hiển thị tên khu vực như cũ. Ca trực hiện chỉ có seed trong `shift_definitions` (QA#19: "cấu hình được trong DB"); feature này thêm CRUD để bàn giao ca (F24) và tổng quan (F09) dùng đúng ca mà khoa thực sự áp dụng.

## 2. Phạm vi

**Trong phạm vi**
- Bảng `areas` (`id`, `code`, `name`, `is_active`, `created_at`); cột `beds.area_id`; migration chuyển `beds.area` sang `areas`.
- API + UI: danh sách, tạo, sửa, xóa mềm, khôi phục khu vực.
- API + UI: danh sách, tạo, sửa, xóa mềm, khôi phục ca trực trên bảng `shift_definitions` có sẵn; kiểm tra không chồng giờ.
- Form giường (F03) chọn khu vực từ danh sách thay vì gõ tự do.
- Audit cho mọi thao tác ghi. Chỉ ADMIN được ghi.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Phân công nhân viên vào ca hoặc khu vực, lịch trực theo người *(không có trong nguồn)*.
- Lọc tổng quan theo khu vực, phân quyền theo khu vực *(không có trong yêu cầu 2026-11-17)*.
- Tính số liệu bàn giao ca (→ F24); hiển thị ca hiện tại (→ F09).
- Xóa cứng *(QA#36)*.

## 3. Yêu cầu chi tiết

**Khu vực**

- **R1.** Bảng `areas`: `code` (bắt buộc, duy nhất kể cả đã xóa, ví dụ `HP-1`), `name` (bắt buộc, ví dụ "Hậu phẫu 1"), `is_active`, `created_at` *(Yêu cầu người dùng 2026-11-17; PDF §10.1)*. `beds.area_id` FK → `areas`, not null.
- **R2.** Migration Alembic *(data-model.md "Quy ước"; giả định cách chuyển)*:
  - tạo `areas`; với mỗi giá trị `beds.area` khác nhau (sau khi bỏ khoảng trắng đầu/cuối) tạo một khu vực `name = giá trị đó`, `code` sinh dạng `KV01`, `KV02`… theo thứ tự chữ cái của `name`;
  - gán `beds.area_id`; rồi bỏ cột `beds.area`;
  - có `downgrade` khôi phục `beds.area` từ `areas.name`;
  - test migration trên dữ liệu mẫu có hai giường cùng khu vực và một giường khác khu vực.
- **R3.** API giường (F03) đổi: `BedCreate`/`BedUpdate` nhận `area_id` thay cho `area`; `BedOut` trả `area: {id, code, name}`. Giao diện vẫn hiện cột "Khu vực" bằng `area.name` *(Yêu cầu người dùng 2026-11-17: giữ cách hiển thị)*. Gán giường vào khu vực đã xóa hoặc không tồn tại → 400 `VALIDATION_ERROR` *(giả định)*.
- **R4.** `GET /api/v1/areas?include_inactive&limit&offset` (mọi vai trò nhân viên, không gồm `FAMILY`), `POST /api/v1/areas`, `PATCH /api/v1/areas/{id}` `{code?, name?}`, `DELETE /api/v1/areas/{id}` (xóa mềm), `POST /api/v1/areas/{id}/restore` (chỉ ADMIN) *(QA#36; api-conventions.md)*. Trùng `code` → 409 `DUPLICATE_CODE`.
- **R5.** Xóa khu vực còn giường đang dùng → 409 `AREA_IN_USE`, `details.bed_ids` *(giả định mã lỗi mới)*. Khu vực đã xóa vẫn hiện tên ở giường đã xóa và ở lịch sử *(QA#36)*.

**Ca trực**

- **R6.** Dùng bảng `shift_definitions` có sẵn (F01, F24 đọc) *(QA#19; data-model.md)*; thêm cột `is_active` (default true) và `created_at`.
- **R7.** `GET /api/v1/shifts?include_inactive` (đã có ở F24, mặc định chỉ ca đang dùng, sắp theo `start_time`); `POST /api/v1/shifts` `{name, start_time, end_time}`, `PATCH /api/v1/shifts/{id}`, `DELETE /api/v1/shifts/{id}` (xóa mềm), `POST /api/v1/shifts/{id}/restore` (chỉ ADMIN) *(QA#19; QA#36)*.
- **R8.** Kiểm tra ca *(giả định)*:
  - `name` bắt buộc, duy nhất trong các ca đang dùng → 409 `DUPLICATE_CODE`;
  - `start_time ≠ end_time`, giờ dạng `HH:mm` (phút chẵn, giây = 0) → nếu sai 400 `VALIDATION_ERROR`;
  - ca có `end_time < start_time` là ca vắt qua nửa đêm (như 22:00–06:00) *(data-model.md)*;
  - ca đang dùng **không được chồng giờ** nhau, xét theo khoảng nửa mở `[start, end)` trên vòng 24 giờ: tạo, sửa hoặc khôi phục làm chồng giờ → 409 `SHIFT_OVERLAP`, `details.conflicting_shift_ids`;
  - không bắt buộc phủ kín 24 giờ.
- **R9.** Ca đã xóa vẫn dùng được cho tra cứu bàn giao ca cũ (`GET /api/v1/handover?shift_id=<ca đã xóa>&date=` vẫn trả kết quả) nhưng không hiện trong danh sách chọn mặc định *(QA#36: bản ghi đã xóa vẫn giữ lịch sử; giả định)*. Sửa giờ của ca làm thay đổi cách tính bàn giao các ngày cũ vì bàn giao tính lúc truy vấn (F24) *(giả định; ghi rõ trên UI)*.

**Chung**

- **R10.** Quyền: ghi chỉ `ADMIN`, vai trò khác → 403 `FORBIDDEN`; đọc: mọi vai trò nhân viên; `FAMILY` → 403 *(QA#36; F35 R2)*.
- **R11.** Xóa/khôi phục lặp lại (xóa bản ghi đã xóa, khôi phục bản ghi đang dùng) trả 200, không đổi gì, không ghi audit *(giả định; giống F03 R16)*.
- **R12.** Audit, `entity_type` = `area` / `shift`: `area.create`, `area.update`, `area.delete`, `area.restore`, `shift.create`, `shift.update`, `shift.delete`, `shift.restore`, có `before`/`after` *(api-conventions.md; PRD NFR08)*.
- **R13.** UI trong "Quản lý" *(QA#15; QA#36)*:
  - tab "Khu vực": mã, tên, số giường, trạng thái; nút "Thêm", "Sửa", "Xóa" (xác nhận), "Khôi phục"; bật "Hiện mục đã xóa";
  - tab "Ca trực": tên, giờ bắt đầu, giờ kết thúc (ghi "qua nửa đêm" nếu vắt ngày), trạng thái; cùng các nút;
  - form giường (F03): ô "Khu vực" là danh sách chọn khu vực đang dùng;
  - lỗi 409 hiện `message` tiếng Việt.
- **R14.** Text chỉ nằm trong `web/src/i18n/vi.ts` *(AGENTS.md quy tắc 3)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/db/models.py` (`Area`; `Bed.area_id`; `ShiftDefinition.is_active`, `created_at`); migration trong `server/src/postcare/db/migrations/`.
  - `server/src/postcare/domain/areas.py`, `domain/shifts.py` (`shifts_overlap(a, b)` thuần, test được riêng).
  - `server/src/postcare/api/v1/areas.py`, `api/v1/shifts.py` (mở rộng router của F24); sửa `api/v1/beds.py`, schema `BedCreate`/`BedUpdate`/`BedOut`.
  - `server/src/postcare/db/seed.py`: seed khu vực mẫu và 3 ca của QA#19.
  - Test: `server/tests/api/test_areas.py`, `test_shifts_admin.py`, `server/tests/domain/test_shift_overlap.py`, `server/tests/db/test_migration_areas.py`.
  - Web: `web/src/pages/Management/AreasTab.tsx`, `ShiftsTab.tsx`, `AreaForm.tsx`, `ShiftForm.tsx`, test `AreasTab.test.tsx`, `ShiftsTab.test.tsx`; sửa `BedForm.tsx`.
- **Dữ liệu:** bảng mới `areas`; `beds.area` → `beds.area_id`; `shift_definitions` thêm `is_active`, `created_at` (xem [data-model.md](../02-architecture/data-model.md#areas-f37)).
- **API:** `GET/POST /api/v1/areas`, `PATCH/DELETE /api/v1/areas/{id}`, `POST /api/v1/areas/{id}/restore`; `GET/POST /api/v1/shifts`, `PATCH/DELETE /api/v1/shifts/{id}`, `POST /api/v1/shifts/{id}/restore` (xem [api-conventions.md](../02-architecture/api-conventions.md)). Chạy `make gen-api-types`.
- **UI:** tab "Khu vực", "Ca trực" trong "Quản lý". Text cần thêm vào `vi.ts`: `area.title` ("Khu vực"), `area.code` ("Mã khu vực"), `area.name` ("Tên khu vực"), `area.bedCount` ("Số giường"), `shift.title` ("Ca trực"), `shift.name` ("Tên ca"), `shift.start` ("Bắt đầu"), `shift.end` ("Kết thúc"), `shift.overnight` ("qua nửa đêm"), `shift.editWarning` ("Sửa giờ ca sẽ thay đổi cách tổng hợp bàn giao của các ngày trước"), dùng lại `management.add`, `management.edit`, `management.delete`, `management.restore`, `management.showDeleted`, `management.deleted` (F03).
- **Cấu hình:** không có khóa engine.

## 5. Acceptance criteria

- [x] **AC1.** Migration chuyển `beds.area` sang `areas` + `beds.area_id` không mất dữ liệu (giường cùng chuỗi khu vực về cùng một khu vực), có `downgrade`; sau migration, danh sách giường vẫn hiện đúng tên khu vực. *(Yêu cầu người dùng 2026-11-17)* — *Kiểm chứng:* test `test_migration_areas_groups_same_area`, `test_migration_areas_downgrade_restores_text`, `test_beds_list_shows_area_name`.
- [x] **AC2.** ADMIN tạo, sửa, xóa mềm, khôi phục khu vực; trùng mã → 409 `DUPLICATE_CODE`; xóa khu vực còn giường đang dùng → 409 `AREA_IN_USE`; gán giường vào khu vực đã xóa → 400. *(QA#36)* — *Kiểm chứng:* test `test_admin_crud_areas`, `test_duplicate_area_code_409`, `test_delete_area_with_active_beds_409`, `test_bed_cannot_use_deleted_area`.
- [x] **AC3.** ADMIN tạo, sửa, xóa mềm, khôi phục ca trực; ca chồng giờ (kể cả qua nửa đêm) → 409 `SHIFT_OVERLAP`; khôi phục ca gây chồng giờ → 409; `start_time = end_time` → 400. *(QA#19; QA#36)* — *Kiểm chứng:* test `test_admin_crud_shifts`, `test_shift_overlap_409`, `test_overnight_shift_overlap_detected`, `test_adjacent_shifts_do_not_overlap` (14:00–22:00 và 22:00–06:00), `test_restore_overlapping_shift_409`, `test_shift_equal_start_end_400`; unit `test_shift_overlap.py` (bảng ca).
- [x] **AC4.** Ghi chỉ ADMIN (NURSE, CHARGE_NURSE, DOCTOR → 403; FAMILY → 403 cả khi đọc); mọi thao tác ghi có audit; ca đã xóa vẫn tra cứu bàn giao được. *(QA#36; PRD NFR08)* — *Kiểm chứng:* test `test_area_shift_writes_admin_only` (tham số hóa vai trò), `test_family_cannot_read_areas_shifts`, `test_area_shift_writes_audited`, `test_handover_works_for_deleted_shift`; component test `AreasTab shows restore for deleted area`, `ShiftsTab marks overnight shift`, `BedForm selects area from list`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | DB (migration) | Upgrade/downgrade trên dữ liệu mẫu | Chuỗi khu vực khác nhau chỉ ở khoảng trắng đầu/cuối → cùng một khu vực |
| AC2 | API | CRUD khu vực; ràng buộc giường | Khu vực chỉ còn giường đã xóa → xóa được |
| AC3 | unit + API | `shifts_overlap` với bảng ca thường và qua nửa đêm | Ca kề nhau không bị coi là chồng; ca đã xóa không chặn ca mới |
| AC4 | API + component | Phân quyền, audit, bàn giao với ca đã xóa | Xóa lặp lại không sinh audit |

## 7. Giả định

- *(giả định)* Cách sinh `code` khu vực khi migration (`KV01`…), bỏ cột `beds.area` sau khi chuyển.
- *(giả định)* `BedOut.area` thành object `{id, code, name}`.
- *(giả định)* Mã lỗi mới `AREA_IN_USE`, `SHIFT_OVERLAP` (409).
- *(giả định)* Quy tắc ca: không chồng giờ theo `[start, end)` trên vòng 24 giờ, không bắt buộc phủ kín, tên duy nhất trong ca đang dùng, giờ tròn phút.
- *(giả định)* Ca đã xóa vẫn tra cứu bàn giao; sửa giờ ca ảnh hưởng tổng hợp ngày cũ.
- *(giả định)* Xóa/khôi phục lặp lại là không đổi.
- *(giả định, thêm khi làm)* Khôi phục giường thuộc khu vực đã xóa → 400 `VALIDATION_ERROR` (`details.field = "area_id"`), như gán giường vào khu vực đã xóa (R3); để không có giường đang dùng trong khu vực đã xóa.
- *(giả định, thêm khi làm)* `OverviewBedOut.area` (F09) giữ dạng chuỗi = tên khu vực; chỉ `BedOut.area` đổi thành object.
- *(giả định, thêm khi làm)* `GET /api/v1/shifts` giữ dạng mảng (không phân trang) như F24; `ShiftOut` thêm `is_active`.
- *(giả định, thêm khi làm)* Seed: khu vực "Khu hậu phẫu" mã `KV01` (trùng mã migration sinh cho DB cũ chỉ có khu vực này); nếu `KV01` đã thuộc khu vực khác thì lấy mã `KVnn` còn trống. Seed tìm khu vực theo tên trước.
- *(giả định, thêm khi làm)* Sửa ca đã xóa không kiểm tra chồng giờ; kiểm tra khi khôi phục. Tạo/sửa/khôi phục ca chạy tuần tự bằng `pg_advisory_xact_lock` để kiểm tra chồng giờ đúng khi đồng thời.

## 8. Câu hỏi mở

- Có cần lưu lịch sử giờ ca theo ngày hiệu lực để bàn giao các ngày cũ không đổi khi sửa ca không? Mặc định: không, chỉ cảnh báo trên UI. **Không chặn.**
- Khi khung giờ có khoảng trống (không thuộc ca nào), F09 hiển thị "Ca hiện tại" thế nào? Mặc định đề xuất: "Ngoài ca trực"; cập nhật F09 khi làm. **Không chặn.**

## 9. Kế hoạch triển khai

> Lập ngày 2026-11-18 (builder F37). Dùng lại pattern F03 (`domain/catalog.py`: `_check_code`, `_flush`, `_locked`, `_audit`, `{items,total}`; `require_admin`/`require_staff`; `ManagementPage` với `Section`, `RowActions`, `ConfirmDeleteDialog`).

1. **Plan** (commit `docs(F37): plan`).
2. **Test trước** (commit `test(F37): …`), xác nhận đỏ đúng lý do:
   - `server/tests/domain/test_shift_overlap.py`: bảng ca (thường/thường, qua đêm/thường, qua đêm/qua đêm, kề nhau 14–22 và 22–06 không chồng, trùng hệt, chứa nhau) cho `shifts_overlap`.
   - `server/tests/db/test_migration_areas.py`: `test_migration_areas_groups_same_area` (2 giường cùng khu vực + 1 giường khác + 1 chuỗi chỉ khác khoảng trắng; downgrade tới `0005_f04`, chèn dữ liệu, upgrade `0006`), `test_migration_areas_downgrade_restores_text`.
   - `server/tests/api/test_areas.py`: `test_admin_crud_areas`, `test_duplicate_area_code_409`, `test_delete_area_with_active_beds_409`, `test_delete_area_only_deleted_beds_ok`, `test_bed_cannot_use_deleted_area`, `test_beds_list_shows_area_name`, `test_area_shift_writes_admin_only` (tham số hóa NURSE/CHARGE_NURSE/DOCTOR/FAMILY), `test_family_cannot_read_areas_shifts`, `test_repeat_delete_restore_no_audit`.
   - `server/tests/api/test_shifts_admin.py`: `test_admin_crud_shifts`, `test_shift_overlap_409`, `test_overnight_shift_overlap_detected`, `test_adjacent_shifts_do_not_overlap`, `test_restore_overlapping_shift_409`, `test_shift_equal_start_end_400`, `test_shift_time_with_seconds_400`, `test_deleted_shift_does_not_block_new`, `test_area_shift_writes_audited`, `test_handover_works_for_deleted_shift`, `test_current_shift_ignores_deleted`.
   - Sửa test cũ dùng `area` chuỗi → `area_id` (`test_beds.py`, `test_cameras.py`, `test_catalog_delete.py`, `test_migrations.py`, `test_isolation.py`, `test_seed.py`).
3. **Model + migration** `0006_areas_shift_admin.py` (`down_revision = "0005_f04"`; ban đầu là `0005`/`0004`, đánh lại số khi merge sau F04): tạo `areas`, chèn từ `DISTINCT btrim(beds.area)` với `code = 'KV' || lpad(n, GREATEST(2, length(n)), '0')` theo `name`, gán `beds.area_id`, `NOT NULL`, FK, bỏ `beds.area`; `shift_definitions` thêm `is_active`, `created_at`. `downgrade` thêm lại `beds.area` từ `areas.name`.
4. **Domain**: `domain/areas.py` (CRUD, `AREA_IN_USE`), `domain/shifts.py` (`shifts_overlap`, CRUD, `SHIFT_OVERLAP`, `list_shifts(active_only)`), sửa `domain/catalog.py` (giường nhận `area_id`, 400 nếu khu vực đã xóa/không tồn tại), `dto.py` (`AreaRef`, `AreaOut`, `AreaCreate/Update`, `ShiftCreate/Update`, `ShiftOut.is_active`), `overview.py` (`area` = tên khu vực), `seed.py` (khu vực "Khu hậu phẫu").
5. **API**: `api/v1/areas.py`, mở rộng `api/v1/catalog.py` (shifts), đăng ký router trong `api/main.py`. `make gen-api-types`.
6. **Web**: `api/hooks.ts` (`useAreas`, `useShifts(includeInactive)`, resource `areas`/`shifts` trong `useSaveCatalogItem`/`useCatalogLifecycle`), `pages/Management/AreasTab.tsx`, `ShiftsTab.tsx`, `AreaForm.tsx`, `ShiftForm.tsx`, sửa `BedForm.tsx` (Select khu vực), `ManagementPage.tsx`; text trong khối `area`, `shift` của `vi.ts`. Test component `AreasTab.test.tsx`, `ShiftsTab.test.tsx`, `BedForm selects area from list`.
7. **Doc**: `data-model.md`, `api-conventions.md` (shape `BedOut.area`, mã lỗi, `GET /shifts`).
8. **Kiểm chứng**: `make check`, `scripts\dev.ps1 check`, curl trên DB `postcare_f37` cổng 8037; ghi §10; trạng thái In review.

**Rủi ro:** F04 song song cũng thêm migration sau `0004` → đã nối lại khi merge (F37 thành `0006`, sau `0005_f04`). `OverviewBedOut.area` giữ là chuỗi tên khu vực *(giả định: không đổi F09)*. `GET /shifts` giữ dạng danh sách (không phân trang) vì F24 đang dùng.

## 10. Ghi chú bàn giao

**2026-11-18 (builder F37).** Hoàn thành 2026-11-18. Nhánh `feat/F37-area-shift-management`.

- **Migration:** `0006_areas_shift_admin.py` (revision `0006`, `down_revision = "0005_f04"`). Ban đầu là `0005` sau `0004`; F04 merge trước với `0005_f04` nên đã đánh lại số khi merge main (2026-11-18). Test `tests/db/test_migration_areas.py` hạ về `BEFORE = "0005_f04"` và nâng lên `AREAS_REVISION = "0006"`.
- **Bằng chứng AC:**
  - AC1: `test_migration_areas_groups_same_area` (2 giường "Khu hậu phẫu" + 1 bản có khoảng trắng thừa → cùng khu vực `KV02`; "Hồi sức" → `KV01`), `test_migration_areas_downgrade_restores_text`, `test_migration_areas_empty_db`, `test_beds_list_shows_area_name`; `test_migrations.py` (schema, FK `beds.area_id → areas`, unique `areas.code`, model khớp migration).
  - AC2: `tests/api/test_areas.py` (`test_admin_crud_areas`, `test_duplicate_area_code_409`, `test_delete_area_with_active_beds_409`, `test_delete_area_only_deleted_beds_ok`, `test_bed_cannot_use_deleted_area`, `test_bed_moves_to_other_area`, `test_repeat_delete_restore_no_audit`).
  - AC3: `tests/domain/test_shift_overlap.py` (13 cặp ca × 2 chiều), `tests/api/test_shifts_admin.py` (`test_admin_crud_shifts`, `test_shift_overlap_409`, `test_overnight_shift_overlap_detected`, `test_adjacent_shifts_do_not_overlap`, `test_restore_overlapping_shift_409`, `test_shift_equal_start_end_400`, `test_shift_time_validation`, `test_deleted_shift_does_not_block_new`, `test_duplicate_active_shift_name_409`, `test_restore_duplicate_name_409`).
  - AC4: `test_area_shift_writes_admin_only` (8 endpoint ghi × NURSE/CHARGE_NURSE/DOCTOR/FAMILY → 403, không audit), `test_family_cannot_read_areas_shifts`, `test_area_shift_writes_audited`, `test_handover_works_for_deleted_shift`, `test_current_shift_ignores_deleted`; web `AreasTab.test.tsx` ("AreasTab shows restore for deleted area", 409 `AREA_IN_USE` hiện message), `ShiftsTab.test.tsx` ("ShiftsTab marks overnight shift", 409 chồng giờ, cảnh báo khi sửa), `ManagementPage.test.tsx` ("BedForm selects area from list").
- **Kiểm chứng thủ công** (DB `postcare_f37`, API cổng 8037): tạo DB ở `0004`, chèn giường `A01 "Khu hậu phẫu"`, `A02 "Khu hậu phẫu "`, `B01 "Hồi sức"`; `alembic upgrade head` → `KV01 Hồi sức (B01)`, `KV02 Khu hậu phẫu (A01, A02)`; `postcare seed` thêm A03 vào `KV02` (không tạo khu vực trùng). curl: nurse `POST /areas` → 403; admin tạo `HP-1` → 201, trùng → 409 `DUPLICATE_CODE`; `DELETE /areas/2` → 409 `AREA_IN_USE` `bed_ids [1,2,4]`; ca 12:00–16:00 → 409 `conflicting_shift_ids [1,2]`; 04:00–07:00 → 409 `[1,3]`; 21:00–01:00 → 409 `[2,3]`; 08:00–08:00 → 400; xóa Ca đêm rồi `GET /handover?shift_id=3&date=…` → 200; xóa Ca sáng, tạo 05:00–06:00 → 409 (chồng Ca đêm), khôi phục Ca sáng → 200; `audit_logs` có `area.create`, `shift.delete`, `shift.restore`. Lưu ý: Git Bash trên Windows gửi chuỗi tiếng Việt trong `-d` sai mã hóa, dùng `--data-binary @file.json`.
- **Ghi chú UI:** trang Quản lý thêm hai mục "Khu vực" và "Ca trực" (dạng mục như Giường/Bệnh nhân/Camera, không phải tab). Thành phần dùng chung tách ra `CatalogParts.tsx`, `catalogActions.ts`. Màn hình Bàn giao ca chỉ liệt kê ca đang dùng (`useShifts()` mặc định).
- `make check` và `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check` đều exit 0 (2026-11-18, DB test `postcare_w1_test`).
- **Review (2026-11-18): Đạt**, kèm điều kiện merge: F04 merge trước, F37 đánh lại migration thành `0006` sau `0005_f04`. Các mục sửa không phụ thuộc merge (5–8) đã làm trước khi merge, xem dòng dưới.
- **Merge main sau F04 (2026-11-18):** migration đổi thành `0006_areas_shift_admin.py`; `ManagementPage.tsx` gộp tay (giữ `SessionCell`, `EndSessionButton`, `TransferSessionDialog`, `PauseCaptureButton` của F04; thành phần danh mục dùng chung lấy từ `CatalogParts.tsx`/`catalogActions.ts`); `sessionTestUtils.tsx` dùng `area` dạng object; `make gen-api-types` chạy lại. `make check` và `scripts\dev.ps1 check` chạy lại sau merge.
- **Sửa theo review (2026-11-18):** (5) `data-model.md` liệt kê migration của F37; (6) seed chỉ dùng khu vực "Khu hậu phẫu" **đang dùng**, khu vực đã xóa bị bỏ qua và tạo khu vực mới với mã còn trống (`test_seed_area_skips_deleted_area`, `test_seed_area_prefers_active_area`); (7) mã migration `'KV' || lpad(n, GREATEST(2, length(n)), '0')` → `KV99`, `KV100`… không bị cắt (`test_migration_area_codes_beyond_99`); (8) seed bỏ qua ca mẫu chồng giờ một ca đang dùng, ca đã xóa không chặn (`test_seed_shifts_do_not_overlap_existing`, `test_seed_shifts_ignore_deleted_overlap`).

## 11. Definition of Done

- [x] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [x] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [x] Doc liên quan đã cập nhật cùng PR.
- [x] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
