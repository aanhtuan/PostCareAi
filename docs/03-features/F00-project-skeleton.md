# F00 – Khung xương dự án

| Thuộc tính | Giá trị |
|---|---|
| Mã | F00 |
| Trạng thái | In progress <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
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
- [x] **AC3.** Có ≥1 test pass ở mỗi phía (pytest, vitest). `make check` trả exit code khác 0 khi có file sai format ở `server/` hoặc `web/`. Test `vi.test.ts` quét từ cấm chạy trong `make check` *(yêu cầu người dùng; glossary.md)* — *Kiểm chứng:* `make test`; thêm tạm một file Python và một file TSX sai format, chạy `make check` thấy lỗi ở bước `format-check`, rồi xóa.
- [ ] **AC4.** `make setup` cài hook pre-commit (ruff format, ruff check, prettier, eslint) và hook pre-push (`make check`). *(yêu cầu người dùng; ADR-0006)* — *Kiểm chứng:* có file `.git/hooks/pre-commit` và `.git/hooks/pre-push`; commit thử một file sai format thì bị chặn; `git push` thử (hoặc `pre-commit run --hook-stage pre-push --all-files`) thì chạy `make check`.
- [x] **AC5.** Contract import-linter "`engine`/`schemas` không import `cv2`, `mediapipe`, `fastapi`, `sqlalchemy`, `httpx`" và các ranh giới ở R7 chạy trong `make check`. *(yêu cầu người dùng; overview.md §3)* — *Kiểm chứng:* `make lint-imports` xanh; thêm tạm `import fastapi` vào `postcare/engine/__init__.py` thì `make lint-imports` báo lỗi, rồi xóa.
- [x] **AC6.** `make gen-api-types` sinh `web/src/api/schema.d.ts` mà không cần chạy server. `make check` báo lỗi khi file này cũ so với OpenAPI. *(ADR-0005)* — *Kiểm chứng:* chạy `make gen-api-types` trên máy sạch; thêm tạm một endpoint mà không sinh lại type thì `make check` báo lỗi.

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
- *(giả định, planner 17/11/2026)* F00 xuất phát từ code prototype ([ADR-0010](../02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md)), **không viết lại**. Phần prototype vượt phạm vi F00 (SQLite, auth, nghiệp vụ, `seed`, `simulate`) được giữ nguyên; câu "F00 không có cơ sở dữ liệu" hiểu là F00 không thêm gì về DB.
- *(giả định)* Giữ CLI dạng package `postcare/cli/` (entry `postcare.cli.main:app`) thay cho `cli.py` ở R2; giữ thêm module `pipeline` theo overview.md §3.
- *(giả định)* R10 "trang gốc": khi chưa đăng nhập, `/` chuyển sang `/login`, nơi hiển thị `vi.app.name` ("PostCare AI") và `vi.app.tagline`. Dùng khóa có sẵn `app.name` thay cho `app.title` ở mục 4, không đổi tên khóa.
- *(giả định)* Contract import-linter theo bảng overview.md §3 (nguồn gốc), nên `domain` cũng không import `engine`.
- *(giả định)* Target `seed` và `simulate` của prototype được giữ; `db-upgrade`, `db-seed` là target giữ chỗ (F01) như R3, thông báo gợi ý dùng `make seed` trong lúc chờ.
- *(giả định)* Bước kiểm tra type API cũ (`check-api-types`) gồm hai phần: so sánh **nội dung JSON đã parse** của `web/src/api/openapi.json` với `app.openapi()` (không so văn bản, tránh lệch CRLF/LF trên Windows), và `openapi-typescript --check` cho `schema.d.ts`.
- *(giả định)* Hook pre-commit chỉ **kiểm tra** (`ruff format --check`, `prettier --check`), không tự sửa file, để hành vi giống `make check`.
- *(giả định)* Thêm test `server/tests/test_tooling.py` để giữ `scripts/dev.ps1` tương đương Makefile và để recipe Makefile không chứa cú pháp cấm ở R4 (tự động hóa ca âm tính AC1).
- *(giả định)* msw khởi động trong `web/src/test/setup.ts` với `onUnhandledRequest: 'error'`; test cũ dùng `mockFetch` vẫn giữ, không chuyển sang msw ở F00.

## 8. Câu hỏi mở

- Có thêm job `windows-latest` vào CI để kiểm chứng AC1 tự động không, hay chỉ kiểm tra tay trên Windows? Mặc định: chỉ kiểm tra tay. **Không chặn.** *(Đã chốt 17/11/2026: có job `windows-latest` chạy `scripts\dev.ps1 check`.)*
- Hook pre-push trên Windows cần `make` có trong `PATH` của Git Bash (Git for Windows chạy hook bằng bash của nó). Cần xác nhận khi chạy thật; nếu lỗi thì bổ sung vào dev-setup.md. **Không chặn.**
- tech-stack.md ghi CI "có service Postgres", nhưng R13 và mục 2 của spec này để service Postgres cho F01; test hiện chạy trên SQLite tạm (`server/tests/conftest.py`). Mặc định: F00 **không** thêm service Postgres, F01 thêm khi chuyển test sang `TEST_DATABASE_URL`. **Không chặn.**
- Có giữ alias `make build` (tên cũ của prototype) cạnh `build-web` không? Mặc định: bỏ `build`, sửa README và `dev.ps1`. **Không chặn.** *(Đã chốt 17/11/2026: giữ `build` làm alias của `build-web`.)*

## 9. Kế hoạch triển khai

> Lập ngày 17/11/2026 (planner). Điểm xuất phát là code prototype trên nhánh `feat/F00-project-skeleton`.

### 9.1. Hiện trạng: phần đã đạt (chỉ cần ghi bằng chứng, không làm lại)

| Yêu cầu / AC | Bằng chứng có sẵn |
|---|---|
| R1 | `server/.python-version` = `3.12`; `server/uv.lock`; `web/package-lock.json`; `web/package.json` `engines.node >=22`; máy dev Node 24 |
| R2 (phần lớn) | `server/src/postcare/{schemas,engine,vision,pipeline,worker,replay,eval,db,domain,api}/__init__.py`; `api/main.py`; CLI ở `cli/main.py` (xem giả định) |
| R8 (phần lớn) | `GET /api/v1/health` trong `server/src/postcare/api/main.py:87`; OpenAPI ở `/api/openapi.json`; `make dev-api` nghe `0.0.0.0:8000` |
| R10 | `web/vite.config.ts` (host `0.0.0.0`, cổng 5173, proxy `/api` có `ws`); `web/src/pages/Login/LoginPage.tsx:54-57` hiển thị `vi.app.name`, `vi.app.tagline`; cấu trúc `web/src/{api,realtime,i18n,pages,components,auth,utils}` |
| R11 (phần Vitest) | `web/vite.config.ts` `test.environment = 'jsdom'`; `web/src/test/setup.ts`; Testing Library trong `devDependencies` |
| R12 (phần sinh type) | `make gen-api-types` = `postcare openapi` (`server/src/postcare/cli/main.py:121`, gọi `create_app().openapi()`, không cần chạy server) + `openapi-typescript` |
| R16 | `server/pyproject.toml` `[tool.ruff] line-length = 100`; `web/tsconfig.json` `strict: true`; `web/eslint.config.js` `no-explicit-any: error` |
| `.gitignore` | đã có `web/dist/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/` |
| AC2 (một phần) | `server/tests/test_auth.py::test_health` (200 `{"status":"ok"}`) |
| AC3 (phần lớn) | pytest 40 test, vitest 25 test (`make check` xanh, session-log 17/11/2026); `web/src/i18n/vi.test.ts` quét từ cấm, chạy trong `npm run test` của `make check`; `format-check` chạy `ruff format --check` và `prettier --check` |

**Còn thiếu:** mypy, import-linter, pre-commit/pre-push hook, CI, msw, `config/engine.default.yaml`, `Procfile.dev` + honcho, các target `help`, `dev`, `worker`, `lint-imports`, `test-vision`, `build-web`, `check-api-types`, `db-upgrade`, `db-seed`, `models`; marker `vision`; lệnh `postcare version`; test `test_cli.py`, `test_unknown_path_returns_404`, `App.test.tsx`; kiểm tra type API cũ; `scripts/dev.ps1` theo kịp Makefile.

### 9.2. Các bước (mỗi bước một commit, test trước khi code)

1. **Công cụ Python.** `server/pyproject.toml`: thêm vào nhóm `dev` `mypy`, `import-linter`, `pre-commit`, `honcho`; `[tool.pytest.ini_options]` thêm `markers = ["vision: cần model MediaPipe và video thật"]` và `--strict-markers`; `[tool.mypy]` (`strict = true`, `mypy_path = "src"`, `packages = ["postcare.schemas", "postcare.engine"]`). Chạy `uv --directory server lock` rồi `sync`. *Kiểm chứng:* `uv --directory server run mypy --version`, `lint-imports --help`, `pre-commit --version`, `honcho --version`. Commit `chore(F00): add mypy, import-linter, pre-commit, honcho`.
2. **Health router và CLI `version` (test trước).** Tạo `server/tests/test_health.py` (`test_health_returns_ok`, `test_unknown_path_returns_404`; chuyển `test_health` khỏi `test_auth.py`) và `server/tests/test_cli.py` (`test_help_exits_zero`, `test_version_prints_package_version`, `test_unknown_command_fails`, dùng `typer.testing.CliRunner`). Sau đó tách endpoint sang `server/src/postcare/api/v1/health.py` (router, đăng ký trong `api/main.py`), thêm lệnh `version` vào `cli/main.py` (đọc `importlib.metadata.version("postcare")`). *Kiểm chứng:* `make test`.
3. **Marker vision.** `server/tests/vision/__init__.py`, `server/tests/vision/test_placeholder.py` (một test `@pytest.mark.vision` gọi `pytest.skip`, lý do "F11"), để `pytest -m vision` trả exit 0 thay vì 5. *Kiểm chứng:* `uv --directory server run pytest -m vision` exit 0 (1 skipped); `pytest -m "not vision"` vẫn 40+ passed.
4. **mypy strict.** Chạy `uv --directory server run mypy`; sửa kiểu trong `server/src/postcare/schemas/{enums,events}.py` nếu báo lỗi (chỉ sửa chú thích kiểu, không đổi hành vi). *Kiểm chứng:* mypy exit 0.
5. **import-linter.** Tạo `server/.importlinter`: `root_packages = postcare`, `include_external_packages = True`; các contract `forbidden`:
   - `engine-schemas-no-io`: `postcare.engine`, `postcare.schemas` ↛ `cv2`, `mediapipe`, `fastapi`, `sqlalchemy`, `httpx`;
   - `schemas-standalone`: `postcare.schemas` ↛ mọi `postcare.*` khác (liệt kê từng module, gồm `postcare.settings`, `postcare.cli`);
   - `engine-pure`: `postcare.engine` ↛ `postcare.vision`, `postcare.api`, `postcare.db`, `postcare.worker`, `postcare.pipeline`;
   - `vision-boundary`: `postcare.vision` ↛ `api`, `db`, `engine`;
   - `offline-no-api-db`: `postcare.pipeline`, `postcare.worker`, `postcare.replay`, `postcare.eval` ↛ `api`, `db`;
   - `db-boundary`: `postcare.db` ↛ `api`, `vision`, `engine`;
   - `domain-boundary`: `postcare.domain` ↛ `api`, `vision`, `engine`;
   - `api-boundary`: `postcare.api` ↛ `vision`, `engine`.
   Khảo sát import hiện tại (grep `from postcare`) cho thấy không có vi phạm. *Kiểm chứng:* `uv --directory server run lint-imports` xanh; thêm tạm `import fastapi` vào `engine/__init__.py` và `from postcare import db` vào `schemas/__init__.py` → báo lỗi, rồi hoàn tác.
6. **Kiểm tra type API cũ (test trước).** Trong `test_cli.py` thêm `test_openapi_check_passes_when_fresh`, `test_openapi_check_fails_when_stale` (file JSON tạm có endpoint thừa/thiếu → exit 1). Thêm cờ `--check` cho `postcare openapi` (so `json.loads(file)` với `app.openapi()`, exit 1 kèm thông báo "chạy make gen-api-types"); khi ghi dùng `newline="\n"`. `web/package.json` thêm script `check-api-types`: `openapi-typescript src/api/openapi.json -o src/api/schema.d.ts --check`. *Kiểm chứng:* chạy hai lệnh trên repo sạch → exit 0.
7. **Web: msw, test App, `.nvmrc`.** `npm --prefix web install -D msw@2`; tạo `web/src/test/msw.ts` (`setupServer()` không handler); `setup.ts` gọi `listen({ onUnhandledRequest: 'error' })`, `resetHandlers`, `close`. Tạo `web/src/App.test.tsx`: `App renders Vietnamese title` (render `App` trong MantineProvider + QueryClient + `MemoryRouter` ở `/`, chưa đăng nhập; kỳ vọng `vi.app.name` và `vi.app.tagline`, lấy từ `vi.ts`). Tạo `web/.nvmrc` (`24`). *Kiểm chứng:* `npm --prefix web run test` (26+ passed).
8. **Cấu hình engine.** Tạo `config/engine.default.yaml`, chép nguyên khối YAML ở event-engine.md §6, thêm dòng chú thích đầu file trỏ về event-engine.md. Không code nào đọc file. *Kiểm chứng:* so nội dung với khối trong doc.
9. **`Procfile.dev`.** Hai dòng `api: uv --directory server run uvicorn postcare.api.main:app --host 0.0.0.0 --port 8000 --reload` và `web: npm --prefix web run dev`. *Kiểm chứng:* `make dev` mở được 8000 và 5173 (thủ công, Windows).
10. **Makefile và `scripts/dev.ps1` (test trước).** Tạo `server/tests/test_tooling.py`:
    - `test_makefile_has_required_targets` (danh sách R3 + `check-api-types`, `seed`, `simulate`);
    - `test_dev_ps1_matches_makefile_targets` (so `.PHONY` của Makefile với `ValidateSet` của `dev.ps1`);
    - `test_makefile_recipes_are_portable` (ca âm tính R4: không có `rm `, `cp `, `mkdir -p`, `export `, `[ `, `$(shell`, dấu nháy đơn, ký tự ngoài ASCII trong recipe);
    - `test_placeholder_targets_exit_nonzero` (recipe `worker`, `db-upgrade`, `db-seed`, `models` có `exit 1`).
    Sau đó viết lại `Makefile`: biến `CAMERA ?=`; `help` (các dòng `@echo` ASCII, không dùng `<>|&()`); `setup` (`uv --directory server sync`, `npm --prefix web ci`, `uv --directory server run pre-commit install --hook-type pre-commit --hook-type pre-push`); `dev` (`uv --directory server run honcho -d .. -f ../Procfile.dev start` hoặc `uv run --project server honcho -f Procfile.dev start`, chọn cách chạy được cả hai OS); `typecheck` (`mypy` + `npm --prefix web run typecheck`); `lint-imports`; `test` (`pytest -m "not vision"` + vitest); `test-vision`; `build-web`; `check-api-types`; `check: format-check lint typecheck lint-imports check-api-types test build-web`; target giữ chỗ in thông báo ASCII rồi `exit 1`. Cập nhật `scripts/dev.ps1` cùng tập lệnh (giữ ASCII, `-Camera` cho `worker`). *Kiểm chứng:* `make help`, `make check` xanh; `make db-upgrade` exit khác 0; `scripts\dev.ps1 check` xanh.
11. **Git hook.** Tạo `.pre-commit-config.yaml`, chỉ `repo: local`, `language: system`:
    - stage `pre-commit`: `ruff format --check` và `ruff check` qua `uv run --project server …` (giữ cwd ở gốc để đường dẫn file đúng), `files: ^server/`; `prettier --check` qua `node web/node_modules/prettier/bin/prettier.cjs --ignore-path web/.prettierignore`, `eslint` qua `node web/node_modules/eslint/bin/eslint.js --config web/eslint.config.js`, `files: ^web/`;
    - stage `pre-push`: `id: make-check`, `entry: make check`, `pass_filenames: false`, `always_run: true`;
    - `default_install_hook_types: [pre-commit, pre-push]`.
    *Kiểm chứng:* `make setup` tạo `.git/hooks/pre-commit`, `.git/hooks/pre-push`; `uv --directory server run pre-commit run --all-files` xanh; `pre-commit run --hook-stage pre-push --all-files` chạy `make check`.
12. **CI.** `.github/workflows/ci.yml`: `on: [push, pull_request]`, job `check` trên `ubuntu-latest`: `actions/checkout`, `astral-sh/setup-uv` (cache theo `server/uv.lock`), `actions/setup-node` (`node-version-file: web/.nvmrc`, cache npm theo `web/package-lock.json`), `make setup`, `make check`. Không có service Postgres (câu hỏi mở 3). *Kiểm chứng:* push nhánh, `gh run watch` xanh.
13. **Tài liệu và kiểm chứng thủ công.** Cập nhật doc ở 9.4; chạy các bước thủ công của AC1–AC6 trên Windows và ghi kết quả vào mục 10. Commit `docs(F00): …`.

### 9.3. Test theo acceptance criteria

| AC | Test tự động | Kiểm chứng thủ công / ca âm tính |
|---|---|---|
| AC1 | Job `check` trong `ci.yml`; `test_tooling.py` (`test_makefile_recipes_are_portable`, `test_dev_ps1_matches_makefile_targets`) | Windows PowerShell: xóa `server/.venv` và `web/node_modules`, chạy `make setup` rồi `make check`, ghi thời gian và kết quả vào mục 10 |
| AC2 | `test_health.py::test_health_returns_ok`, `::test_unknown_path_returns_404`; `App.test.tsx`: `App renders Vietnamese title` | `make dev-api` + `curl http://localhost:8000/api/v1/health`; `make dev-web`, mở `http://localhost:5173` và từ máy khác trong LAN |
| AC3 | `test_cli.py` (`--help`, `version`, lệnh lạ → exit khác 0); `vi.test.ts` (đã có) | Thêm tạm một file `.py` và một file `.tsx` sai format → `make check` dừng ở `format-check`; chèn tạm "chẩn đoán" vào `vi.ts` → vitest fail; hoàn tác |
| AC4 | — | Có `.git/hooks/pre-commit` và `pre-push`; commit file sai format bị chặn, file đúng qua; `pre-commit run --hook-stage pre-push --all-files` chạy `make check`; thử `git push` thật trên Windows (Git Bash cần thấy `make`) |
| AC5 | `make lint-imports` trong `make check` | Thêm tạm import bị cấm vào `engine` và `schemas` → lỗi; hoàn tác |
| AC6 | `test_cli.py::test_openapi_check_passes_when_fresh`, `::test_openapi_check_fails_when_stale`; `check-api-types` trong `make check` | Thêm tạm một endpoint mà không chạy `make gen-api-types` → `make check` lỗi; chạy `make gen-api-types` → xanh; hoàn tác |

Không có migration, không thêm endpoint mới (chỉ chuyển `health` sang router), type API không đổi (chạy `make gen-api-types` sau bước 2 để xác nhận không có diff).

### 9.4. Doc cập nhật cùng PR

- `README.md`: bảng lệnh (`build` → `build-web`, thêm `dev`, `lint-imports`, `test-vision`, `check-api-types`, hook do `make setup` cài).
- `docs/04-guides/dev-setup.md` §3: bỏ chú thích "sau khi F00 hoàn thành"; ghi chú pre-push trên Windows cần `make` trong PATH của Git Bash; dòng sự cố "hook chặn commit".
- `docs/04-guides/testing.md` §4: đã chốt msw (bỏ "giả định chọn msw ở F00"); §1: test giữ chỗ marker `vision`.
- `docs/02-architecture/tech-stack.md`: cột "Phiên bản đã khóa" lấy từ `server/uv.lock` và `web/package-lock.json`.
- `docs/02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md` mục 4: ghi msw, import-linter, mypy, pre-commit, honcho đã có từ F00.
- `docs/03-features/README.md`: trạng thái F00.

### 9.5. Rủi ro

| Rủi ro | Cách xử lý |
|---|---|
| import-linter báo lỗi khi module ngoài bị cấm (`cv2`, `mediapipe`) chưa được cài | Kiểm tra ở bước 5; nếu lỗi, dùng tùy chọn bỏ qua module vắng mặt của import-linter hoặc tách contract ngoài; ghi lại cách xử lý vào mục 10 |
| `openapi-typescript --check` không có trong bản đã khóa, hoặc kết quả lệch do định dạng | Kiểm tra ở bước 6; dự phòng: script Node trong `web/` sinh ra chuỗi và so với file |
| Hook prettier/eslint chạy từ gốc repo không đọc `web/.prettierignore` / `eslint.config.js` (đã từng gặp ở phiên 16/11) | Truyền `--ignore-path` và `--config` tường minh; kiểm chứng bằng `pre-commit run --all-files` |
| Hook pre-push trên Windows không thấy `make` (Git Bash) | Kiểm thử tay ở AC4; ghi hướng dẫn PATH vào dev-setup.md |
| honcho chạy lệnh qua cmd trên Windows, `--reload` của uvicorn có thể không dừng sạch khi Ctrl+C | Chấp nhận; dev-setup.md đã có cách chạy 2 terminal |
| `npm ci` trên Ubuntu thiếu native binding (Rolldown) nếu lockfile sinh trên Windows | Đã gặp và xử lý ngày 16/11; CI là nơi kiểm chứng; nếu lỗi, sinh lại lockfile có đủ optional dependency |
| mypy strict báo lỗi ở `schemas` hiện có | Chỉ sửa chú thích kiểu; không đổi hành vi; test hiện có phải vẫn xanh |
| msw `onUnhandledRequest: 'error'` làm vỡ test cũ | Test cũ thay `globalThis.fetch` bằng `mockFetch`; nếu vẫn vỡ, chuyển sang `'warn'` và ghi lại |

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

### 10.1. Tiến độ các bước 9.2 (triển khai 17/11/2026, nhánh `feat/F00-project-skeleton`)

- [x] 1. Công cụ Python: mypy 2.4.1, import-linter 2.16, pre-commit 4.7.0, honcho 2.0.0, pyyaml 6.0.3 (nhóm dev), marker `vision` + `--strict-markers`, `[tool.mypy]` strict. Commit `chore(F00): add mypy, import-linter, pre-commit, honcho, pyyaml`.
- [x] 2. `postcare.api.v1.health` (router, đăng ký đầu tiên trong `create_app`), lệnh `postcare version`. `make gen-api-types` sau bước này: không có diff.
- [x] 3. `server/tests/vision/test_placeholder.py`: `pytest -m vision` → 1 skipped, exit 0.
- [x] 4. mypy strict `postcare.schemas`, `postcare.engine`: "Success: no issues found in 4 source files", không cần sửa code.
- [x] 5. `server/.importlinter`: 8 contract, "8 kept, 0 broken". Rủi ro 9.5 (module ngoài chưa cài như `cv2`, `mediapipe`) không xảy ra: import-linter 2.16 chấp nhận module bị cấm không có trong graph.
- [x] 6. `postcare openapi --check` (so JSON đã parse) + script `check-api-types` (`openapi-typescript --check`, có sẵn ở 7.13.0). Ghi file bằng `newline="\n"` (sửa lỗi CRLF trên Windows; test `test_openapi_writes_lf_newlines`).
- [x] 7. msw 2.15.0 (`web/src/test/msw.ts`, `setup.ts` với `onUnhandledRequest: 'error'`), `App.test.tsx`, `web/.nvmrc` = 24. Test cũ không vỡ: vitest 30 passed.
- [x] 8. `config/engine.default.yaml` chép nguyên khối event-engine.md §6 (test `test_engine_default_config_matches_doc_values`).
- [x] 9. `Procfile.dev` (`api`, `web`).
- [x] 10. Makefile + `scripts/dev.ps1` (cùng tập 23 target; giữ alias `build` → `build-web` theo quyết định của người dùng, nên câu hỏi mở 4 đổi thành "giữ"). `test_tooling.py` 29 passed.
- [x] 11. `.pre-commit-config.yaml` (chỉ `repo: local`; prettier thêm `--ignore-unknown`, eslint thêm `--no-warn-ignored` để không lỗi khi commit file không thuộc loại đó).
- [x] 12. `.github/workflows/ci.yml`: job `check` (ubuntu-latest, `make setup` + `make check`) và job `windows` (windows-latest, `scripts\dev.ps1 setup` + `scripts\dev.ps1 check`: lint, pytest, vitest và mọi bước khác; câu hỏi mở 1 chốt là **có** job Windows). Chưa push nên chưa có kết quả CI.
- [x] 13. Doc: README, dev-setup.md §3/§6, testing.md §1/§4, tech-stack.md (cột "Phiên bản đã khóa", hàng CI, Git hook), ADR-0010 mục 4.

### 10.2. Kiểm chứng thủ công (Windows 11, Git Bash + PowerShell 5.1, 17/11/2026)

- [ ] **AC1** — `make check` exit 0 (format-check, lint, mypy, lint-imports 8 kept, check-api-types, pytest 80 passed / 1 deselected, vitest 30 passed, build-web). `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check` exit 0. `make setup` trên máy dev lỗi ở `npm ci` với `EPERM unlink ...rolldown-binding.win32-x64-msvc.node` do một tiến trình `vite` (dev server đang chạy, không do phiên này mở) giữ file; `uv sync` và `pre-commit install` chạy được. **Còn thiếu:** chạy `make setup` trên máy sạch (đã dừng dev server) và job CI xanh sau khi push.
- [ ] **AC2** — `test_health_returns_ok`, `test_unknown_path_returns_404`, `App renders Vietnamese title` pass. Chạy uvicorn từ code hiện tại (cổng tạm 8011): `GET /api/v1/health` → 200 `{"status":"ok"}`, đường dẫn lạ → 404. Mở `http://localhost:5173` trong trình duyệt (browser pane của Claude Code): trang hiện "PostCare AI", dashboard Tổng quan tiếng Việt với thẻ A01–A03. **Còn thiếu:** mở từ máy khác trong LAN.
- [x] **AC3** — pytest và vitest đều có test pass. Thêm tạm `server/tests/tmp_bad_format.py` sai format → `make check` dừng ở `format-check` (ruff, exit 2); chỉ còn `web/src/tmpBadFormat.ts` sai format → `make check` dừng ở `format-check` (prettier). Chèn tạm "chẩn đoán" vào `vi.app.tagline` → `vi.test.ts` fail ("does not contain forbidden word"). Đã hoàn tác.
- [ ] **AC4** — `.git/hooks/pre-commit` và `.git/hooks/pre-push` có sau `pre-commit install --hook-type pre-commit --hook-type pre-push`. Commit thử hai file sai format bị chặn (ruff format và prettier Failed, exit 1); commit đúng format (`ci(F00): ...`) qua. `pre-commit run --hook-stage pre-push --all-files` chạy `make check` → Passed. `pre-commit run --all-files` → 4 hook Passed. **Còn thiếu:** `git push` thật (phiên này không được push); khi push từ terminal/IDE, `make`, `uv`, `node` phải có trong PATH người dùng (xem dev-setup.md §3).
- [x] **AC5** — `make lint-imports` xanh trong `make check`. Thêm tạm `import fastapi` vào `postcare/engine/__init__.py` và `from postcare import db` vào `postcare/schemas/__init__.py` → "6 kept, 2 broken" (`postcare.engine -> fastapi`, `postcare.schemas -> postcare.db`), exit 1. Đã hoàn tác.
- [x] **AC6** — `make gen-api-types` không cần server, chạy lại không tạo diff. Thêm tạm endpoint `/health/tmp` vào `api/v1/health.py` → `make check-api-types` exit khác 0 với thông báo "không khớp OpenAPI hiện tại. Chạy `make gen-api-types`"; sửa tay `schema.d.ts` → `npm run check-api-types` exit 1. Đã hoàn tác.

### 10.3. Thư viện mới (AGENTS.md quy tắc 12)

- `mypy`, `import-linter`, `pre-commit`, `honcho`: đã có lý do trong tech-stack.md; thêm vào nhóm dev.
- `pyyaml` (nhóm dev): `test_tooling.py` đọc `.pre-commit-config.yaml`, `ci.yml`, `config/engine.default.yaml`. Trước đó chỉ có gián tiếp qua `uvicorn[standard]`, không được khai báo. F10 chuyển sang phụ thuộc chính khi code đọc config.
- `msw` (devDependency web): R11, testing.md §4.
- `npm audit` báo 8 lỗ hổng (7 moderate, 1 high, ví dụ `undici`) trong cây devDependency; chưa xử lý ở F00.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
