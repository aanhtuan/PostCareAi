# Workflow: Review một feature

**Vai trò:** [code-reviewer](../roles/code-reviewer.md). Nên review trong **phiên mới** hoặc bằng agent khác với agent đã viết code.

## Các bước

1. Đọc spec feature (đặc biệt là AC và "Kế hoạch triển khai"), `AGENTS.md`, `coding-standards.md`.
2. Xem diff: `git diff main...HEAD`.
3. Chạy `make check`. Nếu đỏ, review dừng ở đây, ghi nhận lỗi.
4. Kiểm tra theo checklist dưới. Mỗi mục: Đạt / Không đạt (kèm file:dòng) / Không áp dụng.
5. Ghi kết quả vào mục "Ghi chú bàn giao" của spec, theo mẫu:

```text
Review <ngày> – <tool/agent>: <Đạt | Cần sửa>
- [Không đạt] <mục checklist> – <file:dòng> – <mô tả>
```

6. **Cần sửa:** quay lại [implement-feature.md](implement-feature.md). **Đạt:** sang [update-progress.md](update-progress.md) rồi commit/PR.

## Checklist

**Phạm vi và yêu cầu**
- [ ] Mọi acceptance criteria đều có test hoặc kiểm chứng thủ công đã ghi lại.
- [ ] Không có chức năng ngoài spec. Không có yêu cầu mới thiếu nguồn hoặc thiếu nhãn *(giả định)*.
- [ ] Không có gì thuộc danh sách "Ngoài phạm vi" trong PRD (chẩn đoán, nhận diện danh tính, tự train…).

**Kiến trúc**
- [ ] Ranh giới module đúng (`make check` có lint-imports xanh); `engine` vẫn thuần.
- [ ] Logic nghiệp vụ nằm trong `domain/`, không nằm trong router.
- [ ] Không viết cứng ngưỡng; giá trị mới đã thêm vào `config/engine.default.yaml` và `event-engine.md`.
- [ ] Mã sự kiện/enum chỉ khai báo ở `schemas`; text tiếng Việt chỉ ở `vi.ts`.

**Dữ liệu và bảo mật**
- [ ] Migration có `downgrade`; không sửa migration cũ.
- [ ] Endpoint ghi có kiểm tra vai trò và ghi audit log.
- [ ] Không log hay lưu ảnh, video, dữ liệu cá nhân ngoài phạm vi.
- [ ] Không lộ bí mật (token, mật khẩu) trong code hay log.

**Chất lượng**
- [ ] Engine có ca âm tính tương ứng ([testing.md](../../04-guides/testing.md#2-engine)).
- [ ] UI: không từ cấm, không hiện mã nội bộ, thời gian hiển thị đúng múi giờ.
- [ ] Lệnh chạy được trên Windows và Linux (không có cú pháp chỉ có trên bash).
- [ ] Doc liên quan đã cập nhật cùng PR.
