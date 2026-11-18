# Danh sách feature

Mỗi feature có một spec theo [_TEMPLATE.md](_TEMPLATE.md). Mỗi feature dự kiến làm xong trong 1–3 phiên AI.
- Thứ tự thực hiện và trạng thái tổng: [ROADMAP.md](../progress/ROADMAP.md).
- Ký hiệu nguồn: **HS §x**, **PDF §x (tr.y)**, **QA#n** (xem [00-source/README.md](../00-source/README.md)).
- Nhánh: **A** vision/engine, **B** backend, **C** frontend/test (PDF §12).

| Mã | Tên | Milestone | Ưu tiên | Nhánh | Phụ thuộc | Nguồn chính | Trạng thái |
|---|---|---|---|---|---|---|---|
| [F00](F00-project-skeleton.md) | Khung xương dự án | M0 | MVP | A+B+C | — | Yêu cầu người dùng; HS §6.1 | Done |
| [F01](F01-database-foundation.md) | CSDL và migration nền | M0 | MVP | B | F00 | PDF §10, §10.1; HS §6.2 | Done |
| [F02](F02-auth-roles.md) | Đăng nhập và phân quyền | M0 | MVP | B+C | F01 | PDF §3; HS §2.2; QA#18 | Done |
| [F03](F03-bed-patient-camera-management.md) | Quản lý giường, bệnh nhân, camera | M0 | MVP | B+C | F02 | PDF §4.2, §9.1, §10.1 | Done |
| [F04](F04-monitoring-sessions.md) | Phiên theo dõi | M0 | MVP | B+C | F03 | PDF §4.2, §10.1; HS §6.2 | Done |
| [F05](F05-camera-service.md) | Nguồn video (Camera Service) | M0 | MVP | A | F00 | PDF §10, tr.10; HS §4.2 | Done |
| [F06](F06-worker-backend-link.md) | Kết nối worker với backend | M0 | MVP | B | F04, F05 | PDF §10; HS §4.2, §6.1 | Done |
| [F07](F07-live-view.md) | Theo dõi trực tiếp cơ bản | M0 | MVP | C | F06 | PDF §9.1; HS §4.3 | Done |
| [F08](F08-camera-config-roi.md) | Cấu hình camera và Bed ROI | M0 | MVP | B+C | F07 | PDF §7.2, §9.1; HS §4.1 | Done |
| [F09](F09-overview-dashboard-skeleton.md) | Dashboard khung (Tổng quan) | M0 | MVP | B+C | F04, F06 | PDF §9.1; HS §4.3 Hình 3 | Done |
| [F10](F10-observation-schema-engine-core.md) | Schema quan sát chung và khung Event Engine | M1 | MVP | A | F00 | PDF §10; HS §6.1 | Done |
| [F11](F11-pose-adapter.md) | Pose adapter MediaPipe | M1 | MVP | A | F05, F10 | PDF §6.1; HS §5.2, §5.5 | Done |
| [F12](F12-replay-cli.md) | Replay CLI và fixture | M1 | MVP | A | F11 | PDF §12, §13; HS §8.1 | Done |
| [F13](F13-body-features-target-quality.md) | Đặc trưng cơ thể, người mục tiêu, chất lượng quan sát | M1 | MVP | A | F10 | PDF §6.1, §13.4; HS §5.2 | Done |
| [F14](F14-body-state-machine.md) | State machine tư thế và vị trí | M1 | MVP | A | F13 | PDF §7; HS §5.4 | Done |
| [F15](F15-body-events.md) | Sự kiện cơ thể và vị trí | M1 | MVP | A | F14 | PDF §7.1–7.2; HS §5.1–5.4 | Done |
| [F16](F16-dev-evaluation-tool.md) | Công cụ đánh giá trên tập phát triển | M1 | MVP | A | F12, F15 | PDF §13; HS §8.1–8.2 | Done |
| [F17](F17-event-persistence-alerts.md) | Lưu sự kiện và tạo cảnh báo | M2 | MVP | B | F06, F15 | PDF §5, §10; HS §4.2, §6.2 | Done |
| [F18](F18-realtime-gateway.md) | Realtime gateway (WebSocket) | M2 | MVP | B+C | F17 | PDF §10; HS §6.1 | Done |
| [F19](F19-alert-lifecycle.md) | Vòng đời cảnh báo và audit | M2 | MVP | B | F17, F02 | PDF §5, §9.2; HS §4.2; QA#16 | Done |
| [F20](F20-alerts-screen.md) | Màn hình Cảnh báo | M2 | MVP | C | F18, F19 | PDF §9.1–9.2; HS §4.3 | Done |
| [F21](F21-overview-realtime.md) | Dashboard Tổng quan realtime | M2 | MVP | B+C | F09, F18 | PDF §9.1; HS §4.3 Hình 3 | Done |
| [F22](F22-timeline.md) | Timeline / Lịch sử theo dõi | M2 | MVP | B+C | F19 | PDF §9.1, §9.3; HS §4.3, §6.2 | Todo |
| [F23](F23-activity-abnormal-movement.md) | Mức vận động và chuyển động bất thường | M2 | MVP | A | F15 | PDF §7.3; HS §5.1–5.2 | Done |
| [F24](F24-shift-handover.md) | Bàn giao ca | M2 | MVP | B+C | F19, F22 | PDF §9.1; HS §2.2 | Todo |
| [F25](F25-face-adapter-quality.md) | Face adapter và cổng chất lượng khuôn mặt | M3 | MVP | A | F11, F13 | PDF §6.2, §17; HS §4.1, §5.3 | Done |
| [F26](F26-face-signals-attention.md) | Tín hiệu khuôn mặt và FACE_ATTENTION | M3 | MVP | A+C | F25, F23 | PDF §6.2, §7.4; HS §5.3 | Done |
| [F27](F27-rest-activity-status.md) | Trạng thái nghỉ/hoạt động (tham khảo) | M3 | MVP | A+C | F23, F26 | PDF §6.3; HS §5.3, §7.3 | Todo |
| [F28](F28-privacy-display-modes.md) | Chế độ riêng tư khi hiển thị | M4 | MVP | A+C | F07, F11 | PDF §11, §16; HS §6.3 | Todo |
| [F29](F29-final-evaluation.md) | Đánh giá chính thức và chỉ số realtime/workflow | M4 | MVP | A+B | F16, F18, F19, F26 | PDF §11, §13; HS §8.2 | Todo |
| [F30](F30-demo-readiness.md) | Sẵn sàng demo | M4 | MVP | C | F20–F28, F31 (R1–R3), F36 | PDF §16; HS §8.3; QA#32 | Todo |
| [F31](F31-multi-camera.md) | Nhiều camera/giường chạy đồng thời (R1–R3 cho demo chung kết) | M4 (R1–R3) / Sau MVP | MVP (R1–R3) | A+B | F06, F17 | HS §9.2; PDF §18; QA#32 | Todo |
| [F32](F32-alert-escalation.md) | Chuyển tiếp cảnh báo chưa được tiếp nhận | Sau MVP | Sau MVP | B | F19 | HS §9.2; PDF §18 | Todo |
| [F33](F33-mobile-notifications.md) | Thông báo di động cho điều dưỡng | Sau MVP | Sau MVP | B+C | F18 | HS §9.2; PDF §18, tr.10 | Todo |
| [F34](F34-long-term-statistics.md) | Dashboard thống kê dài hạn theo ca | Sau MVP | Sau MVP | B+C | F24 | HS §9.2; PDF §18 | Todo |
| [F35](F35-user-management.md) | Quản lý người dùng trên UI | M0 | MVP | B+C | F02 | Yêu cầu người dùng (2026-11-17); QA#36 | Done |
| [F36](F36-family-access.md) | Quyền xem của người nhà theo phiên | M4 | MVP | B+C | F02, F04, F18, F22, F28, F35 | Yêu cầu người dùng (2026-11-17); QA#31 | Todo |
| [F37](F37-area-shift-management.md) | Quản lý khu vực và ca trực | M0 | MVP | B+C | F03 | Yêu cầu người dùng (2026-11-17); QA#36 | Done |
