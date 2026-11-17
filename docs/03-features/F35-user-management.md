# F35 – Quản lý người dùng

| Thuộc tính | Giá trị |
|---|---|
| Mã | F35 |
| Trạng thái | In review <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F02 |
| Nhánh code | B+C |
| Nguồn | Yêu cầu người dùng (2026-11-17); QA#36 (quản lý tài khoản là MVP); QA#31 (vai trò `FAMILY`); QA#18; PDF §10 (tr.12), §10.1 (tr.12–13); PRD §3, US11, NFR06, NFR08 |

## 1. Mục tiêu

Cho ADMIN quản lý tài khoản trên giao diện thay vì chỉ tạo bằng seed (QA#18 cũ; nay QA#36 đưa vào MVP): xem danh sách, tạo, sửa họ tên và vai trò (gồm vai trò mới `FAMILY` của QA#31), khóa/mở khóa (xóa mềm bằng `is_active`), đặt lại mật khẩu. PDF §10 và §10.1 có thực thể người dùng và nhật ký thao tác do backend quản lý; mọi thao tác ghi audit (PRD NFR08). Feature này cũng đưa `FAMILY` vào enum vai trò và chặn mặc định mọi API nhân viên cho vai trò đó, để F36 mở đúng phần được phép.

## 2. Phạm vi

**Trong phạm vi**
- Thêm `FAMILY` vào `UserRole` (`postcare.schemas`), nhãn tiếng Việt "Người nhà".
- Guard `require_staff` (NURSE, CHARGE_NURSE, DOCTOR, ADMIN) thay cho "mọi vai trò đã đăng nhập" ở các endpoint đọc của nhân viên.
- API và màn hình: danh sách (lọc vai trò, gồm tài khoản đã khóa), tạo, sửa họ tên và vai trò, khóa, mở khóa, đặt lại mật khẩu. Chỉ ADMIN.
- Chặn tự khóa mình và khóa/hạ vai trò ADMIN cuối cùng đang hoạt động.
- Audit mọi thao tác ghi, không chứa mật khẩu hay hash.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Tự đăng ký, quên mật khẩu qua email, SSO, xác thực hai lớp *(không có trong nguồn)*.
- Người dùng tự đổi mật khẩu của mình *(không có trong yêu cầu 2026-11-17; xem Câu hỏi mở)*.
- Cấp quyền xem phiên cho người nhà (→ F36). F35 chỉ tạo tài khoản `FAMILY`.
- Phân quyền chi tiết hơn 5 vai trò.
- Xóa cứng tài khoản *(QA#36: chỉ xóa mềm)*.

## 3. Yêu cầu chi tiết

- **R1.** `UserRole` có 5 giá trị: `NURSE`, `CHARGE_NURSE`, `DOCTOR`, `ADMIN`, `FAMILY` *(QA#18; QA#31)*. Nhãn: Điều dưỡng / Phụ trách ca / Bác sĩ / Quản trị / Người nhà *(PRD §3)*. Enum DB khớp enum schema (test so sánh, data-model.md).
- **R2.** Chặn mặc định cho `FAMILY` *(QA#31; giả định: an toàn khi F36 chưa xong)*:
  - mọi endpoint đọc của nhân viên dùng `require_staff`; `FAMILY` → 403 `FORBIDDEN`;
  - `FAMILY` chỉ gọi được `POST /auth/login`, `GET /auth/me` (và các endpoint `/api/v1/family/...` khi có F36);
  - WebSocket: trước F36, kết nối của `FAMILY` bị đóng mã 4403 *(giả định; F36 R12)*;
  - web: `FAMILY` đăng nhập xong vào `/family` (trước F36 là trang "Chưa có quyền xem"), không thấy menu nhân viên.
- **R3.** Endpoint, chỉ `ADMIN`; vai trò khác → 403 `FORBIDDEN` *(QA#36; api-conventions.md ma trận quyền)*:
  - `GET /api/v1/users?role&include_inactive&limit&offset` → `{items, total}`;
  - `GET /api/v1/users/{id}`;
  - `POST /api/v1/users` `{username, full_name, role, password}` → 201;
  - `PATCH /api/v1/users/{id}` `{full_name?, role?}`;
  - `POST /api/v1/users/{id}/lock`, `POST /api/v1/users/{id}/unlock`;
  - `POST /api/v1/users/{id}/reset-password` `{new_password}` → 204.
- **R4.** `UserOut` gồm `id`, `username`, `full_name`, `role`, `is_active`, `created_at`. **Không** có `password_hash` *(F02 R4; PRD NFR06)*. Schema request `extra="forbid"`.
- **R5.** `username`: bỏ khoảng trắng đầu/cuối, chữ thường, 3–64 ký tự `[a-z0-9._-]` *(giả định)*; duy nhất kể cả tài khoản đã khóa → 409 `DUPLICATE_CODE` với `details.field = "username"` *(api-conventions.md; giả định dùng lại mã lỗi)*. `username` không sửa được sau khi tạo *(giả định: audit và đăng nhập dựa vào nó)*.
- **R6.** Mật khẩu: tối thiểu 8 ký tự *(giả định)*; lưu bằng `hash_password()` (pwdlib/bcrypt) *(F02 R4; PRD NFR06)*. Đặt lại mật khẩu do ADMIN nhập mật khẩu mới và báo trực tiếp cho người dùng *(giả định: không có email)*.
- **R7.** Khóa = `is_active = false`; mở khóa = `is_active = true` *(QA#36)*. Tài khoản bị khóa:
  - không đăng nhập được (401 `INVALID_CREDENTIALS`, F02 R2);
  - token đang có bị từ chối ở request kế tiếp (401 `UNAUTHORIZED`, F02 R5);
  - kết nối WebSocket đang mở bị đóng mã 4401 *(giả định)*; với `FAMILY`, luồng nhận `family.access_ended` (`ACCOUNT_LOCKED`) trước khi đóng (F36 R14).

  Khóa tài khoản đã khóa hoặc mở khóa tài khoản đang dùng: trả 200, không đổi gì, không ghi audit *(giả định: thao tác lặp là vô hại)*.
- **R8.** Chặn tự gây mất quyền quản trị *(giả định: tránh khóa hệ thống)*:
  - ADMIN khóa chính mình hoặc tự đổi vai trò khỏi `ADMIN` → 409 `CANNOT_MODIFY_SELF`;
  - khóa hoặc đổi vai trò ADMIN cuối cùng đang hoạt động → 409 `LAST_ADMIN`.
- **R9.** Vai trò kiểm tra theo DB ở mỗi request (không tin `role` trong JWT), để đổi vai trò hoặc khóa có hiệu lực ngay *(giả định; bổ sung F02 R3, R5)*. Đổi vai trò khỏi `FAMILY` làm quyền xem của người đó hết hiệu lực (F36 R5).
- **R10.** Audit *(PDF §10.1; PRD NFR08)*, `entity_type = "user"`: `user.create`, `user.update`, `user.lock`, `user.unlock`, `user.reset_password`. `before`/`after` chỉ gồm `username`, `full_name`, `role`, `is_active`; **không bao giờ** có mật khẩu hay hash. Audit nằm cùng transaction với thay đổi.
- **R11.** Màn hình "Người dùng" (`/management/users`), chỉ ADMIN thấy menu và vào được *(F02 R12)*:
  - bảng: tên đăng nhập, họ tên, vai trò (nhãn tiếng Việt), trạng thái ("Đang dùng" / "Đã khóa");
  - lọc theo vai trò, bật "Hiện tài khoản đã khóa";
  - nút "Thêm người dùng", "Sửa", "Khóa" (có hộp thoại xác nhận), "Mở khóa", "Đặt lại mật khẩu";
  - lỗi 409 hiện `message` tiếng Việt của API.
- **R12.** Text chỉ nằm trong `web/src/i18n/vi.ts`, không có từ cấm, không hiện mã vai trò `FAMILY`… *(AGENTS.md quy tắc 3)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/schemas/enums.py` (`UserRole.FAMILY`).
  - `server/src/postcare/api/deps.py`: `STAFF_ROLES`, `require_staff`, `require_admin`; `get_current_user` đọc vai trò từ DB (đã có từ F02).
  - `server/src/postcare/domain/users.py` (`create_user`, `update_user`, `lock_user`, `unlock_user`, `reset_password`); `server/src/postcare/api/v1/users.py`.
  - Schema: `UserCreate`, `UserUpdate`, `UserOut`, `PasswordReset`.
  - Test: `server/tests/api/test_users.py`, `test_family_role_default_deny.py`.
  - Web: `web/src/api/users.ts` (hook), `web/src/pages/Management/Users/UsersPage.tsx`, `UserForm.tsx`, `ResetPasswordDialog.tsx`, `errors.ts`, `UsersPage.test.tsx`; `web/src/pages/Family/FamilyPlaceholder.tsx` (thay bằng F36).
- **Dữ liệu:** `users` (đã có từ F01); enum `user_role` thêm `FAMILY` (migration 0003 `ALTER TYPE user_role ADD VALUE 'FAMILY'`; enum native, không phải CHECK); ghi `audit_logs` ([data-model.md](../02-architecture/data-model.md#users-f01)).
- **API:** `GET/POST /api/v1/users`, `GET/PATCH /api/v1/users/{id}`, `POST /api/v1/users/{id}/lock|unlock|reset-password` ([api-conventions.md](../02-architecture/api-conventions.md)). Chạy `make gen-api-types`.
- **UI:** "Người dùng" trong "Quản lý". Text cần thêm vào `vi.ts`: `users.title` ("Người dùng"), `users.add` ("Thêm người dùng"), `users.username` ("Tên đăng nhập"), `users.fullName` ("Họ tên"), `users.role` ("Vai trò"), `users.status.active` ("Đang dùng"), `users.status.locked` ("Đã khóa"), `users.lock` ("Khóa"), `users.unlock` ("Mở khóa"), `users.confirmLock` ("Khóa tài khoản này? Người dùng sẽ không đăng nhập được."), `users.resetPassword` ("Đặt lại mật khẩu"), `users.newPassword` ("Mật khẩu mới"), `users.showLocked` ("Hiện tài khoản đã khóa"), `role.FAMILY` ("Người nhà"), `family.noAccess` ("Chưa có quyền xem").
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [x] **AC1.** ADMIN liệt kê, tạo, sửa họ tên và vai trò (gồm `FAMILY`), khóa, mở khóa, đặt lại mật khẩu; `NURSE`, `CHARGE_NURSE`, `DOCTOR`, `FAMILY` gọi bất kỳ endpoint `/users` nào → 403. *(QA#36; QA#31)* — *Kiểm chứng:* test `test_admin_user_crud`, `test_admin_can_create_family_user`, `test_users_endpoints_admin_only` (tham số hóa 4 vai trò), `test_reset_password_allows_new_login`.
- [x] **AC2.** Trùng `username` (kể cả khác hoa thường, khoảng trắng) → 409 `DUPLICATE_CODE`; tài khoản bị khóa không đăng nhập được và token cũ bị từ chối; mở khóa thì đăng nhập lại được. *(QA#36; F02)* — *Kiểm chứng:* test `test_duplicate_username_409`, `test_locked_user_cannot_login`, `test_locked_user_token_rejected`, `test_unlock_restores_login`.
- [x] **AC3.** ADMIN tự khóa hoặc tự hạ vai trò → 409 `CANNOT_MODIFY_SELF`; khóa hoặc hạ vai trò ADMIN cuối cùng đang hoạt động → 409 `LAST_ADMIN`; khi còn ADMIN khác thì làm được. *(giả định)* — *Kiểm chứng:* test `test_cannot_lock_self`, `test_cannot_demote_self`, `test_cannot_lock_last_admin`, `test_can_lock_admin_when_another_exists`.
- [x] **AC4.** Mọi thao tác ghi có audit đúng action; `before`/`after` không chứa mật khẩu hay hash; response không có `password_hash`. *(PDF §10.1; PRD NFR06, NFR08)* — *Kiểm chứng:* test `test_user_writes_audited`, `test_audit_never_contains_password` (quét JSON audit tìm mật khẩu thử và tiền tố hash `$2`), `test_user_out_has_no_password_hash`.
- [x] **AC5.** Tài khoản `FAMILY` bị chặn mặc định: mọi endpoint nhân viên → 403; WebSocket bị đóng 4403; web đưa về `/family`. Đổi vai trò có hiệu lực ngay ở request kế tiếp. *(QA#31; giả định)* — *Kiểm chứng:* test `test_family_forbidden_on_staff_read_endpoints` (tham số hóa `/beds`, `/sessions`, `/overview`, `/alerts`, `/timeline`, `/handover`), `test_family_ws_closed_4403`, `test_role_change_effective_next_request`; component test `UsersPage lists users with Vietnamese role labels`, `non-admin cannot open users page`, `family user redirected to /family`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | CRUD người dùng theo vai trò | Vai trò không phải ADMIN → 403; `role = "FOO"` → 400; gửi thêm `password_hash` → 400 |
| AC2 | API | Trùng tên, khóa/mở khóa, đăng nhập | Mật khẩu < 8 ký tự → 400; `username` có ký tự lạ → 400 |
| AC3 | API | Tự khóa, ADMIN cuối cùng | Hai ADMIN: khóa một người được, người còn lại thì không |
| AC4 | API | Quét `audit_logs` | Khóa lặp lại không sinh audit |
| AC5 | API + WS + component | Chặn mặc định `FAMILY`; đổi vai trò | Token cũ mang `role=ADMIN` của người đã bị hạ vai trò → 403 ở endpoint ADMIN |
| — | component | `UsersPage.test.tsx` | Hộp thoại xác nhận trước khi khóa |

## 7. Giả định

- *(giả định)* Quy tắc `username` (R5), mật khẩu tối thiểu 8 ký tự (R6), `username` không sửa được.
- *(giả định)* Dùng lại `DUPLICATE_CODE` cho trùng `username`; mã lỗi mới `CANNOT_MODIFY_SELF`, `LAST_ADMIN` (409).
- *(giả định)* Vai trò đọc từ DB ở mỗi request.
- *(giả định)* Khóa đóng WebSocket đang mở; khóa/mở khóa lặp là không đổi, không audit.
- *(giả định)* `FAMILY` bị chặn mặc định ở mọi endpoint và WS cho tới khi F36 mở phần được phép.
- *(giả định)* Lỗi định dạng request (vai trò lạ, trường thừa, `username` sai, mật khẩu ngắn) trả 422 `VALIDATION_ERROR` theo quy ước chung của api-conventions.md, không phải 400 như bảng §6.
- *(giả định)* Thao tác vừa là tự khóa vừa là khóa ADMIN cuối cùng trả `LAST_ADMIN` (kiểm tra trước `CANNOT_MODIFY_SELF`). Qua API, `LAST_ADMIN` chỉ xảy ra khi ADMIN duy nhất tự thao tác lên mình.
- *(giả định)* Mật khẩu tối đa 72 byte (giới hạn của bcrypt). Nút "Khóa" bị vô hiệu ở dòng của chính mình (backend vẫn chặn).

## 8. Câu hỏi mở

- Người dùng có cần tự đổi mật khẩu của mình (sau khi ADMIN đặt lại) không? Mặc định: không trong MVP. **Không chặn.**
- Tài khoản `FAMILY` có nên tự khóa khi mọi quyền xem đã hết không? Mặc định: không, ADMIN khóa thủ công. **Không chặn.**

## 9. Kế hoạch triển khai

**Khảo sát (2026-11-18):** đã có `api/deps.py` (`get_current_user` đọc người dùng và `is_active` từ DB mỗi request, `require_roles`, `require_writer`), `domain/users.py` (`authenticate`, `get_active_user`), `domain/security.py` (`hash_password`), `domain/audit.py::record_audit`, `api/realtime.py` (WS đóng 4401). R9 (vai trò đọc từ DB) đã đúng từ F02; chỉ thêm test. Guard nằm ở `api/deps.py` (không tách `api/auth.py`, như F02 §9).

**Bước:**

1. Test trước (đỏ đúng lý do): `server/tests/api/test_users.py` (AC1–AC4, tên như §5), `server/tests/api/test_family_role_default_deny.py` (AC5: REST tham số hóa `/beds`, `/patients`, `/cameras`, `/shifts`, `/sessions`, `/overview`, `/events`, `/alerts`, `/timeline`, `/handover`; WS 4403; `test_role_change_effective_next_request`), `server/tests/db/test_enums_match.py` (thêm `FAMILY`), `test_ws_closed_when_user_locked` (4401).
2. Migration `0003_user_role_family`: `ALTER TYPE user_role ADD VALUE 'FAMILY'` (downgrade: tạo lại enum không có `FAMILY`, chỉ được khi không còn tài khoản `FAMILY`). `UserRole.FAMILY` trong `schemas/enums.py`.
3. `api/deps.py`: `STAFF_ROLES`, `require_staff`; `require_writer`/`require_roles` không đổi. Thay `get_current_user` bằng `require_staff` ở mọi route đọc nhân viên (`catalog`, `monitoring`, `sessions`, `alerts`). WS: `FAMILY` → 4403.
4. `domain/users.py`: `list_users`, `get_user`, `create_user`, `update_user`, `lock_user`, `unlock_user`, `reset_password`; kiểm tra `CANNOT_MODIFY_SELF`, `LAST_ADMIN` (khóa `SELECT ... FOR UPDATE` các ADMIN đang hoạt động); audit cùng transaction. DTO `UserOut` (+`is_active`, `created_at`), `UserCreate`, `UserUpdate`, `PasswordReset` (`extra="forbid"`, chuẩn hóa `username`).
5. `api/v1/users.py` (chỉ ADMIN). Khóa: sau commit gọi `publisher.disconnect_user(user_id)`; `WsHub` giữ `user_id` của từng kết nối và đóng 4401.
6. `make gen-api-types`.
7. Web: `vi.ts` khối `users`, `role.FAMILY`, `family.noAccess`; `api/hooks.ts` hook người dùng; `api/client.ts` thêm `PATCH`; `pages/Management/Users/{UsersPage,UserForm,ResetPasswordDialog}.tsx` + `UsersPage.test.tsx`; route `/management/users` bọc `RequireRole roles={['ADMIN']}`; menu "Người dùng" chỉ ADMIN; `FAMILY` → `/family` (`pages/Family/FamilyPlaceholder.tsx`, ngoài layout nhân viên, không mở WS).
8. Doc: `api-conventions.md` (lỗi 422 cho validation, WS), `data-model.md` (migration 0003). `make check`, `scripts\dev.ps1 check`, curl thủ công, ghi §10.

**Rủi ro:** `ALTER TYPE ... ADD VALUE` trong transaction (PostgreSQL 16 cho phép nếu không dùng giá trị mới trong cùng transaction). Thêm trường vào `UserOut` làm đổi fixture test web (sửa cùng PR). Xung đột merge với F03 ở `App.tsx`, `AppLayout.tsx`, `vi.ts`, `hooks.ts`, `client.ts`: giữ thay đổi tách khối.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-18 (builder F35):** chuyển sang In review. Nhánh `feat/F35-user-management`.

Bằng chứng theo AC (test ở `server/tests/api/test_users.py`, `server/tests/api/test_family_role_default_deny.py`, `web/src/pages/Management/Users/UsersPage.test.tsx`):

- **AC1:** `test_admin_user_crud`, `test_admin_can_create_family_user`, `test_users_endpoints_admin_only[nurse|charge|doctor|family]` (7 endpoint, đều 403), `test_users_endpoints_require_login`, `test_reset_password_allows_new_login`; ca âm tính `test_create_user_validation` (vai trò `FOO`, thừa `password_hash`, mật khẩu 7 ký tự, `username` ngắn/có dấu/có `/`, họ tên rỗng), `test_patch_rejects_unknown_fields`, `test_reset_password_too_short`.
- **AC2:** `test_duplicate_username_409` (khác hoa thường, khoảng trắng), `test_duplicate_username_includes_locked`, `test_username_normalized`, `test_locked_user_cannot_login`, `test_locked_user_token_rejected`, `test_unlock_restores_login`, `test_ws_closed_when_user_locked` (4401).
- **AC3:** `test_cannot_lock_self`, `test_cannot_demote_self`, `test_cannot_lock_last_admin`, `test_last_admin_guard_in_domain`, `test_two_admins_lock_one_not_the_other`, `test_can_lock_admin_when_another_exists`.
- **AC4:** `test_user_writes_audited` (khóa/mở khóa lặp không audit), `test_noop_update_not_audited`, `test_audit_never_contains_password` (không có mật khẩu thử, `$2`, `password`), `test_user_out_has_no_password_hash`.
- **AC5:** `test_family_forbidden_on_staff_read_endpoints` (13 endpoint: `/beds`, `/patients`, `/cameras`, `/shifts`, `/sessions`, `/sessions/1`, `/sessions/1/timeline`, `/overview`, `/events`, `/alerts`, `/alerts/1`, `/timeline`, `/handover`), `test_family_forbidden_on_staff_write_endpoints`, `test_family_can_login_and_me`, `test_family_ws_closed_4403`, `test_role_change_effective_next_request`, `test_demoted_admin_old_token_forbidden`; component `UsersPage lists users with Vietnamese role labels`, `asks for confirmation before locking`, `shows the Vietnamese API message on 409`, `non-admin cannot open users page`, `admin sees the users menu item`, `family user redirected to /family`; `AppLayout.test.tsx` `users menu item only for ADMIN`. R1: `tests/db/test_enums_match.py::test_user_role_values_match_qa18_qa31`.

Kiểm chứng:

- `make check` exit 0 (396 passed; web 55 passed). `scripts\dev.ps1 check` exit 0.
- Thủ công (curl, API dev cổng 8035, DB `postcare_f35`): tạo `" NguoiNha01 "` vai trò `FAMILY` → 201, `username` = `nguoinha01`; tạo trùng → 409 `DUPLICATE_CODE` `details.field=username`; `FAMILY` gọi `/api/v1/beds` → 403 `FORBIDDEN`, `/auth/me` → 200; đặt lại mật khẩu → 204, mật khẩu cũ 401, mới 200; khóa → 200 `is_active=false`, token cũ → 401; ADMIN duy nhất tự khóa → 409 `LAST_ADMIN`; NURSE `GET /users` → 403; mở khóa → 200.

Điều người sau cần biết:

- `UserOut` có thêm `is_active`, `created_at` (cả ở `/auth/login`, `/auth/me`); fixture test web đã cập nhật.
- Đóng WS khi khóa: `WsHub` lưu `user_id` từng kết nối; route khóa gọi `notifications.disconnect_user()` sau commit. F36 cần thêm `family.access_ended` (`ACCOUNT_LOCKED`) trước khi đóng.
- F36 thay `pages/Family/FamilyPlaceholder.tsx`, và thay nhánh đóng 4403 trong `api/realtime.py` bằng luồng `family.*`.
- Đăng nhập (F02) chỉ bỏ khoảng trắng, không chuyển chữ thường; tài khoản tạo ở F35 luôn chữ thường.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
