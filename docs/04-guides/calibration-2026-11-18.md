# Hiệu chỉnh ngưỡng trên tập dev (18/11/2026)

Nguồn: HS §5.5, §8.2; QA#22 (hiệu chỉnh trên dev, chốt trước khi chạy test). Công cụ: `postcare eval` (F16). Liên quan: [evaluation.md](evaluation.md) §6, [datasets.md](datasets.md), [event-engine.md](../02-architecture/event-engine.md) §5–§6, F16 và F23 mục 10.

**Chỉ dùng tập dev.** Không xem khung hình, observation hay kết quả của bất kỳ video tập test nào. Tập test chỉ chạy một lần ở F29 với `--frozen <hash>`.

## 1. Cách làm

- Dữ liệu: 189 video dev (1342 s), gồm URFD (100), GMDCSA24 Subject 1–2 (80), Pexels (9). Không có video nhóm tự quay. Nhãn: `dataset` cho URFD/GMDCSA24, `manual` cho Pexels.
- Chạy chỉ engine trên observation đã cache của F16 (model pose `full`, `--max-fps 15`). Ví dụ:

  ```bash
  cd server
  POSTCARE_DATA_DIR=<data> uv run postcare eval --split dev \
    --from-observations ../runs/eval-dev --runs-dir ../runs/cal-<tên> \
    --report ../reports/cal-<tên>.local.md [--engine-config <biến thể>.yaml]
  ```

  Biến thể ngưỡng là bản sao `config/engine.default.yaml` đổi một khóa, để ngoài repo. Báo cáo `reports/cal-*.local.md` không commit.
- Thử từng giả thuyết một và đo P/R/F1 theo mã, FP/giờ, coverage, latency (`detected − start_s`, trung vị). Mỗi kết quả tách theo nguồn dữ liệu.
- **Recall `ABNORMAL_MOVEMENT` tính trên 71 ngã** (URFD cam0 30 + GMDCSA24 41). URFD cam1 (camera trần, coverage 3–5 %) nằm ngoài [camera-setup.md](camera-setup.md) và được ghi riêng (F23 mục 10).
- FP/giờ "NEG" là FP mức MEDIUM/HIGH trên 78 clip ADL (647,6 s).

## 2. Kết quả: ban đầu và sau hiệu chỉnh

`config_hash` ban đầu: `209d60d22e16de6783bcdd230666e573c7c900487178e89812efd757d0491dda`. Sau hiệu chỉnh: `cb7a5ed7043e14946de01cefba39d75c023706282e9bbea66776980e48ae44ec`.

| Mã | Ban đầu TP/FP/FN | P | R | F1 | Latency | Sau TP/FP/FN | P | R | F1 | Latency |
|---|---|---|---|---|---|---|---|---|---|---|
| `ABNORMAL_MOVEMENT` (101, cả cam1) | 2/2/99 | 0,50 | 0,02 | 0,04 | 4,27 s | 19/1/82 | 0,95 | 0,19 | 0,31 | 2,81 s (p90 3,05) |
| `ABNORMAL_MOVEMENT` (71, bỏ cam1) | 2/2/69 | 0,50 | 0,03 | 0,05 | | 19/1/52 | 0,95 | 0,27 | 0,42 | |
| `BED_EDGE` | 2/2/2 | 0,50 | 0,50 | 0,50 | 3,54 s | 2/0/2 | 1,00 | 0,50 | 0,67 | 1,71 s |
| `SIT_UP` | 0/0/4 | — | 0,00 | — | — | 0/0/4 | — | 0,00 | — | — |
| `STAND_UP` | 0/0/3 | — | 0,00 | — | — | 0/0/3 | — | 0,00 | — | — |
| `BED_EXIT` | 0/0/3 | — | 0,00 | — | — | 0/0/3 | — | 0,00 | — | — |

| Tổng hợp | Ban đầu | Sau |
|---|---|---|
| False alerts/giờ (toàn tập dev) | 10,7 | 2,7 |
| False alerts/giờ trên ADL (NEG) | 11,1 | 5,6 |
| Coverage | 40,9 % | 42,7 % |

**Theo nguồn (`ABNORMAL_MOVEMENT`, nhãn `dataset`):**

| Nguồn | Ban đầu TP/FP/FN | Sau TP/FP/FN | Coverage ban đầu → sau |
|---|---|---|---|
| GMDCSA24 S1, 16 ngã | 2/0/14 | 8/0/8 | 33,8 % → 29,0 % |
| GMDCSA24 S2, 25 ngã | 0/0/25 | 9/0/16 | 51,1 % → 57,9 % |
| URFD cam0, 30 ngã | 0/0/30 | 2/0/28 | 24,9 % → 26,0 % |
| URFD cam1, 30 ngã (ghi riêng) | 0/0/30 | 0/0/30 | 3,5 % → 4,5 % |
| GMDCSA24 ADL (âm tính) | FP 1 (`gmd_s2_adl_09`) | FP 1 (`gmd_s2_adl_09`) | 59,2 % → 61,0 % |
| URFD ADL (âm tính) | FP 1 (`urfd_adl11_cam0`) | FP 0 | 33,7 % → 35,3 % |

Mã `BED_*`, `SIT_UP`, `STAND_UP` chỉ có nhãn trên 9 clip stock Pexels (`manual`) và 1 clip GMDCSA24: chỉ để tham khảo (datasets.md §5).

## 3. Thay đổi giữ lại

### 3.1 Dữ liệu: cấu hình camera theo clip (không đổi ngưỡng)

- Thêm `config/cameras/pexels-{8090730,3753707,4052924,6944081,8860232,6130226,6130032,6130026}.yaml`: ROI giường vẽ bằng mắt cho 8 clip stock dev còn lại *(giả định)*, `thresholds: {}`.
- Thêm `config/cameras/urfd-cam1.yaml` và `config/cameras/gmdcsa24-room.yaml`: ROI gần trọn khung *(giả định)*, như `urfd-cam0.yaml` và `caucafall.yaml`. Dataset ngã chỉ chấm `ABNORMAL_MOVEMENT`; rule này không xét ROI, chỉ cần nhận được người mục tiêu. GMDCSA24 Subject 2 đổi vị trí camera nhiều lần.
- Thêm cột `camera_config` vào `data/eval/manifest.csv` (không commit) theo quy tắc ở [datasets.md](datasets.md) §3.5.
- Kết quả (cùng hash `209d60d2…`): hết 2 FP `BED_EDGE` của ROI mẫu (`pexels-4052924` lúc đang nằm, `pexels-8860232`), `BED_EDGE` P = 1,00, latency 3,54 → 1,71 s, coverage 40,9 → 42,7 %. `ABNORMAL_MOVEMENT` không đổi (0/30 URFD cam0 với ROI gần trọn khung, như F23 đã đo).

### 3.2 `abnormal_movement.hold_after_s`: 2,0 → 1,0 (H1)

Chẩn đoán 71 ngã ở cấu hình ban đầu:
- 24 ca có chuyển động **còn chờ khi clip hết**, phần lớn đã có đủ 3 dấu hiệu nhanh;
- 40 ca mất người mục tiêu ngay lúc ngã (phần lớn là MediaPipe không trả về người: 194/239 frame `NO_PERSON` trong 9 clip mẫu);
- 3 ca không có dấu hiệu nhanh; 2 ca thiếu điều kiện; 2 TP.

Rule chấm sau khi hết dấu hiệu nhanh `window_s + hold_after_s` (≈ 3,5 s), trong khi clip dừng 1–3 s sau khi ngã.

| `hold_after_s` (`window_s` 1,5; C4 0,8) | TP/FP (71 ngã) | R | NEG FP/giờ |
|---|---|---|---|
| 2,0 (ban đầu) | 2/2 | 0,03 | 11,1 |
| 1,5 | 6/2 | 0,08 | 11,1 |
| 1,0 | 10/2 | 0,14 | 11,1 |
| 0,5 | 12/1 | 0,17 | 5,6 |

Chọn 1,0 s: tăng ở cả GMDCSA24 S1 và S2, không thêm FP. Không chọn 0,5 s vì C5 ("giữ nguyên sau đó") gần như không còn khoảng để đo. Trên camera thật người nằm lại trên sàn nên không bị cắt clip; giá trị này chủ yếu rút ngắn độ trễ cảnh báo.

Hệ quả: tốc độ mẫu vận động đo trên bước `activity.sample_interval_s` (1,0 s) về trước, nên với khoảng giữ 1,0 s, C5 còn thấy đuôi chuyển động. C5 khó thỏa hơn. Trên dev, C5 vốn hiếm thỏa (mục 4, H3). Test `test_each_condition_counted` cố định `hold_after_s = 2 × sample_interval_s` để vẫn kiểm từng điều kiện C1–C5.

### 3.3 `abnormal_movement.final_low_position_ratio`: 0,8 → 0,75 (H4, đặt chung)

Với `hold_after_s` 1,0, 5 ca có đủ C2 + C3 nhưng hông cuối ở 0,76–0,78 chiều cao khung (GMDCSA24 S1 05, 07, 08; S2 19, 23). Các ca này thiếu điều kiện hạ thấp bắt buộc. FP ADL có hông cuối ở 0,70 và 0,79.

| C4 (`hold` 1,0, `window` 1,5) | TP/FP | R | NEG FP/giờ |
|---|---|---|---|
| 0,80 | 10/2 | 0,14 | 11,1 |
| 0,75 | 15/2 | 0,21 | 11,1 |
| 0,70 | 15/2 | 0,21 | 11,1 |

Chọn 0,75, mức nới nhỏ nhất cho cùng kết quả. Đặt ở ngưỡng mặc định, **không** override theo camera. Lý do: một `config_hash` cho mọi camera của tập test, và tránh tinh chỉnh riêng theo dataset. Override theo camera (H4 gốc) để dành cho camera thật sau khi chốt vị trí đặt (camera-setup.md).

### 3.4 `abnormal_movement.window_s`: 1,5 → 1,0

Cửa sổ ngắn hơn làm dấu hiệu nhanh tắt sớm hơn sau chuyển động, nên rule chấm sớm hơn (≈ 2 s thay vì 3,5 s). Dịch chuyển được đo trên 1 s, nên cử động chậm (nằm xuống chậm, ngồi xuống) khó đạt ngưỡng hơn.

| Biến thể | TP/FP | R | NEG FP/giờ | Latency |
|---|---|---|---|---|
| `window` 1,5, `hold` 1,0, C4 0,75 | 15/2 | 0,21 | 11,1 | 3,36 s |
| `window` 1,0, `hold` 2,0, C4 0,80 | 8/1 | 0,11 | 5,6 | 3,84 s |
| `window` 1,0, `hold` 1,0, C4 0,80 | 15/1 | 0,21 | 5,6 | 2,83 s |
| `window` 1,0, `hold` 1,5, C4 0,75 | 14/1 | 0,20 | 5,6 | 3,37 s |
| `window` 1,0, `hold` 1,2, C4 0,75 | 17/1 | 0,24 | 5,6 | 3,03 s |
| **`window` 1,0, `hold` 1,0, C4 0,75 (chọn)** | **19/1** | **0,27** | **5,6** | **2,81 s** |

Cấu hình chọn tăng recall ở cả ba nguồn (GMDCSA24 S1, S2 và URFD cam0 2/30) và giảm FP ADL (mất FP `urfd_adl11_cam0`). Ngã cuối cùng còn trượt: 38 ca mất người mục tiêu lúc ngã, 8 ca còn chờ khi hết clip, 4 ca thiếu điều kiện, 2 ca không có dấu hiệu nhanh.

## 4. Đã thử nhưng không giữ

| Giả thuyết | Thử | Kết quả | Quyết định |
|---|---|---|---|
| **H2**: cho phép gián đoạn ngắn (frame không `GOOD`) trong cửa sổ | Vá thử tạm thời (không commit): bỏ qua frame không `GOOD` khi cổng còn mở nếu cách mẫu tốt trước ≤ 0,2 / 0,4 / 0,7 s (trên `hold` 1,0, C4 0,75) | 18/5, 18/5, 20/5 so với 15/2; **NEG FP/giờ 11,1 → 27,8** (thêm 3 FP ADL GMDCSA24/URFD) | Không giữ: thêm 3 TP nhưng thêm 3 cảnh báo sai, precision 0,88 → 0,78. Phần lớn ca mất mục tiêu là mất hẳn tới cuối clip (pose không thấy người nằm), không phải gián đoạn ngắn. R8 giữ nguyên. |
| **H3**: ngưỡng "yên" của C5 | `activity.low_threshold` 0,05 / 0,08 / 0,12 (thay cho khóa riêng) | `hold` 2,0: 2/3 (thêm 1 FP ở mọi mức); `hold` 1,0: 11–12/3; cấu hình chọn + 0,05: 20/1 (+1 TP) | Không giữ: chỉ +1 TP, có biến thể thêm FP. Khóa này còn quyết định `activity_level`, `ACTIVITY_LOW_PROLONGED` và F27, nhưng chưa có truth (S16). Xem lại khi có video nhóm quay. Không thêm khóa `abnormal_movement.still_threshold`. |
| Đứng dậy (F16 đề xuất) | `posture.standing_hip_above_knee_ratio` 0,7 / 0,6; `min_duration_s.STANDING` 0,5; cả hai | `STAND_UP` / `BED_EXIT` vẫn 0/3, `BED_EDGE` không đổi | Không giữ. Nguyên nhân không phải ngưỡng: trên `pexels-8090735` lúc đứng dậy, keypoint vai nhảy 0,0–0,5 chiều cao khung (có frame vai thấp hơn hông → tư thế không xác định, ngắt `min_duration`), rồi người ra khỏi khung (`NO_PERSON`). Trên `pexels-4052924` chân bị cắt ở đáy khung, không phân loại được đứng. |
| `min_duration_s.LYING` (SIT_UP) | Không thử | — | F16 mục 10: không hạ khi chưa có video nhóm quay bắt đầu từ nằm yên. SIT_UP trên stock và GMDCSA24 ADL/04 bị trượt vì clip bắt đầu giữa động tác; trạng thái đầu là `RAISING`, không phải `LYING`. |

## 5. Giới hạn còn lại

- **Không có video rời giường quay bằng camera cố định theo camera-setup.md.** `SIT_UP` / `STAND_UP` / `BED_EXIT` vẫn 0 trên dev; không có dữ liệu để hiệu chỉnh `posture.*`, `location.*`, `min_duration_s.*`. Các ngưỡng này giữ giá trị khởi điểm và **cần hiệu chỉnh lại trên tập dev nhóm quay** (HS §7.3) trước khi coi là chốt cho sản phẩm.
- Clip ngã của dataset dừng 1–3 s sau khi ngã; rule chấm sau `window_s + hold_after_s` (≈ 2 s). 8 ca vẫn còn chờ khi hết clip. Nhiều ngã GMDCSA24 bắt đầu trước khi engine có đủ ~2 s quan sát (cổng phục hồi + cửa sổ), nên `occurred_at` rơi vào mốc đầu tiên xét được (~2,0 s).
- MediaPipe Pose thường không trả về người nằm trên sàn (38/71 ca mất mục tiêu lúc ngã), nhất là URFD 320×240. Đây là giới hạn của model pretrained; dự án không train (AGENTS.md quy tắc 2).
- Ngã xuống sàn khác S15 (xuống nệm an toàn); C4 là vị trí tuyệt đối trong khung và phụ thuộc góc camera.
- Mẫu nhỏ: 71 ngã, 78 ADL, 9 clip stock; mỗi thay đổi là vài ca. Không có khoảng tin cậy. Kết quả trên dữ liệu ngoài không thay cho tập dev/test của nhóm (evaluation.md §8).
- Nhãn stock gán tay (sai số 0,5–1 s); ROI của clip stock và dataset ngã là ước lượng *(giả định)*.

## 6. Chốt cho F29

- `config_hash` để chốt: **`cb7a5ed7043e14946de01cefba39d75c023706282e9bbea66776980e48ae44ec`** (`config/engine.default.yaml` ở commit này). Mọi cấu hình camera dùng trên dev/test đều có `thresholds: {}`, nên chung một hash.
- F29 cần: ghi hash vào `reports/frozen-config.txt` (evaluation.md §6), vẽ ROI giường cho dòng GMDCSA24 test có `SIT_UP` (datasets.md §3.5) **trước** khi chạy, rồi chạy `postcare eval --split test --frozen <hash>` một lần.
- Fixture `server/tests/fixtures/gmd_s1_fall12_abnormal_movement.expected.json` được sinh lại bằng lệnh ở [testing.md](testing.md) (`postcare replay --from-observations … --camera-config config/cameras/gmdcsa24-subject1.yaml --start-s 0 --end-s 7 --save-observations … --save-expected`). Observation không đổi; `ABNORMAL_MOVEMENT` `occurred_at_ms` 2563 → 2358 (cửa sổ 1,0 s tìm thấy mẫu nhanh sớm hơn), vẫn trong khoảng "Falling" của nhãn gốc (1,9–6 s); `BED_EXIT` không đổi.
