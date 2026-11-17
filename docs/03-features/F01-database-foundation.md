# F01 – CSDL và migration nền

| Thuộc tính | Giá trị |
|---|---|
| Mã | F01 |
| Trạng thái | In progress <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F00 |
| Nhánh code | B (backend) |
| Nguồn | PDF §10 (tr.12), §10.1 (tr.12–13); HS §6.2, Hình 3; QA#18, QA#19; ADR-0004 |

## 1. Mục tiêu

Dựng tầng dữ liệu PostgreSQL cho các thực thể nền: người dùng, bệnh nhân, giường, camera, phiên theo dõi, nhật ký thao tác, ca trực (PDF §10, §10.1; HS §6.2). Có migration Alembic hai chiều, dữ liệu mẫu, DB test riêng và helper ghi audit log dùng chung. Đây là nền cho mọi feature backend sau (F02–F04, F06, F17…).

## 2. Phạm vi

**Trong phạm vi**
- Kết nối DB qua SQLAlchemy 2.0 + psycopg 3, cấu hình bằng biến môi trường.
- Migration tạo 7 bảng có cột "Tạo ở F01" trong [data-model.md](../02-architecture/data-model.md): `users`, `patients`, `beds`, `cameras`, `monitoring_sessions`, `audit_logs`, `shift_definitions`, cùng các enum và ràng buộc của chúng.
- Lệnh seed dữ liệu mẫu.
- Fixture test DB (`postcare_test`, rollback mỗi test).
- Service Postgres trong CI.
- Helper `record_audit()`.
- Thay target giữ chỗ `db-upgrade`, `db-seed` của F00 bằng lệnh thật.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Bảng `events`, `alerts` (→ F17).
- API CRUD, logic nghiệp vụ phiên theo dõi (→ F03, F04).
- Xác minh mật khẩu, JWT (→ F02). F01 chỉ cần hàm băm mật khẩu để seed.
- Dữ liệu demo đầy đủ (phiên đang mở, sự kiện mẫu) (→ F30 `make demo-seed`).

## 3. Yêu cầu chi tiết

- **R1.** Cấu hình kết nối đọc từ biến môi trường `DATABASE_URL` và `TEST_DATABASE_URL` (đã có trong `.env.example`) qua pydantic-settings *(`.env.example`; testing.md §3)*.
- **R2.** Model SQLAlchemy và migration khớp **đúng** data-model.md cho 7 bảng: tên cột, kiểu, `NOT NULL`, default, unique *(data-model.md)*. Gồm:
  - enum `user_role` (`NURSE`, `CHARGE_NURSE`, `DOCTOR`, `ADMIN`) *(QA#18)*;
  - enum `camera_source_type` (`WEBCAM`, `URL`, `FILE`), `display_mode` (`RAW`, `BLUR`, `SKELETON`, default `BLUR` theo A08), `camera_status` (`ONLINE`, `OFFLINE`, `UNKNOWN`);
  - `cameras.bed_id` unique (MVP 1 camera / giường) *(QA#13)*;
  - `cameras.roi_polygon` jsonb, `cameras.thresholds` jsonb default `{}`, `cameras.config_version` default 1;
  - hai partial unique index của `monitoring_sessions`: `UNIQUE (bed_id) WHERE ended_at IS NULL`, `UNIQUE (patient_id) WHERE ended_at IS NULL` *(data-model.md; logic dùng ở F04)*;
  - mọi cột thời gian là `timestamptz`, lưu UTC *(data-model.md "Quy ước")*.
- **R3.** Bảng `patients` **không** có cột họ tên hay ảnh *(PDF §10.1; HS §6.3)*.
- **R4.** Enum dùng chung giữa API và worker (`CameraSourceType`, `DisplayMode`, `CameraStatus`) định nghĩa ở `postcare/schemas/`; `UserRole` cũng đặt ở `postcare/schemas/` *(data-model.md: "Enum trong DB phải khớp enum trong `postcare.schemas`"; giả định vị trí file)*. Có test so sánh giá trị enum Python với enum trong DB.
- **R5.** Mỗi migration có `downgrade`. `alembic downgrade base` rồi `alembic upgrade head` chạy được không lỗi *(coding-standards.md §2)*.
- **R6.** `make db-upgrade` chạy `alembic upgrade head` trên `DATABASE_URL` *(PDF §10.1; ADR-0004)*.
- **R7.** `make db-seed` gọi lệnh CLI `postcare seed` *(overview.md §3: CLI có `seed`)*, tạo:
  - giường `A01`, `A02`, `A03` *(HS Hình 3)*, cùng khu vực *(giả định: "Khu hậu phẫu")*;
  - 1 camera gắn `A01` *(giả định: tên "Camera A01", `source_type = WEBCAM`, `source = "0"`)*;
  - 4 tài khoản, mỗi vai trò một tài khoản *(QA#18; giả định tên đăng nhập `nurse`, `charge`, `doctor`, `admin`; mật khẩu dev lấy từ biến `SEED_PASSWORD`, mặc định `postcare`; chỉ dùng cho dev)*;
  - 3 ca: "Ca sáng" 06:00–14:00, "Ca chiều" 14:00–22:00, "Ca đêm" 22:00–06:00 *(QA#19; data-model.md)*.
- **R8.** Seed **idempotent**: chạy lại không tạo bản ghi trùng và không ghi đè dữ liệu người dùng đã sửa *(giả định: để chạy lại an toàn trên máy dev)*.
- **R9.** Mật khẩu seed lưu dạng hash bằng pwdlib (bcrypt) *(tech-stack.md; PRD NFR06)*. Hàm `hash_password()` đặt ở `postcare/domain/security.py` để F02 dùng lại *(giả định vị trí)*.
- **R10.** Test DB *(testing.md §3; ADR-0004)*:
  - dùng `TEST_DATABASE_URL` (DB `postcare_test`), không bao giờ chạm DB dev;
  - schema tạo bằng `alembic upgrade head` một lần mỗi lần chạy test;
  - fixture `db_session` bọc mỗi test trong transaction và rollback sau test;
  - không kết nối được DB test → test báo lỗi rõ ràng, **không** tự skip *(giả định: tránh `make check` xanh giả)*.
- **R11.** CI: thêm service container `postgres:16` vào `.github/workflows/ci.yml`, đặt `TEST_DATABASE_URL` *(ADR-0004)*.
- **R12.** Helper `record_audit(session, *, actor_user_id, action, entity_type, entity_id, before=None, after=None)` ở `postcare/domain/audit.py` *(api-conventions.md "Quy ước code backend")*:
  - chỉ thêm bản ghi vào session hiện tại, **không** tự commit, để audit và thay đổi nghiệp vụ cùng một transaction *(giả định)*;
  - `actor_user_id = None` nghĩa là hệ thống/worker *(data-model.md)*;
  - `before`/`after` phải serialize được sang JSON (datetime → ISO 8601 UTC);
  - không có hàm update hay delete cho `audit_logs` *(data-model.md: "Bảng chỉ INSERT")*.
- **R13.** Session DB cho FastAPI qua dependency `get_session` *(coding-standards.md §2)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/settings.py` (pydantic-settings: `DATABASE_URL`, `TEST_DATABASE_URL`…) *(giả định tên file)*.
  - `server/src/postcare/db/base.py`, `db/models.py` (hoặc `db/models/*.py`), `db/session.py`.
  - `server/src/postcare/db/migrations/` (Alembic `env.py`, `versions/0001_foundation.py`), `server/alembic.ini` *(giả định vị trí)*.
  - `server/src/postcare/schemas/enums.py` (`UserRole`, `CameraSourceType`, `DisplayMode`, `CameraStatus`) *(giả định tên file)*.
  - `server/src/postcare/domain/audit.py`, `domain/security.py`, `domain/seed.py`.
  - `server/src/postcare/cli.py`: lệnh `seed`.
  - `server/tests/conftest.py` (fixture `db_session`), `server/tests/db/test_migrations.py`, `server/tests/db/test_seed.py`, `server/tests/db/test_enums_match.py`, `server/tests/domain/test_audit.py`.
  - `Makefile`: `db-upgrade`, `db-seed` thật. `.github/workflows/ci.yml`: service Postgres.
- **Dữ liệu:** `users`, `patients`, `beds`, `cameras`, `monitoring_sessions`, `audit_logs`, `shift_definitions` (xem [data-model.md](../02-architecture/data-model.md)).
- **API:** không có endpoint mới.
- **UI:** không có.
- **Cấu hình:** không đổi `engine.default.yaml`.

## 5. Acceptance criteria

- [ ] **AC1.** `make db-upgrade` trên DB rỗng tạo đủ 7 bảng `users`, `patients`, `beds`, `cameras`, `monitoring_sessions`, `audit_logs`, `shift_definitions` với cột, enum và ràng buộc đúng data-model.md (kể cả 2 partial unique index). *(PDF §10.1)* — *Kiểm chứng:* test `test_upgrade_creates_foundation_tables` (đọc bằng SQLAlchemy `inspect`); test `test_enums_match_schemas`.
- [ ] **AC2.** `make db-seed` tạo giường A01–A03, 1 camera gắn A01, 4 tài khoản (mỗi vai trò một, mật khẩu đã hash), 3 ca; chạy lần hai không tạo trùng. *(HS Hình 3; QA#18, QA#19)* — *Kiểm chứng:* test `test_seed_creates_sample_data`, `test_seed_is_idempotent`, `test_seed_passwords_are_hashed`.
- [ ] **AC3.** Test dùng DB `postcare_test` riêng; dữ liệu một test tạo ra không còn ở test sau. CI có service Postgres và `make check` xanh trên CI. *(testing.md §3)* — *Kiểm chứng:* cặp test `test_rollback_isolation_a` / `test_rollback_isolation_b`; job CI xanh.
- [ ] **AC4.** `alembic downgrade base` rồi `alembic upgrade head` chạy được hai chiều không lỗi. *(coding-standards.md §2: mỗi migration có `downgrade`)* — *Kiểm chứng:* test `test_migrations_roundtrip` (upgrade → downgrade base → upgrade).
- [ ] **AC5.** Có helper `record_audit()` dùng chung, kèm test: ghi đúng actor, action, entity, before/after; actor null cho hệ thống; không tự commit. *(PDF §10.1; api-conventions.md "Quy ước code backend")* — *Kiểm chứng:* test `test_record_audit_inserts_row`, `test_record_audit_system_actor`, `test_record_audit_rolls_back_with_transaction`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | DB | `test_upgrade_creates_foundation_tables`; `test_enums_match_schemas` | `test_patients_has_no_name_or_photo_column`; chèn 2 camera cùng `bed_id` → `IntegrityError` |
| AC1 | DB | `test_partial_unique_open_session_per_bed`, `..._per_patient` | Phiên đã đóng (`ended_at` có giá trị) không chặn phiên mới |
| AC2 | DB | `test_seed_creates_sample_data`, `test_seed_passwords_are_hashed` | `test_seed_is_idempotent` (chạy 2 lần, số bản ghi không đổi) |
| AC3 | DB | `test_rollback_isolation_a` / `_b` | Thiếu `TEST_DATABASE_URL` hoặc DB không kết nối được → lỗi rõ ràng, không skip |
| AC4 | DB | `test_migrations_roundtrip` | — |
| AC5 | unit (DB) | `test_record_audit_inserts_row`, `test_record_audit_system_actor` | `test_record_audit_rolls_back_with_transaction` (rollback thì không còn bản ghi audit) |

## 7. Giả định

- *(giả định)* Khu vực seed là "Khu hậu phẫu" cho cả 3 giường.
- *(giả định)* Camera seed: `WEBCAM`, `source = "0"`; sửa được ở F03.
- *(giả định)* Tên đăng nhập seed `nurse`, `charge`, `doctor`, `admin`. Mật khẩu từ biến `SEED_PASSWORD` (mặc định `postcare`), chỉ dùng trên máy dev. Biến này cần thêm vào `.env.example` cùng PR.
- *(giả định)* Seed idempotent theo khóa tự nhiên (`username`, `beds.code`, tên ca, `cameras.bed_id`).
- *(giả định)* Enum dùng chung đặt ở `postcare/schemas/enums.py`. `postcare.db` import `postcare.schemas` để dùng enum (overview.md không cấm, nhưng cột "Được import" của `db` chỉ ghi `sqlalchemy`; cập nhật overview.md cùng PR nếu cần).
- *(giả định)* Thư mục migration nằm trong `server/src/postcare/db/migrations/`.
- *(giả định)* `record_audit()` không commit; người gọi commit.
- *(giả định)* Không kết nối được DB test thì test lỗi, không skip.
- *(giả định, thêm khi lập kế hoạch)* `TEST_DATABASE_URL` phải khác `DATABASE_URL` và tên database phải kết thúc bằng `_test`; nếu không, test dừng với lỗi rõ ràng (để không bao giờ chạm DB dev).
- *(giả định, thêm khi lập kế hoạch)* Cột có `default` trong data-model.md cũng là `NOT NULL` (ví dụ `is_active`, `created_at`, `thresholds`), trừ cột ghi rõ `null`. Cột `shift_definitions.name/start_time/end_time` là `NOT NULL`.
- *(giả định, thêm khi lập kế hoạch)* Để prototype (ADR-0010) vẫn chạy, migration thứ hai `0002_prototype_events_alerts` tạo `events`, `alerts` (đúng data-model.md) và cột `cameras.last_config_hash` mà prototype đang dùng. F17 tiếp nhận hai bảng này (sửa bằng migration mới, không sửa 0002).
- *(giả định, thêm khi lập kế hoạch)* Dữ liệu demo của prototype (camera A02/A03, ROI mẫu, bệnh nhân BN-001…BN-005, phiên và sự kiện quá khứ) chỉ tạo khi chạy `postcare seed --reset` (`make seed`), không thuộc `make db-seed`. F30 sẽ thay bằng `make demo-seed`.

## 8. Câu hỏi mở

- Có seed sẵn vài bệnh nhân mã thử nghiệm (ví dụ `BN-001`) để thử F04 nhanh hơn không? Mặc định: không (danh sách seed đã duyệt chỉ gồm giường, camera, tài khoản, ca; bệnh nhân tạo qua F03). **Không chặn.**

## 9. Kế hoạch triển khai

Khảo sát: prototype (ADR-0010) đã có `db/models.py` (9 bảng, SQLite, `create_all`), `db/session.py`, `db/types.py` (`UTCDateTime`), `domain/audit.py` (`record_audit`), `domain/security.py` (`hash_password`), `domain/seed.py`, `schemas/enums.py` (đủ 4 enum của R4), `settings.py`, `api/deps.py` (`get_db`), CLI `postcare seed` (xóa và tạo lại). Test API dùng SQLite tạm mỗi test. Kế hoạch là chuyển các phần này sang PostgreSQL + Alembic, không viết lại từ đầu.

1. **Phụ thuộc và cấu hình.** `server/pyproject.toml`: đưa `psycopg[binary]` từ extra `postgres` vào phụ thuộc chính, thêm `alembic` (lý do: ADR-0004; tech-stack.md đã liệt kê). `settings.py`: `database_url` mặc định PostgreSQL, thêm `test_database_url`. `.env.example`: `DATABASE_URL`, `TEST_DATABASE_URL`, `SEED_PASSWORD` (R1).
2. **Hạ tầng test DB.** `server/tests/conftest.py`:
   - fixture phiên `test_engine`: kiểm tra URL an toàn (khác `DATABASE_URL`, tên kết thúc `_test`), thử kết nối; lỗi thì `pytest.fail` kèm hướng dẫn `docker start postcare-db` (không skip); rồi `alembic upgrade head` một lần;
   - fixture `connection` (transaction ngoài, rollback cuối test) và `db_session` (`join_transaction_mode="create_savepoint"`, nên `commit()` trong code chỉ nhả savepoint);
   - fixture `app`/`client` của test API cũ dùng cùng `connection` (`app.state.session_factory` gắn vào connection), `TRUNCATE … RESTART IDENTITY` trong transaction để id bắt đầu từ 1 như test cũ giả định;
   - fixture `committed_app` cho test "lưu trước, phát sau" cần kết nối thứ hai thật: commit thật, dọn bằng `TRUNCATE` sau test;
   - hàm kiểm tra URL đặt ở `server/tests/dbutil.py` để test được.
3. **Test viết trước** (chạy, xác nhận đỏ đúng lý do):
   - `tests/db/test_migrations.py` (AC1, AC4): `test_upgrade_creates_foundation_tables` (đọc bằng `inspect`: cột, kiểu, NOT NULL, default, unique, FK cho 7 bảng); `test_partial_unique_indexes_exist`; `test_patients_has_no_name_or_photo_column` (âm tính); `test_two_cameras_same_bed_rejected` (âm tính, `IntegrityError`); `test_partial_unique_open_session_per_bed`, `..._per_patient`; `test_closed_session_does_not_block_new_one` (âm tính); `test_models_match_migrations` (`alembic.autogenerate.compare_metadata` rỗng); `test_migrations_roundtrip` (upgrade → downgrade base → không còn bảng/enum → upgrade head).
   - `tests/db/test_enums_match.py` (AC1, R4): `test_enums_match_schemas` (so `pg_enum` với enum trong `postcare.schemas`).
   - `tests/db/test_seed.py` (AC2): `test_seed_creates_sample_data`, `test_seed_passwords_are_hashed`, `test_seed_is_idempotent` (chạy 2 lần, số bản ghi không đổi), `test_seed_does_not_overwrite_edited_data` (âm tính, R8).
   - `tests/db/test_isolation.py` (AC3): `test_rollback_isolation_a` / `_b`; `test_test_url_must_differ_from_dev_url`, `test_test_url_must_end_with_test`, `test_unreachable_test_db_fails_clearly` (âm tính R10).
   - `tests/domain/test_audit.py` (AC5): `test_record_audit_inserts_row`, `test_record_audit_system_actor`, `test_record_audit_rolls_back_with_transaction` (âm tính), `test_record_audit_serializes_datetime_utc`, `test_record_audit_does_not_commit`.
   - `tests/test_tooling.py`: `db-upgrade`, `db-seed` không còn là target giữ chỗ; recipe gọi `alembic upgrade head` / `postcare seed`; `dev.ps1` tương ứng; CI có service `postgres:16` và `TEST_DATABASE_URL` (R6, R7, R11).
4. **Model và migration.** `db/models.py`: kiểu PostgreSQL (`BigInteger` PK, `Text`, `JSONB`, enum native, `timestamptz` qua `UTCDateTime`), `server_default` theo data-model.md. `db/base.py`: `Base` với quy ước đặt tên constraint. `db/session.py`: bỏ nhánh SQLite, bỏ `create_schema`/`reset_schema`. `db/migrate.py`: `alembic_config(url)`, `upgrade_head(url)`, `reset_schema(url)` qua Alembic API. `server/alembic.ini`, `db/migrations/env.py` (URL lấy từ config hoặc `DATABASE_URL`; nhận connection có sẵn khi test), `versions/0001_foundation.py` (7 bảng, 4 enum, 2 partial unique index, `downgrade` xóa cả enum), `versions/0002_prototype_events_alerts.py`.
5. **Seed.** `domain/seed.py`: `seed_base()` idempotent theo khóa tự nhiên, chỉ thêm, không sửa bản ghi có sẵn, trả số bản ghi đã tạo; đúng R7 (1 camera "Camera A01", WEBCAM, "0"). `seed_demo()` (prototype: camera A02/A03, ROI mẫu, BN-001…BN-005) và `seed_history()` giữ cho `make seed`. CLI: `postcare seed` (chỉ `seed_base`), `postcare seed --reset [--no-history]` (xóa schema bằng Alembic, tạo lại, thêm dữ liệu demo; thay `make seed` cũ).
6. **Audit và session.** `domain/audit.py`: chuyển `before`/`after` sang JSON (datetime → ISO 8601 UTC, date/time → ISO, enum → value), không commit. `api/deps.py`: đổi `get_db` thành `get_session` (R13), cập nhật router. `api/main.py`: bỏ `create_all` khi khởi động.
7. **Lệnh.** `Makefile`: `db-upgrade` → `uv --directory server run alembic upgrade head`; `db-seed` → `uv --directory server run postcare seed`; `seed` → `postcare seed --reset`. `scripts/dev.ps1` tương ứng. `.github/workflows/ci.yml`: service `postgres:16` cho job Ubuntu (tạo `postcare_test`); job Windows khởi động PostgreSQL có sẵn trên runner (Windows runner không hỗ trợ service container) rồi tạo user/DB.
8. **Tài liệu cùng nhánh:** README (PostgreSQL bằng Docker, `make db-upgrade`, `make db-seed`, `make seed`), `dev-setup.md` §3–4, `data-model.md` (quy ước NOT NULL, migration 0002, `last_config_hash`, enum native), `tech-stack.md` (phiên bản alembic, psycopg chính thức), `testing.md` §3 (fixture), `overview.md` (db dùng Alembic, import `schemas`), ADR-0010 (thay thế một phần: mục 1–2 bởi F01/ADR-0004), `.env.example`.
9. **Kiểm chứng:** `make check` và `scripts\dev.ps1 check` exit 0; thủ công: DB rỗng → `make db-upgrade`, `make db-seed` hai lần (đếm bản ghi bằng `psql`), `alembic downgrade base` / `upgrade head`, `make seed` rồi chạy API + `postcare simulate --bed A01` để chắc prototype còn chạy. Ghi kết quả vào mục 10.

Không cần `make gen-api-types` (không đổi endpoint; chỉ đổi tên dependency).

**Rủi ro:**
- Test API cũ dùng chung một connection qua nhiều session (savepoint): một test gọi `rollback()` giữa chừng có thể xóa dữ liệu của request trước. Kiểm chứng bằng chạy toàn bộ test cũ; test cần commit thật dùng `committed_app`.
- `alembic downgrade base` bị chặn nếu còn connection giữ transaction: test roundtrip không dùng `db_session`.
- Job Windows trên CI chưa chạy được ở máy dev; chỉ kiểm chứng khi push (coordinator).

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
