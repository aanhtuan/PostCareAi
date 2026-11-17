# Tasks

Cập nhật theo [update-progress.md](../ai/workflows/update-progress.md). Thứ tự và phụ thuộc: [ROADMAP.md](ROADMAP.md).

## Prototype đề xuất (ngoài roadmap F00–F30): Done

- [x] Code base chạy được (server FastAPI + web React, SQLite, bộ giả lập `postcare simulate`), README hướng dẫn cài và chạy, [ADR-0010](../02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md). Chi tiết: entry 2026-10-12 21:30 trong [session-log.md](session-log.md).
- **Lưu ý:** prototype **chưa** đạt đủ acceptance criteria của spec, nên các feature F00–F24 vẫn **Todo** trong [ROADMAP.md](ROADMAP.md). Khi làm từng feature, dùng code prototype làm điểm xuất phát và tick AC theo spec.
- Còn thiếu so với kiến trúc đích: PostgreSQL + Alembic, import-linter, mypy, pre-commit, CI, msw, E2E, toàn bộ phần AI (camera, MediaPipe, engine, worker, MJPEG), cấu hình camera/ROI, chế độ hiển thị, CRUD danh mục trên UI.

## Đang làm

- **Tiếp theo trong lúc này:** F01 (B), F05 và F10 (A) theo vòng đời planner → test-writer → implementer → code-reviewer → merge.
- **Lưu ý cho F16:** nhãn trên dữ liệu ngoài chỉ phủ một số mã sự kiện mỗi video (cột notes); F16 phải bỏ qua mã không được gán nhãn khi tính FP *(giả định, datasets.md)*. Script dựng manifest/truth chưa nằm trong repo; quy tắc dựng ghi ở datasets.md §3.5, cần đưa thành lệnh trong F16.

## Tiếp theo

- Máy dev (17/11/2026): Git, uv 0.13.9 (Python 3.12.16), Node 24, GNU Make 4.4.1 và gh 2.104.0 (cài bản zip có kiểm tra checksum), Docker Desktop. PostgreSQL chạy bằng Docker (QA#34). GPU GTX 1650 Ti 4 GB (chỉ dùng nếu benchmark CPU không đạt, QA#35).
- Sau F00, chạy song song theo nhánh: F01 (B), F05 và F10 (A).

## Task không phải code (song song)

| Task | Tuần | Người | Trạng thái | Nguồn |
|---|---|---|---|---|
| Chuẩn bị tripod/giá đỡ có ngàm khóa, dây chống rơi, sạc, điện thoại | 1 | — | Todo | HS §4.1 |
| Dựng giường mô phỏng | 1 | — | Todo | PDF §11; HS §7.2 |
| Buổi thử chọn vị trí camera, ghi "Chuẩn lắp đặt" ([camera-setup.md](../04-guides/camera-setup.md)) | 1–2 | — | Todo | HS §4.1 |
| Chuẩn bị phiếu đồng ý của người tham gia *(giả định)* | 2 | — | Todo | HS §6.3, §7.2 |
| Quay **tập dev** S01–S16 (≥3 lượt / kịch bản) + gán ground truth ([evaluation.md](../04-guides/evaluation.md)). Trước mắt dùng dữ liệu ngoài ([datasets.md](../04-guides/datasets.md), QA#33) | 3 | — | Todo | HS §8.1 |
| Liên hệ lab MICA (Hà Nội) xin quyền dùng CMDFall nếu cần thêm dữ liệu | — | — | Todo | QA#33 |
| Quay **tập test** (người/phiên khác), chỉ sau khi chốt ngưỡng | 8–9 | — | Todo | HS §8.1–8.2 |
| Quay video dự phòng cho demo | 9 | — | Todo | HS §8.3 |
| Lấy tài liệu yêu cầu Đồ án Chuyên ngành 2 [8] (nếu cần nộp đồ án) | — | — | Todo | PDF TLTK [8]; QA#1 |

## Backlog / đề xuất chưa xếp lịch

- Ghi ở đây các ý tưởng ngoài spec phát sinh trong lúc làm. Không tự triển khai.
- Dùng skill tra cứu PubMed (ví dụ `pubmed-database`) để đối chiếu PMID khi làm slide. Công cụ của nhóm, không phải chức năng sản phẩm (đề xuất nhóm 17/11/2026).
- `npm audit` báo 8 lỗ hổng (7 moderate, 1 high) trong devDependency của web (17/11/2026). Xem từng gói, nâng phiên bản nếu không phá build; ghi kết quả vào session-log.

## Đã xong gần đây

- [x] 2026-11-17: **F00 Done.** Mypy, import-linter (8 contract), pre-commit/pre-push, CI GitHub Actions (Ubuntu + Windows, run 44107632897 xanh), `config/engine.default.yaml`, msw, `postcare version`/`openapi --check`. Chi tiết: spec F00 mục 10.
- [x] 2026-11-17: Hợp nhất đề xuất nhóm vào tài liệu (QA#31–QA#37, F35–F37, pitch, DEMO-PLAN, datasets); dữ liệu ngoài 2,5 GB trong `data/external/`.

- [x] 2026-11-16: Chuẩn bị xuất bản GitHub; cài lại phụ thuộc frontend cho Linux, `make check` đạt (40 backend + 25 frontend test, build đạt). SUMMARY.md đã cập nhật; đã push prototype lên origin/main qua SSH (commit đầu tiên e59d28f).
- [x] 2026-11-16: Lưu bản tổng kết hiện trạng và kết quả kiểm tra vào `SUMMARY.md`. Ngày 17/11/2026 nội dung đã gộp vào README ("Trạng thái hiện tại") và session-log, file đã xóa.
- [x] 2026-11-16: Kiểm kê code và kiểm tra hiện trạng: backend 40 test đạt; TypeScript/ESLint đạt; `make check` chưa xanh do phụ thuộc frontend trên Linux và format hai file sinh tự động. Xem entry mới nhất trong [session-log.md](session-log.md).
- Bộ tài liệu khởi tạo: chuyển PDF sang Markdown, tài liệu lõi, adapter, spec F00–F35, roadmap (xem [session-log.md](session-log.md)).
