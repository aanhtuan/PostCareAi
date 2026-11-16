# F29 – Đánh giá chính thức và chỉ số realtime/workflow

| Thuộc tính | Giá trị |
|---|---|
| Mã | F29 |
| Trạng thái | Todo |
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

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
