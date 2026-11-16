# ADR-0007: Tách `status` và `outcome` của cảnh báo

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** PDF §5, §9.2, §11, §16; HS §4.2, §8.3, Hình 3; QA#16

## Bối cảnh

Các nguồn liệt kê 4 thao tác sau khi kiểm tra: "Xác nhận đúng", "Cảnh báo sai", "Bệnh nhân an toàn", "Đã xử lý" (PDF §5, §9.2; HS §4.2). Nhưng:
- Demo trong PDF §16 đi thẳng từ "Đã tiếp nhận" sang "Đã xử lý".
- Demo trong HS §8.3 có bước "ghi kết quả".
- PDF §11 cần dữ liệu "Xác nhận đúng / Cảnh báo sai" để đánh giá cảnh báo sai.

## Quyết định

- `status` (vòng đời): `PENDING` (Chờ tiếp nhận) → `ACKNOWLEDGED` (Đã tiếp nhận) → `RESOLVED` (Đã xử lý). Không đi lùi.
- `outcome` (kết quả kiểm tra): `CONFIRMED` (Xác nhận đúng) / `FALSE_ALARM` (Cảnh báo sai) / `PATIENT_SAFE` (Bệnh nhân an toàn) / null.
  - Chỉ ghi được khi `status = ACKNOWLEDGED`.
  - Ghi lại được nhiều lần trước khi đóng; lần sau ghi đè và mỗi lần đều có audit.
- "Đã xử lý" được phép khi chưa có outcome; UI hiển thị "Chưa ghi kết quả".
- Chỉ **một** người được tiếp nhận. Người thứ hai nhận lỗi 409 kèm tên người đã tiếp nhận.
- Mọi thao tác lưu người và thời điểm (trong `alerts` + `audit_logs`).
- Không có timeout hay chuyển tiếp (để sau MVP: F32).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **Tách status/outcome** | Khớp cả hai kịch bản demo; tính được tỷ lệ cảnh báo sai | Hai trường thay vì một |
| Một enum gồm 6 giá trị | Đơn giản | "Đã xử lý" và "Xác nhận đúng" lẫn lộn; không biết cảnh báo đã đóng có đúng hay không |

## Hệ quả

- Chỉ số "tỷ lệ cảnh báo sai theo phản hồi" (F29) tính trên các cảnh báo có `outcome`.
- Timeline hiển thị riêng từng thao tác.
