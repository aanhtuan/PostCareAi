# PostCare AI — Công nghệ, tính khả thi, thực thi và giá trị ứng dụng AI trong đời sống

Ngày tổng hợp: **17/11/2026**. Mục đích: chuẩn bị nội dung thuyết trình, hồ sơ dự thi và trả lời giám khảo.

Tài liệu tổng hợp từ PRD, kiến trúc và tiến độ của dự án; không thay thế spec hoặc tự bổ sung yêu cầu triển khai. Các nhận định về lợi ích, chi phí và khả năng sử dụng thực tế là giả thuyết cần đánh giá, trừ khi có bằng chứng được nêu rõ.

## 1. Ý tưởng và thông điệp chính

**PostCare AI hướng tới biến hình ảnh quanh giường bệnh thành sự kiện có thời gian, cảnh báo có người tiếp nhận và lịch sử có thể tra cứu.**

Camera cung cấp hình ảnh. Model AI pretrained trích xuất các điểm cơ thể. Engine phân tích diễn biến theo thời gian để nhận biết một số thay đổi quan sát được, như ngồi dậy, ở mép giường, rời hoặc quay lại giường. Nhân viên y tế kiểm tra thực tế, ghi kết quả và hoàn tất cảnh báo trên web tiếng Việt.

Giá trị cần chứng minh là khả năng đưa thông tin phù hợp đến người phụ trách và hỗ trợ xử lý có truy vết. Hệ thống được định vị là công cụ hỗ trợ quan sát; quyết định chuyên môn thuộc nhân viên y tế. Nguồn: HS §1–3, §4.2; PRD §1–4.

### Bài toán đời sống được lựa chọn

- Việc quan sát hình ảnh liên tục đòi hỏi thời gian và sự chú ý của người phụ trách.
- Một màn hình camera thông thường vẫn yêu cầu người dùng chủ động nhìn và tự ghi nhớ diễn biến.
- Khi đổi ca, thông tin cần được truyền lại theo giường, thời điểm, sự kiện và tình trạng xử lý.

Đây là bài toán được nêu trong hồ sơ dự án. Mức độ phổ biến, mức ưu tiên và chi phí của bài toán tại một đơn vị cụ thể cần được xác nhận bằng khảo sát; tài liệu này chưa có kết quả khảo sát điều dưỡng độc lập. Nguồn: HS §2; PDF §2–3.

## 2. Hiện trạng và mức độ bằng chứng

| Hạng mục | Hiện trạng theo tài liệu tiến độ | Có thể kết luận |
|---|---|---|
| Web và backend | Có prototype FastAPI/React, SQLite, đăng nhập và phân quyền | Có nền phần mềm để phát triển tiếp |
| Nghiệp vụ cảnh báo | Có nhận sự kiện giả lập, tiếp nhận, ghi kết quả, hoàn tất, audit, timeline và bàn giao | Có thể kiểm tra quy trình với dữ liệu giả lập |
| Kiểm tra phần mềm | Phiên 16/11 ghi nhận `make check` đạt, 40 test backend, 25 test frontend và build web | Là bằng chứng kiểm tra phần mềm tại phiên đó; chưa chứng minh chất lượng AI |
| Camera và AI | Camera, MediaPipe, engine, worker và replay/eval chưa được triển khai theo nhật ký đã đối chiếu | Chưa có bằng chứng nhận diện từ camera thật |
| Nền kỹ thuật F00 | Trạng thái Planned; còn các công cụ, hook, CI và AC cần hoàn thiện | Prototype chạy được chưa đồng nghĩa F00 Done |
| Sử dụng thực tế | Chưa có bằng chứng thử nghiệm lâm sàng, hiệu quả công việc hoặc vận hành dài hạn trong tài liệu đã đọc | Chưa thể công bố sẵn sàng dùng trong cơ sở chăm sóc |

Kiểm tra bổ sung ngày 17/11/2026 khi lập tài liệu: `make check` hiện có PASS, gồm 40 test backend, 25 test frontend và build web. Lượt chạy thành công thực hiện ngoài sandbox sau khi lượt trong sandbox bị ngắt ở pytest. Đây vẫn là kiểm tra prototype, không bao gồm bằng chứng camera/AI, toàn bộ công cụ F00 hoặc E2E.

Các số test trên là kết quả lịch sử. Kết quả kiểm tra riêng của phiên lập tài liệu được ghi trong `session-log.md`. Nguồn hiện trạng: `TASKS.md`, `session-log.md`, `SUMMARY.md`; không phải một đợt đánh giá runtime/AI mới.

## 3. Công nghệ và lý do lựa chọn

| Lớp | Công nghệ / thiết kế | Vai trò và lý do lựa chọn | Điều kiện hoặc giới hạn |
|---|---|---|---|
| Nguồn hình | Webcam USB; OpenCV | Đọc hình và timestamp; ưu tiên camera cố định cho demo một giường | Cần kiểm tra thiết bị, góc nhìn, ánh sáng và mất kết nối |
| AI cơ thể | MediaPipe Pose Landmarker Full; Lite dự phòng | Dùng model pretrained lấy 33 landmark cơ thể, phù hợp hướng không train | Không cung cấp sẵn sự kiện rời giường; phải đo với tư thế nằm và che khuất |
| AI khuôn mặt | MediaPipe Face Landmarker | Nhánh bổ sung tín hiệu quan sát khi mặt đủ rõ | Hoãn trong demo core; không suy ra đau, ý thức hoặc chẩn đoán |
| Engine | Python thuần, state machine, rule theo thời gian | Kết hợp landmark, vùng giường ROI, chất lượng và thời gian duy trì; có thể replay và kiểm thử xác định | Rule phải có ca âm tính; cần hiệu chỉnh trên dữ liệu phát triển |
| Kết nối xử lý | Worker riêng, HTTP client | Tách inference khỏi API; gửi trạng thái, heartbeat và sự kiện | Cần kiểm thử gửi lại, chống trùng và khôi phục kết nối |
| API | FastAPI, Pydantic, SQLAlchemy | Xác thực dữ liệu và xử lý nghiệp vụ; tái sử dụng prototype | Worker không ghi DB trực tiếp |
| Lưu trữ | SQLite ở prototype; PostgreSQL + Alembic theo F01 | Giữ điểm xuất phát hiện có, có lộ trình migration theo kiến trúc đích | F00 không tự chuyển DB hoặc bỏ qua F01 |
| Realtime | WebSocket | Cập nhật dashboard, cảnh báo và trạng thái | API phải commit dữ liệu trước khi phát; cần xử lý mất kết nối |
| Giao diện | React, TypeScript, Mantine, TanStack Query | Web tiếng Việt, hỗ trợ theo dõi và thao tác nghiệp vụ | Text tập trung trong `vi.ts`; phân quyền cần được thực thi ở API |
| Chất lượng | pytest, Vitest; mypy/import-linter/hook/CI theo F00; Playwright theo F30 | Kiểm tra logic, giao diện, kiến trúc và luồng tích hợp | Các công cụ còn thiếu phải được triển khai và chạy thật |

Nguồn: HS §5–6; PRD §6–7; `tech-stack.md`; F00, F05–F19, F30; phạm vi realtime đã chốt. Tên công nghệ là lựa chọn thiết kế; không có nghĩa toàn bộ đã được cài đặt.

### Luồng xử lý mục tiêu

```text
Camera thật, một giường
    → OpenCV: frame và timestamp
    → MediaPipe Pose: landmark cơ thể
    → Kiểm tra chất lượng và người mục tiêu
    → Engine: ROI + diễn biến + thời gian duy trì
    → Worker → API → commit DB → WebSocket
    → Web: sự kiện / cảnh báo
    → Nhân viên tiếp nhận → kiểm tra → ghi kết quả → hoàn tất
    → Timeline và bàn giao ca
```

Nhánh hiển thị skeleton phải được dựng từ landmark thật. SVG dựng theo trạng thái giả lập hiện tại chưa phải bằng chứng AI.

### Đóng góp của nhóm khi sử dụng model pretrained

Đóng góp dự kiến tập trung ở bốn phần: chuyển landmark thành sự kiện có ý nghĩa theo thời gian; nhận biết lúc thiếu dữ liệu; nối sự kiện vào quy trình có người chịu trách nhiệm; xây dựng dữ liệu và công cụ đánh giá có thể lặp lại. Giá trị từng phần phải được chứng minh bằng test và thực nghiệm. Nhóm không tuyên bố tự huấn luyện model hoặc phát minh thuật toán pose.

LLM/VLM chưa cần cho luồng cảnh báo đã chốt và đang ngoài phạm vi demo. Không có cơ sở để thêm thành phần sinh văn bản khi nhu cầu hiện tại là sự kiện có cấu trúc và khả năng truy vết.

## 4. Tính khả thi

### 4.1. Khả thi về kỹ thuật: có cơ sở, còn phải thử

Model pretrained giúp nhóm bắt đầu mà không cần thu thập tập dữ liệu huấn luyện hay tự tối ưu trọng số. Backend và web đã có giúp giảm lượng công việc nghiệp vụ cần xây mới. Engine tách khỏi camera và API cho phép kiểm tra rule bằng dữ liệu tổng hợp trước khi tích hợp model.

Điểm khó nằm ở tính đúng đắn trong bối cảnh thực tế: người nằm, chăn che, camera lệch, nhiều người và mất quan sát. Model trích xuất được landmark chưa đủ để khẳng định phát hiện sự kiện đúng. Vì vậy, đánh giá phù hợp nhất hiện tại là **có cơ sở để xây dựng prototype một giường trong điều kiện kiểm soát; chưa đủ bằng chứng để khẳng định triển khai thực tế**.

### 4.2. Khả thi về thiết bị và vận hành

Thiết kế ưu tiên laptop, webcam và mạng nội bộ, CPU trước. Mục tiêu pose ≥10 FPS ở 720p và delivery dưới 1 giây là mục tiêu/giả định trong PRD, chưa phải số đo đạt được. Delivery cũng không phải toàn bộ độ trễ từ hành động đến cảnh báo; engine cần thời gian duy trì để xác nhận điều kiện.

Cần đo Full và Lite trên cùng máy, cùng dữ liệu, ghi FPS, CPU/RAM, frame bỏ, chất lượng sự kiện và độ trễ. Nếu giảm độ phân giải hoặc thay model, phải công bố điều kiện và kiểm tra lại. Nguồn: PRD NFR04; F11, F29; kế hoạch demo.

### 4.3. Khả thi về nguồn lực

Kế hoạch 5 ngày trước đây ước lượng 76 giờ công cho hai người, gồm 68 giờ chính và 8 giờ dự phòng. Đây là giả định lập kế hoạch cho demo hẹp, chưa phải lịch bảo đảm và không bao trùm toàn bộ AC của roadmap.

Phải tính cả thời gian hoàn thiện F00, xử lý các phụ thuộc, thu thập dữ liệu có đồng ý và sửa lỗi tích hợp. Nếu chỉ có một người hoặc thiết bị chưa ổn định, cần điều chỉnh thời lượng/phạm vi có ghi nhận; không tự bỏ kiểm tra để giữ lời hứa 5 ngày.

### 4.4. Khả thi kinh tế: cần bảng chi phí thật

Khả năng tận dụng máy tính và camera sẵn có là lợi thế tiềm năng. Chưa có bảng báo giá hoặc phép đo vận hành đủ để kết luận “chi phí thấp hơn” giải pháp khác.

Một bảng chi phí cần gồm camera, giá đỡ, máy xử lý, mạng/điện, lắp đặt và hiệu chỉnh, bảo trì, hỗ trợ, quản lý dữ liệu và thời gian người dùng xử lý cảnh báo. Chi phí cho một giường không thể nhân thẳng lên nhiều giường khi chưa benchmark tải và mô hình vận hành. Đây là đề xuất đánh giá, không phải ngân sách đã duyệt.

## 5. Tính thực thi: từ ý tưởng đến kết quả kiểm chứng

Thứ tự thực hiện phải tuân theo phụ thuộc trong ROADMAP. Bảng dưới tổng hợp đầu ra theo giai đoạn, không cho phép bắt đầu feature khi phụ thuộc chưa Done.

| Giai đoạn | Công việc chính | Đầu ra nghiệm thu |
|---|---|---|
| Hoàn thiện nền | Thực hiện kế hoạch F00, công cụ kiểm tra, hook, CI và type API | Đủ AC1–AC6, bằng chứng Windows/CI và review |
| Camera và schema | F05, F10; sau đó F11 theo phụ thuộc | Camera đọc ổn, timestamp đúng, landmark thật và schema thống nhất |
| Nền nghiệp vụ và worker | Hoàn thiện F01–F04, F06 và các phụ thuộc liên quan | Phiên theo dõi, worker/API, dữ liệu có truy vết theo spec |
| Engine và đánh giá phát triển | F13–F16; replay theo F12 | Rule có test dương/âm, xử lý thiếu quan sát, báo cáo dev |
| Luồng web realtime | Các feature hiển thị/ROI và F17–F24 theo phụ thuộc | Camera → sự kiện → DB → web → xác minh → timeline/bàn giao |
| Chốt demo và đánh giá | Phần hiển thị riêng tư đã chốt, đánh giá và chuẩn bị demo theo spec | Báo cáo có điều kiện thử, runbook, test phù hợp, ba lượt chạy trọn liên tiếp |

Prototype là điểm xuất phát để đối chiếu AC. Việc tái sử dụng code không tự chuyển trạng thái feature sang Done. Face, LLM/VLM và đa camera được hoãn trong demo core; các phần còn lại trong roadmap vẫn giữ trạng thái và yêu cầu riêng.

### Kịch bản nghiệm thu dễ quan sát

1. Khởi động hệ thống, đăng nhập và mở phiên theo dõi một giường mô phỏng.
2. Người tham gia nằm, ngồi dậy, ra mép giường và rời vùng giường; đối chiếu landmark, trạng thái, thời điểm và cảnh báo.
3. Nhân viên tiếp nhận, kiểm tra thực tế, ghi kết quả rồi hoàn tất cảnh báo.
4. Người tham gia quay lại; kiểm tra timeline và tổng hợp bàn giao.
5. Thử trở mình, người đi ngang, che camera và mất nguồn để kiểm tra ca âm tính, thiếu quan sát và phục hồi.
6. Chạy trọn ba lần liên tiếp trên máy demo, lưu bằng chứng và danh sách lỗi còn lại.

Replay dùng để hiệu chỉnh, regression và dự phòng có công bố. Simulator kiểm tra nghiệp vụ. Hai nguồn này không thay nghiệm thu camera thật realtime. Nguồn: HS §8; `DEMO-REALTIME-SCOPE.md`; kế hoạch demo §9–11.

## 6. Tính ứng dụng và giá trị AI trong đời sống

### 6.1. Giá trị đối với từng người liên quan

| Đối tượng | Giá trị kỳ vọng | Bằng chứng cần thu |
|---|---|---|
| Điều dưỡng | Biết giường có tình huống cần kiểm tra, có thông tin thời điểm và trạng thái xử lý | Thời gian tìm/tiếp nhận cảnh báo, lỗi thao tác, mức làm phiền |
| Phụ trách ca | Theo dõi cảnh báo tồn đọng và tổng hợp bàn giao | Thời gian bàn giao, mức đầy đủ, khả năng tìm thông tin |
| Bác sĩ | Tra cứu diễn biến quan sát được làm thông tin tham khảo | Tác vụ tra cứu và phản hồi chuyên môn; timeline không thay hồ sơ bệnh án |
| Người được quan sát | Có khả năng được chú ý khi xuất hiện sự kiện trong phạm vi phát hiện | Chất lượng sự kiện và phản hồi người tham gia; chưa có bằng chứng cải thiện kết quả chăm sóc |
| Đơn vị sử dụng | Quản lý quy trình tiếp nhận và truy vết thao tác | Chi phí, tải vận hành, bảo trì và kiểm soát truy cập |

Nguồn nhu cầu và vai trò: PRD §3–4; HS §2–4. Các lợi ích là kỳ vọng cần kiểm chứng, không phải kết quả đã đo.

### 6.2. Ý nghĩa của AI trong giải pháp

AI phù hợp ở bước chuyển hình ảnh phức tạp thành biểu diễn cơ thể. Logic theo thời gian biến biểu diễn đó thành sự kiện. Phần mềm nghiệp vụ đưa sự kiện đến người có trách nhiệm và lưu kết quả xác minh. Cách kết hợp này làm rõ AI hỗ trợ khâu nào và con người quyết định khâu nào.

Bài học ứng dụng có thể rút ra là: bắt đầu từ một nhu cầu cụ thể, chọn đầu ra có thể kiểm tra, thiết kế trạng thái khi AI thiếu dữ liệu và đo hiệu quả của toàn bộ quy trình. Đây là nhận định tổng hợp, không phải chức năng mới của dự án.

### 6.3. So sánh với phương án khác

| Phương án | Điểm đáng cân nhắc | Câu hỏi cần đánh giá |
|---|---|---|
| Quan sát trực tiếp | Có thông tin ngữ cảnh và khả năng kiểm tra thực tế | PostCare hỗ trợ tác vụ nào trong quy trình hiện có? |
| Camera thông thường | Cung cấp hình ảnh để người dùng tự đánh giá | Cảnh báo có giúp tìm tình huống nhanh hơn và có gây thêm phiền nhiễu không? |
| Nút gọi | Cho phép người dùng chủ động yêu cầu hỗ trợ | Những tình huống quan sát nào có thể bổ sung cho cơ chế chủ động này? |
| Cảm biến áp lực | Cung cấp tín hiệu tiếp xúc/tải trọng cần được thử trong bối cảnh giường | Chi phí, tín hiệu phát hiện và báo sai khác camera thế nào? |
| PostCare AI | Mục tiêu kết hợp diễn biến hình ảnh, cảnh báo và lịch sử xử lý | Có đạt chất lượng và lợi ích đủ để bù chi phí lắp đặt/vận hành không? |

Bảng là khung đối chiếu đề xuất, chưa phải kết quả thử nghiệm so sánh. Chưa có cơ sở tuyên bố PostCare tốt hơn hoặc thay thế các phương án này. Tích hợp cảm biến không thuộc phạm vi triển khai hiện tại.

## 7. Đánh giá để ý tưởng có sức thuyết phục

### Ba lớp bằng chứng cần tách biệt

| Lớp | Cần chứng minh | Không được suy rộng thành |
|---|---|---|
| Phần mềm | API, quyền, vòng đời cảnh báo, lưu trước phát sau, giao diện và khôi phục hoạt động đúng | Model nhận diện đúng |
| AI và engine | Phát hiện từng loại sự kiện trên dữ liệu có ground truth, kể cả ca khó | Có hiệu quả lâm sàng |
| Quy trình sử dụng | Người dùng hoàn thành tác vụ nhanh/đúng hơn hoặc có lợi ích phù hợp được đo | Cải thiện kết quả sức khỏe nếu chưa nghiên cứu điều đó |

### Bộ thử và chỉ số

- Dùng người trưởng thành tự nguyện mô phỏng; ghi nhận quyền sử dụng, thời hạn lưu và quyền dùng hình ảnh trình diễn. Không dùng video bệnh nhân thật trong phạm vi hiện tại.
- Tách tập phát triển và test theo video/phiên; ưu tiên khác người hoặc khác phiên. Không chia frame liền nhau sang hai tập.
- Hiệu chỉnh rule trên dev, khóa model/config trước test, ghi `config_hash`, phiên bản code và điều kiện camera.
- Báo TP/FP/FN, precision, recall và F1 cho từng sự kiện; cảnh báo sai mỗi giờ; coverage và thời gian mất quan sát.
- Đo detection latency và delivery latency riêng, FPS, CPU/RAM và frame bỏ; báo trung vị/p90 độ trễ theo hướng dẫn đánh giá.
- Công bố trường hợp báo sai, bỏ sót và điều kiện thất bại; không chỉ chọn video đẹp.

Kế hoạch demo đề xuất tập con tám kịch bản, 24 clip dev, 16 clip test và đoạn âm tính ban đầu 30 phút. Đây là giả định nguồn lực, chưa phải dữ liệu đã thu; không thay bộ S01–S16 của đánh giá chính thức và không chứng minh vận hành 24/7.

Về workflow, có thể so sánh thời gian tìm cảnh báo, tiếp nhận, ghi kết quả và tra cứu trên tác vụ tương đương. Cần công bố số người/lượt, thứ tự thử, lỗi và vai trò người tham gia. Nếu thành viên nhóm đóng vai, phải ghi đúng như vậy. Phương pháp này là đề xuất đánh giá, chưa có kết quả.

Chưa đặt sẵn accuracy/F1 đạt được hoặc tỷ lệ giảm công việc. Ngưỡng chấp nhận thực nghiệm cần được chốt sau pilot và trước test, ghi vào spec theo quy trình dự án. Nguồn: HS §8; `evaluation.md`; F16, F29; kế hoạch demo §9.

## 8. Rủi ro và điều kiện sử dụng

| Rủi ro | Cách xử lý trong thiết kế / kế hoạch | Điều phải kiểm chứng |
|---|---|---|
| Che khuất, landmark kém | Chuyển thiếu quan sát, không suy ra rời giường | Ca che chăn, mất landmark, coverage và trạng thái web |
| Nhiều người | Cổng chất lượng và lựa chọn người mục tiêu; mơ hồ thì thiếu quan sát | Người đi ngang và người đứng hỗ trợ cạnh giường |
| Cảnh báo sai | Thời gian duy trì, hysteresis, debounce | FP/giờ và đánh đổi với bỏ sót/độ trễ |
| Bỏ sót | Gán nhãn và xem lại FN; giới hạn phạm vi công bố | Recall từng sự kiện, điều kiện gây lỗi |
| Mất nguồn hoặc mạng | Heartbeat, trạng thái gián đoạn, kết nối lại và retry chống trùng | Không hiển thị dữ liệu cũ như đang live; không mất/trùng sự kiện trong các ca thử |
| Thay vị trí camera | Kiểm tra lại ROI và điều kiện lắp đặt | Khả năng tái lập sau thay góc hoặc khoảng cách |
| Lộ dữ liệu | Phân quyền, audit, không lưu video vận hành, skeleton từ landmark thật | Quyền API/stream, log, bộ đệm và dữ liệu lưu trên đĩa |
| Người dùng hiểu quá mức | Công bố phạm vi, thiếu quan sát và vai trò xác minh | Người thử hiểu đúng thông báo và giới hạn |

Không lưu video vận hành không loại bỏ mọi rủi ro riêng tư: luồng hình, metadata, thông tin phiên và tài khoản vẫn cần quản lý. LAN là phạm vi prototype, không tự chứng minh an toàn hoặc đủ điều kiện triển khai thực tế. Chế độ skeleton giảm hình ảnh nguồn được hiển thị, không nên gọi là ẩn danh tuyệt đối.

Hệ thống không chẩn đoán đau, mất ý thức, biến chứng, không phân loại ngủ/tỉnh, không nhận diện danh tính và không thay yêu cầu trực 1:1. Thử nghiệm ngoài mô phỏng cần đánh giá chuyên môn, quyền riêng tư và điều kiện triển khai phù hợp; đây không phải giai đoạn đã được cho phép hoặc hoàn thành. Nguồn: HS §6.3, §9.1; PRD §5.3, §7, §9; AGENTS.md.

## 9. Cách trình bày trước giám khảo

### Đoạn giới thiệu có thể sử dụng

> PostCare AI hướng tới hỗ trợ nhân viên y tế nhận biết một số thay đổi quan sát được quanh giường bệnh và xử lý cảnh báo có lịch sử. Chúng em sử dụng model pretrained để lấy landmark, sau đó xây dựng logic theo thời gian và quy trình xác minh. Hiện nhóm đã có prototype web/backend bằng dữ liệu giả lập. Mục tiêu tiếp theo là chứng minh một camera thật theo dõi một giường, tạo đúng sự kiện và chạy trọn luồng tiếp nhận, xác minh, hoàn tất. Chúng em đánh giá bằng chất lượng sự kiện, cảnh báo sai, độ trễ và tác vụ sử dụng; công bố cả điều kiện hệ thống không quan sát đủ.

### Luận điểm và bằng chứng nên đi cùng

| Luận điểm | Bằng chứng nên trình bày |
|---|---|
| Chọn đúng bài toán | Quy trình hiện có, trao đổi với người dùng chuyên môn và nhu cầu được xác nhận |
| Công nghệ phù hợp | Sơ đồ vai trò từng lớp, lý do dùng pretrained, benchmark trên máy demo |
| Có đóng góp của nhóm | Rule/engine, test ca âm tính, xử lý thiếu quan sát, workflow và báo cáo eval |
| Có khả năng thực thi | Tiến độ theo phụ thuộc, demo thật, runbook và ba lần chạy liên tiếp |
| Có tiềm năng ứng dụng | Kết quả tác vụ, phản hồi người dùng, chi phí và điều kiện vận hành |
| Hiểu giới hạn | FP/FN, coverage, tình huống thất bại và phạm vi không sử dụng |

Không dùng các câu “đã đạt độ chính xác cao”, “giảm tải điều dưỡng”, “ngăn ngừa tai biến”, “chạy 24/7” hoặc “sẵn sàng triển khai bệnh viện” khi chưa có bằng chứng tương ứng. Khi hỏi về phần chưa làm, nêu trạng thái và phép thử tiếp theo thay vì đưa ra số liệu ước đoán như kết quả thật.

## 10. Kết luận đánh giá hiện tại

**Về công nghệ:** hướng pretrained pose kết hợp engine theo thời gian và web nghiệp vụ phù hợp để bắt đầu thử nghiệm một giường, nhưng chất lượng trong bối cảnh mô phỏng phải được đo.

**Về khả thi:** có nền web/backend và kế hoạch kỹ thuật để phát triển tiếp. Camera/AI realtime, dữ liệu đánh giá và bằng chứng hiệu năng vẫn là các khoảng thiếu quyết định.

**Về thực thi:** mốc gần nhất là hoàn thiện F00 theo AC; mốc sản phẩm cần chứng minh là luồng camera thật đến xác minh và timeline. Hai mốc có đầu ra nghiệm thu khác nhau.

**Về ứng dụng:** giá trị kỳ vọng nằm ở hỗ trợ sự chú ý, tiếp nhận có trách nhiệm và bàn giao có cấu trúc. Lợi ích thực tế, chi phí và mức phù hợp với nhân viên y tế còn cần đánh giá. Demo thành công trong mô phỏng là bước tiến kỹ thuật, chưa đủ để kết luận hiệu quả lâm sàng.

## 11. Nguồn đối chiếu

1. [Hồ sơ sơ loại — HS](../00-source/ho-so-so-loai-2026.md): §1–6, §8–9.
2. [Đề tài gốc — PDF chuyển Markdown](../00-source/de-tai.md): bài toán, phạm vi và đánh giá.
3. [PRD](../01-product/PRD.md): vai trò, chức năng, chỉ số và giới hạn.
4. [Tech stack](../02-architecture/tech-stack.md) và [kiến trúc](../02-architecture/overview.md).
5. [Catalog và engine](../02-architecture/event-engine.md).
6. [F00 và tiêu chí nghiệm thu nền](../03-features/F00-project-skeleton.md).
7. [Roadmap](ROADMAP.md), [TASKS](TASKS.md), [nhật ký](session-log.md), [summary](../../SUMMARY.md).
8. [Phạm vi realtime đã chốt](DEMO-REALTIME-SCOPE.md).
9. [Kế hoạch demo 5 ngày](DEMO-5-DAY-PLAN.md): nguồn lực là giả định, không phải cam kết hoàn thành.
10. [Hướng dẫn đánh giá](../04-guides/evaluation.md) và [lắp camera](../04-guides/camera-setup.md).
11. [MediaPipe Pose Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker): tài liệu công nghệ chính thức để tham khảo; không thay benchmark của nhóm.

Tài liệu này tổng hợp nguồn có sẵn trong repo; không thực hiện khảo sát thị trường, phỏng vấn người dùng, nghiên cứu lâm sàng hoặc benchmark AI mới.
