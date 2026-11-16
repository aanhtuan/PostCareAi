# ADR-0005: Frontend React + Mantine + type sinh từ OpenAPI

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** PDF §9, §15.1 ("ứng dụng web tiếng Việt"); HS §4.3

## Bối cảnh

Cần một web app tiếng Việt gồm khoảng 8 màn hình (PDF §9.1), cập nhật realtime, chạy trên laptop và tablet. Code phần lớn do AI viết, nên cần công nghệ phổ biến và type an toàn.

## Quyết định

- **React 19 + TypeScript + Vite** (SPA, không SSR).
- **Mantine 8** cho component và thông báo; **TanStack Query** cho dữ liệu server; **React Router 7**.
- Type API sinh bằng **openapi-typescript** từ `/api/openapi.json` (`make gen-api-types`). Không viết tay type API.
- Toàn bộ text tiếng Việt nằm trong **một file** `web/src/i18n/vi.ts`, có test quét từ cấm.
- Xem trực tiếp bằng thẻ `<img src=".../stream.mjpeg?token=">`.

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **React + Mantine** | Phổ biến nhất, nhiều component sẵn | Bundle lớn hơn Tailwind thuần |
| React + shadcn/ui + Tailwind | Rất phổ biến | Copy component vào repo; nhiều class CSS; AI dễ tạo UI lệch nhau |
| Vue + Element Plus | Dễ học | Ít ví dụ hơn React khi AI viết |
| Next.js | Mạnh | SSR không cần cho dashboard LAN; thêm độ phức tạp |
| Template server-side (Jinja) + htmx | Ít JS | Realtime và tương tác (vẽ ROI) khó hơn |

## Hệ quả

- Backend thay đổi API thì phải chạy `make gen-api-types`. `make check` báo lỗi nếu type cũ (so sánh file sinh ra).
- Thư viện i18n đầy đủ là không cần thiết: chỉ có tiếng Việt, một file từ điển là đủ.
