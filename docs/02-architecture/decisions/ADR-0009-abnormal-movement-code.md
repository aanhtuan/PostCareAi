# ADR-0009: Dùng mã `ABNORMAL_MOVEMENT` thay `FALL_LIKE`

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** PDF §7.3, §9.3; HS §4.3, §5.2, §5.4; [conflicts.md](../../00-source/conflicts.md) C04

## Bối cảnh

PDF gọi là "sự kiện có đặc trưng giống té ngã" và lấy `FALL_LIKE` làm ví dụ mã nội bộ (§9.3). HS (ưu tiên khi xung đột) gọi là "Chuyển động bất thường - đề nghị kiểm tra", với điều kiện rộng hơn: hạ thấp nhanh, dịch chuyển mạnh, đổi hướng thân đột ngột (§5.2). Danh sách từ cấm trên UI có "té ngã".

## Quyết định

- Mã nội bộ: `ABNORMAL_MOVEMENT`. Text UI: "Phát hiện chuyển động bất thường - đề nghị kiểm tra". Mức ưu tiên: `HIGH`.
- Rule kết hợp nhiều điều kiện trong cửa sổ ngắn (xem [event-engine.md](../event-engine.md#5-catalog-sự-kiện)).
- Bộ test vẫn gồm tình huống "chuyển động nhanh xuống nệm an toàn" (HS §8.1) và "mô phỏng ngã an toàn" (PDF §13.1).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **`ABNORMAL_MOVEMENT`** | Khớp HS; tên mã không gợi ý kết luận | Khác ví dụ trong PDF |
| `FALL_LIKE` | Khớp PDF §9.3 | Mâu thuẫn với cách diễn đạt của HS; dễ bị hiểu là khẳng định té ngã |

## Hệ quả

Mọi tài liệu, code và test dùng `ABNORMAL_MOVEMENT`.
