# Workflow: Lập kế hoạch cho một feature

**Đầu vào:** mã feature (ví dụ `F15`). **Vai trò:** [planner](../roles/planner.md). **Không viết code ở bước này.**

## Các bước

1. **Đọc bối cảnh**, theo thứ tự:
   1. `AGENTS.md`.
   2. `docs/progress/TASKS.md` và entry cuối của `docs/progress/session-log.md`.
   3. Spec `docs/03-features/Fxx-*.md`.
   4. Các doc được spec tham chiếu (data-model, api-conventions, event-engine, PRD…).
   5. Đoạn nguồn được trích (`docs/00-source/`).
2. **Kiểm tra điều kiện bắt đầu:**
   - Mọi feature trong "Phụ thuộc" có trạng thái `Done` trong `docs/progress/ROADMAP.md`. Nếu chưa → dừng, báo người dùng.
   - Spec không còn "Câu hỏi mở" mức chặn. Nếu còn → hỏi người dùng, không tự quyết.
3. **Khảo sát code hiện có:** tìm module, hàm, pattern có thể dùng lại. Ghi đường dẫn cụ thể.
4. **Viết mục "Kế hoạch triển khai"** vào chính file spec:
   - Danh sách bước nhỏ, đánh số. Mỗi bước kiểm chứng được và có thể commit riêng.
   - File sẽ tạo/sửa (đường dẫn).
   - Test sẽ viết cho từng acceptance criterion (tên test dự kiến). Với rule engine: liệt kê cả ca âm tính.
   - Migration, endpoint, type cần sinh lại (`make gen-api-types`).
   - Doc cần cập nhật cùng PR.
   - Rủi ro và cách kiểm chứng thủ công (nếu cần camera thật).
5. **Đánh dấu giả định mới:** suy luận không có trong nguồn thì ghi *(giả định)* vào mục "Giả định" của spec.
6. **Cập nhật tiến độ:**
   - Spec: `Trạng thái: Planned`.
   - `docs/progress/TASKS.md`: feature này sang mục "Đang làm", kèm checklist các bước.
   - Thêm entry vào `session-log.md` theo [update-progress.md](update-progress.md).
7. **Xin xác nhận** của người dùng nếu kế hoạch thay đổi phạm vi, thêm thư viện, hoặc đụng tới feature khác.

## Đầu ra

- Spec có mục "Kế hoạch triển khai" đầy đủ.
- `TASKS.md` và `session-log.md` đã cập nhật.
