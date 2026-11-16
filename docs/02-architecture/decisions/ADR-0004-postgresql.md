# ADR-0004: PostgreSQL là cơ sở dữ liệu

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** PDF §10, bảng tr.10; HS §6.1

## Bối cảnh

Dữ liệu có cấu trúc và nhiều quan hệ: bệnh nhân, giường, camera, phiên, sự kiện, cảnh báo, người dùng, audit (PDF §10). Cả hai nguồn đều chọn PostgreSQL.

## Quyết định

- Dùng **PostgreSQL 16**, truy cập qua SQLAlchemy 2.0 + psycopg 3; migration bằng Alembic.
- Dùng các tính năng: `jsonb` (ROI, ngưỡng, explanation), partial unique index (1 phiên mở / giường), `timestamptz`, enum.
- Test chạy trên DB riêng `postcare_test`; CI dùng service container Postgres.
- Trên Windows cài PostgreSQL native. Docker là tùy chọn trên Linux.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **PostgreSQL** | Nguồn chọn, mạnh, JSONB, partial index | Phải cài server |
| SQLite | Không cần cài | Thiếu partial unique index theo cách tương đương và JSONB; khác môi trường so với nguồn |

## Hệ quả

- `dev-setup.md` phải hướng dẫn cài PostgreSQL trên Windows và Linux.
- Test DB cần dọn dẹp mỗi test bằng transaction rollback.
