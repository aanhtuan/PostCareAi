# PostCare AI · Master spec cho bán kết và chung kết AI4Life

**Bản gửi nhóm · 17/11/2026.** Tài liệu tổng hợp hồ sơ sơ loại, slide 12 trang, ghi chú meeting và các quyết định trong buổi trao đổi. Các mốc dưới đây là đề xuất để nhóm phân việc. Chỉ công bố kết quả sau khi đo.

## 1. Nhóm đang làm sản phẩm gì?

**PostCare giúp điều dưỡng biết giường nào vừa có thay đổi cần kiểm tra khi đang phụ trách nhiều người bệnh sau mổ. Người nhà được cấp quyền có thể quan sát đúng người thân của mình, với mức hình ảnh người bệnh đã đồng ý chia sẻ.**

Hãy hình dung người bệnh ở A01 đã hồi tỉnh, có thể ngồi dậy và cần hỗ trợ khi bước xuống. Điều dưỡng đang bận ở A02. Người bệnh dịch ra mép giường. Trên màn hình trực, A01 hiện giờ xảy ra và cảnh báo để điều dưỡng quyết định tới kiểm tra. Đồng nghiệp thấy cảnh báo đã có người nhận. Người nhà mở điện thoại và thấy diễn biến được phép chia sẻ của A01. Cuối ca, người vào sau tra được ai đã kiểm tra, kết quả ra sao và còn việc gì đang chờ.

Giá trị với người bệnh nằm ở **cơ hội được hỗ trợ ngay cả khi người chăm sóc vừa bỏ lỡ một chuyển động**. Giá trị với điều dưỡng nằm ở việc biết nên nhìn giường nào trước. Giá trị với gia đình là vẫn có thông tin về người thân trong phạm vi họ cho phép. Thời gian người thật đến giường, số lần phải hỏi lại hoặc giảm té ngã là những kết quả cần nghiên cứu riêng. Bối cảnh sau hồi tỉnh là lựa chọn đề xuất để thử với điều dưỡng khoa ngoại.

| Trạng thái quyết định | Nội dung |
|---|---|
| Đã thống nhất về hướng sản phẩm | Dùng model có sẵn, giữ nguyên trọng số. Quan sát tư thế, vị trí, vận động và tín hiệu mặt khi đủ rõ. Có tình huống nghi té ngã. Điều dưỡng theo dõi nhiều giường. Người nhà là người dùng trực tiếp có quyền giới hạn. Cần chấp thuận, chế độ riêng tư và người kiểm tra cảnh báo. |
| Đã có trong prototype | Web tiếng Việt và backend tiếp nhận sự kiện giả lập, hiển thị cảnh báo, tiếp nhận, ghi kết quả, lịch sử và bàn giao. Nhóm chưa có đối tác bệnh viện hoặc nhân viên y tế. |
| Cần xây và chứng minh | Camera → model → sự kiện thật, nhiều luồng đồng thời, quyền người nhà theo phiên, chấp thuận và thu hồi, chế độ hình ảnh thực sự bảo vệ dữ liệu. |
| Đề xuất nhóm cần duyệt | Bắt đầu bằng một giường thật cho bán kết, tiến đến hai luồng và hai vai trò cho chung kết. Chọn chế độ mặc định của người nhà, thiết bị mang đi thi, lịch, cỡ mẫu và mục tiêu đo. |

## 2. Quan sát gì và lúc nào cần gọi người tới?

Giữ bốn nhóm tín hiệu của slide sơ khảo trang 4 và cách nhận biết diễn biến ở trang 5. Với mỗi giường, hiệu chỉnh vùng giường theo góc camera. Theo dõi đúng người qua nhiều khung hình và chỉ ghi sự kiện khi hình đủ rõ, điều kiện được duy trì đủ lâu. Điều dưỡng chịu trách nhiệm quyết định cách xử lý tại chỗ.

| Điều camera có thể quan sát | Hành vi dự kiến của sản phẩm |
|---|---|
| Nằm, đổi tư thế, nâng thân, ngồi dậy hoặc đứng dậy | Cập nhật trạng thái và lịch sử. Một lần ngồi dậy bình thường chỉ tạo mốc thông tin. |
| Ngồi ở mép giường đủ lâu | Báo giường và thời điểm ở mức cần chú ý. Đây là mốc có thể xuất hiện trước khi người bệnh bước xuống. |
| Từ mép đi ra ngoài vùng giường, sau đó quay lại | Rời giường tạo cảnh báo ưu tiên cao. Quay lại tạo mốc lịch sử. |
| Ít vận động kéo dài hoặc mức vận động tăng | Ghi nhận thay đổi trong khoảng quan sát đủ rõ để người xem kiểm tra bối cảnh. |
| **Chuyển động nghi té ngã** | Khi có nhiều dấu hiệu như thân hạ nhanh, đổi hướng đột ngột và kết thúc ở vị trí thấp, hiện **“Phát hiện chuyển động bất thường - đề nghị kiểm tra”**. Nhân viên xác minh tại giường. Đây là sự kiện riêng với rời giường. |
| Mắt khép, nheo mắt, lông mày thay đổi | Nhánh phụ dùng khi thấy rõ mặt. Theo thiết kế F26, phối hợp nhiều tín hiệu kéo dài mới tạo cảnh báo biểu hiện cần kiểm tra. Chỉ đưa lên sân khấu khi có kết quả đo. |
| Chăn che, người khác chắn ngang, mất dấu | Hiện “Không đủ dữ liệu quan sát”. Khi camera mất kết nối, báo tình trạng camera. Khi tạm dừng vì riêng tư, hiển thị trạng thái tạm dừng để người xem hiểu lý do. |

Không suy ra đau, mất ý thức, ngủ/tỉnh, biến chứng, danh tính hoặc té ngã đã xác nhận từ ảnh. Các mức ưu tiên nói lên nhu cầu kiểm tra của quy trình. Căn cứ là HS §5, §9.1, PDF §7, [catalog sự kiện](../02-architecture/event-engine.md) và [quyết định về cách gọi chuyển động nghi té ngã](../02-architecture/decisions/ADR-0009-abnormal-movement-code.md).

## 3. Ai được xem và ai được xử lý?

| Người dùng | Quyền và nhiệm vụ đề xuất |
|---|---|
| Người bệnh | Được giải thích việc camera quan sát gì, dữ liệu nào được lưu, ai có thể xem. Chọn có chia sẻ cho thân nhân nào, ở mức nào, trong bao lâu. Có cách yêu cầu dừng hoặc rút quyền. |
| Điều dưỡng | Xem các giường phụ trách trên một màn hình. Mỗi thẻ có tình trạng quan sát, sự kiện mới, mức ưu tiên và tình trạng tiếp nhận. Mở đúng giường, nhận việc, đến kiểm tra, ghi kết quả. |
| Phụ trách ca | Xem việc tồn, ai đã nhận và kết quả để bàn giao. Quản lý chế độ hiển thị trong phạm vi đã được cấp. |
| Người nhà | Đăng nhập bằng tài khoản riêng. Chỉ xem trạng thái, diễn biến và chế độ hình đã được chia sẻ cho **đúng phiên của người thân**. Không xem giường khác hoặc ghi kết quả xử lý chuyên môn. |
| Bác sĩ, quản trị | Theo PRD, bác sĩ có quyền tra cứu. Quản trị cấu hình giường, camera và vùng quan sát. Thẩm quyền xác minh người đại diện và phê duyệt quyền xem cần thống nhất với cơ sở. |

**Chấp thuận quan sát khác với chấp thuận chia sẻ.** Ví dụ, người bệnh đồng ý cho điều dưỡng theo dõi bằng camera nhưng chỉ muốn con mình thấy trạng thái. Khi đó tài khoản người con chỉ nhận thông tin trạng thái. Người nhà xác nhận điều kiện sử dụng quyền xem. Nếu cần người ký thay người bệnh, cơ sở xác minh tư cách đại diện phù hợp. Quan hệ gia đình tự nó không phải giấy phép mở camera. Với cuộc thi, dùng người trưởng thành tự nguyện, ghi nhận riêng việc quay clip thử và trình chiếu trước khán giả. [Luật Bảo vệ dữ liệu cá nhân](https://vanban.chinhphu.vn/?docid=214590&pageid=27160)

**Các chế độ đề xuất** gồm chỉ thông tin, khung xương trên nền trống, video đã làm mờ, video gốc theo quyền riêng và tạm dừng thu hình khi thay đồ hoặc chăm sóc riêng tư. Đề xuất mặc định người nhà chỉ xem thông tin, mời chọn khung xương nếu được cấp thêm. F28 hiện giả định mặc định mờ mặt cho giao diện hiện hành. Nhóm cần duyệt mặc định riêng cho từng vai trò. Mờ mặt vẫn có thể lộ cơ thể, người đi ngang và bối cảnh phòng.

**Điều kiện cho demo quyền riêng tư.** Xử lý ảnh trên máy tại cơ sở, không lưu video vận hành. Khi người xem chọn khung xương, máy chủ chỉ gửi dữ liệu cần để vẽ khung xương của người được theo dõi. Khi không chắc đúng người, báo thiếu quan sát. Giới hạn quyền ở cả API và luồng trực tiếp, ghi nhận cấp/xem/thu hồi quyền. Khi kết thúc phiên hoặc đổi bệnh nhân tại cùng giường, người nhà mất quyền của phiên cũ. Kiểm tra bằng điện thoại đang xem, kể cả khi kết nối lại. Bản đầu thử trong cùng mạng. Truy cập từ nhà là bước mở rộng cần xác thực, bảo vệ đường truyền và kiểm tra với cơ sở trước khi sử dụng dữ liệu thật.

## 4. AI làm phần nào? Nhóm làm phần nào?

Dùng **MediaPipe Pose Landmarker Lite** làm ứng viên đầu tiên. Model trả 33 điểm cơ thể. Nhóm kết hợp vị trí vai, hông, chân với vùng giường, diễn biến theo thời gian và độ rõ của ảnh. Nếu Lite bỏ nhiều sự kiện dù người còn nhìn rõ, chạy thử Pose Full trên chính clip và laptop đó. **MoveNet Lightning/Thunder** là phương án dự phòng với 17 điểm. **Face Landmarker** trả điểm mặt và 52 hệ số biểu cảm. Chỉ thử sau khi phần cơ thể chạy ổn ở đúng góc đặt máy. Hiệu chỉnh vùng và thời gian duy trì bằng dữ liệu mô phỏng, không train hoặc fine-tune. [MediaPipe Pose](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) · [MediaPipe Face](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker) · [MoveNet](https://www.tensorflow.org/hub/tutorials/movenet)

Luồng cần chạy xuyên suốt là **camera → điểm cơ thể → trạng thái theo thời gian → sự kiện của đúng phiên → lưu DB → phát lên màn hình có quyền → tiếp nhận → kiểm tra → bàn giao**. Lưu xong mới phát. Cùng một sự kiện không sinh nhiều việc vì tín hiệu dao động hoặc kết nối lại. Quyền người nhà và cách xử lý khi mất hình là phần mềm nhóm phải xây. Chọn nền tảng sau khi thử góc quay và tốc độ thật. Có thể tận dụng web hiện có để dành thời gian cho phần còn thiếu.

## 5. Vì sao chọn bài toán này ở Việt Nam?

Một nghiên cứu ở khoa Ngoại Tiêu hóa, Bệnh viện Thống Nhất, khảo sát vận động sớm ở **78 người sau mổ u đường tiêu hóa**. Đây là bối cảnh sát với đối tượng dự kiến. Trong một nghiên cứu khác tại **9 bệnh viện công TP.HCM**, hành động xuống giường xuất hiện trong **21 trên 101 ca té ngã nội trú** được ghi nhận. Con số này mô tả các ca đã ngã. Chưa có số liệu riêng cho biết bao nhiêu bệnh nhân hậu phẫu cần cảnh báo của PostCare. [Nghiên cứu vận động sau mổ](https://www.vjol.info.vn/tcsuckhoevalaohoa/vi/article/view/137980/) · [Nghiên cứu té ngã, bảng 3](https://pmc.ncbi.nlm.nih.gov/articles/PMC11416768/)

| Phương án để giám khảo so sánh | Điều phương án đó làm tốt | Câu hỏi PostCare phải trả lời |
|---|---|---|
| Người trực tại giường | Nhìn được bối cảnh và hỗ trợ tại chỗ | Khi người trực bận việc khác, PostCare có giúp nhận đúng giường cần kiểm tra? Yêu cầu trực trực tiếp của cơ sở vẫn áp dụng. |
| Camera thông thường | Cho điều dưỡng hoặc người nhà xem từ xa | Người dùng có tìm đúng thay đổi và kết quả xử lý nhanh hơn trong cùng một nhiệm vụ? |
| Giường báo động rời giường | Có chế độ cảnh báo khi người bệnh dịch chuyển về phía mép hoặc rời giường | Chuỗi vận động và lịch sử xử lý bổ sung thông tin gì? Mang chi phí thiết bị thực trả ra so sánh khi có báo giá tương đương. [Stryker](https://techweb.stryker.com/Critical_Care/FL27/6_0/Operation/2141-800-301A.pdf) |
| Hệ thống quan sát tập trung | Đã có quan sát từ xa có AI và tạm dừng vì riêng tư | Nhóm có chạy được bằng thiết bị đang có, giao diện tiếng Việt và quyền gia đình theo phiên? Chưa có phép so hiệu năng trực tiếp với sản phẩm hãng. [AvaSure](https://avasure.com/patient-safety-observation/) |

Theo ghi chú meeting, chất lượng sản phẩm chiếm 30% và hiệu quả chiếm 20%. Đối chiếu thể lệ cuối trước khi nộp. Lập luận của nhóm nên đi từ một tình huống thật sự cần hỗ trợ, qua demo mà giám khảo tự thử được, tới số liệu bỏ sót, báo nhầm và độ trễ. Việc cảnh báo sớm có cải thiện chăm sóc hay không còn phụ thuộc người nhận có thể đến giường.

## 6. Kế hoạch dựng demo

**Bán kết — một giường, một câu chuyện hoàn chỉnh.** Quay trước ở nhà hoặc phòng học với người tình nguyện trên giường thật hay giường xếp chịu lực. Nếu sân khấu có chỗ, mang giường xếp, webcam hoặc điện thoại trên giá khóa chắc và laptop. Tránh ghép bàn rời cho người nằm. Đặt camera chéo từ bên giường để thấy thân người, mép giường và khoảng sàn bước xuống. Dọn dây khỏi lối đi. Thử ở góc quay này trước khi làm thêm màn hình. Clip dự phòng nên giữ đầu vào nguyên vẹn để chạy model ngay trên laptop và ghi rõ “Phát lại clip mô phỏng”. Nếu dùng bộ giả lập sự kiện, công bố đúng nguồn.

**Kịch bản 90 giây.** Một người ngồi dậy ở giữa giường, lịch sử có mốc mới. Họ dịch ra mép, dừng lại rồi bước xuống. Màn hình trực có cảnh báo đúng giường, đúng mức. Người thứ hai nhận việc và ghi kết quả. Đưa màn hình cho người thứ ba tìm người đã nhận. Mời giám khảo che ống kính để thấy hệ thống báo thiếu quan sát. Với tình huống nghi ngã, dùng đoạn hạ thân có kiểm soát xuống nệm đã quay an toàn. Không yêu cầu người tham gia ngã từ bàn, giường hoặc diễn ngã trực tiếp trên sân khấu.

**Chung kết — cùng một diễn biến, hai người xem khác quyền.** Mục tiêu đề xuất là điều dưỡng thấy A01 và A02 cùng lúc, người nhà chỉ thấy A01 trên điện thoại. Cho A02 xuất hiện sự kiện, kiểm tra điện thoại A01 không nhận được cả hình lẫn sự kiện A02. Đổi A01 sang khung xương, tạm dừng rồi thu hồi quyền ngay khi điện thoại đang mở. Điều dưỡng bàn giao việc còn chờ. Ghi rõ giường nào live, giường nào dùng clip. Chỉ tuyên bố chạy hai camera đồng thời sau khi thử hai camera thật trên cùng phần cứng.

## 7. Bằng chứng phải mang theo

| Điều cần chứng minh | Cách thử và kết quả cần ghi |
|---|---|
| AI nhận đúng sự kiện | Người lớn tự nguyện mô phỏng đúng lẫn dễ nhầm. Hai người gán nhãn thời điểm. Tách người/phiên hiệu chỉnh và đánh giá, khóa ngưỡng trước khi mở tập đánh giá. Báo theo loại sự kiện số đúng, sai, bỏ sót, precision, recall và F1 kèm mẫu số. Đánh giá chuyển động nghi ngã riêng, có ca ngồi xuống nhanh, cúi người, che khuất. |
| Quy tắc theo thời gian có ích | Cùng model, clip, vùng giường và cách chống lặp. So quy tắc đơn giản qua biên với chuỗi có mép giường và kiểm tra chất lượng. Báo cảnh báo sai/giờ, trung vị và p90 độ trễ, phần thời gian đủ quan sát. Tính cả sự kiện bị bỏ lỡ lúc camera bị che. |
| Điều dưỡng và người nhà dùng được | So camera thường với PostCare trên hai tình huống tương đương, đổi thứ tự. Đo số người tìm đúng giường, đúng việc còn chờ và thời gian tìm. Với người nhà, thử đọc thông tin được phép, truy cập giường khác, rút quyền giữa phiên. Ghi rõ người thử là ai. |
| Demo chạy trên thiết bị dự thi | Ghi CPU, RAM, FPS từng luồng, độ trễ từ hành động đến màn hình, chi phí lắp, kết quả lúc ngắt Internet. Kiểm tra bản tin không chứa ảnh gốc ở chế độ khung xương, ổ đĩa không lưu video vận hành và quyền cũ không mở được phiên mới. |

**Mốc thử nội bộ đề xuất** cho lần đầu là sáu người tình nguyện, ba người để hiệu chỉnh, ba người giữ riêng. Mỗi người ở tập giữ riêng thực hiện bốn lần rời giường. Nhắm tới bắt đúng ít nhất 11/12 lần, tối đa hai cảnh báo sai trong hai giờ đánh giá và độ trễ trung vị dưới ba giây. Ghi tổng giờ thực thu cả khi hụt mục tiêu. Mẫu nhỏ này chỉ đủ quyết định có nên mang phiên bản lên sân khấu. Hiện nhóm chưa có số đo model hoặc hiệu quả lâm sàng. [Quy trình đánh giá của dự án](../04-guides/evaluation.md)

## 8. Chia việc và quyết định ở cuộc họp nhóm

Đề xuất dành **14 ngày cho lát cắt một giường** trong lộ trình 10 tuần của hồ sơ. Một bạn phụ trách camera và model, một bạn phụ trách sự kiện, phân quyền và giao diện, một bạn phụ trách dữ liệu có đồng ý, đo lường và bài trình bày. Ngày 1–2 thử camera trên đúng giường. Ngày 3–5 nối một sự kiện thật tới màn hình. Ngày 6–8 hiệu chỉnh và khóa cấu hình. Ngày 9–12 đánh giá trên người/phiên giữ riêng. Hai ngày cuối diễn tập và chuẩn bị clip dự phòng. Ghi kết quả thất bại và nguyên nhân ngay khi gặp.

Trước khi bắt đầu, nhóm cần chọn thiết bị và địa điểm, phân công ba đầu việc, chốt chế độ xem mặc định của người nhà và xác nhận thời gian còn lại trước từng vòng. Nhờ giảng viên kết nối điều dưỡng để hỏi ba việc cụ thể: giường nào sẽ được chọn theo dõi, thay đổi nào đáng gọi và thông tin nào được chia sẻ với gia đình. Với người nhà, hỏi họ muốn biết điều gì khi ra ngoài và lúc nào họ muốn tắt camera. Skill nghiên cứu đề xuất là pubmed-database để tra cứu bài và đối chiếu PMID khi chuẩn bị slide. [Nguồn skill](https://skills.sh/google-deepmind/science-skills/pubmed-database)

**Ranh giới với tài liệu hiện hành.** Hồ sơ sơ loại §4–8 và PRD giữ mốc tối thiểu một giường. QA#13 xếp nhiều camera đồng thời vào F31. Quyền người nhà theo phiên và luồng chấp thuận là mở rộng theo trao đổi cho vòng sau. Trước khi viết các phần này, chuyển quyết định nhóm duyệt vào PRD, QA, F28/F31 và spec quyền người nhà. Các giới hạn nguồn dữ liệu, thuật ngữ UI và thứ tự phụ thuộc tiếp tục áp dụng. [Hồ sơ sơ loại](../00-source/ho-so-so-loai-2026.md) · [PRD](PRD.md) · [QA](qa-decisions.md) · [Hiện trạng prototype](../../SUMMARY.md) · [Phương án thử chi tiết](de-xuat-demo-end-to-end.md)
