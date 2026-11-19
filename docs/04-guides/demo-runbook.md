# Demo video có sẵn (lát cắt F30)

Đây là phương án phân tích **video ghi trước**, không phải nghiệm thu webcam realtime,
không phải số liệu đánh giá chính thức hay hoàn thành toàn bộ F30.

## Chuẩn bị

1. Cài dự án theo `dev-setup.md`, migration, dữ liệu nền và model (`make models`).
2. Đặt clip Pexels 8090735 của PNW Production (Pexels License) vào
   `data/external/pexels/pexels-8090735.mp4`, xem nguồn và cách tải ở `datasets.md` §3.4.
   Không đưa video, ảnh người, model, `.env` hoặc DB vào Git.
3. Đặt `DEMO_ENABLED=1` trong `.env`, `API_BASE_URL` trỏ đúng API. Chỉ chạy **một tiến trình
   API** (không `--workers N`, không reload khi clip đang phân tích). API tự dùng Python trong
   venv để mở worker FILE; không cần chạy thêm worker cho camera demo.
4. Khởi động DB, API và web theo `dev-setup.md`. Không chạy `make demo-seed` hoặc reset DB
   cho lát cắt này: trang demo chỉ tạo thêm dữ liệu trong khu vực `DEMO-VIDEO`.

Máy local fresh hiện dùng API 8002 và web 5175; máy khác dùng cổng theo cấu hình của mình.

## Thao tác

1. Đăng nhập ADMIN, mở **Demo video** (`/demo`). Clip ghi rõ nguồn và giới hạn.
2. Bấm **Chuẩn bị giường và vùng giường**. Hệ thống tạo camera FILE, giường và bệnh nhân thử
   nghiệm `DEMO-VIDEO-8090735`, khởi tạo ROI từ `config/cameras/pexels-8090735.yaml`.
   ROI là ước lượng theo clip; những lần chuẩn bị sau giữ ROI và chế độ đã lưu.
3. **Bắt đầu phân tích**: MediaPipe Pose/Face pretrained và engine hiện tại chạy thật, theo
   thời gian clip. Trái giữ chế độ hiển thị camera demo; phải là skeleton + ROI. Có thể chọn
   **Video gốc** cho clip diễn viên nếu cần xem rõ. Lựa chọn này chỉ áp dụng camera demo.
4. Clip dài khoảng 7,7 giây. Bản đã kiểm tra trước có sự kiện **ở mép giường**, chưa có bằng
   chứng **rời vùng giường**. Không thêm sự kiện mẫu và không đổi ngưỡng để tạo kết quả.
5. Hết clip → worker gửi hết sự kiện, ghi marker metadata `.completed` trong `runs/video-demo/`;
   API đóng phiên, hiển thị “Đã phân tích hết, đang đóng video” trong lúc dọn model. Sau khi
   tiến trình thoát mới hiện hoàn tất và cho chạy lại. Đây là dừng dự kiến, không tạo cảnh báo
   mất camera do thời gian dọn tài nguyên.
   Dừng chủ động đóng đúng lượt; **Chạy lại từ đầu** luôn tạo session mới, giữ lịch sử.
6. Điều dưỡng đăng nhập ở cửa sổ khác, vào trang demo để tiếp nhận cảnh báo, ghi kết quả
   dựa trên hình thực tế, thêm ghi chú và xử lý. Mọi vai trò nhân viên xem được kết quả;
   chỉ ADMIN điều khiển video. Cảnh báo chưa xử lý của lượt trước vẫn hiển thị riêng.
7. Bấm **Mở lịch sử theo dõi** hoặc liên kết trong **Lịch sử các lượt demo** để xem đúng
   session và chuỗi sự kiện/thao tác. Không trộn phiên webcam A01 với clip.

## Sự cố

- Không có clip: không khởi động worker; đặt đúng file local như trên. Không nhập đường dẫn
  tùy ý từ trình duyệt và không có upload video trong lát cắt này.
- Lượt thất bại: xem `runs/video-demo/session-<id>.log` trên máy chủ (không commit).
  Kiểm tra model, API_BASE_URL và WORKER_TOKEN; không đưa token vào ảnh chụp/báo cáo.
- Worker kẹt quá `DEMO_MAX_RUN_S` (mặc định 120 giây, gồm thời gian nạp model) → dừng và đánh
  dấu thất bại. Không báo hoàn tất khi còn sự kiện chưa gửi được.
- API tắt bình thường dọn worker. Nếu API bị kill/crash, có thể còn tiến trình con: dừng đúng
  worker demo trước khi đóng phiên bị gián đoạn trên UI và chạy lại. Không dừng worker A01.
- Khi clip dừng/hết, hai khung chuyển thông báo dừng; không tiếp tục phát khung cũ như đang live.
- Khi API tắt đột ngột, trạng thái dựa trên audit là **Phiên bị gián đoạn**; ADMIN cần đóng
  phiên trước lượt mới. Chế độ này chỉ phục vụ local một API process, chưa hỗ trợ nhiều replica.

Webcam thật vẫn cần góc quay trọn giường/toàn thân và ROI riêng theo `camera-setup.md`.
Demo chính, kịch bản phụ, E2E và ba lượt diễn tập đầy đủ của F30 vẫn chưa nghiệm thu.
