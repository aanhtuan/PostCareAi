# ADR-0001: Modular monolith chạy trên một máy

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** HS §6.1; PDF §10; QA#10

## Bối cảnh

PDF §10 mô tả 5 thành phần: Camera Service, AI Inference Service, Event Service, Backend, Realtime Gateway. HS §6.1 cho phép "MVP có thể chạy trên một máy tính thay vì tách thành nhiều microservice", miễn là ranh giới dữ liệu rõ ràng. Nhóm là sinh viên, có 10 tuần, và phần lớn code do AI viết.

## Quyết định

- Một repo, một package Python `postcare` chia module theo trách nhiệm (xem [overview.md](../overview.md#3-module-trong-serversrcpostcare)).
- Khi chạy có **2 loại tiến trình**: API (FastAPI) và worker (1 tiến trình / camera). Thêm web app (Vite).
- Ranh giới module được kiểm tra tự động bằng import-linter.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| Microservices (5 service, message broker) | Đúng hình PDF §10, scale riêng từng phần | Nhiều hạ tầng (broker, nhiều deploy), khó cho AI và người mới, chậm |
| Một tiến trình duy nhất (API chạy AI trong thread) | Đơn giản nhất | AI chiếm CPU làm API chậm; camera lỗi có thể làm sập API; GIL |
| **Modular monolith, 2 loại tiến trình** | Đơn giản, cô lập được AI, ranh giới rõ, dễ nhân bản worker cho nhiều camera | Phải định nghĩa API nội bộ |

## Hệ quả

- Cần API nội bộ worker ↔ API ([ADR-0002](ADR-0002-worker-http-internal-api.md)).
- Muốn tách thành service riêng sau này thì các module đã có ranh giới rõ.
