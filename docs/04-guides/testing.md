# Hướng dẫn kiểm thử

Mục tiêu: mọi thay đổi đều được kiểm chứng tự động bằng `make check`. Hành vi của engine phải chứng minh được bằng test xác định, không cần camera.

## 1. Các tầng test

| Tầng | Công cụ | Vị trí | Chạy trong `make check`? | Ghi chú |
|---|---|---|---|---|
| Unit: schemas, engine | pytest | `server/tests/engine/`, `server/tests/schemas/` | Có | Không cần DB, camera, model |
| Unit: domain | pytest | `server/tests/domain/` | Có | Dùng DB test |
| API | pytest + FastAPI TestClient | `server/tests/api/` | Có | DB `postcare_test`, rollback mỗi test |
| Tích hợp worker ↔ API | pytest | `server/tests/integration/` | Có | Worker chạy với `FakeFrameSource` / `FakePoseAdapter` |
| Vision (model thật) | pytest marker `vision` | `server/tests/vision/` | **Không**; chạy `make test-vision` | Cần `models/` và video trong `data/`; bỏ qua nếu thiếu. Marker đăng ký trong `pyproject.toml` (`--strict-markers`); F00 có `test_placeholder.py` (luôn skip) để `pytest -m vision` trả exit 0 thay vì 5 cho tới F11 |
| Eval | pytest | `server/tests/eval/` | Có | Dữ liệu tổng hợp nhỏ |
| Frontend unit/component | Vitest + Testing Library | `web/src/**/*.test.tsx` | Có | Mock API |
| Từ cấm | Vitest | `web/src/i18n/vi.test.ts` (tạo ở F00) | Có | Quét `vi.ts` theo [danh sách](../01-product/glossary.md#từ-cấm-trên-ui) |
| E2E | Playwright | `web/e2e/` | **Không**; chạy `make e2e` | Kịch bản demo chính (F30) |

## 2. Engine

**Nguyên tắc:**
- Viết test **trước** khi viết rule.
- Mỗi rule có ít nhất 1 ca dương tính và 1 **ca âm tính** (tình huống dễ gây nhầm, HS §8.1, §8.3).
- Test chỉ dùng `FrameObservation` và `EngineConfig`, không gọi MediaPipe.
- Không dùng `sleep` hay đồng hồ thật; thời gian lấy từ `ts_ms`.

**Builder chuỗi pose tổng hợp** (`server/tests/engine/builders.py`, tạo ở F13):

```python
seq = (PoseSequence(fps=15, roi=BED_ROI)
       .lying(seconds=3)
       .raise_to_sitting(seconds=1.5)
       .sitting(seconds=3)
       .move_to_edge(seconds=1)
       .standing(seconds=1.5)
       .walk_out(seconds=2)
       .build())            # -> list[FrameObservation]
out = run_engine(seq, config=default_config())
assert codes(out) == ["SIT_UP", "BED_EDGE", "STAND_UP", "BED_EXIT"]
```

Builder hỗ trợ thêm các thao tác: `noise(frames=2)`, `drop_landmarks(seconds=…)`, `add_person_outside_roi(…)`, `add_second_person_in_roi(…)`, `turn_over(…)`, `fast_drop(…)`, `face(signals={…}, seconds=…)`.

**Ca âm tính bắt buộc** (mỗi ca là một test có tên rõ):

| Tình huống | Kỳ vọng | Nguồn |
|---|---|---|
| Ngồi dậy rồi nằm lại | Không có BED_EXIT, BED_EDGE | PDF §7.2 |
| Nhiễu "ngồi" 1–3 frame | Không đổi trạng thái | PDF §5, §7 |
| Góc thân dao động quanh ngưỡng | Không đổi trạng thái liên tục (hysteresis) | PDF §7 |
| Mất landmark / bị che khi đang ở mép giường | NO_OBSERVATION, **không** BED_EXIT | HS §5.2 |
| Điều dưỡng đứng cạnh giường (ngoài ROI) | Không có sự kiện từ người đó | PDF §13.1; HS §8.1 |
| Hai người trong ROI | NO_OBSERVATION (MULTIPLE_PEOPLE) | QA#20 |
| Trở mình | POSTURE_CHANGE (LOG), không ABNORMAL_MOVEMENT | HS §5.2 |
| Hạ lông mày ngắn khi nằm yên | Không FACE_ATTENTION | PDF §7.4 |
| Mặt không rõ | Không kết luận "Đang nghỉ", không FACE_ATTENTION | HS §9.1 |
| Lặp sự kiện trong cửa sổ debounce | Chỉ 1 sự kiện | PDF §7 |

**Fixture từ video thật:**
- `postcare replay … --save-observations` cắt đoạn ngắn, lưu `server/tests/fixtures/<scenario>.jsonl` (chỉ toạ độ, không ảnh).
- Test regression: chạy engine trên fixture và so sánh danh sách sự kiện với file `.expected.json`.

## 3. Backend

- DB test: biến `TEST_DATABASE_URL` (mặc định `postgresql+psycopg://postcare:postcare@localhost:5432/postcare_test`). Fixture `db_session` bọc transaction và rollback sau mỗi test.
- Fixture `client` (TestClient), `auth_headers(role)` để test phân quyền.
- Với mỗi endpoint ghi, test:
  - thành công;
  - validation sai (400/422);
  - không đủ quyền (403);
  - xung đột (409, nếu có);
  - audit log được ghi.
- WebSocket: dùng `client.websocket_connect`, kiểm tra thứ tự "commit trước, phát sau".

## 4. Frontend

- Component test cho mọi màn hình chính. Mock API bằng `msw` (đã chốt ở F00): server dùng chung ở `web/src/test/msw.ts`, khởi động trong `web/src/test/setup.ts` với `onUnhandledRequest: 'error'`, mỗi test tự thêm handler bằng `server.use(...)`. Test prototype cũ thay `globalThis.fetch` bằng mock thủ công vẫn được giữ.
- Test `vi.ts`:
  - có đủ text cho mọi `EventCode`, `BodyState`, `AlertStatus`, `AlertOutcome` (so với danh sách export từ type OpenAPI);
  - không chứa từ cấm.
- Không snapshot toàn trang (dễ vỡ); kiểm tra text và hành vi.

## 5. Lệnh

| Lệnh | Làm gì |
|---|---|
| `make test` | pytest (trừ marker `vision`) + vitest |
| `make test-vision` | pytest `-m vision` (cần model + dữ liệu) |
| `make e2e` | Playwright |
| `make check` | format-check + lint + typecheck + lint-imports + kiểm tra type API đã sinh khớp OpenAPI + test + build-web |

## 6. Định nghĩa "đã test" cho một feature

- Mọi acceptance criteria đều có ít nhất một test tự động, **hoặc** một bước kiểm chứng thủ công ghi rõ trong spec (ví dụ với camera thật).
- `make check` xanh.
- Feature engine có thêm ca âm tính tương ứng ở bảng mục 2.
