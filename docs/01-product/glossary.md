# Thuật ngữ

Dùng thống nhất các thuật ngữ dưới đây trong tài liệu, code và UI. Cột "Code" là tên dùng trong code/DB. **Không bao giờ hiển thị cột này cho người dùng cuối.**

## Thuật ngữ nghiệp vụ

| Tiếng Việt (UI/tài liệu) | Tiếng Anh | Code | Định nghĩa |
|---|---|---|---|
| Bệnh nhân / người được theo dõi | Patient | `patients` | Người thử nghiệm, chỉ định danh bằng **mã thử nghiệm** (không có họ tên hay ảnh) |
| Giường | Bed | `beds` | Vị trí giường, mã dạng `A01`, có khu vực |
| Camera | Camera | `cameras` | Nguồn video gắn với một giường (MVP: 1 camera / giường) |
| Vùng giường | Bed ROI | `roi_polygon` | Polygon trên khung hình camera, toạ độ chuẩn hóa 0–1 |
| Phiên theo dõi | Monitoring session | `monitoring_sessions` | Gắn một bệnh nhân với một giường/camera trong một khoảng thời gian |
| Người mục tiêu | Target person | `target` | Người được coi là bệnh nhân trong khung hình (tâm hông trong ROI) |
| Trạng thái cơ thể | Body state | `BodyState` | Một trong 7 trạng thái của state machine |
| Sự kiện | Event | `events` | Thay đổi có ý nghĩa do engine tạo, có thời điểm, mức ưu tiên, căn cứ |
| Cảnh báo | Alert | `alerts` | Sự kiện mức Cần chú ý / Ưu tiên cao cần người tiếp nhận |
| Mức ưu tiên | Priority | `Priority` | Nhật ký / Thông tin / Cần chú ý / Ưu tiên cao. Đây là ưu tiên **workflow**, không phải nguy cơ lâm sàng (PDF §7) |
| Chờ tiếp nhận | Pending | `PENDING` | Cảnh báo chưa có ai nhận |
| Đã tiếp nhận | Acknowledged | `ACKNOWLEDGED` | Đã có một người nhận trách nhiệm |
| Đã xử lý | Resolved | `RESOLVED` | Cảnh báo đã đóng |
| Xác nhận đúng / Cảnh báo sai / Bệnh nhân an toàn | Confirmed / False alarm / Patient safe | `CONFIRMED` / `FALSE_ALARM` / `PATIENT_SAFE` | Kết quả kiểm tra thực tế (`outcome`) |
| Timeline / Lịch sử theo dõi | Timeline | — | Chuỗi sự kiện và thao tác của một phiên, sắp theo thời gian |
| Bàn giao ca | Shift handover | — | Tổng hợp sự kiện và cảnh báo trong một ca |
| Ca trực | Shift | `shift_definitions` | Khung giờ làm việc (ví dụ 14:00–22:00) |
| Nhật ký thao tác | Audit log | `audit_logs` | Ai làm gì, lúc nào; chỉ thêm, không sửa |
| Không đủ dữ liệu quan sát | No observation | `NO_OBSERVATION` | Chất lượng quan sát không đủ để kết luận |
| Chế độ hiển thị | Display mode | `RAW` / `BLUR` / `SKELETON` | Video gốc / Làm mờ khuôn mặt / Chỉ skeleton + ROI |
| Đang nghỉ - dữ liệu tham khảo / Đang hoạt động | Resting / Active (reference) | `RESTING` / `ACTIVE` | Trạng thái hiển thị dựa trên mức vận động và mắt; **không** phải phân loại giấc ngủ |

## Trạng thái cơ thể (state machine)

| UI | Code |
|---|---|
| Nằm | `LYING` |
| Đang nâng thân | `RAISING` |
| Ngồi | `SITTING` |
| Ở mép giường | `AT_EDGE` |
| Đứng | `STANDING` |
| Ngoài giường | `OUT_OF_BED` |
| Không đủ dữ liệu quan sát | `NO_OBSERVATION` |

## Thuật ngữ kỹ thuật

| Thuật ngữ | Giải thích |
|---|---|
| Landmark / keypoint | Điểm mốc cơ thể do Pose Landmarker trả về (33 điểm) |
| Blendshape | Hệ số 0–1 mô tả chuyển động cơ mặt do Face Landmarker trả về (52 hệ số) |
| FrameObservation | Schema chung, output của adapter AI, input của engine |
| Adapter | Lớp chuyển output của một model cụ thể sang schema chung |
| Smoothing | Làm mượt đặc trưng theo thời gian để giảm nhiễu |
| Debounce | Chặn cùng một sự kiện lặp lại liên tiếp |
| Hysteresis | Ngưỡng vào khác ngưỡng ra, để trạng thái không dao động quanh ngưỡng |
| Min duration | Thời gian một điều kiện phải giữ liên tục trước khi đổi trạng thái |
| Coverage | Tỷ lệ thời gian hệ thống có đủ dữ liệu quan sát để kết luận |
| Detection latency | Thời gian từ khi hành động bắt đầu (ground truth) tới khi event được tạo |
| Delivery latency | Thời gian từ khi event được lưu tới khi dashboard nhận được |
| False alerts / giờ | Số cảnh báo (MEDIUM/HIGH) sai trên mỗi giờ video |
| Tập dev / tập test | Video dùng hiệu chỉnh ngưỡng / video dùng đánh giá chính thức (chạy với ngưỡng đã chốt) |
| Worker | Tiến trình đọc camera, chạy AI và engine, gửi kết quả lên API |

## Từ cấm trên UI

Không dùng trong text hiển thị cho người dùng (PDF §9.2, §17; HS §4.3, §9.1). Có test tự động quét `web/src/i18n/vi.ts`.

| Không dùng | Lý do | Dùng thay |
|---|---|---|
| chẩn đoán | Hệ thống không chẩn đoán | "đề nghị kiểm tra" |
| đau | Không ước lượng mức đau | "biểu hiện khuôn mặt cần kiểm tra" |
| bất tỉnh, mất ý thức | Không xác định | "không đủ dữ liệu quan sát" / mô tả quan sát |
| té ngã, ngã | Không khẳng định hoàn cảnh (HS dùng "chuyển động bất thường") | "chuyển động bất thường - đề nghị kiểm tra" |
| ngủ, tỉnh | Không phân loại giấc ngủ | "đang nghỉ - dữ liệu tham khảo" / "đang hoạt động" |
| Fall detected, Pain detected | Tiếng Anh và mang tính kết luận | Câu mô tả tiếng Việt |
| Mã nội bộ (`BED_EXIT`…) | Chỉ dùng trong code/DB (PDF §9.3) | Text tiếng Việt từ `vi.ts` |
