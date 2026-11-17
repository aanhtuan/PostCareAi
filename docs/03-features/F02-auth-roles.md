# F02 – Đăng nhập và phân quyền

| Thuộc tính | Giá trị |
|---|---|
| Mã | F02 |
| Trạng thái | Done <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F01 |
| Nhánh code | B+C |
| Nguồn | PDF §3 (tr.4–5), §10.1 (tr.12–13); HS §2.2; QA#18; A09, A10; PRD NFR06 |

## 1. Mục tiêu

Cho phép nhân viên đăng nhập bằng tên đăng nhập và mật khẩu, nhận JWT, và giới hạn thao tác theo 4 vai trò: điều dưỡng, phụ trách ca, bác sĩ (chỉ xem), quản trị (PDF §3; HS §2.2; QA#18). Mọi feature backend sau dùng chung guard phân quyền và định dạng lỗi của feature này. Giao diện có trang Đăng nhập tiếng Việt và khung ứng dụng hiển thị người đang đăng nhập.

## 2. Phạm vi

**Trong phạm vi**
- `POST /api/v1/auth/login`, `GET /api/v1/auth/me`.
- Tạo và kiểm tra JWT; dependency lấy người dùng hiện tại; guard theo vai trò.
- Định dạng lỗi chung `{error:{code,message,details}}`, lớp `DomainError`, handler bọc lỗi 422 thành `VALIDATION_ERROR` (đây là feature đầu tiên trả lỗi nghiệp vụ).
- Web: trang Đăng nhập, lưu token, client fetch gắn `Authorization`, tự quay về trang đăng nhập khi gặp 401, khung ứng dụng (header có tên, vai trò, nút Đăng xuất), route guard theo vai trò.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Quản lý người dùng trên UI, đổi mật khẩu (→ F35).
- Token cho worker `X-Worker-Token` (→ F06).
- Xác thực WebSocket/MJPEG qua `?token=` (→ F07, F18). F02 cung cấp hàm giải mã token dùng lại được.
- HTTPS (không làm, A09).
- Refresh token, khóa tài khoản khi nhập sai nhiều lần *(không có trong nguồn)*.

## 3. Yêu cầu chi tiết

- **R1.** `POST /api/v1/auth/login` nhận `{username, password}`. Đúng → 200 `{access_token, token_type: "bearer", user: {id, username, full_name, role}}` *(api-conventions.md; QA#18)*.
- **R2.** Sai tên đăng nhập, sai mật khẩu hoặc tài khoản `is_active = false` → 401 `INVALID_CREDENTIALS`, cùng một thông báo cho mọi trường hợp *(api-conventions.md; giả định: không tiết lộ tài khoản có tồn tại hay không)*.
- **R3.** JWT ký bằng `JWT_SECRET` (biến môi trường), có `sub` (user id), `role`, `exp`. Hết hạn sau 8 giờ *(A10)*. Thời hạn đặt trong settings, không viết cứng *(giả định)*.
- **R4.** Mật khẩu kiểm tra bằng pwdlib/bcrypt, dùng lại `hash_password()` của F01 *(tech-stack.md; PRD NFR06)*. Không API nào trả `password_hash` *(giả định: tối thiểu hóa lộ thông tin)*.
- **R5.** Header `Authorization: Bearer <token>`. Thiếu, sai chữ ký, hết hạn, hoặc người dùng đã bị ngừng → 401 `UNAUTHORIZED` *(api-conventions.md)*.
- **R6.** Dependency `get_current_user` và `require_roles(*roles)` ở `postcare/api/auth.py`. Sai vai trò → 403 `FORBIDDEN` *(api-conventions.md)*. Ma trận quyền theo bảng "Xác thực và phân quyền" của api-conventions.md *(QA#18)*; DOCTOR chỉ đọc.
- **R7.** `GET /api/v1/auth/me` trả người dùng hiện tại *(api-conventions.md)*.
- **R8.** Định dạng lỗi chung *(api-conventions.md "Lỗi"; coding-standards.md §2)*:
  - `DomainError(code, message, http_status, details=None)`, handler chung chuyển sang `{error:{code,message,details}}`;
  - lỗi validation 422 của FastAPI bọc lại thành `VALIDATION_ERROR`;
  - `message` viết tiếng Việt.
- **R9.** Web, trang "Đăng nhập" *(PDF §9 (tr.11))*:
  - form tên đăng nhập + mật khẩu, nút "Đăng nhập", hiện thông báo lỗi tiếng Việt khi sai;
  - đăng nhập xong chuyển về trang "Tổng quan" (`/`);
  - header hiện họ tên và vai trò bằng tiếng Việt: Điều dưỡng / Phụ trách ca / Bác sĩ / Quản trị *(PRD §3)*;
  - nút "Đăng xuất" xóa token và về trang đăng nhập.
- **R10.** Client fetch (`web/src/api/client.ts`) gắn token vào mọi request. Gặp 401 → xóa token, chuyển về trang đăng nhập *(QA#18; api-conventions.md; giả định cách xử lý phía web)*.
- **R11.** Token lưu ở `localStorage` *(giả định: giữ đăng nhập khi tải lại trang; chỉ chạy trong LAN)*.
- **R12.** Route guard phía web: ẩn hoặc chặn trang/nút mà vai trò không có quyền (ví dụ màn hình quản trị chỉ ADMIN). Backend vẫn là nơi kiểm tra quyền chính *(giả định)*.
- **R13.** Mọi text giao diện nằm trong `web/src/i18n/vi.ts` *(ADR-0005)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/deps.py` (JWT `create_token`/`user_from_token`, `get_current_user`, `require_roles`, `require_writer`). Prototype đặt sẵn ở đây; không tách thêm `api/auth.py` để tránh hai nơi định nghĩa guard.
  - `server/src/postcare/domain/errors.py` (`DomainError`) và `server/src/postcare/api/errors.py` (handler chung) *(giả định: tách để `domain` raise được mà không import `api`)*.
  - `server/src/postcare/api/v1/auth.py` (router).
  - `server/src/postcare/domain/users.py` (`authenticate(username, password)`).
  - `server/src/postcare/domain/security.py` (thêm `verify_password`).
  - `server/tests/api/test_auth.py`, `server/tests/api/test_role_guard.py`, `server/tests/api/test_errors.py`.
  - `web/src/components/AppLayout.tsx` (khung ứng dụng, header) thay cho `AppShellLayout.tsx`; `web/src/components/AppLayout.test.tsx`, `web/src/auth/RequireRole.test.tsx`.
  - `web/src/api/client.ts`, `web/src/auth/AuthContext.tsx`, `web/src/auth/RequireRole.tsx`, `web/src/pages/Login/LoginPage.tsx`, `web/src/components/AppShellLayout.tsx`.
  - `web/src/pages/Login/LoginPage.test.tsx`, `web/src/api/client.test.ts`.
- **Dữ liệu:** đọc `users` (xem [data-model.md](../02-architecture/data-model.md#users-f01)).
- **API:** `POST /api/v1/auth/login`, `GET /api/v1/auth/me` (xem [api-conventions.md](../02-architecture/api-conventions.md#xác-thực-và-phân-quyền)). Chạy `make gen-api-types` sau khi thêm.
- **UI:** trang "Đăng nhập"; khung ứng dụng có header. Text cần thêm vào `vi.ts`: `auth.title` ("Đăng nhập"), `auth.username` ("Tên đăng nhập"), `auth.password` ("Mật khẩu"), `auth.submit` ("Đăng nhập"), `auth.logout` ("Đăng xuất"), `auth.invalid` ("Tên đăng nhập hoặc mật khẩu không đúng"), `role.NURSE`…`role.ADMIN`.
- **Cấu hình:** `JWT_SECRET` (đã có trong `.env.example`); thời hạn token trong settings.

## 5. Acceptance criteria

- [x] **AC1.** `POST /api/v1/auth/login` với thông tin đúng trả JWT và thông tin người dùng; sai mật khẩu, sai tên hoặc tài khoản đã ngừng → 401 `INVALID_CREDENTIALS`. *(QA#18)* — *Kiểm chứng:* test `test_login_success_returns_jwt`, `test_login_wrong_password_401`, `test_login_unknown_user_401`, `test_login_inactive_user_401`.
- [x] **AC2.** Guard theo vai trò: DOCTOR gọi một API ghi → 403 `FORBIDDEN`; không có token hoặc token sai → 401 `UNAUTHORIZED`. *(api-conventions.md)* — *Kiểm chứng:* test `test_doctor_write_forbidden` (router ghi tạm chỉ mount trong test), `test_missing_token_401`, `test_bad_signature_401`.
- [x] **AC3.** UI: trang Đăng nhập tiếng Việt; gặp 401 thì tự quay về trang đăng nhập; header hiện họ tên và vai trò tiếng Việt. *(PDF §9 (tr.11); QA#18)* — *Kiểm chứng:* component test `LoginPage shows error on 401`, `client redirects to login on 401`, `header shows full name and role label`.
- [x] **AC4.** Mật khẩu lưu dạng hash (không có API nào trả `password_hash`). Token hết hạn sau 8 giờ: token quá hạn → 401. *(A10)* — *Kiểm chứng:* test `test_password_stored_as_hash`, `test_me_does_not_expose_password_hash`, `test_token_expiry_is_8_hours`, `test_expired_token_401` (tạo token với thời điểm giả lập, không `sleep`).

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | `test_login_success_returns_jwt` | Sai mật khẩu, sai tên, tài khoản ngừng → 401 cùng một `code` và `message` |
| AC1 | API | `test_validation_error_format` (body thiếu trường) | 422 bọc thành `VALIDATION_ERROR` theo định dạng chung |
| AC2 | API | `test_role_matrix` (tham số hóa theo 4 vai trò, router tạm trong test) | DOCTOR ghi → 403; thiếu/sai token → 401 |
| AC3 | component | `LoginPage.test.tsx`, `client.test.ts` (msw) | 401 ở bất kỳ request nào → về trang đăng nhập |
| AC4 | unit + API | `test_password_stored_as_hash`, `test_token_expiry_is_8_hours`, `test_expired_token_401` | `/auth/me` không có trường `password_hash` |

## 7. Giả định

- *(giả định)* Tài khoản ngừng dùng trả cùng lỗi `INVALID_CREDENTIALS` như sai mật khẩu.
- *(giả định)* Token lưu ở `localStorage`.
- *(giả định)* Không có refresh token; hết hạn thì đăng nhập lại.
- *(giả định)* Không ghi audit cho đăng nhập (nguồn chỉ yêu cầu audit cho thay đổi trạng thái phiên/cảnh báo/cấu hình).
- *(giả định)* `DomainError` đặt ở `postcare/domain/errors.py` để `domain` dùng được mà không vi phạm ranh giới import (`domain` không được import `api`); handler đặt ở `api`.
- *(giả định)* Thuật toán ký JWT là HS256.

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

**Khảo sát (2026-11-17):** prototype đã có phần lớn F02. Không viết lại code đang chạy; chỉ bổ sung test theo đúng tên trong §5 và lấp chỗ thiếu.

| Yêu cầu / AC | Đã có | Bằng chứng | Còn thiếu |
|---|---|---|---|
| R1, R2 / AC1 | `api/v1/auth.py`, `domain/users.py::authenticate` (cùng lỗi cho sai tên, sai mật khẩu, tài khoản ngừng) | `tests/test_auth.py::test_login_returns_token_and_user`, `test_login_wrong_password_and_unknown_user_same_error` | Test tài khoản ngừng; test cùng `message` |
| R3 / AC4 | `api/deps.py::create_token` (HS256, `sub`, `role`, `exp`), `Settings.jwt_expire_hours = 8` | Chưa có test | Test 8 giờ, token quá hạn → 401 (cần cho `create_token` nhận `now` để giả lập thời điểm) |
| R4 / AC4 | `domain/security.py` (`hash_password`, `verify_password`), `UserOut` không có `password_hash` | Một phần trong test login | Test hash trong DB, `/auth/me` không có `password_hash` |
| R5, R6 / AC2 | `deps.py::get_current_user`, `require_roles`, `require_writer`; vai trò và `is_active` đọc từ DB mỗi request | `tests/test_auth.py::test_missing_or_bad_token_is_401`, `test_doctor_is_read_only` | Test sai chữ ký, người dùng bị ngừng giữa chừng, ma trận 4 vai trò với router tạm |
| R7 | `GET /auth/me` | test login | — |
| R8 | `domain/errors.py::DomainError`, `api/errors.py` | `test_validation_error_is_wrapped` | Test định dạng đủ `{code,message,details}` |
| WS `?token=` 4401 (F18) | `api/realtime.py` dùng `user_from_token` | `tests/test_realtime_seed.py` | Thêm ca token hết hạn → 4401 |
| R9, R11, R13 / AC3 | `pages/Login/LoginPage.tsx`, `auth/AuthContext.tsx`, `components/AppLayout.tsx`, `vi.ts` (`auth.*`, `role.*`) | Chưa có component test | `LoginPage.test.tsx`, test header |
| R10 / AC3 | `api/client.ts` (gắn token, 401 → xóa token + handler) | Chưa có test | `client.test.ts` (msw) |
| R12 | Nút ghi ẩn theo `canWrite` (`AlertActions`, `ManagementPage`) | — | `auth/RequireRole.tsx` dùng lại được (chưa có màn hình chỉ ADMIN; F03/F08/F35 sẽ dùng) + test |

**Bước:**

1. Chuyển `server/tests/test_auth.py` → `server/tests/api/test_auth.py`, thêm `test_login_success_returns_jwt`, `test_login_wrong_password_401`, `test_login_unknown_user_401`, `test_login_inactive_user_401`, `test_password_stored_as_hash`, `test_me_does_not_expose_password_hash`, `test_token_expiry_is_8_hours`, `test_expired_token_401`, `test_deactivated_user_token_401`, `test_ws_expired_token_closes_4401`.
2. `server/tests/api/test_role_guard.py`: router ghi tạm chỉ mount trong test; `test_role_matrix` tham số hóa 4 vai trò, `test_doctor_write_forbidden`, `test_missing_token_401`, `test_bad_signature_401`.
3. `server/tests/api/test_errors.py`: `test_validation_error_format`, `test_domain_error_format`.
4. Code: `create_token(user, settings, now=None)` để test giả lập thời điểm (không đổi API).
5. Web test: `web/src/api/client.test.ts` (gắn header, 401 → xóa token + về đăng nhập; 401 của `/auth/login` không gọi handler), `web/src/pages/Login/LoginPage.test.tsx` (lỗi tiếng Việt khi 401, đăng nhập xong về `/`), `web/src/components/AppLayout.test.tsx` (`header shows full name and role label`, nút Đăng xuất).
6. `web/src/auth/RequireRole.tsx` + `RequireRole.test.tsx`.
7. Doc: cập nhật §4 spec (guard nằm ở `api/deps.py`, không tách `api/auth.py`), `api-conventions.md` nếu cần. Không đổi API → không cần `make gen-api-types` (chạy để xác nhận không có diff).
8. `make check`, `scripts\dev.ps1 check`, kiểm tra thủ công bằng curl, ghi §10.

**Không làm (F35/F36):** vai trò `FAMILY`, `require_staff`, quản lý người dùng. `require_roles(*roles)` nhận tập vai trò bất kỳ nên thêm vai trò sau không phải sửa guard.

**Rủi ro:** test cũ giả định vị trí file `tests/test_auth.py` (không có). Thêm `tests/api/__init__.py` để tránh trùng tên module.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-17 (builder F02):** chuyển sang In review.

Bằng chứng theo AC:

- **AC1:** `server/tests/api/test_auth.py::test_login_success_returns_jwt`, `test_login_wrong_password_401`, `test_login_unknown_user_401`, `test_login_inactive_user_401` (cùng `code` và `message`); `server/tests/api/test_errors.py::test_validation_error_format`, `test_domain_error_format`.
- **AC2:** `server/tests/api/test_role_guard.py::test_role_matrix` (4 vai trò × đọc/ghi/chỉ ADMIN, router tạm chỉ mount trong test), `test_doctor_write_forbidden`, `test_missing_token_401`, `test_bad_signature_401`, `test_role_comes_from_db_not_token`; `test_auth.py::test_doctor_is_read_only` (endpoint thật), `test_deactivated_user_token_401`, `test_ws_expired_token_closes_4401`.
- **AC3:** `web/src/pages/Login/LoginPage.test.tsx` (`LoginPage shows error on 401`, đăng nhập xong về `/`, token bị từ chối → về trang đăng nhập), `web/src/api/client.test.ts` (`client redirects to login on 401`, gắn `Authorization`, 401 của login và 403 không chuyển trang), `web/src/components/AppLayout.test.tsx` (`header shows full name and role label` cho 4 vai trò, nút Đăng xuất).
- **AC4:** `test_password_stored_as_hash`, `test_me_does_not_expose_password_hash`, `test_token_expiry_is_8_hours`, `test_expired_token_401` (thời điểm cấp giả lập qua `create_token(..., now=)`, không `sleep`).

Thay đổi code: `create_token` nhận `now` tùy chọn; thêm `web/src/auth/RequireRole.tsx` (route guard dùng lại được, chưa gắn vào route nào vì chưa có màn hình chỉ ADMIN; F03/F08/F35 dùng). Không đổi API (`check-api-types` xanh, không cần sinh lại type). `server/tests/test_auth.py` chuyển sang `server/tests/api/test_auth.py`.

Kiểm tra: `make check` và `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check` exit 0 (214 test server, 47 test web), chạy với `TEST_DATABASE_URL=.../postcare_f02_test` vì nhiều builder dùng chung PostgreSQL.

Kiểm chứng thủ công (API chạy cổng 8102, DB đã seed, curl):

| Yêu cầu | Kết quả |
|---|---|
| `POST /auth/login` nurse sai mật khẩu | 401 `INVALID_CREDENTIALS` |
| `GET /auth/me` với token nurse / doctor | 200, không có `password_hash` |
| doctor `GET /overview` | 200 |
| doctor `POST /sessions` | 403 `FORBIDDEN` |
| nurse `POST /sessions` | 201 |
| `GET /overview` không token | 401 `UNAUTHORIZED` |

Không làm (F35/F36): vai trò `FAMILY`, `require_staff`, quản lý người dùng. `require_roles(*roles)` nhận tập vai trò bất kỳ và đọc vai trò từ DB nên thêm vai trò sau không phải sửa guard.

**2026-11-17, review: Đạt.** Đã sửa theo góp ý review (test viết trước, commit `06e6c66`, `f370c65`, `a937485`):

1. **Bí mật mặc định:** `Settings.ensure_secure_secrets()` (`server/src/postcare/settings.py`) từ chối `JWT_SECRET` / `WORKER_TOKEN` bắt đầu bằng `change-me` hoặc ngắn hơn 32 byte (`InsecureSecretError`, thông báo tiếng Việt + tiếng Anh, kèm lệnh tạo giá trị). API gọi hàm này trong lifespan: `uvicorn` dừng với "Application startup failed"; import module (sinh OpenAPI) vẫn chạy. `.env.example` có giá trị chỉ dùng cho dev (`dev-only-…`, ≥ 32 byte); README §2 và `dev-setup.md` §3 hướng dẫn copy `.env` và tạo giá trị mới. Worker và giả lập đọc cùng `.env` qua `get_settings()`. Fixture test dùng `WORKER_TOKEN` ≥ 32 byte; CI không cần thêm biến. Test: `server/tests/test_settings_secrets.py` (mặc định, mặc định cũ đủ dài, ngắn, tính theo byte, API từ chối khởi động / khởi động được, `.env.example` hợp lệ). Kiểm chứng thủ công: không có `.env` thì `uvicorn postcare.api.main:app` báo `InsecureSecretError` và thoát.
2. **Thời gian đăng nhập:** `authenticate` (`server/src/postcare/domain/users.py`) luôn gọi `verify_password`, với `DUMMY_PASSWORD_HASH` (bcrypt của chuỗi ngẫu nhiên) khi không có tài khoản, kể cả tài khoản ngừng. Test: `server/tests/domain/test_users.py` (cả hai nhánh đều gọi verify).
3. `RequireRole` chưa gắn vào route nào; gắn khi có màn hình chỉ ADMIN (F03, F08, F35).

`make check` và `scripts\dev.ps1 check` exit 0 (231 test server, 47 test web) với `TEST_DATABASE_URL=.../postcare_f02_test`.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
