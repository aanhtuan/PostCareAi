# AGENTS.md: PostCare AI

File này là **nguồn sự thật duy nhất** về quy tắc làm việc cho mọi AI agent (Claude Code, Codex, Cursor, Copilot, Gemini CLI…) và cho người.
Chi tiết nằm trong `docs/`. File này chỉ chứa quy tắc, lệnh và đường dẫn.

## Dự án

PostCare AI là prototype hỗ trợ quan sát bệnh nhân hậu phẫu:
camera → MediaPipe Pose/Face (pretrained, không train) → Event Detection Engine theo thời gian → cảnh báo realtime trên web tiếng Việt → nhân viên y tế tiếp nhận và xác nhận → timeline, bàn giao ca.
Xem [docs/01-product/PRD.md](docs/01-product/PRD.md).

## Bắt đầu mỗi phiên: đọc theo thứ tự

1. File này.
2. [docs/progress/TASKS.md](docs/progress/TASKS.md): đang làm gì, việc tiếp theo.
3. Entry mới nhất trong [docs/progress/session-log.md](docs/progress/session-log.md).
4. Spec của feature đang làm: `docs/03-features/Fxx-*.md`.
5. Các doc mà spec tham chiếu.

## Bản đồ tài liệu

| Cần biết | Đọc |
|---|---|
| Đề tài gốc, thứ tự ưu tiên nguồn, xung đột | `docs/00-source/` (README, conflicts.md) |
| Yêu cầu, vai trò, phạm vi, ngoài phạm vi | `docs/01-product/PRD.md` |
| Quyết định đã chốt, giả định A01–A15 | `docs/01-product/qa-decisions.md` |
| Thuật ngữ, **từ cấm trên UI** | `docs/01-product/glossary.md` |
| Kiến trúc, module, ranh giới import | `docs/02-architecture/overview.md` |
| Công nghệ và phiên bản | `docs/02-architecture/tech-stack.md` |
| Bảng DB | `docs/02-architecture/data-model.md` |
| REST, WebSocket, API nội bộ, lỗi | `docs/02-architecture/api-conventions.md` |
| Trạng thái, catalog sự kiện, ngưỡng | `docs/02-architecture/event-engine.md` |
| Quyết định kiến trúc (ADR) | `docs/02-architecture/decisions/` |
| Danh sách feature và spec | `docs/03-features/README.md` |
| Quy ước code / test | `docs/04-guides/coding-standards.md`, `testing.md` |
| Cài đặt, camera, đánh giá, dữ liệu ngoài | `docs/04-guides/dev-setup.md`, `camera-setup.md`, `evaluation.md`, `datasets.md` |
| Prompt mẫu cho mọi AI tool | `docs/04-guides/prompt-guide.md` |
| Kế hoạch demo, nội dung trình bày | `docs/progress/DEMO-PLAN.md`, `docs/01-product/pitch-and-evidence.md` |
| Quy trình làm feature | `docs/ai/workflows/` |
| Vai trò planner / reviewer / test writer | `docs/ai/roles/` |
| Roadmap, task, nhật ký phiên | `docs/progress/` |

## Lệnh

Có sau F00. Chạy từ thư mục gốc, dùng được trên Windows (cài GNU Make) và Linux.

| Lệnh | Mục đích |
|---|---|
| `make setup` | Cài phụ thuộc (uv, npm) và git hook (pre-commit) |
| `make check` | **Bắt buộc xanh trước khi xong việc**: format-check, lint, typecheck, lint-imports, check-api-types, test, build web |
| `make format` | Tự format code (ruff, prettier) |
| `make test` / `make test-vision` / `make e2e` | Test thường / test cần model + video / Playwright |
| `make dev` / `make dev-api` / `make dev-web` | Chạy API + web khi phát triển |
| `make worker CAMERA=<id>` | Chạy worker cho một camera |
| `make db-upgrade` / `make db-seed` | Migration / dữ liệu mẫu |
| `make models` | Tải model MediaPipe vào `models/` |
| `make gen-api-types` | Sinh type TS từ OpenAPI (sau khi API đổi) |
| `make demo-seed` | Tạo lại dữ liệu demo (F30; cần `DEMO_RESET=1`) |

Lệnh CLI Python: `uv run postcare <worker|probe|replay|eval|...>` (chạy trong `server/`; Makefile bọc sẵn).

## Cấu trúc repo

```text
AGENTS.md  CLAUDE.md  README.md  Makefile  .pre-commit-config.yaml
config/            engine.default.yaml, cameras/*.yaml
server/            Python package `postcare` (src/postcare/{schemas,engine,vision,worker,replay,eval,db,domain,api}), tests/
web/               React + TS (src/{api,realtime,i18n,pages,components,auth,utils})
docs/              tài liệu lõi (Markdown thuần)
data/ runs/ models/ reports/*.local.md   KHÔNG commit (gitignore)
```

## Quy tắc bắt buộc

1. **Phạm vi:** chỉ làm những gì có trong spec feature. Mọi yêu cầu phải truy được về `HS §x`, `PDF §x`, `QA#n`, hoặc ghi rõ *(giả định)*. **Không tự bịa yêu cầu.** Gặp chỗ mơ hồ: ghi vào "Câu hỏi mở" của spec và hỏi người dùng.
2. **Ngoài phạm vi, không làm:**
   - tự train hoặc fine-tune model;
   - chẩn đoán đau, mất ý thức, biến chứng; phân loại ngủ/tỉnh;
   - nhận diện danh tính bằng khuôn mặt;
   - lưu video vận hành.
3. **Ngôn ngữ UI:**
   - Tiếng Việt, mô tả điều quan sát được.
   - **Không dùng từ cấm** (`glossary.md`).
   - Không hiện mã nội bộ (`BED_EXIT`…).
   - Text chỉ nằm trong `web/src/i18n/vi.ts`.
4. **Một nguồn sự thật:**
   - Mã sự kiện, trạng thái, mức ưu tiên: `server/src/postcare/schemas/`.
   - Ngưỡng: `config/engine.default.yaml`.
   - Không viết cứng số ngưỡng trong code.
5. **Engine thuần:** `postcare.engine` không import cv2, mediapipe, fastapi, sqlalchemy, httpx; không đọc đồng hồ hệ thống; deterministic. Import-linter kiểm tra.
6. **Không tin một frame:**
   - Mọi chuyển trạng thái và sự kiện phải giữ đủ `min_duration`.
   - Mất landmark hoặc bị che → `NO_OBSERVATION`, **không bao giờ** là rời giường.
7. **Lưu trước, phát sau:** API commit DB rồi mới gửi WebSocket.
8. **Bảo mật:**
   - Endpoint ghi phải kiểm tra vai trò và ghi audit log.
   - Không commit bí mật, `.env`, video, ảnh người, model.
9. **Test:** viết test trước cho rule engine và vòng đời cảnh báo; mỗi rule có ca âm tính. `make check` phải xanh. Không dùng `--no-verify`.
10. **Đa nền tảng:** lệnh và script phải chạy được trên Windows và Linux; file text dùng LF.
11. **Tài liệu đi cùng code:** thay đổi hành vi thì cập nhật doc liên quan trong cùng PR. Markdown thuần, không dùng cú pháp riêng của tool AI trong `docs/` và file này.
12. **Thư viện mới:** chỉ thêm khi đã ghi lý do vào spec và `tech-stack.md`.

## Quy trình mỗi feature

Chi tiết ở `docs/ai/workflows/`:

1. **Plan**: [plan-feature.md](docs/ai/workflows/plan-feature.md). Viết "Kế hoạch triển khai" vào spec.
2. **Implement**: [implement-feature.md](docs/ai/workflows/implement-feature.md). Nhánh `feat/Fxx-<slug>`, test trước, commit nhỏ.
3. **Review**: [review.md](docs/ai/workflows/review.md). Nên dùng phiên hoặc agent khác.
4. **Cập nhật tiến độ**: [update-progress.md](docs/ai/workflows/update-progress.md). Cập nhật spec, ROADMAP, TASKS, session-log.

Chỉ bắt đầu feature khi mọi phụ thuộc đã `Done` trong `docs/progress/ROADMAP.md`.

## Git

- Commit theo Conventional Commits, có mã feature: `feat(F15): detect bed exit sequence`.
- Mỗi feature một nhánh và một PR vào `main`.
- Hook pre-commit (format/lint) và pre-push (`make check`) do `make setup` cài. Không bỏ qua hook.

## Definition of Done

- [ ] Mọi acceptance criteria trong spec đã tick, có bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh (feature vision: thêm `make test-vision` hoặc replay).
- [ ] Doc liên quan đã cập nhật.
- [ ] Review: Đạt.
- [ ] `docs/progress/` đã cập nhật.

## Bàn giao giữa các phiên / đổi AI

- Cuối **mỗi** phiên, kể cả khi dừng giữa chừng: thêm entry vào `docs/progress/session-log.md`, gồm đã làm, đang dở, bước tiếp theo (tới mức lệnh), blocker. Tick checklist trong `TASKS.md`.
- Không giữ trạng thái quan trọng chỉ trong bộ nhớ của tool AI. Mọi thứ cần thiết phải nằm trong repo.
