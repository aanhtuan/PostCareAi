# PostCare AI

Hệ thống AI hỗ trợ giám sát bệnh nhân hậu phẫu và phát hiện sớm sự kiện cần chú ý. Đây là prototype dự thi **DANANG AI4LIFE 2026**, bảng AI for Life.

> PostCare AI là công cụ **hỗ trợ quan sát**: nó không chẩn đoán và không thay thế quyết định chuyên môn của nhân viên y tế.

## Hệ thống làm gì

```text
Smartphone/webcam → MediaPipe Pose + Face (pretrained) → Event Detection Engine (theo thời gian)
→ cảnh báo realtime → nhân viên y tế tiếp nhận và xác nhận → timeline, bàn giao ca
```

- Theo dõi tư thế, vị trí quanh giường, mức vận động và một số tín hiệu khuôn mặt khi đủ rõ.
- Sinh sự kiện có mức ưu tiên: ngồi dậy, ở mép giường, rời giường, chuyển động bất thường…
- Dashboard tiếng Việt: Tổng quan, Theo dõi trực tiếp, Cảnh báo, Lịch sử, Bàn giao ca.
- Lưu metadata sự kiện, không lưu video. Có chế độ làm mờ và chỉ hiển thị skeleton.

## Trạng thái hiện tại: prototype đề xuất

Repo đã có một **code base chạy được** để trình bày các phần chính (ngoài roadmap F00–F30, xem [ADR-0010](docs/02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md)):

| Đã có | Chưa có (đang giả lập / để sau) |
|---|---|
| API FastAPI: đăng nhập JWT, phân quyền 4 vai trò, giường/camera/bệnh nhân, phiên theo dõi, sự kiện → cảnh báo, vòng đời cảnh báo + audit, timeline, bàn giao ca, WebSocket realtime | **Phần AI và camera:** MediaPipe, Event Detection Engine, worker đọc camera, MJPEG. Thay bằng lệnh giả lập `postcare simulate` gửi dữ liệu qua đúng API nội bộ mà worker thật sẽ dùng |
| Web React tiếng Việt: Tổng quan, Theo dõi trực tiếp (skeleton mô phỏng), Cảnh báo, Lịch sử theo dõi, Bàn giao ca, Quản lý giường | Màn hình Cấu hình camera / vẽ ROI, chế độ hiển thị, thêm/sửa danh mục trên UI |
| PostgreSQL 16 (Docker) + Alembic migration (F01), test trên DB `postcare_test` rollback mỗi test | E2E. Đã có từ F00: mypy, import-linter, pre-commit/pre-push hook, CI GitHub Actions, msw |
| Bộ giả lập CLI: rời giường, mất quan sát, chuyển động bất thường, tín hiệu khuôn mặt, đổi tư thế | Quyền xem của người nhà (F36), quản lý tài khoản (F35), khu vực/ca trực (F37), chuyển giường (F04) |

- Sự kiện do `postcare simulate` sinh ra **không** phải kết quả nhận diện AI và không phải bằng chứng chạy camera thật.
- Prototype **chưa** đạt đủ acceptance criteria của các spec. Mọi feature vẫn là Todo trong [ROADMAP](docs/progress/ROADMAP.md): có code không đồng nghĩa feature đã Done. Kết quả kiểm tra từng phiên ghi trong [session-log](docs/progress/session-log.md).
- Kế hoạch từ prototype tới demo bằng dữ liệu thật: [DEMO-PLAN](docs/progress/DEMO-PLAN.md). Nội dung trình bày và bằng chứng cần có: [pitch-and-evidence](docs/01-product/pitch-and-evidence.md). Nguồn video dùng cho phát triển: [datasets](docs/04-guides/datasets.md).

## 1. Yêu cầu cài đặt

| Công cụ | Phiên bản | Windows | Linux (Ubuntu) |
|---|---|---|---|
| Git | ≥ 2.40 | có sẵn / `winget install Git.Git` | `sudo apt install git` |
| uv (tự cài Python 3.12) | mới nhất | `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python | 3.12 (qua uv) | `uv python install 3.12` | `uv python install 3.12` |
| Node.js + npm | 24 LTS (≥ 22) | `winget install OpenJS.NodeJS.LTS`, hoặc bản zip (xem dưới) | nvm / NodeSource |
| GNU Make | tùy chọn | `winget install ezwinports.make` (không bắt buộc: dùng `scripts\dev.ps1`) | `sudo apt install make` |
| Docker (chạy PostgreSQL 16) | mới nhất | Docker Desktop | `sudo apt install docker.io` |

Máy có Python khác (ví dụ 3.15) không sao: uv dùng 3.12 theo `server/.python-version`.

**Cài Node.js khi không có winget (cách đã dùng trên Windows Server của nhóm):**

```powershell
# Tải bản zip LTS chính thức, kiểm tra SHA256, giải nén vào thư mục người dùng
$v = 'v24.21.0'
Invoke-WebRequest "https://nodejs.org/dist/$v/node-$v-win-x64.zip" -OutFile "$env:TEMP\node.zip"
# So sánh với https://nodejs.org/dist/$v/SHASUMS256.txt
Get-FileHash "$env:TEMP\node.zip" -Algorithm SHA256
Expand-Archive "$env:TEMP\node.zip" -DestinationPath "$env:USERPROFILE\.local\node"
# Thêm vào PATH của người dùng (mở terminal mới sau lệnh này)
[Environment]::SetEnvironmentVariable('Path', "$env:USERPROFILE\.local\node\node-$v-win-x64;" + [Environment]::GetEnvironmentVariable('Path','User'), 'User')
```

Sau khi cài uv/Node, **mở terminal mới** rồi kiểm tra: `uv --version`, `node --version`, `npm --version`.

> **Terminal báo `uv` / `npm` "is not recognized"?** Terminal (nhất là terminal trong VS Code) vẫn giữ PATH cũ. Có hai cách:
> - **Tạm thời**, chỉ cho terminal đang mở. Dán lệnh dưới vào mỗi terminal PowerShell mới mở:
>
>   ```powershell
>   $env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.local\node\node-v24.21.0-win-x64;$env:Path"
>   ```
>
> - **Lâu dài:** đóng **toàn bộ** VS Code (mọi cửa sổ) rồi mở lại. Terminal mới sẽ tự nhận PATH.
>
> Nếu cài Node phiên bản khác, sửa `v24.21.0` cho đúng thư mục trong `%USERPROFILE%\.local\node\`.

## 2. Thiết lập (một lần)

Chạy ở thư mục gốc repo. **Tạo `.env` trước khi chạy API:** `cp .env.example .env` (PowerShell: `Copy-Item .env.example .env`). API từ chối khởi động nếu `JWT_SECRET` hoặc `WORKER_TOKEN` còn là giá trị mặc định (`change-me…`) hoặc ngắn hơn 32 byte. Giá trị trong `.env.example` chỉ dùng cho dev; chạy demo trong LAN thì tạo giá trị mới bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Worker và giả lập đọc cùng file `.env` nên `WORKER_TOKEN` tự khớp. Các biến khác có giá trị mặc định.

| Việc | Có make | Không có make (PowerShell / bash) |
|---|---|---|
| Cài phụ thuộc và git hook | `make setup` | `uv --directory server sync`, `npm --prefix web ci`, rồi `uv --directory server run pre-commit install --hook-type pre-commit --hook-type pre-push` |
| Chạy PostgreSQL 16 (một lần) | xem [mục 4](#4-postgresql) | xem [mục 4](#4-postgresql) |
| Tạo/cập nhật bảng (migration) | `make db-upgrade` | `uv --directory server run alembic upgrade head` |
| Dữ liệu mẫu nền (chạy lại an toàn) | `make db-seed` | `uv --directory server run postcare seed` |
| Dữ liệu demo prototype (**xóa hết** rồi tạo lại) | `make seed` | `uv --directory server run postcare seed --reset` |

Windows có thể dùng script thay make: `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 <lệnh>` với `<lệnh>` là tên target bất kỳ của Makefile (`setup`, `dev`, `seed`, `dev-api`, `dev-web`, `simulate`, `test`, `lint`, `format`, `check`…). Danh sách đầy đủ: `make help`.

`make setup` cài hook **pre-commit** (ruff format/check, prettier, eslint: chỉ kiểm tra, không tự sửa) và **pre-push** (`make check`). Hook cần `uv`, `node` và (pre-push) `make` có trong PATH.

API không tự tạo bảng: chạy `make db-upgrade` sau khi tạo DB và sau mỗi lần pull có migration mới.

- `postcare seed` (`make db-seed`, F01) chỉ **thêm phần còn thiếu**: 4 tài khoản (`nurse`, `charge`, `doctor`, `admin`, mật khẩu `SEED_PASSWORD`, mặc định `postcare`), 3 ca trực, giường A01–A03 ("Khu hậu phẫu"), camera A01. Không sửa dữ liệu đã có.
- `postcare seed --reset` (`make seed`, prototype) **xóa toàn bộ bảng**, chạy lại migration, tạo dữ liệu nền và thêm dữ liệu demo: camera A02/A03, bệnh nhân BN-001…BN-005, phiên đang mở cho A01–A03, vài sự kiện quá khứ cho A02 (một cảnh báo đã tiếp nhận) và A03 (cảnh báo mới) để dashboard giống phác thảo HS Hình 3. Thêm `--no-history` để bỏ phiên và sự kiện. Nếu API đang chạy, khởi động lại API sau khi seed.

## 3. Chạy

`make dev` chạy API và web cùng lúc (honcho, `Procfile.dev`). Hoặc mở 3 terminal ở thư mục gốc:

| Terminal | Có make | Không có make |
|---|---|---|
| 1. API (cổng 8000) | `make dev-api` | `uv --directory server run uvicorn postcare.api.main:app --host 0.0.0.0 --port 8000 --reload` |
| 2. Web (cổng 5173) | `make dev-web` | `npm --prefix web run dev` |
| 3. Worker camera (F06) | `make worker CAMERA=1` | `uv --directory server run postcare worker --camera-id 1` |
| 3'. Hoặc giả lập (không cần camera/model) | `make simulate` | `uv --directory server run postcare simulate --bed A01` |

URL:

| Địa chỉ | Nội dung |
|---|---|
| http://localhost:5173 | Dashboard (Vite proxy `/api` và WebSocket sang `127.0.0.1:8000`) |
| `http://<ip-laptop>:5173` | Truy cập từ máy khác trong LAN (Vite nghe `0.0.0.0`; có thể cần mở cổng 5173 trên tường lửa) |
| http://127.0.0.1:8000/api/v1/health | Kiểm tra API: `{"status":"ok"}` |
| http://127.0.0.1:8000/api/docs | Swagger UI (OpenAPI tại `/api/openapi.json`) |

### Tài khoản mẫu

Mật khẩu chung là `SEED_PASSWORD` (mặc định **`postcare`**).

| Tên đăng nhập | Vai trò | Quyền |
|---|---|---|
| `nurse` | Điều dưỡng | Xem mọi màn hình, thao tác cảnh báo, mở/đóng phiên |
| `charge` | Phụ trách ca | Như điều dưỡng |
| `doctor` | Bác sĩ | **Chỉ xem**, không thấy nút thao tác (API trả 403) |
| `admin` | Quản trị | Toàn quyền |

### Kịch bản demo (HS §8.3, khoảng 1 phút)

1. `seed`, chạy API và web, đăng nhập `nurse` / `postcare`. Mở **Tổng quan** (A01 "Cần kiểm tra" vì chưa nhận trạng thái; A02 "Cần kiểm tra"; A03 "Cảnh báo mới"). Có thể mở **Theo dõi trực tiếp** giường A01 ở tab khác.
2. Terminal 3: `uv --directory server run postcare simulate --bed A01`. Giả lập gửi lần lượt: Nằm → ngồi dậy → mép giường (cảnh báo Cần chú ý) → đứng dậy → rời vùng giường (**cảnh báo Ưu tiên cao**, có thông báo nổi + âm thanh) → sau 10 giây quay lại giường → nằm.
3. Trên **Cảnh báo** hoặc khối "Sự kiện cần chú ý": bấm **[Đã tiếp nhận]**, rồi **[Bệnh nhân an toàn]** (kèm ghi chú) và **[Đã xử lý]**. Đăng nhập `charge` ở trình duyệt khác và bấm tiếp nhận lần nữa để thấy thông báo "Cảnh báo đã được tiếp nhận bởi …".
4. Mở **Lịch sử theo dõi** (giường A01, phiên đang mở): thấy đủ chuỗi "hh:mm:ss - Bệnh nhân ngồi dậy …", người tiếp nhận và kết quả. Mở **Bàn giao ca** để xem tổng hợp và in.
5. Sau khi giả lập dừng ~5 giây, camera A01 chuyển "Mất kết nối camera" (cảnh báo Cần chú ý, đúng A02). Dùng `--hold` để giữ heartbeat cho tới khi nhấn Ctrl+C.

### Chạy worker thật thay giả lập (F06)

Cần model pose (`make models`) và camera có **ROI giường** (F08 chưa có UI vẽ ROI: tạm đặt `cameras.roi_polygon` trong DB, ví dụ lấy từ `config/cameras/*.yaml`).

```bash
make worker CAMERA=1                        # nguồn trong cấu hình camera (webcam/URL/file)
make worker CAMERA=1 VIDEO=D:/clip.mp4      # phát file video như camera, theo nhịp thời gian thật
uv --directory server run postcare worker --camera-id 1 --model lite -v
```

Worker lấy cấu hình qua API nội bộ, gửi heartbeat mỗi 2 giây, trạng thái giường khi đổi, sự kiện của engine (chỉ khi giường có phiên mở) và khung JPEG ~5 fps (API chỉ giữ khung mới nhất trong RAM). API tạm sập thì worker thử lại, không thoát; Ctrl+C để dừng. Khung gửi đi là ảnh RAW (chưa làm mờ) cho tới F28: chỉ dùng với người tham gia mô phỏng đã đồng ý (F06 §8).

Tham số giả lập:

```bash
uv --directory server run postcare simulate --help
#   --bed A01            mã giường (giường phải có phiên theo dõi đang mở)
#   --scenario bed-exit  | observation-lost | abnormal-movement | face-attention | posture-change
#   --speed 2            nhanh gấp đôi       --away 10   số giây ở ngoài giường
#   --repeat 3 --gap 5   lặp kịch bản        --hold      giữ heartbeat sau khi xong
make simulate BED=A02 SCENARIO=abnormal-movement SPEED=2
```

## 4. PostgreSQL

Dự án dùng PostgreSQL 16 ([ADR-0004](docs/02-architecture/decisions/ADR-0004-postgresql.md)), chạy bằng Docker trên máy dev (QA#34). Mở Docker Desktop rồi chạy một lần:

```bash
docker run -d --name postcare-db -e POSTGRES_USER=postcare -e POSTGRES_PASSWORD=postcare \
  -e POSTGRES_DB=postcare -p 5432:5432 -v postcare-pgdata:/var/lib/postgresql/data postgres:16
docker exec postcare-db createdb -U postcare postcare_test
make db-upgrade && make db-seed     # hoặc make seed để có dữ liệu demo
```

Các lần sau: `docker start postcare-db`. Địa chỉ mặc định (đổi trong `.env`):

- `DATABASE_URL=postgresql+psycopg://postcare:postcare@localhost:5432/postcare` (API, CLI, migration);
- `TEST_DATABASE_URL=postgresql+psycopg://postcare:postcare@localhost:5432/postcare_test` (pytest; tên DB phải kết thúc bằng `_test`).

Test tự chạy `alembic upgrade head` trên DB test và rollback sau mỗi test. Không kết nối được DB test thì test **lỗi** (không skip). Chi tiết: [dev-setup.md](docs/04-guides/dev-setup.md) mục 4.

## 5. Test, lint, format

| Việc | Có make | Không có make |
|---|---|---|
| Test (pytest + Vitest) | `make test` | `uv --directory server run pytest -m "not vision"` và `npm --prefix web run test` |
| Test cần model + video | `make test-vision` | `uv --directory server run pytest -m vision` |
| Lint (ruff + ESLint) | `make lint` | `uv --directory server run ruff check .` và `npm --prefix web run lint` |
| Format | `make format` | `uv --directory server run ruff format .` và `npm --prefix web run format` |
| Kiểm tra kiểu (mypy strict cho `schemas`, `engine`; tsc) | `make typecheck` | `uv --directory server run mypy` và `npm --prefix web run typecheck` |
| Ranh giới module (import-linter) | `make lint-imports` | `uv --directory server run lint-imports` |
| Type API còn khớp OpenAPI | `make check-api-types` | `uv --directory server run postcare openapi --out ../web/src/api/openapi.json --check` và `npm --prefix web run check-api-types` |
| Build web | `make build-web` (alias `make build`) | `npm --prefix web run build` |
| **Tất cả (bắt buộc xanh)** | `make check` | `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 check` |
| Sinh lại type TS từ OpenAPI | `make gen-api-types` | `uv --directory server run postcare openapi --out ../web/src/api/openapi.json` rồi `npm --prefix web run gen-api-types` |

## 6. Cấu trúc thư mục

```text
AGENTS.md  CLAUDE.md  README.md  Makefile  .env.example  Procfile.dev  .pre-commit-config.yaml
.github/workflows/ci.yml       CI: make check (Ubuntu), dev.ps1 check (Windows)
config/engine.default.yaml     Ngưỡng mặc định của engine (event-engine.md §6)
scripts/dev.ps1                Lệnh tương đương Makefile cho Windows
server/                        Python 3.12 (uv), package `postcare`
  src/postcare/
    schemas/                   Enum, catalog sự kiện (nguồn sự thật cho mã/mức ưu tiên)
    db/                        SQLAlchemy model, kiểu UTC, engine/session, migrations/ (Alembic)
    domain/                    Nghiệp vụ: phiên, sự kiện→cảnh báo, vòng đời, audit,
                               overview, timeline, handover, ca trực, seed, kho RAM
    api/                       FastAPI: v1/ (REST), internal/ (worker), realtime.py (WS), deps, errors
    cli/                       Typer: `postcare version | seed | simulate | worker | probe | replay | eval | models | openapi`
    engine/ vision/ pipeline/  Engine thuần, camera + pose MediaPipe, pipeline dùng chung worker/replay
    worker/                    Worker realtime một camera (F06): config, heartbeat, state, sự kiện, khung JPEG
    replay/ eval/              Replay offline (F12), đánh giá (F16)
  tests/                       pytest (DB PostgreSQL postcare_test, rollback mỗi test)
web/                           React 19 + TypeScript + Vite + Mantine 8
  src/api/                     client fetch, hook TanStack Query, schema.d.ts (sinh từ OpenAPI)
  src/realtime/                WebSocket client, cập nhật cache, âm thanh cảnh báo
  src/i18n/vi.ts               Toàn bộ text tiếng Việt (+ test từ cấm)
  src/pages/                   Login, Overview, LiveView, Alerts, Timeline, Handover, Management
  src/components/ auth/ utils/
docs/                          Tài liệu sản phẩm, kiến trúc, spec, tiến độ
```

## 7. Xử lý sự cố thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `uv` / `node` / `npm` báo "is not recognized" | Terminal còn giữ PATH cũ. Tạm thời: dán `$env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.local\node\node-v24.21.0-win-x64;$env:Path"` vào terminal PowerShell (mỗi terminal mới đều phải dán lại). Lâu dài: đóng **toàn bộ** VS Code rồi mở lại. Xem thêm [mục 1](#1-yêu-cầu-cài-đặt) |
| `npm.ps1 cannot be loaded because running scripts is disabled` | Dùng `npm.cmd …`, hoặc chạy lệnh qua `powershell -ExecutionPolicy Bypass -File scripts\dev.ps1 …` |
| `make` không có trên Windows | Dùng cột "Không có make" hoặc `scripts\dev.ps1` |
| Commit bị hook chặn (`ruff format --check`, `prettier --check`…) | Chạy `make format` (hoặc `scripts\dev.ps1 format`), `git add` lại rồi commit. Không dùng `--no-verify` |
| Web báo "Mất kết nối cập nhật trực tiếp" / lỗi tải dữ liệu | API chưa chạy ở cổng 8000. Kiểm tra http://127.0.0.1:8000/api/v1/health |
| Giả lập báo "Giường A01 chưa có phiên theo dõi" | Mở phiên ở **Quản lý giường** ("Bắt đầu theo dõi") hoặc chạy lại `seed` |
| Giả lập báo không kết nối được API / 401 | API chưa chạy, hoặc `WORKER_TOKEN` của API và giả lập khác nhau (cùng đọc `.env` ở thư mục gốc) |
| Cổng 8000 hoặc 5173 bị chiếm | Dừng tiến trình cũ, hoặc đổi cổng: `--port 8001` cho API và đặt `VITE_API_TARGET=http://127.0.0.1:8001` trước khi chạy web |
| API / test báo không kết nối được PostgreSQL | `docker start postcare-db` (Docker Desktop phải đang chạy); kiểm tra `DATABASE_URL` / `TEST_DATABASE_URL` |
| API báo lỗi `relation "..." does not exist` | Chưa chạy migration: `make db-upgrade` |
| Không nghe âm thanh cảnh báo | Trình duyệt chặn tự phát âm thanh cho tới khi bạn bấm vào trang ít nhất một lần |
| Tiếng Việt bị lỗi font trong terminal Windows | Lệnh `postcare` tự in UTF-8; dùng Windows Terminal hoặc `chcp 65001` |
| Gửi JSON có tiếng Việt bằng `curl` trên Git Bash bị 400 | Do mã hóa dòng lệnh; dùng UI, Swagger (`/api/docs`) hoặc file JSON UTF-8 với `--data-binary @file.json` |
| Máy khác trong LAN không mở được | Mở cổng 5173 trên Windows Defender Firewall; dùng IP mà Vite in ra ở dòng `Network:` |

## Tài liệu

| Bạn là | Đọc |
|---|---|
| Thành viên nhóm / người mới | [PRD](docs/01-product/PRD.md) → [overview](docs/02-architecture/overview.md) → [dev-setup](docs/04-guides/dev-setup.md) |
| AI agent | [AGENTS.md](AGENTS.md) (bắt buộc) |
| Người lắp camera / quay dữ liệu | [camera-setup](docs/04-guides/camera-setup.md), [evaluation](docs/04-guides/evaluation.md) |

- Đề tài gốc: [docs/00-source/](docs/00-source/) · Sản phẩm: [docs/01-product/](docs/01-product/) · Kiến trúc: [docs/02-architecture/](docs/02-architecture/)
- Feature: [docs/03-features/](docs/03-features/) · Hướng dẫn: [docs/04-guides/](docs/04-guides/) · Quy trình AI: [docs/ai/](docs/ai/) · Tiến độ: [docs/progress/](docs/progress/)

## Giới hạn

Prototype dùng dữ liệu mô phỏng có sự đồng ý của người tham gia; bản đề xuất hiện tại **chưa có phần AI** (dữ liệu do bộ giả lập sinh ra). Prototype **chưa** đủ điều kiện triển khai lâm sàng. Triển khai thực tế phải đánh giá pháp lý (Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15), bảo mật, quy trình bệnh viện và kiểm chứng với chuyên gia y tế.
