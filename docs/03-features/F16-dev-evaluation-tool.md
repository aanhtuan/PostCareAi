# F16 – Công cụ đánh giá trên tập phát triển

| Thuộc tính | Giá trị |
|---|---|
| Mã | F16 |
| Trạng thái | In review |
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

- [x] **AC1.** Có định dạng manifest CSV (video, split, người, phiên, điều kiện camera, thời lượng) và ground truth CSV (`video_id, event_code, start_s, end_s`), kèm validator báo lỗi theo R2 *(HS §8.1; evaluation.md mục 4)*. — *Kiểm chứng:* `server/tests/eval/test_manifest.py` (`test_valid_manifest_passes`, `test_unknown_event_code_rejected`, `test_start_after_end_rejected`, `test_truth_references_unknown_video_rejected`).
- [x] **AC2.** `postcare eval --split dev` tính TP/FP/FN, P/R/F1 từng code. Tolerance mặc định `[start − 1 s, end + 3 s]`, đổi được *(PDF §13.1–13.2 (tr.14); A06)*. — *Kiểm chứng:* `server/tests/eval/test_matching.py` (`test_prediction_inside_tolerance_is_tp`, `test_prediction_outside_tolerance_is_fp_and_fn`, `test_two_predictions_one_truth_gives_one_tp_one_fp`, `test_custom_tolerance`).
- [x] **AC3.** Tính false alerts/giờ (chỉ MEDIUM/HIGH), detection latency (trung vị, p90), coverage, FPS, frame bỏ, CPU/RAM *(HS §8.2; PDF §13.3 (tr.14–15))*. — *Kiểm chứng:* `server/tests/eval/test_metrics.py` (`test_false_alerts_per_hour_counts_only_medium_high`, `test_latency_median_p90`, `test_coverage_excludes_no_observation`); FPS/CPU/RAM kiểm bằng lần chạy thủ công ghi ở mục 10.
- [x] **AC4.** Xuất `reports/eval-dev-<date>.md` có `config_hash`, thời lượng video, điều kiện camera, bảng theo code, danh sách FP/FN *(HS §8.2)*. — *Kiểm chứng:* `test_report.py::test_report_contains_required_sections`; chạy thủ công `postcare eval --split dev` trên ít nhất một video dev.
- [x] **AC5.** Validator báo lỗi khi một video nằm ở cả hai tập (trùng `video_id` hoặc `path`) *(HS §8.1)*. — *Kiểm chứng:* `test_manifest.py::test_video_in_both_splits_rejected`, `test_same_path_two_ids_rejected`.

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
- *(giả định)* Dữ liệu ngoài: dự đoán có mã không nằm trong `eval_codes` (cột `notes`) của video không tính FP; ground truth chỉ đầy đủ với các mã đó (evaluation.md §8, datasets.md §5). Video không ghi `eval_codes` thì mọi mã đều được chấm.
- *(giả định)* Cột tuỳ chọn `camera_config` trong manifest (đường dẫn `config/cameras/*.yaml`); trống thì dùng `config/cameras/<tên file video>.yaml` nếu có, còn lại dùng `--camera-config` (mặc định `example.yaml`).
- *(giả định)* Đường dẫn tương đối trong manifest bắt đầu bằng `data/` được tính từ thư mục dữ liệu (`POSTCARE_DATA_DIR`, mặc định `data/` ở gốc repo); đường dẫn khác tính từ gốc repo.
- *(giả định)* File báo cáo có hậu tố `.local` (`reports/eval-dev-<date>.local.md` + `.local.json`) để không commit nhầm (`.gitignore`: `reports/*.local.md`, `reports/*.local.json`).
- *(giả định)* Thời điểm ghép là `occurred_at_ms`; latency dùng `detected_at_ms` (QA#37: đã gồm `min_duration`).

## 8. Câu hỏi mở

- **Không chặn:** F16 cần `frames.jsonl` của F12 có trạng thái cơ thể và thời gian xử lý từng frame (để tính coverage và FPS). Nếu spec F12 không có các trường này thì bổ sung vào F12 khi làm F16.
- **Không chặn (phụ thuộc ngoài code):** cần có video dev và ground truth (tuần 3, HS §7.3) để chạy AC4 thật.
- **Không chặn:** script sinh `data/eval/manifest.csv` / `truth.csv` từ dữ liệu ngoài (quy tắc ở datasets.md §3.5) chưa có trong repo. Spec F16 chỉ có định dạng và validator, không có lệnh sinh manifest, nên F16 **không** làm. Nếu cần, mở feature/task riêng.

## 9. Kế hoạch triển khai

Khảo sát code (2026-11-18): F12 đã có `postcare.replay.runner.replay_video` / `replay_observations` (ghi `observations.jsonl`, `events.jsonl` = `EventRecord`, `frames.jsonl` = `FrameRecord` có `body_state`, `run.json` có `fps_processing`, `dropped_frames`, `cpu_percent`, `ram_peak_mb`, `config_hash`, `video_duration_s`). Câu hỏi mở về `frames.jsonl` (mục 8) đã được F12 đáp ứng, không cần sửa F12. `load_camera_config`, `CameraConfig.engine_config` dùng lại cho cấu hình camera. Catalog mức ưu tiên ở `postcare.schemas.events.EVENT_CATALOG`.

1. **Manifest/truth** — `server/src/postcare/eval/manifest.py`: `ManifestRow`, `TruthRow`, `load_manifest`, `load_truth`, `validate(manifest, truth) → ValidationResult(errors, warnings)`. Đọc cột bổ sung của dữ liệu ngoài (`source`, `license`, `display`, `label_source`; evaluation.md §8), tách `scenario=`/`eval_codes=` trong `notes`. Cột tuỳ chọn `camera_config` *(giả định, mục 7)*. Test `tests/eval/test_manifest.py`: `test_valid_manifest_passes`, `test_missing_column_rejected`, `test_bad_split_rejected`, `test_unknown_event_code_rejected`, `test_start_after_end_rejected`, `test_time_beyond_duration_rejected`, `test_truth_references_unknown_video_rejected`, `test_video_in_both_splits_rejected`, `test_same_path_two_ids_rejected`, `test_participant_overlap_is_warning_only`, `test_eval_codes_parsed_from_notes`.
2. **Ghép** — `eval/matching.py`: `Prediction`, `match_video(preds, truths, tol_before_s, tol_after_s) → MatchResult(tp, fp, fn)`; ghép tham lam theo khoảng cách thời gian nhỏ nhất (khoảng cách tới đoạn `[start, end]`, hòa thì ưu tiên dự đoán sớm hơn), từng `code`. Lọc mã không thuộc `eval_codes` của video *(giả định datasets.md §5, evaluation.md §8)*. Test `test_matching.py`: `test_prediction_inside_tolerance_is_tp`, `test_prediction_outside_tolerance_is_fp_and_fn` (ngay ngoài hai biên), `test_wrong_code_is_fp_and_fn`, `test_two_predictions_one_truth_gives_one_tp_one_fp`, `test_custom_tolerance`, `test_greedy_nearest_pairing`, `test_unlisted_code_not_counted_as_fp`.
3. **Metric** — `eval/metrics.py` (hàm thuần): `per_code_counts`, `prf` (mẫu số 0 → `None`, báo cáo ghi "—"), `false_alerts_per_hour` (chỉ FP MEDIUM/HIGH), `latency_stats` (trung vị, p90 nội suy tuyến tính), `coverage(frames)` (theo thời gian: mỗi khung kéo dài tới khung sau, khung cuối dùng trung vị bước), `aggregate_perf(runs)`. Test `test_metrics.py`: `test_false_alerts_per_hour_counts_only_medium_high` (2 FP HIGH / 0,5 h → 4/giờ; FP LOG/INFO không tính), `test_latency_median_p90`, `test_coverage_excludes_no_observation`, `test_prf_zero_denominator_is_none`, `test_perf_aggregate`.
4. **Báo cáo** — `eval/report.py`: `EvalResult` → Markdown (mục 7 evaluation.md: thông tin chung, bảng theo code, tổng hợp, phân rã `camera_condition`/kịch bản/nguồn + `label_source`, danh sách FP/FN, giới hạn) và JSON. Kịch bản lấy `scenario=` trong `notes`, không có thì tiền tố `Sxx` của `video_id`. Test `test_report.py::test_report_contains_required_sections`, `test_report_marks_external_sources`.
5. **Runner** — `eval/runner.py`: với mỗi video của split: chọn cấu hình camera (cột `camera_config` → `config/cameras/<tên file video>.yaml` nếu có → `--camera-config` mặc định `example.yaml`); chạy `replay_video` (pose) hoặc `replay_observations` (`--from-observations <dir>` đọc `<dir>/<video_id>/observations.jsonl`); `--reuse` bỏ qua video đã có kết quả cùng `config_hash`. Đầu ra `runs/eval-<split>/<video_id>/`. `eval/perf.py` đọc FPS/CPU/RAM/khung bỏ từ `run.json` (psutil đo trong replay F12). Adapter pose truyền vào từ CLI (runner không import mediapipe). Test `test_runner.py` với `FakePoseAdapter`/observation tổng hợp: chạy từ observations, `--reuse`, thiếu file → lỗi theo video.
6. **CLI** — `cli/main.py`: nhóm `postcare eval` (`--split`, `--manifest`, `--truth`, `--tol-before-s`, `--tol-after-s`, `--runs-dir`, `--from-observations`, `--reuse`, `--report`, `--model`, `--models-dir`, `--max-fps`, `--limit`, `--video-id`) và lệnh con `postcare eval check`. `--split test` → exit 2, hướng dẫn F29 `--frozen` (R7). Lỗi validator → exit 1. Báo cáo mặc định `reports/eval-<split>-<date>.local.md` + `.local.json` *(giả định: hậu tố `.local` để gitignore, mục 7)*. Test `test_cli.py`: `test_split_test_rejected`, `test_check_command_errors_exit_nonzero`, `test_check_warns_only`, `test_eval_from_observations_writes_report`.
7. **Chạy thật** trên split dev của `D:\PostCareAi\data\eval\manifest.csv` (model `full`, `--max-fps 15`); ghi kết quả và đề xuất hiệu chỉnh ngưỡng vào mục 10 (F16 không đổi ngưỡng).
8. **Doc**: `evaluation.md` (§4 cột `camera_config`, cách chạy `postcare eval`, mục 7 tên file), `dev-setup.md` nếu cần, `.gitignore` thêm `reports/*.local.json`.

Không migration, không endpoint, không sinh lại type API, không thêm thư viện (psutil đã có từ F12). Ranh giới: `postcare.eval` chỉ import `schemas`, `replay`, `engine` (không `api`, `db`, không mediapipe) — import-linter `offline-no-api-db`.

Rủi ro: chạy pose trên ~190 video dev mất nhiều phút (≈ 17 FPS xử lý ở F12) → chạy nền, có `--reuse` để chạy tiếp; ROI của dữ liệu ngoài là ước lượng hoặc mặc định nên metric BED_* chỉ tham khảo.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

Ngày 2026-11-18, nhánh `feat/F16-dev-eval`, Windows 11, Intel i5-10300H (8 luồng), model pose `full` (CPU), `--max-fps 15`.

**Test (không media):** `tests/eval/` 43 test xanh: `test_manifest.py` (AC1, AC5, R2: cột thiếu, split lạ, code lạ, `start_s > end_s`, vượt `duration_s`, truth tham chiếu video lạ, trùng `video_id`/`path`, trùng người/phiên chỉ cảnh báo, `scenario=`/`eval_codes=` trong `notes`, cột dữ liệu ngoài); `test_matching.py` (AC2: hai biên tolerance, ngay ngoài biên, sai code, hai dự đoán một truth, tolerance tùy chỉnh, ghép gần nhất, mã ngoài `eval_codes` không tính FP); `test_metrics.py` (AC3: FP/giờ chỉ MEDIUM/HIGH, latency trung vị/p90, coverage theo thời gian bỏ NO_OBSERVATION, P/R/F1 mẫu số 0, gộp FPS/CPU/RAM); `test_report.py` (AC4); `test_runner_cli.py` (R3, R7: chạy video với `FakePoseAdapter`, `--from-observations`, `--reuse`, cấu hình camera theo tên file video, `--split test` exit ≠ 0 và nhắc F29 `--frozen`, `eval check` lỗi/cảnh báo, báo cáo + JSON).

**Chạy thật (AC3, AC4):** `postcare eval check` trên `D:\PostCareAi\data\eval\` → hợp lệ, 379 video (dev 189, test 190), 211 dòng truth, không cảnh báo. `POSTCARE_DATA_DIR=D:\PostCareAi\data POSTCARE_MODELS_DIR=D:\PostCareAi\models uv run postcare eval --split dev` chạy **toàn bộ** 189 video dev (1342 s video, ~13 phút xử lý), 0 video lỗi, `config_hash 782ec946…`. Báo cáo `reports/eval-dev-2026-11-18.local.md` (không commit).

| Mã | Nguồn (nguồn nhãn) | TP | FP | FN | P | R | F1 | Latency trung vị |
|---|---|---|---|---|---|---|---|---|
| ABNORMAL_MOVEMENT | URFD 60 + GMDCSA24 41 (dataset) | 0 | 0 | 101 | — | 0,00 | — | — |
| SIT_UP | Pexels 3 (manual) + GMDCSA24 1 (dataset) | 0 | 0 | 4 | — | 0,00 | — | — |
| BED_EDGE | Pexels (manual) | 2 | 2 | 2 | 0,50 | 0,50 | 0,50 | 3,5 s (p90 5,3 s) |
| STAND_UP | Pexels (manual) | 0 | 0 | 3 | — | 0,00 | — | — |
| BED_EXIT | Pexels (manual) | 0 | 0 | 3 | — | 0,00 | — | — |

- Tổng hợp: false alerts/giờ 5,4 (2 FP BED_EDGE trong 22,4 phút; riêng Pexels 38/giờ trên 189 s), coverage 40,9 % (URFD 25,9 %, trong đó cam1 trần nhà 3,5 %; GMDCSA24 53,1 %; Pexels 38,1 %), FPS xử lý 25,9, khung bỏ 17.955 (do `--max-fps 15` trên video 24–30 fps), CPU tiến trình 126 %, RAM đỉnh 326 MB. 25 dự đoán (BED_EDGE 12, BED_EXIT 8, STAND_UP 5) trên video ngã bị bỏ qua vì không thuộc `eval_codes`.
- **ABNORMAL_MOVEMENT = 0 dự đoán là đúng với code hiện tại:** rule này thuộc F23 (chưa làm). 101 FN là mốc trước F23, không phải lỗi ngưỡng.
- **BED_* yếu do thiếu dữ liệu đúng bối cảnh** (datasets.md §5): chỉ 9 clip stock dev, chỉ `pexels-8090735` có ROI riêng; 8 clip còn lại dùng `example.yaml`. Chạy lại `--from-observations` với cột `camera_config` gán `gmdcsa24-subject1.yaml` cho GMDCSA24 Subject 1 (bản manifest sao chép trong scratchpad) cho cùng bảng theo code: ROI không phải nguyên nhân chính trên tập này. Chế độ `--from-observations` chạy 189 video trong vài giây và giữ số liệu FPS/CPU/RAM của lần chạy pose gốc.
- Quan sát theo timeline `frames.jsonl`: (1) mọi clip bắt đầu ở `NO_OBSERVATION` 2–3 s (cần `LYING` giữ 2 s để có trạng thái đầu), trong khi SIT_UP gán ở 0,5–4 s → SIT_UP gần như không thể bắt trên clip stock cắt ngắn; (2) `AT_EDGE` giữ tới hết clip ở `pexels-8090735`, `pexels-4052924` (không lên `STANDING` khi người đứng dậy, chân hay bị cắt khỏi khung hoặc góc thấp) → không có STAND_UP/BED_EXIT; (3) 2 FP BED_EDGE ở `pexels-4052924` (1,0 s, người đang nằm) và `pexels-8860232` (3,2 s, ngồi tựa đầu giường, tối) đều dùng ROI mẫu.

**Đề xuất hiệu chỉnh (F16 không đổi ngưỡng; `config/engine.default.yaml` giữ nguyên):**
1. Trước khi chỉnh ngưỡng: tạo `config/cameras/<clip>.yaml` (ROI đo tay) cho từng clip stock dev, thêm cột `camera_config` cho GMDCSA24 Subject 1–2; chạy lại bằng `--from-observations` (không cần MediaPipe).
2. `posture.standing_hip_above_knee_ratio` (0,8) và `min_duration_s.STANDING` (1,0): kiểm tra trên tập nhóm quay; trên stock, `AT_EDGE` không chuyển `STANDING` dù người đã đứng. Thử 0,6 / 0,7 bằng override camera và so bảng STAND_UP/BED_EXIT.
3. `min_duration_s.LYING` (2,0) cho trạng thái đầu: chỉ ảnh hưởng clip bắt đầu giữa hành động; **không** đề xuất hạ khi chưa có video nhóm quay (bắt đầu từ nằm yên theo evaluation.md §3).
4. ABNORMAL_MOVEMENT: chạy lại eval sau F23; tách URFD cam1 (trần nhà, coverage 3,5 %) khỏi kết luận vì pose gần như không thấy người từ trên xuống.
5. Metric BED_EDGE/STAND_UP/BED_EXIT ở đây chỉ để tham khảo cho tới khi có tập dev nhóm quay (HS §7.3).

**Người sau cần biết:**
- Script sinh `data/eval/manifest.csv`, `truth.csv` vẫn chưa có trong repo (ngoài phạm vi F16, xem mục 8).
- F29 làm `--split test --frozen`; F16 chặn `--split test` với exit 2.
- F23 xong thì chạy `postcare eval --split dev --from-observations ../runs/eval-dev --runs-dir ../runs/eval-dev-f23` để có ABNORMAL_MOVEMENT mà không chạy lại pose.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
