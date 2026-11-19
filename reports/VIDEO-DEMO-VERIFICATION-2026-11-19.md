# Kiểm chứng demo video — 19/11/2026

## Phạm vi

Theo yêu cầu dùng video có sẵn trong source làm demo, bổ sung trang `/demo` trong clone
`PostCareAI-fresh`, nhánh `codex/F30-video-demo`. Đây là lát cắt F30 do người dùng yêu cầu,
không hoàn thành F30 toàn phần hay nghiệm thu webcam rời giường.

Nguồn: Pexels 8090735, PNW Production, Pexels License; clip diễn viên dài 7,674 giây.
File video và model giữ local, không đưa lên Git. ROI khởi tạo từ YAML sẵn có, là ước lượng.

## Thay đổi

- Trang Demo video: nguồn/giới hạn rõ ràng, chuẩn bị, bắt đầu, dừng, chạy lại, hai khung
  display/skeleton, cảnh báo chưa xử lý và liên kết lịch sử theo phiên.
- Chỉ ADMIN điều khiển; mọi nhân viên xem, điều dưỡng xử lý cảnh báo theo quyền hiện có.
- API opt-in `DEMO_ENABLED=1`; nguồn cố định, không nhận đường dẫn, không shell, không thêm
  thư viện hay bảng DB. Dữ liệu khu vực/giường/bệnh nhân/camera riêng, tạo thêm trong một transaction.
- Mỗi lần bắt đầu có monitoring session mới. Worker dùng MediaPipe + engine thật và API nội bộ;
  không tạo sẵn cảnh báo hoặc đổi ngưỡng để khớp kịch bản.
- EOF marker báo đã gửi hết sự kiện trước lúc dọn model; API đóng phiên và giữ FINISHING đến
  khi reap process. Timeout/lỗi có trạng thái thất bại. Dừng có kiểm tra session_id để tab cũ
  không đóng lượt mới. Shutdown bình thường dọn worker; crash/restart có trạng thái gián đoạn.

## Bằng chứng runtime

API local 8002, web 5175, DB riêng `postcare_fresh`.

| Kiểm tra | Kết quả |
|---|---|
| Chuẩn bị | Giường 4, camera 2, bệnh nhân 2, mã `DEMO-VIDEO-8090735`; webcam A01 vẫn camera 1 / phiên 1 |
| Hai khung | Browser xác nhận video theo chế độ BLUR và skeleton + ROI cùng lúc, bố cục cạnh nhau ở viewport 930 px |
| Phân tích clip | Phiên 2 tạo BED_EDGE thật; không BED_EXIT |
| Vòng đời cảnh báo | Cảnh báo 40: NURSE `Nguyễn Thị Hoa` tiếp nhận, CONFIRMED kèm ghi chú kiểm thử, resolve; ba request HTTP 200 |
| Timeline | `/timeline?bed=4&session=2`: một event và ba alert_action, tên người thực hiện và ghi chú đầy đủ |
| Chạy lại sau sửa EOF | Phiên 5 COMPLETED; BED_EDGE + CAMERA_ONLINE, không CAMERA_OFFLINE hay BED_EXIT |
| Dừng chủ động | Phiên 6 STOPPED, ended_at có giá trị; lịch sử các phiên trước giữ nguyên |

Lượt 3 từng phát sinh CAMERA_OFFLINE do dọn MediaPipe kéo dài hơn heartbeat timeout. Đã sửa
bằng EOF marker và kiểm chứng lại ở lượt 5. Bản ghi cũ được giữ trong lịch sử, không xóa dữ liệu.
Điều dưỡng đã ghi FALSE_ALARM và xử lý cảnh báo kỹ thuật cũ 45 với ghi chú nguyên nhân/sửa lỗi.
File kiểm chứng JSON/log/marker nằm trong `runs/video-demo/` và ảnh browser giữ ngoài Git.
Đã sao lưu DB local trước khi thêm dữ liệu demo; không reset/seed DB.

## Kiểm tra phần mềm

- Test mục tiêu: 11 backend (quyền, nguồn, vòng đời, cách ly, recovery, timeout, EOF) đạt;
  8 frontend (DemoPage/CameraStream) đạt.
- `make check` bản cuối PASS: format/lint/typecheck/import/API types, 1375 pytest (433,85 s),
  258 Vitest / 35 file và production build.
- `make test-vision`: 5 passed, 1 skipped vì thiếu clip cận mặt, 1375 deselected (5,55 s).
- Tự review quyền/nguồn/process/session/privacy/diff: đạt cho lát cắt local; chưa có review độc lập.
- Sau kiểm tra: health API, web `/demo`, proxy health và API demo đều HTTP 200; phiên A01 vẫn mở.
- Kiểm chứng vision bằng worker thật trên clip ở trên; kết quả không phải đánh giá chính thức.

## Giới hạn và bàn giao

Chỉ hỗ trợ một API process local; không dùng nhiều replica. Nếu API bị kill/crash có thể còn
worker con: kiểm tra/dừng đúng worker demo rồi đóng phiên gián đoạn trước khi chạy lại.
Không cam kết chất lượng phát hiện với clip/góc quay khác; không có bằng chứng BED_EXIT từ clip này.
F30 AC1–AC6, E2E demo chính, kịch bản phụ và ba lượt diễn tập đầy đủ vẫn chưa nghiệm thu.

Hướng dẫn cài nguồn và thao tác: [demo-runbook.md](../docs/04-guides/demo-runbook.md).
