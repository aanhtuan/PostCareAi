# F29 – Đánh giá chính thức và chỉ số realtime/workflow

| Thuộc tính | Giá trị |
|---|---|
| Mã | F29 |
| Trạng thái | In progress |
| Ưu tiên | MVP |
| Milestone | M4 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F16, F18, F19, F26 |
| Nhánh code | A (vision/engine) + B (backend) |
| Nguồn | HS §8.1, §8.2, §7.3; PDF §11 (tr.13), §13 (tr.14–15); conflicts C07; ADR-0008; A07 |

## 1. Mục tiêu

Chạy **lần đánh giá chính thức** trên tập test với ngưỡng **đã chốt**, rồi xuất báo cáo cuối có đủ bộ chỉ số của HS §8.2: TP/FP/FN, Precision/Recall/F1, false alerts/giờ, detection và delivery latency, coverage, FPS/CPU/RAM/frame bỏ, chỉ số workflow, kèm thời lượng video, điều kiện camera và phần cứng. Feature này bổ sung cho công cụ eval trên tập dev (F16) ba phần: cơ chế chốt bằng `config_hash`, đo delivery latency qua WebSocket, và chỉ số workflow lấy từ DB (ADR-0008; conflicts C07).

## 2. Phạm vi

**Trong phạm vi**
- Chốt ngưỡng: `reports/frozen-config.txt` + `postcare eval --split test --frozen <hash>`.
- Đo delivery latency: client WS ghi thời điểm nhận `event.created`.
- Chỉ số workflow từ bảng `alerts`: thời gian chờ → tiếp nhận → xử lý, tỷ lệ có ghi kết quả, tỷ lệ "Cảnh báo sai".
- Báo cáo `reports/final-eval.md` theo mẫu ở [evaluation.md](../04-guides/evaluation.md) mục 7, cộng delivery latency và workflow.
- Điền bảng hiệu năng trong `tech-stack.md`.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Metric P/R/F1, FP/giờ, detection latency, coverage, FPS, CPU/RAM trên tập dev (đã có ở F16; F29 dùng lại).
- Quay video và gán ground truth (task không phải code trong `TASKS.md`).
- Đặt trước chỉ tiêu accuracy (không làm; PDF §13).
- Dashboard thống kê dài hạn (→ F34).

## 3. Yêu cầu chi tiết

- **R1.** Chốt ngưỡng: ghi `config_hash` của cấu hình đã hợp nhất (mặc định + override camera dùng khi quay) vào `reports/frozen-config.txt` và commit **trước** khi chạy tập test. *(HS §8.2; evaluation.md mục 6)*
- **R2.** `postcare eval --split test --frozen <hash>` từ chối chạy (exit code ≠ 0, thông báo rõ) khi: hash của cấu hình hiện tại khác `<hash>`, hoặc có sự kiện trong `runs/` mang `config_hash` khác. `--split test` mà thiếu `--frozen` cũng bị từ chối. *(HS §8.2; ADR-0008; giả định: chặn luôn trường hợp thiếu `--frozen`)*
- **R3.** Delivery latency = thời điểm client WS nhận `event.created` − `events.created_at`. Báo trung vị và p90, kèm số mẫu. *(HS §8.2; PDF §13.3; ADR-0002; evaluation.md mục 5)*
- **R4.** Lệnh đo `postcare measure-delivery --duration <s> --out runs/<id>/delivery.jsonl` kết nối `/api/v1/ws?token=`, ghi mỗi `event.created` nhận được. Luồng sự kiện lấy từ worker đang chạy với camera thật hoặc file video. Client đo chạy **trên cùng máy với API** để không lệch đồng hồ. *(giả định: tên lệnh và cách đo; giới hạn ghi trong báo cáo: chưa gồm độ trễ Wi-Fi tới thiết bị khác)*
- **R5.** Chỉ số workflow tính bằng SQL aggregation trên `alerts` trong một khoảng thời gian: *(HS §8.2; PDF §11; evaluation.md mục 5)*
  - thời gian chờ tiếp nhận `acknowledged_at − created_at` (trung vị, p90);
  - thời gian xử lý `resolved_at − acknowledged_at` (trung vị, p90);
  - tỷ lệ cảnh báo đã xử lý có `outcome ≠ null`;
  - tỷ lệ `outcome = FALSE_ALARM`;
  - số cảnh báo còn PENDING / ACKNOWLEDGED cuối khoảng.
- **R6.** Logic workflow đặt ở `domain` (không đặt trong `eval`, vì `eval` không được import `db`). Lệnh `postcare workflow-report --from <ISO> --to <ISO> --out runs/<id>/workflow.json`. *(overview.md mục 3; giả định: tên lệnh)*
- **R7.** Buổi thử workflow thủ công: người đóng vai điều dưỡng tìm cảnh báo, tiếp nhận, ghi kết quả, tra cứu timeline; bấm giờ từng bước và ghi vào báo cáo. *(HS §8.2 "tìm cảnh báo… tra cứu timeline"; PRD §8; giả định cho cách đo)*
- **R8.** `reports/final-eval.md` theo [evaluation.md](../04-guides/evaluation.md) mục 7 và có thêm: delivery latency, workflow (R5, R7), phần cứng, tổng thời lượng video, điều kiện camera, `config_hash` đã chốt, commit code. Lệnh tạo: `postcare eval --split test --frozen <hash> --delivery runs/<id>/delivery.jsonl --workflow runs/<id>/workflow.json --out reports/final-eval.md`. *(HS §8.2; PDF §13; giả định: tên tùy chọn)*
- **R9.** Báo cáo **không** đặt trước con số accuracy; ghi rõ giới hạn (dữ liệu mô phỏng, số người tham gia). *(PDF §13; evaluation.md mục 7)*
- **R10.** Điền bảng "Kết quả đo hiệu năng" trong `tech-stack.md` (FPS, CPU %, RAM MB, face bật/tắt). So sánh với mục tiêu A07 (≥ 10 FPS pose; delivery < 1 giây) nhưng chỉ ghi nhận, không coi là tiêu chí đạt/trượt. *(HS §8.2; A07)*

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/eval/frozen.py`: kiểm tra hash.
  - `server/src/postcare/eval/delivery.py`: client WS đo delivery latency.
  - `server/src/postcare/eval/report.py`: mở rộng báo cáo của F16 với phần delivery và workflow.
  - `server/src/postcare/domain/workflow_metrics.py`: SQL aggregation trên `alerts`.
  - `server/src/postcare/cli.py`: `measure-delivery`, `workflow-report`, tùy chọn `--frozen`, `--delivery`, `--workflow` của `eval`.
  - Artefact: `reports/frozen-config.txt` (commit), `reports/final-eval.md` (commit).
- **Dữ liệu:** đọc `events.created_at`, `events.config_hash`, `alerts.*_at`, `alerts.outcome` ([data-model.md](../02-architecture/data-model.md)). Không có bảng mới.
- **API:** dùng WS `/api/v1/ws?token=` và message `event.created` ([api-conventions.md](../02-architecture/api-conventions.md)). Không có endpoint mới.
- **UI:** không có.
- **Cấu hình:** dùng `config_hash` do engine tính ([event-engine.md](../02-architecture/event-engine.md) mục 6). Không thêm khóa ngưỡng.
- **Thư viện:** client WS dùng `websockets` (thường đã có qua `uvicorn[standard]`). Nếu thêm làm phụ thuộc trực tiếp thì ghi lý do vào [tech-stack.md](../02-architecture/tech-stack.md) *(giả định)*.

## 5. Acceptance criteria

- [ ] **AC1.** `postcare eval --split test --frozen <hash>` từ chối chạy khi cấu hình hoặc sự kiện có hash khác; `--split test` thiếu `--frozen` cũng bị từ chối. *(HS §8.2; ADR-0008)* — *Kiểm chứng:* test `test_eval_test_split_rejects_hash_mismatch`, `test_eval_test_split_requires_frozen`, `test_eval_test_split_runs_with_matching_hash` (dữ liệu tổng hợp nhỏ trong `server/tests/eval/`).
- [ ] **AC2.** Đo được delivery latency (`WS nhận − events.created_at`), báo trung vị và p90. *(HS §8.2; PDF §13.3)* — *Kiểm chứng:* test tích hợp `test_measure_delivery_records_event_created` (TestClient + WS, POST event nội bộ, client ghi được 1 mẫu với latency ≥ 0); chạy thủ công `postcare measure-delivery` khi demo với worker.
- [ ] **AC3.** Chỉ số workflow từ DB: thời gian chờ → tiếp nhận → xử lý (trung vị, p90), tỷ lệ cảnh báo có ghi kết quả, tỷ lệ "Cảnh báo sai". *(HS §8.2; PDF §11)* — *Kiểm chứng:* test domain `test_workflow_metrics_on_seeded_alerts` với dữ liệu cảnh báo mẫu có thời điểm biết trước, so sánh số liệu tính tay.
- [ ] **AC4.** `reports/final-eval.md` có TP/FP/FN, P/R/F1 từng mã, FP/giờ, detection và delivery latency, coverage, FPS/CPU/RAM/frame bỏ, workflow, phần cứng, thời lượng, điều kiện camera, `config_hash`. *(HS §8.2; evaluation.md mục 7)* — *Kiểm chứng:* test `test_final_report_has_required_sections` (kiểm tra đủ tiêu đề và trường); reviewer đối chiếu file thật sau lần chạy chính thức.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit (eval) | `test_eval_test_split_runs_with_matching_hash` | `test_eval_test_split_rejects_hash_mismatch` (sửa 1 ngưỡng → từ chối); `test_eval_test_split_requires_frozen`; một sự kiện trong `runs/` mang hash cũ → từ chối |
| AC2 | tích hợp (API + WS) | `test_measure_delivery_records_event_created`, `test_delivery_stats_median_p90` | Không nhận được sự kiện nào → báo "0 mẫu", không chia cho 0 |
| AC3 | domain (DB test) | `test_workflow_metrics_on_seeded_alerts` | Cảnh báo chưa tiếp nhận không tính vào thời gian chờ; `outcome = null` tính vào tỷ lệ "chưa ghi kết quả" |
| AC4 | unit (report) | `test_final_report_has_required_sections` | Thiếu file delivery → báo cáo ghi "chưa đo", không bịa số |
| — | thủ công | Chạy đủ quy trình evaluation.md mục 6 trên tập test; buổi thử workflow (R7) | — |

## 7. Giả định

- *(giả định)* Thiếu `--frozen` với tập test cũng bị từ chối.
- *(giả định)* Tên lệnh `measure-delivery`, `workflow-report` và tùy chọn `--delivery`, `--workflow`, `--out`.
- *(giả định)* Client đo delivery chạy trên cùng máy với API; báo cáo ghi rõ giới hạn này.
- *(giả định)* Tập test dùng **một** cấu hình camera đã chốt (camera-setup.md mục 4), nên chỉ có một `config_hash`.
- *(giả định A07)* Mục tiêu hiệu năng chỉ để tham chiếu.

## 8. Câu hỏi mở

- Nếu tập test có nhiều cấu hình camera (nhiều override) thì sẽ có nhiều `config_hash`. Khi đó `--frozen` nhận nhiều giá trị, hay `frozen-config.txt` ghi theo từng setup? **Không chặn**; mặc định một setup.
- Có cần đo delivery latency trên thiết bị thứ hai qua Wi-Fi (cần đồng bộ đồng hồ) không? **Không chặn**; mặc định đo trên cùng máy.

## 9. Kế hoạch triển khai

Lập 2026-11-18 (builder F29). Phụ thuộc F16, F18, F19, F26 đều Done.

**Khảo sát.** `postcare eval` (F16) đã có replay theo split, ghép truth, metric, báo cáo `.local.md/.json`, và chặn cứng `--split test`. `EngineConfig.config_hash()` bỏ khối `privacy` (F28). WS `/api/v1/ws` phát `event.created` sau commit, payload là `EventOut` có `created_at` (đặt bằng `utcnow()` phía Python lúc flush). `websockets` 17 đã có qua `uvicorn[standard]`. `eval` không được import `db`/`api` (import-linter), nên workflow nằm ở `domain`.

**Hash cấu hình so với lần hiệu chỉnh.** Hash hiện tại của `config/engine.default.yaml` là `886768c0eef0c652ed49eef0519e31a8e4423581f6378a29efbbff3023b9f8d1`, khác hash đã chốt ở [calibration-2026-11-18.md](../04-guides/calibration-2026-11-18.md) (`cb7a5ed7…`). So sánh từng khóa (cùng schema hiện tại) cho thấy chỉ khác **`face.head_crop_scale` 1.6 → 2.2** (F25, merge sau lần hiệu chỉnh) và `privacy.head_box_scale` 1.8 → 2.4 (F28, không tính vào hash). Đặt lại `head_crop_scale = 1.6` cho đúng `cb7a5ed7…`. Mọi khóa body/movement/rest/observation không đổi. `postcare eval` chạy replay **không** bật face (runner không truyền `FaceGate`), nên khóa này không ảnh hưởng sự kiện trên tập test; tập test cũng không có truth cho mã face. Lưu ý trung thực: F25 chọn 2.2 khi đếm khung face `OK` trên 8 clip, trong đó 4 clip thuộc tập test (pexels-6010768, pexels-6010961, mixkit-5457, mixkit-5568). Việc này không chạm metric sự kiện nhưng được ghi ở mục giới hạn của báo cáo. **Quyết định:** chốt hash hiện tại `886768c0…` (đúng cấu hình sẽ demo), không chỉnh bất kỳ ngưỡng nào sau khi xem tập test.

**Thay đổi so với mô tả spec (ghi rõ):**
- Báo cáo do lệnh sinh ra là `reports/final-eval.local.md` + `.local.json` (gitignore, như F16). Bản tổng hợp commit là `docs/04-guides/final-evaluation-2026-11-18.md` (tiếng Việt, số liệu lấy từ báo cáo local). `reports/frozen-config.txt` commit theo R1.
- `eval --out` là tên khác của `--report` (đã có ở F16).
- ROI giường cho `gmd_s3_adl_03` (dòng GMDCSA24 test duy nhất có `SIT_UP`, datasets.md §3.5): vẽ bằng mắt trên 1 khung đầu clip **trước** khi chạy, không xem kết quả; file `config/cameras/gmdcsa24-s3-bed.yaml` với `thresholds: {}` (không đổi hash). Clip stock tập test để trống `camera_config` theo datasets.md §3.5.

**Các bước:**
1. Test trước (không media), xác nhận đỏ, commit `test(F29): …`:
   - `tests/eval/test_frozen.py`: `test_eval_test_split_requires_frozen`, `test_eval_test_split_rejects_hash_mismatch` (biến thể engine config đổi 1 ngưỡng), `test_eval_test_split_rejects_stale_run_events` (events.jsonl trong `--runs-dir` mang hash cũ khi `--reuse`), `test_eval_test_split_rejects_frozen_file_mismatch`, `test_eval_test_split_runs_with_matching_hash`, `test_freeze_writes_frozen_config`.
   - `tests/eval/test_delivery.py`: `test_delivery_stats_median_p90`, `test_delivery_stats_zero_samples`, `test_delivery_record_from_message`.
   - `tests/api/test_measure_delivery.py`: `test_measure_delivery_records_event_created` (TestClient + WS, POST event nội bộ, 1 mẫu latency ≥ 0).
   - `tests/domain/test_workflow_metrics.py`: `test_workflow_metrics_on_seeded_alerts` (thời điểm biết trước, so số tính tay; chưa tiếp nhận không vào thời gian chờ; `outcome = null` vào tỷ lệ chưa ghi; đếm PENDING/ACKNOWLEDGED cuối khoảng), `test_workflow_metrics_empty_range`.
   - `tests/eval/test_final_report.py`: `test_final_report_has_required_sections`, `test_final_report_missing_delivery_says_not_measured`.
2. Code:
   - `eval/frozen.py`: đọc/ghi `reports/frozen-config.txt` (hash, ngày, commit, engine config, camera config); kiểm hash cấu hình hợp nhất của từng dòng test; quét `runs/<video>/events.jsonl` + `run.json` sau khi chạy (và trước khi `--reuse`).
   - `eval/delivery.py`: `DeliverySample`, `sample_from_message`, `delivery_stats`, `read_samples`, client `record_delivery` (websockets, async) + login httpx.
   - `domain/workflow_metrics.py`: `workflow_metrics(db, start, end)` (SQL `count` theo trạng thái/outcome; thời lượng lấy bằng SELECT cột rồi tính phân vị như `eval.metrics.percentile`).
   - `eval/report.py`: `FinalExtras` + `render_final_markdown` (thêm mục chốt cấu hình, delivery, workflow, buổi thử workflow R7 "chưa đo" nếu thiếu, hiệu năng, giới hạn).
   - `cli/main.py`: `eval freeze`, `eval --split test --frozen <hash> [--frozen-file] [--delivery] [--workflow] [--out]`, `measure-delivery`, `workflow-report`.
   - Doc: evaluation.md (§5–§6 lệnh F29), dev-setup.md nếu cần, tech-stack.md (bảng hiệu năng, ghi `websockets` dùng qua uvicorn[standard]).
3. Chạy chính thức: `eval freeze` → commit `reports/frozen-config.txt` → `eval --split test --frozen 886768c0…` (model `full`, `--max-fps 15`) một lần. Delivery: DB `postcare_f29`, API cổng 8029, `postcare simulate` + `measure-delivery` cùng máy; workflow-report trên khoảng đó (cảnh báo tiếp nhận/xử lý bằng script API: chỉ để kiểm công cụ, không phải số đo người dùng). Buổi thử R7 cần người thật: ghi "chưa đo".
4. Viết `docs/04-guides/final-evaluation-2026-11-18.md`; điền §10; `make check` một lần; trạng thái In review.

**Rủi ro:** thời gian replay ~190 video (chạy nền); MediaPipe mất người nằm sàn (đã biết); hash lệch do override camera (kiểm bằng `eval freeze` trước khi chạy).

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
