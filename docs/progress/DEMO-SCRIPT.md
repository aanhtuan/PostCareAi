# Kịch bản demo trước hội đồng

Kịch bản chạy thật để thuyết phục hội đồng rằng đề tài làm được, theo [DEMO-PLAN.md](DEMO-PLAN.md).

- **Mọi cảnh báo đều do model chạy ngay trên laptop sinh ra.** Không dùng `postcare simulate`, không phát kết quả quay sẵn.
- Clip dùng làm đầu vào được chọn bằng cách replay qua đúng pipeline của worker. Bảng ở mục 2 ghi sự kiện mà mỗi clip đã sinh ra.
- Thông điệp cần nói, so sánh phương án và các câu không được nói nằm ở [pitch-and-evidence.md](../01-product/pitch-and-evidence.md).

## 1. Thông điệp chính (nói trong 20 giây đầu)

> "Camera thường cần người nhìn liên tục. PostCare để AI theo dõi tư thế theo thời gian, chỉ báo khi chuỗi hành động đủ rõ, và cho điều dưỡng một quy trình tiếp nhận có dấu vết. Hôm nay mọi cảnh báo trên màn hình đều do model chạy ngay trên laptop này, không phải dữ liệu mô phỏng."

Ba điều hội đồng cần thấy:

1. **Thật:** video vào và cảnh báo ra trong vài giây, trên máy cá nhân không cần GPU.
2. **Không báo bừa:** che camera thì hệ thống nói "Không đủ dữ liệu quan sát", không báo rời giường.
3. **Dùng được trong khoa:** cảnh báo có người tiếp nhận, kết quả, timeline và bàn giao ca.

## 2. Nguồn video đã kiểm chứng

Sinh bảng bằng `postcare replay` trên đúng model `full`, ngưỡng `config/engine.default.yaml` và cấu hình camera trong `config/cameras/`, ngày 2026-11-21. Chạy lại cách kiểm ở mục 7 trước buổi demo.

Tổng hợp: 22/41 clip ngã GMDCSA24 (Subject 1 + 2) sinh `ABNORMAL_MOVEMENT` mức cao. 2/9 clip stock giường sinh `BED_EDGE`. 5/5 clip sinh hoạt đã thử không sinh cảnh báo. Chỉ dùng các clip trong bảng dưới.

| Tên trong `data/demo/` | Nguồn gốc (giấy phép) | Nội dung | Sự kiện đã sinh (giây trong clip) | Camera / hồ sơ | Vai trò |
|---|---|---|---|---|---|
| `fall-a.mp4` | GMDCSA24 Subject 1 Fall/12 (MIT) | Ngã trong phòng, 6,8 s | `ABNORMAL_MOVEMENT` HIGH @2,4 s. Đã thử qua worker thật | A02, Chuyển động bất thường | **Chính** |
| `fall-b.mp4` | GMDCSA24 Subject 1 Fall/05 (MIT) | Ngã, 5,9 s | `ABNORMAL_MOVEMENT` HIGH @2,0 s | A02 | Dự phòng |
| `fall-c.mp4` | GMDCSA24 Subject 2 Fall/16 (MIT) | Ngã, người khác, phòng khác | `ABNORMAL_MOVEMENT` HIGH @2,0 s | A02 | Dự phòng, cho thấy chạy được trên người khác |
| `adl-pickup.mp4` | GMDCSA24 Subject 1 ADL/15 (MIT) | Đi tới, cúi nhặt điện thoại dưới sàn, ngồi ghế | Không có cảnh báo | A02 | **Ca âm tính** |
| `bed-edge.mp4` | Pexels 3753707 (Pexels License, stock, diễn viên) | Người ngồi dậy ra mép giường, 21,4 s | `BED_EDGE` MEDIUM @4,5 s | A03, Theo dõi giường + phiên | **Chính** |
| `bed-edge-b.mp4` | Pexels 8090735 (Pexels License, stock, diễn viên) | Người phụ nữ ra khỏi giường, 7,7 s | `BED_EDGE` MEDIUM @1,8 s | A03 | Dự phòng |

ROI phải vẽ cho A03 (toạ độ 0–1 theo chiều rộng, chiều cao khung, lấy từ `config/cameras/`):

- `bed-edge.mp4`: (0,30; 0,74) → (1,0; 0,74) → (1,0; 1,0) → (0,30; 1,0).
- `bed-edge-b.mp4`: (0,31; 0,32) → (1,0; 0,32) → (1,0; 0,62) → (0,31; 0,62).

Giới hạn cần biết:

- **Chưa có clip nào sinh `BED_EXIT` (rời giường).** Clip stock bị cắt chân hoặc người ra khỏi khung quá nhanh ([calibration-2026-11-18.md](../04-guides/calibration-2026-11-18.md) §5). Không hứa cảnh báo rời giường trong buổi demo, trừ khi nhóm đã tự quay được clip đạt chuẩn.
- Clip ngã chỉ dài 5–7 giây. Khi phát lặp (`LOOP=1`), cảnh ngã lặp lại liên tục, nhưng debounce `same_code_same_session_s` 60 giây giới hạn còn khoảng **1 cảnh báo mỗi phút** cho mỗi camera.
- Muốn trình diễn lại ngay thì khởi động lại worker. Engine mới không còn trạng thái debounce cũ.
- Clip và bộ dữ liệu ngoài phải ghi nguồn trên slide: GMDCSA24 (MIT), Pexels (stock footage – diễn viên).

**Chuẩn bị clip:** các clip trên đã được chép sang `data/demo/` trên máy này, tên ngắn và không có dấu cách (vì `make` tách đường dẫn theo dấu cách). Máy khác thì tải bộ dữ liệu theo [datasets.md](../04-guides/datasets.md) rồi chép lại theo cột "Nguồn gốc". Thư mục `data/` không được commit.

## 3. Chuẩn bị trước giờ demo

| Việc | Lệnh hoặc thao tác | Kiểm tra |
|---|---|---|
| DB và dữ liệu mẫu | `make db-upgrade`, `make db-seed` | Đăng nhập `nurse` / `postcare` được |
| API và web | `make dev` | Mở `http://localhost:5173` |
| Camera clip ngã | Quản lý camera → camera A02: hồ sơ **Chuyển động bất thường** (nguồn để gì cũng được, `VIDEO=` ghi đè) | Không cần ROI |
| Camera clip giường | Camera A03: hồ sơ **Theo dõi giường**, vẽ ROI theo toạ độ ở mục 2 (trang Cấu hình camera cần có khung hình, nên chạy worker A03 trước rồi mới vẽ) | Theo dõi trực tiếp thấy ROI trùng mặt nệm |
| Camera webcam | Camera A01: nguồn **Webcam 0**, hồ sơ **Tín hiệu khuôn mặt** | Theo dõi trực tiếp thấy hình |
| **Phiên theo dõi** | Mở phiên cho **cả ba** giường A01, A02, A03 (mỗi giường một bệnh nhân mẫu) | Camera đã gắn giường thì mọi sự kiện, kể cả chuyển động bất thường và khuôn mặt, chỉ được ghi khi giường có phiên đang mở. Không có phiên thì API trả 409 và không có cảnh báo |
| Chế độ hiển thị | Để **Làm mờ khuôn mặt** (có skeleton đè lên) | Mặt bị làm mờ, thấy skeleton |
| Hai màn hình | Máy 1: Tổng quan + Cảnh báo (vai điều dưỡng). Máy 2 hoặc tab 2: Theo dõi trực tiếp | |

Chạy worker, mỗi lệnh một terminal (từ thư mục gốc repo):

```bash
make worker CAMERA=1
```

```bash
make worker CAMERA=2 VIDEO=D:/PostCareAi/data/demo/fall-a.mp4 LOOP=1
```

```bash
make worker CAMERA=3 VIDEO=D:/PostCareAi/data/demo/bed-edge.mp4 LOOP=1
```

- Id camera theo `make db-seed`: A01 = 1, A02 = 2, A03 = 3. Kiểm tra lại ở "Quản lý camera" nếu đã đổi.
- `LOOP=1`: hết clip thì phát lại, camera không chuyển "Mất kết nối".
- Khởi động worker **trước khi hội đồng vào** khoảng 1 phút để model nạp xong.
- Sau mỗi lượt tập, xử lý hết cảnh báo cũ để màn hình Cảnh báo sạch.

## 4. Kịch bản (khoảng 6–8 phút, có thể rút còn 3 phút)

### Cảnh 1. Hệ thống đang chạy thật (30 giây)

- Mở **Tổng quan**: ba giường, mỗi giường có nguồn (Webcam / Phát lại clip) và trạng thái.
- Nói rõ: "A01 là webcam trực tiếp. A02 và A03 phát lại clip từ bộ dữ liệu công khai có giấy phép. Clip chỉ là đầu vào, model xử lý ngay lúc này."
- Mở **Theo dõi trực tiếp** A02: khung xương bám theo người trong clip. Đây là bằng chứng model đang chạy, không phải video có sẵn kết quả.

### Cảnh 2. Chuyển động bất thường, cảnh báo mức cao (1–2 phút)

- Ở Theo dõi trực tiếp A02, chờ đoạn người trong clip hạ thân nhanh xuống sàn.
- Khoảng 2–3 giây sau, màn hình Cảnh báo nhận "Phát hiện chuyển động bất thường - đề nghị kiểm tra", mức **Ưu tiên cao**, kèm âm báo.
- Nói: "Hệ thống không kết luận té ngã. Nó báo chuyển động bất thường để điều dưỡng kiểm tra. Rule cần hạ thân nhanh, hông ở thấp và giữ yên ít nhất 1 giây, nên cúi nhặt đồ hay ngồi xuống không báo."
- Thao tác điều dưỡng: **Tiếp nhận** → ghi kết quả **Xác nhận đúng** + ghi chú → **Đã xử lý**.
- Mở **Lịch sử theo dõi**: thấy sự kiện, ai tiếp nhận, lúc nào, kết quả.

### Cảnh 2b. Ca âm tính: cúi nhặt đồ không báo (1 phút)

- Dừng worker A02 (Ctrl+C), chạy lại với clip sinh hoạt:

```bash
make worker CAMERA=2 VIDEO=D:/PostCareAi/data/demo/adl-pickup.mp4 LOOP=1
```

- Người trong clip cúi xuống sàn nhặt điện thoại rồi ngồi ghế. Skeleton vẫn bám theo, **không** có cảnh báo.
- Nói: "Hệ thống phân biệt được hạ thân có chủ đích với chuyển động bất thường. Đây là lý do dùng chuỗi theo thời gian thay vì xét từng frame."
- Xong thì chạy lại `fall-a.mp4` cho các cảnh sau.

### Cảnh 3. Theo dõi giường: mép giường (1 phút)

- Theo dõi trực tiếp A03: vùng giường (ROI) vẽ trên hình, người trong clip ngồi dậy và dịch ra mép.
- Màn hình Cảnh báo nhận "Bệnh nhân đang ở mép giường", mức **Cần chú ý**.
- Nói: "Sự kiện có nghĩa theo thời gian: phải giữ đủ lâu mới báo, một frame nhầm không tạo cảnh báo."

### Cảnh 4. Webcam trực tiếp: tín hiệu khuôn mặt (1–2 phút)

Người thao tác ngồi trước webcam A01.

1. Mở Theo dõi trực tiếp A01, phần **Tín hiệu khuôn mặt**. Trạng thái phải là "Quan sát rõ khuôn mặt".
2. Lần lượt làm, mỗi động tác giữ 2–3 giây, chỉ vào panel cho hội đồng thấy tín hiệu bật rồi tắt:
   - nhắm mắt → "Mắt đóng";
   - nheo mắt → "Nheo mắt";
   - cau mày → "Hạ lông mày";
   - mím hoặc kéo miệng → "Thay đổi vùng miệng".
3. Mời một giám khảo ngồi vào thử. Đây là phần thuyết phục nhất vì không thể dàn dựng trước.
4. Nói: "Hệ thống chỉ mô tả điều nhìn thấy trên khuôn mặt, không chẩn đoán đau và không nhận diện danh tính. Mặt luôn được làm mờ khi hiển thị."

**Cảnh báo khuôn mặt (nếu đã tập đạt ở mục 5):** ngồi lùi để webcam thấy cả vai và hông, rồi giữ cùng lúc **cau mày + nheo mắt** (hai nhóm tín hiệu) khoảng 5 giây. Màn hình Cảnh báo nhận "Phát hiện biểu hiện khuôn mặt cần kiểm tra", mức Cần chú ý.

### Cảnh 5. Không báo bừa (30 giây)

- Lấy tay che webcam A01, hoặc mời giám khảo che.
- Sau khoảng 2 giây, trạng thái chuyển "Không đủ dữ liệu quan sát" và panel khuôn mặt chuyển "Không thấy khuôn mặt". **Không** có cảnh báo nào được tạo.
- Nói: "Mất hình thì hệ thống nói không đủ dữ liệu, không bao giờ đoán là bệnh nhân rời giường."

### Cảnh 6. Riêng tư và quy trình (1 phút)

- Đổi A01 giữa **Làm mờ khuôn mặt** và **Chỉ skeleton + ROI**: chế độ skeleton không còn ảnh người.
- Ở A03 (giường có phiên theo dõi), bấm **Tạm dừng thu hình** vì riêng tư rồi tiếp tục.
- Mở **Bàn giao ca**: cảnh báo đã xử lý, ai làm, việc còn chờ.
- Nói: "Không lưu video vận hành. Chỉ lưu sự kiện và thao tác của nhân viên."

## 5. Tập trước: webcam và khuôn mặt

Điều kiện để panel khuôn mặt hoạt động ổn định:

- Đủ sáng phía trước mặt, không ngồi ngược sáng cửa sổ.
- Mặt nhìn thẳng webcam, không che miệng hay mắt bằng tay hoặc kính phản sáng.
- Ngồi sát cũng được: từ bản sửa ngày 2026-11-21, hồ sơ khuôn mặt vẫn đọc mặt khi hông ra ngoài khung.

Điều kiện để có **cảnh báo** khuôn mặt (rule `FACE_ATTENTION`):

- Engine phải quan sát được thân người, tức là vai và hông trong khung với độ rõ đủ. Ngồi sát webcam thì chỉ có tín hiệu, không có cảnh báo, và đây là hành vi đúng.
- Cần ít nhất 2 nhóm tín hiệu cùng bật (nhóm mắt tính là một), giữ liên tục ≥ 5 giây.
- Đặt laptop trên bàn và ngồi lùi khoảng 1–1,5 m. Vùng đầu trên khung phải ≥ 80 px, nếu không panel sẽ báo "Khuôn mặt quá nhỏ trong khung hình".
- Tập ít nhất 5 lần liên tiếp đạt. Chưa đạt thì bỏ phần cảnh báo khuôn mặt, chỉ trình diễn panel tín hiệu.

Lưu ý: ngưỡng nheo mắt và mắt đóng khá nhạy. Mắt mở bình thường đôi khi vẫn bật "Nheo mắt". Khi trình bày thì nói đây là tín hiệu quan sát, cần người kiểm tra.

## 6. Câu hỏi hội đồng hay hỏi

| Câu hỏi | Trả lời ngắn |
|---|---|
| Có phải video dựng sẵn kết quả không? | Không. Clip chỉ là đầu vào, có thể đổi clip bất kỳ ngay tại chỗ. Khung xương vẽ realtime. Webcam là trực tiếp, giám khảo có thể tự thử |
| Dùng model gì, có train không? | MediaPipe Pose (33 điểm) và Face Landmarker (478 điểm, 52 blendshape), pretrained, không train. Phần nhóm làm là engine sự kiện theo thời gian và quy trình cảnh báo |
| Sao không báo rời giường trên webcam? | Rời giường cần camera thấy trọn giường, thân và sàn. Góc laptop không đủ, nên hệ thống trả "Không đủ dữ liệu quan sát" thay vì đoán |
| Độ chính xác bao nhiêu? | Chỉ nêu số đã đo trên tập dev, ghi rõ nguồn dữ liệu và mẫu số ([calibration-2026-11-18.md](../04-guides/calibration-2026-11-18.md)). Chưa có số lâm sàng |
| Có nhận diện ai không? | Không. Không nhận diện danh tính, không lưu video, mặt được làm mờ khi hiển thị |
| Chạy trên phần cứng gì? | Laptop i5-10300H, CPU, không cần Internet |

## 7. Kiểm lại clip trước buổi demo

Chạy lại trên máy demo, từ `server/`:

```bash
uv run postcare replay --video ../data/demo/fall-a.mp4 --camera-config ../config/cameras/gmdcsa24-room.yaml --out ../runs/check-fall-a --overwrite
```

Mở `runs/check-fall-a/events.jsonl`: phải có `ABNORMAL_MOVEMENT` mức `HIGH`. Clip giường làm tương tự với file `config/cameras/<clip>.yaml` của clip đó.

## 8. Phương án dự phòng

| Sự cố | Xử lý |
|---|---|
| Clip không ra cảnh báo lần này | Kiểm tra giường có phiên đang mở. Còn trong 60 giây debounce thì chờ, hoặc khởi động lại worker. Vẫn không được thì đổi sang clip dự phòng ở mục 2 |
| Webcam tối hoặc không nhận | Bật đèn bàn. Kiểm tra index webcam ở Quản lý camera. Chạy lại `make worker CAMERA=1` |
| API mất kết nối | Worker tự thử lại, giữ nguyên `event_uid`, nên sự kiện không bị mất hay nhân đôi |
| Máy chậm | Tắt bớt ứng dụng. Chỉ chạy 2 worker (A01 + A02) |
