# F19 – Vòng đời cảnh báo và audit

| Thuộc tính | Giá trị |
|---|---|
| Mã | F19 |
| Trạng thái | In review |
| Ưu tiên | MVP |
| Milestone | M2 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F17, F02 |
| Nhánh code | B (backend) |
| Nguồn | PDF §5 (tr.6), §9.2 (tr.11), §10.1 (tr.12–13), §11 (tr.13), §16 (tr.17); HS §4.2, §8.3, Hình 3; QA#16, QA#18; ADR-0007 |

## 1. Mục tiêu

Một cảnh báo không chỉ là thông báo tức thời mà phải trở thành **bản ghi truy vết được**: ai tiếp nhận, lúc nào, kết quả kiểm tra là gì, xử lý xong khi nào (HS §4.2; PDF §5 (tr.6)). Feature này làm API backend cho vòng đời cảnh báo theo [ADR-0007](../02-architecture/decisions/ADR-0007-alert-status-outcome.md):
- `status` (vòng đời) và `outcome` (kết quả kiểm tra) là hai trường riêng.
- Chỉ một người được tiếp nhận.
- Mọi thao tác đều có audit.

Dữ liệu `outcome` còn dùng để tính tỷ lệ cảnh báo sai (PDF §11 (tr.13); F29).

## 2. Phạm vi

**Trong phạm vi**
- `POST /api/v1/alerts/{id}/acknowledge`, `POST /api/v1/alerts/{id}/outcome`, `POST /api/v1/alerts/{id}/resolve`.
- `GET /api/v1/alerts` (lọc, sắp xếp) và `GET /api/v1/alerts/{id}`.
- Kiểm tra chuyển trạng thái, xử lý tranh chấp khi hai người cùng tiếp nhận, phân quyền, audit.
- Gọi publisher `alert.updated` sau commit (F18 phát).

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Giao diện nút thao tác, hiển thị "Chưa ghi kết quả" (→ F20).
- Tạo alert từ sự kiện (đã có ở F17).
- Timeout, chuyển tiếp cảnh báo chưa tiếp nhận (→ F32, sau MVP; QA#16).
- Mở lại cảnh báo đã xử lý *(ADR-0007: không đi lùi)*.
- Chỉ số workflow (→ F29).

## 3. Yêu cầu chi tiết

- **R1.** Vòng đời `status`: `PENDING` (Chờ tiếp nhận) → `ACKNOWLEDGED` (Đã tiếp nhận) → `RESOLVED` (Đã xử lý). Không đi lùi, không bỏ bước *(ADR-0007; QA#16; PDF §5 (tr.6))*. Chuyển sai → 409 `INVALID_ALERT_TRANSITION`, gồm:
  - `resolve` khi đang `PENDING`;
  - `outcome` khi đang `PENDING` hoặc `RESOLVED`;
  - `acknowledge` khi đang `RESOLVED`.
- **R2.** `acknowledge`: chỉ **một** người tiếp nhận *(ADR-0007; QA#16)*.
  - Cài bằng câu `UPDATE … WHERE id = :id AND status = 'PENDING'`. Không cập nhật được dòng nào thì đọc lại người đã tiếp nhận *(giả định: cách cài đặt chống tranh chấp)*.
  - Người thứ hai (kể cả chính người đã tiếp nhận bấm lại) nhận 409 `ALERT_ALREADY_ACKNOWLEDGED`. `message` tiếng Việt có tên người đã tiếp nhận (ví dụ "Cảnh báo đã được tiếp nhận bởi Nguyễn Văn A"). `details` = `{acknowledged_by: {id, full_name}, acknowledged_at}` *(api-conventions.md, mục Lỗi; giả định: người đã tiếp nhận bấm lại cũng nhận 409)*.
- **R3.** `outcome` `{outcome, note?}`: `outcome ∈ {CONFIRMED, FALSE_ALARM, PATIENT_SAFE}` (Xác nhận đúng / Cảnh báo sai / Bệnh nhân an toàn) *(PDF §9.2 (tr.11); HS §4.2; ADR-0007)*.
  - Chỉ ghi được khi `status = ACKNOWLEDGED`.
  - Ghi lại được nhiều lần trước khi đóng; lần sau ghi đè `outcome`, `outcome_by`, `outcome_at`. Mỗi lần đều có audit *(ADR-0007)*.
  - `note` nếu có thì ghi đè ghi chú hiện tại; lịch sử ghi chú nằm ở audit *(giả định)*.
- **R4.** `resolve` `{note?}` *(PDF §9.2 (tr.11); HS §4.2; ADR-0007)*:
  - Chỉ khi `status = ACKNOWLEDGED`. Đặt `RESOLVED`, `resolved_by`, `resolved_at`.
  - Được phép khi `outcome = null`. Khi đó giữ `outcome = null` (UI hiển thị "Chưa ghi kết quả", F20).
- **R5.** Người được ghi kết quả và xử lý: bất kỳ người dùng có quyền ghi (NURSE, CHARGE_NURSE, ADMIN), không bắt buộc là người đã tiếp nhận. Người thực hiện mỗi bước được lưu riêng (`outcome_by`, `resolved_by`) *(api-conventions.md, ma trận quyền; giả định: nguồn không giới hạn người ghi kết quả)*.
- **R6.** Phân quyền *(QA#18; api-conventions.md; PDF §3 (tr.5))*:
  - DOCTOR gọi `acknowledge`, `outcome`, `resolve` → 403 `FORBIDDEN`.
  - Chưa đăng nhập → 401.
  - Mọi vai trò xem được danh sách và chi tiết.
- **R7.** Mỗi thao tác lưu người thực hiện và thời điểm *(HS §4.2; PDF §10.1 (tr.13); ADR-0007)*:
  - trong `alerts` (`acknowledged_by/at`, `outcome_by/at`, `resolved_by/at`);
  - và trong `audit_logs` qua `record_audit()` (F01), với `action` là `alert.acknowledge`, `alert.outcome`, `alert.resolve`, `entity_type = "alert"`, `before`/`after` gồm `status`, `outcome`, `note`.
  
  Hai bảng được ghi trong cùng transaction. Thời điểm lấy từ server (UTC).
- **R8.** Commit xong mới gọi publisher `alert.updated` (payload alert) *(HS §4.2; ADR-0002)*. Request bị 403/404/409 không gọi publisher.
- **R9.** `GET /api/v1/alerts?status&bed_id&priority&from&to&limit&offset` → `{items, total}` *(PDF §9.1 (tr.11): danh sách theo thời gian, giường, mức ưu tiên, trạng thái; api-conventions.md)*.
  - Sắp xếp mặc định: chưa xử lý trước (`PENDING`, rồi `ACKNOWLEDGED`, rồi `RESOLVED`); trong mỗi nhóm thì mới nhất trước *(F20 AC1: "cảnh báo chưa xử lý xếp đầu"; giả định: thứ tự trong nhóm)*.
  - `from`/`to` lọc theo `events.occurred_at` *(giả định)*.
- **R10.** `AlertOut` gồm:
  - `id`, `status`, `outcome`, `note`, `created_at`;
  - người và thời điểm từng thao tác (`{id, full_name}` + thời điểm);
  - sự kiện kèm theo (`code`, `priority`, `occurred_at`, `observation_quality`);
  - `bed {id, code}`, `session {id, patient_code}`.
  
  Không trả câu tiếng Việt cho sự kiện; frontend tự ánh xạ *(api-conventions.md)*.
- **R11.** Không tìm thấy alert → 404 `NOT_FOUND`. Body sai (`outcome` lạ, thiếu `outcome`, trường thừa, `note` > 1000 ký tự) hoặc `limit > 200` → 422 `VALIDATION_ERROR` (lỗi schema, theo [api-conventions.md](../02-architecture/api-conventions.md)).

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/domain/alerts.py`: `acknowledge_alert`, `record_outcome`, `resolve_alert`, `list_alerts`, `get_alert`; lỗi qua `DomainError`.
  - `server/src/postcare/api/v1/alerts.py`: router.
  - Schema `AlertOut`, `AlertOutcomeIn`, `AlertResolveIn`.
  - Test: `server/tests/domain/test_alert_lifecycle.py`, `server/tests/api/test_alerts_api.py`.
- **Dữ liệu:** bảng `alerts` (F17), `audit_logs` (F01), `users`. Không có migration mới.
- **API:** các endpoint ở mục 2. Mã lỗi `INVALID_ALERT_TRANSITION`, `ALERT_ALREADY_ACKNOWLEDGED`, `FORBIDDEN`, `NOT_FOUND` (đã có trong [api-conventions.md](../02-architecture/api-conventions.md)).
- **UI:** không có (F20). `message` lỗi tiếng Việt.
- **Cấu hình:** không có.

## 5. Acceptance criteria

- [x] **AC1.** `PENDING → ACKNOWLEDGED → RESOLVED`. Chỉ sau khi tiếp nhận mới ghi được outcome và ghi chú. Chuyển sai → 409 `INVALID_ALERT_TRANSITION` *(ADR-0007; QA#16)*. — *Kiểm chứng:* `server/tests/api/test_alerts_api.py::test_transition_matrix` (9 ca trạng thái × thao tác), `test_outcome_values_accepted`, `test_body_validation_422`; `server/tests/test_alerts.py::test_full_lifecycle` (ghi outcome hai lần), `test_invalid_transitions`; `server/tests/domain/test_alert_lifecycle.py::test_concurrent_resolve_only_one_winner`, `test_concurrent_outcome_and_resolve_never_outcome_after_resolved`.
- [x] **AC2.** Chỉ một người tiếp nhận. Người thứ hai nhận 409 `ALERT_ALREADY_ACKNOWLEDGED`, có tên người đã tiếp nhận trong `message` và `details` *(ADR-0007; api-conventions.md)*. — *Kiểm chứng:* `server/tests/test_alerts.py::test_second_acknowledge_is_409_with_name`; `server/tests/domain/test_alert_lifecycle.py::test_conditional_update_only_one_winner` (hai session DB tiếp nhận cùng alert).
- [x] **AC3.** Mỗi thao tác lưu người thực hiện và thời điểm trong `alerts` **và** `audit_logs` (`alert.acknowledge`, `alert.outcome`, `alert.resolve`, có `before`/`after`). `alert.updated` chỉ phát sau commit *(HS §4.2; PDF §10.1 (tr.13))*. — *Kiểm chứng:* `server/tests/api/test_alerts_api.py::test_each_action_writes_alert_fields_and_audit`, `test_publisher_called_after_commit_only_on_success` (kết nối DB khác đọc thấy thay đổi lúc publish), `test_transition_matrix` (409 không audit, không phát), `test_unknown_alert_404_no_publish`.
- [x] **AC4.** DOCTOR gọi API ghi của cảnh báo → 403; DOCTOR vẫn xem được danh sách và chi tiết *(QA#18; api-conventions.md)*. — *Kiểm chứng:* `server/tests/api/test_alerts_api.py::test_doctor_cannot_ack_outcome_resolve_403`, `test_doctor_can_list_and_get`, `test_no_token_401`; FAMILY 403: `server/tests/api/test_family_role_default_deny.py`.
- [x] **AC5.** Bấm "Đã xử lý" khi chưa ghi kết quả → `status = RESOLVED`, `outcome = null` (UI hiển thị "Chưa ghi kết quả", kiểm ở F20) *(ADR-0007)*. — *Kiểm chứng:* `server/tests/api/test_alerts_api.py::test_resolve_without_outcome_keeps_null`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | API | Đi đủ vòng đời; ghi outcome hai lần | Mọi cặp chuyển sai trả 409; `outcome` lạ → 400 |
| AC2 | API + domain | Hai NURSE lần lượt tiếp nhận; hai session DB tranh chấp | Chính người đã tiếp nhận bấm lại → 409 |
| AC3 | API | Đọc `alerts` và `audit_logs` sau mỗi bước; publisher giả ghi thứ tự | 403/404/409 không ghi audit, không gọi publisher |
| AC4 | API | `auth_headers("DOCTOR")` cho 3 endpoint ghi và 2 endpoint đọc | Không token → 401 |
| AC5 | API | Tiếp nhận rồi xử lý ngay | — |
| R9 | API | Lọc theo `status`, `bed_id`, `priority`, `from/to`; kiểm thứ tự mặc định | `limit > 200` → 422 |
| R11 | API | Alert không tồn tại | 404 |

## 7. Giả định

- *(giả định)* Chống tranh chấp bằng `UPDATE` có điều kiện (R2); `outcome`/`resolve` khóa dòng alert (`SELECT … FOR UPDATE`) trước khi kiểm tra trạng thái.
- *(giả định)* Người đã tiếp nhận bấm lại cũng nhận 409 (R2).
- *(giả định)* `note` ghi đè, lịch sử nằm ở audit (R3).
- *(giả định)* Mọi người có quyền ghi đều được ghi kết quả và xử lý, không chỉ người tiếp nhận (R5).
- *(giả định)* Thứ tự sắp trong mỗi nhóm trạng thái; `from/to` lọc theo `occurred_at` (R9).
- Ma trận quyền theo QA#18 *(giả định)*.

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

> Planner điền mục này theo [plan-feature.md](../ai/workflows/plan-feature.md) trước khi bắt đầu code.

**Khảo sát (2026-11-18).** Prototype đã có phần lớn F19:
- `server/src/postcare/domain/alerts.py`: `acknowledge` (UPDATE có điều kiện `status = PENDING`, 409 `ALERT_ALREADY_ACKNOWLEDGED` có tên), `set_outcome`, `resolve`, `list_alerts`, `get_alert`; `record_audit` cùng transaction; `_finish` commit rồi mới `safe_publish("alert.updated")`.
- `server/src/postcare/api/v1/alerts.py`: đọc dùng `require_staff`, ghi dùng `require_writer` (DOCTOR/FAMILY → 403).
- `OutcomeIn`/`ResolveIn` (`domain/dto.py`): `extra="forbid"`, `note` tối đa 1000 ký tự.
- Test có sẵn `server/tests/test_alerts.py`: vòng đời đầy đủ, 409 lần tiếp nhận thứ hai (cả chính người đã tiếp nhận), chuyển sai, `outcome` lạ, 404, thứ tự danh sách. FAMILY 403 ở `tests/api/test_family_role_default_deny.py` (F35).

**AC đã đạt (bằng chứng hiện có):** AC1 phần lớn (`test_full_lifecycle`, `test_invalid_transitions`), AC2 tuần tự (`test_second_acknowledge_is_409_with_name`), AC5 (`test_invalid_transitions`: resolve khi chưa có outcome → `outcome = null`).

**Khoảng trống cần làm:**
1. `outcome`/`resolve` đọc trạng thái rồi ghi qua ORM, không khóa dòng: hai `resolve` đồng thời đều qua kiểm tra (hai audit `alert.resolve`), hoặc `outcome` ghi đè sau khi đã `RESOLVED`. Sửa: đọc alert bằng `SELECT … FOR UPDATE` cho `set_outcome` và `resolve` *(giả định: cách cài đặt chống tranh chấp, giống R2)*.
2. Chưa có test tranh chấp hai session DB cho `acknowledge` (AC2) và `resolve`.
3. Chưa có test audit `before`/`after` + người thực hiện cho từng thao tác, publish sau commit (đọc từ kết nối khác lúc publish), 403/404/409 không ghi audit/không phát (AC3).
4. Chưa có test DOCTOR 403 cho 3 endpoint ghi, DOCTOR đọc được, không token → 401 (AC4).
5. Chưa có test ma trận trạng thái × thao tác đầy đủ, cả 3 giá trị `outcome`, `note` > 1000 ký tự, `resolve` ghi đè `note`, lọc `bed_id`/`from`/`to`, `limit > 200`.

**Bước:**
1. Test trước (`server/tests/api/test_alerts_api.py`, `server/tests/domain/test_alert_lifecycle.py`): các mục 2–5 ở trên. Xác nhận test tranh chấp `resolve` đỏ vì không khóa dòng. Commit `test(F19): …`.
2. Cài `_get(..., lock=True)` dùng `with_for_update()` trong `set_outcome`, `resolve`. Commit `feat(F19): …`.
3. Doc: sửa R11 cho khớp api-conventions (lỗi schema → 422 `VALIDATION_ERROR`, không phải 400); ghi giả định khóa dòng; cập nhật tên test ở AC. Không có migration, không đổi API/OpenAPI nên không cần `make gen-api-types`.
4. `make check` một lần; ghi bằng chứng vào §10; trạng thái "In review".

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

**2026-11-18 (builder).**
- Thay đổi code duy nhất: `domain/alerts.py` `_get(..., lock=True)` (`SELECT … FOR UPDATE OF alerts`) trong `set_outcome` và `resolve`. Trước đó hai `resolve` đồng thời đều thành công (hai audit `alert.resolve`) và `outcome` có thể ghi sau khi đã `RESOLVED`; test tranh chấp đỏ trước khi sửa, xanh sau khi sửa. `acknowledge` giữ `UPDATE` có điều kiện (R2). SQLite (ADR-0010) bỏ qua `FOR UPDATE`, không ảnh hưởng.
- Test mới: `server/tests/api/test_alerts_api.py` (ma trận trạng thái × thao tác, 3 giá trị outcome, validation 422, audit before/after + người thực hiện, publish sau commit, DOCTOR 403/đọc được, 401, 404, lọc `bed_id`/`from`/`to`, `limit`), `server/tests/domain/test_alert_lifecycle.py` (tranh chấp `acknowledge`, `resolve`, `outcome`×`resolve` với hai session DB thật, mỗi ca chạy 3 lần).
- Lệch spec: R11 ghi 400 cho body sai; code và api-conventions dùng 422 `VALIDATION_ERROR` cho lỗi schema. Đã sửa R11 theo api-conventions.
- Không có migration, không đổi OpenAPI (không cần `make gen-api-types`).

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
