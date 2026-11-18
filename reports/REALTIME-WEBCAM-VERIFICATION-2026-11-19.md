# Báo cáo phiên nghiệm thu realtime webcam A01

**Ngày thực hiện:** 19/11/2026 (giờ Việt Nam)
**Bản clone:** `/home/atuna/Downloads/PostCareAI-fresh`
**Nhánh:** `feat/F07-dual-live-view`
**Phạm vi:** cấu hình ROI, mở phiên theo dõi và kiểm tra luồng camera thật qua sự kiện, cảnh báo, xử lý điều dưỡng và timeline.

## 1. Mục tiêu

Kiểm tra sản phẩm bằng webcam USB thật trên một giường A01, giữ chế độ riêng tư ở khung trái và hiển thị skeleton + ROI ở khung phải. Kịch bản mong muốn là:

`nằm → ngồi dậy → mép giường → đứng lên → rời vùng giường`

Sau sự kiện, điều dưỡng phải tiếp nhận cảnh báo, ghi kết quả, xử lý và xem được lịch sử.

## 2. Môi trường

- Web: `http://127.0.0.1:5175`
- API: `http://127.0.0.1:8002`
- Camera: `Camera A01`, nguồn webcam USB, index `0`
- Tài khoản thao tác: ADMIN để cấu hình và xử lý cảnh báo (`Phạm Thu Hà`)
- Bệnh nhân thử nghiệm: `BN-DEMO-A01`
- Phiên theo dõi bắt đầu lúc `01:29:53`
- Không dùng simulator và không lưu video vận hành.

## 3. Các bước đã thực hiện

1. Đăng nhập ADMIN trên bản clone mới.
2. Mở `Quản lý giường → Camera A01 → Cấu hình`.
3. Vẽ ROI 5 điểm bao quanh vùng giường và lưu thành công.
4. Tạo bệnh nhân thử nghiệm `BN-DEMO-A01`.
5. Mở phiên theo dõi cho giường A01.
6. Mở `Theo dõi trực tiếp`, xác nhận camera hoạt động, ảnh riêng tư và skeleton cùng ROI.
7. Chạy thử chuyển động trước webcam.
8. Mở danh sách cảnh báo, tiếp nhận cảnh báo, ghi kết quả `Xác nhận đúng`, thêm ghi chú và đánh dấu đã xử lý.
9. Mở `Lịch sử theo dõi` để kiểm tra sự kiện và thao tác đã được lưu.

## 4. Kết quả

| Hạng mục | Kết quả | Bằng chứng |
|---|---|---|
| Camera thật hoạt động | PASS | Live view hiển thị `CAMERA HOẠT ĐỘNG`; pose cập nhật realtime |
| ROI giường | PASS | ROI 5 điểm được lưu, hiển thị lại trên live view |
| Phiên theo dõi | PASS | A01 hiển thị `Đang theo dõi · Bệnh nhân BN-DEMO-A01` |
| Phát hiện mép giường | PASS | Sự kiện `Bệnh nhân đang ở mép giường` lúc `01:30:33`, chất lượng quan sát tốt |
| Tạo cảnh báo | PASS | Cảnh báo mép giường xuất hiện ở màn hình Cảnh báo |
| Điều dưỡng tiếp nhận | PASS | Người tiếp nhận `Phạm Thu Hà`, lúc `01:34:25` |
| Ghi kết quả | PASS | Kết quả `Xác nhận đúng`, có ghi chú kiểm tra |
| Xử lý cảnh báo | PASS | Trạng thái chuyển sang `ĐÃ XỬ LÝ` |
| Timeline | PASS | Timeline hiển thị sự kiện, trạng thái xử lý và kết quả xác nhận |
| Rời khỏi vùng giường | BLOCKED | Chưa phát được `BED_EXIT` vì góc webcam chưa thấy đủ toàn thân/chân |

## 5. Phân tích blocker

Khi người di chuyển ra khỏi vùng quan sát, hệ thống chuyển sang `Không đủ dữ liệu quan sát` thay vì suy diễn thành rời giường. Đây là hành vi đúng theo quy tắc an toàn khi landmark không đủ.

Góc webcam hiện tại chưa bao phủ trọn giường và phần chân. Vì vậy, phiên này chứng minh được luồng realtime đến cảnh báo và xử lý điều dưỡng, nhưng chưa đủ bằng chứng cho cảnh báo rời giường mức cao.

## 6. Việc cần làm tiếp theo

1. Lùi hoặc hạ webcam để thấy trọn giường và toàn thân người.
2. Mở lại `http://127.0.0.1:5175/cameras/1/config` và vẽ lại ROI theo khung hình mới.
3. Chạy lại đủ chuỗi nằm → ngồi → mép → đứng → rời vùng giường.
4. Xác nhận cảnh báo rời giường mức cao, sau đó tiếp nhận, ghi kết quả và kiểm tra timeline.
5. Khi đạt, cập nhật runbook demo và chuyển sang F24 – Bàn giao ca.

## 7. Kiểm tra mã nguồn

- `make check` gần nhất trước phiên này: PASS, gồm backend, frontend và production build.
- Nhánh xuất bản chỉ gồm báo cáo và tài liệu tiến độ. Phần live view hai khung đã thử trong clone local nằm ở nhánh riêng `feat/F07-dual-live-view`, chưa được đưa lên `main` cùng báo cáo này.
- Hook pre-push chạy `make check` trước khi xuất bản; kết quả kiểm tra phần mềm không thay thế nghiệm thu webcam thực tế.
- Nhật ký chi tiết nằm tại [docs/progress/session-log.md](../docs/progress/session-log.md).
