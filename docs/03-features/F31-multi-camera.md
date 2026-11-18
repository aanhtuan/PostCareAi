# F31 – Nhiều camera/giường chạy đồng thời

| Thuộc tính | Giá trị |
|---|---|
| Mã | F31 |
| Trạng thái | Done |
| Ưu tiên | MVP cho R1–R4; phần còn lại Sau MVP |
| Milestone | M4 (R1–R4) / Sau MVP |
| Ước lượng | 3 phiên |
| Phụ thuộc | F06, F17 |
| Nhánh code | A (vision/engine) + B (backend) |
| Nguồn | HS §9.2, §2.2; PDF §18 (tr.18); conflicts C01; QA#13; QA#32 |

> Theo QA#32, R1–R3 (và R4, lệnh khởi động, vì rẻ) được làm ở M4 để demo chung kết chạy cùng lúc A01 (camera live) và A02 (clip phát lại bằng `--video`, theo nhịp thời gian thực). Phần còn lại (nhiều camera cho một giường, nhiều máy, GPU) là **Sau MVP**. Chỉ tuyên bố "hai camera live" khi đã thử hai camera thật trên cùng phần cứng.

## 1. Mục tiêu

Sau khi MVP một giường ổn định, cho phép nhiều giường, mỗi giường một camera, được theo dõi **cùng lúc** trên một máy. Người trực có thể ưu tiên các giường đang có sự kiện thay vì chú ý đều cho mọi luồng camera (HS §2.2, §9.2; PDF §18). Data model và dashboard đã hỗ trợ nhiều giường từ MVP (conflicts C01). Chung kết: A01 camera live + A02 clip, mỗi giường một tiến trình worker (QA#32).

## 2. Phạm vi

**Trong phạm vi (M4)**
- Chạy nhiều tiến trình worker đồng thời, mỗi tiến trình một camera (overview.md mục 1): R1, R2.
- Đo FPS/CPU/RAM/độ trễ khi chạy 1 và 2 worker trên máy demo: R3.
- Lệnh tiện ích khởi động/dừng worker của mọi camera đang hoạt động: R4.

**Ngoài phạm vi** (Sau MVP hoặc không làm)
- Nhiều camera cho **cùng một** giường (cần đổi ràng buộc `cameras.bed_id` unique; chưa có trong nguồn).
- Chạy worker trên nhiều máy, GPU.
- Cấu hình rule theo khu vực (PDF §18; ngoài phạm vi PRD).
- Tự khởi động lại worker đã thoát *(giả định, mục 7)*.

## 3. Yêu cầu chi tiết

- **R1.** Chạy ≥ 2 worker cùng lúc trên một máy, mỗi worker gắn đúng camera và giường của nó: mọi request nội bộ của worker chỉ mang `camera_id` của nó; sự kiện lưu đúng `camera_id`, `bed_id`, `session_id`. *(HS §9.2; PDF §18; QA#32)*
- **R2.** Một worker lỗi, bị dừng hoặc mất nguồn video không ảnh hưởng worker khác và API: chỉ camera đó chuyển `OFFLINE` (heartbeat quá hạn A02, hoặc `source_status` OFFLINE), các giường khác vẫn nhận trạng thái và sự kiện. Launcher không dừng các worker còn lại khi một worker thoát. *(overview.md mục 1; HS §4.1)*
- **R3.** Báo cáo FPS xử lý của mỗi worker, CPU %, RAM, độ trễ ghi sự kiện (`events.created_at − detected_at`) khi chạy 1 và 2 worker (face bật/tắt) trên máy demo, ghi vào `tech-stack.md` mục "Kết quả đo hiệu năng". *(HS §8.2)*
- **R4.** Lệnh `postcare workers` (bọc bằng `make workers`) khởi động một tiến trình `postcare worker` cho mỗi camera đang hoạt động có gắn giường (hoặc danh sách `--camera-id`), cho phép gán clip theo camera (`--video 2=<file>`); Ctrl+C dừng tất cả; chạy được trên Windows và Linux. *(giả định: tên lệnh)*

## 4. Thiết kế liên quan

- **Module / file:**
  - `server/src/postcare/worker/launcher.py` (mới): dựng lệnh, chạy và giám sát tiến trình con. Không import `db`/`api` (import-linter).
  - `server/src/postcare/__main__.py` (mới): `python -m postcare`, để launcher gọi đúng trình thông dịch bằng `sys.executable`.
  - `server/src/postcare/domain/cameras.py`: `worker_camera_ids(db)`.
  - `server/src/postcare/cli/main.py`: lệnh `workers`. `Makefile`: mục `workers`.
- **Worker:** không đổi kiến trúc. Mỗi tiến trình có `WorkerApiClient(camera_id=…)`, engine, adapter MediaPipe, cổng face và nguồn riêng; không chia sẻ trạng thái giữa tiến trình.
- **Dữ liệu:** không đổi (`cameras.bed_id` vẫn unique) ([data-model.md](../02-architecture/data-model.md)).
- **API:** không đổi; API nội bộ đã theo `camera_id` ([api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** không đổi; "Tổng quan" đã hiển thị nhiều giường (F21).
- **Cấu hình:** không thêm ngưỡng; override theo camera qua `cameras.thresholds` (đã có).
- **Dừng tiến trình:** POSIX gửi SIGINT (worker đóng nguồn gọn), quá hạn thì `terminate()` rồi `kill()`. Windows dùng `terminate()` (TerminateProcess), camera chuyển OFFLINE sau khi heartbeat quá hạn (A02). Ctrl+C trong console đã tới mọi tiến trình con cùng nhóm; launcher chỉ chờ rồi dọn phần còn lại.

## 5. Acceptance criteria

- [x] **AC1.** 3 worker (A01–A03) chạy cùng lúc; mỗi sự kiện gắn đúng giường, camera và phiên của nó. *(R1)* — *Kiểm chứng:* `tests/integration/test_multi_worker.py::test_three_workers_events_bound_to_own_bed`; thủ công với 1 camera/clip + 1 clip (mục 10).
- [x] **AC2.** Một worker mất nguồn hoặc chết → chỉ camera đó `OFFLINE`; các giường khác vẫn `ONLINE` và nhận sự kiện. *(R2)* — *Kiểm chứng:* `test_multi_worker.py::test_source_loss_only_affects_own_camera`, `::test_dead_worker_only_own_camera_offline`; `tests/worker/test_launcher.py::test_child_exit_does_not_stop_others`.
- [x] **AC3.** Có bảng FPS/CPU/RAM/độ trễ theo 1 và 2 worker (face bật/tắt) trong `tech-stack.md`, kèm kết luận trung thực về hai camera live. *(R3)* — *Kiểm chứng:* thủ công, reviewer xem bảng.
- [x] **AC4.** `postcare workers` khởi động worker cho mọi camera đang hoạt động có giường (bỏ camera ngừng dùng / chưa gắn giường), gán `--video` đúng camera, dừng tất cả khi Ctrl+C hoặc `stop()`, trên Windows và Linux. *(R4)* — *Kiểm chứng:* `tests/worker/test_launcher.py`, `tests/domain/test_worker_cameras.py`, `tests/test_cli_workers.py`.
- [x] **AC5.** Runbook 2 worker cho chung kết trong `docs/progress/DEMO-PLAN.md`. *(QA#32)* — *Kiểm chứng:* reviewer đọc.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | tích hợp (worker thật + API thật, `FakeFrameSource`, đồng hồ giả) | 3 worker chạy xen kẽ, mỗi worker một chuỗi rời giường | Không sự kiện nào của camera 2/3 nằm ở giường A01; mỗi camera đúng 4 sự kiện engine |
| AC2 | tích hợp | Worker 2 không mở được nguồn | Camera 1, 3 vẫn ONLINE, đủ sự kiện; camera 2 OFFLINE, không có sự kiện engine |
| AC2 | tích hợp | Worker 2 chết giữa chừng (lỗi adapter), heartbeat quá hạn | `mark_offline_cameras` chỉ trả `[2]` |
| AC2, AC4 | tiến trình con thật | Launcher: một con thoát mã 1 | Con còn lại vẫn chạy; `stop()` dừng hết, không còn tiến trình sống |
| AC4 | unit | Dựng lệnh (`sys.executable -m postcare worker --camera-id N [--video]`), parse `--video 2=path` | `--video` cho camera không có trong danh sách → lỗi; chuỗi sai dạng → lỗi |
| AC4 | DB | `worker_camera_ids` | Camera `is_active = false` hoặc không gắn giường không có trong danh sách |
| AC3, AC5 | thủ công | Đo trên i5-10300H; runbook | — |

## 7. Giả định

- *(giả định)* Giữ mô hình 1 camera / giường; tên lệnh `postcare workers` / `make workers`.
- *(giả định)* Launcher không tự khởi động lại worker đã thoát: worker tự thử lại API và nguồn (F06), nên thoát nghĩa là lỗi không tự hết (401/404, thiếu model) cần người sửa.
- *(giả định)* "Camera đang hoạt động" = `cameras.is_active` và có `bed_id` trỏ tới giường đang hoạt động.

## 8. Câu hỏi mở

- Số giường mục tiêu khi mở rộng sau MVP là bao nhiêu? Quyết định cấu hình phần cứng. Không chặn M4: QA#32 chốt chung kết = 1 camera live + 1 clip.

## 9. Kế hoạch triển khai

1. Spec (mục này), trạng thái In progress. Commit `docs(F31)`.
2. Test trước: `server/tests/integration/test_multi_worker.py` (AC1, AC2), `server/tests/worker/test_launcher.py` (AC2, AC4; tiến trình con thật `sys.executable -c …` để kiểm tra dừng trên Windows/Linux), `server/tests/domain/test_worker_cameras.py`, `server/tests/test_cli_workers.py`. Xác nhận đỏ (launcher chưa có → ImportError; test tích hợp nhiều worker có thể xanh sẵn vì worker F06 đã theo `camera_id`, ghi lại). Commit `test(F31)`.
3. Code: `worker/launcher.py` (`WorkerSpec`, `parse_video_args`, `worker_command`, `WorkerLauncher.start/poll/stop/run`), `postcare/__main__.py`, `domain/cameras.py::worker_camera_ids`, lệnh CLI `workers`, `Makefile` mục `workers`. Commit `feat(F31)`.
4. Đo (R3): DB riêng `postcare_f31`, `seed --reset`, API cổng 8031; 1 worker rồi 2 worker (A01 webcam 0 nếu có, nếu không thì clip; A02 clip `--video`), face bật/tắt. Script đo (psutil + `GET /api/v1/cameras/{id}` lấy fps heartbeat + `events.created_at − detected_at`) nằm ngoài repo. Ghi bảng vào `tech-stack.md`.
5. Doc: runbook 2 worker trong `DEMO-PLAN.md`; `dev-setup.md` nếu có mục lệnh worker.
6. `make check` một lần; bằng chứng vào mục 10; trạng thái In review.

- **Migration / endpoint / gen-api-types:** không có.
- **Rủi ro:** CPU 4 nhân / 8 luồng chia cho 2 tiến trình MediaPipe → FPS mỗi worker giảm; đo thật để quyết định. Máy builder có thể không có webcam → dùng clip và ghi rõ.

## 10. Ghi chú bàn giao

2026-11-18, nhánh `feat/F31-multi-worker`.

**Bằng chứng theo AC**
- **AC1:** `tests/integration/test_multi_worker.py::test_three_workers_events_bound_to_own_bed` (3 worker thật, engine thật, API thật, chạy xen kẽ): mỗi camera đúng `SIT_UP, BED_EDGE, STAND_UP, BED_EXIT`, đúng `bed_id`/`session_id`; không sự kiện camera 2/3 ở A01. Thủ công: lượt đo 2–3 worker trên DB `postcare_f31`, sự kiện nằm đúng cặp camera/giường (1→A01, 2→A02, 3→A03).
- **AC2:** `test_source_loss_only_affects_own_camera` (camera 2 không mở được nguồn → chỉ camera 2 OFFLINE, 1 và 3 ONLINE, đủ sự kiện), `test_dead_worker_only_own_camera_offline` (worker 2 chết giữa chừng → `mark_offline_cameras` chỉ trả `[2]`), `tests/worker/test_launcher.py::test_child_exit_does_not_stop_others`, `::test_start_failure_of_one_camera_keeps_others`.
- **AC3:** bảng "Nhiều worker đồng thời (F31, R3)" trong `tech-stack.md`: 1 / 2 / 3 worker, face bật/tắt; mọi cấu hình giữ 15 FPS (trần A03); webcam + clip có face ~46 % CPU máy, ~0.3 GB RAM mỗi worker, ghi sự kiện ≤ ~0.1 s. Chưa thử hai camera thật (chỉ có một webcam), nên chỉ tuyên bố 1 camera trực tiếp + 1 clip.
- **AC4:** `tests/worker/test_launcher.py` (dựng lệnh, parse `--video`, tiến trình con thật: khởi động/dừng hết, buộc dừng con bỏ qua SIGINT, `run()` trả mã lỗi lớn nhất, dọn con đã chạy khi `start()` lỗi giữa chừng), `tests/domain/test_worker_cameras.py`, `tests/test_cli_workers.py`. Smoke thủ công trên Windows: `WorkerLauncher` với worker thật (webcam camera 1 + clip camera 2) → cả hai ONLINE giữa lượt, dừng sau 15 s, mã 0, không còn tiến trình worker nào.
- **AC5:** `DEMO-PLAN.md` mục "Chạy hai worker cho chung kết (F31)"; `dev-setup.md`, `README.md` thêm `make workers`; `scripts/dev.ps1 workers` cho Windows không có make.

**make check** (2026-11-18, một lần): format-check, lint, typecheck, lint-imports, check-api-types xanh; pytest 1277 passed, 1 failed: `tests/test_tooling.py::test_dev_ps1_matches_makefile_targets` (target `workers` mới chưa có trong `scripts/dev.ps1`). Đã thêm task `workers` vào `scripts/dev.ps1` (`-Cameras 1,2 -Videos 2=<file>`), chạy lại `tests/test_tooling.py`: 34 passed. Hai bước còn lại chạy riêng sau đó: vitest (`--maxWorkers=1`) 31 file / 232 test passed, build web xanh.

**Review** (2026-11-18, agent khác): **Đạt**, kèm các sửa nhỏ đã làm (test trước) trên cùng nhánh:
1. Launcher xử lý SIGTERM (POSIX) như Ctrl+C: dừng mọi worker rồi thoát, trả lại handler cũ (`launcher.py`, `_install_sigterm`). Test `test_sigterm_to_launcher_stops_children` (chỉ POSIX, skip trên Windows) và `test_run_restores_sigterm_handler`; xác nhận đỏ rồi xanh trên Linux bằng container `python:3.12-slim` (19 passed), Windows 18 passed + 1 skip.
2. `tech-stack.md`: cột độ trễ ghi "trung vị / max" cho mọi dòng và mọi worker; ghi cách bật/tắt face (`cameras.thresholds.face.enabled`).
3. `DEMO-PLAN.md`: nói rõ phải truyền `CAMERAS="1 2"` cho demo 2 worker; clip không có dấu cách khi dùng `make workers`.
4. `Makefile` help: đường dẫn clip trong `VIDEOS` không được có dấu cách.
5. `postcare.worker.launcher` thêm vào `[tool.mypy] packages` (mypy strict xanh).

Sau review, đã merge `main` mới; `make check` một lần đầy đủ, xanh: lint/format/typecheck/lint-imports/check-api-types OK, pytest 1359 passed + 1 skipped (SIGTERM, Windows), vitest 34 file / 253 test, build web OK.

**Ghi chú cho người sau**
- Test tích hợp nhiều worker xanh ngay khi viết: worker F06 đã theo `camera_id`, không cần sửa worker. Phần code mới chỉ là launcher, `python -m postcare`, `worker_camera_ids`, lệnh `workers`, `make workers`.
- Smoke đầu tiên phát hiện lỗi: `start()` ném lỗi (console cp1252 không in được tiếng Việt) sau khi đã chạy một worker → worker đó mồ côi. Đã sửa (`start()` nằm trong `try/finally` của `run()`), có test `test_run_stops_started_children_when_start_fails_midway`. CLI đã ép stdout UTF-8 nên lệnh `postcare workers` không gặp lỗi này.
- Windows: `python.exe` của venv là trampoline chạy tiến trình Python thật; `terminate()` trampoline cũng dừng tiến trình con (đã kiểm: không còn tiến trình sót). Đo CPU/RAM phải cộng cả tiến trình con.
- Windows dừng bằng TerminateProcess (worker không kịp đóng nguồn gọn); camera chuyển OFFLINE sau ~5 s (A02). Ctrl+C trong console thì worker tự dừng gọn.
- Sau MVP: nhiều camera một giường, nhiều máy/GPU, tự khởi động lại worker.


## 11. Definition of Done

- [x] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [x] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [x] Doc liên quan đã cập nhật cùng PR.
- [x] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
