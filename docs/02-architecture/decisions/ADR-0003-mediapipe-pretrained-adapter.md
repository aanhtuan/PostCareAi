# ADR-0003: MediaPipe pretrained + adapter + schema chung

- **Trạng thái:** Chấp nhận
- **Ngày:** 2026-10-12
- **Nguồn liên quan:** PDF §6, §10, §17; HS §5.2, §5.3, §5.5, §6.1

## Bối cảnh

Hai nguồn bắt buộc dùng model huấn luyện sẵn, không train và không đổi trọng số. MVP chỉ dùng MediaPipe Pose Landmarker + Face Landmarker. MMPose/RTMPose và Py-Feat chỉ là phương án dự phòng (PDF §6, §17; HS §5.5). PDF §10 yêu cầu Event Engine không phụ thuộc trực tiếp vào API của MediaPipe.

## Quyết định

- Dùng MediaPipe **Tasks API**: `PoseLandmarker` và `FaceLandmarker`, chế độ `VIDEO` với timestamp đơn điệu. Model `.task` tải bằng `make models` vào `models/` (không commit).
- `postcare.vision.inference` chứa các adapter. Adapter chuyển output sang `FrameObservation` (schema trong `postcare.schemas`) với **tên keypoint trung lập**.
- Engine chỉ thấy schema chung. Muốn đổi model thì viết adapter mới, không sửa engine hay frontend.
- Face Landmarker chỉ chạy khi vùng đầu đủ lớn (cắt theo keypoint đầu của pose, *giả định A05*).

## Phương án đã cân nhắc

| Phương án | Ưu | Nhược |
|---|---|---|
| **MediaPipe Tasks** | Nguồn chọn, chạy CPU, có cho Windows/Linux, có blendshape | Kém với người nằm, bị chăn che, góc cao (cần thử) |
| MMPose/RTMPose | Nhiều model, mạnh ở góc khó | Cài đặt nặng (PyTorch), nguồn chỉ coi là dự phòng |
| Py-Feat | Có Action Units, head pose | Thêm framework; nguồn chỉ coi là mở rộng |
| Legacy `mp.solutions` | Nhiều ví dụ cũ | Đã cũ, không phải hướng chính của tài liệu tham khảo |

## Hệ quả

- Rủi ro "pose kém ở góc chéo cao hoặc người nằm" phải đo sớm (F11). Khi pose không tin cậy, hệ thống báo NO_OBSERVATION.
- Python bị khóa ở 3.12 để có wheel mediapipe ổn định *(giả định)*.
