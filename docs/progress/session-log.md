# Nhật ký phiên làm việc

Entry mới nhất ở trên cùng. Mẫu và quy tắc: [update-progress.md](../ai/workflows/update-progress.md). Không xóa entry cũ.

## 2026-11-21 – Codex – Triển khai trạng thái và nhật ký trên Live View

- **Đã làm:** Đưa trạng thái và lý do lên cạnh hai khung, thu gọn tín hiệu phụ, thêm cột nhật ký gần đây cuộn riêng. Sự kiện mở tóm tắt tại chỗ; cảnh báo mở chi tiết theo ID từ nhật ký hoặc toast. Giữ quyền hiện có và dữ liệu vận hành theo QA#29.
- **Kiểm tra:** `make check` xanh trên PostgreSQL test riêng (1368 test Python, 265 test web và build), kiểm tra tĩnh lặp sau chỉnh màu đạt. Playwright ở 1280×720, 1366×768 và 390 px với dữ liệu giả lập kiểm tra hai video, cuộn nhật ký, đổi giường, mở sự kiện và cảnh báo đúng ID. Vite cục bộ đang phục vụ giao diện mới.
- **Đang dở / blocker:** Chưa phát và xử lý cảnh báo mới bằng camera thật trong phiên này.
- **Bước tiếp theo:** Tải lại `/beds/1/live` để xem trạng thái và nhật ký A01. Dùng **Lịch sử theo dõi** để xem thêm bản ghi.


## 2026-11-20 – Codex – Triển khai lối vào vùng giường và mở rộng hai khung live

- **Đã làm:** Đặt **Vẽ vùng giường** nổi bật trên Theo dõi trực tiếp cho quản trị viên; thêm **Sửa vùng giường** khi đã lưu. Dùng lại trình vẽ F08 và quay về đúng giường. Đưa chi tiết trạng thái xuống dưới để hai khung dùng toàn chiều rộng vùng nội dung.
- **Kiểm tra:** `make check` xanh trên PostgreSQL test riêng (1368 test Python, 261 test web, build đạt). Playwright với camera giả lập đã vẽ và lưu bốn góc, quay lại đúng giường, kiểm tra overlay khi resize. Hai khung đạt 491 px ở 1280×720 và 534 px ở 1366×768, xếp dọc ở viewport 640 px và 390 px. Vite cục bộ đã phục vụ bản Live View mới.
- **Đang dở / blocker:** Còn kiểm tra vùng trên khung iPhone thật theo vị trí mặt nệm của người dùng.
- **Bước tiếp theo:** Trên trang A01 khi `make worker CAMERA=1` đang chạy, bấm **Vẽ vùng giường**, đánh dấu mặt nệm, lưu và quay lại kiểm tra đường viền.


## 2026-11-20 – Codex – F07 kết nối camera từ Theo dõi trực tiếp

- **Đã làm:** Trên `feat/F07-camera-connect`, thêm nút “Kết nối camera” cho quản trị viên. Form F03 dùng lại cho đúng giường và giữ ràng buộc phiên đang mở. Worker báo phiên bản nguồn trên JPEG; live view đợi cả hai khung mới và hướng dẫn khởi động worker khi thiếu heartbeat. Clip ghi đè bằng `--video` tiếp tục phát được.
- **Kiểm tra:** `make check` xanh (1368 pytest, 257 Vitest, web build). Playwright trên bản build kiểm tra luồng URL RTSP và Webcam với API giả lập. Dùng PostgreSQL test riêng `postcare_camera_connect_test` vì DB test mặc định chưa tồn tại.
- **Đang dở / blocker:** Chưa thử iPhone thật qua Wi-Fi hoặc cáp USB.
- **Bước tiếp theo:** Khởi động API/web bằng `make dev`, thiết lập nguồn iPhone theo [hướng dẫn Fedora](../04-guides/dev-setup.md#5-dùng-điện-thoại-làm-camera), bấm **Lưu và kết nối** và chạy `make worker CAMERA=1` cho camera seed A01. Kiểm tra lại vùng giường nếu đổi góc.


## 2026-11-19 – Codex – Xuất bản code live view hai khung

- **Phạm vi:** Người dùng yêu cầu push code và merge vào main, không đưa dữ liệu local lên GitHub. Chỉ thao tác clone PostCareAI-fresh và worktree tạm của clone này.
- **Đã làm:** Rà soát diff F07: worker render display/skeleton từ cùng observation, hai bộ đệm và MJPEG riêng, UI giữ chế độ riêng tư bên trái; kèm test, API types và spec. Hợp nhất báo cáo đã xuất bản trên main, giữ cả hai nhật ký; không thay DB, cấu hình máy, video hoặc model.
- **Review:** Không phát hiện blocker trong diff phạm vi F07; không đổi rule engine hoặc suy diễn mất landmark thành rời giường. Bằng chứng hai stream thực tế và make check trước đó nằm trong entry mở rộng F07; bộ kiểm tra cuối do hook pre-push chạy.
- **Kiểm tra xuất bản:** Dừng lượt push cũ trước khi chạy lượt kiểm tra cuối, tránh hai bộ test dùng chung DB. make check phải PASS trước khi Git cập nhật remote; không bỏ hook. make test-vision: 5 passed, 1 skipped (thiếu clip cận mặt), 1364 deselected, 7.89 s. Hash và kết quả make check được xác nhận trong bàn giao cuối.
- **Bước tiếp theo:** Push feat/F07-dual-live-view và main cùng một lượt atomic; kiểm tra hai hash remote trùng bản merge. Trước lần chỉnh code tiếp theo chạy git fetch origin và kiểm tra trạng thái nhánh.
- **Blocker nghiệp vụ:** BED_EXIT vẫn chưa nghiệm thu do góc quay, cần người dùng chỉnh webcam và chạy lại kịch bản. Không coi việc push code là nghiệm thu camera.

## 2026-11-19 – Codex – Chuẩn bị xuất bản báo cáo webcam

- **Phạm vi:** Theo yêu cầu người dùng chỉ đưa báo cáo và tiến độ liên quan lên GitHub; tách khỏi các commit code live view hai khung.
- **Đã làm:** Tạo nhánh `codex/webcam-session-report` từ `origin/main`; bổ sung báo cáo nghiệm thu, entry webcam và task tài liệu. Code trong `feat/F07-dual-live-view` được giữ local.
- **Kiểm tra:** Rà soát diff chỉ chứa Markdown; hook pre-push bắt buộc chạy `make check`. Các lượt test trước có deadlock do chạy đồng thời trên một DB test; chạy duy nhất một lượt khi xuất bản.
- **Bước tiếp theo:** Push nhánh báo cáo và hợp nhất vào `main` theo yêu cầu người dùng; xác nhận hash remote. Vẫn cần chỉnh góc webcam và nghiệm thu `BED_EXIT`.
- **Blocker:** Chưa đủ góc quay để nghiệm thu rời giường; báo cáo ghi rõ BLOCKED.

## 2026-11-19 01:35 – Codex – Nghiệm thu realtime webcam A01

- **Mục tiêu phiên:** Cấu hình webcam thật, mở phiên theo dõi và kiểm tra chuỗi sự kiện → cảnh báo → điều dưỡng xử lý → timeline trong clone mới.
- **Đã làm:** Đăng nhập ADMIN trên `http://127.0.0.1:5175`, vẽ và lưu Bed ROI 5 điểm cho Camera A01; tạo bệnh nhân thử nghiệm `BN-DEMO-A01`; mở phiên theo dõi A01 lúc 01:29:53. Giữ chế độ riêng tư làm mờ khuôn mặt ở khung trái và skeleton + ROI ở khung phải.
- **Kết quả kiểm tra:** Webcam online, pose thật cập nhật realtime. Engine phát sự kiện `Bệnh nhân đang ở mép giường` lúc 01:30:33 với chất lượng quan sát tốt; người dùng `Phạm Thu Hà` (tài khoản ADMIN) tiếp nhận cảnh báo, ghi `Xác nhận đúng`, thêm ghi chú kiểm tra và đánh dấu đã xử lý. Timeline hiển thị sự kiện, trạng thái đã xử lý và kết quả xác nhận. Trạng thái `BED_EXIT` chưa đạt: góc webcam chưa bắt đủ toàn thân/chân, sau khi người ra ngoài chỉ chuyển sang `Không đủ dữ liệu quan sát`, không phát cảnh báo rời giường.
- **Đang dở:** Cần lùi hoặc hạ webcam để thấy trọn giường và toàn thân; sau đó vẽ lại ROI và lặp lại kịch bản nằm → ngồi → mép → đứng → rời vùng giường. Không đánh dấu nghiệm thu BED_EXIT.
- **Bước tiếp theo:** Chỉnh vị trí webcam, mở lại `/cameras/1/config`, vẽ ROI theo khung mới; chạy lại và kiểm tra cảnh báo ưu tiên cao, rồi cập nhật timeline/runbook.
- **Blocker / câu hỏi cho người dùng:** Thiếu góc quay đủ rộng để xác nhận an toàn chuỗi rời giường; cần người dùng chỉnh vật lý webcam.
- **Giả định mới:** Không có.

## 2026-11-19 – Codex – Mở rộng live view hai khung theo yêu cầu người dùng

- **Mục tiêu phiên:** Đưa kiểu demo video cạnh skeleton vào sản phẩm; người dùng xác nhận giữ chế độ riêng tư đã chọn ở trái và thêm skeleton ở phải.
- **Đã làm:** Nhánh `feat/F07-dual-live-view`. Worker vẫn render `display_mode` hiện tại, đồng thời render JPEG skeleton nền trơn + ROI từ cùng observation; API lưu hai view trong RAM (`display`, `skeleton`) và phát MJPEG theo `view`, cùng auth/stale/revalidation. Khi chưa có ROI, worker vẫn chạy pose cho khung skeleton nhưng không tạo engine/state/event. Live View responsive hai khung, nhãn tiếng Việt và hướng dẫn riêng tư; không thêm thư viện, không migration, không đổi DB.
- **Kết quả kiểm tra:** Test mục tiêu backend worker/API đạt; 18 test UI LiveView/CameraStream đạt. `make check` PASS lần chạy thứ hai: 1364 pytest passed, 254 Vitest passed, build web đạt; lần chạy đầu có một lỗi stale-frame đơn lẻ nhưng test chạy riêng đạt.
- **Đang dở:** Không còn phần code; dịch vụ API/worker/web đã restart trong clone mới và browser đã xác nhận hai ảnh thật. Không đổi webcam sang RAW.
- **Bước tiếp theo:** `make check`; sau đó restart `uv ... --port 8002`, Vite 5175 và worker camera 1; mở `http://127.0.0.1:5175/live`.
- **Blocker / câu hỏi cho người dùng:** Không có. ROI thật của webcam chưa cấu hình nên skeleton có thể chỉ là nền + pose, và engine vẫn báo chưa đủ dữ liệu.
- **Giả định mới:** Mở rộng này là yêu cầu người dùng, ghi tại F07 §12; hai luồng không cam kết đồng bộ pixel từng thời điểm trên trình duyệt.

## 2026-11-19 00:31 – Codex – Minh họa skeleton bằng clip stock

- **Mục tiêu phiên:** Người dùng chưa có góc quay đủ giường, yêu cầu dùng một video/ảnh bất kỳ để xem hệ thống hoạt động.
- **Đã làm:** Tải đúng clip Pexels 8090735 của PNW Production đã liệt kê trong datasets.md (Pexels License) vào data/external/pexels; ghi nguồn/giấy phép/ngày vào data/external/SOURCES.md. Chạy pipeline thật `postcare replay --video <clip> --camera-config config/cameras/pexels-8090735.yaml --out runs/stock-skeleton-demo-20261119 --preview --display-mode SKELETON`. Ghép clip gốc cạnh skeleton thành comparison.mp4, tạo trang minh họa local có nhãn “Stock footage – diễn viên”, trạng thái và sự kiện đồng bộ thời gian. Không sửa app hoặc đặt RAW cho webcam A01.
- **Kết quả kiểm tra:** Replay PASS: 115 khung/7,674 giây, 1 BED_EDGE (ở mép giường), occurred 1,835 s và detected 3,337 s; không có BED_EXIT. Face errors 0. ROI dùng cấu hình clip có sẵn, được ghi nhãn ước lượng trong YAML; không suy ra độ chính xác chung. Browser http://127.0.0.1:5180/ phát comparison.mp4 không lỗi, 1280x360, readyState 4; hiển thị sự kiện ở mép giường. Ảnh chứng minh /tmp/postcare-stock-demo-page.png. `make test-vision`: 5 passed, 1 skipped (thiếu clip cận mặt), 1360 deselected, 8.57 s. Không chạy lại make check vì không đổi code/dependency; make check gần nhất cùng chat PASS 1360 pytest + 253 Vitest + build.
- **Đang dở:** Không còn phần minh họa video được yêu cầu. Clip chưa chứng minh pipeline camera realtime hoặc phát hiện rời giường. Demo dùng replay, không gửi sự kiện vào DB vận hành.
- **Bước tiếp theo:** Mở http://127.0.0.1:5180/, bấm “Xem lại từ đầu”; video gốc ở trái, skeleton + ROI ở phải. Kết quả tại runs/stock-skeleton-demo-20261119/{comparison.mp4,events.jsonl,frames.jsonl,run.json}; khởi động lại trang bằng `python3 -m http.server 5180 --bind 127.0.0.1 --directory runs/stock-skeleton-demo-20261119` từ clone mới. HTTP server exec session 67286 chỉ có ý nghĩa trong chat này; giữ tab demo cho người dùng.
- **Blocker / câu hỏi cho người dùng:** Không cho video minh họa. Camera thật vẫn cần ROI/phiên đúng thực tế.
- **Giả định mới:** Không có yêu cầu sản phẩm mới. Trang trong runs là công cụ minh họa local, video và metadata không commit.

## 2026-11-19 00:09 – Codex – Cài và chạy clone mới trên Linux

- **Mục tiêu phiên:** Cài dependency, DB và chạy dự án đầy đủ từ clone mới theo yêu cầu; không thao tác bản cũ.
- **Đã làm:** `make setup` PASS (uv/npm/hook); tạo `.env` và `.env.postgres` riêng, secret ngẫu nhiên, quyền 600, gitignore. Kiểm kê Docker/cổng trước thao tác; tạo container PostgreSQL 16 `postcare-fresh-db`, volume `postcare-fresh-pgdata`, bind 127.0.0.1:55433, restart unless-stopped; DB `postcare_fresh` và `postcare_fresh_test` riêng. Migration tới 0006 và `make db-seed` thành công: 4 user, 3 ca, 1 khu vực, 3 giường, 1 camera. Chưa có bệnh nhân/phiên/sự kiện; không reset hoặc chạy simulator. Tải đủ 4 model MediaPipe theo manifest, SHA256 khớp.
- **Kết quả kiểm tra:** API 127.0.0.1:8002 và web 127.0.0.1:5175 chạy (cổng mặc định đã có ứng dụng khác). Health trực tiếp/proxy, HTML, login admin và GET auth/me/overview/beds/cameras HTTP 200. Browser đăng nhập nurse thành công, dashboard 3 giường, “ĐANG CẬP NHẬT TRỰC TIẾP”; ảnh `/tmp/postcare-fresh-dashboard.png`. OpenCV/MediaPipe import và model face khởi tạo PASS. `make test-vision`: 2 passed, 4 skipped vì thiếu video. `make check` PASS (exit 0): format/lint/mypy/tsc, 10 import contract, schema/type API; 1360 pytest passed (779.28 s), 253 Vitest passed (34 file), Vite production build PASS. npm ci báo 14 vulnerability (6 moderate, 8 high), chưa tự nâng dependency.
- **Đang dở:** Không còn bước cài đặt/check đang dở; chưa có video dev để chạy 4 vision test còn thiếu. Đã phát hiện webcam qua kiểm tra ngoài sandbox (sandbox không hiện /dev/video*), probe thật 640x480 + pose thành công; worker camera 1 chạy ở exec session 10489, UI /live CAMERA HOẠT ĐỘNG và MJPEG tải 640x480. Chưa có ROI/phiên nên worker chỉ phát hình làm mờ và heartbeat, chưa chạy engine sự kiện. Không đánh dấu feature mới Done. Tab mới được giữ cho người dùng.
- **Bước tiếp theo:** Khi khởi động lại đọc `reports/LOCAL-SETUP.local.md`: `docker start postcare-fresh-db`; API `uv --directory server run uvicorn postcare.api.main:app --host 127.0.0.1 --port 8002`; web Linux `VITE_API_TARGET=http://127.0.0.1:8002 CHOKIDAR_USEPOLLING=1 npm --prefix web run dev -- --host 127.0.0.1 --port 5175 --strictPort`. Nguồn webcam 0 đã có; camera còn cần ROI và phiên theo dõi phù hợp; không mô tả simulator là camera thật.
- **Blocker / câu hỏi cho người dùng:** Không chặn dùng web/DB/camera stream. Người dùng chọn kết nối webcam; nguồn webcam 0 đã đọc được. Còn cần ROI/phiên phù hợp để theo dõi sự kiện. Tiến trình API exec session 64743, web 49477 (chỉ có ý nghĩa trong chat này).
- **Giả định mới:** Dùng cổng riêng cho clone mới để tránh trùng dịch vụ hiện hữu; đây là cấu hình local, không đổi yêu cầu sản phẩm.

## 2026-11-18 (tối) – Claude Code (Opus) – Đã Done 32 feature, demo chạy được

- **Đã làm:** Done và đã push thêm F07, F08, F09, F17–F23, F26–F28, F31. Sửa lỗi an toàn F08 (ghi đè ngưỡng không được tắt luật "không tin một frame"), F35 (đổi vai trò → đóng WS), F19 (race khi resolve), F28 (render lỗi → bỏ khung, không gửi ảnh gốc). Giới hạn vitest `maxWorkers: 2` để tránh hết RAM.
- **Demo đã chạy thử (DB `postcare_demo`, API 8090, web 5190):** 2 worker MediaPipe song song trên clip ghép lặp (A01 Pexels 3753707 → BED_EDGE; A02 GMDCSA24 ngã → ABNORMAL_MOVEMENT HIGH). Live View hiện video thật, làm mờ mặt, ROI; toast cảnh báo ưu tiên cao realtime.
- **Đang dở:** F24 (Done trên nhánh `feat/F24-handover`, chưa merge). F29 (nhánh `feat/F29-final-eval` có tooling + báo cáo, builder dừng giữa chừng). F36 (nhánh `feat/F36-family-access` mới có plan + test đỏ). F30 chưa bắt đầu.
- **Bàn giao sang máy khác:** đã commit WIP và push các nhánh `feat/F24-handover` (Done, chờ merge), `feat/F29-final-eval` (WIP), `feat/F36-family-access` (WIP, chưa chạy test). Hướng dẫn cài lại và tiếp tục: mục "Đang làm" trong TASKS.md.
- **Bước tiếp theo:** merge F24; tiếp tục F29 và F36 bằng builder; F30 (runbook, `--loop` cho worker file, `make demo-seed`, E2E Playwright, chạy trọn 3 lần).
- **Blocker:** Không. Lưu ý: worker `--video` không tự lặp và không thoát khi hết clip (demo dùng video ghép trong scratchpad) → F30 thêm `--loop`. Dữ liệu rời giường camera cố định vẫn thiếu.

## 2026-11-18 – Claude Code (Opus) – Đợt 2–4: M1 xong, M0/M2 phần lớn

- **Mục tiêu phiên:** Làm tiếp roadmap theo vòng đời subagent, chạy được pipeline thật từ video/camera tới dashboard.
- **Đã làm:** Done và đã push: F02, F03, F04, F06, F07, F09, F11, F12, F13, F14, F15, F16, F17, F23, F25, F35, F37 (cùng F00, F01, F05, F10 trước đó). Hiệu chỉnh ngưỡng trên tập dev (ABNORMAL_MOVEMENT 2/71 → 19/71, precision 0,95; FP/giờ 10,7 → 2,7). Quyết định an toàn: phát BED_EDGE khi chưa có lịch sử quan sát; ABNORMAL_MOVEMENT bắt buộc có điều kiện hạ thấp; SITTING→STANDING→OUT_OF_BED là đường rời giường hợp lệ. Sửa lỗi script merge đánh dấu nhầm dòng milestone trong ROADMAP.
- **Kết quả kiểm tra:** `make check` trên `main` (8d2b332): pytest 1071 passed, vitest xanh, build xanh. End-to-end F06/F07: worker chạy MediaPipe trên clip Pexels → BED_EDGE thật → cảnh báo; Live View hiện luồng MJPEG thật kèm ROI. Chưa thử điện thoại thật.
- **Đang dở:** F08, F18 (builder đang chạy trong worktree).
- **Bước tiếp theo:** review + merge F08, F18; rồi F19, F20–F22, F24, F26–F28, F36, F31 R1–R3, F29, F30 và dựng demo.
- **Blocker / câu hỏi cho người dùng:** Không chặn. Dữ liệu rời giường từ camera cố định chưa có (cần nhóm tự quay). MediaPipe mất dấu người nằm sàn ở 38/71 ca ngã.
- **Giả định mới:** xem spec F15, F23, F25, F04 mục 7; calibration-2026-11-18.md.

## 2026-11-17 – Claude Code (Opus) – Đợt 1 (F01, F05, F10), tạm dừng

- **Mục tiêu phiên:** Làm tiếp roadmap theo vòng đời subagent (builder trong worktree → code-reviewer → merge).
- **Đã làm:** Khởi động Docker Desktop, tạo container `postcare-db` (PostgreSQL 16, volume `postcare-pgdata`, DB `postcare` và `postcare_test`). F10 (schema + khung engine, review Đạt), F05 (FrameSource webcam/URL/file, `postcare probe`, review Đạt; đã sửa race khi `close()`, backoff khi đọc lỗi, FPS lệch), F01 (Alembic, PostgreSQL thay SQLite, seed idempotent, CI có Postgres; review Cần sửa → đã sửa) merge vào `main` và push. Sửa test timeline chập chờn do độ phân giải đồng hồ Windows. Thêm `.claude/worktrees/` vào `.gitignore`. Ghim credential GitHub `quocvien0123` trong cấu hình git global.
- **Kết quả kiểm tra:** `make check` trên `main` sau merge: exit 0 (pytest 189 passed, vitest 30 passed). Hook pre-push Passed. URL source kiểm bằng server MJPEG cục bộ (mất kết nối → nối lại đúng). CI run 44118900094 đang chạy lúc dừng.
- **Đang dở:** F01 AC3 (chờ CI). F11 dừng giữa chừng (worktree `agent-ade276c7bc986db7b`, chưa commit). F13 dừng trước khi có thay đổi.
- **Bước tiếp theo:** `curl -s "https://api.github.com/repos/aanhtuan/PostCareAi/actions/runs/44118900094/jobs"` xem kết quả; nếu xanh: tick F01 AC3, Done. Sau đó F02, F11, F13.
- **Blocker / câu hỏi cho người dùng:** Không. Điện thoại thật (DroidCam/IP Webcam) cho F05 chưa thử. `test_handover_counts` từng fail ngẫu nhiên trước F01, chưa tái hiện được sau khi chuyển test sang PostgreSQL.
- **Giả định mới:** xem spec F01, F05, F10 mục 7.

## 2026-11-17 – Claude Code (Opus) – F00 hoàn tất

- **Mục tiêu phiên:** Hoàn thành F00 theo vòng đời subagent (planner → test-writer → implementer → code-reviewer) và các kiểm chứng tay còn thiếu.
- **Đã làm:** 14 commit trên `feat/F00-project-skeleton`: mypy strict cho `schemas`/`engine`, import-linter 8 contract, `postcare version`, `postcare openapi --check` (sửa lỗi ghi CRLF), router health v1, marker `vision`, msw, `config/engine.default.yaml`, `Procfile.dev`, Makefile ↔ `scripts/dev.ps1` có test giữ tương đương, pre-commit + pre-push, CI Ubuntu + Windows. Review: chỉ vướng kiểm tay; đã sửa góp ý nhỏ (AGENTS bước check-api-types, mypy 2.x, ghi `npm audit` vào Backlog).
- **Kết quả kiểm tra:** `make check` và `dev.ps1 check` exit 0 (pytest 80 passed, vitest 30 passed). Bản clone sạch: `make setup` + `make check` exit 0. `git push` thật chạy hook pre-push (`make check` Passed). CI run 44107632897: ubuntu success, windows success. Trình duyệt mở 5173 được; IP LAN 192.168.2.113:5173 trả 200. Chưa thử từ một thiết bị khác.
- **Đang dở:** Không.
- **Bước tiếp theo:** F01 (PostgreSQL Docker + Alembic), F05 (FrameSource), F10 (schema + engine core) song song.
- **Blocker / câu hỏi cho người dùng:** Không.
- **Giả định mới:** pyyaml đang ở nhóm dev; F10 chuyển sang phụ thuộc chính.

## 2026-11-17 – Claude Code (Opus, planner) – F00

- **Mục tiêu phiên:** Lập kế hoạch F00 theo plan-feature.md, xuất phát từ code prototype.
- **Đã làm:** Khảo sát Makefile, `scripts/dev.ps1`, `server/pyproject.toml`, `api/main.py`, `cli/main.py`, test backend/frontend, cấu hình web. Ghi bảng phần đã đạt (9.1), 13 bước (9.2), test theo AC (9.3), doc cần cập nhật (9.4), rủi ro (9.5) vào spec mục 9; thêm giả định mới vào mục 7 và 2 câu hỏi mở không chặn vào mục 8. Spec, ROADMAP: F00 `Planned`; TASKS: F00 sang "Đang làm" kèm checklist. Chỉ sửa tài liệu, không chạy git, chưa commit.
- **Kết quả kiểm tra:** Không chạy `make check` (chỉ đổi tài liệu). Khảo sát import `from postcare` cho thấy chưa có vi phạm ranh giới overview.md §3.
- **Đang dở:** Chưa triển khai bước nào của 9.2. `docs/03-features/README.md` chưa đổi trạng thái F00 (ngoài quyền của planner).
- **Bước tiếp theo:** test-writer viết test bước 2, 6, 7, 10 (`server/tests/test_health.py`, `test_cli.py`, `test_tooling.py`, `web/src/App.test.tsx`); implementer làm bước 1 (`uv --directory server add --dev mypy import-linter pre-commit honcho`) rồi lần lượt tới bước 13, `make check` sau mỗi bước.
- **Blocker / câu hỏi cho người dùng:** Không chặn. Câu hỏi mở: job CI Windows; `make` trong PATH Git Bash cho pre-push; service Postgres trong CI để F01 (mặc định); bỏ alias `make build`.
- **Giả định mới:** giữ prototype và package `cli/`; trang gốc là trang đăng nhập dùng `vi.app.name`; kiểm tra OpenAPI so JSON đã parse; hook chỉ kiểm tra không tự sửa; `test_tooling.py` giữ dev.ps1 tương đương Makefile; msw `onUnhandledRequest: 'error'` (đã ghi vào spec mục 7).

## 2026-11-17 – Claude Code (Opus) – Hợp nhất đề xuất nhóm, chốt kế hoạch tới demo dữ liệu thật

- **Mục tiêu phiên:** Đánh giá hai file đề xuất của nhóm (MASTER-SPEC, Tổng hợp), gỡ mâu thuẫn, gộp vào tài liệu, xóa tài liệu lỗi thời; lập kế hoạch triển khai đầy đủ theo roadmap với dữ liệu thật thay bộ giả lập.
- **Đã làm:**
  - Cài công cụ thiếu trên máy dev (không có winget): uv 0.13.9 qua pip, GNU Make 4.4.1 (zip ezwinports, đã so SHA1), gh 2.104.0 (zip GitHub Releases, đã so SHA256); thêm vào PATH người dùng. Docker Desktop có sẵn.
  - Quyết định người dùng: QA#31 (người nhà, F36), QA#32 (chung kết 1 camera live + 1 clip, F31 R1–R3), QA#33 (dữ liệu ngoài), QA#34 (PostgreSQL bằng Docker), QA#35 (MediaPipe chính, chọn biến thể bằng benchmark, GPU qua WSL2, RTMPose dự phòng), QA#36 (chỉ xóa mềm; F35 vào MVP; F37 khu vực/ca trực; chuyển giường trong F04), QA#37 (hai loại độ trễ). Đi đúng roadmap, không làm lát cắt tắt.
  - Tài liệu mới: `docs/01-product/pitch-and-evidence.md`, `docs/progress/DEMO-PLAN.md`, `docs/04-guides/datasets.md`, spec F36, F37; viết lại F35; mở rộng F03, F04; cập nhật PRD, glossary, tech-stack, dev-setup, data-model, api-conventions, ROADMAP, mục lục feature, F31, ghi chú ở F18/F21/F22, README, AGENTS, TASKS, evaluation.md §8.
  - Dữ liệu (không commit): URFD, GMDCSA24, CAUCAFall, 19 clip Pexels/Mixkit vào `data/external/` (~2,5 GB); `data/eval/manifest.csv` (379 video, 0,87 giờ) và `truth.csv` (211 nhãn, có cột `label_source`). Le2i bỏ qua vì không còn mirror video. Không tải NTU, Toyota Smarthome, ETRI, SLP, CMDFall, Montreal.
  - Xóa `SUMMARY.md` (nội dung đã vào README và nhật ký) và hai file đề xuất; bản gốc ở commit `fc5a2bf`.
- **Kết quả kiểm tra:** Chỉ đổi tài liệu. Kiểm tra link tương đối bằng script: không còn link hỏng. `make check` PASS (ruff, prettier, eslint, tsc, pytest 40 passed, vitest 25 passed, build). Chưa đổi code.
- **Đang dở:** Chưa bắt đầu feature nào; mọi F00–F37 vẫn Todo.
- **Bước tiếp theo:** F00 theo vòng đời planner → test-writer → implementer → code-reviewer → cập nhật tiến độ → merge (`feat/F00-project-skeleton`). Sau F00 chạy song song F01 (B), F05 và F10 (A).
- **Blocker / câu hỏi cho người dùng:** Không chặn. Câu hỏi mở ghi trong F35/F36/F37/F04 (người nhà thấy sự kiện nào, grant sau chuyển giường, đổi ca ảnh hưởng bàn giao cũ…). Khoảng trống dữ liệu: không có video công khai về rời giường bệnh từ camera cố định; S02, S07, S12, S14, S16 chưa có nguồn.
- **Giả định mới:** nhãn tay trên stock clip; mã không gán nhãn trên một video không tính là FP (datasets.md, F16); tạm dừng thu hình là cờ của phiên (F04/F36).

## 2026-11-16 12:28 – Codex – Chuẩn bị xuất bản GitHub

- **Mục tiêu phiên:** Đẩy dự án lên https://github.com/aanhtuan/PostCareAi.git theo yêu cầu người dùng.
- **Đã làm:** Xác nhận remote trống, cấu hình origin; kiểm tra danh sách 206 file và mẫu bí mật phổ biến, không phát hiện mẫu bí mật. Dữ liệu SQLite, .env, phụ thuộc, model và video được gitignore; ảnh trong docs/00-source/assets là hình tham khảo của tài liệu nguồn. Cài lại phụ thuộc frontend bằng `npm --prefix web ci` để phù hợp Linux. Cập nhật SUMMARY.md theo kết quả mới. Không sửa code ứng dụng, không seed dữ liệu.
- **Kết quả kiểm tra:** `make check` PASS: Ruff format/lint, Prettier, ESLint, TypeScript, pytest 40 passed (13.72 s), Vitest 25 passed và production build. Kết luận sai format hai file API ở phiên kiểm kê do gọi Prettier ngoài thư mục web, không áp dụng đúng .prettierignore; lần chạy đúng không cần sửa file. Chưa kiểm tra camera thật, trình duyệt hoặc E2E; chưa có hook thực thi trong repo, không bỏ qua hook.
- **Đã xuất bản:** Commit đầu tiên `e59d28f` đã push thành công lên `origin/main`. HTTPS không có thông tin đăng nhập dùng được; chuyển push URL sang SSH `git@github.com:aanhtuan/PostCareAi.git`, giữ fetch URL HTTPS. Không force-push.
- **Đang dở:** Không; cập nhật bàn giao kết quả xuất bản.
- **Bước tiếp theo:** Tiếp tục lập kế hoạch F00 khi người dùng yêu cầu; dùng `git status` và `git pull --ff-only` trước khi làm việc từ máy khác.
- **Blocker / câu hỏi cho người dùng:** Không; quyền push qua SSH đã được xác nhận. `git diff --cached --check` trước commit có báo khoảng trắng cuối dòng trong tài liệu nguồn nhập từ trước; giữ nguyên nguồn theo docs/00-source/README.md.
- **Giả định mới:** Không; đây là xuất bản prototype hiện có, không đánh dấu feature Done.

## 2026-11-16 12:21 – Codex – Lưu summary Markdown

- **Mục tiêu phiên:** Lưu bản tổng kết dự án thành file Markdown theo yêu cầu người dùng.
- **Đã làm:** Tạo SUMMARY.md tại thư mục gốc, tổng hợp chức năng đã có, phần còn thiếu, kết quả kiểm tra ngày 16/11/2026, roadmap, Git và bước tiếp theo. Tick task tài liệu trong TASKS.md.
- **Kết quả kiểm tra:** Đối chiếu với kết quả kiểm kê ngay trước đó; kiểm tra file Markdown được lưu. Không chạy lại test vì chỉ bổ sung tài liệu; `make check` vẫn chưa xanh theo entry kiểm kê.
- **Đang dở:** Không.
- **Bước tiếp theo:** Đọc SUMMARY.md; nếu tiếp tục phát triển, xử lý phụ thuộc frontend rồi chạy `make check` theo entry kiểm kê.
- **Blocker / câu hỏi cho người dùng:** Không có blocker cho việc tạo summary; blocker kỹ thuật giữ nguyên như entry trước.
- **Giả định mới:** Không.

## 2026-11-16 12:18 – Codex – Kiểm kê hiện trạng dự án

- **Mục tiêu phiên:** Đối chiếu tài liệu tiến độ với code và chạy kiểm tra để tóm tắt hiện trạng theo yêu cầu người dùng.
- **Đã làm:** Đọc AGENTS, TASKS, nhật ký, ROADMAP, README và spec F00; kiểm kê API, nghiệp vụ cảnh báo, simulator, trang web và test. Xác nhận engine/vision/worker/pipeline/replay/eval chỉ là module giữ chỗ; chưa có config/engine.default.yaml. Không sửa code ứng dụng, không seed dữ liệu, không commit.
- **Kết quả kiểm tra:** Backend pytest 40 passed (13.78 s), Ruff lint và format đạt; TypeScript tsc và ESLint đạt khi gọi trực tiếp bằng Node từ đúng thư mục. `make check` thất bại ở frontend format-check vì node_modules/.bin/prettier thiếu quyền thực thi. Gọi Prettier trực tiếp báo sai format tại web/src/api/openapi.json và schema.d.ts. Vitest và Vite build chưa chạy thành công: thiếu native binding Rolldown cho Linux. Không kiểm tra giao diện bằng trình duyệt, camera thật hoặc E2E. uv tự tạo lại server/.venv cho môi trường Linux khi chạy check.
- **Đang dở:** Không triển khai feature trong phiên kiểm kê. Toàn bộ F00–F35 vẫn Todo; prototype có chức năng nhưng chưa đạt Definition of Done theo spec.
- **Bước tiếp theo:** Nếu tiếp tục phát triển: cài lại phụ thuộc frontend phù hợp Linux bằng `npm --prefix web ci`, kiểm tra lại format hai file sinh tự động rồi chạy `make check`; sau đó lập kế hoạch F00 theo docs/ai/workflows/plan-feature.md trước khi triển khai.
- **Blocker / câu hỏi cho người dùng:** Bộ phụ thuộc frontend hiện tại chưa dùng được đầy đủ trên Linux; repo chưa có commit nào. TASKS vẫn còn mục review trước khi viết code từ phiên khởi tạo, cần điều chỉnh khi chốt bước phát triển tiếp theo.
- **Giả định mới:** Không.

## 2026-10-12 21:30 – Claude Code (Opus) – Prototype đề xuất (ngoài roadmap)

- **Mục tiêu phiên:** Theo yêu cầu người dùng (thay quy tắc "chưa viết code"): tạo code base chạy được cho các phần chính để đề xuất, chưa cần phần AI, có hướng dẫn trong README.
- **Đã làm:** (chưa commit, theo yêu cầu)
  - Cài công cụ cấp người dùng: uv 0.13.0 (script Astral) + CPython 3.12.15; Node.js v24.21.0 / npm 11.19.0 (bản zip chính thức, kiểm tra SHA256, giải nén vào `%USERPROFILE%\.local\node`, thêm vào PATH người dùng). Không có winget nên **chưa cài GNU Make**; thay bằng `scripts/dev.ps1`.
  - `server/`: package `postcare` (schemas, db, domain, api, cli; engine/vision/pipeline/worker/replay/eval để trống). Auth JWT + 4 vai trò, giường/camera/bệnh nhân (chỉ đọc), phiên theo dõi (409), API nội bộ config/heartbeat/state/events (idempotent, MEDIUM/HIGH → alert PENDING, lưu trước phát sau), camera offline sau 5 s (A02), vòng đời cảnh báo theo ADR-0007 + audit, overview, events, alerts, timeline (UNION ALL), handover (SQL aggregation), WebSocket `/api/v1/ws` (đóng 4401 khi token sai). CLI `postcare seed | simulate | openapi`.
  - `web/`: React 19 + Mantine 8 + TanStack Query 5 + React Router 7; trang Đăng nhập, Tổng quan (A12), Theo dõi trực tiếp (skeleton SVG mô phỏng), Cảnh báo (nút đúng PDF §9.2, âm thanh Web Audio cho HIGH), Lịch sử theo dõi, Bàn giao ca (in được), Quản lý giường (mở/đóng phiên). Text trong `web/src/i18n/vi.ts`; type sinh từ OpenAPI (`schema.d.ts`).
  - Root: `Makefile` (setup, dev-api, dev-web, seed, simulate, test, lint, format, check…), `scripts/dev.ps1`, `.env.example` (SQLite mặc định), `.gitignore` (`server/postcare.db*`), README viết lại.
  - ADR-0010 (SQLite + create_all + bộ giả lập, điều kiện quay lại PostgreSQL + Alembic ở F01).
- **Kết quả kiểm tra:** `scripts\dev.ps1 check` xanh: ruff format/check, prettier, eslint, tsc, pytest 40 passed, vitest 25 passed, `vite build`. Kiểm tra tay: health 200, login `nurse/postcare`, web dev trả HTML, proxy REST + WS qua 5173, `postcare simulate --bed A01` tạo BED_EXIT HIGH PENDING, acknowledge/outcome/resolve 200, tiếp nhận lần 2 → 409 kèm tên, DOCTOR → 403, timeline đủ chuỗi, WS token sai → 4401. Chưa kiểm tra giao diện bằng trình duyệt thật (máy không có trình duyệt tự động).
- **Đang dở:** Không.
- **Bước tiếp theo:**
  - Người dùng chạy thử theo README mục 3 (kịch bản demo) và góp ý giao diện.
  - Quyết định giữ code prototype làm nền cho F00/F01 hay viết lại theo spec; nếu giữ: `/plan-feature F00` (thêm pre-commit, import-linter, mypy, CI), rồi F01 (PostgreSQL + Alembic theo ADR-0010).
- **Blocker / câu hỏi cho người dùng:** Cài GNU Make (`winget`/`choco`) nếu muốn dùng `make`; máy này không có winget.
- **Giả định mới:** (ghi trong ADR-0010 và code) giường chưa nhận trạng thái được coi như "Không đủ dữ liệu quan sát" → thẻ "Cần kiểm tra"; camera offline đặt trạng thái giường về NO_OBSERVATION/CAMERA_ISSUE; câu cảnh báo dạng "{sự kiện} lúc HH:mm:ss."; danh mục chỉ đọc trên UI (thêm/sửa qua seed).

## 2026-10-12 – Claude Code (Opus) – Khởi tạo tài liệu (trước F00)

- **Mục tiêu phiên:** Tạo bộ tài liệu lõi trung lập với AI, adapter cho Claude, spec cho toàn bộ feature và roadmap. **Không viết code ứng dụng.**
- **Đã làm:**
  - Khởi tạo git (`main`, chưa commit). Di chuyển nguồn vào `docs/00-source/`: `de-tai.pdf`, `ho-so-so-loai-2026.md`, `assets/image*.png`.
  - Chuyển PDF sang `docs/00-source/de-tai.md` (21 dấu trang, 20 mục, dựng lại bảng trang 10/15/19). Viết `conflicts.md` (C01–C17, áp dụng HS khi xung đột).
  - `docs/01-product/`: PRD, glossary (gồm từ cấm), qa-decisions (QA#1–30, giả định A01–A15).
  - `docs/02-architecture/`: overview, tech-stack, data-model, api-conventions, event-engine, ADR-0001…0009.
  - `docs/03-features/`: template, mục lục, 36 spec F00–F35 (F31–F35 viết ngắn).
  - `docs/04-guides/`: coding-standards, testing, dev-setup, camera-setup, evaluation.
  - `docs/ai/`: 4 workflow, 3 role. `docs/progress/`: ROADMAP, TASKS, file này.
  - Root: `AGENTS.md`, `CLAUDE.md`, `README.md`, `.gitignore`, `.gitattributes`, `.editorconfig`, `.env.example`. Adapter: `.claude/commands/*` (4), `.claude/agents/*` (3), `.gemini/settings.json`.
  - Rà soát chéo giữa spec và tài liệu kiến trúc. Đã thống nhất:
    - `FaceObservation` (output của adapter) và `FaceSignals` (tín hiệu do engine suy ra).
    - `EngineContext` truyền ROI vào engine.
    - Module `pipeline` dùng chung cho worker và replay; `EngineConfig` đặt trong `schemas`.
    - `activity_level` có thêm UNKNOWN; STANDING được ưu tiên hơn AT_EDGE.
    - `config_hash` không tính các khóa `privacy.*`.
    - Mã lỗi mới: `NO_ACTIVE_SESSION`, `BED_ALREADY_HAS_CAMERA`, `SESSION_ALREADY_ENDED`; mã đóng WebSocket 4401.
    - `events.bed_id` cho phép null; `config_hash` mặc định chuỗi rỗng.
    - Test từ cấm làm từ F00; F21 thêm AC cho màn hình Theo dõi trực tiếp; F09 và F21 thuộc nhánh B+C.
- **Kết quả kiểm tra:** chưa có code nên chưa có `make check`. Đã kiểm tra tài liệu bằng script: link tương đối, đủ mục của template, độ dài AGENTS.md.
- **Đang dở:** Không.
- **Bước tiếp theo:**
  - Người dùng review tài liệu (checklist ở `TASKS.md` mục "Đang làm").
  - Sau khi người dùng xác nhận: cài GNU Make, uv, Node LTS, PostgreSQL 16 ([dev-setup.md](../04-guides/dev-setup.md)), rồi `/plan-feature F00`.
- **Blocker / câu hỏi cho người dùng:**
  - Xác nhận hoặc sửa các giả định A01–A15 và các giả định trong từng spec.
  - Các câu hỏi mở không chặn: F08 (thêm F10 vào phụ thuộc hay giữ cách tạm), F27 (có hiện nghỉ/hoạt động trên timeline không).
  - Một câu hỏi **chặn**, nhưng ở feature sau MVP: F33 (thông báo di động cần cloud/HTTPS, trái với QA#25 và A09).
- **Giả định mới:** đã ghi trong mục 7 của từng spec và trong `event-engine.md` (các khóa `face.enabled`, `face.head_crop_scale`, `rest.active_hold_s`, `privacy.*`).
