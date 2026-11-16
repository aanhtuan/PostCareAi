# Nhật ký phiên làm việc

Entry mới nhất ở trên cùng. Mẫu và quy tắc: [update-progress.md](../ai/workflows/update-progress.md). Không xóa entry cũ.

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
