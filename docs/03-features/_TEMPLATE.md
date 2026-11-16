# Fxx – <Tên feature>

| Thuộc tính | Giá trị |
|---|---|
| Mã | Fxx |
| Trạng thái | Todo <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP / Sau MVP |
| Milestone | M0 / M1 / M2 / M3 / M4 / Sau MVP |
| Ước lượng | 1–3 phiên |
| Phụ thuộc | Fyy, Fzz |
| Nhánh code | A (vision/engine) / B (backend) / C (frontend/test) |
| Nguồn | HS §x; PDF §x (tr.y); QA#n |

## 1. Mục tiêu

Một đoạn ngắn: feature giải quyết việc gì cho ai. Trích nguồn.

## 2. Phạm vi

**Trong phạm vi**
- …

**Ngoài phạm vi** (để feature khác hoặc không làm)
- … (→ Fzz)

## 3. Yêu cầu chi tiết

Đánh số `R1`, `R2`… Mỗi yêu cầu có nguồn hoặc nhãn *(giả định)*.

- **R1.** … *(HS §x)*
- **R2.** … *(giả định: lý do)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:** `server/src/postcare/...`, `web/src/...`
- **Dữ liệu:** bảng/cột (xem [data-model.md](../02-architecture/data-model.md))
- **API:** endpoint (xem [api-conventions.md](../02-architecture/api-conventions.md))
- **UI:** màn hình, text cần thêm vào `vi.ts`
- **Cấu hình:** khóa ngưỡng trong `config/engine.default.yaml` (nếu có)

## 5. Acceptance criteria

Kiểm chứng được. Mỗi AC ghi cách kiểm chứng.

- [ ] **AC1.** … — *Kiểm chứng:* test `…` / lệnh `…`
- [ ] **AC2.** …
- [ ] **AC3.** …

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit / API / component / thủ công | … | … |

## 7. Giả định

- *(giả định)* …

## 8. Câu hỏi mở

- (Không) / Câu hỏi cho người dùng, ghi rõ có **chặn** việc triển khai hay không.

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

1. …

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
