# Xung đột giữa PDF và HS

Theo quy tắc ở [README.md](README.md), **HS được ưu tiên** khi khác với PDF. Bảng dưới liệt kê mọi điểm khác nhau đã phát hiện và cách áp dụng trong dự án.

| # | Chủ đề | PDF nói | HS nói | Áp dụng |
|---|---|---|---|---|
| C01 | Số giường trong MVP | Tổng quan nhiều giường (§3, §9.1); nhiều camera/giường là mở rộng (§18) | Prototype kiểm chứng **trên một giường**; dashboard vẫn thiết kế theo hướng nhiều giường; nhiều camera/giường là mở rộng (§2.2, §9.2) | MVP chạy 1 camera, 1 giường. Data model và dashboard hỗ trợ nhiều giường. Chạy nhiều camera đồng thời: F31 (sau MVP) |
| C02 | Trạng thái nghỉ/hoạt động | Bảng tr.10 xếp **Mở rộng** | Mô tả trong §5.3; lộ trình tuần 7–8 có "mức hoạt động tham khảo" (§7.3) | **Đưa vào MVP** (F27) |
| C03 | Sự kiện "Đứng dậy" | Chỉ có trạng thái Đứng | Bảng §5.1 có sự kiện "đứng dậy" | Thêm sự kiện STAND_UP (F15) |
| C04 | Sự kiện té ngã | "Sự kiện có đặc trưng giống té ngã"; mã ví dụ `FALL_LIKE` (§7.3, §9.3) | "Chuyển động bất thường - đề nghị kiểm tra" khi hạ thấp nhanh, dịch chuyển mạnh hoặc đổi hướng thân đột ngột (§5.2, §4.3) | Mã `ABNORMAL_MOVEMENT`, text theo HS, điều kiện rộng hơn (ADR-0009) |
| C05 | Ưu tiên của sự kiện khuôn mặt | Fusion: sinh "Sự kiện cần chú ý - đề nghị kiểm tra" khi kèm vận động (§7.4) | Mức ưu tiên **tăng** khi tín hiệu mặt đi kèm thay đổi vận động (§5.3) | Một mã `FACE_ATTENTION`; nâng lên HIGH khi kèm vận động HIGH **hoặc** đổi trạng thái cơ thể (gộp HS §5.3 + PDF §7.4; F26) |
| C06 | Kịch bản demo phụ | Kịch bản khuôn mặt + kịch bản privacy (§16) | Kịch bản phụ là các tình huống dễ gây nhầm: thay đổi tư thế, người đi ngang, che camera, mặt quay đi (§8.3) | Demo phụ theo HS (F30). Khuôn mặt và privacy vẫn được kiểm chứng ở F26, F28 |
| C07 | Chỉ số đánh giá | P/R/F1, false alerts/giờ, latency, FPS, CPU/RAM (§13) | Thêm coverage / mất quan sát, frame bỏ, chỉ số workflow; báo cáo TP/FP/FN, thời lượng video, điều kiện camera; chốt ngưỡng trước tập đánh giá (§8.2) | Dùng bộ chỉ số của HS (F16, F29) |
| C08 | Chia tập dữ liệu | Không nói rõ | Tách tập hiệu chỉnh và tập đánh giá; không chia frame của cùng video sang hai tập; tập đánh giá nên có người/phiên khác (§8.1) | Áp dụng HS (F16) |
| C09 | Vị trí camera | Không nói rõ | Tripod/giá có tay vươn, đặt ở đầu giường hoặc lệch một bên, quay chéo từ trên xuống; vị trí cuối chốt qua thử nghiệm; có chống rơi nếu vươn qua giường (§4.1) | Áp dụng HS ([camera-setup.md](../04-guides/camera-setup.md)) |
| C10 | Nguồn camera | Webcam hoặc camera IP (§12) | Smartphone hoặc webcam; DroidCam là một lựa chọn (§1, §4.2); có thể tận dụng smartphone sẵn có khi chủ sở hữu đồng ý (§3) | Hỗ trợ webcam, URL stream (DroidCam / IP Webcam), file video (F05) |
| C11 | Dùng điện thoại của người bệnh | Không đề cập | Chỉ khi có đồng ý rõ ràng và quy trình quản lý thiết bị; triển khai thực tế nên dùng camera chuyên dụng (§6.3, §9.1) | Chỉ ghi trong PRD (giới hạn). Không có feature riêng |
| C12 | Vận hành 24/7 | Không đề cập | Có thể chạy 24/7 nếu camera, máy, mạng ổn định; phụ thuộc điện, mạng, thiết bị (§1, §9.1) | Ghi vào PRD kèm điều kiện. Không đặt chỉ tiêu 24/7 cho prototype |
| C13 | Kiến trúc triển khai | 5 service (§10) | MVP chạy trên một máy, không bắt buộc microservice, ranh giới dữ liệu rõ (§6.1) | Modular monolith (ADR-0001) |
| C14 | Lộ trình | 6 giai đoạn, không có thời lượng (§15.2) | 10 tuần, 5 giai đoạn (§7.3) | Roadmap theo HS. Công cụ eval làm sớm hơn (ADR-0008) |
| C15 | Pháp lý | Cần đánh giá trước khi triển khai thực tế (ghi chú cuối) | Tuân thủ Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP khi triển khai thực tế (§6.3) | Ghi vào PRD (giới hạn, privacy) |
| C16 | Video gốc | Không phải đối tượng lưu trữ chính; ảnh minh chứng là tùy chọn (§10) | Chỉ lưu video gốc khi có mục đích và quyền sử dụng phù hợp (§3) | Không lưu ảnh/video trong vận hành; video test lưu ngoài git (QA#29) |
| C17 | Bàn giao ca và thống kê | Bàn giao ca / thống kê sự kiện là Cốt lõi (bảng tr.10) | Bàn giao ca là nhu cầu chính (§2.2); "dashboard thống kê theo ca" là hướng mở rộng (§9.2) | Bàn giao ca cơ bản: MVP (F24). Dashboard thống kê dài hạn: sau MVP (F34) |

## Các điểm hai nguồn thống nhất (không xung đột)

- Không train model; dùng MediaPipe Pose + Face pretrained; MMPose/RTMPose, Py-Feat là phương án dự phòng.
- Không chẩn đoán, không nhận diện danh tính.
- Vòng đời cảnh báo với 4 kết quả.
- Timeline tiếng Việt.
- Lưu metadata thay vì video.
- Chế độ làm mờ / chỉ skeleton.
- PostgreSQL.
- Debounce, hysteresis, state machine.
- Mất landmark không được coi là rời giường (HS §5.2, phù hợp PDF §4.3).
