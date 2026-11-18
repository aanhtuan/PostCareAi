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
| Pose / Face | mediapipe (Tasks API) | 1.x (`>=1.2.3,<2`) | 1.2.3 (F11; bản mới nhất có wheel cp312 Windows/Linux khi khóa, Tasks API `PoseLandmarker` giống 0.10.x; kéo theo opencv-contrib-python 4.14.0.94, numpy 2.5.5, matplotlib, sounddevice). Model `.task` khóa theo URL `.../float16/1/...` + sha256 trong `config/models.yaml`; biến thể mặc định `full` theo benchmark bên dưới | Nguồn bắt buộc (PDF §6, HS §5.5). Chế độ VIDEO, `num_poses`, blendshapes. Biến thể pose (`lite` / `full` / `heavy`) chọn bằng benchmark trên máy dev (QA#35). MediaPipe Python trên Windows chỉ chạy CPU; GPU delegate chỉ có trên Linux/macOS (thử qua WSL2) | MMPose/RTMPose, Py-Feat (dự phòng, sau MVP) |
| Pose dự phòng (chỉ khi MediaPipe không đạt) | rtmlib + onnxruntime-gpu (CUDA) | — | — | RTMPose chạy được trên GPU NVIDIA dưới Windows; giấy phép Apache-2.0; chỉ viết adapter khi benchmark MediaPipe không đạt (QA#35, ADR-0003) | MoveNet (cần TensorFlow, không dùng), YOLO-pose (AGPL-3.0) |
| Video | OpenCV qua `opencv-contrib-python` (kéo theo mediapipe) | 4.x | opencv-contrib-python 4.14.0.94, numpy 2.5.5 (F05) | Đọc webcam, URL HTTP/RTSP, file (PDF bảng tr.10). F05 thêm thẳng vào `dependencies` vì Camera Service (`vision.camera`) cần trước khi có mediapipe (F11); chọn bản `contrib` vì mediapipe kéo theo đúng gói này. **Không** cài thêm `opencv-python` (xung đột) | PyAV |
| Web framework | FastAPI + Uvicorn | FastAPI ≥ 0.115 | fastapi 0.143.0, uvicorn 0.54.0 | WebSocket và OpenAPI có sẵn; tích hợp Pydantic | Django + DRF, Flask |
| Validation | Pydantic v2 + pydantic-settings | 2.x | pydantic 2.14.1, pydantic-settings 2.15.0 | Dùng chung cho schema engine và API | dataclasses + marshmallow |
| ORM | SQLAlchemy | 2.0.x | 2.0.54 | Ổn định, phổ biến | SQLModel |
| Migration | Alembic | 1.x | 1.20.1 (F01; `server/alembic.ini`, `db/migrations/`) | Chuẩn đi cùng SQLAlchemy | — |
| Driver DB | psycopg | 3.x | 3.3.6 (`psycopg[binary]`, phụ thuộc chính từ F01) | Driver PostgreSQL chính thức thế hệ mới | psycopg2 |
| Database | PostgreSQL | 16 | image `postgres:16` (máy dev, CI Ubuntu); CI Windows dùng bản PostgreSQL cài sẵn trên runner | Nguồn chọn (PDF §10, HS §6.1); JSONB, partial unique index, `timestamptz`. Trên máy dev chạy bằng Docker image `postgres:16` (QA#34) | SQLite (đã bỏ ở F01; trước đó dùng cho prototype, ADR-0010) |
| Auth | PyJWT + pwdlib[bcrypt] | 2.x / 0.x | pyjwt 2.15.1, pwdlib 0.3.1, bcrypt 5.0.0 | Giống hướng dẫn bảo mật của FastAPI | fastapi-users, session cookie |
| CLI | Typer | 0.x | 0.27.3 | Đơn giản, có type hint | click, argparse |
| HTTP client (worker) | httpx | 0.x | 0.28.1 | Sync + async, keep-alive | requests |
| Cấu hình engine | PyYAML | 6.x | 6.0.3 (phụ thuộc chính từ F10: `postcare.schemas.engine_config` đọc `config/engine.default.yaml` và `config/cameras/*.yaml`; không thêm `types-PyYAML`, mypy bỏ qua stub thiếu cho `yaml`) | File ngưỡng dễ đọc | TOML |
| Đo tài nguyên | psutil | 5.x+ | 7.2.2 (F11: `postcare probe --pose` đo CPU %, RAM MB) | CPU/RAM cho báo cáo (HS §8.2) | — |
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
| CI | GitHub Actions | Phổ biến. F00: job Ubuntu (`make setup` + `make check`) và job Windows (`scripts/dev.ps1 setup` + `check`, AGENTS.md quy tắc 10). F01: service `postgres:16` cho job Ubuntu, PostgreSQL cài sẵn cho job Windows, biến `TEST_DATABASE_URL` | GitLab CI |
| Nguồn camera điện thoại | DroidCam hoặc IP Webcam | HS §4.2 [7] | camera IP |

## Cài đặt

Xem [docs/04-guides/dev-setup.md](../04-guides/dev-setup.md).

## Kết quả đo hiệu năng

F11, F25, F29 và F31 (mục con bên dưới) điền bảng này (HS §8.2: chứng minh chạy ổn định trên phần cứng được công bố).

| Ngày | Máy (CPU / RAM / GPU) | Nguồn | Độ phân giải | Model | Face bật? | FPS xử lý | CPU % | RAM MB | Ghi chú |
|---|---|---|---|---|---|---|---|---|---|
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-8090730 (rời giường)` | 1280×720 | lite | không | 33.6 | 135 / 17 | 274 | F11; khung có người 32 %, đủ 4 keypoint thân 28 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-8090730 (rời giường)` | 1280×720 | full | không | 26.7 | 121 / 15 | 284 | F11; khung có người 26 %, đủ 4 keypoint thân 25 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-8090730 (rời giường)` | 1280×720 | heavy | không | 12.8 | 110 / 14 | 348 | F11; khung có người 56 %, đủ 4 keypoint thân 51 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-6130032 (giường bệnh)` | 1280×720 | lite | không | 28.8 | 130 / 16 | 275 | F11; khung có người 100 %, đủ 4 keypoint thân 72 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-6130032 (giường bệnh)` | 1280×720 | full | không | 16.1 | 105 / 13 | 286 | F11; khung có người 100 %, đủ 4 keypoint thân 49 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-6130032 (giường bệnh)` | 1280×720 | heavy | không | **9.1** | 108 / 13 | 350 | F11; khung có người 100 %, đủ 4 keypoint thân 17 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/mixkit/mixkit-5457 (nằm giường)` | 1280×720 | lite | không | 26.7 | 116 / 15 | 268 | F11; khung có người 100 %, đủ 4 keypoint thân 100 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/mixkit/mixkit-5457 (nằm giường)` | 1280×720 | full | không | 26.1 | 120 / 15 | 278 | F11; khung có người 100 %, đủ 4 keypoint thân 100 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/mixkit/mixkit-5457 (nằm giường)` | 1280×720 | heavy | không | 12.2 | 111 / 14 | 345 | F11; khung có người 100 %, đủ 4 keypoint thân 100 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/gmdcsa24 Subject 1/Fall/01` | 1280×720 | lite | không | 30.6 | 125 / 16 | 264 | F11; khung có người 65 %, đủ 4 keypoint thân 65 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/gmdcsa24 Subject 1/Fall/01` | 1280×720 | full | không | 27.9 | 135 / 17 | 274 | F11; khung có người 72 %, đủ 4 keypoint thân 72 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/gmdcsa24 Subject 1/Fall/01` | 1280×720 | heavy | không | 13.7 | 115 / 14 | 340 | F11; khung có người 73 %, đủ 4 keypoint thân 73 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/gmdcsa24 Subject 1/ADL/06` | 1280×720 | lite | không | 28.2 | 125 / 16 | 265 | F11; khung có người 79 %, đủ 4 keypoint thân 79 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/gmdcsa24 Subject 1/ADL/06` | 1280×720 | full | không | 21.0 | 126 / 16 | 275 | F11; khung có người 100 %, đủ 4 keypoint thân 100 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/gmdcsa24 Subject 1/ADL/06` | 1280×720 | heavy | không | 10.5 | 112 / 14 | 339 | F11; khung có người 100 %, đủ 4 keypoint thân 100 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/caucafall/Subject1/FallSitting` | 720×480 | lite | không | 32.2 | 106 / 13 | 235 | F11; khung có người 99 %, đủ 4 keypoint thân 99 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/caucafall/Subject1/FallSitting` | 720×480 | full | không | 21.5 | 96 / 12 | 247 | F11; khung có người 96 %, đủ 4 keypoint thân 96 % |
| 2026-11-17 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/caucafall/Subject1/FallSitting` | 720×480 | heavy | không | 11.4 | 100 / 13 | 311 | F11; khung có người 100 %, đủ 4 keypoint thân 100 % |
| 2026-11-18 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-6130032 (giường bệnh)` | 1280×720 | full + face | **có** | 18.8 | 121 / 15 | 318 | F25; 137 khung chạy face: OK 97, NOT_VISIBLE 40; 0 lỗi face |
| 2026-11-18 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-6130032 (giường bệnh)` | 1280×720 | full | không | 22.3 | 126 / 16 | 287 | F25 (cùng video, so sánh) |
| 2026-11-18 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-3753707 (rời giường)` | 1280×720 | full + face | **có** | 22.6 | 132 / 17 | 314 | F25; 322 khung chạy face: OK 236, NOT_VISIBLE 84, LOW_CONFIDENCE 2 |
| 2026-11-18 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-3753707 (rời giường)` | 1280×720 | full | không | 26.7 | 132 / 17 | 284 | F25 (cùng video, so sánh) |
| 2026-11-18 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-6010961 (giường bệnh)` | 1280×720 | full + face | **có** | 23.6 | 132 / 17 | 311 | F25; 203 khung chạy face: OK 174, NOT_VISIBLE 29 |
| 2026-11-18 | i5-10300H (4 nhân / 8 luồng) / 16 GB / không dùng GPU | `data/external/pexels/pexels-6010961 (giường bệnh)` | 1280×720 | full | không | 21.6 | 119 / 15 | 284 | F25 (cùng video; lần này chậm hơn lần bật face do máy đang chạy việc khác song song: nhiễu đo) |

Cách đo (F25, AC4): `uv run postcare replay --video <clip> --camera-config <cam.yaml> --out <dir> --max-fps 30` trong `server/`, hai lần cho mỗi clip: cấu hình camera có `thresholds: {face: {enabled: false}}` và không có. ROI cả khung, `face.run_every_n_frames = 2`, `face.head_crop_scale = 2.2`. FPS đọc từ `run.json`, phân bố `face.status` từ `observations.jsonl`. Face làm chậm khoảng 15 % (18.8 so với 22.3, 22.6 so với 26.7 FPS), RAM thêm ~30 MB; vẫn ≥ 10 FPS (A07). `events.jsonl` (bỏ `config_hash`) và `frames.jsonl` giống hệt giữa hai lần. Máy dùng chung với tác vụ khác trong lúc đo, nên sai số vài FPS.

Cách đo (F11, AC4): `uv run postcare probe --source <clip> --pose --model <lite|full|heavy> --max-fps 30 --seconds 120` trong `server/`, chạy hết clip, mỗi lần một tiến trình, máy cắm sạc, MediaPipe 1.2.3 chạy CPU (XNNPACK). Clip đọc theo đường dẫn tuyệt đối từ `data/external/` (datasets.md), không chép vào repo.
- **FPS xử lý** = số khung đã chạy pose / thời gian đồng hồ, gồm cả giải mã video, chưa có engine và face. Thời gian suy luận thuần: lite 27–35 ms, full 33–59 ms, heavy 70–107 ms mỗi khung.
- **CPU %** ghi "% tiến trình (100 % = một luồng) / % tổng máy (8 luồng)", lấy trung bình cả lượt chạy bằng psutil. **RAM MB** là RSS đỉnh của tiến trình.
- "Khung có người" = khung có ít nhất một `PersonPose`. "Đủ 4 keypoint thân" = có người thấy cả `pose.required_keypoints` (vai, hông) với visibility ≥ `pose.min_keypoint_visibility` (0.5). Đây chỉ là độ đầy đủ landmark, chưa phải độ chính xác so với nhãn.
- Lúc đo, một builder khác cũng đang chạy test trên máy, nên số FPS có thể thấp hơn khi máy rảnh.

**Kết luận (QA#35, A07):** biến thể mặc định là **`full`** (`pose.default` trong `config/models.yaml`). `heavy` chính xác nhất về lý thuyết nhưng không đạt ổn định ≥ 10 FPS ở 720p (9.1 FPS trên `pexels-6130032`, trung bình khoảng 11.7 FPS trên 5 clip 720p). Chưa tính engine, face (F25) và chạy hai worker cùng lúc (QA#32), nên heavy không còn dư địa. `full` đạt 16–28 FPS trên mọi clip 720p. `full` thấy người nhiều hơn hoặc bằng `lite` ở 4/5 clip 720p, `lite` chỉ là phương án giảm tải. Trên các clip đã đo, heavy không tốt hơn đồng đều: hơn rõ ở `pexels-8090730` (người ra khỏi khung một phần), kém về độ đủ keypoint thân ở `pexels-6130032`. Cả ba biến thể đều đạt ≥ 10 FPS trên CPU ở hầu hết clip, nên chưa cần GPU qua WSL2 hay RTMPose.

### Nhiều worker đồng thời (F31, R3)

Đo 2026-11-18 trên i5-10300H (4 nhân / 8 luồng) / 16 GB, không GPU, model pose `full`, `WORKER_MAX_FPS` = 15 (A03), API dev cổng 8031 + PostgreSQL Docker trên cùng máy. Webcam = camera tích hợp 640×480; clip = `pexels-3753707` (rời giường, 1280×720), `pexels-6944081`, `pexels-8860232` (1366×720), phát bằng `--video` theo nhịp thời gian thực.

| Số worker | Nguồn (camera → nguồn) | Face | FPS xử lý mỗi worker (trung vị) | CPU % mỗi worker | CPU tổng máy % | RAM MB mỗi worker | Độ trễ ghi sự kiện ms (trung vị / max) |
|---|---|---|---|---|---|---|---|
| 1 | A02 → clip 720p | tắt | 14.9 | 96 | 36 | 302 | 47 / 53 |
| 1 | A02 → clip 720p | bật | 14.9 | 105 | 37 | 329 | 44 / 46 |
| 1 | A01 → webcam | tắt | 15.0 | 38 | 29 | 263 | 47 |
| 1 | A01 → webcam | bật | 15.0 | 32 | 29 | 288 | 24 |
| 2 | A01 → webcam, A02 → clip 720p | tắt | 15.0 / 14.9 | 37 / 110 | 43 | 263 / 301 | 21 / 47–52 |
| 2 | A01 → webcam, A02 → clip 720p | bật | 14.8 / 15.1 | 37 / 117 | 46 | 289 / 330 | 87 / 52–55 |
| 2 | A01 → clip 720p, A02 → clip 720p | bật | 14.8 / 14.9 | 112 / 120 | 56 | 331 / 329 | 95 / 103–135 |
| 3 | webcam + 2 clip 720p | bật | 15.1 / 14.9 / 14.8 | 50 / 123 / 107 | 68 | 288 / 329 / 331 | 42 / 81–103 / — |

Cách đo: script ngoài repo khởi động mỗi worker bằng `python -m postcare worker --camera-id N [--video …]` (cùng lệnh `postcare workers` dùng), chờ 6 s cho model và nguồn, rồi lấy mẫu mỗi giây trong 14 s:
- **FPS xử lý** = `fps` trong heartbeat (`GET /api/v1/cameras/{id}` → `runtime.fps`): số khung worker đọc và xử lý (pose + engine + face) mỗi giây, bị chặn trên bởi `WORKER_MAX_FPS` = 15. Mọi cấu hình đều giữ được trần 15 FPS, nên dư địa đọc ở cột CPU.
- **CPU %** của worker gồm cả tiến trình con (trên Windows `python.exe` của venv là trampoline chạy tiến trình Python thật), 100 % = một luồng. **CPU tổng máy** = psutil toàn máy (8 luồng), gồm cả API, PostgreSQL và tác vụ khác đang chạy trên máy. **RAM** = RSS lớn nhất.
- **Độ trễ ghi sự kiện** = `events.created_at − detected_at` của sự kiện engine trong lượt đo (`detected_at` là thời điểm của khung đã quy đổi UTC): gồm cả trễ xử lý so với thời gian thật, gửi HTTP và commit DB. Mỗi lượt chỉ 1–2 sự kiện mỗi camera, nên đây là số chỉ dẫn, không phải phân bố.
- Webcam lúc đo không có người trong ROI giường (sự kiện duy nhất là `OBSERVATION_LOST`), nên pose/face trên webcam nhẹ hơn khi có bệnh nhân thật. Khi có người, nên ước lượng như một clip 720p (~110–120 % CPU).

**Kết luận (QA#32):** một camera trực tiếp + một clip 720p chạy đồng thời ổn định: cả hai worker giữ 15 FPS (trần A03), máy dùng khoảng 45 % CPU, mỗi worker ~0.3 GB RAM, sự kiện ghi vào DB trong vòng ~0.1 s. Hai clip 720p có face (tải gần với hai camera có người) vẫn giữ 15 FPS ở ~56 % CPU, và ba worker ~68 %, nên **về tài nguyên** hai camera trực tiếp có vẻ vừa máy này. Tuy vậy **chưa thử hai camera thật** (máy chỉ có một webcam; chưa đo USB bandwidth, hai camera cùng driver, nhiệt độ khi chạy lâu), nên chung kết chỉ tuyên bố "một camera trực tiếp + một clip". Mỗi lượt đo ngắn (14 s); chưa đo chạy liên tục nhiều giờ.
