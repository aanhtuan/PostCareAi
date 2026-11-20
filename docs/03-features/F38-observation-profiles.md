# F38 – Hồ sơ quan sát camera

| Thuộc tính | Giá trị |
|---|---|
| Mã | F38 |
| Tên | Hồ sơ quan sát camera |
| Trạng thái | In progress |
| Ưu tiên | MVP mở rộng |
| Phụ thuộc | F07, F15, F23, F25, F26, F28 |
| Nguồn | Yêu cầu người dùng 2026-11-21; PRD FR01, FR02, FR12; QA#20, QA#24, QA#29; ADR-0009 |

## 1. Mục tiêu

Cho phép chọn mục tiêu vận hành của từng camera mà không tạo nhãn chẩn đoán hoặc lưu ảnh/video. Ba hồ sơ được chốt trong phiên này:

- **Theo dõi giường**. Dùng vùng giường, state machine tư thế/vị trí và các sự kiện F15.
- **Chuyển động bất thường**. Không bắt buộc vùng giường hoặc phiên theo dõi, dùng người quan sát được trong khung và rule `ABNORMAL_MOVEMENT`. UI mô tả “Chuyển động bất thường - đề nghị kiểm tra”, không dùng nhãn “té ngã” theo ADR-0009.
- **Tín hiệu khuôn mặt**. Không bắt buộc vùng giường hoặc phiên theo dõi. Dùng Face Landmarker và chỉ hiển thị tín hiệu quan sát được. Không nhận diện danh tính, không suy luận danh tính hay chẩn đoán.

## 2. Phạm vi

**Trong phạm vi**

- Lưu hồ sơ theo camera, có audit và `config_version`.
- UI quản trị chọn hồ sơ trong cấu hình camera, hiển thị hướng dẫn ROI tương ứng.
- Worker tải hồ sơ qua config poll và chọn pipeline phù hợp.
- Hồ sơ chuyển động bất thường chạy khi không có ROI. Hồ sơ theo dõi giường vẫn yêu cầu ROI.
- Seed ba camera mẫu với hồ sơ và cấu hình an toàn.
- Replay/probe trên video thật đã có trong `data/external`, ghi rõ kết quả và giới hạn.
- Cảnh báo realtime có fallback polling để không phụ thuộc hoàn toàn vào WebSocket.

**Ngoài phạm vi**

- Đổi tên mã `ABNORMAL_MOVEMENT` thành `FALL` hoặc khẳng định “té ngã” (ADR-0009).
- Huấn luyện/fine-tune model.
- Nhận diện danh tính khuôn mặt.
- Lưu ảnh/video vận hành (QA#29).
- Thông báo mobile ngoài trình duyệt (F33).

## 3. Thiết kế

### 3.1 Hồ sơ và dữ liệu

Thêm enum `ObservationProfile` trong `postcare.schemas` với `BED_MONITORING`, `ABNORMAL_MOVEMENT`, `FACE_SIGNALS`. Thêm cột `cameras.observation_profile` qua migration, mặc định `BED_MONITORING`. API camera chi tiết và config worker trả hồ sơ. Đổi hồ sơ tăng `config_version`, ghi `camera.update_observation_profile` vào audit.

### 3.2 Pipeline

- `BED_MONITORING` giữ pipeline hiện tại và từ chối chạy engine nếu thiếu ROI.
- `ABNORMAL_MOVEMENT` tạo engine với ROI toàn khung hình khi không có ROI và chỉ phát `ABNORMAL_MOVEMENT`. Cần kiểm tra nhiều người và chất lượng quan sát trước khi phát sự kiện. Camera không gắn giường vẫn có thể ghi sự kiện với `bed_id` và `session_id` rỗng. Event code vẫn là `ABNORMAL_MOVEMENT`.
- `FACE_SIGNALS` giữ pose/face gate, phát `FACE_ATTENTION` theo rule hiện tại và không yêu cầu ROI. Khung BLUR vẫn hiển thị khung mới nhất khi không có người. Không thay đổi privacy render F28.

### 3.3 Cảnh báo realtime

Giữ WebSocket là kênh chính. Khi WebSocket không mở, màn hình Cảnh báo và Live View polling danh sách/thông tin mới trong giới hạn hiện có. Toast chỉ hiện cho `alert.created` MEDIUM/HIGH, có liên kết tới chi tiết. Event LOG như `CAMERA_ONLINE` chỉ vào nhật ký.

### 3.4 UI

Trong cấu hình camera, thêm chọn hồ sơ và mô tả tiếng Việt. Live View hiện hồ sơ đang dùng, trạng thái quan sát và cảnh báo phù hợp. Hồ sơ không thay đổi quyền xem hoặc quyền xử lý cảnh báo.

## 4. Acceptance criteria

- [x] AC1: API/DB lưu hồ sơ, mặc định theo dõi giường, audit và tăng phiên bản cấu hình.
- [x] AC2: UI quản trị chọn được ba hồ sơ, hiển thị hướng dẫn ROI đúng hồ sơ.
- [x] AC3: Theo dõi giường giữ nguyên STAND_UP, BED_EDGE, BED_EXIT và yêu cầu ROI.
- [x] AC4: Chuyển động bất thường chạy không cần ROI, phát đúng mã `ABNORMAL_MOVEMENT` với ca âm tính không có chuyển động mạnh.
- [x] AC5: Tín hiệu khuôn mặt chạy không cần ROI, không nhận diện danh tính và có ca âm tính không phát FACE_ATTENTION.
- [x] AC6: BLUR vẫn hiển thị khung khi không có người, dùng fallback render hiện có.
- [x] AC7: Toast MEDIUM/HIGH hiển thị khi WebSocket hoạt động và danh sách vẫn cập nhật khi WebSocket gián đoạn.
- [ ] AC8: Seed có dữ liệu ba hồ sơ và kịch bản cảnh báo. Replay trên ít nhất một video giường, một video rời vùng và một video URFD/CaucaFall được ghi kết quả. Đã chạy URFD `fall-21-cam0-rgb.mp4`: 28 khung, 0 sự kiện, chưa chạy đủ ba nhóm clip.

## 5. Kế hoạch triển khai

1. Test/schema/migration cho enum và cột hồ sơ. Sinh API types sau khi API đổi.
2. Domain/API/worker config và audit. Thêm validation hồ sơ, điều kiện ROI, và test quyền.
3. Engine/pipeline cho hồ sơ không ROI. Viết test âm tính cho nhiều người, không có người, chuyển động bình thường và không có tín hiệu khuôn mặt.
4. UI cấu hình hồ sơ, Live View, fallback cảnh báo và toast. Giữ toàn bộ text trong `vi.ts`.
5. Seed demo và runbook. Chọn fixture nhỏ từ `data/external`, không commit media.
6. Chạy `make check`, `make test-vision`, replay các clip đã chốt, cập nhật báo cáo và review.

## 6. Câu hỏi mở

- Cần chốt chính sách khi hồ sơ `ABNORMAL_MOVEMENT` thấy nhiều người trong khung. Mặc định an toàn là `NO_OBSERVATION` và không phát sự kiện *(giả định)*.
- Đã chốt seed A01 theo dõi giường, A02 chuyển động bất thường, A03 tín hiệu khuôn mặt.
