# ADR-0008: Làm công cụ đánh giá sớm, chốt ngưỡng trước tập test

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** HS §5.5, §7.3, §8.1, §8.2; PDF §12, §13

## Bối cảnh

Lộ trình HS §7.3 đặt "Bộ test, Precision/Recall/F1, FP/giờ, latency" ở tuần 9–10. Nhưng HS §5.5 và §8.2 yêu cầu **hiệu chỉnh** ngưỡng trên tập phát triển trước, rồi **chốt** ngưỡng để chạy tập đánh giá. Muốn hiệu chỉnh có cơ sở thì phải đo được từ sớm. PDF §12 cũng gợi ý dựng và kiểm thử Event Engine trên file video trước.

## Quyết định

- **F12** (tuần 3–4): lệnh `postcare replay` chạy pipeline trên file video và ghi JSONL.
- **F16** (tuần 3–4): lệnh `postcare eval --split dev`, gồm định dạng manifest và ground truth, metric P/R/F1, FP/giờ, latency, coverage, FPS.
- **F29** (tuần 9–10): lần đánh giá **chính thức** trên tập test với ngưỡng đã chốt (`--frozen <config_hash>`), cộng delivery latency và chỉ số workflow. Đầu ra của tuần 9–10 theo HS giữ nguyên.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **Công cụ eval sớm + đánh giá chính thức cuối** | Hiệu chỉnh có số liệu; đúng HS §8.2 | Thêm việc ở tuần 3–4 |
| Làm toàn bộ eval ở tuần 9–10 | Đúng thứ tự trong bảng HS §7.3 | Hiệu chỉnh ngưỡng dựa trên cảm tính; dễ phát hiện vấn đề quá muộn |

## Hệ quả

- Nhóm phải quay tập dev sớm (tuần 3). Đây là task không phải code trong `TASKS.md`.
- Mọi sự kiện mang `config_hash` để truy vết.
