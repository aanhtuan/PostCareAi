# Tasks

Cập nhật theo [update-progress.md](../ai/workflows/update-progress.md). Thứ tự và phụ thuộc: [ROADMAP.md](ROADMAP.md).

## Prototype đề xuất (ngoài roadmap F00–F30): Done

- [x] Code base chạy được (server FastAPI + web React, SQLite, bộ giả lập `postcare simulate`), README hướng dẫn cài và chạy, [ADR-0010](../02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md). Chi tiết: entry 2026-10-12 21:30 trong [session-log.md](session-log.md).
- **Lưu ý:** prototype **chưa** đạt đủ acceptance criteria của spec, nên các feature F00–F24 vẫn **Todo** trong [ROADMAP.md](ROADMAP.md). Khi làm từng feature, dùng code prototype làm điểm xuất phát và tick AC theo spec.
- Còn thiếu so với kiến trúc đích: PostgreSQL + Alembic, import-linter, mypy, pre-commit, CI, msw, E2E, toàn bộ phần AI (camera, MediaPipe, engine, worker, MJPEG), cấu hình camera/ROI, chế độ hiển thị, CRUD danh mục trên UI.

## Đang làm

**Trạng thái bàn giao (cập nhật 20/11/2026, sau khi gộp commit F07 từ máy khác).** `main` = 32 feature Done (F00–F23, F25–F28, F31, F35, F37) + hiệu chỉnh ngưỡng dev. Mọi nhánh dưới đây đã push lên GitHub.

| Feature | Nhánh | Trạng thái | Việc còn lại |
|---|---|---|---|
| F24 Bàn giao ca | `feat/F24-handover` | Code xong, review Đạt (đã sửa, có bằng chứng in bằng Playwright), spec Done | Merge vào `main` → `make check` → push; đánh dấu Done ở ROADMAP/README |
| F29 Đánh giá chính thức | `feat/F29-final-eval` | Đã có `--frozen`, `measure-delivery`, `workflow-report`, báo cáo nháp; commit cuối là WIP | Chạy eval tập **test** với cấu hình đã chốt, hoàn thiện `docs/04-guides/final-evaluation-2026-11-18.md`, `make check`, review |
| F36 Quyền xem của người nhà | `feat/F36-family-access` | Plan + test (đỏ) + phần code đang viết dở (migration `0007_f36_family_access_grants`, domain, API, WS family stream); commit cuối là WIP, **chưa chạy test** | Làm cho test xanh, UI staff cấp/thu hồi + trang `/family`, kiểm tay, review |
| F07 mở rộng (từ máy khác, 19/11) | đã merge vào `main` (`ebf4866`) | Live view hai khung: trái theo chế độ riêng tư, phải skeleton + ROI; [báo cáo webcam A01](../../reports/REALTIME-WEBCAM-VERIFICATION-2026-11-19.md) | Webcam thật: mép giường → cảnh báo → tiếp nhận đã chạy; **rời giường BLOCKED do góc quay** — chỉnh webcam thấy trọn giường + toàn thân, vẽ lại ROI, chạy lại kịch bản |
| F30 Sẵn sàng demo | `main` (một phần) | Đã có `--loop` cho worker phát file (20/11) | Phụ thuộc F24, F31, F36: runbook, `make demo-seed`, E2E Playwright, chạy trọn 3 lần |

**Tiếp tục trên máy khác (Windows):**

```bash
git clone https://github.com/aanhtuan/PostCareAi.git && cd PostCareAi
cp .env.example .env                      # API từ chối secret mặc định change-me
docker run -d --name postcare-db -e POSTGRES_USER=postcare -e POSTGRES_PASSWORD=postcare -e POSTGRES_DB=postcare -p 5432:5432 -v postcare-pgdata:/var/lib/postgresql/data postgres:16
docker exec postcare-db createdb -U postcare postcare_test
make setup && make db-upgrade && make seed && make models && make check
```

- Công cụ: Git, uv, Node 24, GNU Make, Docker, gh ([dev-setup.md](../04-guides/dev-setup.md)). Máy cũ không có winget nên make/gh cài bằng zip có kiểm tra checksum.
- Dữ liệu `data/` (~2,5 GB, gitignore) không có trong repo: tải lại theo [datasets.md](../04-guides/datasets.md); `data/eval/manifest.csv` + `truth.csv` cần dựng lại theo §3.5 (gồm cột `camera_config`). Model: `make models`.
- Tiếp nhánh dở: `git fetch && git switch feat/F36-family-access` (tương tự F29, F24). Nhánh WIP chưa qua review.

**Demo đã chạy được (cách dựng lại):** DB riêng `postcare_demo` (`docker exec postcare-db createdb -U postcare postcare_demo`, rồi `DATABASE_URL=…/postcare_demo` + `alembic upgrade head` + `postcare seed --reset`), API `uvicorn … --port 8090`, web `VITE_API_TARGET=http://127.0.0.1:8090 npm --prefix web run dev -- --port 5190`, đặt ROI camera 1/2 bằng `PUT /api/v1/cameras/{id}/roi` từ `config/cameras/pexels-3753707.yaml` và `gmdcsa24-room.yaml`, rồi `postcare workers --camera 1 --camera 2 --video 1=<clip A01> --video 2=<clip A02> --api http://127.0.0.1:8090`. Từ 20/11 dùng `--loop` (`make worker CAMERA=1 VIDEO=<clip> LOOP=1`) thay cho clip ghép lặp.

**Quy trình và hạ tầng đã dùng:** builder trong worktree → code-reviewer → sửa → merge vào `main` → `make check` → push (người dùng cho phép push nhánh feature và `main`, không force-push). Mỗi worktree dùng DB test riêng (`postcare_<x>_test`), `main` dùng `postcare_main_test`. Máy 16 GB: tối đa 2 `make check` cùng lúc; vitest giới hạn `maxWorkers: 2`; Docker từng treo khi thiếu RAM (khởi động lại Docker Desktop + `wsl --shutdown`).

- **Lưu ý cho F16/F29:** nhãn trên dữ liệu ngoài chỉ phủ một số mã sự kiện mỗi video (cột notes, `eval_codes`); mã không gán nhãn không tính FP *(giả định, datasets.md)*.
- **Giới hạn đã biết:** không có video công khai quay rời giường bằng camera cố định (BED_EXIT chưa bắt được trên clip stock; cần nhóm tự quay S01–S16). MediaPipe mất dấu người nằm sàn ở 38/71 ca ngã dev. Điện thoại thật (DroidCam/IP Webcam) chưa thử. S02, S07, S12, S14, S16 chưa có dữ liệu.

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

- [x] 2026-11-20: F07 thêm nút “Kết nối camera” trên Theo dõi trực tiếp cho quản trị viên và hướng dẫn iPhone qua Wi-Fi/USB. Kiểm chứng iPhone thật còn chờ thiết bị.

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
