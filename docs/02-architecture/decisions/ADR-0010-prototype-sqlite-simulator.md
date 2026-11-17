# ADR-0010: Prototype đề xuất dùng SQLite, create_all và bộ giả lập thay worker AI

- **Trạng thái:** Thay thế một phần. Mục 1 (SQLite) và mục 2 (`create_all`) bị thay bởi F01 theo [ADR-0004](ADR-0004-postgresql.md) (17/11/2026). Mục 3 (bộ giả lập) vẫn hiệu lực tới khi có worker thật
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** yêu cầu người dùng (tạo code base chạy được để đề xuất, chưa cần phần AI); HS §8.3 (kịch bản demo); ADR-0002, ADR-0004

## Bối cảnh

Người dùng cần một code base chạy được ngay để trình bày các phần chính (đăng nhập, Tổng quan, Theo dõi trực tiếp, Cảnh báo, Lịch sử theo dõi, Bàn giao ca, Quản lý giường) **trước** khi làm roadmap F00–F30. Máy dev chưa có PostgreSQL; phần AI (MediaPipe, camera, engine) chưa được xây dựng.

ADR-0004 chọn PostgreSQL và Alembic. ADR-0002 định nghĩa worker gửi dữ liệu qua API nội bộ.

## Quyết định

1. **SQLite file là mặc định** (`server/postcare.db`, gitignore). PostgreSQL vẫn dùng được qua `DATABASE_URL=postgresql+psycopg://…` và `uv sync --extra postgres`.
   - Không dùng tính năng chỉ có ở PostgreSQL: cột JSON thay JSONB; enum lưu dạng VARCHAR + CHECK (`native_enum=False`); thời gian lưu UTC qua kiểu `UTCDateTime` (SQLite không giữ múi giờ).
   - "1 phiên mở / giường và / bệnh nhân": domain kiểm tra trước để trả 409; thêm partial unique index (cả SQLite và PostgreSQL đều hỗ trợ) làm lớp chặn cuối; có test.
   - Idempotent theo `event_uid`: kiểm tra tồn tại + bắt `IntegrityError` thay cho `ON CONFLICT DO NOTHING`.
2. **`Base.metadata.create_all` thay Alembic** (API tự tạo bảng khi khởi động; `postcare seed` xóa và tạo lại toàn bộ dữ liệu mẫu). Chưa có migration.
3. **Bộ giả lập thay worker AI:** `uv run postcare simulate --bed A01 [--scenario …]` đóng vai worker, gọi đúng API nội bộ của ADR-0002 (`config`, `heartbeat` 2 s, `state`, `events` với `event_uid` UUID, header `X-Worker-Token`). Kịch bản mặc định theo HS §8.3: Nằm → SIT_UP → BED_EDGE → STAND_UP → BED_EXIT (HIGH) → (chờ) → RETURN_TO_BED. Kịch bản phụ: `observation-lost`, `abnormal-movement`, `face-attention`, `posture-change`, dùng đúng mã trong event-engine.md mục 5.
   - Màn hình "Theo dõi trực tiếp" vẽ hình người que + vùng giường từ `bed.state`, ghi rõ là dữ liệu mô phỏng. Không có MJPEG.
   - Module `engine`, `vision`, `pipeline`, `worker`, `replay`, `eval` mới chỉ có `__init__.py`.
4. Thư viện thêm ngoài tech-stack.md: `tzdata` (zoneinfo trên Windows cần dữ liệu múi giờ), `jsdom` (môi trường test Vitest). Chưa dùng `msw`, `import-linter`, `mypy`, `pre-commit`, `honcho`, `alembic` trong prototype. *(Cập nhật F00, 17/11/2026: `msw`, `import-linter`, `mypy`, `pre-commit`, `honcho` đã được thêm ở F00; `alembic` vẫn để F01.)*

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **SQLite + create_all + giả lập** | Chạy ngay, không cần cài DB, demo được toàn bộ luồng cảnh báo | Lệch ADR-0004 (tạm thời); không có migration; chưa chứng minh phần AI |
| PostgreSQL + Alembic ngay | Đúng kiến trúc đích | Phải cài PostgreSQL trên mọi máy xem đề xuất; chậm có bản chạy được |
| Mock dữ liệu tĩnh phía frontend | Nhanh nhất | Không kiểm chứng được API, vòng đời cảnh báo, "lưu trước phát sau" |

## Hệ quả

- Bản prototype **không** hoàn thành acceptance criteria của các feature F00–F24; các feature đó vẫn Todo trong roadmap.
- **Điều kiện quay lại PostgreSQL + Alembic (làm ở F01):**
  - thêm Alembic (`server/src/postcare/db/migrations/`), migration đầu tiên tạo đúng các bảng hiện có (đổi JSON → JSONB, enum native, partial unique index), có `downgrade`;
  - bỏ `create_all` khỏi lúc khởi động API, `make db-upgrade` / `make db-seed` thay `postcare seed`;
  - test chạy trên `TEST_DATABASE_URL` PostgreSQL (rollback mỗi test) như testing.md; giữ SQLite chỉ cho chạy nhanh nếu nhóm muốn.
- **Điều kiện thay bộ giả lập:** khi F05/F06/F10–F15 xong, `postcare worker --camera-id N` gửi dữ liệu thật qua cùng API nội bộ; `postcare simulate` giữ lại làm công cụ demo/kiểm thử dự phòng (HS §8.3: video dự phòng).
- Khi đổi lại, đánh dấu ADR này "Thay thế bởi ADR-XXXX".
- *(Cập nhật F01, 17/11/2026)* Điều kiện quay lại PostgreSQL + Alembic đã làm: migration `0001` (bảng nền F01) và `0002` (giữ `events`, `alerts`, `cameras.last_config_hash` của prototype), API không còn `create_all`, `make db-upgrade` / `make db-seed` là lệnh thật, `make seed` thành `postcare seed --reset` (xóa và tạo lại dữ liệu demo), test chạy trên `TEST_DATABASE_URL` với rollback. SQLite đã bỏ hoàn toàn.
