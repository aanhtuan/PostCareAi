# Tasks

Cập nhật theo [update-progress.md](../ai/workflows/update-progress.md). Thứ tự và phụ thuộc: [ROADMAP.md](ROADMAP.md).

## Prototype đề xuất (ngoài roadmap F00–F30): Done

- [x] Code base chạy được (server FastAPI + web React, SQLite, bộ giả lập `postcare simulate`), README hướng dẫn cài và chạy, [ADR-0010](../02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md). Chi tiết: entry 2026-10-12 21:30 trong [session-log.md](session-log.md).
- **Lưu ý:** prototype **chưa** đạt đủ acceptance criteria của spec, nên các feature F00–F24 vẫn **Todo** trong [ROADMAP.md](ROADMAP.md). Khi làm từng feature, dùng code prototype làm điểm xuất phát và tick AC theo spec.
- Còn thiếu so với kiến trúc đích: PostgreSQL + Alembic, import-linter, mypy, pre-commit, CI, msw, E2E, toàn bộ phần AI (camera, MediaPipe, engine, worker, MJPEG), cấu hình camera/ROI, chế độ hiển thị, CRUD danh mục trên UI.

## Đang làm

- **Review bộ tài liệu khởi tạo** (người dùng). Chưa viết code ứng dụng cho tới khi người dùng xác nhận.
  - [ ] Đọc `AGENTS.md`, `docs/01-product/PRD.md`, `docs/01-product/qa-decisions.md` (đặc biệt các mục *(giả định)*).
  - [ ] Đọc `docs/00-source/conflicts.md` (xử lý xung đột PDF ↔ HS).
  - [ ] Đọc `docs/02-architecture/` (kiến trúc, data model, API, event engine, ADR).
  - [ ] Đọc các spec `docs/03-features/F00`–`F35`.
  - [ ] Xác nhận hoặc sửa các giả định A01–A15.
  - [ ] Cho phép bắt đầu F00.

## Tiếp theo

- **F00 – Khung xương dự án** ([spec](../03-features/F00-project-skeleton.md)). Bắt đầu bằng `/plan-feature F00` hoặc [plan-feature.md](../ai/workflows/plan-feature.md).
  - Trước F00, cài trên máy dev: GNU Make, uv, Node.js LTS, PostgreSQL 16 ([dev-setup.md](../04-guides/dev-setup.md)). Máy hiện tại đã có Git, uv 0.13.0 (Python 3.12.15), Node v24.21.0; còn thiếu GNU Make (không có winget) và PostgreSQL.

## Task không phải code (song song)

| Task | Tuần | Người | Trạng thái | Nguồn |
|---|---|---|---|---|
| Chuẩn bị tripod/giá đỡ có ngàm khóa, dây chống rơi, sạc, điện thoại | 1 | — | Todo | HS §4.1 |
| Dựng giường mô phỏng | 1 | — | Todo | PDF §11; HS §7.2 |
| Buổi thử chọn vị trí camera, ghi "Chuẩn lắp đặt" ([camera-setup.md](../04-guides/camera-setup.md)) | 1–2 | — | Todo | HS §4.1 |
| Chuẩn bị phiếu đồng ý của người tham gia *(giả định)* | 2 | — | Todo | HS §6.3, §7.2 |
| Quay **tập dev** S01–S16 (≥3 lượt / kịch bản) + gán ground truth ([evaluation.md](../04-guides/evaluation.md)) | 3 | — | Todo | HS §8.1 |
| Quay **tập test** (người/phiên khác), chỉ sau khi chốt ngưỡng | 8–9 | — | Todo | HS §8.1–8.2 |
| Quay video dự phòng cho demo | 9 | — | Todo | HS §8.3 |
| Lấy tài liệu yêu cầu Đồ án Chuyên ngành 2 [8] (nếu cần nộp đồ án) | — | — | Todo | PDF TLTK [8]; QA#1 |

## Backlog / đề xuất chưa xếp lịch

- (trống) Ghi ở đây các ý tưởng ngoài spec phát sinh trong lúc làm. Không tự triển khai.

## Đã xong gần đây

- [x] 2026-11-16: Chuẩn bị xuất bản GitHub; cài lại phụ thuộc frontend cho Linux, `make check` đạt (40 backend + 25 frontend test, build đạt). SUMMARY.md đã cập nhật; đã push prototype lên origin/main qua SSH (commit đầu tiên e59d28f).
- [x] 2026-11-16: Lưu bản tổng kết hiện trạng và kết quả kiểm tra vào [SUMMARY.md](../../SUMMARY.md).
- [x] 2026-11-16: Kiểm kê code và kiểm tra hiện trạng: backend 40 test đạt; TypeScript/ESLint đạt; `make check` chưa xanh do phụ thuộc frontend trên Linux và format hai file sinh tự động. Xem entry mới nhất trong [session-log.md](session-log.md).
- Bộ tài liệu khởi tạo: chuyển PDF sang Markdown, tài liệu lõi, adapter, spec F00–F35, roadmap (xem [session-log.md](session-log.md)).
