# F18 – Realtime gateway (WebSocket)

| Thuộc tính | Giá trị |
|---|---|
| Mã | F18 |
| Trạng thái | In progress |
| Ưu tiên | MVP |
| Milestone | M2 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F17 |
| Nhánh code | B+C (backend + frontend) |
| Nguồn | PDF §10 (tr.12), bảng tr.10; HS §4.2, §6.1; QA#11; A07, A09 |

## 1. Mục tiêu

Feature này đẩy thay đổi lên dashboard ngay khi có, để điều dưỡng không phải tải lại trang hay nhìn camera liên tục (HS §2.2, §4.2). Theo HS §6.1, đây là module **Realtime Gateway**, dùng WebSocket (PDF §10 (tr.12), bảng tr.10; QA#11). Quy tắc cốt lõi là **chỉ phát sau khi đã lưu DB** (HS §4.2; ADR-0002). Phía web có client tự kết nối lại và làm mới dữ liệu, để F20 và F21 bỏ được polling.

> **Liên quan F36/F04 (bổ sung 17/11/2026):** F18 giữ phạm vi cho nhân viên. Lọc theo quyền người nhà (grant), đóng kết nối mã 4403 khi quyền hết hiệu lực, và trạng thái tạm dừng thu hình được đặc tả ở [F36](F36-family-access.md) và [F04](F04-monitoring-sessions.md). Khi làm F18, thiết kế hub sao cho thêm bộ lọc theo từng kết nối mà không phải viết lại (QA#31).

## 2. Phạm vi

**Trong phạm vi**
- Endpoint `GET /api/v1/ws?token=<jwt>`, xác thực bằng JWT.
- Hub kết nối trong RAM của API, cài interface `Publisher` của F17.
- Phát các loại `event.created`, `alert.created`, `alert.updated`, `camera.status`, `bed.state`, `session.updated` theo [api-conventions.md](../02-architecture/api-conventions.md).
- Client WebSocket trong `web/src/realtime/`: kết nối lại có backoff, làm mới cache TanStack Query.
- Chỉ báo mất kết nối realtime trên giao diện.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Giao diện danh sách cảnh báo, âm thanh (→ F20). Thẻ giường realtime (→ F21).
- Thông báo di động, FCM (→ F33, sau MVP; QA#11).
- Chạy nhiều tiến trình API hoặc dùng broker (Redis…) *(ADR-0001: một máy, một tiến trình API)*.
- Đo delivery latency chính thức (→ F29).

## 3. Yêu cầu chi tiết

**Backend**

- **R1.** `GET /api/v1/ws?token=<jwt>`: token sai, hết hạn hoặc thiếu → đóng kết nối, không gửi dữ liệu nào *(api-conventions.md: WS dùng `?token=`)*. Mã đóng: 4401 *(giả định: mã riêng trong dải 4000–4999 để frontend phân biệt với lỗi mạng)*.
- **R2.** Mọi vai trò đăng nhập hợp lệ đều nhận cùng luồng thông báo *(api-conventions.md: mọi vai trò được xem tổng quan, cảnh báo, timeline)*.
- **R3.** Định dạng server → client: `{ "type": "<loại>", "payload": {...}, "sent_at": "<ISO UTC>" }`. Payload theo bảng WebSocket của [api-conventions.md](../02-architecture/api-conventions.md):
  - `event.created` (như item của `GET /events`);
  - `alert.created` (alert + event);
  - `alert.updated` (alert);
  - `camera.status`;
  - `bed.state`;
  - `session.updated`.
- **R4.** Chỉ phát **sau khi commit DB** *(HS §4.2; ADR-0002)*. Hub nhận lời gọi từ `Publisher` (F17); domain gọi publisher sau commit. Hai trường hợp riêng:
  - `camera.status`: phát sau khi commit thay đổi của bảng `cameras`.
  - `bed.state`: không có gì để lưu DB (trạng thái giường chỉ nằm trong RAM, theo data-model.md), nên phát ngay sau khi API cập nhật RAM.
- **R5.** Nối các nguồn phát:
  - `event.created`, `alert.created`: F17.
  - `alert.updated`: F19.
  - `camera.status`: F06, khi `cameras.status` đổi.
  - `bed.state`: F17, khi nhận `state`.
  - `session.updated`: F04, khi mở hoặc đóng phiên.
  
  Nguồn nào chưa có thì nối khi feature đó xong *(giả định: F18 chỉ cung cấp hub và cách gọi)*.
- **R6.** Client gửi `{"type":"ping"}` để giữ kết nối. Server chấp nhận, không cần trả lời; message lạ thì bỏ qua *(api-conventions.md; giả định: không trả lời)*.
- **R7.** Một client gửi chậm hoặc lỗi không làm chặn các client khác hay request ghi dữ liệu. Kết nối lỗi thì bị loại khỏi hub *(giả định: yêu cầu độ bền, NFR03 trong PRD)*.
- **R8.** Không mã hóa TLS, chỉ chạy trong LAN *(A09)*. Token hết hạn khi đang kết nối thì không ngắt giữa chừng; lần kết nối lại sẽ bị từ chối *(giả định)*.

**Frontend**

- **R9.** `web/src/realtime/`: một kết nối cho mỗi tab *(api-conventions.md)*. Tự kết nối lại theo exponential backoff có giới hạn trên *(PDF §10 (tr.12); giả định: hằng số backoff đặt trong code UI, không phải ngưỡng engine)*.
- **R10.** Nhận message thì chỉ cập nhật cache TanStack Query (invalidate hoặc `setQueryData`), không giữ state riêng song song *(coding-standards.md mục 3)*.
- **R11.** Kết nối lại thành công → invalidate toàn bộ query liên quan (overview, alerts, events, timeline). Không giả định là không bỏ lỡ gì *(api-conventions.md)*.
- **R12.** Bị đóng với mã 4401 → không thử lại, chuyển về trang đăng nhập như khi gặp 401 (F02) *(giả định)*.
- **R13.** Khi mất kết nối realtime, header hiện chỉ báo tiếng Việt, ví dụ "Mất kết nối cập nhật trực tiếp, đang kết nối lại…". Text đặt trong `vi.ts` *(giả định: PRD US07, người dùng không được hiểu nhầm "không có cảnh báo" là "an toàn")*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/api/realtime.py`: route WS, `WsHub` (cài `Publisher`).
  - `server/src/postcare/domain/notifications.py` (F17): interface `Publisher`.
  - `server/src/postcare/api/main.py`: đăng ký hub vào app, inject vào domain service.
  - `web/src/realtime/wsClient.ts`, `web/src/realtime/useRealtime.ts`, `web/src/realtime/invalidation.ts`, `web/src/components/RealtimeStatus.tsx`.
  - Test: `server/tests/api/test_realtime.py`; `web/src/realtime/wsClient.test.ts`, `web/src/realtime/invalidation.test.ts`.
- **Dữ liệu:** không có bảng mới.
- **API:** `GET /api/v1/ws?token=`.
- **UI:** chỉ báo kết nối realtime; thêm text vào `web/src/i18n/vi.ts`.
- **Cấu hình:** không có khóa engine. Hằng số backoff nằm trong code frontend.

## 5. Acceptance criteria

- [ ] **AC1.** `/api/v1/ws?token=` từ chối token sai, hết hạn hoặc thiếu (đóng kết nối, không gửi message nào); token đúng thì kết nối được *(api-conventions.md; PDF §10.1 (tr.12–13): phân quyền người dùng)*. — *Kiểm chứng:* `server/tests/api/test_realtime.py` (`test_ws_rejects_invalid_token`, `test_ws_rejects_expired_token`, `test_ws_accepts_valid_token`).
- [ ] **AC2.** Chỉ phát `event.created`, `alert.created`, `alert.updated`, `camera.status`, `bed.state` (và `session.updated`) **sau khi commit DB** *(HS §4.2; ADR-0002)*. — *Kiểm chứng:* `test_ws_alert_created_after_commit` (khi client nhận `alert.created`, một session DB khác đọc được alert đó); `test_no_broadcast_when_transaction_fails`.
- [ ] **AC3.** Client tự kết nối lại theo backoff và làm mới dữ liệu sau khi kết nối lại *(api-conventions.md)*. — *Kiểm chứng:* `web/src/realtime/wsClient.test.ts` (`reconnects with backoff after close`, `invalidates queries after reconnect`, `does not retry after 4401`).
- [ ] **AC4.** Client nhận `alert.created` trong ≤ 1 giây sau khi `POST /internal/v1/events` một sự kiện HIGH (chạy local) *(A07)*. — *Kiểm chứng:* `test_realtime.py::test_alert_created_delivered_within_1s`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API (TestClient WS) | `client.websocket_connect("/api/v1/ws?token=…")` với token đúng/sai/hết hạn/thiếu | Token sai không nhận được message nào dù có sự kiện mới |
| AC2 | API + domain | POST sự kiện HIGH → nhận `event.created` rồi `alert.created`; ép lỗi DB giữa transaction | Lỗi DB → không có message |
| AC2 | API | Gửi lại cùng `event_uid` | Không có message thứ hai |
| AC3 | unit frontend (Vitest, WebSocket giả) | Đóng socket → kiểm tra lịch kết nối lại; mở lại → `invalidateQueries` được gọi | Mã 4401 → không thử lại, chuyển về đăng nhập |
| AC4 | API | Đo thời gian từ POST tới lúc nhận message | — |
| R7 | API | Một client không đọc message, client khác vẫn nhận | — |
| R13 | component | Mất kết nối → hiện chỉ báo; kết nối lại → ẩn | — |

## 7. Giả định

- *(giả định)* Mã đóng 4401 cho lỗi xác thực (R1, R12).
- *(giả định)* Server không trả lời `ping` (R6).
- *(giả định)* Client lỗi bị loại khỏi hub và không chặn client khác (R7).
- *(giả định)* Token hết hạn giữa chừng thì không ngắt kết nối (R8).
- *(giả định)* Hằng số backoff đặt trong code UI (R9).
- *(giả định)* Có chỉ báo mất kết nối realtime trên header (R13).
- *(giả định)* Client bị loại vì gửi chậm được đóng với mã 1013 (Try Again Later) để tự kết nối lại và làm mới dữ liệu (R7).
- *(giả định)* Web nhận mã 4403 thì không thử lại, tải lại thông tin người dùng để định tuyến theo vai trò mới (R12).
- Delivery < 1 giây trong LAN (A07); không HTTPS (A09).

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

> Lập ngày 2026-11-18 (nhánh `feat/F18-realtime`).

**Khảo sát:** prototype, F17 và F35 đã làm phần lớn F18.

| Yêu cầu | Đã có | Bằng chứng / chỗ thiếu |
|---|---|---|
| R1 (4401) | `api/realtime.py::websocket_endpoint` (`user_from_token`, kiểm `is_active`, `token_version`) | `tests/test_realtime_seed.py::test_ws_rejects_bad_token`, `tests/api/test_auth.py::test_ws_expired_token_closes_4401`. Thiếu: thiếu token, token đúng kết nối được, token sai không nhận message dù có sự kiện |
| R2 | Mọi vai trò nhân viên (`STAFF_ROLES`) cùng luồng; `FAMILY` → 4403 (F35) | `test_family_role_default_deny.py::test_family_ws_closed_4403`. Thiếu: test cả 4 vai trò nhân viên |
| R3 | `WsHub.publish` tạo `{type, payload, sent_at}` | `test_ws_receives_event_after_commit` (chỉ kiểm `type`). Thiếu: `sent_at` ISO UTC, payload đúng hình |
| R4 | Domain gọi `safe_publish` sau commit (F17, F04, F06, F19) | `test_events.py::test_publish_happens_after_commit`, `test_ingest_event.py::test_db_error_publishes_nothing`. Thiếu ở mức WS: phiên DB khác đọc được alert khi client nhận; lỗi DB → client không nhận gì; trùng `event_uid` → không có message thứ hai |
| R5 | Đủ nguồn: `events.py`, `alerts.py`, `cameras.py`, `sessions.py` | Đã nối hết; không cần việc mới |
| R6 | `_receiver` bỏ qua mọi message | Thiếu test: ping và message lạ không làm đóng kết nối, không có trả lời |
| R7 | Hàng đợi riêng, `QueueFull` → loại khỏi hub | **Thiếu:** client bị loại vẫn mở socket nhưng không nhận gì nữa (tưởng đang kết nối). Sửa: đóng với mã 1013 để client tự kết nối lại và làm mới *(giả định)*. Test client không đọc, client khác vẫn nhận |
| R8 | Token chỉ kiểm lúc kết nối | Không đổi |
| F36 (QA#31) | Hub lưu `queue → user_id` | Đổi sang bản ghi kết nối `_Connection(user_id, accept)`; `register(..., accept=)` là bộ lọc theo từng kết nối, `close_where(pred, code)`; F36 dùng để lọc `family.*` và đóng 4403. Test bộ lọc ở mức hub |
| Log | `log_redaction.install_access_log_redaction()` gắn vào `uvicorn.access` (F07) | **Thiếu:** uvicorn ghi `"WebSocket /api/v1/ws?token=…" [accepted]` qua logger `uvicorn.error`, không qua access log. Sửa: gắn cùng filter vào `uvicorn.error`. Test |
| R9 | `wsClient.ts` backoff 1 s → 15 s, ping 20 s | Thiếu test |
| R10, R11 | `invalidation.ts::applyMessage`, `invalidateAll` khi mở lại | Thiếu test |
| R12 | 4401 → `logout` | Thiếu test. **Thiếu:** 4403 (đổi vai trò sang `FAMILY` giữa chừng) đang thử lại mãi. Sửa: 4403 → không thử lại, tải lại `/auth/me` để định tuyến theo vai trò mới *(giả định)* |
| R13 | `AppLayout.tsx::RealtimeStatus`, `vi.realtime.reconnecting` | Thiếu test component |
| AC4 | — | Thiếu `test_alert_created_delivered_within_1s`. Lệnh `measure-delivery` thuộc F29 (R4), không làm ở F18; đo thủ công bằng script client WS |

**Các bước:**

1. **Test trước** (commit `test(F18): …`):
   - `server/tests/api/test_realtime.py`: `test_ws_rejects_invalid_token`, `test_ws_rejects_missing_token`, `test_ws_rejects_expired_token`, `test_ws_accepts_valid_token` (4 vai trò nhân viên), `test_invalid_token_receives_nothing`, `test_message_envelope_has_type_payload_sent_at`, `test_ws_alert_created_after_commit` (`real_commit`), `test_no_broadcast_when_transaction_fails`, `test_duplicate_event_uid_no_second_message`, `test_ping_and_unknown_messages_ignored`, `test_slow_client_dropped_others_still_receive`, `test_slow_client_closed_1013`, `test_alert_created_delivered_within_1s`, `test_ws_token_redacted_in_server_log`; hub: `test_per_connection_filter`, `test_close_where`.
   - `web/src/realtime/wsClient.test.ts`: `reconnects with backoff after close`, `backoff capped`, `invalidates queries after reconnect`, `does not retry after 4401`, `does not retry after 4403`, `sends ping`.
   - `web/src/realtime/invalidation.test.ts`: `bed.state` cập nhật overview, `alert.created` invalidate, `invalidateAll`.
   - `web/src/components/AppLayout.test.tsx`: chỉ báo mất kết nối hiện/ẩn theo trạng thái.
2. **Backend:** `api/realtime.py` (`_Connection`, bộ lọc, `close_where`, client chậm → 1013), `api/main.py` + `log_redaction.py` (filter cho `uvicorn.error`).
3. **Web:** `wsClient.ts` (4403 → `onForbidden`), `RealtimeProvider.tsx`, `auth/AuthContext.tsx` (`reloadUser`).
4. **Docs:** `api-conventions.md` (mã 1013, 4403 phía web), spec §7, §10.
5. `make check`; kiểm thử thủ công (DB `postcare_f18`, cổng 8028, đo độ trễ); trạng thái In review.

Không có migration, endpoint mới hay thư viện mới; không cần `make gen-api-types`.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
