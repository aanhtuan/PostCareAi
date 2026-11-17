# PRD: PostCare AI

**Phiên bản:** 0.1 (dự thi DANANG AI4LIFE 2026) · **Nguồn:** [HS](../00-source/ho-so-so-loai-2026.md) > [PDF](../00-source/de-tai.md) > [QA](qa-decisions.md)

## 1. Tóm tắt

PostCare AI là hệ thống phần mềm hỗ trợ quan sát bệnh nhân hậu phẫu bằng camera và AI. Video được chuyển thành **sự kiện có thời gian, mức ưu tiên và trạng thái xử lý**. Nhân viên y tế nhận cảnh báo, kiểm tra thực tế và xác nhận trên giao diện tiếng Việt (HS §1).

Hệ thống dùng MediaPipe Pose Landmarker và Face Landmarker đã huấn luyện sẵn và **không thay đổi trọng số**. Phần giá trị nằm ở Event Detection Engine, workflow cảnh báo, timeline và kiểm thử (HS §1, §5.5; PDF §1).

> **Định vị:** công cụ hỗ trợ quan sát. AI phát hiện và ưu tiên tình huống cần chú ý. Nhân viên y tế kiểm tra thực tế và quyết định chuyên môn (PDF §1; HS §9.1).

## 2. Bài toán

- Điều dưỡng không thể quan sát liên tục nhiều giờ, nhất là khi phụ trách nhiều giường (PDF §2; HS §2.1).
- Camera thường chỉ chuyển vị trí quan sát: người dùng vẫn phải nhìn màn hình, và tìm lại sự kiện trong video dài tốn thời gian (PDF §2; HS §2.1).
- Cần một lớp phần mềm biến video liên tục thành thông tin ngắn gọn, có cấu trúc, có người chịu trách nhiệm xử lý (PDF §2; HS §3).

## 3. Người dùng và vai trò

| Vai trò | Code | Nhu cầu | Quyền | Nguồn |
|---|---|---|---|---|
| Điều dưỡng / nhân viên y tế | `NURSE` | Biết giường nào có sự kiện, lúc nào, mức ưu tiên, đã có ai nhận chưa; tiếp nhận và ghi kết quả | Xem mọi màn hình; thao tác cảnh báo; mở/đóng phiên | PDF §3; HS §2.2 |
| Phụ trách ca / quản lý khu vực | `CHARGE_NURSE` | Tổng quan nhiều giường, cảnh báo tồn đọng, lịch sử, bàn giao ca | Như NURSE + đổi chế độ hiển thị | PDF §3; HS §2.2 |
| Bác sĩ / người có thẩm quyền | `DOCTOR` | Tra cứu timeline như nguồn tham khảo | **Chỉ đọc** | PDF §3; HS §2.2 |
| Quản trị | `ADMIN` | Cấu hình giường, bệnh nhân, camera, ROI, ngưỡng, khu vực, ca trực, tài khoản | Toàn quyền cấu hình | *(giả định)*; PDF §9.1 (màn hình cấu hình); QA#36 |
| Người nhà | `FAMILY` | Biết trạng thái và diễn biến của đúng người thân khi không ở cạnh giường | **Chỉ xem** phiên được cấp quyền, ở mức chia sẻ đã được đồng ý (thông tin hoặc skeleton). Không thấy giường khác, không thao tác cảnh báo | QA#31; F36 |

Bệnh nhân là người được quan sát, **không** phải người dùng. Họ được gắn với hệ thống qua giường và phiên theo dõi, không nhận diện bằng khuôn mặt (PDF §4.2). Chấp thuận cho nhân viên quan sát khác với chấp thuận chia sẻ cho người nhà (QA#31).

## 4. User story chính

| ID | Là… | Tôi muốn… | Để… | Feature |
|---|---|---|---|---|
| US01 | Điều dưỡng | nhận cảnh báo ngay khi bệnh nhân rời vùng giường | đến hỗ trợ kịp thời mà không phải nhìn camera liên tục | F15, F17–F20 |
| US02 | Điều dưỡng | bấm "Đã tiếp nhận" rồi ghi kết quả kiểm tra | mọi người biết cảnh báo đã có người xử lý | F19, F20 |
| US03 | Phụ trách ca | xem tổng quan các giường và cảnh báo tồn đọng | ưu tiên giường đang có sự kiện | F09, F21 |
| US04 | Phụ trách ca | xem tổng hợp theo ca | bàn giao ca nhanh và đủ | F24 |
| US05 | Bác sĩ | xem timeline một phiên | tham khảo diễn biến quan sát được | F22 |
| US06 | Quản trị | vẽ vùng giường trên khung hình và chỉnh ngưỡng | hệ thống hiểu đúng ranh giới giường | F08 |
| US07 | Người dùng | biết khi hệ thống không quan sát đủ | không hiểu nhầm "không có cảnh báo" là "an toàn" | F13, F17, F21 |
| US08 | Phụ trách ca | chuyển sang chế độ chỉ hiển thị skeleton | giảm hình ảnh nhận dạng phải xem | F28 |
| US09 | Nhóm phát triển | đo P/R/F1, cảnh báo sai/giờ, latency trên video mô phỏng | chứng minh hệ thống bằng số liệu | F16, F29 |
| US10 | Người nhà | xem trên điện thoại trạng thái và diễn biến của người thân, trong phạm vi được chia sẻ | yên tâm khi không ở cạnh giường | F36 |
| US11 | Quản trị | thêm, sửa, xóa (mềm) và khôi phục giường, bệnh nhân, camera, khu vực, ca trực, tài khoản | quản lý danh mục mà không cần chạy seed | F03, F35, F37 |
| US12 | Điều dưỡng | chuyển bệnh nhân sang giường khác trong một thao tác | timeline của bệnh nhân không bị đứt | F04 |

## 5. Phạm vi

### 5.1. MVP (10 tuần, HS §7.3)

| Nhóm | Nội dung | Feature |
|---|---|---|
| Nền tảng | Nguồn video (smartphone / webcam / file), Bed ROI, DB, API, đăng nhập, quản lý giường/bệnh nhân/camera, phiên theo dõi, dashboard khung | F00–F09 |
| Body AI | Pose, người mục tiêu, chất lượng quan sát, 7 trạng thái, sự kiện ngồi dậy / đứng dậy / thay đổi tư thế / mép giường / rời giường / quay lại giường, công cụ đánh giá trên tập dev | F10–F16 |
| Event + workflow | Lưu sự kiện, cảnh báo realtime, vòng đời cảnh báo, audit, màn hình Cảnh báo, Tổng quan realtime, Timeline, mức vận động, chuyển động bất thường, Bàn giao ca | F17–F24 |
| Face + hoạt động | Face có điều kiện chất lượng, tín hiệu mắt/lông mày/nheo/mũi-miệng, "Biểu hiện khuôn mặt cần kiểm tra", trạng thái nghỉ/hoạt động (tham khảo) | F25–F27 |
| Đánh giá + demo | Chế độ riêng tư, đánh giá chính thức (P/R/F1, FP/giờ, latency, coverage, FPS/CPU/RAM), chuẩn bị demo | F28–F30 |
| Bổ sung 17/11/2026 | Quản lý tài khoản (F35), khu vực và ca trực (F37), quyền xem của người nhà (F36), hai worker đồng thời cho demo (F31 R1–R3) | F31, F35–F37; QA#31–QA#36 |

**Mốc tối thiểu:** chuỗi Body AI → sự kiện → cảnh báo → xác nhận → timeline (hết M2). Nếu nhánh khuôn mặt chưa ổn định, hệ thống vẫn giữ được giá trị cốt lõi (HS §7.3; PDF §12).

### 5.2. Sau MVP

Theo HS §9.2 và PDF §18:
- F31: nhiều camera/giường chạy đồng thời. Riêng R1–R3 (hai worker trên một máy) được kéo vào demo chung kết (QA#32).
- F32: chuyển tiếp cảnh báo chưa được tiếp nhận.
- F33: thông báo di động.
- F34: dashboard thống kê dài hạn theo ca.
- ~~F35~~: quản lý người dùng trên UI đã chuyển vào MVP (QA#36).

### 5.3. Ngoài phạm vi (không làm)

- Tự train, fine-tune, "AI tự học" từ phản hồi (PDF §4.2, §11, bảng tr.10; HS §5.5).
- Chẩn đoán đau, mất ý thức, biến chứng, nguyên nhân y khoa của chuyển động; phân loại ngủ/tỉnh (PDF §4.2; HS §9.1).
- Nhận diện danh tính bằng khuôn mặt (PDF §4.2).
- Tích hợp HIS, cấu hình rule theo khu vực, cảm biến phi hình ảnh (PDF §18; HS §9.2).
- MMPose/RTMPose, Py-Feat, classifier chuyên biệt (chỉ là hướng dự phòng: PDF §6, §17; HS §5.5). RTMPose chỉ được viết adapter khi benchmark MediaPipe không đạt (QA#35).
- Truy cập của người nhà từ ngoài LAN, xác minh tư cách pháp lý của người đại diện (QA#31; F36).
- Triển khai lâm sàng (HS §6.3; PDF ghi chú cuối).

## 6. Yêu cầu chức năng tổng quát

| ID | Yêu cầu | Nguồn |
|---|---|---|
| FR01 | Nhận video từ smartphone (DroidCam / IP Webcam), webcam hoặc file; theo dõi trạng thái kết nối | HS §4.2, §6.1; PDF §10 |
| FR02 | Cấu hình Bed ROI dạng polygon cho từng camera | PDF §7.2; HS §5.2 |
| FR03 | Trích xuất 33 landmark cơ thể; face landmarks/blendshapes chỉ khi mặt đủ rõ | PDF §6; HS §4.1, §5.2–5.3 |
| FR04 | Chuẩn hóa output AI thành schema chung qua adapter | PDF §10; HS §6.1 |
| FR05 | State machine 7 trạng thái có thời gian duy trì, hysteresis, confidence | PDF §7; HS §5.4 |
| FR06 | Sinh các sự kiện theo catalog ([event-engine.md](../02-architecture/event-engine.md)), có debounce và mức ưu tiên | HS §5.1–5.4; PDF §7 |
| FR07 | Mất landmark hoặc bị che **không** được coi là rời giường; chất lượng kém → "Không đủ dữ liệu quan sát" | HS §5.2; PDF §4.3, §13.4 |
| FR08 | Lưu sự kiện **trước khi** gửi cập nhật realtime lên dashboard | HS §4.2 |
| FR09 | Vòng đời cảnh báo: Đã tiếp nhận → kết quả (Xác nhận đúng / Cảnh báo sai / Bệnh nhân an toàn) → Đã xử lý; lưu người và thời điểm của mỗi thao tác | PDF §5, §9.2; HS §4.2 |
| FR10 | Timeline tiếng Việt theo phiên; lọc theo giường/thời gian; xem người tiếp nhận | PDF §9.3; HS §4.3 Hình 3 |
| FR11 | Bàn giao ca: tổng hợp sự kiện, cảnh báo đã/chưa xử lý, số lần đổi trạng thái | PDF §9.1; HS §2.2 |
| FR12 | Ba chế độ hiển thị: video gốc / làm mờ khuôn mặt / chỉ skeleton + ROI | PDF §11; HS §6.3 |
| FR13 | Lưu phản hồi "Xác nhận đúng / Cảnh báo sai" để đánh giá cảnh báo sai và hiệu chỉnh rule; **không** tự đưa vào training | PDF §11 |
| FR14 | Công cụ đánh giá trên video mô phỏng có ground truth | PDF §13; HS §8 |

## 7. Yêu cầu phi chức năng

| ID | Nhóm | Yêu cầu | Nguồn |
|---|---|---|---|
| NFR01 | Ngôn ngữ | UI tiếng Việt, mô tả điều quan sát được; tuân thủ danh sách từ cấm ([glossary.md](glossary.md)) | PDF §9.2, §17; HS §4.3, §9.1 |
| NFR02 | Độ tin cậy | Không kết luận từ một frame đơn lẻ | PDF §4.3, §7 |
| NFR03 | Độ bền | Face hỏng không ảnh hưởng body; camera mất kết nối thì tự kết nối lại và báo trạng thái | HS §4.1; PDF §14 |
| NFR04 | Hiệu năng | Chạy ổn định trên phần cứng được công bố, chỉ CPU; báo cáo FPS, CPU/RAM, frame bỏ. *(giả định A07)* ≥10 FPS pose ở 720p, delivery < 1 giây | HS §7.2, §8.2; PDF §13.3 |
| NFR05 | Privacy | Tối thiểu hóa dữ liệu: lưu metadata, không lưu video vận hành, bệnh nhân chỉ có mã thử nghiệm; chỉ dùng dữ liệu mô phỏng có đồng ý | PDF §10–§11; HS §3, §6.3 |
| NFR06 | Bảo mật | Hash mật khẩu, JWT, phân quyền theo vai trò, token riêng cho worker, audit log, chỉ chạy trong LAN *(giả định A09: không HTTPS)* | PDF §10.1; QA#18 |
| NFR07 | Bảo trì | Module có ranh giới rõ; đổi model chỉ cần sửa adapter; ngưỡng trong file cấu hình | PDF §10; HS §6.1 |
| NFR08 | Truy vết | Mọi thay đổi trạng thái cảnh báo/phiên ghi audit log | PDF §5, §10.1 |
| NFR09 | Thiết bị | Một laptop + smartphone/webcam + giá đỡ + mạng nội bộ; GPU là tùy chọn | HS §7.2 |
| NFR10 | Vận hành liên tục | Có thể chạy liên tục (kể cả 24/7) **khi** nguồn điện, mạng, thiết bị ổn định. Prototype không cam kết chỉ tiêu này | HS §1, §9.1 |

## 8. Chỉ số thành công

Đo trên bộ video mô phỏng, theo HS §8.2. **Không đặt trước con số accuracy** (PDF §13).

- Precision, Recall, F1 cho từng loại sự kiện; kèm TP/FP/FN.
- False alerts / giờ.
- Detection latency và delivery latency.
- Coverage / tỷ lệ mất quan sát.
- FPS, CPU/RAM, frame bỏ, cấu hình phần cứng.
- Chỉ số workflow: thời gian tìm và tiếp nhận cảnh báo, tỷ lệ ghi kết quả, tra cứu timeline.
- Demo chính khoảng 1 phút chạy trọn chuỗi (HS §8.3).

## 9. Giới hạn sử dụng (phải nêu trong UI và tài liệu)

- Hỗ trợ quan sát và ưu tiên sự chú ý; **không** chẩn đoán đau, mất ý thức, biến chứng hay nguyên nhân y khoa (HS §9.1).
- Không thay yêu cầu trực 1:1 khi quy trình chuyên môn yêu cầu (HS §1, §9.1).
- Timeline không thay thế hồ sơ bệnh án (PDF §3; HS §2.2).
- Nhánh khuôn mặt nhạy với khoảng cách, góc và ánh sáng. Thiếu dữ liệu mặt **không** được suy ra là bình thường (HS §9.1).
- Điện thoại cá nhân có thể bị lấy lại hoặc bị hệ điều hành gián đoạn. Triển khai thực tế nên dùng camera chuyên dụng (HS §9.1). Dùng điện thoại của người bệnh chỉ khi có đồng ý rõ ràng và quy trình quản lý thiết bị (HS §6.3).
- Triển khai thực tế phải tuân thủ Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15 và Nghị định 356/2025/NĐ-CP. Prototype **chưa** đủ điều kiện triển khai lâm sàng (HS §6.3).

## 10. Ánh xạ feature ↔ nguồn

Xem bảng đầy đủ ở [docs/03-features/README.md](../03-features/README.md).
