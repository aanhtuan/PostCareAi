# PostCare AI — Tổng kết hiện trạng dự án

Ngày kiểm tra: **16/11/2026**.

## 1. Tổng quan

Dự án hiện có **prototype web và backend phục vụ demo bằng dữ liệu giả lập**. Đã xây dựng luồng nghiệp vụ từ nhận sự kiện, tạo cảnh báo, nhân viên y tế tiếp nhận và ghi kết quả đến lịch sử và bàn giao ca.

**Phần AI xử lý hình ảnh từ camera chưa được triển khai.** Không nên coi các sự kiện do simulator tạo ra là kết quả nhận diện AI hoặc bằng chứng chạy camera thật.

## 2. Những phần đã có

| Hạng mục | Chức năng hiện có |
|---|---|
| Tài liệu | PRD, quyết định sản phẩm, kiến trúc, data model, API, event engine, spec F00–F35, roadmap và hướng dẫn |
| Backend | FastAPI, SQLAlchemy, SQLite mặc định; có tùy chọn kết nối PostgreSQL |
| Đăng nhập và phân quyền | JWT; vai trò điều dưỡng, phụ trách ca, bác sĩ và quản trị; bác sĩ chỉ xem |
| Danh mục | API xem giường, bệnh nhân, camera và ca trực; UI hiển thị danh mục |
| Phiên theo dõi | Mở và kết thúc phiên; kiểm tra xung đột phiên |
| Nhận sự kiện | API nội bộ cho simulator/worker; chống trùng theo mã định danh sự kiện; sự kiện ưu tiên trung bình/cao tạo cảnh báo |
| Vòng đời cảnh báo | Tiếp nhận, ghi kết quả, hoàn tất; kiểm soát chuyển trạng thái; ghi audit log |
| Realtime | WebSocket cập nhật sự kiện, cảnh báo và trạng thái; lưu sự kiện/cảnh báo vào DB trước khi phát |
| Trạng thái camera | Nhận heartbeat và phát hiện mất kết nối dựa trên heartbeat; chưa có worker đọc camera thật |
| Tổng quan | Thẻ giường, trạng thái theo dõi và các sự kiện cần chú ý |
| Theo dõi trực tiếp | Hiển thị skeleton SVG dựng từ trạng thái giả lập |
| Cảnh báo | Danh sách, chi tiết, thao tác xử lý; có code thông báo và âm thanh cho cảnh báo ưu tiên cao |
| Lịch sử | Timeline sự kiện và thao tác xử lý cảnh báo |
| Bàn giao ca | Tổng hợp theo ca và giao diện in |
| Bộ giả lập | CLI mô phỏng rời giường, mất quan sát, chuyển động bất thường, tín hiệu khuôn mặt và thay đổi tư thế |
| Công cụ phát triển | Makefile, script PowerShell, sinh type TypeScript từ OpenAPI và bộ test backend/frontend |

Các trang web hiện có: Đăng nhập, Tổng quan, Theo dõi trực tiếp, Cảnh báo, Lịch sử theo dõi, Bàn giao ca và Quản lý giường. Text giao diện tập trung tại `web/src/i18n/vi.ts`.

## 3. Những phần chưa triển khai hoặc chưa hoàn thiện

### Camera và AI

- Đọc camera/webcam/luồng video thật và hiển thị MJPEG.
- MediaPipe Pose/Face và xử lý chất lượng landmark.
- Engine thuần, đặc trưng cơ thể, state machine và rule phát hiện sự kiện theo thời gian.
- Worker xử lý camera và pipeline dùng chung.
- Replay video, công cụ đánh giá và báo cáo chỉ số AI.
- Nhận diện tín hiệu khuôn mặt, mức vận động và trạng thái nghỉ/hoạt động theo spec.

Các module `engine`, `vision`, `pipeline`, `worker`, `replay`, `eval` hiện là phần giữ chỗ. Chưa có `config/engine.default.yaml`.

### Giao diện và nền tảng

- Cấu hình camera, vẽ vùng giường ROI.
- Chế độ hiển thị riêng tư/làm mờ.
- Thêm/sửa danh mục giường, bệnh nhân và camera trên UI.
- PostgreSQL và Alembic theo kiến trúc đích; hiện tạo bảng bằng `create_all`.
- Import-linter, mypy, git hook pre-commit/pre-push, CI, MSW và E2E theo spec.

## 4. Kết quả kiểm tra ngày 16/11/2026

| Kiểm tra | Kết quả | Bằng chứng hoặc giới hạn |
|---|---|---|
| Backend pytest | PASS | 40 test đạt trong 13,72 giây; dùng SQLite tạm |
| Ruff format | PASS | 57 file đã đúng format |
| Ruff lint | PASS | All checks passed |
| TypeScript | PASS | Gọi trực tiếp `tsc --noEmit` bằng Node |
| ESLint | PASS | Gọi trực tiếp bằng Node từ thư mục `web/` |
| `make check` | PASS | Đạt sau khi cài lại phụ thuộc frontend bằng `npm --prefix web ci` |
| Prettier | PASS | Chạy qua `make check` từ đúng thư mục; hai file API sinh tự động được cấu hình bỏ qua trong `web/.prettierignore` |
| Vitest | PASS | 25 test đạt, 3 file test |
| Vite build | PASS | Build production thành công |
| Giao diện trên trình duyệt | NOT RUN | Chưa kiểm tra trong phiên kiểm kê |
| Camera thật và E2E | NOT RUN | Chưa kiểm chứng; phần camera/AI chưa triển khai |

Đã xử lý lỗi quyền thực thi và thiếu native binding bằng cách cài lại phụ thuộc frontend cho Linux. Kết luận sai format ban đầu xuất phát từ việc gọi Prettier ngoài thư mục `web/`, không áp dụng đúng file ignore; không cần sửa hai file sinh tự động.

Nhật ký ngày 12/10/2026 ghi nhận 40 test backend, 25 test frontend và build đã đạt trên môi trường trước đó. Đây là kết quả lịch sử, không thay thế kết quả kiểm tra môi trường Linux hiện tại.

## 5. Tiến độ chính thức và Git

- Theo `docs/progress/ROADMAP.md`, **F00–F35 đều đang Todo**.
- Prototype nằm ngoài roadmap và chưa đạt đủ acceptance criteria của từng feature; có code không đồng nghĩa feature đã Done.
- Chưa đủ điều kiện xác nhận milestone M0 vì chưa xem được camera thật hoặc cấu hình ROI.
- Tại thời điểm kiểm kê ban đầu, nhánh `main` chưa có commit. Phiên xuất bản sau đó đã đẩy commit đầu tiên `e59d28f` lên `main` của [GitHub PostCareAi](https://github.com/aanhtuan/PostCareAi). Fetch dùng HTTPS, push dùng SSH; xem nhật ký phiên để biết chi tiết.
- `TASKS.md` còn mục review tài liệu trước khi viết code từ phiên khởi tạo, trong khi prototype đã được viết theo yêu cầu sau đó được ghi trong session-log.

## 6. Bước tiếp theo đề xuất

1. Đã cài lại phụ thuộc frontend phù hợp Linux bằng `npm --prefix web ci`.
2. Đã chạy lại `make check`: toàn bộ kiểm tra hiện có đều đạt.
3. Lập kế hoạch F00 theo `docs/ai/workflows/plan-feature.md`, hoàn thiện nền tảng và các kiểm tra còn thiếu.
4. Triển khai các feature kế tiếp theo phụ thuộc trong roadmap; hoàn thiện camera, ROI, Pose, engine và worker để có chuỗi demo bằng camera thật.
5. Kiểm chứng trình duyệt, E2E và đánh giá AI trước khi công nhận các milestone tương ứng.

Các bước 1–2 đã hoàn tất trong phiên chuẩn bị xuất bản GitHub. Các bước 3–5 là đề xuất tiếp theo, chưa thực hiện. `make check` hiện tại chưa bao gồm các kiểm tra còn thiếu theo F00 như mypy và import-linter; kết quả xanh không đồng nghĩa F00 đã Done.

## 7. Tài liệu đối chiếu

- [README](README.md)
- [Tasks](docs/progress/TASKS.md)
- [Roadmap](docs/progress/ROADMAP.md)
- [Nhật ký phiên](docs/progress/session-log.md)
- [ADR-0010: Prototype SQLite và simulator](docs/02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md)
- [Spec F00](docs/03-features/F00-project-skeleton.md)
