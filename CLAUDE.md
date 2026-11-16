@AGENTS.md

# Ghi chú riêng cho Claude Code

Mọi quy tắc nằm trong `AGENTS.md` và `docs/`. File này chỉ thêm cách dùng các tính năng của Claude Code. **Không thêm quy tắc dự án vào đây.**

- Slash command (adapter mỏng, trỏ về `docs/ai/workflows/`):
  - `/plan-feature Fxx`
  - `/implement-feature Fxx`
  - `/review Fxx`
  - `/update-progress Fxx`
- Subagent (trỏ về `docs/ai/roles/`):
  - `planner` (chỉ đọc)
  - `code-reviewer` (chỉ đọc + chạy `make check`)
  - `test-writer`
- Lập kế hoạch: có thể dùng plan mode, nhưng kết quả cuối **phải** ghi vào mục "Kế hoạch triển khai" của spec. Plan nằm ngoài repo thì AI khác không thấy.
- Kiểm tra code bằng `make check` và git hook của repo. **Không** dựa vào hook trong `.claude/settings.json` để thay thế các bước này.
- Memory của Claude không phải nơi lưu tiến độ. Ghi vào `docs/progress/`.
