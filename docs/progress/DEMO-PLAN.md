# Kế hoạch demo: bán kết và chung kết

Kế hoạch kỹ thuật và trình diễn cho hai vòng AI4Life. Hợp nhất từ hai bản đề xuất của nhóm. Thông điệp, so sánh phương án và bộ chỉ số công khai nằm ở [pitch-and-evidence.md](../01-product/pitch-and-evidence.md).

- Đây là **đề xuất để nhóm duyệt**, không phải spec. Yêu cầu triển khai nằm trong `docs/03-features/`.
- Không ghi trạng thái feature ở đây. Trạng thái xem [ROADMAP](ROADMAP.md) và [TASKS](TASKS.md).
- Chỉ công bố kết quả sau khi đo.

## Mục tiêu từng vòng

| Vòng | Mục tiêu | Ghi nhãn trên màn hình |
|---|---|---|
| Bán kết | Một giường, một câu chuyện hoàn chỉnh. Phát lại clip từ bộ dữ liệu có giấy phép qua **model thật trên laptop** (không dùng sự kiện giả lập), chạy trọn luồng tới cảnh báo, tiếp nhận, timeline | "Phát lại clip" |
| Chung kết | Cùng một pipeline xử lý đồng thời **A01 bằng camera trực tiếp** và **A02 bằng clip**. Điều dưỡng thấy cả hai giường. Điện thoại người nhà chỉ thấy A01, đúng mức quyền được cấp | A01: trực tiếp; A02: "Phát lại clip" |

Quy tắc chung:

- Clip phải giữ đầu vào nguyên vẹn để model chạy ngay trên laptop, không phát kết quả quay sẵn.
- Nếu buộc phải dùng bộ giả lập sự kiện, công bố đúng nguồn trên màn hình và khi nói.
- Chỉ tuyên bố "hai camera đồng thời" sau khi đã thử hai camera thật trên cùng phần cứng. Chung kết như kế hoạch là một camera + một clip.

## Nguồn dữ liệu

1. Trước hết: bộ dữ liệu video bên ngoài có giấy phép cho phép đánh giá và trình chiếu. Ghi tên bộ, giấy phép, phiên bản, danh sách clip.
2. Sau đó: clip của người trưởng thành tự nguyện, có đồng ý theo [evaluation.md](../04-guides/evaluation.md) §2, ghi nhận riêng việc trình chiếu trước khán giả.
3. Không dùng video bệnh nhân thật, không train model. Dữ liệu ngoài dùng theo QA#33 và [datasets.md](../04-guides/datasets.md); kết quả trên dữ liệu ngoài phải ghi nguồn nhãn.

## Kịch bản demo

Độ dài linh hoạt theo thời lượng ban tổ chức cho phép.

### Bản ngắn (khoảng 90 giây)

1. Người trong clip (hoặc trước camera) ngồi dậy ở giữa giường → lịch sử có mốc mới.
2. Họ dịch ra mép, dừng lại → giường hiện ở mức cần chú ý.
3. Họ bước xuống → màn hình trực có cảnh báo rời giường đúng giường, đúng mức ưu tiên.
4. Người thứ hai bấm tiếp nhận và ghi kết quả kiểm tra.
5. Đưa màn hình cho người thứ ba (có thể là giám khảo) tìm xem ai đã nhận cảnh báo.

### Bản đầy đủ

Bản ngắn, cộng thêm:

| Bước | Điều khán giả thấy |
|---|---|
| Mời giám khảo che ống kính (A01 trực tiếp) | Giường chuyển sang "Không đủ dữ liệu quan sát", **không** báo rời giường |
| Clip hạ thân có kiểm soát xuống nệm, đã quay an toàn từ trước | "Phát hiện chuyển động bất thường - đề nghị kiểm tra"; điều dưỡng xác minh |
| A02 có sự kiện | Điện thoại người nhà A01 **không** nhận hình lẫn sự kiện của A02 |
| Đổi A01 sang chế độ khung xương khi điện thoại người nhà đang mở | Điện thoại chỉ còn khung xương, không còn ảnh gốc |
| Tạm dừng thu hình vì riêng tư | Cả hai phía hiện trạng thái tạm dừng |
| Thu hồi quyền người nhà khi điện thoại đang mở | Điện thoại mất quyền xem ngay, kể cả khi kết nối lại |
| Bàn giao ca | Người vào sau thấy ai đã kiểm tra, kết quả, việc còn chờ |

Ghi rõ trên màn hình và khi nói giường nào trực tiếp, giường nào dùng clip.

## Quy tắc an toàn khi quay và trình diễn

- **Không** yêu cầu người tham gia ngã từ bàn, giường hoặc diễn ngã trực tiếp trên sân khấu.
- Tình huống nghi ngã chỉ dùng đoạn **hạ thân có kiểm soát xuống nệm**, quay trước, có người đứng cạnh.
- Dùng giường thật hoặc giường xếp chịu lực. Tránh ghép bàn rời cho người nằm.
- Đặt nệm ở vùng có thể hạ người xuống.
- Dọn dây khỏi lối đi và khoảng sàn bước xuống; giá camera khóa chắc.
- Chỉ người trưởng thành tự nguyện, đã ghi nhận đồng ý quay và trình chiếu.

## Đặt camera

- Đặt chéo từ bên giường, thấy được thân người, mép giường và khoảng sàn bước xuống.
- Webcam hoặc điện thoại trên giá khóa chắc; hiệu chỉnh vùng giường sau khi cố định giá.
- Thử ở góc quay này **trước** khi làm thêm màn hình.
- Đổi góc hoặc khoảng cách thì kiểm tra lại vùng giường.
- Chi tiết: [camera-setup.md](../04-guides/camera-setup.md).

## Chạy hai worker cho chung kết (F31)

A01 = camera trực tiếp (nguồn trong cấu hình camera, ví dụ webcam `0`), A02 = clip phát lại theo nhịp thời gian thực. Mỗi giường một tiến trình worker; một worker dừng không kéo theo worker kia. Chạy từ thư mục gốc repo, mỗi lệnh một terminal:

```bash
make dev-api                       # hoặc make dev (API + web)
make workers CAMERAS="1 2" VIDEOS="2=D:/PostCareAi/data/demo/a02.mp4"
# tương đương: cd server && uv run postcare workers --camera-id 1 --camera-id 2 --video 2=<file>
# xem trước lệnh, không chạy: thêm --dry-run
```

- Id camera xem ở "Quản lý camera" hoặc `GET /api/v1/cameras` (sau `make seed`: A01 = 1, A02 = 2, A03 = 3). Bỏ `CAMERAS` thì chạy mọi camera đang dùng có gắn giường.
- Đường dẫn clip nên là đường dẫn tuyệt đối (lệnh chạy trong `server/`). Clip hết thì A02 chuyển "Mất kết nối"; chạy lại lệnh để phát lại.
- Ctrl+C dừng cả hai worker. Nếu muốn tách riêng (ví dụ khởi động lại một giường): `make worker CAMERA=1` và `make worker CAMERA=2 VIDEO=<file>` ở hai terminal.
- Trước giờ demo: kiểm tra "Tổng quan" thấy A01 và A02 cùng "Đang theo dõi", rút camera A01 thử → chỉ A01 "Mất kết nối", A02 vẫn nhận sự kiện.
- Tài nguyên đo trên i5-10300H: xem `tech-stack.md` mục "Kết quả đo hiệu năng" (F31). Chỉ nói "một camera trực tiếp + một clip"; chưa thử hai camera thật.

## Checklist thiết bị

- [ ] Laptop demo (đúng máy đã đo FPS/CPU/RAM), sạc
- [ ] Webcam USB hoặc điện thoại + ứng dụng camera, cáp, sạc
- [ ] Giá đỡ camera khóa chắc
- [ ] Giường xếp chịu lực và nệm (nếu sân khấu có chỗ)
- [ ] Router hoặc mạng nội bộ riêng; thử chạy khi ngắt Internet
- [ ] Màn hình hoặc máy thứ hai cho màn hình trực
- [ ] Điện thoại cho vai người nhà, tài khoản đã cấp quyền A01
- [ ] Clip dự phòng (đầu vào nguyên vẹn) trên ổ máy demo
- [ ] Băng dính, dây nối điện, ổ cắm

## Bằng chứng phải mang theo

| Điều cần chứng minh | Cách thử và kết quả cần ghi |
|---|---|
| AI nhận đúng sự kiện | Clip có giấy phép và người tự nguyện mô phỏng cả ca đúng lẫn ca dễ nhầm. Hai người gán nhãn thời điểm. Tách người/phiên hiệu chỉnh và đánh giá, khóa ngưỡng trước khi mở tập đánh giá. Báo theo loại sự kiện: số đúng, sai, bỏ sót, precision, recall, F1 kèm mẫu số. Đánh giá chuyển động bất thường riêng, có ca ngồi xuống nhanh, cúi người, che khuất |
| Quy tắc theo thời gian có ích | Cùng model, clip, vùng giường, chống lặp. So quy tắc đơn giản "qua biên" với chuỗi có mép giường và kiểm tra chất lượng. Báo cảnh báo sai/giờ, trung vị và p90 độ trễ, phần thời gian đủ quan sát. Tính cả sự kiện bị bỏ lỡ lúc camera bị che |
| Điều dưỡng và người nhà dùng được | So camera thường với PostCare trên hai tình huống tương đương, đổi thứ tự. Đo số người tìm đúng giường, đúng việc còn chờ, thời gian tìm. Với người nhà: đọc thông tin được phép, thử truy cập giường khác, rút quyền giữa phiên. Ghi rõ người thử là ai |
| Demo chạy trên thiết bị dự thi | Ghi CPU, RAM, FPS từng luồng, độ trễ hành động → màn hình, chi phí lắp, kết quả khi ngắt Internet. Kiểm tra bản tin không chứa ảnh gốc ở chế độ khung xương, ổ đĩa không lưu video vận hành, quyền cũ không mở được phiên mới |

Ghi kết quả thất bại và nguyên nhân ngay khi gặp. Quy trình đo: [evaluation.md](../04-guides/evaluation.md).

## Ngưỡng go/no-go nội bộ

> **Chỉ dùng nội bộ** để quyết định có mang phiên bản lên sân khấu hay không. **Không** phải tuyên bố công khai, không đưa lên slide như kết quả, không thay ngưỡng chấp nhận chốt trong spec F29.

| Mục | Ngưỡng |
|---|---|
| Mẫu | 6 người tình nguyện: 3 để hiệu chỉnh, 3 giữ riêng (hold-out) |
| Rời giường | Mỗi người hold-out làm 4 lần → bắt đúng **≥ 11/12** |
| Cảnh báo sai | **≤ 2** trong 2 giờ đánh giá |
| Độ trễ | Trung vị **< 3 giây** từ hành động tới màn hình |

- Ghi tổng giờ thực thu, kể cả khi hụt mục tiêu.
- Mẫu nhỏ này chỉ đủ cho quyết định nội bộ; nhóm hiện chưa có số đo model hay hiệu quả lâm sàng.
- **Hai loại độ trễ khác nhau:** "hành động → màn hình" ở đây **bao gồm** `min_duration` mà engine phải chờ để xác nhận điều kiện. Mục tiêu "< 1 giây" của A07 (PRD NFR04) chỉ là **delivery latency**, từ lúc sự kiện được lưu tới lúc dashboard nhận. Không đem so hai con số này với nhau.

## Phụ thuộc feature

Chỉ bắt đầu feature khi phụ thuộc đã `Done` trong [ROADMAP](ROADMAP.md). Bảng dưới cho biết mỗi vòng cần gì; không phải lịch.

| Vòng | Feature cần |
|---|---|
| Bán kết | Nền và luồng một giường: F00–F24 (camera/clip → pose → engine → sự kiện → cảnh báo → tiếp nhận → timeline → bàn giao), F28 (chế độ hiển thị), F29 (số đo), F30 (sẵn sàng demo). F25–F27 (khuôn mặt, nghỉ/hoạt động) chỉ đưa lên khi có kết quả đo |
| Chung kết | Tất cả của bán kết, cộng: F35 (quản lý người dùng, tạo tài khoản người nhà); F36 (quyền người nhà theo phiên: cấp, mức hình, tạm dừng, thu hồi); F37 (khu vực/ca trực: điều dưỡng chỉ thấy giường được phân); F31 R1–R3 (hai worker cùng máy, worker lỗi không ảnh hưởng worker khác, báo FPS/CPU/RAM theo số luồng) |

Ghi chú:

- F35, F36 và F37 là mở rộng theo trao đổi của nhóm, đã duyệt ngày 17/11/2026 (QA#31, QA#36) và đã có trong ROADMAP.
- QA#13 xếp nhiều camera đồng thời vào [F31](../03-features/F31-multi-camera.md); chung kết chỉ cần R1–R3.
- Đường cắt phạm vi: thiếu thời gian thì dừng sau M2 (ROADMAP).

## Phân vai trong nhóm

| Vai | Phụ trách |
|---|---|
| Camera và model | Thử camera trên đúng giường, góc đặt máy, pose adapter, benchmark biến thể model, FPS/CPU/RAM |
| Sự kiện, phân quyền, giao diện | Engine và rule theo thời gian, cảnh báo, quyền người nhà theo phiên, màn hình trực và điện thoại |
| Dữ liệu, đo lường, trình bày | Bộ dữ liệu có giấy phép, đồng ý của người tham gia, gán nhãn, eval, bằng chứng mang theo, slide và kịch bản nói |

Thứ tự công việc gợi ý: thử camera trên đúng giường → nối một sự kiện thật tới màn hình → hiệu chỉnh và khóa cấu hình → đánh giá trên người/phiên giữ riêng → diễn tập và chuẩn bị clip dự phòng.

**Nhóm cần chốt trước khi bắt đầu:** thiết bị và địa điểm quay; phân công ba vai; thời gian còn lại trước từng vòng. Chế độ xem mặc định của người nhà đang là "Chỉ thông tin" *(giả định, F36)*.

## Câu hỏi cho điều dưỡng và người nhà

Nhờ giảng viên kết nối điều dưỡng (nhóm chưa có đối tác bệnh viện).

**Điều dưỡng:**

1. Giường nào sẽ được chọn để theo dõi?
2. Thay đổi nào đáng để gọi người tới?
3. Thông tin nào được phép chia sẻ với gia đình?

**Người nhà:**

1. Khi ra ngoài, anh/chị muốn biết điều gì về người thân?
2. Lúc nào anh/chị muốn tắt camera?
