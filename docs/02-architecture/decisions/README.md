# Architecture Decision Records

Mỗi quyết định kiến trúc quan trọng được ghi thành một ADR, theo mẫu [_TEMPLATE.md](_TEMPLATE.md).
- Không sửa nội dung ADR đã "Chấp nhận".
- Muốn đổi quyết định thì tạo ADR mới và đánh dấu ADR cũ là "Thay thế bởi".

| ADR | Tiêu đề | Trạng thái |
|---|---|---|
| [ADR-0001](ADR-0001-modular-monolith.md) | Modular monolith chạy trên một máy | Chấp nhận |
| [ADR-0002](ADR-0002-worker-http-internal-api.md) | Worker giao tiếp với API qua HTTP nội bộ | Chấp nhận |
| [ADR-0003](ADR-0003-mediapipe-pretrained-adapter.md) | MediaPipe pretrained + adapter + schema chung | Chấp nhận |
| [ADR-0004](ADR-0004-postgresql.md) | PostgreSQL là cơ sở dữ liệu | Chấp nhận |
| [ADR-0005](ADR-0005-react-mantine-openapi-types.md) | Frontend React + Mantine + type sinh từ OpenAPI | Chấp nhận |
| [ADR-0006](ADR-0006-ai-neutral-tooling.md) | Tài liệu và công cụ trung lập với AI | Chấp nhận |
| [ADR-0007](ADR-0007-alert-status-outcome.md) | Tách `status` và `outcome` của cảnh báo | Chấp nhận |
| [ADR-0008](ADR-0008-early-eval-tooling.md) | Làm công cụ đánh giá sớm, chốt ngưỡng trước tập test | Chấp nhận |
| [ADR-0009](ADR-0009-abnormal-movement-code.md) | Dùng mã `ABNORMAL_MOVEMENT` thay `FALL_LIKE` | Chấp nhận |
| [ADR-0010](ADR-0010-prototype-sqlite-simulator.md) | Prototype đề xuất dùng SQLite, create_all và bộ giả lập thay worker AI | Chấp nhận (tạm thời) |
