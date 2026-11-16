# POSTCARE AI - BÁO CÁO Ý TƯỞNG AI FOR LIFE

> **Ghi chú chuyển đổi:** Bản Markdown của [de-tai.pdf](de-tai.pdf) (21 trang), trích bằng `pdftotext` và biên tập lại.
> - Nội dung giữ nguyên câu chữ gốc. Chỉ nối lại các dòng bị ngắt và bỏ header/footer lặp lại ở mỗi trang.
> - Dấu `<!-- Trang N -->` đánh dấu nơi bắt đầu trang N theo số in ở chân trang PDF.
> - Các bảng ở trang 10, 15 và 19 bị vỡ cột khi trích xuất và đã được **dựng lại**. Nếu nghi ngờ, đối chiếu với PDF gốc.
> - Khi xung đột với [ho-so-so-loai-2026.md](ho-so-so-loai-2026.md), áp dụng hồ sơ sơ loại (xem [conflicts.md](conflicts.md)).

<!-- Trang 1 -->

## Trang bìa

BÁO CÁO Ý TƯỞNG DỰ THI AI FOR LIFE

**POSTCARE AI**

Hệ thống AI hỗ trợ giám sát bệnh nhân hậu phẫu và phát hiện sớm các sự kiện cần chú ý

Định hướng: Software Engineering ứng dụng Computer Vision
Sử dụng mô hình huấn luyện sẵn - không tự huấn luyện mô hình

Nhóm thực hiện: ............................................................
Giảng viên hướng dẫn: .....................................................

Thời gian: 10/2026

*Chân trang (lặp lại ở mọi trang): PostCare AI | Prototype hỗ trợ giám sát - không thay thế quyết định chuyên môn*

<!-- Trang 2 -->

## MỤC LỤC NỘI DUNG

1. Tóm tắt ý tưởng
2. Bối cảnh và vấn đề cần giải quyết
3. Đối tượng sử dụng và nhu cầu
4. Mục tiêu, phạm vi và nguyên tắc thiết kế
5. Giải pháp tổng thể và quy trình vận hành
6. Thiết kế khối AI không cần huấn luyện
7. Event Detection Engine - phần lõi của sản phẩm
8. Hệ thống chức năng và mức độ khả thi
9. Thiết kế ứng dụng tiếng Việt và luồng sử dụng
10. Kiến trúc phần mềm dự kiến
11. Dữ liệu, quyền riêng tư và an toàn
12. Tính khả thi về nguồn lực và triển khai
13. Kế hoạch kiểm thử và đánh giá
14. Tính khác biệt và giá trị cạnh tranh
15. Phạm vi MVP và lộ trình triển khai
16. Kịch bản demo vòng trong
17. Rủi ro và phương án giảm thiểu
18. Định hướng mở rộng
19. Đối chiếu tiêu chí vòng sơ tuyển
20. Kết luận

Tài liệu tham khảo

<!-- Trang 3 -->

## 1. TÓM TẮT Ý TƯỞNG

PostCare AI là hệ thống phần mềm ứng dụng trí tuệ nhân tạo nhằm hỗ trợ nhân viên y tế giám sát bệnh nhân trong giai đoạn hậu phẫu. Hệ thống sử dụng camera tại khu vực giường bệnh, kết hợp Computer Vision và cơ chế phát hiện sự kiện theo thời gian để ghi nhận những thay đổi về tư thế, vận động và một số dấu hiệu biểu cảm có thể quan sát được trên khuôn mặt. Thay vì yêu cầu điều dưỡng liên tục theo dõi nhiều màn hình camera, PostCare AI chuyển luồng video thành các sự kiện có cấu trúc, xác định mức độ ưu tiên, gửi cảnh báo và xây dựng timeline theo dõi cho từng bệnh nhân.

Điểm cốt lõi của đề tài không nằm ở việc tự nghiên cứu hay huấn luyện một mô hình AI mới. PostCare AI được định hướng đúng với vai trò của một dự án Software Engineering: sử dụng các mô hình đã được huấn luyện sẵn để thực hiện phần nhận biết hình ảnh, sau đó tập trung vào tích hợp hệ thống, xử lý chuỗi thời gian, phát hiện sự kiện, cảnh báo thời gian thực, xác nhận của người dùng, quản lý lịch sử, quyền riêng tư, kiểm thử và đánh giá. Cách tiếp cận này giúp đề tài vừa có AI đủ rõ, vừa có khối lượng kỹ thuật phần mềm đủ sâu và phù hợp với nguồn lực sinh viên.

Các tình huống trọng tâm của phiên bản đầu gồm bệnh nhân ngồi dậy, di chuyển tới mép giường, rời khỏi giường, quay lại giường, thay đổi tư thế, ít hoặc tăng vận động bất thường và các chuyển động có đặc trưng giống tình huống té ngã. Ở nhánh khuôn mặt, hệ thống chỉ ghi nhận những tín hiệu có thể quan sát tương đối trực tiếp như mắt đóng/mở, nhắm mắt kéo dài, hạ lông mày, nheo hoặc siết vùng mắt, thay đổi vùng mũi và miệng. Những tín hiệu này được xem là dữ liệu hỗ trợ; hệ thống không tự kết luận bệnh nhân đang đau ở mức độ nào, không chẩn đoán bệnh và không xác định mất ý thức.

> GIÁM SÁT → PHÂN TÍCH AI → PHÁT HIỆN SỰ KIỆN → CẢNH BÁO → XÁC NHẬN → GHI NHẬN → TỔNG HỢP

> **Tuyên bố định vị sản phẩm**
> PostCare AI là công cụ hỗ trợ giám sát và quản lý sự kiện hậu phẫu. AI giúp phát hiện và ưu tiên tình huống cần chú ý; nhân viên y tế vẫn là người kiểm tra thực tế và đưa ra quyết định chuyên môn cuối cùng.

## 2. BỐI CẢNH VÀ VẤN ĐỀ CẦN GIẢI QUYẾT

Trong môi trường bệnh viện, té ngã và các tình huống mất an toàn khi vận động là vấn đề được quan tâm trong chăm sóc người bệnh. WHO xem té ngã là một nguyên nhân

<!-- Trang 4 -->

quan trọng gây chấn thương trên toàn cầu, còn AHRQ duy trì các chương trình phòng ngừa té ngã trong bệnh viện và nhấn mạnh vai trò của quy trình chăm sóc, đánh giá nguy cơ và phối hợp của đội ngũ y tế. PostCare AI không tuyên bố thay thế các quy trình đó; đề tài chỉ tập trung vào một lớp hỗ trợ quan sát bằng camera để nhân viên y tế có thêm thông tin đúng thời điểm.

Trong giai đoạn hậu phẫu, người bệnh có thể thay đổi tư thế, cố gắng ngồi dậy hoặc rời khỏi giường. Một số hành động là bình thường, một số hành động cần hỗ trợ, và ý nghĩa thực tế phụ thuộc vào tình trạng từng bệnh nhân. Trong khi đó, điều dưỡng thường phải đồng thời thực hiện nhiều nhiệm vụ như chăm sóc, theo dõi chỉ số, hỗ trợ vận động, ghi nhận diễn biến và bàn giao ca. Việc quan sát trực tiếp liên tục một bệnh nhân trong suốt nhiều giờ là khó thực hiện, đặc biệt khi phải theo dõi nhiều giường cùng lúc.

Camera giám sát có thể mở rộng khả năng quan sát nhưng bản thân camera chỉ cung cấp hình ảnh. Nếu hệ thống chỉ phát video lên màn hình, người dùng vẫn phải liên tục nhìn camera để tự phát hiện thời điểm có sự kiện. Mặt khác, việc tìm lại một sự kiện trong nhiều giờ video cũng tốn thời gian. Vấn đề cốt lõi vì vậy không phải là thiếu video, mà là thiếu một lớp phần mềm có khả năng biến video liên tục thành thông tin ngắn gọn, có cấu trúc và có thể hành động.

PostCare AI giải quyết khoảng trống này bằng cách quan sát thay cho con người ở mức sơ bộ: AI trích xuất tư thế và các đặc trưng khuôn mặt, Event Detection Engine theo dõi biến đổi theo thời gian, còn hệ thống nghiệp vụ biến kết quả thành cảnh báo và lịch sử theo dõi. Người dùng không cần xem mọi frame; họ được thông báo khi một chuỗi hành vi đạt điều kiện đã định nghĩa.

## 3. ĐỐI TƯỢNG SỬ DỤNG VÀ NHU CẦU

Đối tượng sử dụng chính của PostCare AI là điều dưỡng và nhân viên y tế phụ trách khu vực hậu phẫu. Họ cần biết giường nào đang có sự kiện cần chú ý, sự kiện xảy ra lúc nào, mức ưu tiên ra sao, cảnh báo đã có ai tiếp nhận hay chưa và kết quả kiểm tra thực tế là gì. Vì vậy giao diện phải ưu tiên thông tin ngắn gọn, dễ đọc, dùng tiếng Việt và giảm tối đa thao tác không cần thiết.

Đối tượng sử dụng thứ hai là người phụ trách ca hoặc quản lý khu vực. Nhóm người dùng này cần xem tổng quan nhiều giường, biết cảnh báo nào chưa xử lý, xem lịch sử sự kiện và hỗ trợ bàn giao ca. Họ không nhất thiết cần xem toàn bộ video; điều quan trọng hơn là timeline và trạng thái xử lý của từng sự kiện.

<!-- Trang 5 -->

Bác sĩ hoặc nhân viên có thẩm quyền có thể tra cứu timeline như một nguồn thông tin bổ sung khi cần xem lại diễn biến quan sát được. Tuy nhiên PostCare AI không được coi là hồ sơ bệnh án chính thức và không thay thế dữ liệu lâm sàng từ hệ thống bệnh viện.

Về nhu cầu sử dụng, sản phẩm cần đáp ứng bốn yêu cầu lớn: giảm nhu cầu theo dõi camera liên tục; phát hiện và cảnh báo theo sự kiện; hỗ trợ xác nhận - bác bỏ cảnh báo bởi con người; và tự động lưu lại lịch sử để có thể tra cứu hoặc tổng hợp. Đây là các nhu cầu trực tiếp mà một hệ thống Software Engineering có thể giải quyết bằng cách kết hợp AI với workflow.

## 4. MỤC TIÊU, PHẠM VI VÀ NGUYÊN TẮC THIẾT KẾ

### 4.1. Mục tiêu tổng quát

Mục tiêu của đề tài là xây dựng một prototype có thể chạy được từ đầu đến cuối: nhận video từ camera, phân tích tư thế và khuôn mặt bằng mô hình huấn luyện sẵn, phát hiện một số sự kiện định nghĩa trước, gửi cảnh báo tới giao diện tiếng Việt, cho phép nhân viên y tế xác nhận kết quả và tự động tạo timeline. Prototype phải chứng minh được AI thực sự tham gia vào giải pháp, nhưng giá trị cuối cùng được thể hiện qua quy trình phần mềm hoàn chỉnh chứ không chỉ qua hình ảnh skeleton trên màn hình.

### 4.2. Phạm vi chủ động giới hạn

Đề tài không tự huấn luyện model, không xây dựng mô hình chẩn đoán, không dự đoán biến chứng, không ước lượng mức đau lâm sàng, không nhận diện danh tính bệnh nhân bằng khuôn mặt và không cố xác định trạng thái ngủ/tỉnh theo nghĩa y khoa. Những giới hạn này là chủ động nhằm giữ tính khả thi và tránh đưa ra tuyên bố vượt quá những gì camera RGB và mô hình huấn luyện sẵn có thể chứng minh trong phạm vi đồ án.

Thay cho Face Recognition, bệnh nhân được gắn với một giường và một phiên theo dõi. Ví dụ Camera 03 được cấu hình cho Giường A03; trong thời gian theo dõi, Giường A03 được gán cho một mã bệnh nhân. Các sự kiện xảy ra trong vùng giường này được gắn với phiên theo dõi tương ứng. Cách làm này đơn giản hơn, giảm dữ liệu sinh trắc học và phù hợp hơn với bài toán.

### 4.3. Nguyên tắc thiết kế

- AI chỉ cung cấp tín hiệu quan sát và ứng viên sự kiện; người dùng xác nhận kết quả cuối cùng.

<!-- Trang 6 -->

- Không tạo cảnh báo từ một frame đơn lẻ; mọi sự kiện quan trọng phải được đánh giá theo thời gian.
- Hệ thống ưu tiên lưu metadata sự kiện thay vì lưu video liên tục.
- Khi AI không đủ tin cậy, hệ thống phải thể hiện trạng thái "Không đủ dữ liệu quan sát" thay vì cố đưa ra kết luận.
- Giao diện ứng dụng sử dụng tiếng Việt, tên trạng thái và nút thao tác phải rõ nghĩa đối với người dùng.
- MVP phải hoàn chỉnh theo chiều dọc từ camera đến timeline trước khi mở rộng thêm chức năng.

## 5. GIẢI PHÁP TỔNG THỂ VÀ QUY TRÌNH VẬN HÀNH

Hệ thống bắt đầu từ camera hoặc video thử nghiệm. Luồng hình ảnh được chuyển tới AI Inference Service. Tại đây, nhánh phân tích cơ thể tạo ra các landmark tư thế, còn nhánh phân tích khuôn mặt tạo ra các landmark và blendshape cần thiết. Kết quả của hai nhánh được chuẩn hóa thành AI Features, sau đó truyền tới Temporal Processing Layer.

Temporal Processing Layer thực hiện smoothing, kiểm tra độ tin cậy, theo dõi biến đổi giữa các frame và duy trì trạng thái hiện tại. Ví dụ, nếu mô hình chỉ nhận "ngồi" trong một frame rồi ngay lập tức quay về "nằm", kết quả này có thể bị loại bỏ như nhiễu. Nếu trạng thái ngồi duy trì đủ lâu và đi kèm sự thay đổi hợp lý của thân người, hệ thống mới chuyển trạng thái.

Event Detection Engine nhận chuỗi trạng thái, vùng giường và tín hiệu khuôn mặt để quyết định sự kiện. Sự kiện sau đó được Alert Service đánh mức ưu tiên và gửi lên giao diện. Điều dưỡng chọn "Đã tiếp nhận" để nhận trách nhiệm xử lý. Sau khi kiểm tra, người dùng có thể chọn "Xác nhận đúng", "Cảnh báo sai", "Bệnh nhân an toàn" hoặc "Đã xử lý", đồng thời thêm ghi chú khi cần.

Mọi thay đổi của vòng đời sự kiện được lưu vào cơ sở dữ liệu. Nhờ đó một cảnh báo không chỉ tồn tại dưới dạng thông báo tạm thời mà trở thành một bản ghi có thể truy vết: được phát hiện lúc nào, ai tiếp nhận, kết quả xác nhận là gì và xử lý khi nào. Đây là nền tảng để xây dựng timeline và báo cáo bàn giao ca.

> CAMERA → AI FEATURES → XỬ LÝ THEO THỜI GIAN → EVENT ENGINE → CẢNH BÁO → XÁC NHẬN CON NGƯỜI → TIMELINE

<!-- Trang 7 -->

## 6. THIẾT KẾ KHỐI AI KHÔNG CẦN HUẤN LUYỆN

### 6.1. Phân tích cơ thể bằng MediaPipe Pose Landmarker

Phiên bản MVP ưu tiên MediaPipe Pose Landmarker vì mô hình có sẵn, hỗ trợ chạy trên ảnh, video và luồng trực tiếp, đồng thời trả về 33 landmark cơ thể. Các landmark bao gồm những vị trí quan trọng như vai, hông, đầu gối, cổ chân và bàn chân. Dữ liệu này đủ để xây dựng nhiều rule về hướng thân người, độ cao của hông, vị trí chân và chuyển động tương đối với giường mà không cần huấn luyện thêm một classifier.

Từ landmark, hệ thống tính các đặc trưng như hip center, shoulder center, góc thân, độ cao tương đối của vai - hông - đầu gối, tốc độ thay đổi vị trí và khoảng cách tới ranh giới vùng giường. Các đặc trưng được dùng để xác định những trạng thái quan sát như nằm, đang nâng thân, ngồi, đứng và ở ngoài giường. Đây là classification ở lớp logic của hệ thống, không phải model học máy mới.

Nếu trong giai đoạn sau MediaPipe không đáp ứng đủ một số tình huống nhiều người hoặc góc camera phức tạp, MMPose/RTMPose có thể được khảo sát như phương án thay thế vì thư viện cung cấp nhiều model pretrained và giao diện inference cho ảnh/video. Tuy nhiên đây là phương án dự phòng; MVP không nên bắt đầu bằng việc tích hợp quá nhiều framework.

### 6.2. Phân tích khuôn mặt bằng MediaPipe Face Landmarker

MediaPipe Face Landmarker được chọn làm công nghệ chính cho nhánh khuôn mặt vì có thể chạy ở chế độ video/live stream và có thể xuất các hệ số blendshape. Tài liệu chính thức mô tả 52 blendshape coefficients, trong đó có các tín hiệu phù hợp với mục tiêu quan sát như hạ lông mày, chớp/nhắm mắt, nheo mắt, mở hàm, thay đổi vùng miệng và nhăn mũi. PostCare AI chỉ sử dụng một tập con cần thiết thay vì cố phân tích toàn bộ biểu cảm.

Các tín hiệu khuôn mặt dự kiến sử dụng gồm trạng thái mắt đóng/mở, thời gian nhắm mắt kéo dài, mức hạ lông mày, mức nheo/siết vùng mắt, chuyển động vùng mũi và một số thay đổi vùng miệng. Hệ thống không gán nhãn trực tiếp "đau", "mất ý thức" hay "ngủ". Khi nhiều tín hiệu xuất hiện đồng thời và duy trì trong một khoảng thời gian, Event Engine có thể tạo sự kiện "Biểu hiện khuôn mặt cần kiểm tra".

Py-Feat có thể được dùng ở giai đoạn mở rộng hoặc kiểm chứng bổ sung nếu nhóm cần Action Units, head pose hoặc thông tin hành vi khuôn mặt chi tiết hơn. Tài liệu Py-Feat cho thấy Detectorv2 có thể chạy bằng pretrained weights và trả về Action Units, cảm

<!-- Trang 8 -->

xúc, gaze, head pose và FaceMesh. Tuy nhiên để giảm rủi ro tích hợp, MVP nên ưu tiên một face pipeline duy nhất trước.

### 6.3. Theo dõi trạng thái nghỉ/hoạt động

Yêu cầu ban đầu về theo dõi tỉnh/ngủ được tinh chỉnh thành một chức năng an toàn hơn về mặt diễn đạt: hệ thống chỉ ghi nhận mức hoạt động và trạng thái mắt theo thời gian. Khi cơ thể gần như không chuyển động và mắt đóng kéo dài, giao diện có thể hiển thị "Đang nghỉ - dữ liệu tham khảo". Khi chuyển động tăng hoặc mắt mở trở lại, hệ thống chuyển về "Đang hoạt động". Đây không phải phân loại giấc ngủ và không thay thế phương pháp đánh giá y khoa.

## 7. EVENT DETECTION ENGINE - PHẦN LÕI CỦA SẢN PHẨM

Nếu chỉ gọi model trên từng frame, PostCare AI sẽ không khác nhiều so với một demo Computer Vision. Phần tạo nên giá trị Software Engineering là Event Detection Engine: thành phần biến output AI thành trạng thái và sự kiện có ý nghĩa. Event Engine hoạt động theo nguyên tắc "không tin một frame đơn lẻ", luôn đánh giá lịch sử ngắn hạn trước khi phát sinh cảnh báo.

Một state machine có thể duy trì các trạng thái như Nằm, Đang nâng thân, Ngồi, Ở mép giường, Đứng, Ngoài giường và Không đủ dữ liệu quan sát. Mỗi chuyển trạng thái cần thỏa mãn điều kiện về landmark, vị trí trong Bed ROI, thời gian duy trì và confidence. Cách làm này vừa dễ giải thích với giám khảo vừa dễ kiểm thử vì từng rule có thể được mô tả rõ ràng.

Debounce được sử dụng để ngăn cùng một sự kiện tạo nhiều cảnh báo liên tiếp. Hysteresis giúp tránh trạng thái dao động quanh ngưỡng. Ví dụ nếu góc thân liên tục nằm gần ranh giới giữa "nằm" và "ngồi", hệ thống không đổi trạng thái ở mỗi frame mà cần vượt ngưỡng xác nhận và duy trì đủ thời gian.

Mỗi event có thể có mức ưu tiên. "Thay đổi tư thế" chỉ cần lưu nhật ký. "Ngồi dậy" có thể ở mức thông tin hoặc thấp. "Ở mép giường" có thể ở mức trung bình. "Rời giường" hoặc "Sự kiện có đặc trưng giống té ngã" được ưu tiên cao hơn. Đây là mức ưu tiên của workflow phần mềm, không phải phân tầng nguy cơ lâm sàng.

### 7.1. Phát hiện ngồi dậy

Sự kiện "Ngồi dậy" được phát hiện khi trạng thái thay đổi theo chuỗi hợp lý từ Nằm sang Đang nâng thân rồi sang Ngồi. Hệ thống quan sát sự thay đổi của góc thân, độ cao

<!-- Trang 9 -->

vai so với hông và vị trí hông trong Bed ROI. Khi trạng thái Ngồi được duy trì đủ thời gian, sự kiện được ghi vào timeline. Nếu người bệnh chỉ nhúc nhích hoặc model sai trong vài frame, event không được tạo.

### 7.2. Phát hiện ở mép giường và rời giường

Bed ROI được cấu hình dưới dạng polygon khi cài camera. Event Engine theo dõi hip center/body center so với polygon và ranh giới của giường. Trạng thái "Ở mép giường" xuất hiện khi cơ thể đã chuyển về rìa, có tín hiệu ngồi/đứng và một phần chân hoặc body center tiến gần ra ngoài vùng. Trạng thái "Rời giường" chỉ được xác nhận khi cơ thể thực sự ra khỏi Bed ROI hoặc vượt qua ngưỡng vị trí đã định nghĩa.

Chuỗi Nằm → Ngồi dậy → Ở mép giường → Đứng → Rời giường giúp hệ thống có ngữ cảnh tốt hơn so với việc chỉ kiểm tra một bounding box có nằm ngoài giường hay không. Nếu bệnh nhân ngồi dậy rồi nằm lại, hệ thống không tạo cảnh báo rời giường.

### 7.3. Phát hiện sự kiện có đặc trưng giống té ngã

Sự kiện này được thiết kế thận trọng và không dùng tên "chẩn đoán té ngã". Event Engine kết hợp tốc độ giảm của hip center/body center, thay đổi góc thân, mức dịch chuyển trong thời gian ngắn, vị trí cuối cùng gần vùng thấp và trạng thái duy trì sau chuyển động. Nếu nhiều điều kiện cùng xuất hiện, hệ thống tạo "Cảnh báo chuyển động bất thường - nghi sự kiện té ngã" để yêu cầu kiểm tra.

Cách diễn đạt trên phản ánh đúng giới hạn của prototype: camera có thể phát hiện một pattern vận động đáng chú ý nhưng không đủ để tự khẳng định hoàn cảnh hoặc hậu quả lâm sàng. Nhân viên y tế vẫn phải kiểm tra và xác nhận.

### 7.4. Kết hợp tín hiệu cơ thể và khuôn mặt

Không phải mọi tín hiệu khuôn mặt đều tạo cảnh báo. Nếu bệnh nhân nằm ổn định và chỉ hạ lông mày trong thời gian ngắn, hệ thống chỉ lưu hoặc bỏ qua. Nếu đồng thời xuất hiện mức vận động tăng, cơ thể chuyển trạng thái và có nhiều dấu hiệu khuôn mặt kéo dài, Event Engine có thể tạo "Sự kiện cần chú ý - đề nghị kiểm tra". Cách fusion này giúp facial analysis trở thành thông tin bổ sung thay vì một hệ thống chẩn đoán độc lập.

## 8. HỆ THỐNG CHỨC NĂNG VÀ MỨC ĐỘ KHẢ THI

Bảng dưới đây là phạm vi chức năng được tinh chỉnh cho phiên bản dự thi. Cột "Khả thi" đánh giá khả năng triển khai trực tiếp bằng mô hình huấn luyện sẵn và logic phần

<!-- Trang 10 -->

mềm, không phải độ chính xác lâm sàng. Các chức năng "Cốt lõi" cần hoàn thành trước; "Mở rộng" chỉ thực hiện nếu MVP đã ổn định.

> *Bảng dựng lại từ văn bản trích xuất bị vỡ cột. Nên đối chiếu với PDF.*

| Chức năng | Cách thực hiện / mô hình | Tự huấn luyện? | Khả thi | Mức ưu tiên |
|---|---|---|---|---|
| Nhận luồng camera/video | OpenCV/RTSP | Không | Rất cao | Cốt lõi |
| Cấu hình vùng giường | Polygon ROI + OpenCV | Không | Rất cao | Cốt lõi |
| Pose và 33 landmark cơ thể | MediaPipe Pose Landmarker | Không | Rất cao | Cốt lõi |
| Nằm / ngồi / đứng | Pose + rule + temporal smoothing | Không | Cao | Cốt lõi |
| Ngồi dậy | Pose + state machine | Không | Cao | Cốt lõi |
| Ở mép giường | Pose + Bed ROI | Không | Cao | Cốt lõi |
| Rời giường / quay lại giường | Pose + Bed ROI + state machine | Không | Rất cao | Cốt lõi |
| Thay đổi tư thế / mức vận động | Pose delta theo thời gian | Không | Cao | Cốt lõi |
| Sự kiện có đặc trưng giống té ngã | Pose + tốc độ + góc thân + rule | Không | Trung bình - cao | Cốt lõi có giới hạn |
| Face landmarks / blendshapes | MediaPipe Face Landmarker | Không | Rất cao | Cốt lõi |
| Mắt đóng/mở, nhắm mắt kéo dài | Face blendshapes + timer | Không | Cao | Cốt lõi |
| Hạ lông mày / nheo mắt / thay đổi vùng mũi-miệng | Face blendshapes | Không | Cao khi thấy rõ mặt | Cốt lõi giới hạn |
| Biểu hiện khuôn mặt cần kiểm tra | Kết hợp blendshapes + temporal rule | Không | Trung bình | Cốt lõi có giới hạn |
| Trạng thái nghỉ/hoạt động tham khảo | Mắt + mức vận động | Không | Trung bình - cao | Mở rộng |
| Cảnh báo thời gian thực | WebSocket / FCM | Không | Rất cao | Cốt lõi |
| Đã tiếp nhận / xác nhận / cảnh báo sai / đã xử lý | Backend workflow | Không | Rất cao | Cốt lõi |
| Timeline bệnh nhân | PostgreSQL + API | Không | Rất cao | Cốt lõi |
| Bàn giao ca / thống kê sự kiện | SQL aggregation | Không | Rất cao | Cốt lõi |
| Chế độ làm mờ / chỉ hiển thị skeleton | OpenCV + landmarks | Không | Rất cao | Cốt lõi privacy |
| Tự học từ phản hồi người dùng | Cần training/fine-tuning | Có | Không làm trong đề tài | Không triển khai |
| Nhận diện danh tính bằng khuôn mặt | Không cần cho bài toán | Không cần | Không cần thiết | Không triển khai |
| Chẩn đoán đau / mất ý thức / biến chứng | Không phù hợp với phạm vi | - | Không tuyên bố | Không triển khai |

<!-- Trang 11 -->

## 9. THIẾT KẾ ỨNG DỤNG TIẾNG VIỆT VÀ LUỒNG SỬ DỤNG

Toàn bộ giao diện của prototype được định hướng bằng tiếng Việt. Điều này không chỉ đáp ứng yêu cầu trình bày mà còn giúp sản phẩm gần với bối cảnh sử dụng thực tế hơn. Tên màn hình, trạng thái, mức cảnh báo và nút thao tác cần tránh thuật ngữ kỹ thuật không cần thiết.

### 9.1. Các màn hình chính

- "Tổng quan": hiển thị danh sách giường, trạng thái theo dõi, số cảnh báo đang chờ và mức ưu tiên.
- "Theo dõi trực tiếp": hiển thị camera hoặc chế độ skeleton, trạng thái cơ thể hiện tại, chất lượng quan sát và sự kiện gần nhất.
- "Cảnh báo": danh sách cảnh báo theo thời gian, giường, mức ưu tiên và trạng thái xử lý.
- "Lịch sử bệnh nhân": timeline các sự kiện đã ghi nhận trong phiên theo dõi.
- "Bàn giao ca": tổng hợp sự kiện theo ca, cảnh báo đã/ chưa xử lý, số lần thay đổi trạng thái.
- "Quản lý giường": cấu hình giường, camera, bệnh nhân hiện tại và phiên theo dõi.
- "Cấu hình camera": thiết lập vùng giường, ngưỡng quan sát và kiểm tra chất lượng hình ảnh.

### 9.2. Ngôn ngữ cảnh báo

Ứng dụng không hiển thị "Fall detected" hay "Pain detected". Thay vào đó, thông báo được viết theo hướng mô tả điều hệ thống quan sát được. Ví dụ: "Bệnh nhân rời khỏi vùng giường", "Bệnh nhân đang ở mép giường", "Phát hiện chuyển động bất thường - đề nghị kiểm tra", "Phát hiện biểu hiện khuôn mặt cần kiểm tra", hoặc "Không đủ dữ liệu quan sát".

> **Ví dụ cảnh báo trên giao diện**
> Giường A03 - Cảnh báo ưu tiên cao
> Phát hiện bệnh nhân rời khỏi vùng giường lúc 14:38:34.
> Thao tác: [Đã tiếp nhận] [Xem chi tiết]
> Sau khi kiểm tra: [Xác nhận đúng] [Cảnh báo sai] [Bệnh nhân an toàn] [Đã xử lý]

<!-- Trang 12 -->

### 9.3. Timeline bằng tiếng Việt

Timeline cũng dùng mô tả dễ hiểu thay vì mã kỹ thuật nội bộ. Ví dụ: "14:38:12 - Bệnh nhân ngồi dậy", "14:38:26 - Bệnh nhân ở mép giường", "14:38:34 - Bệnh nhân rời khỏi vùng giường", "14:38:41 - Điều dưỡng đã tiếp nhận cảnh báo", "14:39:53 - Hỗ trợ bệnh nhân trở lại giường", "14:40:05 - Sự kiện đã xử lý". Các mã nội bộ như BED_EXIT hoặc FALL_LIKE chỉ được dùng trong code/database.

## 10. KIẾN TRÚC PHẦN MỀM DỰ KIẾN

Kiến trúc được chia thành các module để phần AI có thể thay đổi mà không làm ảnh hưởng lớn tới phần nghiệp vụ. Camera Service chịu trách nhiệm nhận stream, lấy frame và theo dõi trạng thái kết nối. AI Inference Service nhận frame và trả về một cấu trúc dữ liệu thống nhất gồm pose landmarks, face features và confidence. Event Service xử lý chuỗi thời gian, state machine và tạo event. Backend quản lý bệnh nhân, giường, phiên theo dõi, cảnh báo, timeline và người dùng. Realtime Gateway đẩy thay đổi lên frontend qua WebSocket.

Một interface rõ ràng giữa AI Inference Service và Event Service là điểm quan trọng. Event Engine không nên phụ thuộc trực tiếp vào API cụ thể của MediaPipe. Thay vào đó, inference adapter chuyển output model thành một schema chung. Nếu sau này cần thay MediaPipe Pose bằng RTMPose, nhóm chỉ thay adapter, còn business logic và frontend giữ nguyên. Đây là cách thiết kế phù hợp với tư duy bảo trì và mở rộng của Software Engineering.

Cơ sở dữ liệu dự kiến dùng PostgreSQL vì dữ liệu chính có cấu trúc và nhiều quan hệ: bệnh nhân - giường - camera - phiên theo dõi - sự kiện - cảnh báo - người dùng - audit log. Video raw không phải đối tượng lưu trữ chính. Nếu cần lưu một ảnh minh chứng cho event, đây sẽ là dữ liệu tùy chọn với chính sách riêng.

### 10.1. Các thực thể dữ liệu chính

- Bệnh nhân: mã bệnh nhân thử nghiệm, thông tin tối thiểu cần cho prototype.
- Giường: mã giường, khu vực, camera liên kết, trạng thái hoạt động.
- Phiên theo dõi: bệnh nhân nào đang được theo dõi ở giường nào, bắt đầu và kết thúc lúc nào.
- Sự kiện: loại sự kiện, thời điểm, mức ưu tiên, confidence, dữ liệu giải thích tối thiểu.
- Cảnh báo: trạng thái gửi, thời gian tiếp nhận, người tiếp nhận và kết quả xử lý.

<!-- Trang 13 -->

- Nhật ký thao tác: ai đã thay đổi trạng thái nào, vào thời điểm nào.

## 11. DỮ LIỆU, QUYỀN RIÊNG TƯ VÀ AN TOÀN

Video trong bối cảnh chăm sóc sức khỏe là dữ liệu nhạy cảm, do đó PostCare AI áp dụng nguyên tắc tối thiểu hóa dữ liệu ngay từ thiết kế. Mục tiêu là xử lý hình ảnh để tạo event rồi ưu tiên lưu metadata, thay vì xây một kho video liên tục. Cách làm này vừa giảm dung lượng vừa giảm lượng dữ liệu hình ảnh phải quản lý.

Trong prototype, dữ liệu test được tạo từ tình huống mô phỏng có sự đồng ý của người tham gia, không sử dụng video bệnh nhân thật. Camera có thể chạy trong phòng mô phỏng hoặc khu vực được bố trí giống một giường bệnh. Đây là cách tiếp cận khả thi cho giai đoạn dự thi và tránh phụ thuộc vào quyền tiếp cận dữ liệu bệnh viện.

Giao diện có thể cung cấp ba chế độ hiển thị: video gốc trong môi trường thử nghiệm; video đã làm mờ một phần khuôn mặt; và chế độ chỉ hiển thị skeleton/ROI. Trong kịch bản trình diễn về privacy, nhóm có thể cho thấy hệ thống vẫn phát hiện event trong khi dashboard không cần hiển thị video gốc liên tục.

Phản hồi "Xác nhận đúng/Cảnh báo sai" được lưu để đánh giá false alarm và hiệu chỉnh rule. Trong phạm vi hiện tại, hệ thống không tự động đưa dữ liệu này trở lại model để training. Việc nói rõ cơ chế này giúp tránh tuyên bố "AI tự học" khi sản phẩm chưa có pipeline huấn luyện.

## 12. TÍNH KHẢ THI VỀ NGUỒN LỰC VÀ TRIỂN KHAI

Tính khả thi của PostCare AI đến từ việc lựa chọn đúng mức độ phức tạp. Hai model chính đều là model huấn luyện sẵn; dữ liệu test có thể tự tạo; phần lớn chức năng còn lại là bài toán phần mềm quen thuộc gồm backend, database, realtime communication, frontend và testing. Nhóm không cần GPU lớn để training và không cần một dataset hàng nghìn mẫu được gắn nhãn.

Prototype có thể phát triển bằng một máy tính cá nhân có webcam hoặc camera IP. Nếu thiết bị có GPU thì inference có thể được tối ưu thêm, nhưng kiến trúc không bắt buộc phải dựa vào GPU cao cấp. Trong giai đoạn đầu, nhóm có thể dùng file video để xây và kiểm thử Event Engine trước, sau đó mới chuyển sang camera realtime.

Dự án cũng có thể chia việc rõ ràng giữa các thành viên: một người tập trung AI inference và Event Engine, một người xây backend/database/realtime, một người xây frontend/UX/testing. Nếu nhóm chỉ có hai người, body/face inference và backend có thể

<!-- Trang 14 -->

được gom một nhánh, còn frontend/testing là nhánh còn lại. Các module có interface rõ giúp giảm phụ thuộc lẫn nhau.

Quan trọng hơn, phạm vi MVP có thứ tự ưu tiên. Nếu thời gian hạn chế, nhóm vẫn có thể nộp một sản phẩm hoàn chỉnh với Body AI + Bed Exit + Cảnh báo + Timeline. Facial Analysis là phần tăng chiều sâu, không được phép làm chậm phần core. Điều này giúp dự án có phương án "giảm phạm vi nhưng không vỡ sản phẩm".

## 13. KẾ HOẠCH KIỂM THỬ VÀ ĐÁNH GIÁ

Một prototype AI chỉ có giá trị nếu có cách kiểm chứng. PostCare AI sẽ không sử dụng những con số accuracy tự đặt trước. Nhóm xây dựng bộ tình huống mô phỏng, gắn ground truth theo thời gian và chạy hệ thống trên cùng điều kiện để đo kết quả. Đây là dữ liệu đánh giá sản phẩm, không phải dữ liệu train model.

### 13.1. Bộ tình huống kiểm thử

Bộ test tối thiểu nên bao gồm: nằm yên; xoay người; ngồi dậy rồi nằm lại; ngồi ở mép giường; đứng lên; rời giường; quay lại giường; người khác đi ngang camera; điều dưỡng đứng gần giường; cơ thể bị che một phần; quay mặt khỏi camera; nhắm mắt; hạ lông mày; nheo mắt; chuyển động nhanh; và một số tình huống mô phỏng ngã an toàn trên nệm/thảm phù hợp. Mỗi scenario được quay nhiều lần, thay đổi tốc độ và vị trí ở mức vừa phải để tránh việc test chỉ đúng cho một kịch bản duy nhất.

Ground truth gồm thời điểm bắt đầu/kết thúc và loại event. Ví dụ một video có thể ghi: 00:10-00:13 ngồi dậy, 00:20-00:25 ở mép giường, 00:27 rời giường. Hệ thống tạo output tương ứng và được so sánh với ground truth theo một khoảng tolerance thời gian đã quy định trước.

### 13.2. Chỉ số đánh giá event

Đối với mỗi event, nhóm tính Precision, Recall và F1-score. Precision phản ánh tỷ lệ cảnh báo được tạo ra là đúng; Recall phản ánh tỷ lệ sự kiện thực tế được hệ thống phát hiện; F1 giúp cân bằng hai yếu tố. Với một hệ thống cảnh báo, cần theo dõi thêm false alerts/hour vì một sản phẩm tạo quá nhiều cảnh báo sai có thể gây "mệt mỏi cảnh báo" và giảm khả năng chấp nhận sử dụng.

### 13.3. Chỉ số realtime và hiệu năng

Hệ thống đo thời gian từ khi hành động thực tế bắt đầu đến khi event được xác nhận, và thời gian từ lúc event được tạo đến khi cảnh báo xuất hiện trên dashboard. Hai thành

<!-- Trang 15 -->

phần này cho biết detection latency và delivery latency. Nhóm cũng ghi FPS, CPU/RAM và nếu có GPU thì ghi mức sử dụng tương ứng. Mục tiêu không phải đạt benchmark tuyệt đối, mà chứng minh prototype chạy ổn định trên phần cứng được công bố.

### 13.4. Kiểm thử chất lượng quan sát

Nhóm cần có test riêng cho tình huống khuôn mặt quay khỏi camera, ánh sáng kém hoặc cơ thể bị che. Hệ thống được đánh giá không chỉ ở khả năng "đoán đúng event" mà còn ở khả năng biết khi nào không nên đoán. Nếu confidence thấp kéo dài, kết quả mong muốn là chuyển sang trạng thái "Không đủ dữ liệu quan sát".

## 14. TÍNH KHÁC BIỆT VÀ GIÁ TRỊ CẠNH TRANH

PostCare AI không tuyên bố phát minh pose estimation hay facial landmark. Điểm khác biệt nằm ở cách tích hợp những công nghệ có sẵn thành một workflow phục vụ đúng một vấn đề: biến quan sát camera thành event, cảnh báo, xác nhận và lịch sử. Đây là khác biệt quan trọng giữa một demo AI và một sản phẩm phần mềm có AI.

Một camera truyền thống lưu hoặc hiển thị video. Một demo pose estimation vẽ skeleton. Một hệ thống cảnh báo đơn giản có thể chỉ phát âm thanh khi phát hiện một hành động. PostCare AI đi thêm nhiều bước: giữ trạng thái theo thời gian, quản lý vòng đời cảnh báo, yêu cầu con người xác nhận, liên kết sự kiện với bệnh nhân/giường, tạo timeline và tổng hợp theo ca.

> *Bảng dựng lại từ văn bản trích xuất bị vỡ cột.*

| Tiêu chí | Camera thông thường | Demo AI theo frame | PostCare AI |
|---|---|---|---|
| Đầu vào | Video | Video | Video |
| Hiểu tư thế/biểu hiện | Không | Có | Có |
| Phân tích theo thời gian | Không | Thường hạn chế | Có state machine/temporal rule |
| Sự kiện có cấu trúc | Không | Có thể chưa có | Có |
| Cảnh báo và mức ưu tiên | Không | Có thể có | Có |
| Xác nhận bởi điều dưỡng | Không | Không | Có |
| Timeline và bàn giao ca | Không | Không | Có |
| Privacy mode | Phụ thuộc hệ thống | Thường không | Thiết kế từ đầu |

Một điểm khác biệt thứ hai là cách kết hợp Body AI và Facial AI nhưng không vượt quá phạm vi khoa học. Cơ thể được dùng để phát hiện hành vi và vùng giường; khuôn mặt chỉ bổ sung tín hiệu quan sát. Nếu face pipeline thất bại vì bệnh nhân quay mặt, body pipeline vẫn hoạt động. Thiết kế này thực tế hơn một hệ thống buộc mọi model phải cùng thành công.

<!-- Trang 16 -->

Điểm khác biệt thứ ba là privacy-by-design. Mục tiêu không phải thu thập thật nhiều video, mà là giảm nhu cầu lưu video bằng cách chuyển nội dung thành metadata sự kiện. Trong bối cảnh AI for Life, đây là một yếu tố thể hiện sản phẩm có suy nghĩ về cách sử dụng AI an toàn và có trách nhiệm.

## 15. PHẠM VI MVP VÀ LỘ TRÌNH TRIỂN KHAI

### 15.1. MVP bắt buộc

- Camera/video input và cấu hình vùng giường.
- Pose inference realtime bằng model pretrained.
- Trạng thái Nằm - Ngồi - Đứng - Ở mép giường - Ngoài giường.
- Sự kiện Ngồi dậy, Ở mép giường, Rời giường và chuyển động bất thường nghi té ngã.
- Face landmarks và tối thiểu các tín hiệu mắt/ lông mày/ nheo mắt khi khuôn mặt đủ rõ.
- Event Detection Engine có temporal window, debounce và confidence.
- Ứng dụng web tiếng Việt có Tổng quan, Cảnh báo, Theo dõi trực tiếp, Timeline.
- Các thao tác "Đã tiếp nhận", "Xác nhận đúng", "Cảnh báo sai", "Đã xử lý".
- Lưu lịch sử và tổng hợp cơ bản theo ca.
- Bộ test có ground truth và báo cáo metric.

### 15.2. Lộ trình theo giai đoạn

- **Giai đoạn 1 - Nền tảng hệ thống:** Thiết kế database, API, quản lý giường/bệnh nhân/phiên theo dõi, camera input, dashboard mock.
- **Giai đoạn 2 - Body AI:** Tích hợp Pose Landmarker, Bed ROI, tính đặc trưng, state machine Nằm/Ngồi/Đứng.
- **Giai đoạn 3 - Event cốt lõi:** Ngồi dậy, mép giường, rời giường, debounce, mức ưu tiên, logging.
- **Giai đoạn 4 - Facial AI:** Face Landmarker, mắt, lông mày, nheo mắt, sự kiện biểu hiện cần kiểm tra.
- **Giai đoạn 5 - Workflow hoàn chỉnh:** Realtime alert, tiếp nhận, xác nhận, xử lý, timeline, bàn giao ca.
- **Giai đoạn 6 - Đánh giá và tối ưu:** Bộ test, Precision/Recall/F1, false alerts/hour, latency, privacy mode, chuẩn bị demo.

<!-- Trang 17 -->

## 16. KỊCH BẢN DEMO VÒNG TRONG

Kịch bản demo chính nên ngắn nhưng thể hiện toàn bộ chuỗi giá trị. Một người đóng vai bệnh nhân nằm trên giường mô phỏng. Dashboard hiển thị "Giường A01 - Đang theo dõi - Trạng thái ổn định". Khi người đó ngồi dậy, giao diện cập nhật "Bệnh nhân ngồi dậy". Khi di chuyển tới mép giường, trạng thái đổi thành "Bệnh nhân ở mép giường". Khi đứng lên và bước khỏi ROI, hệ thống tạo cảnh báo ưu tiên cao "Bệnh nhân rời khỏi vùng giường".

Ở giao diện điều dưỡng, người demo nhấn "Đã tiếp nhận". Sau đó người đóng vai điều dưỡng hỗ trợ bệnh nhân trở lại giường và chọn "Đã xử lý". Cuối cùng mở "Lịch sử bệnh nhân" để cho thấy toàn bộ chuỗi sự kiện đã được ghi tự động với timestamp. Chỉ trong khoảng một phút, giám khảo có thể nhìn thấy AI, realtime, workflow và timeline hoạt động cùng nhau.

Kịch bản phụ dùng để thể hiện facial analysis. Camera được đặt ở khoảng cách đủ nhìn rõ mặt. Khi người dùng nhắm mắt kéo dài hoặc tạo một số biểu hiện như hạ lông mày và nheo mắt, dashboard hiển thị các tín hiệu tương ứng. Nếu rule đủ điều kiện, hệ thống tạo "Biểu hiện khuôn mặt cần kiểm tra". Người trình bày phải nhấn mạnh đây là tín hiệu quan sát, không phải chẩn đoán đau.

Một kịch bản privacy có thể chuyển dashboard từ video sang "Chế độ riêng tư", chỉ còn skeleton, Bed ROI và event text. Nếu event vẫn được phát hiện, giám khảo sẽ thấy rõ giá trị của việc xử lý AI nhưng giảm hiển thị hình ảnh gốc.

## 17. RỦI RO VÀ PHƯƠNG ÁN GIẢM THIỂU

**Che khuất cơ thể:** Chăn, thành giường hoặc người khác có thể che landmark. Giải pháp là kiểm tra confidence, ưu tiên landmark còn quan sát được và chuyển trạng thái "Không đủ dữ liệu quan sát" khi cần.

**Khuôn mặt quá nhỏ hoặc quay khỏi camera:** Facial analysis chỉ chạy khi kích thước mặt và confidence đạt ngưỡng. Không có mặt rõ thì bỏ facial event, không cố suy đoán.

**Ánh sáng và góc camera:** Chuẩn hóa vị trí camera cho demo, ghi rõ điều kiện thử nghiệm và kiểm tra với một số biến thể góc/ánh sáng.

**Cảnh báo sai nhiều:** Dùng temporal window, debounce, hysteresis, Bed ROI và state machine; đánh giá false alerts/hour và hiệu chỉnh threshold.

**Tích hợp quá nhiều model:** MVP chỉ dùng MediaPipe Pose + Face. Py-Feat/MMPose là phương án mở rộng, không phải phụ thuộc bắt buộc.

<!-- Trang 18 -->

**Scope y tế bị phóng đại:** Tất cả UI và báo cáo dùng ngôn ngữ "phát hiện sự kiện/tín hiệu cần kiểm tra", tránh "chẩn đoán", "xác định đau", "bất tỉnh".

**Thiếu thời gian:** Ưu tiên Body AI + Rời giường + Cảnh báo + Timeline. Facial AI có thể giảm phạm vi mà không làm vỡ câu chuyện sản phẩm.

## 18. ĐỊNH HƯỚNG MỞ RỘNG

Sau khi MVP hoạt động ổn định, PostCare AI có thể mở rộng theo chiều hệ thống thay vì vội tăng số lượng model. Ví dụ: hỗ trợ nhiều camera và nhiều giường; mobile app cho điều dưỡng; cơ chế chuyển tiếp cảnh báo nếu chưa có người tiếp nhận; dashboard thống kê dài hạn; cấu hình rule theo từng khu vực; hoặc tích hợp với hệ thống quản lý bệnh nhân qua API nếu có môi trường phù hợp.

Về AI, nếu có dữ liệu hợp pháp và sự tham gia của chuyên gia y tế, nhóm có thể nghiên cứu fine-tuning cho các góc camera thực tế hoặc xây bộ event classifier chuyên biệt. Đây là định hướng nghiên cứu sau này, không phải điều kiện để phiên bản dự thi hiện tại hoạt động.

Một hướng mở rộng khác là thêm cảm biến phi hình ảnh, ví dụ dữ liệu từ thiết bị theo dõi đã có sẵn, để fusion với camera. Tuy nhiên PostCare AI hiện tại không nên tự đọc hay diễn giải chỉ số y sinh nếu không có thiết bị và dữ liệu phù hợp. Scope camera + event workflow là đủ mạnh cho bản đầu.

<!-- Trang 19 -->

## 19. ĐỐI CHIẾU TIÊU CHÍ VÒNG SƠ TUYỂN

Báo cáo được xây dựng bám sát bốn nhóm tiêu chí của vòng sơ tuyển: tính khả thi, tính độc đáo, tính phù hợp của công nghệ ứng dụng và tính thuyết phục trong trình bày. Mục tiêu là không chỉ "kể ý tưởng hay", mà phải cho thấy ý tưởng có thể triển khai và có cách kiểm chứng.

> *Bảng dựng lại từ văn bản trích xuất bị vỡ cột.*

| Tiêu chí | Cách PostCare AI đáp ứng |
|---|---|
| Tính khả thi - 20% | Phạm vi MVP rõ; không train; mô hình có sẵn; dữ liệu test tự tạo có kiểm soát; lộ trình theo giai đoạn; có phương án giảm scope. |
| Tính độc đáo - 30% | Không nhận pose estimation là mới. Điểm khác biệt là body + face + temporal event engine + human verification + timeline + privacy trong một workflow thống nhất. |
| Tính phù hợp công nghệ - 30% | AI giải quyết trực tiếp raw video; chọn Pose/Face Landmarker phù hợp nguồn lực; Event Engine xử lý theo thời gian; có metric Precision/Recall/F1, false alerts/hour và latency. |
| Tính thuyết phục - 20% | Bối cảnh, người dùng, nhu cầu, giới hạn và luồng giá trị được mô tả xuyên suốt; mọi tuyên bố mang tính y tế được giới hạn ở mức hỗ trợ quan sát. |

Để tăng khả năng qua sơ tuyển, phần đăng ký ngắn nên giữ đúng thông điệp của báo cáo: PostCare AI không phải một model nhận diện tư thế; đây là một hệ thống biến camera thành sự kiện có cấu trúc và đưa AI vào quy trình xử lý thực tế. Tính khả thi được chứng minh bằng việc sử dụng mô hình huấn luyện sẵn, phạm vi core rõ ràng và phương pháp đánh giá cụ thể.

## 20. KẾT LUẬN

PostCare AI được định vị là một sản phẩm Software Engineering ứng dụng Computer Vision, không phải đề tài nghiên cứu mô hình. AI đảm nhiệm phần nhận biết dữ liệu hình ảnh; Event Detection Engine và hệ thống phần mềm biến kết quả đó thành trạng thái, sự kiện, cảnh báo, xác nhận và lịch sử. Cấu trúc này giúp đề tài có AI thật sự nhưng không phụ thuộc vào việc tự train một model mới.

Phiên bản được tinh chỉnh tập trung vào những thứ camera có thể quan sát: tư thế, vị trí so với giường, vận động và một số tín hiệu khuôn mặt. Những khái niệm đòi hỏi đánh giá lâm sàng như mức đau, mất ý thức, biến chứng hoặc giấc ngủ không được tuyên bố là khả năng của hệ thống. Điều này làm sản phẩm đáng tin hơn, dễ bảo vệ hơn và giảm nguy cơ bị giám khảo phản biện vì vượt quá bằng chứng.

<!-- Trang 20 -->

Giá trị nổi bật nhất của PostCare AI là chuỗi chuyển đổi từ quan sát tới hành động: camera tạo dữ liệu, AI tạo đặc trưng, Event Engine tạo sự kiện, hệ thống gửi cảnh báo, người dùng xác nhận và timeline lưu lại kết quả. Nhờ đó một luồng video liên tục trở thành thông tin ngắn gọn, có thể tra cứu và có trách nhiệm xử lý rõ ràng.

> CAMERA → AI → SỰ KIỆN → CẢNH BÁO → CON NGƯỜI XÁC NHẬN → TIMELINE

Với phạm vi này, PostCare AI có đủ chiều sâu để thể hiện Computer Vision, xử lý thời gian thực, backend, database, frontend, bảo mật, quyền riêng tư, kiểm thử và kiến trúc hệ thống; đồng thời vẫn giữ tính khả thi nhờ sử dụng model huấn luyện sẵn và dữ liệu mô phỏng. Đây là phạm vi phù hợp để xây một prototype thuyết phục cho AI for Life và tiếp tục phát triển nếu được vào vòng trong.

## TÀI LIỆU THAM KHẢO

1. Google AI for Developers. MediaPipe PoseLandmark - 33 pose landmarks. https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/PoseLandmark
2. Google AI for Developers. MediaPipe Face Landmarker - 52 blendshape coefficients và chế độ video/live stream. https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/drawing_styles/face_landmarker/Blendshapes
3. Google AI for Developers. FaceLandmarkerOptions. https://ai.google.dev/edge/api/mediapipe/python/mp/tasks/vision/FaceLandmarkerOptions
4. OpenMMLab. MMPose - Inference with existing pretrained models. https://github.com/open-mmlab/mmpose/blob/main/docs/en/user_guides/inference.md
5. Py-Feat Documentation. Detectorv2 / Detecting facial expressions from images and videos. https://py-feat.org/basic_tutorials/Detecting_Images/ ; https://py-feat.org/basic_tutorials/Detecting_Videos/
6. World Health Organization. Falls - Fact sheet. https://www.who.int/news-room/fact-sheets/detail/falls
7. Agency for Healthcare Research and Quality (AHRQ). Fall TIPS: A Patient-Centered Fall Prevention Toolkit. https://www.ahrq.gov/patient-safety/settings/hospital/fall-tips/index.html

<!-- Trang 21 -->

8. Tài liệu yêu cầu Đồ án Chuyên ngành 2 - chuyên ngành Công nghệ phần mềm, năm học 2026-2027.
9. Bảng tiêu chí chấm ý tưởng AI for Life do người dùng cung cấp: Tính khả thi 20%, Tính độc đáo 30%, Tính phù hợp công nghệ 30%, Tính thuyết phục 20%.

> **Ghi chú sử dụng**
> Bản báo cáo này mô tả một prototype phục vụ mục đích học tập và dự thi. Trước khi triển khai trong môi trường y tế thực tế cần đánh giá kỹ về pháp lý, bảo mật, quy trình bệnh viện, chất lượng mô hình và kiểm chứng với chuyên gia y tế.
