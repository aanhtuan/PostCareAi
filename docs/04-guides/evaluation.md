# Thu thập dữ liệu và đánh giá

Nguồn: HS §7.2, §8.1, §8.2; PDF §13. Công cụ: F12 (replay), F16 (eval trên tập dev), F29 (đánh giá chính thức).

## 1. Nguyên tắc

- Chỉ dùng tình huống **mô phỏng** với người trưởng thành **tự nguyện**, có quyền sử dụng rõ ràng. Không dùng video bệnh nhân thật (HS §6.3, §7.2; PDF §11).
- Dữ liệu dùng để **hiệu chỉnh rule và đánh giá sản phẩm**, không dùng để train model (HS §7.2; PDF §13).
- Không đặt trước con số accuracy (PDF §13).
- Video lưu ở `data/` (gitignore). Chỉ những người trong nhóm truy cập.

## 2. Đồng ý của người tham gia *(giả định: mẫu nội bộ)*

Trước khi quay, ghi lại cho mỗi người tham gia:
- họ tên;
- đồng ý được quay cho mục đích dự thi và đánh giá;
- đồng ý hoặc không đồng ý dùng hình ảnh trong slide/video demo;
- thời hạn lưu;
- yêu cầu xóa.

Bản ký lưu ngoài repo. Trong manifest chỉ dùng mã người tham gia (`P01`, `P02`…).

## 3. Bộ kịch bản (HS §8.1; PDF §13.1)

| Mã | Kịch bản | Sự kiện kỳ vọng |
|---|---|---|
| S01 | Nằm yên | — |
| S02 | Trở mình / xoay người | POSTURE_CHANGE |
| S03 | Ngồi dậy rồi nằm lại | SIT_UP (không BED_EXIT) |
| S04 | Ngồi ở mép giường | SIT_UP, BED_EDGE |
| S05 | Đứng dậy | STAND_UP |
| S06 | Rời giường (bắt đầu từ nằm) | SIT_UP, BED_EDGE, STAND_UP, BED_EXIT |
| S07 | Quay lại giường | RETURN_TO_BED |
| S08 | Người khác đi ngang khung hình | — |
| S09 | Điều dưỡng đứng gần giường | — |
| S10 | Cơ thể bị che một phần | — hoặc OBSERVATION_LOST |
| S11 | Thay đổi ánh sáng | — hoặc OBSERVATION_LOST |
| S12 | Mặt quay khỏi camera | — (không FACE_ATTENTION) |
| S13 | Nhắm mắt kéo dài | tín hiệu mắt; có thể "Đang nghỉ" |
| S14 | Hạ lông mày, nheo mắt kéo dài | FACE_ATTENTION |
| S15 | Chuyển động nhanh xuống nệm an toàn | ABNORMAL_MOVEMENT |
| S16 | Ít vận động kéo dài | ACTIVITY_LOW_PROLONGED |

Mỗi kịch bản quay **nhiều lượt**, thay đổi vừa phải về tốc độ và vị trí (HS §8.1). Gợi ý *(giả định)*: tập dev ≥ 3 lượt / kịch bản, tập test ≥ 2 lượt / kịch bản, với người hoặc phiên khác.

## 4. Định dạng file

`data/eval/manifest.csv`:

```csv
video_id,path,split,participant_id,session_id,camera_condition,duration_s,notes
S06_P01_r1,data/videos/S06_P01_r1.mp4,dev,P01,day1,"tripod-head-left;light-normal",42.0,
```

`data/eval/truth.csv` (ground truth, HS §8.1):

```csv
video_id,event_code,start_s,end_s,notes
S06_P01_r1,BED_EDGE,20.0,25.0,
S06_P01_r1,BED_EXIT,27.0,27.0,
```

`config/cameras/<setup>.yaml`: ROI (toạ độ chuẩn hóa) + override ngưỡng cho cấu hình camera dùng khi quay.

**Quy tắc chia tập** (HS §8.1):
- Một `video_id` chỉ thuộc **một** split.
- Không cắt frame của cùng một video sang hai tập.
- Tập test nên có `participant_id` hoặc `session_id` khác tập dev.

Validator của F16 kiểm tra các quy tắc này.

## 5. Cách khớp và metric

- **Khớp sự kiện:** một sự kiện dự đoán cùng `code` khớp ground truth nếu thời điểm `occurred_at` nằm trong `[start_s − 1, end_s + 3]` giây *(giả định A06, cấu hình được)*. Mỗi ground truth khớp tối đa một dự đoán.
- **Metric** (HS §8.2):
  - TP, FP, FN, Precision, Recall, F1 cho từng `code`.
  - False alerts / giờ: số FP mức MEDIUM/HIGH chia cho tổng giờ video.
  - Detection latency: `detected_at − start_s` của các TP (trung vị, p90).
  - Delivery latency (F29): `WS nhận − events.created_at` (trung vị, p90).
  - Coverage: tỷ lệ thời gian không ở NO_OBSERVATION.
  - FPS trung bình, frame bỏ, CPU %, RAM MB (psutil).
  - Workflow (F29): thời gian Chờ → Tiếp nhận → Xử lý, tỷ lệ cảnh báo có ghi kết quả, tỷ lệ "Cảnh báo sai".

## 6. Quy trình hiệu chỉnh và chốt (HS §8.2)

1. Quay tập dev; gán ground truth.
2. Lặp: `postcare replay` → `postcare eval --split dev` → chỉnh `config/engine.default.yaml` hoặc override camera → lặp lại.
3. **Chốt**: ghi `config_hash` vào `reports/frozen-config.txt` và commit.
4. Quay tập test (người/phiên khác). **Không** xem kết quả tập test trước khi chốt.
5. `postcare eval --split test --frozen <hash>` → `reports/final-eval.md`.
6. Báo cáo kèm:
   - TP/FP/FN;
   - thời lượng video;
   - điều kiện camera;
   - phần cứng.

## 7. Mẫu báo cáo (`reports/eval-<split>-<date>.md`)

- **Thông tin chung:** ngày, `config_hash`, phiên bản code (commit), phần cứng, số video, tổng thời lượng.
- **Bảng theo `code`:** TP, FP, FN, Precision, Recall, F1, latency trung vị/p90.
- **Tổng hợp:** false alerts/giờ, coverage, FPS, frame bỏ, CPU, RAM.
- **Phân rã** theo `camera_condition` và kịch bản.
- **Danh sách FP/FN** (video, thời điểm) để xem lại.
- **Giới hạn:** điều kiện mô phỏng, số người tham gia.
