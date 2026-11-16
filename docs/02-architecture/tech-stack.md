# Tech stack

Nguyên tắc chọn công nghệ:
- Phổ biến, nhiều tài liệu, AI viết đúng nhiều.
- Chạy được trên Windows và Linux.
- Không cần GPU.

Phiên bản chính xác được **khóa ở F00** bằng `server/uv.lock` và `web/package-lock.json`. Khi khóa xong, cập nhật cột "Phiên bản đã khóa".

## Backend và AI

| Thành phần | Chọn | Phiên bản mục tiêu | Phiên bản đã khóa | Lý do | Đã cân nhắc |
|---|---|---|---|---|---|
| Ngôn ngữ | Python | 3.12.x | — | MediaPipe có wheel cho Windows/Linux. Máy dev có sẵn 3.15 nhưng *(giả định)* MediaPipe chưa hỗ trợ, nên dùng uv cài riêng 3.12 | 3.11, 3.13 |
| Môi trường và phụ thuộc | uv | bản ổn định mới nhất | — | Nhanh, có lockfile, tự cài Python đúng phiên bản | pip+venv, Poetry |
| Pose / Face | mediapipe (Tasks API) | 0.10.x | — | Nguồn bắt buộc (PDF §6, HS §5.5). Chế độ VIDEO, `num_poses`, blendshapes | MMPose/RTMPose, Py-Feat (dự phòng, sau MVP) |
| Video | OpenCV qua `opencv-contrib-python` (kéo theo mediapipe) | 4.x | — | Đọc webcam, URL HTTP/RTSP, file (PDF bảng tr.10). **Không** cài thêm `opencv-python` (xung đột) | PyAV |
| Web framework | FastAPI + Uvicorn | FastAPI ≥ 0.115 | — | WebSocket và OpenAPI có sẵn; tích hợp Pydantic | Django + DRF, Flask |
| Validation | Pydantic v2 + pydantic-settings | 2.x | — | Dùng chung cho schema engine và API | dataclasses + marshmallow |
| ORM | SQLAlchemy | 2.0.x | — | Ổn định, phổ biến | SQLModel |
| Migration | Alembic | 1.x | — | Chuẩn đi cùng SQLAlchemy | — |
| Driver DB | psycopg | 3.x | — | Driver PostgreSQL chính thức thế hệ mới | psycopg2 |
| Database | PostgreSQL | 16 | — | Nguồn chọn (PDF §10, HS §6.1); JSONB, partial unique index, `timestamptz` | SQLite |
| Auth | PyJWT + pwdlib[bcrypt] | 2.x / 0.x | — | Giống hướng dẫn bảo mật của FastAPI | fastapi-users, session cookie |
| CLI | Typer | 0.x | — | Đơn giản, có type hint | click, argparse |
| HTTP client (worker) | httpx | 0.x | — | Sync + async, keep-alive | requests |
| Cấu hình engine | PyYAML | 6.x | — | File ngưỡng dễ đọc | TOML |
| Đo tài nguyên | psutil | 5.x+ | — | CPU/RAM cho báo cáo (HS §8.2) | — |
| Client WebSocket (đo delivery) | websockets | 12.x+ | — | Lệnh `measure-delivery` của F29 đo thời gian WS nhận sự kiện | httpx-ws |
| Chạy nhiều tiến trình dev | honcho | 2.x | — | Đọc `Procfile.dev`, chạy được trên Windows | 3 terminal riêng |
| Lint + format | ruff | 0.x | — | Một công cụ cho cả lint và format | black + flake8 + isort |
| Kiểm tra kiểu | mypy | 1.x | — | Strict cho `schemas` và `engine` (phần lõi) | pyright |
| Ranh giới module | import-linter | 2.x | — | Kiểm tra tự động [quy tắc import](overview.md#3-module-trong-serversrcpostcare) | review thủ công |
| Test | pytest | 8.x | — | Chuẩn | unittest |

## Frontend

| Thành phần | Chọn | Phiên bản mục tiêu | Phiên bản đã khóa | Lý do | Đã cân nhắc |
|---|---|---|---|---|---|
| Runtime | Node.js | 24 LTS *(giả định A13; nếu chưa là LTS thì dùng 22 LTS)* | — | LTS | — |
| Package manager | npm | đi kèm Node | — | Không cần cài thêm | pnpm, yarn |
| Framework | React | 19 | — | Phổ biến nhất | Vue, Svelte |
| Ngôn ngữ | TypeScript | 5.x | — | Type an toàn, AI viết đúng hơn | JS |
| Build | Vite | bản ổn định mới nhất | — | Nhanh, cấu hình ít | Next.js (không cần SSR), CRA (đã ngừng) |
| UI kit | Mantine (+ @mantine/notifications) | 8.x | — | Nhiều component sẵn, ít phải viết CSS | MUI, shadcn/ui + Tailwind |
| Server state | TanStack Query | 5.x | — | Cache, refetch, invalidation khi có WS | SWR, Redux |
| Routing | React Router | 7.x (declarative mode) | — | Chuẩn | TanStack Router |
| Type API | openapi-typescript | 7.x | — | Sinh type TS từ OpenAPI của FastAPI (`make gen-api-types`) | viết tay |
| Lint / format | ESLint 9 (flat config) + Prettier 3 | — | — | Chuẩn | Biome |
| Test | Vitest + Testing Library | — | — | Chung cấu hình với Vite | Jest |
| Mock API trong test | msw | 2.x | — | Mock fetch ở mức mạng, test gần thực tế (F00) | mock fetch thủ công |
| E2E | Playwright | 1.x | — | Chạy trên Windows/Linux, ổn định | Cypress |

## Công cụ chung (trung lập với AI)

| Thành phần | Chọn | Lý do | Đã cân nhắc |
|---|---|---|---|
| Task runner | GNU Make | Người dùng yêu cầu `make check`. Recipe chỉ gọi `uv run …` và `npm --prefix web …`, chạy được dưới cả cmd và sh | npm scripts, just |
| Git hook | pre-commit | Độc lập với AI tool. Hook pre-commit chạy format/lint; hook pre-push chạy `make check` | husky, lefthook |
| CI | GitHub Actions | Phổ biến; có service Postgres | GitLab CI |
| Nguồn camera điện thoại | DroidCam hoặc IP Webcam | HS §4.2 [7] | camera IP |

## Cài đặt

Xem [docs/04-guides/dev-setup.md](../04-guides/dev-setup.md).

## Kết quả đo hiệu năng

F11, F25 và F29 điền bảng này (HS §8.2: chứng minh chạy ổn định trên phần cứng được công bố).

| Ngày | Máy (CPU / RAM / GPU) | Nguồn | Độ phân giải | Model | Face bật? | FPS xử lý | CPU % | RAM MB | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — | chưa đo |
