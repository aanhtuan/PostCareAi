# ADR-0006: Tài liệu và công cụ trung lập với AI

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** Yêu cầu của người dùng; QA#6

## Bối cảnh

Code do nhiều AI tool viết (Claude Code, Codex, Cursor, Copilot, Gemini CLI). Có thể đổi tool giữa chừng. Nếu quy tắc nằm trong cấu hình riêng của một tool, các tool khác sẽ không thấy.

## Quyết định

- **Lớp lõi:**
  - `AGENTS.md` (nguồn sự thật, < 150 dòng) + `docs/` (Markdown thuần, không dùng cú pháp riêng của tool).
  - Quy trình (`docs/ai/workflows/`) và vai trò (`docs/ai/roles/`) viết dạng văn bản để mọi tool làm theo được.
- **Lớp adapter mỏng:**
  - `CLAUDE.md` chỉ chứa `@AGENTS.md` + ghi chú riêng cho Claude.
  - `.claude/commands/*` và `.claude/agents/*` chỉ trỏ về file trong `docs/ai/`.
  - `.gemini/settings.json` trỏ context file về `AGENTS.md` *(giả định tên khóa)*.
  - Codex, Cursor, Copilot đọc `AGENTS.md` sẵn.
- **Kiểm tra tự động không phụ thuộc AI tool:**
  - `Makefile` (`make check`).
  - Hook **pre-commit** (format/lint khi commit; `make check` khi push).
  - GitHub Actions chạy cùng `make check`.
- **Tiến độ và bàn giao:** `docs/progress/ROADMAP.md`, `TASKS.md`, `session-log.md`.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **Lõi chung + adapter mỏng** | Đổi tool không mất quy tắc; một nơi để sửa | Phải giữ adapter không "phình" ra |
| Chỉ dùng cấu hình Claude (CLAUDE.md, hooks) | Tận dụng tính năng Claude | Tool khác không đọc được; hook chỉ chạy trong Claude |
| Mỗi tool một bộ quy tắc riêng | Tối ưu cho từng tool | Lệch nhau, khó bảo trì |

## Hệ quả

- Khi sửa quy tắc, sửa `AGENTS.md` hoặc `docs/`, **không** sửa adapter (trừ khi đổi đường dẫn).
- GNU Make phải được cài trên Windows ([dev-setup.md](../../04-guides/dev-setup.md)).
