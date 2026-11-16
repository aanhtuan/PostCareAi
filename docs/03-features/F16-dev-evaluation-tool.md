# F16 – Công cụ đánh giá trên tập phát triển

| Thuộc tính | Giá trị |
|---|---|
| Mã | F16 |
| Trạng thái | Todo |
| Ưu tiên | MVP |
| Milestone | M1 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F12, F15 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §13 (tr.14), §13.1–13.3 (tr.14–15); HS §5.5, §8.1, §8.2; ADR-0008; A06 |

## 1. Mục tiêu

Nhóm cần đo được chất lượng rule **từ sớm** để hiệu chỉnh ngưỡng trên tập phát triển (HS §5.5, §8.2). Feature này làm lệnh `postcare eval --split dev`. Lệnh chạy pipeline trên video có ground truth rồi tính P/R/F1 từng loại sự kiện, cảnh báo sai/giờ, latency, coverage và tài nguyên (PDF §13 (tr.14); HS §8.2). Lệnh còn kiểm tra quy tắc chia tập để không lẫn dữ liệu dev với test (HS §8.1). Lý do làm sớm ở M1 xem [ADR-0008](../02-architecture/decisions/ADR-0008-early-eval-tooling.md). Quy trình chung xem [evaluation.md](../04-guides/evaluation.md).

## 2. Phạm vi

**Trong phạm vi**
- Định dạng và validator cho `data/eval/manifest.csv` và `data/eval/truth.csv`.
- Khớp sự kiện dự đoán với ground truth có tolerance cấu hình được.
- Metric: TP/FP/FN, Precision/Recall/F1 từng code, false alerts/giờ, detection latency, coverage, FPS, frame bỏ, CPU/RAM.
- Báo cáo `reports/eval-<split>-<date>.md`.
- Lệnh `postcare eval --split dev` (và lệnh con kiểm tra manifest).

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Chạy trên tập test, `--frozen <hash>`, delivery latency, chỉ số workflow (→ F29).
- Quay video và gán ground truth (task không phải code, ghi trong `docs/progress/TASKS.md`).
- Tự động dò ngưỡng tối ưu (grid search) *(không có trong nguồn)*.
- Train hay fine-tune model (ngoài phạm vi dự án; PDF §13 (tr.14)).

## 3. Yêu cầu chi tiết

- **R1.** Định dạng file theo [evaluation.md](../04-guides/evaluation.md) mục 4 *(HS §8.1; PDF §13.1 (tr.14))*:
  - `manifest.csv`: `video_id, path, split, participant_id, session_id, camera_condition, duration_s, notes`.
  - `truth.csv`: `video_id, event_code, start_s, end_s, notes`.
- **R2.** Validator báo **lỗi** (exit ≠ 0) khi *(HS §8.1)*:
  - thiếu cột bắt buộc, hoặc `split` không thuộc `{dev, test}`;
  - `video_id` hoặc `path` xuất hiện ở hai dòng (cùng video nằm ở hai tập, hoặc khai báo trùng);
  - `event_code` không thuộc `EventCode` (`postcare.schemas`);
  - `start_s > end_s`, hoặc thời điểm vượt `duration_s`;
  - `truth.csv` tham chiếu `video_id` không có trong manifest.
  
  Validator báo **cảnh báo** (không lỗi) khi `participant_id` hoặc `session_id` của tập test trùng với tập dev *(HS §8.1 ghi "khi có thể"; giả định: mức cảnh báo)*.
- **R3.** `postcare eval --split dev` *(ADR-0008)*:
  - Với mỗi video của split, gọi pipeline replay (F12) để có `events.jsonl` và `frames.jsonl`. Có tùy chọn dùng lại thư mục `runs/` đã có *(giả định: tiết kiệm thời gian khi chỉ đổi ngưỡng; với `--from-observations` của F12 thì không cần chạy lại MediaPipe)*.
  - Dùng cấu hình camera (`config/cameras/<setup>.yaml`) giống replay.
- **R4.** Khớp sự kiện *(evaluation.md mục 5; PDF §13.1 (tr.14); A06)*:
  - Sự kiện dự đoán khớp ground truth khi cùng `code` và `occurred_at` nằm trong `[start_s − tol_before, end_s + tol_after]`.
  - Mặc định `tol_before = 1 s`, `tol_after = 3 s` (A06), đổi được bằng tùy chọn CLI *(giả định tên tùy chọn: `--tol-before-s`, `--tol-after-s`)*.
  - Mỗi ground truth khớp tối đa một dự đoán, mỗi dự đoán khớp tối đa một ground truth. Ghép tham lam theo thời gian gần nhất *(giả định: thuật toán ghép)*.
  - Dự đoán không khớp là FP, ground truth không khớp là FN.
- **R5.** Metric *(HS §8.2; PDF §13.2–13.3 (tr.14–15); evaluation.md mục 5)*:
  - TP, FP, FN, Precision, Recall, F1 cho từng `code`. Mẫu số bằng 0 thì ghi "—" *(giả định)*.
  - False alerts/giờ = số FP có priority `MEDIUM` hoặc `HIGH` chia tổng số giờ video của split.
  - Detection latency = `detected_at − start_s` của các TP: trung vị và p90, theo từng code.
  - Coverage = tỷ lệ thời gian trạng thái khác `NO_OBSERVATION` (lấy trạng thái từng frame từ `frames.jsonl` của F12).
  - FPS xử lý trung bình, số frame bỏ, CPU % và RAM MB đo bằng psutil trong lúc chạy replay.
- **R6.** Báo cáo `reports/eval-<split>-<date>.md` theo mẫu [evaluation.md](../04-guides/evaluation.md) mục 7 *(HS §8.2: kèm TP/FP/FN, thời lượng video, điều kiện camera)*:
  - Thông tin chung: ngày, `config_hash`, commit, phần cứng, số video, tổng thời lượng.
  - Bảng theo `code`. Phần tổng hợp. Phân rã theo `camera_condition` và theo kịch bản (lấy tiền tố `Sxx` của `video_id`, *giả định theo quy ước đặt tên ở evaluation.md*).
  - Danh sách FP/FN (video, thời điểm) để xem lại. Mục giới hạn.
- **R7.** Lệnh F16 chỉ chạy `--split dev`. `--split test` báo lỗi rõ ràng và hướng dẫn dùng F29 với `--frozen` *(HS §8.2: không xem kết quả tập test trước khi chốt; giả định: chặn ngay trong công cụ)*.
- **R8.** Phần tính metric là hàm thuần trong `postcare.eval`, test được bằng dữ liệu tổng hợp nhỏ, không cần video *(testing.md mục 1, tầng Eval)*. Ranh giới import: `eval` không import `api`, `db` *(overview.md mục 3)*.
- **R9.** Không commit video hay dữ liệu `data/` *(QA#29; coding-standards.md mục 1)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/eval/manifest.py`: đọc và kiểm tra CSV.
  - `server/src/postcare/eval/matching.py`: ghép dự đoán với ground truth.
  - `server/src/postcare/eval/metrics.py`: P/R/F1, FP/giờ, latency, coverage.
  - `server/src/postcare/eval/perf.py`: đo FPS, CPU, RAM (psutil).
  - `server/src/postcare/eval/report.py`: sinh Markdown.
  - `server/src/postcare/eval/runner.py`: gọi replay cho từng video.
  - `server/src/postcare/cli.py`: lệnh `eval` (và lệnh con kiểm tra manifest).
  - Test: `server/tests/eval/test_manifest.py`, `test_matching.py`, `test_metrics.py`, `test_report.py`.
- **Dữ liệu:** file trong `data/eval/` (gitignore), `runs/`, `reports/`. Không dùng DB.
- **API:** không có.
- **UI:** không có.
- **Cấu hình:** không thêm khóa vào `config/engine.default.yaml`. Báo cáo ghi `config_hash` của cấu hình đã hợp nhất (F10). Tolerance là tùy chọn CLI (A06).

## 5. Acceptance criteria

- [ ] **AC1.** Có định dạng manifest CSV (video, split, người, phiên, điều kiện camera, thời lượng) và ground truth CSV (`video_id, event_code, start_s, end_s`), kèm validator báo lỗi theo R2 *(HS §8.1; evaluation.md mục 4)*. — *Kiểm chứng:* `server/tests/eval/test_manifest.py` (`test_valid_manifest_passes`, `test_unknown_event_code_rejected`, `test_start_after_end_rejected`, `test_truth_references_unknown_video_rejected`).
- [ ] **AC2.** `postcare eval --split dev` tính TP/FP/FN, P/R/F1 từng code. Tolerance mặc định `[start − 1 s, end + 3 s]`, đổi được *(PDF §13.1–13.2 (tr.14); A06)*. — *Kiểm chứng:* `server/tests/eval/test_matching.py` (`test_prediction_inside_tolerance_is_tp`, `test_prediction_outside_tolerance_is_fp_and_fn`, `test_two_predictions_one_truth_gives_one_tp_one_fp`, `test_custom_tolerance`).
- [ ] **AC3.** Tính false alerts/giờ (chỉ MEDIUM/HIGH), detection latency (trung vị, p90), coverage, FPS, frame bỏ, CPU/RAM *(HS §8.2; PDF §13.3 (tr.14–15))*. — *Kiểm chứng:* `server/tests/eval/test_metrics.py` (`test_false_alerts_per_hour_counts_only_medium_high`, `test_latency_median_p90`, `test_coverage_excludes_no_observation`); FPS/CPU/RAM kiểm bằng lần chạy thủ công ghi ở mục 10.
- [ ] **AC4.** Xuất `reports/eval-dev-<date>.md` có `config_hash`, thời lượng video, điều kiện camera, bảng theo code, danh sách FP/FN *(HS §8.2)*. — *Kiểm chứng:* `test_report.py::test_report_contains_required_sections`; chạy thủ công `postcare eval --split dev` trên ít nhất một video dev.
- [ ] **AC5.** Validator báo lỗi khi một video nằm ở cả hai tập (trùng `video_id` hoặc `path`) *(HS §8.1)*. — *Kiểm chứng:* `test_manifest.py::test_video_in_both_splits_rejected`, `test_same_path_two_ids_rejected`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit | CSV tổng hợp nhỏ trong `tmp_path` | Thiếu cột; code lạ; `start_s > end_s`; tham chiếu video không có |
| AC2 | unit | Danh sách dự đoán và ground truth tự viết | Dự đoán ngay ngoài biên tolerance; sai `code`; hai dự đoán cho một ground truth |
| AC3 | unit | Số liệu tính tay (ví dụ 2 FP HIGH trong 0,5 giờ → 4/giờ) | FP mức LOG/INFO không tính vào FP/giờ; frame `NO_OBSERVATION` không tính vào coverage |
| AC4 | unit + thủ công | Sinh báo cáo từ kết quả giả; chạy thật trên video dev | — |
| AC5 | unit | Hai dòng cùng `video_id` khác split; cùng `path` khác `video_id` | — |
| R2 | unit | Test trùng người/phiên giữa dev và test | Chỉ cảnh báo, exit 0 |
| R7 | unit | `eval --split test` không có `--frozen` | Exit ≠ 0, thông báo dùng F29 |

## 7. Giả định

- *(giả định)* Trùng người/phiên giữa dev và test chỉ là cảnh báo (R2).
- *(giả định)* Dùng lại `runs/` đã có để chạy nhanh khi chỉ đổi ngưỡng (R3).
- *(giả định)* Tên tùy chọn tolerance và thuật toán ghép tham lam (R4).
- *(giả định)* Metric có mẫu số 0 ghi "—" (R5).
- *(giả định)* Kịch bản lấy từ tiền tố `video_id` (R6).
- *(giả định)* Công cụ chặn `--split test` khi chưa có F29 (R7).
- Tolerance mặc định theo A06.

## 8. Câu hỏi mở

- **Không chặn:** F16 cần `frames.jsonl` của F12 có trạng thái cơ thể và thời gian xử lý từng frame (để tính coverage và FPS). Nếu spec F12 không có các trường này thì bổ sung vào F12 khi làm F16.
- **Không chặn (phụ thuộc ngoài code):** cần có video dev và ground truth (tuần 3, HS §7.3) để chạy AC4 thật.

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
