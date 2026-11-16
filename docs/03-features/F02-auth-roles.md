# F02 – Đăng nhập và phân quyền

| Thuộc tính | Giá trị |
|---|---|
| Mã | F02 |
| Trạng thái | Todo <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
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
  - `server/src/postcare/api/auth.py` (JWT, `get_current_user`, `require_roles`).
  - `server/src/postcare/domain/errors.py` (`DomainError`) và `server/src/postcare/api/errors.py` (handler chung) *(giả định: tách để `domain` raise được mà không import `api`)*.
  - `server/src/postcare/api/v1/auth.py` (router).
  - `server/src/postcare/domain/users.py` (`authenticate(username, password)`).
  - `server/src/postcare/domain/security.py` (thêm `verify_password`).
  - `server/tests/api/test_auth.py`, `server/tests/api/test_role_guard.py`, `server/tests/api/test_errors.py`.
  - `web/src/api/client.ts`, `web/src/auth/AuthContext.tsx`, `web/src/auth/RequireRole.tsx`, `web/src/pages/Login/LoginPage.tsx`, `web/src/components/AppShellLayout.tsx`.
  - `web/src/pages/Login/LoginPage.test.tsx`, `web/src/api/client.test.ts`.
- **Dữ liệu:** đọc `users` (xem [data-model.md](../02-architecture/data-model.md#users-f01)).
- **API:** `POST /api/v1/auth/login`, `GET /api/v1/auth/me` (xem [api-conventions.md](../02-architecture/api-conventions.md#xác-thực-và-phân-quyền)). Chạy `make gen-api-types` sau khi thêm.
- **UI:** trang "Đăng nhập"; khung ứng dụng có header. Text cần thêm vào `vi.ts`: `auth.title` ("Đăng nhập"), `auth.username` ("Tên đăng nhập"), `auth.password` ("Mật khẩu"), `auth.submit` ("Đăng nhập"), `auth.logout` ("Đăng xuất"), `auth.invalid` ("Tên đăng nhập hoặc mật khẩu không đúng"), `role.NURSE`…`role.ADMIN`.
- **Cấu hình:** `JWT_SECRET` (đã có trong `.env.example`); thời hạn token trong settings.

## 5. Acceptance criteria

- [ ] **AC1.** `POST /api/v1/auth/login` với thông tin đúng trả JWT và thông tin người dùng; sai mật khẩu, sai tên hoặc tài khoản đã ngừng → 401 `INVALID_CREDENTIALS`. *(QA#18)* — *Kiểm chứng:* test `test_login_success_returns_jwt`, `test_login_wrong_password_401`, `test_login_unknown_user_401`, `test_login_inactive_user_401`.
- [ ] **AC2.** Guard theo vai trò: DOCTOR gọi một API ghi → 403 `FORBIDDEN`; không có token hoặc token sai → 401 `UNAUTHORIZED`. *(api-conventions.md)* — *Kiểm chứng:* test `test_doctor_write_forbidden` (router ghi tạm chỉ mount trong test), `test_missing_token_401`, `test_bad_signature_401`.
- [ ] **AC3.** UI: trang Đăng nhập tiếng Việt; gặp 401 thì tự quay về trang đăng nhập; header hiện họ tên và vai trò tiếng Việt. *(PDF §9 (tr.11); QA#18)* — *Kiểm chứng:* component test `LoginPage shows error on 401`, `client redirects to login on 401`, `header shows full name and role label`.
- [ ] **AC4.** Mật khẩu lưu dạng hash (không có API nào trả `password_hash`). Token hết hạn sau 8 giờ: token quá hạn → 401. *(A10)* — *Kiểm chứng:* test `test_password_stored_as_hash`, `test_me_does_not_expose_password_hash`, `test_token_expiry_is_8_hours`, `test_expired_token_401` (tạo token với thời điểm giả lập, không `sleep`).

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
