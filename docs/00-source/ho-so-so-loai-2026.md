**CUỘC THI “TRÍ TUỆ NHÂN TẠO VÀ ỨNG DỤNG - DANANG AI4LIFE” 2026** 

**BẢNG THI: AI FOR LIFE - SẢN PHẨM ỨNG DỤNG TRÍ TUỆ NHÂN TẠO** 

# **POSTCARE AI** 

**HỆ THỐNG AI HỖ TRỢ GIÁM SÁT BỆNH NHÂN HẬU PHẪU VÀ PHÁT HIỆN SỚM SỰ KIỆN CẦN CHÚ Ý** 

**HỒ SƠ Ý TƯỞNG VÀ ĐỀ XUẤT GIẢI PHÁP - VÒNG SƠ LOẠI** 

Nhóm dự thi: PostCare AI 

Định hướng: Software Engineering ứng dụng Computer Vision 

Đà Nẵng, tháng 10 năm 2026 

## **MỤC LỤC** 

|**1. TÓM TẮT VÀ ĐỊNH VỊ SẢN PHẨM.............................................................3**|
|---|
|**2. BÀI TOÁN CẦN GIẢI QUYẾT VÀ NGƯỜI SỬ DỤNG...............................3**|
|**3. GIÁ TRỊ NỔI BẬT CỦA POSTCARE AI.......................................................5**|
|**4. GIẢI PHÁP VÀ CÁCH VẬN HÀNH...............................................................5**|
|**5. CÁC CHỨC NĂNG AI VÀ EVENT DETECTION ENGINE.......................7**|
|**6. KIẾN TRÚC PHẦN MỀM, DỮ LIỆU VÀ QUYỀN RIÊNG TƯ..................9**|
|**7. TÍNH KHÁC BIỆT VÀ TÍNH KHẢ THI......................................................10**|
|**8. KẾ HOẠCH KIỂM THỬ VÀ KỊCH BẢN DEMO.......................................12**|
|**9. GIỚI HẠN, HƯỚNG MỞ RỘNG VÀ KẾT LUẬN......................................13**|
|TÀI LIỆU THAM KHẢO......................................................................................14|



2 

### **1. TÓM TẮT VÀ ĐỊNH VỊ SẢN PHẨM** 

PostCare AI là hệ thống phần mềm hỗ trợ quan sát bệnh nhân trong giai đoạn hậu phẫu bằng camera và trí tuệ nhân tạo. Hệ thống theo dõi liên tục các thay đổi về tư thế, vị trí quanh giường, mức vận động và một số tín hiệu khuôn mặt khi đủ điều kiện quan sát. Những thay đổi đáng chú ý được chuyển thành sự kiện có thời gian, mức ưu tiên và trạng thái xử lý; nhân viên y tế nhận cảnh báo, kiểm tra thực tế và xác nhận kết quả trên giao diện tiếng Việt. 

PostCare AI tập trung vào phần công việc tốn nhiều sự chú ý nhưng lặp lại: quan sát liên tục để nhận ra khi bệnh nhân có thay đổi đáng chú ý. Hệ thống theo dõi video, tạo sự kiện và gửi cảnh báo để người phụ trách kiểm tra. Khi camera, máy tính và mạng hoạt động ổn định, lớp quan sát này có thể chạy liên tục, kể cả 24/7, qua đó giảm thời gian con người phải ngồi cạnh giường hoặc nhìn màn hình camera. Trường hợp quy trình chuyên môn yêu cầu trực tiếp 1:1 vẫn được giữ nguyên. 

Prototype sử dụng điện thoại thông minh hoặc webcam làm nguồn hình ảnh, cố định trên giá đỡ cao và quay chéo từ trên xuống. Máy tính chạy các mô hình huấn luyện sẵn để trích xuất điểm cơ thể và đặc trưng khuôn mặt; Event Detection Engine xử lý chuỗi kết quả theo thời gian để nhận biết các trạng thái như nằm, ngồi, đứng, ở mép giường, rời hoặc quay lại giường, thay đổi vận động và chuyển động bất thường. Nhánh khuôn mặt bổ sung các tín hiệu như nhắm mắt kéo dài, hạ lông mày hoặc nheo mắt khi hình ảnh đủ rõ. 

Phiên bản dự thi sử dụng MediaPipe Pose Landmarker và Face Landmarker đã được huấn luyện sẵn. Nhóm chỉ hiệu chỉnh vùng giường, ngưỡng chất lượng, khoảng thời gian duy trì và quy tắc sự kiện trên dữ liệu mô phỏng; trọng số của mô hình không thay đổi. Nhờ vậy, nhóm có thể tập trung vào Event Detection Engine, cảnh báo, timeline và trải nghiệm sử dụng thay vì xây dựng một mô hình mới từ đầu. 

### **2. BÀI TOÁN CẦN GIẢI QUYẾT VÀ NGƯỜI SỬ DỤNG** 

### **2.1. Bài toán quan sát liên tục sau phẫu thuật** 

Trong giai đoạn hậu phẫu, người bệnh có thể trở mình, ngồi dậy, di chuyển ra mép giường, đứng lên hoặc rời khỏi giường vào thời điểm cần hỗ trợ. Điều dưỡng đồng thời phải chăm sóc, theo dõi, ghi nhận và bàn giao nhiều bệnh nhân. Vì vậy, việc bố trí một người chỉ để quan sát liên tục một bệnh nhân trong nhiều giờ khó mở rộng khi số giường cần theo dõi tăng. 

3 

Các tài liệu của WHO và AHRQ về an toàn vận động và phòng ngừa té ngã cho thấy việc nhận biết sớm thay đổi trong vận động là một phần quan trọng của chăm sóc người bệnh [1, 2]. PostCare AI bổ sung một lớp quan sát bằng camera để đưa những thay đổi đáng chú ý tới người phụ trách đúng thời điểm. 

Camera thông thường chỉ chuyển vị trí quan sát: nếu một người vẫn phải nhìn màn hình liên tục thì gánh nặng chú ý gần như không đổi. Các nghiên cứu về continuous video monitoring và virtual patient observation đã ghi nhận khả năng giảm số giờ cần bố trí người trực 1:1 và cải thiện hiệu quả sử dụng nhân lực điều dưỡng [3, 4]. PostCare AI đi theo hướng đó ở mức prototype: hệ thống tự theo dõi video và gọi người phụ trách khi xuất hiện sự kiện cần kiểm tra. 

|**Cách theo dõi**|**Điểm mạnh**|**Hạn chế chính**|
|---|---|---|
|Người trực trực tiếp 1:1|Quan sát tại chỗ, phản ứng nhanh<br>khi có tình huống rõ ràng.|Tiêu tốn sự chú ý và nhân lực liên<br>tục; khó mở rộng khi nhiều bệnh<br>nhân cùng cần quan sát.|
|Camera thông thường|Mở rộng tầm nhìn, có thể theo<br>dõi từ xa và lưu video.|Vẫn cần người nhìn màn hình; sự<br>kiện dễ bị bỏ sót hoặc mất thời<br>gian tìm lại trong video dài.|
|PostCare AI|Tự động theo dõi trạng thái, tạo<br>sự kiện, cảnh báo, timeline và<br>trạng thái xử lý.|Cần góc quan sát đủ tốt; sự kiện<br>quan trọng vẫn được người phụ<br>trách kiểm tra trước khi xử lý.|



### **2.2. Người dùng và nhu cầu** 

Người dùng chính là điều dưỡng hoặc nhân viên y tế phụ trách khu vực hậu phẫu. Họ cần biết giường nào đang có thay đổi đáng chú ý, sự kiện xảy ra lúc nào, mức ưu tiên ra sao và cảnh báo đã có người tiếp nhận hay chưa. Người phụ trách ca cần xem tổng quan nhiều giường, các cảnh báo còn tồn đọng và lịch sử xử lý để bàn giao. Bác sĩ hoặc người có thẩm quyền có thể tra cứu timeline như nguồn thông tin bổ sung, nhưng timeline không thay thế hồ sơ bệnh án. 

Prototype được kiểm chứng trước trên một giường để giảm biến số. Dashboard vẫn được thiết kế theo hướng nhiều giường; khi mở rộng, người trực có thể ưu tiên các giường đang có sự kiện thay vì phải duy trì mức chú ý như nhau cho mọi luồng camera. Hiệu quả nhân lực sẽ được đánh giá khi hệ thống được thử nghiệm ở quy mô lớn hơn. 

4 

### **3. GIÁ TRỊ NỔI BẬT CỦA POSTCARE AI** 

PostCare AI chuyển luồng video liên tục thành các sự kiện ngắn gọn, có mức ưu tiên và có người chịu trách nhiệm xử lý. Giá trị của sản phẩm tập trung ở năm điểm sau. 

|**Giá trị**|**PostCare AI mang lại**|
|---|---|
|Giảm quan sát thủ công liên tục|Hệ thống duy trì quan sát tự động và chủ động<br>thông báo sự kiện, giúp giảm thời gian nhân viên y<br>tế phải ngồi cạnh giường hoặc nhìn màn hình<br>camera liên tục.|
|Theo dõi nhiều loại thay đổi|Hệ thống theo dõi tư thế, vị trí quanh giường, mức<br>vận động, chuyển động bất thường và một số tín<br>hiệu khuôn mặt khi đủ điều kiện.|
|Biến video thành workflow|Mỗi sự kiện có thời điểm, mức ưu tiên, người tiếp<br>nhận, kết quả xác nhận và lịch sử để phục vụ tra<br>cứu và bàn giao ca.|
|Dễ tiếp cận ở mức prototype|Có thể bắt đầu bằng smartphone/webcam, máy tính<br>cá nhân và mô hình huấn luyện sẵn; không cần hạ<br>tầng train model.|
|Tối thiểu hóa dữ liệu hình ảnh|Ưu tiên lưu metadata sự kiện và nhật ký thao tác;<br>video gốc chỉ được lưu khi có mục đích và quyền<br>sử dụng phù hợp.|



Prototype có thể tận dụng smartphone sẵn có làm camera khi chủ sở hữu đồng ý và tạm thời không cần sử dụng thiết bị. Cách này giảm chi phí thử nghiệm và dễ thay đổi vị trí quan sát. Khi cần, smartphone được thay bằng webcam hoặc camera IP mà không làm thay đổi luồng xử lý của hệ thống. 

### **4. GIẢI PHÁP VÀ CÁCH VẬN HÀNH** 

### **4.1. Bố trí camera bằng điện thoại** 

Trong bản prototype, điện thoại được gắn chắc chắn trên tripod hoặc giá đỡ có tay vươn, đặt ở đầu giường hoặc lệch một bên và hướng chéo từ trên xuống. Góc quay cần bao quát thân người, hai mép giường và vùng người bệnh có thể bước xuống. Vị trí cuối cùng được chọn qua thử nghiệm landmark và mức che khuất; không cố định một góc duy nhất cho mọi loại giường. 

Góc quay toàn thân có thể khiến khuôn mặt nhỏ hoặc nghiêng. Pose Landmarker vì thế đảm nhiệm theo dõi cơ thể liên tục; Face Landmarker chỉ chạy khi khuôn mặt đủ rõ. Mất tín hiệu khuôn mặt không làm gián đoạn việc theo dõi tư thế và vị trí cơ thể. 

5 

Giá đỡ phải có ngàm khóa, dây sạc được bố trí gọn và nên có biện pháp chống rơi nếu thiết bị vươn qua vùng giường. 



<!-- Start of picture text -->
Dién thoai quay chéo<br>a<br>Gia do cao tirtrén xuéng<br>Video qua mang ngi bd May tinh xir ly<br>Al + bé phat hién sy kin<br>Web dashboard<br>Canh béo, xéc nhén, lich str<br>Giuéng mé phéng<br>OO )<br>6 tri minh hoa cho mét giuding; vi tri cui cing cén thir theo géc nhin va dé che khust.<br><!-- End of picture text -->

_Hình 1. Bố trí smartphone làm camera quan sát một giường mô phỏng (minh họa)._ 

### **4.2. Luồng vận hành từ quan sát đến hành động** 

Điện thoại hoặc webcam gửi video tới máy tính xử lý qua mạng nội bộ hoặc kết nối phù hợp. Trong giai đoạn thử nghiệm, DroidCam là một lựa chọn để khảo sát việc dùng điện thoại như webcam trên Linux [7]. Khối AI trích xuất pose landmarks và, khi đủ điều kiện, face landmarks/blendshapes. Lớp xử lý thời gian làm mượt dữ liệu, theo dõi trạng thái và kiểm tra chất lượng quan sát. Event Detection Engine tạo sự kiện khi chuỗi điều kiện đạt ngưỡng. Backend lưu sự kiện trước khi gửi cập nhật realtime lên dashboard. 

Khi có cảnh báo, điều dưỡng chọn “Đã tiếp nhận”, kiểm tra thực tế rồi ghi “Xác nhận đúng”, “Cảnh báo sai”, “Bệnh nhân an toàn” hoặc “Đã xử lý”. Các thao tác này được lưu cùng timestamp và người thực hiện. Nhờ đó, một sự kiện không chỉ là thông báo tức thời mà trở thành bản ghi có thể truy vết và dùng cho bàn giao ca. 



<!-- Start of picture text -->
Nguén video Alsuyluan |_| Xirly théi gian Taosukién |. anh bdo<br>Bign thoal/ video thir Pose + Face (c6 diéu kién) Lam mugt, trang thai Quy tac, dé tin cay Tiép nhan, xéc nan<br>Luu két qua<br>Co sé dif liéu va timeline<br>Luu su kién, trang thai va thao tac nguii ding<br><!-- End of picture text -->

_Hình 2. Luồng xử lý từ nguồn video đến cảnh báo và timeline._ 

6 

### **4.3. Giao diện theo dõi** 

Dashboard tiếng Việt tập trung vào ba nhóm thông tin: trạng thái từng giường, sự kiện đang cần chú ý và diễn biến gần đây. Thông báo sử dụng mô tả trực tiếp như “Bệnh nhân đang ở mép giường”, “Bệnh nhân rời vùng giường” hoặc “Chuyển động bất thường - đề nghị kiểm tra”, thay vì hiển thị mã kỹ thuật nội bộ. 



<!-- Start of picture text -->
PostCare Al / Téng quan theo déi a truc: 14:00-22:00<br>Giuéng AO1 Giuéng Ao2 Giuéng Ao3<br>Dang theo doi Can kiém tra Canh bao mdi<br>SU KIEN CAN CHU Y / GIUONG AO3 DIEN BIEN GAN DAY<br>14:38 - Ghinhan ngudi dugc theo doi ra khdi ving giudng 14:37 + Ngéi day<br>Trang thai: Cho tiép nhan Da tiép nhan 14:38 + O mép giudng<br>14:38 * Rdi ving giudng<br>Lich str theo doi<br>Loc theo giuéng/ thdi gian + Xem ngudi tiép nhan + Ghi két qua kiém tra<br><!-- End of picture text -->

_Hình 3. Phác thảo dashboard tổng quan nhiều giường và luồng tiếp nhận cảnh báo._ 

### **5. CÁC CHỨC NĂNG AI VÀ EVENT DETECTION ENGINE** 

### **5.1. Nhóm chức năng quan sát** 

Các chức năng được chia thành bốn nhóm: tư thế cơ thể, vị trí quanh giường, mức vận động và tín hiệu khuôn mặt. Tất cả dùng chung dữ liệu thời gian và trạng thái chất lượng để tạo sự kiện nhất quán. 

|**Lớp quan sát**|**Tín hiệu / trạng thái**|**Sự kiện hoặc đầu ra chính**|
|---|---|---|
|Tư thế cơ thể|Nằm, nâng thân, ngồi, đứng; góc<br>thân, quan hệ vai-hông.|Ngồi dậy, đứng dậy, thay đổi tư<br>thế.|
|Vị trí quanh giường|Tâm cơ thể, chân và vị trí so với<br>Bed ROI.|Ở mép giường, rời giường, quay<br>lại giường.|
|Mức vận động|Độ dịch chuyển theo thời gian,<br>tốc độ thay đổi, hướng thân.|Ít/tăng vận động; hạ thấp nhanh;<br>dịch chuyển mạnh hoặc đổi<br>hướng thân đột ngột cần kiểm tra.|
|Khuôn mặt (có điều kiện)|Mắt đóng/mở, nhắm kéo dài, hạ<br>lông mày, nheo mắt, thay đổi<br>vùng mũi-miệng.|Tín hiệu quan sát; khi nhiều tín<br>hiệu duy trì có thể tạo “Biểu hiện<br>khuôn mặt cần kiểm tra”.|



7 

### **5.2. Theo dõi tư thế và vị trí quanh giường** 

MediaPipe Pose Landmarker được chọn vì có mô hình huấn luyện sẵn, hỗ trợ ảnh, video và luồng trực tiếp, đồng thời trả về 33 landmark cơ thể [5]. Từ các điểm vai, hông, đầu gối, cổ chân và bàn chân, phần mềm tính tâm hông, tâm vai, hướng thân, độ dịch chuyển và vị trí tương đối với vùng giường. Các đặc trưng này được dùng trực tiếp trong logic trạng thái của hệ thống. 

Sự kiện “Ngồi dậy” được nhận biết từ chuyển đổi hợp lý giữa trạng thái nằm, nâng thân và ngồi. “Ở mép giường” kết hợp tư thế ngồi/đứng với vị trí cơ thể tiến gần ranh giới Bed ROI. “Rời giường” chỉ được xác nhận khi người mục tiêu được quan sát ra ngoài vùng giường đủ lâu; mất landmark hoặc bị che không được coi là rời giường. “Quay lại giường” được ghi khi đối tượng xuất hiện lại trong vùng và trạng thái được xác lập đủ chắc chắn. 

Bên cạnh vị trí, hệ thống theo dõi độ dịch chuyển và hướng thân trong một cửa sổ thời gian. Xoay người hoặc thay đổi tư thế thông thường được lưu vào timeline. Khi cơ thể hạ thấp nhanh, dịch chuyển mạnh hoặc đổi hướng thân đột ngột, hệ thống tạo sự kiện “Chuyển động bất thường - đề nghị kiểm tra” để người phụ trách xác minh. 

### **5.3. Tín hiệu khuôn mặt và mức hoạt động** 

MediaPipe Face Landmarker cung cấp landmark và các hệ số blendshape liên quan đến mắt, lông mày, mũi và miệng [6]. Hệ thống dùng một tập tín hiệu nhỏ gồm mắt đóng/mở, nhắm mắt kéo dài, nheo mắt, hạ lông mày và thay đổi vùng mũi-miệng. Các tín hiệu này được lưu như dữ liệu quan sát để bổ sung ngữ cảnh cho sự kiện. 

Khi nhiều tín hiệu khuôn mặt xuất hiện đồng thời và duy trì đủ lâu, Event Engine có thể tạo “Biểu hiện khuôn mặt cần kiểm tra”. Mức ưu tiên tăng khi tín hiệu khuôn mặt đi kèm thay đổi vận động; ví dụ vận động tăng đồng thời với nheo mắt và hạ lông mày kéo dài. Nhánh khuôn mặt bổ sung thông tin quan sát, còn việc đánh giá tình trạng bệnh nhân thuộc nhân viên y tế. 

Mức hoạt động cũng được theo dõi theo thời gian. Khi cơ thể ít chuyển động trong một khoảng kéo dài và mắt đóng trong điều kiện quan sát đủ rõ, giao diện hiển thị “Đang nghỉ - dữ liệu tham khảo”; khi vận động tăng hoặc mắt mở trở lại, trạng thái chuyển về “Đang hoạt động”. Trạng thái này chỉ mô tả mức hoạt động quan sát được. 

### **5.4. Event Detection Engine** 

Event Detection Engine giữ lịch sử ngắn hạn của các tín hiệu, loại nhiễu và chỉ tạo sự kiện khi trạng thái duy trì đủ lâu hoặc đi theo một chuỗi vị trí hợp lý. Cơ chế 

8 

debounce và hysteresis hạn chế cảnh báo lặp và dao động quanh ngưỡng, giúp kết quả ổn định hơn so với xử lý từng frame độc lập. 

Mỗi sự kiện có mức ưu tiên phục vụ thứ tự xử lý. Thay đổi tư thế thường chỉ được lưu nhật ký; ngồi dậy ở mức thông tin; ở mép giường cần chú ý; rời giường hoặc chuyển động bất thường được ưu tiên cao hơn để người trực kiểm tra trước. 

### **5.5. Triển khai bằng mô hình huấn luyện sẵn** 

Pose Landmarker và Face Landmarker đã cung cấp các đặc trưng thị giác cần thiết. Phần còn lại được triển khai bằng tọa độ, Bed ROI, state machine và quy tắc theo thời gian. Nhóm chỉ hiệu chỉnh thời gian duy trì, ngưỡng chất lượng, khoảng cách tới biên giường và mức thay đổi vận động trên tập phát triển; trọng số của mô hình pretrained được giữ nguyên. 

Nếu sau này các rule không đủ cho môi trường nhiều người, góc quay phức tạp hoặc cần nhận biết hành vi khó hơn, nhóm có thể khảo sát MMPose/RTMPose hoặc xây classifier chuyên biệt trên dữ liệu hợp pháp. Đó là hướng mở rộng sau khi prototype hiện tại đã chứng minh được chuỗi quan sát - sự kiện - cảnh báo - xác nhận. 

### **6. KIẾN TRÚC PHẦN MỀM, DỮ LIỆU VÀ QUYỀN RIÊNG TƯ** 

### **6.1. Kiến trúc module** 

Hệ thống được chia thành các module có trách nhiệm rõ ràng. Camera Service nhận luồng hình ảnh và theo dõi kết nối. AI Inference Service chuẩn hóa đầu ra pose/face thành một cấu trúc dữ liệu chung. Temporal Processing và Event Engine tạo trạng thái, sự kiện và mức ưu tiên. Backend quản lý giường, phiên theo dõi, người dùng, cảnh báo và audit log. Realtime Gateway cập nhật dashboard; PostgreSQL lưu trạng thái nghiệp vụ lâu dài. 

MVP có thể chạy trên một máy tính thay vì tách thành nhiều microservice. Điều quan trọng là ranh giới dữ liệu rõ: nếu sau này thay Pose Landmarker bằng một model khác, adapter chỉ cần chuyển output về schema chung, còn Event Engine và giao diện giữ nguyên. Thiết kế này phù hợp với mục tiêu Software Engineering và giảm rủi ro tích hợp. 

### **6.2. Dữ liệu sự kiện và timeline** 

PostCare AI lưu sự kiện làm dữ liệu vận hành chính. Mỗi phiên theo dõi gắn một người thử nghiệm với một giường và camera trong một khoảng thời gian. Sự kiện lưu loại, thời điểm, mức ưu tiên, chất lượng quan sát và căn cứ ngắn gọn; cảnh báo lưu người tiếp nhận, thời điểm tiếp nhận, kết quả xác nhận và thời điểm hoàn tất. Nhờ đó 

9 

người dùng có thể tra cứu, thống kê và bàn giao ca mà không phải xem lại toàn bộ video. 

### **6.3. Quyền riêng tư và dữ liệu cá nhân** 

Video trong bối cảnh chăm sóc sức khỏe có thể chứa dữ liệu cá nhân nhạy cảm. Prototype chỉ sử dụng dữ liệu mô phỏng có sự đồng ý của người tham gia; việc dùng điện thoại của người bệnh thật làm camera chỉ được đặt ra khi có sự đồng ý rõ ràng và quy trình quản lý thiết bị phù hợp. Giao diện có thể hỗ trợ chế độ làm mờ hoặc chỉ hiển thị skeleton/ROI để giảm lượng hình ảnh nhận dạng mà người dùng phải xem. 

Thiết kế ưu tiên xử lý hình ảnh để tạo event rồi lưu metadata thay vì mặc định ghi video liên tục. Việc triển khai thực tế phải tuân thủ Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15, có hiệu lực từ 01/01/2026, cùng các quy định hướng dẫn liên quan như Nghị định 356/2025/NĐ-CP [8, 9]. Báo cáo này không tuyên bố prototype đã đủ điều kiện triển khai lâm sàng; các yêu cầu pháp lý, bảo mật và quy trình bệnh viện phải được đánh giá lại khi chuyển khỏi môi trường mô phỏng. 

### **7. TÍNH KHÁC BIỆT VÀ TÍNH KHẢ THI** 

### **7.1. Điểm khác biệt** 

PostCare AI kết hợp camera thông dụng, mô hình pretrained và Event Detection Engine thành một quy trình quan sát hoàn chỉnh cho khu vực hậu phẫu. Hệ thống không dừng ở việc hiển thị video hay skeleton: tín hiệu hình ảnh được chuyển thành sự kiện có ngữ cảnh, cảnh báo có người tiếp nhận và timeline có thể tra cứu. 

|**Tiêu chí**|**Camera thường**|**Demo AI theo frame**|**PostCare AI**|
|---|---|---|---|
|Quan sát tư thế / biểu<br>hiện|Không tự phân tích|Có thể có|Có, theo điều kiện chất<br>lượng|
|Phân tích theo thời gian|Không|Thường hạn chế|Có state machine và quy<br>tắc theo thời gian|
|Sự kiện có ngữ cảnh|Không|Có thể chưa có|Có, gắn giường và phiên|
|Cảnh báo + người tiếp<br>nhận|Không|Có thể có cảnh báo|Có vòng đời tiếp nhận<br>và xác nhận|
|Timeline / bàn giao ca|Không|Thường không|Có|
|Mất quan sát|Người xem tự nhận biết|Có thể không xử lý|Hiển thị trạng thái riêng|
|Thiết bị prototype|Camera chuyên dụng<br>hoặc webcam|Tùy demo|Smartphone/webcam +<br>máy tính phổ thông|



10 

Các sản phẩm thương mại đã có chức năng giường thông minh, cảnh báo rời giường hoặc quan sát video từ xa. Stryker ProCuity mô tả Adaptive Bed Alarm; LIO/Oxehealth phát triển nền tảng giám sát và workflow cho môi trường nội trú [10, 11]. Trong bối cảnh đó, PostCare AI tập trung vào một cấu hình phù hợp nguồn lực sinh viên: thiết bị phổ biến, giao diện tiếng Việt, rule giải thích được, trạng thái mất quan sát rõ và workflow xác nhận. Điểm khác biệt của đề tài nằm ở cách gắn các thành phần này thành một quy trình có thể kiểm chứng cho hậu phẫu mô phỏng, thay vì chỉ dừng ở một cảnh báo tư thế. 

### **7.2. Khả thi về công nghệ và nguồn lực** 

Prototype không cần hạ tầng huấn luyện AI. Một máy tính cá nhân, smartphone hoặc webcam, giá đỡ chắc chắn và mạng nội bộ là đủ để triển khai bản đầu; GPU chỉ là tùy chọn để tối ưu tốc độ suy luận. Dữ liệu mô phỏng được dùng để hiệu chỉnh rule và đánh giá sự kiện, không dùng để train lại model. 

Nguồn dữ liệu kiểm thử cũng chủ động: nhóm tự quay các tình huống mô phỏng với người trưởng thành tự nguyện, có quyền sử dụng rõ ràng và ground truth theo thời gian. Nhờ đó, nguồn dữ liệu không phụ thuộc vào quyền truy cập bệnh viện trong giai đoạn sơ loại và nhóm có thể chủ động tổ chức thử nghiệm. 

### **7.3. Lộ trình 10 tuần** 

|**Giai đoạn**|**Thời gian**|**Đầu ra chính**|
|---|---|---|
|Nền tảng|Tuần 1-2|Camera input, ROI, database,<br>API, dashboard khung, phiên<br>theo dõi.|
|Body AI|Tuần 3-4|Pose, nằm/ngồi/đứng, ngồi dậy,<br>mép giường, rời/quay lại giường.|
|Event + workflow|Tuần 5-6|Temporal rule, mức ưu tiên, cảnh<br>báo, tiếp nhận, timeline, audit.|
|Face + hoạt động|Tuần 7-8|Tín hiệu mắt/lông mày/nheo mắt,<br>biểu hiện cần kiểm tra, mức hoạt<br>động tham khảo.|
|Đánh giá + demo|Tuần 9-10|Bộ test, Precision/Recall/F1,<br>FP/giờ, latency, privacy mode,<br>demo hoàn chỉnh.|



Mốc tối thiểu được xác định là chuỗi Body AI - sự kiện - cảnh báo - xác nhận - timeline. Nếu nhánh khuôn mặt chưa đủ ổn định ở góc quay toàn thân, hệ thống vẫn 

11 

giữ được giá trị cốt lõi; face được giới hạn theo chất lượng quan sát thay vì làm chậm toàn bộ MVP. 

### **8. KẾ HOẠCH KIỂM THỬ VÀ KỊCH BẢN DEMO** 

### **8.1. Bộ tình huống kiểm thử** 

Bộ dữ liệu mô phỏng phải bao phủ cả tình huống đúng và tình huống dễ gây nhầm. Các nhóm chính gồm nằm yên, trở mình, ngồi dậy rồi nằm lại, ở mép giường, đứng dậy, rời giường, quay lại giường, người khác đi ngang, cơ thể bị che một phần, thay đổi ánh sáng, mặt quay khỏi camera, nhắm mắt kéo dài và chuyển động nhanh xuống nệm an toàn. Mỗi kịch bản được quay nhiều lượt với thay đổi vừa phải về tốc độ và vị trí để tránh việc hệ thống chỉ đúng cho một màn diễn cố định. 

Ground truth ghi loại sự kiện và thời điểm bắt đầu/kết thúc. Một phần lượt quay dùng để hiệu chỉnh rule, phần còn lại giữ riêng cho lần đánh giá chính. Không tách các frame liền nhau của cùng video sang hai tập khác nhau. Khi có thể, tập đánh giá nên chứa người hoặc phiên quay khác với tập hiệu chỉnh để kiểm tra khả năng khái quát ở mức cơ bản. 

### **8.2. Chỉ số đánh giá** 

|**Nhóm chỉ số**|**Mục đích**|
|---|---|
|Precision / Recall / F1|Đo cảnh báo đúng, bỏ sót và cân bằng hai phía cho<br>từng loại sự kiện.|
|False alerts / giờ|Đo mức nhiễu cảnh báo; tránh một hệ thống đúng<br>nhiều nhưng gây mệt mỏi vì cảnh báo sai.|
|Detection + delivery latency|Đo thời gian từ hành động đến khi event được xác<br>nhận và từ event đến dashboard.|
|Coverage / mất quan sát|Cho biết hệ thống có đủ dữ liệu để kết luận trong<br>bao nhiêu phần thời gian.|
|FPS, CPU/RAM, frame bỏ|Chứng minh prototype chạy ổn định trên phần cứng<br>được công bố.|
|Workflow|Đo khả năng tìm cảnh báo, tiếp nhận, ghi kết quả<br>và tra cứu timeline.|



Sau vòng thử thăm dò, nhóm chốt ngưỡng cho các sự kiện cốt lõi rồi giữ nguyên khi chạy tập đánh giá. Báo cáo kết quả kèm TP/FP/FN, thời lượng video và điều kiện camera để thể hiện rõ phạm vi kiểm thử. 

12 

### **8.3. Kịch bản demo vòng trong** 

Kịch bản chính kéo dài khoảng một phút. Một người nằm trên giường mô phỏng; dashboard hiển thị giường đang được theo dõi. Khi người đó ngồi dậy, di chuyển tới mép giường, đứng lên rồi bước khỏi ROI, timeline cập nhật từng trạng thái và tạo cảnh báo ưu tiên cao ở thời điểm rời giường. Thành viên đóng vai điều dưỡng chọn “Đã tiếp nhận”, kiểm tra, ghi kết quả và mở lịch sử để cho thấy toàn bộ chuỗi đã được lưu. 

Kịch bản phụ kiểm tra các trường hợp dễ gây nhầm: người tham gia thay đổi tư thế nhưng vẫn ở trên giường, người khác đi ngang khung hình, camera bị che một phần hoặc khuôn mặt quay khỏi camera. Hệ thống phải tránh tạo sự kiện sai và chuyển sang trạng thái thiếu dữ liệu khi chất lượng quan sát không đủ. 

### **9. GIỚI HẠN, HƯỚNG MỞ RỘNG VÀ KẾT LUẬN** 

### **9.1. Giới hạn sử dụng** 

PostCare AI hỗ trợ quan sát và ưu tiên sự chú ý; hệ thống không chẩn đoán đau, mất ý thức, biến chứng hoặc nguyên nhân y khoa của một chuyển động. Khi quy trình chuyên môn yêu cầu có người trực trực tiếp bên bệnh nhân, yêu cầu đó vẫn được giữ nguyên. Nhân viên y tế là người kiểm tra thực tế và quyết định cách xử lý. 

Khả năng vận hành liên tục, kể cả 24/7, phụ thuộc vào nguồn điện, mạng, thiết bị, góc camera và độ ổn định của phần mềm. Điện thoại cá nhân có thể bị lấy lại để liên lạc hoặc bị gián đoạn bởi hệ điều hành, vì vậy triển khai thực tế nên có camera chuyên dụng hoặc thiết bị thay thế. Nhánh khuôn mặt đặc biệt nhạy với khoảng cách, góc quay và ánh sáng; thiếu dữ liệu mặt không được suy diễn thành trạng thái bình thường. 

### **9.2. Hướng mở rộng** 

Sau khi MVP một giường ổn định, PostCare AI có thể mở rộng sang nhiều camera/giường, thông báo di động cho điều dưỡng, cơ chế chuyển tiếp cảnh báo chưa tiếp nhận, dashboard thống kê theo ca và tích hợp API với hệ thống quản lý bệnh nhân khi có điều kiện phù hợp. Về AI, chỉ khi thu thập được dữ liệu hợp pháp và xác định rõ giới hạn của rule, nhóm mới cân nhắc fine-tuning hoặc classifier chuyên biệt cho góc camera thực tế. 

### **9.3. Kết luận** 

PostCare AI được định vị là một trợ lý quan sát bằng AI cho khu vực hậu phẫu: theo dõi liên tục trạng thái cơ thể, vận động và một số tín hiệu khuôn mặt; chuyển các thay đổi đáng chú ý thành sự kiện; đưa sự kiện tới người phụ trách; và lưu lại quá trình 

13 

xác nhận trong timeline. Giá trị lớn nhất là chuyển bài toán “phải nhìn liên tục” thành bài toán “xử lý khi có sự kiện”. 

Mô hình pretrained giúp nhóm tránh chi phí dữ liệu và tài nguyên cho việc huấn luyện từ đầu. Phần giá trị của sản phẩm nằm ở Event Detection Engine, backend, cảnh báo thời gian thực, dashboard, quản lý dữ liệu và kiểm thử. Với phạm vi một giường mô phỏng, dữ liệu có quyền sử dụng rõ ràng và lộ trình 10 tuần, nhóm có thể hoàn thiện một prototype chạy xuyên suốt và đo được kết quả trong điều kiện mô phỏng. 

### **TÀI LIỆU THAM KHẢO** 

- [1] World Health Organization. Falls. 26/04/2021. [Truy cập] 

- [2] Agency for Healthcare Research and Quality. Fall TIPS: A Patient-Centered Fall Prevention Toolkit. [Truy cập] 

- [3] Kalafus, L. et al. Implementation of a Continuous Video Monitoring Program to Decrease Inpatient Falls in a Long-Term Acute Care Hospital Setting. American Journal of Nursing, 2025. PMID: 41261482. [Truy cập] 

- [4] Integration of Virtual Technology and Artificial Intelligence Improves Satisfaction, Patient Safety, and Nursing Workforce Efficiency. PubMed, 2025. PMID: 39999215. [Truy cập] 

- [5] Google AI for Developers. Pose Landmarker / Pose landmarks. [Truy cập] 

- [6] Google AI for Developers. Face Landmarker. [Truy cập] 

- [7] Dev47Apps. DroidCam - Phone as Webcam. [Truy cập] 

- [8] Quốc hội. Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15; hiệu lực từ 01/01/2026. <u>[Truy cập]</u> 

- [9] Chính phủ. Nghị định số 356/2025/NĐ-CP quy định chi tiết một số điều và biện pháp thi hành Luật Bảo vệ dữ liệu cá nhân; hiệu lực từ 01/01/2026. [Truy cập] 

- [10] Stryker. ProCuity connected hospital bed / Adaptive Bed Alarm. [Truy cập] 

- [11] LIO Health. Patient safety / virtual monitoring information. [Truy cập] 

- [12] OpenMMLab. MMPose - inference with existing pretrained models. [Truy cập] 

14 

