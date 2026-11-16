# ADR-0002: Worker giao tiếp với API qua HTTP nội bộ

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** HS §4.2, §6.1; PDF §10

## Bối cảnh

Worker cần gửi lên API trạng thái, sự kiện, heartbeat và khung hình xem trực tiếp, đồng thời nhận cấu hình (ROI, ngưỡng, chế độ hiển thị). HS §4.2 yêu cầu "Backend lưu sự kiện trước khi gửi cập nhật realtime lên dashboard".

## Quyết định

- Worker gọi `/internal/v1/*` bằng **HTTP (httpx, keep-alive)**, xác thực bằng header `X-Worker-Token`.
- Cấu hình được poll mỗi 5 giây; heartbeat trả về `config_version` để worker biết khi nào tải lại.
- Sự kiện có `event_uid` để gửi lại an toàn (idempotent).
- Khung hình JPEG (~5 fps, *giả định A03*) gửi bằng POST. API chỉ giữ khung mới nhất trong RAM và phát lại dạng MJPEG cho trình duyệt.
- API lưu DB, commit xong **mới** phát WebSocket.

Chi tiết endpoint: [api-conventions.md](../api-conventions.md#api-nội-bộ-cho-worker).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **HTTP nội bộ** | Dễ viết, dễ test (TestClient), dễ debug bằng curl, idempotent rõ | Overhead nhỏ cho mỗi request (không đáng kể với 1 camera) |
| WebSocket hai chiều worker ↔ API | Ít overhead | Khó test, phải tự xử lý reconnect và ack |
| Worker ghi thẳng DB + `LISTEN/NOTIFY` | Không cần API nội bộ | Hai nơi ghi DB, logic cảnh báo bị chia đôi, vi phạm ranh giới module |
| Message broker (Redis/RabbitMQ) | Chuẩn khi scale | Thêm hạ tầng, quá mức cho MVP |
| Worker tự phục vụ MJPEG | Bớt một bước chuyển frame | Frontend phải gọi hai origin, xác thực tách rời, khó áp chế độ riêng tư tập trung |

## Hệ quả

- Worker và API phải chạy cùng LAN (thường là cùng máy).
- Đo delivery latency bắt đầu từ `events.created_at` (lúc lưu DB).
