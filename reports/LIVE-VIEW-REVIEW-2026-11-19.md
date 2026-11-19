# Rà soát video Live View – 19/11/2026

## Phạm vi và bằng chứng

- Video người dùng cung cấp: `2026-11-19 16-45-01.mp4`, 67,65 giây, 1920×1080, 60 fps.
- Đối chiếu ảnh lấy mẫu khoảng mỗi 6 giây, khung đầy đủ tại giây 39/57 và các khung quanh chuyển trạng thái tại giây 34–40, 50, 53, 55. Đây là rà soát hình ảnh giao diện, không phải đo độ chính xác AI hay kiểm thử toàn bộ vòng đời cảnh báo.
- Source đối chiếu: clone PostCareAI-fresh, main `ebf4866`, spec F07/F28/F21 và component/render liên quan.
- Không sửa code, tài khoản, quyền, chế độ riêng tư, ROI hoặc dữ liệu vận hành. Video và ảnh trích nằm ngoài Git; không đưa vào báo cáo để xuất bản.

## Điều đã thấy hoạt động

- Camera hiển thị hoạt động, hai luồng skeleton cập nhật; tài khoản trong video là vai trò Điều dưỡng.
- Khoảng giây 37–39, giao diện hiện trạng thái Ở mép giường, thông báo cảnh báo với thời điểm sự kiện 16:45:36.
- Đến giây 40, mục Sự kiện gần nhất đã chuyển sang Mức vận động tăng (16:45:37), mức Nhật ký.
- Khoảng giây 55 trở đi, trạng thái chuyển Không đủ dữ liệu quan sát; chất lượng Độ tin cậy thấp. Video chưa cho thấy cảnh báo rời giường.
- Không hiện bộ chọn chế độ với tài khoản Điều dưỡng là đúng F28 R2/R10; không phải bằng chứng chức năng bị mất sau merge.

## Các cập nhật đề xuất

### P1 – Dễ nhận biết dữ liệu quan sát yếu

Ảnh từ khoảng giây 39–57 có phần skeleton bị cắt ở mép khung và các cạnh rất dài; về cuối UI báo độ tin cậy thấp rồi không đủ dữ liệu. Video chỉ có skeleton nên không thể xác định tư thế người thật hoặc kết luận model/engine đúng sai.

`vision/render.py::_draw_person` vẫn nối hai điểm khi cả hai tồn tại; cạnh có visibility thấp được vẽ mờ, không bị bỏ. Đề xuất làm rõ skeleton không đủ tin cậy, cân nhắc bỏ các cạnh không đủ visibility và xử lý rõ điểm ngoài ảnh; kiểm chứng bằng observation gốc trước khi chốt cách sửa. Một số cạnh sáng cũng có hình học bất thường, nên không mặc định lọc visibility sẽ giải quyết hết.

Ưu tiên thực tế: chỉnh camera thấy toàn thân và giường, vẽ lại ROI theo ảnh mới rồi lặp kịch bản có người quan sát. Không hạ ngưỡng engine để buộc có BED_EXIT; mất landmark vẫn phải là NO_OBSERVATION (AGENTS quy tắc 6).

### P1 – Giữ cảnh báo chưa xử lý nổi bật trong Live View (đề xuất mở rộng)

Trong video, sự kiện cảnh báo mép giường bị sự kiện Nhật ký mới hơn thay trong ô Sự kiện gần nhất. Đây phù hợp cách lấy sự kiện mới nhất, không chứng minh cảnh báo đã mất khỏi DB hoặc bị tự xử lý.

`LiveViewPage` dùng `useEvents({bed_id, limit: 1})`. Đề xuất thêm khối Cảnh báo chưa xử lý theo giường, độc lập với Sự kiện gần nhất, có trạng thái tiếp nhận và liên kết tới màn hình Cảnh báo. F21 R2/R3/R5 đã có ý nghĩa cảnh báo mở ở Tổng quan; đưa khối tương ứng vào Live View là mở rộng cần ghi spec F07 trước khi triển khai.

### P2 – Giải thích quyền đổi chế độ ngay cạnh nhãn

Video xác nhận vai trò Điều dưỡng chỉ thấy Chỉ skeleton + ROI. Code UI và API đều chỉ cho ADMIN/CHARGE_NURSE đổi (F28 R2/R10).

Đề xuất thêm câu Chỉ quản trị hoặc điều dưỡng trưởng được đổi chế độ; nêu lựa chọn áp dụng cho khung trái, khung phải luôn là skeleton. Giữ nguyên phân quyền, không cấp thêm quyền cho nurse.

### P2 – Làm rõ hai khung khi bên trái cũng chọn skeleton

Hai khung gần như lặp nội dung vì display_mode đang là SKELETON; đây đúng cấu hình. Khung trái còn có ROI SVG xanh phủ lên ROI đã được worker vẽ trong JPEG; khung phải chỉ có ROI trong JPEG màu vàng.

Đề xuất hiển thị chế độ cụ thể trong tiêu đề bên trái và chỉ vẽ ROI một lần khi JPEG đã là skeleton. Giữ bố cục hai khung theo yêu cầu người dùng; không tự đổi sang RAW/BLUR.

### P2 – Sửa nhãn dữ liệu mô phỏng đang hiển thị cố định

Footer video ghi Bản thử nghiệm - dữ liệu mô phỏng, dù nguồn camera thật đã được xác nhận khi khởi động. `vi.app.prototype` là chuỗi cố định và AppLayout luôn dùng nó.

Đề xuất dùng nhãn chung Bản thử nghiệm; phân biệt riêng nguồn webcam/video/bộ giả lập nếu đã có thông tin nguồn đáng tin cậy. Không gắn nhãn dữ liệu mô phỏng cho toàn bộ ứng dụng chỉ vì bệnh nhân là tài khoản/demo thử nghiệm. Giữ câu công cụ hỗ trợ quan sát, không thay thế quyết định chuyên môn.

## Giới hạn và bước tiếp theo

- Không có ảnh gốc/ground truth đồng thời nên chưa thể đánh giá độ chính xác các nhãn Nằm, Ở mép giường hoặc lý do không có BED_EXIT.
- Clip không cho thấy tiếp nhận, ghi kết quả hoặc timeline; chưa xác nhận trọn chuỗi từ clip này.
- Thứ tự đề xuất: chỉnh góc quay/ROI và kiểm chứng observation; sửa cách thể hiện skeleton yếu; bổ sung cảnh báo mở trong Live View; làm rõ chế độ/quyền và nhãn nguồn.
- Chưa triển khai các đề xuất hoặc đổi ngưỡng. Không chạy lại make check vì phiên này chỉ rà soát video/source và viết tài liệu; không dùng kết quả kiểm tra cũ để khẳng định đã sửa các mục trên.
