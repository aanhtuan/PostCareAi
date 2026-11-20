# Câu hỏi làm rõ và quyết định (QA#n)

Đây là 30 câu hỏi đặt ra sau khi đọc đề tài. Người dùng yêu cầu tự đề xuất câu trả lời hợp lý nhất, không vượt phạm vi nguồn. Bảng đã được cập nhật theo HS (xem [conflicts.md](../00-source/conflicts.md)).

- Khi trích dẫn, dùng `QA#n`.
- Câu trả lời có nhãn *(giả định)* là suy luận, chưa có nguồn xác nhận. **Có thể thay đổi** khi người dùng quyết định khác. Khi đổi, cập nhật bảng này và các spec liên quan.

## A. Bối cảnh, thời gian, nhân sự

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#1 | Mục tiêu chính | Prototype dự thi DANANG AI4LIFE 2026, bảng AI for Life (sơ loại → demo vòng trong). Tài liệu Đồ án Chuyên ngành 2 làm sau khi có tài liệu yêu cầu [8] | HS bìa, §8.3; PDF TLTK [8] |
| QA#2 | Deadline | Lộ trình 10 tuần, 5 giai đoạn × 2 tuần | HS §7.3 |
| QA#3 | Nhân sự | Chia 3 nhánh: (A) vision + engine, (B) backend + DB + realtime, (C) frontend + test. Nhóm 2 người thì gộp A+B | PDF §12 (tr.13–14) |

## B. Kinh nghiệm và cách làm

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#4 | Kinh nghiệm lập trình | *(giả định)* Biết lập trình cơ bản, chưa chuyên Computer Vision | — |
| QA#5 | Mức review code AI viết | *(giả định)* Review theo checklist ở mỗi feature; test tự động là bắt buộc ở phần lõi (engine, workflow cảnh báo) | — |
| QA#6 | Dùng nhiều AI tool | `AGENTS.md` là nguồn sự thật duy nhất. Adapter từng tool chỉ trỏ về đó. Tiến độ lưu trong `docs/progress/` | Yêu cầu người dùng |
| QA#7 | Ngôn ngữ | Tên file, biến, code, mã sự kiện: tiếng Anh. Tài liệu, comment giải thích nghiệp vụ, UI: tiếng Việt | Yêu cầu người dùng; PDF §9 |
| QA#8 | Repo và CI | *(giả định)* GitHub + GitHub Actions | — |

## C. Tech stack và kiến trúc

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#9 | Tech stack | Python 3.12 + FastAPI + SQLAlchemy + PostgreSQL; React + TypeScript + Vite + Mantine. Chi tiết: [tech-stack.md](../02-architecture/tech-stack.md) | PDF §10; HS §6.1 (PostgreSQL, MediaPipe) |
| QA#10 | Kiến trúc | Modular monolith chạy trên một máy: tiến trình API + tiến trình worker cho mỗi camera; ranh giới module được kiểm tra tự động | HS §6.1 |
| QA#11 | Kênh realtime | WebSocket. FCM / thông báo di động để sau MVP | PDF bảng tr.10; HS §9.2 |

## D. Phạm vi MVP

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#12 | Phạm vi MVP | Toàn bộ đầu ra của 10 tuần. **Mốc tối thiểu** là chuỗi Body AI → sự kiện → cảnh báo → xác nhận → timeline (hết M2). Face được giới hạn theo chất lượng quan sát | HS §7.3; PDF §12, §17 |
| QA#13 | Số giường / camera | MVP 1 giường, 1 camera. Data model và dashboard hỗ trợ nhiều giường. Chạy nhiều camera đồng thời là F31 (sau MVP) | HS §2.2, §9.2 |
| QA#14 | Các sự kiện | Ngồi dậy, đứng dậy, thay đổi tư thế, ở mép giường, rời giường, quay lại giường, ít/tăng vận động, chuyển động bất thường, biểu hiện khuôn mặt cần kiểm tra; cộng trạng thái nghỉ/hoạt động (chỉ hiển thị) | HS §5.1–5.3 |
| QA#15 | Cấu hình ROI và quản lý | Vẽ polygon bằng cách click lên khung hình camera. Quản lý giường, bệnh nhân, camera, phiên bằng form tối giản | PDF §7.2, §9.1 |

## E. Quy tắc nghiệp vụ

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#16 | Vòng đời cảnh báo | `status`: Chờ tiếp nhận (PENDING) → Đã tiếp nhận (ACKNOWLEDGED) → Đã xử lý (RESOLVED). `outcome`: Xác nhận đúng / Cảnh báo sai / Bệnh nhân an toàn / chưa ghi. Chỉ 1 người được tiếp nhận. Không có timeout hay chuyển tiếp | PDF §5, §9.2, §16; HS §4.2, Hình 3; §9.2 (chuyển tiếp là mở rộng) |
| QA#17 | Mức ưu tiên | 4 mức: Nhật ký (LOG), Thông tin (INFO), Cần chú ý (MEDIUM), Ưu tiên cao (HIGH). *(giả định)* Chỉ MEDIUM và HIGH tạo cảnh báo cần tiếp nhận; HIGH có âm thanh trên trình duyệt | HS §5.4; PDF §7 |
| QA#18 | Đăng nhập và vai trò | Username/password + JWT. *(giả định)* 4 vai trò: NURSE (điều dưỡng), CHARGE_NURSE (phụ trách ca), DOCTOR (chỉ xem), ADMIN (cấu hình). Tài khoản tạo bằng seed | PDF §3, §10.1; HS §2.2 |
| QA#19 | Ca trực | *(giả định)* 3 ca 06:00–14:00, 14:00–22:00, 22:00–06:00, cấu hình được trong DB. Bàn giao ca cho chọn khoảng thời gian tùy ý | HS Hình 3 ("Ca trực: 14:00-22:00") |
| QA#20 | Nhiều người trong khung | *(giả định)* Nhận tối đa 2 người. Người mục tiêu là người có tâm hông trong Bed ROI và liên tục với vị trí trước. Có ≥2 người trong ROI → "Không đủ dữ liệu quan sát" | HS §5.2 ("người mục tiêu"), §8.1, §8.3 |
| QA#21 | Mất quan sát, mất camera | Hiển thị trạng thái riêng. *(giả định)* Mất quan sát kéo dài → sự kiện mức Thông tin; mất camera → cảnh báo mức Cần chú ý | PDF §4.3, §10; HS §7.1 (bảng "Mất quan sát") |
| QA#22 | Ngưỡng | Lưu trong file cấu hình, override được theo camera, không viết cứng trong code. Hiệu chỉnh trên tập dev, **chốt** trước khi chạy tập đánh giá | HS §5.5, §8.2 |

## F. Môi trường chạy và deploy

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#23 | Máy dev | Windows và Linux; chỉ CPU; Python chạy native; Docker không bắt buộc | HS §7.2; PDF §12 |
| QA#24 | Camera | Smartphone (DroidCam / IP Webcam) hoặc webcam; tripod hoặc giá có tay vươn, ngàm khóa; quay chéo từ trên xuống; vị trí chốt qua thử nghiệm. Hỗ trợ thêm file video | HS §4.1, §4.2; PDF §12 |
| QA#25 | Deploy | Chạy local trên 1 laptop; thiết bị khác truy cập dashboard qua LAN. Không dùng cloud | HS §7.2 |
| QA#26 | Thiết bị xem dashboard | *(giả định)* Laptop là chính; tablet (≥768px) dùng được | — |

## G. Dữ liệu và kiểm thử

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#27 | Dữ liệu test | Nhóm tự quay với người trưởng thành tự nguyện, có quyền sử dụng; ground truth theo thời gian; chia dev/test theo video (và theo người/phiên khi có thể) | HS §7.2, §8.1 |
| QA#28 | Mức test phần mềm | Bắt buộc unit test cho engine, API test cho backend, component test cho UI quan trọng; 1 test E2E cho kịch bản demo chính | HS §8; PDF §13 |
| QA#29 | Lưu ảnh/video | Không lưu ảnh hay video trong vận hành; API chỉ giữ khung mới nhất trong RAM. Video test chỉ lưu khi có quyền sử dụng, đặt ngoài git (`data/`) | HS §3, §6.3; PDF §10, §11 |

## H. Khác

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#30 | Tài liệu đầu ra | Theo cấu trúc `docs/` ở [AGENTS.md](../../AGENTS.md); báo cáo metric sinh tự động ở `reports/` | Yêu cầu người dùng; HS §8.2 |

## I. Quyết định bổ sung ngày 17/11/2026

Các quyết định dưới đây có sau khi nhóm đề xuất mở rộng (đã gộp vào [pitch-and-evidence.md](pitch-and-evidence.md) và [DEMO-PLAN.md](../progress/DEMO-PLAN.md)). Bản gốc của hai đề xuất (`POSTCARE-AI-MASTER-SPEC.md`, viết tắt "MS", và `PostCare-AI-Tong-hop.md`) được lưu trong lịch sử git ở commit `fc5a2bf`: `git show fc5a2bf:POSTCARE-AI-MASTER-SPEC.md`. Chúng thay thế phần tương ứng của các QA ở trên khi có khác biệt.

| # | Câu hỏi | Quyết định | Nguồn |
|---|---|---|---|
| QA#31 | Người nhà | Thêm vai trò `FAMILY` vào phạm vi chính. Người nhà chỉ xem đúng phiên của người thân, ở mức đã được chia sẻ, có cấp/thu hồi quyền và audit. Chấp thuận quan sát khác chấp thuận chia sẻ. Spec: F36 | Yêu cầu người dùng (2026-11-17); đề xuất nhóm |
| QA#32 | Số camera trong demo | Chung kết: một camera live (A01) và một clip phát lại (A02) chạy cùng lúc qua cùng pipeline, mỗi giường một tiến trình worker. Làm F31 R1–R3. Chỉ tuyên bố hai camera live khi đã thử thật. Thay một phần QA#13 | Yêu cầu người dùng (2026-11-17) |
| QA#33 | Dữ liệu ngoài | Trước khi nhóm tự quay, dùng dataset và stock footage có giấy phép phù hợp (xem [datasets.md](../04-guides/datasets.md)). Kết quả trên dữ liệu ngoài phải ghi nguồn nhãn. Nguồn cấm trình chiếu chỉ dùng nội bộ. Bổ sung QA#27 | Yêu cầu người dùng (2026-11-17) |
| QA#34 | PostgreSQL trên máy dev | Chạy PostgreSQL 16 bằng Docker (xem [dev-setup.md](../04-guides/dev-setup.md)). Thay câu "Docker không bắt buộc" của QA#23 cho máy dev Windows | Yêu cầu người dùng (2026-11-17) |
| QA#35 | Model pose | MediaPipe Pose là model chính. Chọn biến thể Lite / Full / Heavy bằng benchmark trên máy dev (CPU). MediaPipe Python trên Windows không có GPU, nên GPU delegate qua WSL2 là phương án tăng tốc. RTMPose (ONNX Runtime CUDA) chỉ là adapter dự phòng. Không dùng MoveNet | Yêu cầu người dùng (2026-11-17); PDF §6; HS §5.5; ADR-0003 |
| QA#36 | Xóa danh mục | Chỉ xóa mềm (`is_active = false`), có khôi phục. Bản ghi đã xóa vẫn giữ lịch sử, timeline, audit. Quản lý gồm giường, bệnh nhân, camera (F03), tài khoản (F35, nay là MVP), khu vực và ca trực (F37), chuyển bệnh nhân giữa giường (F04) | Yêu cầu người dùng (2026-11-17) |
| QA#37 | Hai loại độ trễ | "Độ trễ phát hiện" tính từ lúc hành động tới lúc sự kiện hiện trên màn hình, đã gồm `min_duration`. "Delivery latency" (A07, < 1 giây) chỉ tính từ lúc lưu DB tới lúc web nhận. Báo cáo ghi riêng hai số | evaluation.md; đề xuất nhóm |
| QA#38 | Dòng miễn trừ trên giao diện | Bỏ khỏi UI: dòng "Bản thử nghiệm - dữ liệu mô phỏng. Công cụ hỗ trợ quan sát…" (chân menu, trang đăng nhập), ghi chú "Timeline là nguồn tham khảo…", "Video gốc chỉ dùng trong môi trường thử nghiệm", gợi ý "Chỉ dùng mã thử nghiệm…". Giới hạn sử dụng (PRD §9) vẫn nêu trong tài liệu, slide và khi trình bày. Nhãn "Đang nghỉ - dữ liệu tham khảo" giữ nguyên vì là quy tắc ngôn ngữ (không phân loại ngủ/tỉnh) | Yêu cầu người dùng (2026-11-20) |

## Danh sách giả định kỹ thuật dùng chung

Các giá trị dưới đây đều là *(giả định)*. Chúng nằm trong file cấu hình, có thể chỉnh sau khi đo thực tế.

| Mã | Giả định | Dùng ở |
|---|---|---|
| A01 | Debounce: cùng code, cùng phiên không lặp trong 60 giây | F15 |
| A02 | Heartbeat worker 2 giây; quá 5 giây không có heartbeat → camera offline | F06, F17 |
| A03 | Worker gửi JPEG xem trực tiếp ~5 fps; giới hạn FPS xử lý 15 | F05, F06 |
| A04 | PoseLandmarker `num_poses = 2` | F11, F13 |
| A05 | Vùng đầu ≥ 80 px mới chạy Face Landmarker; cắt vùng đầu trước khi chạy; face chạy mỗi 2 frame | F25 |
| A06 | Tolerance khi khớp với ground truth: thời điểm dự đoán trong `[start − 1 s, end + 3 s]` | F16 |
| A07 | Mục tiêu hiệu năng: ≥ 10 FPS pose trên CPU ở 720p; delivery latency < 1 giây trong LAN | F11, F18, F29 |
| A08 | Chế độ hiển thị mặc định là "Làm mờ khuôn mặt" | F28 |
| A09 | Không dùng HTTPS cho prototype (chỉ chạy trong LAN) | F02, F18 |
| A10 | JWT hết hạn sau 8 giờ (bằng một ca) | F02 |
| A11 | STAND_UP và RETURN_TO_BED mức Thông tin; ACTIVITY_* mức Nhật ký; OBSERVATION_LOST mức Thông tin; CAMERA_OFFLINE mức Cần chú ý | F15, F17, F23 |
| A12 | Ánh xạ thẻ giường: có cảnh báo PENDING → "Cảnh báo mới"; có cảnh báo ACKNOWLEDGED chưa xử lý hoặc đang "Không đủ dữ liệu quan sát" → "Cần kiểm tra"; còn lại → "Đang theo dõi" | F21 |
| A13 | GNU Make cài trên Windows qua `winget` hoặc `choco`, hoặc bản zip ezwinports có kiểm tra checksum khi không có winget; Node 24 LTS (nếu chưa là LTS thì dùng 22 LTS) | F00 |
| A14 | DroidCam / IP Webcam cung cấp URL MJPEG mà OpenCV đọc được | F05 |
| A15 | Trang bàn giao ca in được bằng print CSS | F24 |
