# Tasks

Cập nhật theo [update-progress.md](../ai/workflows/update-progress.md). Thứ tự và phụ thuộc: [ROADMAP.md](ROADMAP.md).

## Prototype đề xuất (ngoài roadmap F00–F30): Done

- [x] Code base chạy được (server FastAPI + web React, SQLite, bộ giả lập `postcare simulate`), README hướng dẫn cài và chạy, [ADR-0010](../02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md). Chi tiết: entry 2026-10-12 21:30 trong [session-log.md](session-log.md).
- **Lưu ý:** prototype **chưa** đạt đủ acceptance criteria của spec, nên các feature F00–F24 vẫn **Todo** trong [ROADMAP.md](ROADMAP.md). Khi làm từng feature, dùng code prototype làm điểm xuất phát và tick AC theo spec.
- Còn thiếu so với kiến trúc đích: PostgreSQL + Alembic, import-linter, mypy, pre-commit, CI, msw, E2E, toàn bộ phần AI (camera, MediaPipe, engine, worker, MJPEG), cấu hình camera/ROI, chế độ hiển thị, CRUD danh mục trên UI.

## Đang làm


- **Đợt hiện tại (18/11/2026):** Done 21 feature: F00–F07, F09–F17, F23, F25, F35, F37, cộng hiệu chỉnh ngưỡng trên tập dev ([calibration-2026-11-18.md](../04-guides/calibration-2026-11-18.md), config_hash chốt cho F29 `cb7a5ed7…44ec`). Đang làm: F08 (cấu hình camera, ROI), F18 (realtime gateway). Tiếp theo: F19 → F20, F21, F22, F24; F26 → F27; F28 → F36; F31 R1–R3; F29; F30.
  - Quy trình: builder trong worktree → code-reviewer → sửa → merge vào `main` → `make check` → push (người dùng cho phép push nhánh feature và `main`).
  - Hạ tầng: mỗi worktree dùng DB test riêng (`postcare_<x>_test`), `main` dùng `postcare_main_test`. Máy 16 GB: chạy tối đa 2 `make check` cùng lúc; Docker từng treo khi quá tải (khởi động lại Docker Desktop + `wsl --shutdown`).
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

- [x] 2026-11-19: Rà soát phạm vi xuất bản code/hướng dẫn demo video, fetch xác nhận base main ebf4866; giữ media/model/DB/.env/runs ngoài Git. Commit/push/merge đang thực hiện; trạng thái remote cần đối chiếu khi kết thúc.

- **2026-11-19 — Lát cắt F30 video demo — hoàn tất local (yêu cầu người dùng, trước F24; không hoàn thành toàn F30):**
  - [x] Ghi scope/kế hoạch; nguồn Pexels 8090735 + ROI sẵn có, không thay webcam A01.
  - [x] API opt-in/ADMIN, worker file thật, EOF marker, stop, phiên độc lập, audit và recovery.
  - [x] Trang Demo video: hai khung, điều khiển, cảnh báo mở và lịch sử từng lượt; API types/runbook.
  - [x] Kiểm chứng clip thật BED_EDGE → NURSE tiếp nhận/kết quả/xử lý → timeline; replay và stop.
  - [x] Make check PASS (1375 pytest, 258 Vitest, build); test-vision 5 passed/1 skipped; tự review và [báo cáo bàn giao](../../reports/VIDEO-DEMO-VERIFICATION-2026-11-19.md).


- [x] 2026-11-19: Rà soát video Live View người dùng gửi, ghi bằng chứng và 5 nhóm cập nhật đề xuất tại [báo cáo review](../../reports/LIVE-VIEW-REVIEW-2026-11-19.md). Chưa triển khai các đề xuất; chưa nghiệm thu BED_EXIT.

- [x] 2026-11-19 16:42: Khởi động lại clone fresh trên main ebf4866: DB/API 8002/web 5175/worker webcam A01 hoạt động; health/auth/overview HTTP 200, camera ONLINE và cả hai MJPEG có khung mới. Giữ ROI/phiên/chế độ hiện tại, không reset dữ liệu.

- [x] 2026-11-19: Rà soát và chuẩn bị xuất bản code F07 hai khung cùng test/API types/spec; hợp nhất báo cáo hiện có, giữ dữ liệu/cấu hình local ngoài Git. Push nhánh feature và main cùng một lượt, không bỏ hook.

- [x] 2026-11-19: Viết [báo cáo nghiệm thu webcam A01](../../reports/REALTIME-WEBCAM-VERIFICATION-2026-11-19.md): ROI, phiên demo, mép giường → cảnh báo → ADMIN tiếp nhận/xác nhận → timeline. Rời giường còn BLOCKED do góc webcam. Báo cáo đã có trên main; lần xuất bản tiếp theo bổ sung code hai khung theo yêu cầu người dùng.

- [x] 2026-11-19: Mở rộng Theo dõi trực tiếp theo yêu cầu người dùng: khung trái giữ chế độ riêng tư hiện tại, khung phải skeleton + vùng giường từ cùng observation; tách bộ đệm/luồng MJPEG, giữ quyền và stale policy, hỗ trợ pose preview khi chưa có ROI nhưng không phát state/event. Test worker/API/UI, `make check` (1364 pytest, 254 Vitest, build) và browser hai stream đều đạt.

- [x] 2026-11-19 00:31: Minh họa clip stock Pexels 8090735 → MediaPipe → skeleton/ROI và engine thật; 115 khung, 1 sự kiện ở mép giường, chưa có rời giường. Mở http://127.0.0.1:5180/ để xem video gốc cạnh skeleton. `make test-vision`: 5 passed, 1 skipped; không thay webcam A01 hoặc source ứng dụng. Chi tiết trong session-log.

- [x] 2026-11-19: Cài và chạy clone Linux mới `/home/atuna/Downloads/PostCareAI-fresh`: dependency/hook, PostgreSQL 16 riêng (`postcare-fresh-db`, cổng 55433), migration 0006, seed nền, 4 model khớp SHA256; API 8002, web 5175, đăng nhập UI nurse và WebSocket thành công. `make test-vision`: 2 passed, 4 skipped (thiếu video); `make check` PASS: 1360 pytest + 253 Vitest + build; webcam USB index 0 và worker đã chạy, /live nhận MJPEG 640x480, còn cần ROI/phiên để phát hiện sự kiện. Hướng dẫn local (không commit): `reports/LOCAL-SETUP.local.md`. Webcam thật đã hoạt động; chưa nghiệm thu hành vi quanh giường.

- [x] 2026-11-17: **F00 Done.** Mypy, import-linter (8 contract), pre-commit/pre-push, CI GitHub Actions (Ubuntu + Windows, run 44107632897 xanh), `config/engine.default.yaml`, msw, `postcare version`/`openapi --check`. Chi tiết: spec F00 mục 10.
- [x] 2026-11-17: Hợp nhất đề xuất nhóm vào tài liệu (QA#31–QA#37, F35–F37, pitch, DEMO-PLAN, datasets); dữ liệu ngoài 2,5 GB trong `data/external/`.

- [x] 2026-11-16: Chuẩn bị xuất bản GitHub; cài lại phụ thuộc frontend cho Linux, `make check` đạt (40 backend + 25 frontend test, build đạt). SUMMARY.md đã cập nhật; đã push prototype lên origin/main qua SSH (commit đầu tiên e59d28f).
- [x] 2026-11-16: Lưu bản tổng kết hiện trạng và kết quả kiểm tra vào `SUMMARY.md`. Ngày 17/11/2026 nội dung đã gộp vào README ("Trạng thái hiện tại") và session-log, file đã xóa.
- [x] 2026-11-16: Kiểm kê code và kiểm tra hiện trạng: backend 40 test đạt; TypeScript/ESLint đạt; `make check` chưa xanh do phụ thuộc frontend trên Linux và format hai file sinh tự động. Xem entry mới nhất trong [session-log.md](session-log.md).
- Bộ tài liệu khởi tạo: chuyển PDF sang Markdown, tài liệu lõi, adapter, spec F00–F35, roadmap (xem [session-log.md](session-log.md)).
