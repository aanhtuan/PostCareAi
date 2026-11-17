# Thuyết trình và bằng chứng: PostCare AI

Tài liệu dùng khi trình bày trước giám khảo AI4Life và trả lời câu hỏi. Nội dung hợp nhất hai bản đề xuất của nhóm (master spec bán kết/chung kết và bản tổng hợp công nghệ, khả thi, giá trị ứng dụng). Kế hoạch dựng demo nằm ở [DEMO-PLAN.md](../progress/DEMO-PLAN.md).

**Nguyên tắc chung:**

- Tài liệu không thay spec và không tự bổ sung yêu cầu triển khai. Yêu cầu nằm trong [PRD](PRD.md), [QA](qa-decisions.md) và `docs/03-features/`.
- Lợi ích, chi phí và khả năng dùng thực tế là **giả thuyết cần đánh giá**, trừ khi có bằng chứng được nêu rõ.
- Mọi số liệu hoặc nhận định bên ngoài chưa kiểm chứng được trong repo được đánh dấu *(cần kiểm chứng)*.
- Không nêu trạng thái feature ở đây. Trạng thái xem [ROADMAP](../progress/ROADMAP.md) và [TASKS](../progress/TASKS.md).

## 1. Thông điệp chính

**PostCare giúp điều dưỡng biết giường nào vừa có thay đổi cần kiểm tra khi đang phụ trách nhiều người bệnh sau mổ. Người nhà được cấp quyền có thể quan sát đúng người thân của mình, với mức hình ảnh người bệnh đã đồng ý chia sẻ.**

Cách nói ngắn: PostCare biến hình ảnh quanh giường bệnh thành **sự kiện có thời gian**, **cảnh báo có người tiếp nhận** và **lịch sử có thể tra cứu**.

- Camera cung cấp hình ảnh.
- Model AI pretrained trích xuất điểm cơ thể.
- Engine phân tích diễn biến theo thời gian: ngồi dậy, ở mép giường, rời hoặc quay lại giường.
- Nhân viên y tế kiểm tra thực tế, ghi kết quả và hoàn tất cảnh báo trên web tiếng Việt.

Hệ thống là **công cụ hỗ trợ quan sát**. Quyết định chuyên môn thuộc nhân viên y tế. Nguồn: HS §1–3, §4.2; PRD §1–4.

## 2. Câu chuyện người dùng: A01 và A02

Người bệnh ở **A01** đã hồi tỉnh, có thể ngồi dậy và cần hỗ trợ khi bước xuống. Điều dưỡng đang bận ở **A02**.

1. Người bệnh A01 dịch ra mép giường.
2. Trên màn hình trực, A01 hiện giờ xảy ra và cảnh báo để điều dưỡng quyết định tới kiểm tra.
3. Đồng nghiệp thấy cảnh báo đã có người nhận.
4. Người nhà mở điện thoại và thấy diễn biến được phép chia sẻ của A01.
5. Cuối ca, người vào sau tra được ai đã kiểm tra, kết quả ra sao và còn việc gì đang chờ.

Bối cảnh "sau hồi tỉnh" là lựa chọn đề xuất, cần thử với điều dưỡng khoa ngoại.

## 3. Giá trị cho từng người liên quan

| Đối tượng | Giá trị kỳ vọng | Bằng chứng cần thu |
|---|---|---|
| Người bệnh | Cơ hội được hỗ trợ ngay cả khi người chăm sóc vừa bỏ lỡ một chuyển động; được giải thích và tự chọn mức chia sẻ | Chất lượng sự kiện, phản hồi người tham gia. Chưa có bằng chứng cải thiện kết quả chăm sóc |
| Điều dưỡng | Biết nên nhìn giường nào trước, có thời điểm và trạng thái xử lý | Thời gian tìm/tiếp nhận cảnh báo, lỗi thao tác, mức làm phiền |
| Phụ trách ca | Theo dõi cảnh báo tồn đọng, ai đã nhận, tổng hợp bàn giao | Thời gian bàn giao, mức đầy đủ, khả năng tìm thông tin |
| Bác sĩ | Tra cứu diễn biến quan sát được làm thông tin tham khảo | Tác vụ tra cứu, phản hồi chuyên môn. Timeline không thay hồ sơ bệnh án |
| Người nhà | Vẫn có thông tin về người thân trong phạm vi được cho phép | Đọc đúng thông tin được phép; không truy cập được giường khác; mất quyền khi bị thu hồi |
| Đơn vị sử dụng | Quản lý quy trình tiếp nhận và truy vết thao tác | Chi phí, tải vận hành, bảo trì, kiểm soát truy cập |

Thời gian người thật đến giường, số lần phải hỏi lại hoặc giảm số ca ngã là **kết quả cần nghiên cứu riêng**, không phải điều demo chứng minh. Nguồn vai trò: PRD §3–4; HS §2–4.

## 4. Quan sát gì, lúc nào cần gọi người tới

Giữ bốn nhóm tín hiệu của slide sơ khảo (trang 4) và cách nhận biết diễn biến (trang 5). Mỗi giường hiệu chỉnh vùng giường theo góc camera. Theo dõi đúng người qua nhiều khung hình, chỉ ghi sự kiện khi hình đủ rõ và điều kiện được duy trì đủ lâu.

| Điều camera có thể quan sát | Hành vi dự kiến của sản phẩm |
|---|---|
| Nằm, đổi tư thế, nâng thân, ngồi dậy, đứng dậy | Cập nhật trạng thái và lịch sử. Ngồi dậy bình thường chỉ tạo mốc thông tin |
| Ngồi ở mép giường đủ lâu | Báo giường và thời điểm ở mức cần chú ý; mốc có thể xuất hiện trước khi bước xuống |
| Từ mép đi ra ngoài vùng giường, sau đó quay lại | Rời giường: cảnh báo ưu tiên cao. Quay lại: mốc lịch sử |
| Ít vận động kéo dài hoặc vận động tăng | Ghi nhận thay đổi trong khoảng quan sát đủ rõ để người xem kiểm tra bối cảnh |
| Chuyển động nghi ngã (thân hạ nhanh, đổi hướng đột ngột, kết thúc ở vị trí thấp) | Hiện "Phát hiện chuyển động bất thường - đề nghị kiểm tra". Nhân viên xác minh tại giường. Sự kiện riêng, khác rời giường |
| Mắt khép, nheo mắt, lông mày thay đổi | Nhánh phụ khi thấy rõ mặt. Theo F26, phối hợp nhiều tín hiệu kéo dài mới tạo cảnh báo "biểu hiện khuôn mặt cần kiểm tra". Chỉ đưa lên sân khấu khi có kết quả đo |
| Chăn che, người khác chắn, mất dấu | "Không đủ dữ liệu quan sát". Camera mất kết nối: báo tình trạng camera. Tạm dừng vì riêng tư: hiện trạng thái tạm dừng |

Không suy ra đau, mất ý thức, ngủ/tỉnh, biến chứng, danh tính hoặc việc ngã đã xảy ra. Mức ưu tiên nói lên nhu cầu kiểm tra của quy trình, không phải nguy cơ lâm sàng. Căn cứ: HS §5, §9.1; PDF §7; [catalog sự kiện](../02-architecture/event-engine.md); [ADR-0009](../02-architecture/decisions/ADR-0009-abnormal-movement-code.md).

## 5. Ai được xem, ai được xử lý

| Người dùng | Quyền và nhiệm vụ đề xuất |
|---|---|
| Người bệnh | Được giải thích camera quan sát gì, dữ liệu nào được lưu, ai xem được. Chọn chia sẻ cho thân nhân nào, ở mức nào, trong bao lâu. Có cách yêu cầu dừng hoặc rút quyền |
| Điều dưỡng | Xem các giường phụ trách trên một màn hình. Mỗi thẻ có tình trạng quan sát, sự kiện mới, mức ưu tiên, tình trạng tiếp nhận. Mở giường, nhận việc, đến kiểm tra, ghi kết quả |
| Phụ trách ca | Xem việc tồn, ai đã nhận, kết quả để bàn giao. Quản lý chế độ hiển thị trong phạm vi được cấp |
| Người nhà | Tài khoản riêng. Chỉ xem trạng thái, diễn biến và chế độ hình được chia sẻ cho **đúng phiên của người thân**. Không xem giường khác, không ghi kết quả chuyên môn |
| Bác sĩ, quản trị | Bác sĩ tra cứu (PRD). Quản trị cấu hình giường, camera, vùng quan sát. Thẩm quyền xác minh người đại diện và duyệt quyền xem cần thống nhất với cơ sở |

**Chấp thuận quan sát khác chấp thuận chia sẻ.** Ví dụ: người bệnh đồng ý cho điều dưỡng theo dõi bằng camera nhưng chỉ muốn con mình thấy trạng thái. Khi đó tài khoản người con chỉ nhận thông tin trạng thái.

- Người nhà xác nhận điều kiện sử dụng quyền xem.
- Nếu cần người ký thay, cơ sở xác minh tư cách đại diện. Quan hệ gia đình tự nó không phải giấy phép mở camera.
- Với cuộc thi: dùng người trưởng thành tự nguyện, ghi nhận riêng việc quay clip thử và trình chiếu trước khán giả.
- Tham chiếu pháp lý: [Luật Bảo vệ dữ liệu cá nhân](https://vanban.chinhphu.vn/?docid=214590&pageid=27160) *(cần kiểm chứng đường dẫn và số hiệu; PRD §9 ghi Luật 91/2025/QH15 và Nghị định 356/2025/NĐ-CP)*.

**Chế độ hiển thị đề xuất:** chỉ thông tin; khung xương trên nền trống; video đã làm mờ; video gốc theo quyền riêng; tạm dừng thu hình khi thay đồ hoặc chăm sóc riêng tư.

- Đề xuất mặc định cho người nhà: chỉ thông tin, mời chọn khung xương nếu được cấp thêm.
- F28 hiện giả định mặc định mờ mặt cho giao diện hiện hành. Nhóm cần duyệt mặc định riêng cho từng vai trò.
- Mờ mặt vẫn có thể lộ cơ thể, người đi ngang và bối cảnh phòng. Khung xương giảm hình ảnh nguồn, **không** nên gọi là ẩn danh tuyệt đối.

**Điều kiện cho phần riêng tư:**

- Xử lý ảnh trên máy tại cơ sở, không lưu video vận hành.
- Chế độ khung xương: máy chủ chỉ gửi dữ liệu cần để vẽ khung xương của người được theo dõi. Không chắc đúng người thì báo thiếu quan sát.
- Giới hạn quyền ở cả API và luồng trực tiếp; ghi nhận cấp, xem, thu hồi quyền.
- Kết thúc phiên hoặc đổi bệnh nhân tại cùng giường: người nhà mất quyền của phiên cũ. Kiểm tra bằng điện thoại đang xem, kể cả khi kết nối lại.
- Bản đầu thử trong cùng mạng. Truy cập từ nhà là mở rộng, cần xác thực, bảo vệ đường truyền và kiểm tra với cơ sở trước khi dùng dữ liệu thật.

**Ranh giới với tài liệu hiện hành.** HS §4–8 và PRD giữ mốc tối thiểu một giường. QA#13 xếp nhiều camera đồng thời vào F31. Quyền người nhà theo phiên và luồng chấp thuận là mở rộng cho vòng sau. Trước khi viết code các phần này, chuyển quyết định nhóm đã duyệt vào PRD, QA, F28/F31 và spec quyền người nhà.

## 6. AI làm phần nào, nhóm làm phần nào

### 6.1. Model

- **MediaPipe Pose Landmarker** trả 33 điểm cơ thể. Chọn biến thể Lite / Full / Heavy bằng benchmark trên đúng máy và clip demo (QA#35; F11 giả định mặc định Full, có Lite để so FPS).
- **Face Landmarker** trả điểm mặt và 52 hệ số biểu cảm. Chỉ thử sau khi phần cơ thể chạy ổn ở đúng góc đặt máy.
- Bản đề xuất có nêu MoveNet làm dự phòng. QA#35 đã chốt **không dùng MoveNet**; dự phòng là RTMPose qua adapter.
- Hiệu chỉnh vùng và thời gian duy trì bằng dữ liệu, **không train hoặc fine-tune**.
- Tài liệu chính thức: [MediaPipe Pose](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) · [MediaPipe Face](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker). Không thay benchmark của nhóm.

LLM/VLM không cần cho luồng cảnh báo đã chốt và ngoài phạm vi demo: nhu cầu là sự kiện có cấu trúc và truy vết được.

### 6.2. Luồng xuyên suốt

```text
Camera (một giường)
    → OpenCV: frame và timestamp
    → MediaPipe Pose: landmark cơ thể
    → Kiểm tra chất lượng và người mục tiêu
    → Engine: vùng giường + diễn biến + thời gian duy trì
    → Sự kiện của đúng phiên → Worker → API → commit DB → WebSocket
    → Màn hình có quyền: sự kiện / cảnh báo
    → Tiếp nhận → kiểm tra → ghi kết quả → hoàn tất
    → Timeline và bàn giao ca
```

- Lưu xong mới phát. Cùng một sự kiện không sinh nhiều việc do tín hiệu dao động hoặc kết nối lại.
- Khung xương hiển thị phải dựng từ landmark thật. Hình vẽ theo trạng thái giả lập không phải bằng chứng AI.

### 6.3. Công nghệ theo lớp

| Lớp | Công nghệ / thiết kế | Vai trò | Điều kiện hoặc giới hạn |
|---|---|---|---|
| Nguồn hình | Webcam USB / điện thoại; OpenCV | Đọc hình và timestamp | Kiểm tra thiết bị, góc, ánh sáng, mất kết nối |
| AI cơ thể | MediaPipe Pose (biến thể theo benchmark) | 33 landmark, không train | Không cho sẵn sự kiện rời giường; phải đo với tư thế nằm, che khuất |
| AI khuôn mặt | MediaPipe Face Landmarker | Tín hiệu bổ sung khi mặt đủ rõ | Không suy ra đau, ý thức, chẩn đoán |
| Engine | Python thuần, state machine, rule theo thời gian | Kết hợp landmark, vùng giường, chất lượng, thời gian duy trì; replay và test xác định | Rule phải có ca âm tính; hiệu chỉnh trên tập dev |
| Worker | Tiến trình riêng, HTTP client | Tách inference khỏi API; gửi trạng thái, heartbeat, sự kiện | Gửi lại, chống trùng, khôi phục kết nối. Worker không ghi DB trực tiếp |
| API | FastAPI, Pydantic, SQLAlchemy | Xác thực dữ liệu, nghiệp vụ | Phân quyền thực thi ở API |
| Lưu trữ | SQLite ở prototype; PostgreSQL + Alembic theo F01 | Lộ trình migration theo kiến trúc đích | Xem [ADR-0010](../02-architecture/decisions/ADR-0010-prototype-sqlite-simulator.md) |
| Realtime | WebSocket | Cập nhật dashboard, cảnh báo, trạng thái | Commit trước khi phát; xử lý mất kết nối |
| Giao diện | React, TypeScript, Mantine, TanStack Query | Web tiếng Việt | Text chỉ trong `vi.ts` |
| Chất lượng | pytest, Vitest, mypy, import-linter, hook, CI; Playwright (F30) | Kiểm tra logic, giao diện, kiến trúc, tích hợp | Công cụ phải chạy thật |

Tên công nghệ là lựa chọn thiết kế, không có nghĩa đã cài đặt xong. Chi tiết: [tech-stack.md](../02-architecture/tech-stack.md), [overview.md](../02-architecture/overview.md).

### 6.4. Đóng góp của nhóm khi dùng model pretrained

Nhóm **không** tuyên bố tự huấn luyện model hay phát minh thuật toán pose. Đóng góp nằm ở bốn phần, mỗi phần phải chứng minh bằng test và thực nghiệm:

1. Chuyển landmark thành sự kiện có ý nghĩa theo thời gian (vùng giường, chuỗi mép giường → rời giường, thời gian duy trì, chống lặp).
2. Nhận biết lúc thiếu dữ liệu và không kết luận bừa ("Không đủ dữ liệu quan sát").
3. Nối sự kiện vào quy trình có người chịu trách nhiệm: tiếp nhận, kết quả, audit, timeline, bàn giao; quyền người nhà theo phiên.
4. Xây dữ liệu và công cụ đánh giá lặp lại được (replay, eval, ngưỡng khóa trước tập test).

AI hợp ở bước chuyển hình ảnh phức tạp thành biểu diễn cơ thể. Logic theo thời gian biến biểu diễn đó thành sự kiện. Phần mềm nghiệp vụ đưa sự kiện đến người có trách nhiệm. Cách chia này làm rõ AI hỗ trợ khâu nào, con người quyết định khâu nào.

## 7. Bài toán ở Việt Nam

- Việc quan sát liên tục đòi hỏi thời gian và sự chú ý của người phụ trách, nhất là khi trông nhiều giường (PDF §2; HS §2.1).
- Camera thông thường vẫn bắt người dùng chủ động nhìn và tự nhớ diễn biến.
- Khi đổi ca, thông tin cần truyền lại theo giường, thời điểm, sự kiện và tình trạng xử lý.

Số liệu tham khảo bên ngoài:

- Một nghiên cứu ở khoa Ngoại Tiêu hóa, Bệnh viện Thống Nhất, khảo sát vận động sớm ở **78 người sau mổ u đường tiêu hóa**; bối cảnh sát đối tượng dự kiến *(cần kiểm chứng)*. [Nghiên cứu vận động sau mổ](https://www.vjol.info.vn/tcsuckhoevalaohoa/vi/article/view/137980/)
- Một nghiên cứu tại **9 bệnh viện công TP.HCM**: hành động xuống giường xuất hiện trong **21/101 ca ngã nội trú** được ghi nhận *(cần kiểm chứng; xem bảng 3)*. [Nghiên cứu ngã nội trú](https://pmc.ncbi.nlm.nih.gov/articles/PMC11416768/)

Con số thứ hai mô tả các ca đã ngã. Chưa có số liệu riêng cho biết bao nhiêu bệnh nhân hậu phẫu cần cảnh báo của PostCare. Mức độ phổ biến, mức ưu tiên và chi phí bài toán tại một đơn vị cụ thể cần khảo sát; nhóm chưa có khảo sát điều dưỡng độc lập và chưa có đối tác bệnh viện.

## 8. So sánh phương án

| Phương án | Điều phương án đó làm tốt | Câu hỏi PostCare phải trả lời |
|---|---|---|
| Người trực tại giường / quan sát trực tiếp | Nhìn được bối cảnh, hỗ trợ tại chỗ | Khi người trực bận việc khác, PostCare có giúp nhận đúng giường cần kiểm tra? Yêu cầu trực trực tiếp của cơ sở vẫn áp dụng |
| Camera thông thường | Cho điều dưỡng hoặc người nhà xem từ xa | Người dùng có tìm đúng thay đổi và kết quả xử lý nhanh hơn trong cùng nhiệm vụ? Có gây thêm phiền nhiễu? |
| Nút gọi | Người bệnh chủ động yêu cầu hỗ trợ | Tình huống quan sát nào bổ sung được cho cơ chế chủ động này? |
| Cảm biến áp lực | Tín hiệu tiếp xúc/tải trọng tại giường | Chi phí, tín hiệu phát hiện và báo sai khác camera thế nào? |
| Giường báo động rời giường | Cảnh báo khi người bệnh dịch về mép hoặc rời giường | Chuỗi vận động và lịch sử xử lý bổ sung gì? So chi phí thiết bị khi có báo giá tương đương. [Stryker](https://techweb.stryker.com/Critical_Care/FL27/6_0/Operation/2141-800-301A.pdf) *(cần kiểm chứng)* |
| Hệ thống quan sát tập trung | Quan sát từ xa có AI, tạm dừng vì riêng tư | Nhóm có chạy được bằng thiết bị sẵn có, giao diện tiếng Việt, quyền gia đình theo phiên? Chưa có phép so hiệu năng trực tiếp. [AvaSure](https://avasure.com/patient-safety-observation/) *(cần kiểm chứng)* |
| PostCare AI | Kết hợp diễn biến hình ảnh, cảnh báo, lịch sử xử lý | Chất lượng và lợi ích có đủ bù chi phí lắp đặt, vận hành? |

Bảng là khung đối chiếu, chưa phải kết quả thử so sánh. **Không** tuyên bố PostCare tốt hơn hoặc thay thế các phương án này. Tích hợp cảm biến không thuộc phạm vi hiện tại (PRD §5.3).

**Tiêu chí chấm.** Theo ghi chú meeting, chất lượng sản phẩm chiếm 30% và hiệu quả chiếm 20% *(cần kiểm chứng với thể lệ cuối trước khi nộp)*. Lập luận nên đi từ một tình huống thật cần hỗ trợ, qua demo giám khảo tự thử được, tới số liệu bỏ sót, báo nhầm và độ trễ. Cảnh báo sớm có cải thiện chăm sóc hay không còn phụ thuộc người nhận có thể đến giường.

## 9. Tính khả thi

**Kỹ thuật: có cơ sở, còn phải thử.**

- Model pretrained giúp bắt đầu mà không cần tập huấn luyện hay tối ưu trọng số.
- Backend và web prototype giảm phần nghiệp vụ phải xây mới ([README](../../README.md)).
- Engine tách khỏi camera và API, nên kiểm tra rule bằng dữ liệu tổng hợp trước khi có model.
- Điểm khó là tính đúng trong bối cảnh thật: người nằm, chăn che, camera lệch, nhiều người, mất quan sát. Model trả landmark chưa đủ để khẳng định sự kiện đúng.

**Thiết bị và vận hành.** Laptop, webcam, mạng nội bộ, CPU trước. Mục tiêu ≥10 FPS pose ở 720p và delivery dưới 1 giây là giả định A07 (PRD NFR04), chưa phải số đo. Delivery không phải toàn bộ độ trễ từ hành động đến màn hình: engine cần thời gian duy trì để xác nhận. Phải đo các biến thể pose trên cùng máy, cùng dữ liệu (FPS, CPU/RAM, frame bỏ, chất lượng sự kiện, độ trễ). Giảm độ phân giải hoặc đổi model thì công bố điều kiện và đo lại.

**Nguồn lực.** Phải tính cả việc hoàn thiện F00, phụ thuộc giữa feature, thu dữ liệu có đồng ý và sửa lỗi tích hợp. Thiếu người hoặc thiết bị chưa ổn thì thu hẹp phạm vi có ghi nhận; **không** bỏ kiểm tra để giữ lời hứa thời gian.

**Kinh tế: cần bảng chi phí thật.** Tận dụng máy và camera sẵn có là lợi thế tiềm năng, nhưng chưa có báo giá hay số đo đủ để nói "chi phí thấp hơn". Bảng chi phí cần gồm: camera, giá đỡ, máy xử lý, mạng/điện, lắp đặt và hiệu chỉnh, bảo trì, hỗ trợ, quản lý dữ liệu, thời gian người dùng xử lý cảnh báo. Không nhân thẳng chi phí một giường lên nhiều giường khi chưa benchmark tải.

**Thực thi.** Thứ tự theo phụ thuộc trong [ROADMAP](../progress/ROADMAP.md). Tái dùng code prototype không tự chuyển feature sang Done. Phụ thuộc cho từng vòng thi: [DEMO-PLAN.md](../progress/DEMO-PLAN.md#phụ-thuộc-feature).

## 10. Ba lớp bằng chứng

| Lớp | Cần chứng minh | Không được suy rộng thành |
|---|---|---|
| Phần mềm | API, quyền, vòng đời cảnh báo, lưu trước phát sau, giao diện, khôi phục | Model nhận diện đúng |
| AI và engine | Phát hiện từng loại sự kiện trên dữ liệu có ground truth, kể cả ca khó | Có hiệu quả lâm sàng |
| Quy trình sử dụng | Người dùng hoàn thành tác vụ nhanh/đúng hơn, hoặc lợi ích phù hợp được đo | Cải thiện kết quả sức khỏe khi chưa nghiên cứu điều đó |

Kết quả `make check` là bằng chứng lớp phần mềm, không chứng minh chất lượng AI. Replay dùng để hiệu chỉnh, regression và dự phòng có công bố; simulator kiểm tra nghiệp vụ. Hai nguồn này không thay nghiệm thu camera realtime.

## 11. Dữ liệu và bộ chỉ số

**Nguồn dữ liệu (đề xuất):**

1. Trước hết dùng **bộ dữ liệu video bên ngoài có giấy phép** cho phép dùng để đánh giá và trình chiếu. Ghi tên bộ, giấy phép, phiên bản, clip đã dùng.
2. Sau đó bổ sung clip của **người trưởng thành tự nguyện** trong nhóm hoặc quen biết, có đồng ý theo [evaluation.md](../04-guides/evaluation.md) §2.
3. Không dùng video bệnh nhân thật. Không dùng dữ liệu để train.

Hiện [evaluation.md](../04-guides/evaluation.md) chỉ mô tả dữ liệu mô phỏng tự quay. Việc dùng bộ dữ liệu ngoài cần ghi vào QA và evaluation.md trước khi dùng.

**Chia tập và khóa cấu hình:**

- Tách dev và test theo video/phiên, ưu tiên khác người hoặc khác phiên. Không chia frame liền nhau sang hai tập.
- Hiệu chỉnh trên dev, khóa model/config trước khi mở tập test; ghi `config_hash`, phiên bản code, điều kiện camera.
- Hai người gán nhãn thời điểm.

**Chỉ số (PRD §8; evaluation.md §5):**

| Nhóm | Chỉ số |
|---|---|
| Sự kiện | TP/FP/FN, precision, recall, F1 cho từng loại, kèm mẫu số. Đánh giá chuyển động bất thường riêng, có ca dễ nhầm: ngồi xuống nhanh, cúi người, che khuất |
| Cảnh báo | Cảnh báo sai mỗi giờ; tính cả sự kiện bị bỏ lỡ lúc camera bị che |
| Quan sát | Coverage, thời gian mất quan sát |
| Độ trễ | Detection latency và delivery latency đo riêng; trung vị, p90 |
| Tài nguyên | FPS từng luồng, CPU, RAM, frame bỏ, cấu hình phần cứng |
| Quy tắc theo thời gian | Cùng model, clip, vùng giường, chống lặp: so quy tắc đơn giản "qua biên" với chuỗi có mép giường và kiểm tra chất lượng |
| Quy trình | So camera thường với PostCare trên hai tình huống tương đương, đổi thứ tự: số người tìm đúng giường, đúng việc còn chờ, thời gian tìm. Ghi số người, số lượt, thứ tự, lỗi, vai trò người thử (thành viên nhóm đóng vai thì ghi đúng như vậy) |
| Người nhà | Đọc đúng thông tin được phép; thử truy cập giường khác; rút quyền giữa phiên |

Công bố cả trường hợp báo sai, bỏ sót và điều kiện thất bại; không chỉ chọn video đẹp. **Không đặt trước con số accuracy** (PDF §13). Ngưỡng chấp nhận thực nghiệm chốt sau pilot và trước test, ghi vào spec. Ngưỡng go/no-go nội bộ để quyết định mang bản nào lên sân khấu nằm ở [DEMO-PLAN.md](../progress/DEMO-PLAN.md) và **không** phải tuyên bố công khai.

Bản tổng hợp có nêu một tập con tám kịch bản, 24 clip dev, 16 clip test và 30 phút âm tính ban đầu. Đó là giả định nguồn lực, không thay bộ S01–S16 của evaluation.md và không chứng minh vận hành 24/7.

## 12. Rủi ro và điều kiện sử dụng

| Rủi ro | Cách xử lý trong thiết kế | Điều phải kiểm chứng |
|---|---|---|
| Che khuất, landmark kém | Chuyển "Không đủ dữ liệu quan sát", không suy ra rời giường | Ca che chăn, mất landmark, coverage, trạng thái trên web |
| Nhiều người | Cổng chất lượng, chọn người mục tiêu; mơ hồ thì thiếu quan sát | Người đi ngang, người đứng hỗ trợ cạnh giường |
| Cảnh báo sai | Thời gian duy trì, hysteresis, debounce | FP/giờ và đánh đổi với bỏ sót, độ trễ |
| Bỏ sót | Gán nhãn và xem lại FN; giới hạn phạm vi công bố | Recall từng sự kiện, điều kiện gây lỗi |
| Mất nguồn hoặc mạng | Heartbeat, trạng thái gián đoạn, kết nối lại, retry chống trùng | Không hiện dữ liệu cũ như đang live; không mất/trùng sự kiện |
| Thay vị trí camera | Kiểm tra lại vùng giường và điều kiện lắp | Tái lập được sau khi đổi góc hoặc khoảng cách |
| Lộ dữ liệu | Phân quyền, audit, không lưu video vận hành, khung xương từ landmark thật | Quyền API/stream, log, bộ đệm, dữ liệu trên đĩa; quyền cũ không mở được phiên mới |
| Người dùng hiểu quá mức | Công bố phạm vi, trạng thái thiếu quan sát, vai trò xác minh | Người thử hiểu đúng thông báo và giới hạn |

Không lưu video vận hành không loại bỏ mọi rủi ro riêng tư: luồng hình, metadata, thông tin phiên và tài khoản vẫn cần quản lý. LAN là phạm vi prototype, không tự chứng minh an toàn hay đủ điều kiện triển khai.

Hệ thống không chẩn đoán đau, mất ý thức, biến chứng; không phân loại ngủ/tỉnh; không nhận diện danh tính; không thay yêu cầu trực 1:1. Thử nghiệm ngoài mô phỏng cần đánh giá chuyên môn, quyền riêng tư và điều kiện triển khai; giai đoạn đó chưa được cho phép. Nguồn: HS §6.3, §9.1; PRD §5.3, §7, §9; AGENTS.md.

## 13. Cách trình bày trước giám khảo

### 13.1. Câu không được nói

Không dùng khi chưa có bằng chứng tương ứng:

- "đã đạt độ chính xác cao"
- "giảm tải điều dưỡng"
- "ngăn ngừa tai biến"
- "chạy 24/7"
- "sẵn sàng triển khai bệnh viện"
- "chạy hai camera đồng thời" (chỉ nói sau khi đã thử hai camera thật trên cùng phần cứng)
- bất kỳ con số nào chưa đo, nói như kết quả thật

Khi bị hỏi về phần chưa làm: nêu trạng thái và phép thử tiếp theo, không đưa số ước đoán.

### 13.2. Luận điểm và bằng chứng đi kèm

| Luận điểm | Bằng chứng nên trình bày |
|---|---|
| Chọn đúng bài toán | Quy trình hiện có, trao đổi với người dùng chuyên môn, nhu cầu được xác nhận |
| Công nghệ phù hợp | Sơ đồ vai trò từng lớp, lý do dùng pretrained, benchmark trên máy demo |
| Có đóng góp của nhóm | Rule/engine, test ca âm tính, xử lý thiếu quan sát, workflow, báo cáo eval |
| Có khả năng thực thi | Tiến độ theo phụ thuộc, demo thật, runbook, ba lần chạy liên tiếp |
| Có tiềm năng ứng dụng | Kết quả tác vụ, phản hồi người dùng, chi phí, điều kiện vận hành |
| Hiểu giới hạn | FP/FN, coverage, tình huống thất bại, phạm vi không sử dụng |

### 13.3. Đoạn giới thiệu mẫu

> PostCare AI hỗ trợ điều dưỡng nhận biết một số thay đổi quan sát được quanh giường bệnh sau mổ, như ngồi ra mép giường hay rời giường, và xử lý cảnh báo có người tiếp nhận, có lịch sử. Chúng em dùng model pretrained để lấy điểm cơ thể, không train lại; phần nhóm xây là logic theo thời gian, cách xử lý khi không quan sát đủ, quy trình tiếp nhận và quyền xem của người nhà theo đúng phiên. Nhóm đã có web và backend cho quy trình cảnh báo, và đang dựng luồng thật từ camera và video qua model tới màn hình. Dữ liệu đánh giá lấy trước từ bộ video có giấy phép, sau đó bổ sung clip của người tình nguyện. Chúng em đánh giá bằng số sự kiện đúng, bỏ sót, cảnh báo sai mỗi giờ, độ trễ và tác vụ của người dùng, và công bố cả những lúc hệ thống không quan sát đủ.

## 14. Kết luận đánh giá hiện tại

- **Công nghệ:** pose pretrained + engine theo thời gian + web nghiệp vụ phù hợp để bắt đầu thử một giường. Chất lượng trong bối cảnh thử phải được đo.
- **Khả thi:** có nền web/backend và kế hoạch kỹ thuật. Camera/AI realtime, dữ liệu đánh giá và số đo hiệu năng là các khoảng thiếu quyết định. Đánh giá phù hợp nhất: có cơ sở để xây prototype một giường trong điều kiện kiểm soát; chưa đủ bằng chứng cho triển khai thực tế.
- **Thực thi:** mốc gần nhất là hoàn thiện F00 theo AC; mốc sản phẩm cần chứng minh là luồng camera thật → xác minh → timeline. Hai mốc có đầu ra nghiệm thu khác nhau. Trạng thái xem [ROADMAP](../progress/ROADMAP.md).
- **Ứng dụng:** giá trị kỳ vọng nằm ở hỗ trợ sự chú ý, tiếp nhận có trách nhiệm và bàn giao có cấu trúc. Lợi ích, chi phí và mức phù hợp với nhân viên y tế còn cần đánh giá. Demo thành công trong điều kiện thử là bước tiến kỹ thuật, chưa đủ kết luận hiệu quả lâm sàng.

## 15. Nguồn đối chiếu

1. [Hồ sơ sơ loại (HS)](../00-source/ho-so-so-loai-2026.md): §1–6, §8–9.
2. [Đề tài gốc (PDF)](../00-source/de-tai.md).
3. [PRD](PRD.md), [QA](qa-decisions.md), [thuật ngữ và từ cấm](glossary.md).
4. [Tech stack](../02-architecture/tech-stack.md), [kiến trúc](../02-architecture/overview.md), [catalog và engine](../02-architecture/event-engine.md).
5. [Danh sách feature](../03-features/README.md), [F00](../03-features/F00-project-skeleton.md).
6. [ROADMAP](../progress/ROADMAP.md), [TASKS](../progress/TASKS.md), [nhật ký](../progress/session-log.md), [hiện trạng prototype](../../README.md).
7. [Hướng dẫn đánh giá](../04-guides/evaluation.md), [lắp camera](../04-guides/camera-setup.md).
8. [Kế hoạch demo](../progress/DEMO-PLAN.md).

Công cụ tra cứu tài liệu khoa học (đối chiếu bài báo, PMID khi làm slide) là công cụ của nhóm, ngoài sản phẩm.

Tài liệu tổng hợp nguồn có trong repo và hai bản đề xuất của nhóm; không thực hiện khảo sát thị trường, phỏng vấn người dùng, nghiên cứu lâm sàng hay benchmark AI mới.
