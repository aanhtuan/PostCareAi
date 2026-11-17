# Tech stack

Nguyên tắc chọn công nghệ:
- Phổ biến, nhiều tài liệu, AI viết đúng nhiều.
- Chạy được trên Windows và Linux.
- Không cần GPU. GPU chỉ là phương án tăng tốc khi benchmark CPU không đạt (QA#35).

Phiên bản chính xác được **khóa ở F00** bằng `server/uv.lock` và `web/package-lock.json`. Khi khóa xong, cập nhật cột "Phiên bản đã khóa".

## Backend và AI

| Thành phần | Chọn | Phiên bản mục tiêu | Phiên bản đã khóa | Lý do | Đã cân nhắc |
|---|---|---|---|---|---|
| Ngôn ngữ | Python | 3.12.x | 3.12.16 (uv) | MediaPipe có wheel cho Windows/Linux. Máy dev có sẵn 3.15 nhưng *(giả định)* MediaPipe chưa hỗ trợ, nên dùng uv cài riêng 3.12 | 3.11, 3.13 |
| Môi trường và phụ thuộc | uv | bản ổn định mới nhất | 0.13.9 (máy dev; không khóa trong repo) | Nhanh, có lockfile, tự cài Python đúng phiên bản | pip+venv, Poetry |
| Pose / Face | mediapipe (Tasks API) | 0.10.x | — | Nguồn bắt buộc (PDF §6, HS §5.5). Chế độ VIDEO, `num_poses`, blendshapes. Biến thể pose (`lite` / `full` / `heavy`) chọn bằng benchmark trên máy dev (QA#35). MediaPipe Python trên Windows chỉ chạy CPU; GPU delegate chỉ có trên Linux/macOS (thử qua WSL2) | MMPose/RTMPose, Py-Feat (dự phòng, sau MVP) |
| Pose dự phòng (chỉ khi MediaPipe không đạt) | rtmlib + onnxruntime-gpu (CUDA) | — | — | RTMPose chạy được trên GPU NVIDIA dưới Windows; giấy phép Apache-2.0; chỉ viết adapter khi benchmark MediaPipe không đạt (QA#35, ADR-0003) | MoveNet (cần TensorFlow, không dùng), YOLO-pose (AGPL-3.0) |
| Video | OpenCV qua `opencv-contrib-python` (kéo theo mediapipe) | 4.x | opencv-contrib-python 4.14.0.94, numpy 2.5.5 (F05) | Đọc webcam, URL HTTP/RTSP, file (PDF bảng tr.10). F05 thêm thẳng vào `dependencies` vì Camera Service (`vision.camera`) cần trước khi có mediapipe (F11); chọn bản `contrib` vì mediapipe kéo theo đúng gói này. **Không** cài thêm `opencv-python` (xung đột) | PyAV |
| Web framework | FastAPI + Uvicorn | FastAPI ≥ 0.115 | fastapi 0.143.0, uvicorn 0.54.0 | WebSocket và OpenAPI có sẵn; tích hợp Pydantic | Django + DRF, Flask |
| Validation | Pydantic v2 + pydantic-settings | 2.x | pydantic 2.14.1, pydantic-settings 2.15.0 | Dùng chung cho schema engine và API | dataclasses + marshmallow |
| ORM | SQLAlchemy | 2.0.x | 2.0.54 | Ổn định, phổ biến | SQLModel |
| Migration | Alembic | 1.x | — | Chuẩn đi cùng SQLAlchemy | — |
| Driver DB | psycopg | 3.x | 3.3.6 (extra `postgres`) | Driver PostgreSQL chính thức thế hệ mới | psycopg2 |
| Database | PostgreSQL | 16 | — | Nguồn chọn (PDF §10, HS §6.1); JSONB, partial unique index, `timestamptz`. Trên máy dev chạy bằng Docker image `postgres:16` (QA#34) | SQLite (chỉ cho test nhanh và prototype, ADR-0010) |
| Auth | PyJWT + pwdlib[bcrypt] | 2.x / 0.x | pyjwt 2.15.1, pwdlib 0.3.1, bcrypt 5.0.0 | Giống hướng dẫn bảo mật của FastAPI | fastapi-users, session cookie |
| CLI | Typer | 0.x | 0.27.3 | Đơn giản, có type hint | click, argparse |
| HTTP client (worker) | httpx | 0.x | 0.28.1 | Sync + async, keep-alive | requests |
| Cấu hình engine | PyYAML | 6.x | 6.0.3 (F00: nhóm dev, cho test_tooling.py đọc YAML; F10 chuyển sang phụ thuộc chính khi đọc config) | File ngưỡng dễ đọc | TOML |
| Đo tài nguyên | psutil | 5.x+ | — | CPU/RAM cho báo cáo (HS §8.2) | — |
| Client WebSocket (đo delivery) | websockets | 12.x+ | — | Lệnh `measure-delivery` của F29 đo thời gian WS nhận sự kiện | httpx-ws |
| Chạy nhiều tiến trình dev | honcho | 2.x | 2.0.0 | Đọc `Procfile.dev`, chạy được trên Windows | 3 terminal riêng |
| Lint + format | ruff | 0.x | 0.17.0 | Một công cụ cho cả lint và format | black + flake8 + isort |
| Kiểm tra kiểu | mypy | 2.x | 2.4.1 | Strict cho `schemas` và `engine` (phần lõi) | pyright |
| Ranh giới module | import-linter | 2.x | 2.16 | Kiểm tra tự động [quy tắc import](overview.md#3-module-trong-serversrcpostcare) | review thủ công |
| Test | pytest | 8.x | 9.1.1 (bản mới nhất khi khóa; mục tiêu ghi 8.x) | Chuẩn | unittest |

## Frontend

| Thành phần | Chọn | Phiên bản mục tiêu | Phiên bản đã khóa | Lý do | Đã cân nhắc |
|---|---|---|---|---|---|
| Runtime | Node.js | 24 LTS *(giả định A13; nếu chưa là LTS thì dùng 22 LTS)* | `web/.nvmrc` = 24; `engines.node >=22` | LTS | — |
| Package manager | npm | đi kèm Node | đi kèm Node (máy dev 11.7.0) | Không cần cài thêm | pnpm, yarn |
| Framework | React | 19 | 19.3.0 | Phổ biến nhất | Vue, Svelte |
| Ngôn ngữ | TypeScript | 5.x | 5.9.3 | Type an toàn, AI viết đúng hơn | JS |
| Build | Vite | bản ổn định mới nhất | 8.3.4 | Nhanh, cấu hình ít | Next.js (không cần SSR), CRA (đã ngừng) |
| UI kit | Mantine (+ @mantine/notifications) | 8.x | 8.3.18 | Nhiều component sẵn, ít phải viết CSS | MUI, shadcn/ui + Tailwind |
| Server state | TanStack Query | 5.x | 5.104.2 | Cache, refetch, invalidation khi có WS | SWR, Redux |
| Routing | React Router | 7.x (declarative mode) | 7.18.4 | Chuẩn | TanStack Router |
| Type API | openapi-typescript | 7.x | 7.13.0 | Sinh type TS từ OpenAPI của FastAPI (`make gen-api-types`) | viết tay |
| Lint / format | ESLint 9 (flat config) + Prettier 3 | — | eslint 9.39.5, prettier 3.9.10 | Chuẩn | Biome |
| Test | Vitest + Testing Library | — | vitest 5.0.4, @testing-library/react 16.3.3, jsdom 30.1.2 | Chung cấu hình với Vite | Jest |
| Mock API trong test | msw | 2.x | 2.15.0 | Mock fetch ở mức mạng, test gần thực tế. Thêm ở F00 (devDependency; `web/src/test/msw.ts`) | mock fetch thủ công |
| E2E | Playwright | 1.x | — | Chạy trên Windows/Linux, ổn định | Cypress |

## Công cụ chung (trung lập với AI)

| Thành phần | Chọn | Lý do | Đã cân nhắc |
|---|---|---|---|
| Task runner | GNU Make | Người dùng yêu cầu `make check`. Recipe chỉ gọi `uv run …` và `npm --prefix web …`, chạy được dưới cả cmd và sh. `scripts/dev.ps1` giữ các lệnh tương đương cho máy Windows chưa có make | npm scripts, just |
| Container cho PostgreSQL | Docker (Docker Desktop trên Windows) | Chạy PostgreSQL 16 giống nhau trên mọi máy dev, không cần cài server (QA#34) | cài PostgreSQL native |
| GitHub CLI | gh | Tạo PR, xem CI từ dòng lệnh | giao diện web |
| Git hook | pre-commit (4.7.0, nhóm dev trong `server/uv.lock`) | Độc lập với AI tool. Hook pre-commit chạy format/lint (chỉ kiểm tra); hook pre-push chạy `make check`. Mọi hook là `repo: local`, dùng ruff/prettier/eslint đã khóa trong lockfile | husky, lefthook |
| CI | GitHub Actions | Phổ biến. F00: job Ubuntu (`make setup` + `make check`) và job Windows (`scripts/dev.ps1 setup` + `check`, AGENTS.md quy tắc 10). Service Postgres thêm ở F01 | GitLab CI |
| Nguồn camera điện thoại | DroidCam hoặc IP Webcam | HS §4.2 [7] | camera IP |

## Cài đặt

Xem [docs/04-guides/dev-setup.md](../04-guides/dev-setup.md).

## Kết quả đo hiệu năng

F11, F25 và F29 điền bảng này (HS §8.2: chứng minh chạy ổn định trên phần cứng được công bố).

| Ngày | Máy (CPU / RAM / GPU) | Nguồn | Độ phân giải | Model | Face bật? | FPS xử lý | CPU % | RAM MB | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | — | — | chưa đo |
