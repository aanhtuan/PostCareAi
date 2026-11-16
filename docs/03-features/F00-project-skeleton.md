# F00 – Khung xương dự án

| Thuộc tính | Giá trị |
|---|---|
| Mã | F00 |
| Trạng thái | Todo <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M0 |
| Ước lượng | 2 phiên |
| Phụ thuộc | — |
| Nhánh code | A+B+C |
| Nguồn | Yêu cầu người dùng; HS §6.1; QA#6, QA#8, QA#9, QA#10, QA#23; A13; ADR-0001, ADR-0005, ADR-0006 |

## 1. Mục tiêu

Tạo bộ khung chạy được cho cả backend (Python, package `postcare`) và frontend (React + TS). Có sẵn lint, format, typecheck, kiểm tra ranh giới module, test, git hook và CI. Nhờ vậy mọi feature sau (do người hoặc AI agent viết) đều được kiểm chứng tự động bằng một lệnh `make check`, chạy giống nhau trên Windows và Linux (yêu cầu người dùng; QA#6, QA#23; ADR-0006). Cấu trúc module theo HS §6.1 và [overview.md](../02-architecture/overview.md#3-module-trong-serversrcpostcare).

F00 là **khung xương**: chỉ có endpoint `GET /api/v1/health` và trang chào tiếng Việt. **F00 không có cơ sở dữ liệu.** PostgreSQL, SQLAlchemy, Alembic và các target DB thật thuộc F01.

## 2. Phạm vi

**Trong phạm vi**
- `Makefile` với đủ các target ở mục R3 (một số là target giữ chỗ cho feature sau).
- `server/`: `pyproject.toml`, `.python-version` (3.12), `uv.lock`, package `postcare` với các module rỗng theo overview.md, Typer CLI, FastAPI app có `/api/v1/health`, test đầu tiên.
- `server/.importlinter`: contract ranh giới module.
- `web/`: Vite + React + TS + Mantine, ESLint, Prettier, Vitest, `src/i18n/vi.ts`, test đầu tiên.
- `web/src/i18n/vi.test.ts`: test quét **từ cấm** trong `vi.ts` theo [glossary.md](../01-product/glossary.md#từ-cấm-trên-ui). Làm từ F00 để mọi text UI của F02–F09 cũng được kiểm tra *(testing.md §1)*. F20 bổ sung test "đủ text cho mọi enum".
- `config/engine.default.yaml` bản khởi điểm (chép từ [event-engine.md §6](../02-architecture/event-engine.md#6-cấu-hình-và-ngưỡng-mặc-định)).
- `Procfile.dev` cho `make dev` (honcho).
- `.pre-commit-config.yaml`: hook pre-commit và pre-push.
- `.github/workflows/ci.yml`: CI Ubuntu chạy `make setup` rồi `make check`.
- Cập nhật cột "Phiên bản đã khóa" trong [tech-stack.md](../02-architecture/tech-stack.md) cho các gói đã cài.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Cơ sở dữ liệu, migration, seed, service Postgres trong CI (→ F01).
- Đăng nhập, định dạng lỗi `{error:{code,message}}`, `DomainError` (→ F02).
- Lệnh `worker` (→ F06), `probe` (→ F05), `replay` (→ F12), `eval` (→ F16), tải model (→ F11).
- `EngineConfig` và schema engine (→ F10). F00 chỉ tạo file YAML.
- Test "đủ text cho mọi enum" trong `vi.ts` (→ F20).
- Playwright và target `make e2e` (→ F30).
- `.gitignore`, `.gitattributes`, `.editorconfig`, `.env.example`, `AGENTS.md`, `README.md`: đã tạo ở bước tài liệu. F00 chỉ bổ sung mục còn thiếu (ví dụ `web/dist/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`).

## 3. Yêu cầu chi tiết

- **R1.** Python 3.12 do uv quản lý qua `server/.python-version`; phụ thuộc khóa bằng `server/uv.lock`. Node 24 LTS (hoặc 22 LTS); phụ thuộc khóa bằng `web/package-lock.json` *(tech-stack.md; A13)*.
- **R2.** Package `server/src/postcare/` có đủ các module của overview.md §3: `schemas`, `engine`, `vision`, `worker`, `replay`, `eval`, `db`, `domain`, `api` (mỗi module có `__init__.py`), cộng `cli.py` và `api/main.py` *(HS §6.1; overview.md §3)*.
- **R3.** `Makefile` có các target: `help`, `setup`, `dev`, `dev-api`, `dev-web`, `worker`, `format`, `format-check`, `lint`, `typecheck`, `lint-imports`, `test`, `test-vision`, `build-web`, `check`, `db-upgrade`, `db-seed`, `models`, `gen-api-types` *(yêu cầu người dùng)*.
  - `check` = `format-check` + `lint` + `typecheck` + `lint-imports` + `test` + `build-web` *(testing.md §5)*, cộng bước kiểm tra type API cũ ở R12 *(ADR-0005)*.
  - `test` chạy pytest với `-m "not vision"` rồi vitest. `test-vision` chạy `pytest -m vision` *(testing.md §1)*.
  - `typecheck` chạy mypy strict cho `postcare.schemas` và `postcare.engine`, và kiểm tra kiểu TypeScript của `web/` *(coding-standards.md §2, §3)*.
  - `worker`, `db-upgrade`, `db-seed`, `models` là target giữ chỗ: in thông báo ASCII cho biết feature nào sẽ hoàn thiện (`F06`, `F01`, `F01`, `F11`) và trả exit code khác 0 *(giả định: để không ai tưởng lệnh đã chạy thật)*.
  - `worker` nhận biến `CAMERA` (`make worker CAMERA=1`) *(overview.md §1)*.
- **R4.** Recipe Makefile **không dùng cú pháp chỉ có trên bash/sh** *(yêu cầu người dùng; coding-standards.md §1)*:
  - chỉ gọi `uv` (`uv --directory server run …` hoặc `uv run --project server …`) và `npm --prefix web run …`;
  - không dùng `rm`, `cp`, `mkdir -p`, `test`/`[ ]`, `export`, `VAR=x cmd`, `$(shell …)` gọi công cụ Unix, dấu nháy đơn để bọc tham số;
  - thông báo trong recipe chỉ dùng ký tự ASCII *(giả định: cmd trên Windows có thể hiển thị sai tiếng Việt)*;
  - logic phức tạp đặt trong script npm của `web/package.json` hoặc lệnh Python, không đặt trong recipe.
- **R5.** `make setup`: `uv sync` cho `server/`, `npm ci` cho `web/`, rồi cài git hook bằng pre-commit cho cả `pre-commit` và `pre-push` *(dev-setup.md §3; tech-stack.md)*.
- **R6.** `.pre-commit-config.yaml` *(ADR-0006; tech-stack.md "Git hook")*:
  - stage `pre-commit`: `ruff format`, `ruff check` (file trong `server/`), `prettier --check` và `eslint` (file trong `web/`);
  - stage `pre-push`: hook local `make check` (`pass_filenames: false`, `always_run: true`);
  - prettier và eslint dùng đúng phiên bản trong `web/package-lock.json` *(giả định: hook `repo: local`, gọi binary trong `web/node_modules`, tránh lệch phiên bản giữa hook và `make check`)*;
  - prettier **chỉ** áp dụng cho `web/` *(giả định: prettier tự căn lại bảng Markdown, sẽ làm thay đổi hàng loạt file trong `docs/`)*.
- **R7.** Contract import-linter trong `server/.importlinter`, chạy bởi `make lint-imports` *(yêu cầu người dùng; overview.md §3; AGENTS.md quy tắc 5)*:
  - **bắt buộc:** `postcare.engine` và `postcare.schemas` không import `cv2`, `mediapipe`, `fastapi`, `sqlalchemy`, `httpx`;
  - **bắt buộc:** `postcare.schemas` không import module `postcare.*` khác; `postcare.engine` không import `postcare.vision`, `postcare.api`, `postcare.db`;
  - các ranh giới còn lại của bảng overview.md §3 (`api` không import `vision`/`engine`; `vision`, `worker`, `replay`, `eval` không import `api`/`db`; `db` không import `api`/`vision`/`engine`; `domain` không import `api`/`vision`) cũng được khai báo ngay ở F00 *(overview.md §3: "các ranh giới trên được kiểm tra tự động")*.
- **R8.** FastAPI app tại `postcare.api.main:app`, router `GET /api/v1/health` → 200 `{"status":"ok"}`, OpenAPI tại `/api/openapi.json` *(api-conventions.md)*. `make dev-api` chạy uvicorn có reload, nghe `0.0.0.0` để truy cập qua LAN *(QA#25; giả định cổng 8000)*.
- **R9.** Typer CLI `postcare` khai báo trong `pyproject.toml` (`[project.scripts]`). F00 chỉ cần lệnh `postcare --help` và `postcare version` *(giả định: lệnh tối thiểu để kiểm chứng CLI cài đúng)*.
- **R10.** Web: trang gốc hiển thị tiêu đề "PostCare AI" và một dòng mô tả tiếng Việt lấy từ `web/src/i18n/vi.ts` *(yêu cầu người dùng; ADR-0005)*. `make dev-web` chạy Vite nghe `0.0.0.0` *(QA#25; giả định cổng 5173)* và proxy `/api` sang API *(giả định: tránh CORS khi dev)*. Cấu trúc thư mục `web/src/` theo coding-standards.md §3.
- **R11.** Vitest + Testing Library, môi trường `jsdom`. Chốt dùng **msw** để mock API, cài sẵn file setup không có handler *(testing.md §4 ghi "giả định chọn msw ở F00")*.
- **R12.** `make gen-api-types` sinh `web/src/api/schema.d.ts` từ OpenAPI bằng openapi-typescript, **không cần chạy server** *(ADR-0005; giả định: xuất `app.openapi()` ra file JSON bằng lệnh Python rồi đưa vào openapi-typescript)*. `make check` báo lỗi khi file sinh ra không khớp với OpenAPI hiện tại *(ADR-0005 "Hệ quả")*.
- **R13.** `.github/workflows/ci.yml` chạy trên `ubuntu-latest` với mỗi push và pull request: checkout, cài uv, cài Node, `make setup`, `make check` *(QA#8; yêu cầu người dùng)*. F00 chưa cần service Postgres (thêm ở F01).
- **R14.** `config/engine.default.yaml` có nội dung khởi điểm như event-engine.md §6. F00 không đọc file này trong code *(yêu cầu người dùng)*.
- **R15.** `Procfile.dev` có 2 tiến trình `api` và `web`. `make dev` chạy bằng honcho *(tech-stack.md)*.
- **R16.** Ruff: độ dài dòng 100, cấu hình trong `server/pyproject.toml`. TypeScript `strict: true`; ESLint cấm `any` *(coding-standards.md §2, §3)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - Gốc repo: `Makefile`, `Procfile.dev`, `.pre-commit-config.yaml`, `.github/workflows/ci.yml`, `config/engine.default.yaml`.
  - `server/pyproject.toml`, `server/.python-version`, `server/uv.lock`, `server/.importlinter`.
  - `server/src/postcare/__init__.py`, `server/src/postcare/cli.py`.
  - `server/src/postcare/{schemas,engine,vision,worker,replay,eval,db,domain}/__init__.py` (rỗng).
  - `server/src/postcare/api/__init__.py`, `server/src/postcare/api/main.py`, `server/src/postcare/api/v1/__init__.py`, `server/src/postcare/api/v1/health.py`.
  - `server/tests/test_health.py`, `server/tests/test_cli.py`.
  - `web/package.json`, `web/package-lock.json`, `web/vite.config.ts`, `web/tsconfig.json`, `web/eslint.config.js`, `web/.prettierrc`, `web/index.html`.
  - `web/src/main.tsx`, `web/src/App.tsx`, `web/src/App.test.tsx`, `web/src/i18n/vi.ts`, `web/src/test/setup.ts`, `web/src/api/schema.d.ts` (sinh tự động).
- **Dữ liệu:** không có (DB ở F01).
- **API:** `GET /api/v1/health` (xem [api-conventions.md](../02-architecture/api-conventions.md#danh-sách-endpoint-dự-kiến)).
- **UI:** trang gốc tạm thời. Thêm vào `vi.ts`: `app.title` ("PostCare AI"), `app.tagline` (ví dụ "Hệ thống hỗ trợ quan sát bệnh nhân hậu phẫu").
- **Cấu hình:** `config/engine.default.yaml` (bản khởi điểm, chưa được đọc).

## 5. Acceptance criteria

- [ ] **AC1.** Trên máy sạch đã cài công cụ ở dev-setup.md, `make setup` rồi `make check` thành công (exit 0) trên Windows (GNU Make, chạy từ PowerShell) và trên CI Ubuntu. *(yêu cầu người dùng; QA#23)* — *Kiểm chứng:* job CI `ci.yml` xanh; trên Windows chạy tay `make setup` và `make check`, ghi kết quả vào mục 10.
- [ ] **AC2.** `make dev-api` → `GET /api/v1/health` trả 200 `{"status":"ok"}`. `make dev-web` mở trang có tiêu đề "PostCare AI" và dòng mô tả tiếng Việt lấy từ `vi.ts`. *(yêu cầu người dùng)* — *Kiểm chứng:* test `test_health_returns_ok`; test vitest `App renders Vietnamese title`; mở trình duyệt kiểm tra tay.
- [ ] **AC3.** Có ≥1 test pass ở mỗi phía (pytest, vitest). `make check` trả exit code khác 0 khi có file sai format ở `server/` hoặc `web/`. Test `vi.test.ts` quét từ cấm chạy trong `make check` *(yêu cầu người dùng; glossary.md)* — *Kiểm chứng:* `make test`; thêm tạm một file Python và một file TSX sai format, chạy `make check` thấy lỗi ở bước `format-check`, rồi xóa.
- [ ] **AC4.** `make setup` cài hook pre-commit (ruff format, ruff check, prettier, eslint) và hook pre-push (`make check`). *(yêu cầu người dùng; ADR-0006)* — *Kiểm chứng:* có file `.git/hooks/pre-commit` và `.git/hooks/pre-push`; commit thử một file sai format thì bị chặn; `git push` thử (hoặc `pre-commit run --hook-stage pre-push --all-files`) thì chạy `make check`.
- [ ] **AC5.** Contract import-linter "`engine`/`schemas` không import `cv2`, `mediapipe`, `fastapi`, `sqlalchemy`, `httpx`" và các ranh giới ở R7 chạy trong `make check`. *(yêu cầu người dùng; overview.md §3)* — *Kiểm chứng:* `make lint-imports` xanh; thêm tạm `import fastapi` vào `postcare/engine/__init__.py` thì `make lint-imports` báo lỗi, rồi xóa.
- [ ] **AC6.** `make gen-api-types` sinh `web/src/api/schema.d.ts` mà không cần chạy server. `make check` báo lỗi khi file này cũ so với OpenAPI. *(ADR-0005)* — *Kiểm chứng:* chạy `make gen-api-types` trên máy sạch; thêm tạm một endpoint mà không sinh lại type thì `make check` báo lỗi.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | CI + thủ công | Job `check` trong `ci.yml`; chạy tay trên Windows (PowerShell) | Thử thêm tạm một recipe dùng `rm -rf` → review từ chối (R4) |
| AC2 | API | `test_health_returns_ok` (TestClient, không cần DB) | `test_unknown_path_returns_404` |
| AC2 | component | `App.test.tsx`: `App renders Vietnamese title` (lấy text từ `vi.ts`, không viết cứng trong test) | — |
| AC2 | thủ công | `make dev-api`, `make dev-web`, mở `http://localhost:5173` và từ máy khác trong LAN | — |
| AC3 | unit | `test_cli.py`: `postcare --help` và `postcare version` trả exit 0 | Lệnh không tồn tại → exit khác 0 |
| AC3 | thủ công | File sai format làm `make check` thất bại | File đúng format → xanh |
| AC3 | unit (Vitest) | `vi.test.ts`: `contains no forbidden words` | Chèn tạm chuỗi chứa "chẩn đoán" → test fail |
| AC4 | thủ công | Commit file sai format bị chặn; pre-push chạy `make check` | Commit file đúng format → qua |
| AC5 | lệnh | `make lint-imports` | Import bị cấm thêm tạm vào `engine` và `schemas` → lỗi |
| AC6 | lệnh | `make gen-api-types`; bước kiểm tra type cũ trong `make check` | Endpoint mới chưa sinh lại type → lỗi |

## 7. Giả định

- *(giả định)* Cổng mặc định: API 8000, web 5173. Cả hai nghe `0.0.0.0` để dùng qua LAN (QA#25).
- *(giả định)* Target giữ chỗ (`worker`, `db-upgrade`, `db-seed`, `models`) in thông báo ASCII và trả exit khác 0 cho tới khi feature tương ứng hoàn thành.
- *(giả định)* Thông báo trong Makefile dùng ASCII vì cmd trên Windows có thể không hiển thị đúng tiếng Việt.
- *(giả định)* `make help` in danh sách target bằng các dòng `@echo` cố định (không parse Makefile bằng awk/grep).
- *(giả định)* `pyproject.toml` ở F00 chỉ khai báo các gói cần ngay: fastapi, uvicorn, pydantic, pydantic-settings, typer; nhóm dev: pytest, httpx (cho TestClient), ruff, mypy, import-linter, pre-commit, honcho. Feature sau tự thêm gói mình cần (sqlalchemy ở F01, opencv ở F05, mediapipe ở F11…) theo quy tắc trong tech-stack.md.
- *(giả định)* Prettier chỉ chạy trên `web/`, không chạy trên `docs/`.
- *(giả định)* Hook prettier/eslint là hook `local`, dùng binary trong `web/node_modules`.
- *(giả định)* Vite proxy `/api` sang API khi dev.
- *(giả định)* `test-vision` phải trả exit 0 khi chưa có test vision nào. Pytest trả exit 5 khi không thu được test nào; planner chọn cách xử lý (ví dụ một test giữ chỗ có marker `vision` luôn được skip).
- *(giả định)* Lệnh `postcare version` là lệnh CLI tối thiểu.
- *(giả định)* Phiên bản Node của CI lấy từ `web/.nvmrc` (hoặc trường `engines` trong `package.json`).

## 8. Câu hỏi mở

- Có thêm job `windows-latest` vào CI để kiểm chứng AC1 tự động không, hay chỉ kiểm tra tay trên Windows? Mặc định: chỉ kiểm tra tay. **Không chặn.**
- Hook pre-push trên Windows cần `make` có trong `PATH` của Git Bash (Git for Windows chạy hook bằng bash của nó). Cần xác nhận khi chạy thật; nếu lỗi thì bổ sung vào dev-setup.md. **Không chặn.**

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
