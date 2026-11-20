# F30 – Sẵn sàng demo

| Thuộc tính | Giá trị |
|---|---|
| Mã | F30 |
| Trạng thái | Todo |
| Ưu tiên | MVP |
| Milestone | M4 |
| Ước lượng | 3 phiên |
| Phụ thuộc | F20, F21, F22, F24, F27, F28 (cả chuỗi F20–F28) |
| Nhánh code | C (frontend/test) |
| Nguồn | HS §8.3, §4.3 Hình 3, §9.1; PDF §16 (tr.17), §17 (tr.17–18); conflicts C06; QA#28; A12 |

## 1. Mục tiêu

Làm cho buổi demo vòng trong chạy **ổn định và lặp lại được**. Kịch bản chính dài khoảng một phút: người tham gia nằm → ngồi dậy → tới mép giường → đứng lên → bước khỏi ROI; dashboard cập nhật từng trạng thái, tạo cảnh báo ưu tiên cao lúc rời giường; người đóng vai điều dưỡng tiếp nhận, ghi kết quả, xử lý, rồi mở lịch sử để thấy cả chuỗi đã được lưu (HS §8.3; PDF §16). Kịch bản phụ theo HS là các tình huống dễ gây nhầm; hệ thống phải tránh sự kiện sai và chuyển sang "Không đủ dữ liệu quan sát" khi chất lượng không đủ (HS §8.3; conflicts C06). Feature gồm dữ liệu demo, phương án dự phòng phát lại video, test E2E và runbook.

## 2. Phạm vi

**Trong phạm vi**
- `make demo-seed`: dữ liệu demo theo Hình 3 HS.
- Worker phát lại file video như một camera (`--source file --realtime`).
- Test E2E Playwright cho kịch bản chính (`make e2e`).
- Kiểm chứng kịch bản phụ trên video đã quay.
- `docs/04-guides/demo-runbook.md`.
- Diễn tập 3 lần.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Tính năng mới của dashboard, cảnh báo, timeline (đã có ở F20–F24).
- Kịch bản demo khuôn mặt và privacy của PDF §16: chỉ là phần tùy chọn trong runbook; đã kiểm chứng ở F26, F28 (conflicts C06).
- Số liệu đánh giá chính thức (→ F29).
- Chạy nhiều camera thật cùng lúc (→ F31).

## 3. Yêu cầu chi tiết

- **R1.** `make demo-seed` tạo trạng thái giống Hình 3 HS: *(HS §4.3 Hình 3; PDF §16; A12)*
  - A01: có bệnh nhân mã thử nghiệm, phiên đang mở, camera thật/dự phòng; không có cảnh báo → "Đang theo dõi".
  - A02: phiên đang mở, có một cảnh báo `ACKNOWLEDGED` chưa xử lý → "Cần kiểm tra".
  - A03: phiên đang mở, có chuỗi sự kiện mẫu "Ngồi dậy → Ở mép giường → Rời khỏi vùng giường" và cảnh báo `BED_EXIT` `PENDING` → "Cảnh báo mới".
- **R2.** Dữ liệu mẫu có thời điểm tính lùi từ lúc chạy lệnh (vài phút trước), để nằm trong ca hiện tại và "Diễn biến gần đây". Mỗi giường A02, A03 có một camera nguồn `FILE` (vì `events.camera_id` bắt buộc). Trạng thái camera không bị giả lập "online". *(data-model.md; giả định)*
- **R3.** `make demo-seed` làm mới dữ liệu demo từ đầu (`alembic downgrade base` → `upgrade head` → `db-seed` → dữ liệu demo). Lệnh chỉ chạy khi có biến `DEMO_RESET=1` để tránh xóa nhầm DB đang dùng. *(giả định: data-model.md cấm xóa cứng sự kiện trong vận hành; DB demo được tạo lại thay vì xóa từng dòng)*
- **R4.** Phương án dự phòng: `postcare worker --camera-id N --source file --video <path> --realtime [--loop]` phát lại video đã quay theo đúng nhịp thời gian thật. Đi qua cùng pipeline và API nội bộ như camera; API không phân biệt hai nguồn. Ở chế độ `--realtime`, `ts_ms` = thời điểm bắt đầu phát + thời gian trong video, để timeline hiện giờ thực. *(PDF §12 (tr.13–14); HS §8.3; giả định: tùy chọn `--video`, `--loop` và cách quy đổi thời gian)*
> **Tiến độ R4 (20/11/2026):** đã có `--video` (F06, phát theo nhịp thời gian thật) và `--loop` cho `postcare worker` / `postcare workers` (`make worker … LOOP=1`, `dev.ps1 … -Loop`). Hết file thì đóng nguồn và mở lại từ đầu; engine, adapter MediaPipe tạo mới mỗi vòng. Test: `tests/worker/test_worker_loop.py::test_loop_reopens_file_source_when_it_ends`, `::test_without_loop_ended_source_is_not_reopened`. Kiểm tay: clip GMDCSA24 Subject 1 Fall 12, 40 s, 4 vòng, mỗi vòng sinh lại sự kiện, camera giữ ONLINE. Phần còn lại của R4 (quy đổi `ts_ms` theo giờ thực) chưa làm.

- **R5.** Test E2E Playwright chạy kịch bản chính HS §8.3. *(HS §8.3; QA#28; testing.md mục 1)* Các bước:
  1. Đăng nhập NURSE.
  2. "Tổng quan" hiện A01 "Đang theo dõi".
  3. Worker phát lại video kịch bản chính.
  4. Timeline/Diễn biến gần đây lần lượt hiện "Bệnh nhân ngồi dậy", "Bệnh nhân đang ở mép giường", "Bệnh nhân đứng dậy".
  5. Cảnh báo ưu tiên cao "Bệnh nhân rời khỏi vùng giường" tự hiện, không cần tải lại trang.
  6. Bấm [Đã tiếp nhận] → ghi [Xác nhận đúng] kèm ghi chú → [Đã xử lý].
  7. Mở "Lịch sử theo dõi": đủ chuỗi sự kiện và thao tác, đúng thứ tự, có giờ `HH:mm:ss`, có tên người tiếp nhận.
- **R6.** Để E2E chạy được khi máy không có model hoặc video, worker hỗ trợ phát lại fixture observation (chỉ toạ độ) của chính video kịch bản chính, qua `FakePoseAdapter`. *(testing.md mục 1, 2; giả định)*
- **R7.** Trong E2E, các trang đã mở không chứa từ cấm và không hiện mã nội bộ (`BED_EXIT`…). *(PDF §9.2–9.3; glossary.md)*
- **R8.** Kịch bản phụ trên video đã quay: thay đổi tư thế trên giường (S02), người đi ngang (S08), che camera một phần (S10), mặt quay đi (S12). Không có sự kiện mức `MEDIUM`/`HIGH` nào ngoài kỳ vọng ở [evaluation.md](../04-guides/evaluation.md) mục 3. Khi chất lượng không đủ, trạng thái chuyển sang `NO_OBSERVATION`. *(HS §8.3, §8.1)*
- **R9.** `docs/04-guides/demo-runbook.md` (tạo trong feature này) gồm: *(PDF §16, §17; HS §4.1, §8.3, §9.1)*
  - checklist thiết bị: laptop, điện thoại, tripod có ngàm khóa, dây chống rơi, sạc;
  - mạng: router riêng, IP laptop, URL DroidCam/IP Webcam;
  - camera: vị trí đã chốt theo camera-setup.md, vẽ lại ROI nếu lệch;
  - lệnh khởi động theo thứ tự (`make demo-seed`, API, web, worker);
  - kịch bản chính kèm lời thoại; kịch bản phụ; phần tùy chọn khuôn mặt và privacy;
  - câu nhấn mạnh "tín hiệu quan sát, không phải chẩn đoán";
  - xử lý sự cố: camera rớt → chuyển sang phát lại video; worker lỗi; Wi-Fi; DB.
- **R10.** Diễn tập trọn kịch bản chính 3 lần liên tiếp không lỗi, ghi kết quả vào mục 10. *(ROADMAP M4 "demo chạy ổn 3 lần")*

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/domain/demo_seed.py` + lệnh `postcare demo-seed` trong `server/src/postcare/cli.py`; target `demo-seed`, `e2e` trong `Makefile`.
  - `server/src/postcare/vision/camera/` (nguồn file, nhịp `--realtime`, `--loop`), `server/src/postcare/worker/` (tùy chọn CLI, phát lại fixture observation).
  - `web/e2e/demo-main.spec.ts`, `web/playwright.config.ts`.
  - `server/tests/fixtures/demo_main.jsonl` (+ `.expected.json`), chỉ chứa toạ độ.
  - `docs/04-guides/demo-runbook.md`.
- **Dữ liệu:** dùng các bảng `patients`, `beds`, `cameras`, `monitoring_sessions`, `events`, `alerts`, `audit_logs` ([data-model.md](../02-architecture/data-model.md)). Không có bảng mới.
- **API:** không có endpoint mới. E2E dùng API công khai và WS ([api-conventions.md](../02-architecture/api-conventions.md)); worker dùng API nội bộ.
- **UI:** không có màn hình mới. Có thể thêm `data-testid` cho Playwright.
- **Cấu hình:** không thêm khóa ngưỡng. Override camera cho video demo đặt ở `config/cameras/<setup>.yaml` (evaluation.md mục 4).

## 5. Acceptance criteria

- [ ] **AC1.** `make demo-seed` (với `DEMO_RESET=1`) cho "Tổng quan" giống Hình 3: A01 "Đang theo dõi", A02 "Cần kiểm tra", A03 "Cảnh báo mới". *(HS Hình 3; A12)* — *Kiểm chứng:* API test `test_demo_seed_overview_matches_figure3` gọi `GET /api/v1/overview`; chạy lệnh thiếu `DEMO_RESET=1` → thoát với thông báo, không đổi DB.
- [ ] **AC2.** Worker phát lại video đã quay như một camera (`--source file --realtime`): camera "online", sự kiện đến API theo nhịp thời gian thật. *(PDF §12; HS §8.3)* — *Kiểm chứng:* test tích hợp `test_worker_file_realtime_paces_frames` (video ngắn tổng hợp, kiểm tra thời gian chạy ≈ thời lượng video và `ts_ms` tăng theo giờ thực); thủ công với video kịch bản chính.
- [ ] **AC3.** `make e2e` xanh với kịch bản chính HS §8.3 (R5): phát lại video (hoặc fixture observation của video đó) → cảnh báo "Bệnh nhân rời khỏi vùng giường" → tiếp nhận → ghi kết quả → xử lý → lịch sử đủ chuỗi. Các trang không có từ cấm hay mã nội bộ. *(HS §8.3; QA#28)* — *Kiểm chứng:* `web/e2e/demo-main.spec.ts`.
- [ ] **AC4.** Có `docs/04-guides/demo-runbook.md` đủ các mục ở R9. *(PDF §16, §17)* — *Kiểm chứng:* reviewer đối chiếu checklist R9; một thành viên không viết runbook làm theo được từ đầu đến cuối.
- [ ] **AC5.** Kịch bản phụ (S02, S08, S10, S12) trên video đã quay không sinh cảnh báo sai; thiếu chất lượng thì chuyển "Không đủ dữ liệu quan sát". *(HS §8.3)* — *Kiểm chứng:* `postcare replay` từng video, `events.jsonl` không có `MEDIUM`/`HIGH` ngoài kỳ vọng; test regression trên fixture của các video này.
- [ ] **AC6.** Diễn tập kịch bản chính 3 lần liên tiếp thành công với camera thật (hoặc phương án dự phòng), ghi ngày, thiết bị, sự cố vào mục 10. *(ROADMAP M4)* — *Kiểm chứng:* thủ công.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API (DB test) | `test_demo_seed_overview_matches_figure3` | Thiếu `DEMO_RESET=1` → không chạy |
| AC2 | tích hợp | `test_worker_file_realtime_paces_frames`, `test_worker_file_loop` | File không tồn tại → worker báo `offline`, không crash |
| AC3 | E2E (Playwright) | `demo-main.spec.ts` | Không có BED_EXIT trước bước đứng dậy; không có từ cấm trên trang |
| AC4 | thủ công | Đọc runbook theo checklist R9 | — |
| AC5 | replay + regression | Fixture S02, S08, S10, S12 + `.expected.json` | Đây chính là các ca âm tính (HS §8.3) |
| AC6 | thủ công | 3 lần diễn tập | — |

## 7. Giả định

- *(giả định A12)* Ánh xạ trạng thái thẻ giường dùng để dựng dữ liệu Hình 3.
- *(giả định)* `make demo-seed` tạo lại DB từ đầu và yêu cầu `DEMO_RESET=1`.
- *(giả định)* Dữ liệu mẫu có thời điểm tính lùi từ lúc chạy; camera A02, A03 là nguồn `FILE`, không giả lập "online".
- *(giả định)* Tùy chọn `--video`, `--loop`; quy đổi `ts_ms` theo giờ thực ở chế độ `--realtime`.
- *(giả định)* E2E chạy được bằng fixture observation khi thiếu model/video.
- *(giả định)* Kết quả ghi ở bước 6 của E2E là "Xác nhận đúng".

## 8. Câu hỏi mở

- Khi demo, A02 và A03 không có worker nên thẻ giường sẽ hiện camera chưa kết nối. Có chấp nhận như vậy, hay chạy thêm worker phát lại video lặp cho A02/A03 (cần F31 nếu chạy đồng thời nhiều worker)? **Không chặn**; mặc định chấp nhận và giải thích trong runbook.
- Kịch bản phụ có cần chạy trực tiếp bằng camera trong buổi demo, hay chỉ trình bày kết quả trên video đã quay? **Không chặn**; mặc định video đã quay, camera trực tiếp là tùy chọn.

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
