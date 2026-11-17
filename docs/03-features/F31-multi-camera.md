# F31 – Nhiều camera/giường chạy đồng thời

| Thuộc tính | Giá trị |
|---|---|
| Mã | F31 |
| Trạng thái | Todo |
| Ưu tiên | MVP cho R1–R3; phần còn lại Sau MVP |
| Milestone | M4 (R1–R3) / Sau MVP |
| Ước lượng | 3 phiên |
| Phụ thuộc | F06, F17 |
| Nhánh code | A (vision/engine) + B (backend) |
| Nguồn | HS §9.2, §2.2; PDF §18 (tr.18); conflicts C01; QA#13; QA#32 |

> Spec ngắn, ở mức định hướng. **Sẽ chi tiết hóa khi bắt đầu.** Theo QA#32, R1–R3 được làm ở M4 để demo chung kết chạy cùng lúc A01 (camera live) và A02 (clip phát lại, `FILE --realtime`). Chỉ tuyên bố "hai camera live" khi đã thử hai camera thật trên cùng phần cứng.

## 1. Mục tiêu

Sau khi MVP một giường ổn định, cho phép nhiều giường, mỗi giường một camera, được theo dõi **cùng lúc** trên một máy. Người trực có thể ưu tiên các giường đang có sự kiện thay vì chú ý đều cho mọi luồng camera (HS §2.2, §9.2; PDF §18). Data model và dashboard đã hỗ trợ nhiều giường từ MVP (conflicts C01).

## 2. Phạm vi

**Trong phạm vi**
- Chạy nhiều tiến trình worker đồng thời, mỗi tiến trình một camera (overview.md mục 1).
- Lệnh tiện ích khởi động/dừng các worker của mọi camera đang hoạt động.
- Đo tài nguyên khi tăng số camera.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Nhiều camera cho **cùng một** giường (cần đổi ràng buộc `cameras.bed_id` unique; chưa có trong nguồn).
- Chạy worker trên nhiều máy, GPU.
- Cấu hình rule theo khu vực (PDF §18; ngoài phạm vi PRD).

## 3. Yêu cầu chi tiết

- **R1.** Chạy ≥ 2 worker cùng lúc trên một máy, mỗi worker gắn đúng camera và giường của nó. *(HS §9.2; PDF §18)*
- **R2.** Một worker lỗi hoặc mất camera không ảnh hưởng worker khác và API. *(overview.md mục 1; HS §4.1)*
- **R3.** Báo cáo FPS, CPU, RAM theo số camera để biết giới hạn của phần cứng được công bố. *(HS §8.2)*
- **R4.** Lệnh khởi động tất cả worker *(giả định: ví dụ `make workers` hoặc `postcare worker --all`)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:** `server/src/postcare/cli.py`, `server/src/postcare/worker/`, `Makefile`, `Procfile.dev`.
- **Dữ liệu:** không đổi (`cameras.bed_id` vẫn unique) ([data-model.md](../02-architecture/data-model.md)).
- **API:** không đổi; API nội bộ đã theo `camera_id` ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** "Tổng quan" đã hiển thị nhiều giường (F21).
- **Cấu hình:** override ngưỡng theo camera qua `cameras.thresholds` (đã có).

## 5. Acceptance criteria

Định hướng, sẽ chi tiết hóa khi bắt đầu.

- [ ] **AC1.** 3 worker (A01–A03) chạy cùng lúc; mỗi sự kiện gắn đúng giường và camera. *(HS §9.2)* — *Kiểm chứng:* test tích hợp với 3 `FakeFrameSource`; thủ công với 2 nguồn thật hoặc video.
- [ ] **AC2.** Dừng hoặc làm lỗi một worker → chỉ camera đó `offline`; các giường khác vẫn nhận sự kiện. *(overview.md mục 1)* — *Kiểm chứng:* test tích hợp.
- [ ] **AC3.** Có bảng FPS/CPU/RAM theo 1, 2, 3 camera trong `tech-stack.md`. *(HS §8.2)* — *Kiểm chứng:* thủ công, reviewer xem bảng.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | tích hợp | Nhiều worker giả gửi sự kiện | Sự kiện của camera 2 không xuất hiện ở giường A01 |
| AC2 | tích hợp | Dừng một worker | Các giường khác không đổi trạng thái camera |
| AC3 | thủ công | Đo tài nguyên | — |

## 7. Giả định

- *(giả định)* Giữ mô hình 1 camera / giường; tên lệnh khởi động nhiều worker.

## 8. Câu hỏi mở

- Số giường mục tiêu khi mở rộng là bao nhiêu? Quyết định cấu hình phần cứng. **Chặn** khi bắt đầu chi tiết hóa.

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
