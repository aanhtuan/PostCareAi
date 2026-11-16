# Quy ước viết code

Áp dụng cho mọi người và mọi AI agent. Ruff, ESLint, Prettier, mypy, import-linter tự kiểm tra phần lớn các quy ước này qua `make check`.

## 1. Chung

- **Ngôn ngữ:**
  - Tên file, thư mục, biến, hàm, class, mã sự kiện, commit message: **tiếng Anh**.
  - Comment giải thích nghiệp vụ, docstring nghiệp vụ, tài liệu: **tiếng Việt** (QA#7).
  - Text hiển thị cho người dùng: **tiếng Việt**, chỉ đặt trong `web/src/i18n/vi.ts`. Thông báo lỗi API dùng `message` tiếng Việt.
- **Một nguồn sự thật:**
  - Mã sự kiện, trạng thái, mức ưu tiên: `server/src/postcare/schemas/`.
  - Câu tiếng Việt: `web/src/i18n/vi.ts`.
  - Ngưỡng engine: `config/engine.default.yaml`.
  - Không lặp lại ở nơi khác.
- **Không viết cứng ngưỡng** trong code rule. Mọi số liệu điều chỉnh được phải nằm trong `EngineConfig`.
- **Không dùng từ cấm** trên UI ([glossary.md](../01-product/glossary.md#từ-cấm-trên-ui)).
- **Không commit** video, ảnh người, model `.task`, `.env`, dữ liệu trong `data/`.
- **Đa nền tảng:**
  - Dùng `pathlib`, không nối chuỗi đường dẫn.
  - Lệnh trong Makefile không dùng cú pháp chỉ có trên bash.
  - File text dùng LF (`.gitattributes`).
- Không thêm thư viện mới nếu chưa ghi lý do vào spec feature và cập nhật [tech-stack.md](../02-architecture/tech-stack.md).
- Giữ hàm ngắn (gợi ý < 50 dòng), mỗi module một trách nhiệm.

## 2. Python (`server/`)

- Python 3.12, type hint đầy đủ cho hàm public. `schemas` và `engine` qua **mypy strict**.
- Format và lint bằng **ruff** (cấu hình trong `server/pyproject.toml`). Độ dài dòng 100.
- Đặt tên: `snake_case` cho hàm/biến/module, `PascalCase` cho class, `UPPER_SNAKE` cho hằng và giá trị enum.
- Schema dữ liệu dùng Pydantic v2 `BaseModel` (`model_config = ConfigDict(frozen=True)` cho schema engine).
- **Ranh giới module** theo [overview.md](../02-architecture/overview.md#3-module-trong-serversrcpostcare):
  - `engine` không import cv2, mediapipe, fastapi, sqlalchemy, httpx.
  - `api` không import `vision` hoặc `engine`.
- FastAPI:
  - Router chỉ parse request, gọi `domain`, trả response.
  - Logic nghiệp vụ nằm ở `postcare/domain/`.
  - Phụ thuộc DB qua `Depends(get_session)`.
- Lỗi nghiệp vụ: raise `DomainError(code, message, http_status)`. Handler chung chuyển thành định dạng lỗi của [api-conventions.md](../02-architecture/api-conventions.md#lỗi).
- Thời gian:
  - Dùng `datetime` có tzinfo UTC (`datetime.now(UTC)`).
  - **Trong `engine` không gọi đồng hồ hệ thống**, chỉ dùng `ts_ms` của observation.
- Logging dùng `logging` chuẩn, logger theo module. Không log ảnh hay dữ liệu cá nhân.
- Migration: mỗi thay đổi schema là một file Alembic mới, có `downgrade`.

## 3. TypeScript / React (`web/`)

- TypeScript `strict: true`. Không dùng `any` (ESLint báo lỗi).
- Format bằng **Prettier**, lint bằng **ESLint 9** (flat config).
- Cấu trúc:

```text
web/src/
  api/          # client fetch, schema.d.ts (sinh tự động, không sửa tay), hooks TanStack Query
  realtime/     # WebSocket client + invalidation
  i18n/vi.ts    # toàn bộ text tiếng Việt
  pages/        # mỗi màn hình một thư mục: Overview, LiveView, Alerts, Timeline, Handover, Management, CameraConfig, Login
  components/   # component dùng lại
  auth/         # context đăng nhập, guard theo vai trò
  utils/        # format thời gian (Asia/Ho_Chi_Minh, HH:mm:ss)
```

- Component: `PascalCase.tsx`, hook: `useXxx.ts`. Một component chính mỗi file.
- Dữ liệu server chỉ lấy qua TanStack Query. WebSocket chỉ làm mới cache (invalidate hoặc setQueryData), không giữ state riêng song song.
- Không hiển thị mã nội bộ (`BED_EXIT`…). Luôn ánh xạ qua `vi.ts`.
- Thời gian hiển thị theo `Asia/Ho_Chi_Minh`, định dạng `HH:mm:ss` cho timeline (PDF §9.3).

## 4. Git

- Nhánh: `feat/Fxx-<slug>`, `fix/Fxx-<slug>`, `docs/<slug>`, `chore/<slug>`.
- Commit theo Conventional Commits, có mã feature: `feat(F15): detect bed exit sequence`, `test(F14): add hysteresis cases`, `docs(F08): update ROI spec`.
- Mỗi feature một PR. PR phải xanh `make check` và đã review theo [review.md](../ai/workflows/review.md).
- Không `--no-verify`. Nếu hook lỗi thì sửa nguyên nhân.

## 5. Tài liệu

- Markdown thuần, không dùng cú pháp riêng của tool AI trong `AGENTS.md` và `docs/`.
- Thay đổi hành vi thì cập nhật doc liên quan **trong cùng PR** (data-model, api-conventions, event-engine, spec).
- Mọi yêu cầu ghi nguồn (`HS §x`, `PDF §x (tr.y)`, `QA#n`) hoặc nhãn *(giả định)*.
