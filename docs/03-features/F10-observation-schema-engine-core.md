# F10 – Schema quan sát chung và khung Event Engine

| Thuộc tính | Giá trị |
|---|---|
| Mã | F10 |
| Trạng thái | In progress <!-- Todo / Planned / In progress / In review / Done / Blocked --> |
| Ưu tiên | MVP |
| Milestone | M1 |
| Ước lượng | 2 phiên |
| Phụ thuộc | F00 |
| Nhánh code | A (vision/engine) |
| Nguồn | PDF §7 (tr.8), §10 (tr.12); HS §5.4, §5.5, §6.1; QA#22; ADR-0003 |

## 1. Mục tiêu

Định nghĩa schema chung giữa adapter AI và Event Engine (`FrameObservation` và các kiểu liên quan), catalog mã sự kiện / mức ưu tiên, cấu hình ngưỡng `EngineConfig`, và lớp `Engine` rỗng có API duy nhất `Engine.process(obs)`. PDF §10 yêu cầu "Event Engine không nên phụ thuộc trực tiếp vào API cụ thể của MediaPipe… inference adapter chuyển output model thành một schema chung"; HS §6.1 nêu lại: đổi model thì chỉ adapter đổi, engine và giao diện giữ nguyên. Feature này mở đường cho nhánh A làm F13–F15 ngay trên dữ liệu tổng hợp, không cần camera hay model.

## 2. Phạm vi

**Trong phạm vi**
- Schema Pydantic trong `postcare/schemas`: `FrameObservation`, `PersonPose`, `Keypoint`, `KeypointName`, `FaceObservation`, `FaceSignals`, `BodyState`, `ObservationQuality`, `BodyStateSnapshot`, `EngineEvent`, `EngineOutput`, `EventCode`, `Priority`, `RoiPolygon` (nếu F08 chưa tạo).
- Catalog `EventCode → Priority mặc định, có tạo cảnh báo hay không` ở `postcare/schemas/events.py`.
- `EngineConfig`: đọc `config/engine.default.yaml`, hợp nhất override theo camera, tính `config_hash`.
- `Engine` với các bước pipeline để trống; observation rỗng → `NO_OBSERVATION`.
- Hoàn thiện `config/engine.default.yaml` theo event-engine.md §6.
- mypy strict xanh cho `schemas` và `engine`.

**Ngoài phạm vi** (để feature khác hoặc không làm)
- Chọn người mục tiêu, đặc trưng, làm mượt, chất lượng quan sát (→ F13).
- State machine và các trạng thái khác ngoài khởi tạo (→ F14).
- Rule sự kiện, debounce (→ F15, F17, F23, F26).
- Adapter MediaPipe (→ F11); replay (→ F12).
- Enum DB `event_code`, `priority` và test so khớp với DB (→ F17).
- Text tiếng Việt của sự kiện (`vi.ts`) (→ F20, F22).

## 3. Yêu cầu chi tiết

- **R1.** Schema theo event-engine.md §2, dùng Pydantic v2 `BaseModel` với `ConfigDict(frozen=True)` *(coding-standards.md §2)*:
  - `FrameObservation`: `camera_id`, `frame_index`, `ts_ms` (đơn điệu, theo đồng hồ khung hình), `image_size` (width, height), `persons: list[PersonPose]`, `face: FaceObservation | None`, `source_ok: bool`;
  - `PersonPose.keypoints: dict[KeypointName, Keypoint]`; `Keypoint`: `x`, `y` ∈ [0, 1] (chuẩn hóa theo khung hình), `visibility` ∈ [0, 1];
  - `FaceObservation`: `status` (`OK` / `NOT_VISIBLE` / `TOO_SMALL` / `LOW_CONFIDENCE`), `head_box_px`, `blendshapes: dict[str, float]`;
  - `FaceSignals`: tín hiệu mặt đã suy ra theo thời gian, nằm trong `BodyStateSnapshot.face_signals` *(overview.md §3 gọi tên `FaceSignals`; event-engine.md §2 gọi đầu vào là `FaceObservation`; giả định: giữ cả hai, `FaceObservation` là đầu vào từ adapter, `FaceSignals` là đầu ra của engine)*. F10 chỉ khai báo cấu trúc rỗng hoặc tối thiểu; F26 điền trường.
  - `BodyStateSnapshot`: `body_state`, `observation_quality`, `activity_level`, `rest_status`, `face_status`, `face_signals`;
  - `EngineEvent`: `code`, `priority`, `occurred_at_ms`, `detected_at_ms`, `confidence`, `observation_quality`, `explanation` (dict, luôn có `rule_id`);
  - `EngineOutput`: `state`, `state_changed`, `events`.
- **R2.** Enum *(glossary.md; event-engine.md §4, §5; data-model.md)*:
  - `BodyState`: `LYING`, `RAISING`, `SITTING`, `AT_EDGE`, `STANDING`, `OUT_OF_BED`, `NO_OBSERVATION`;
  - `ObservationQuality`: `GOOD`, `LOW_CONFIDENCE`, `MULTIPLE_PEOPLE`, `NO_PERSON`, `CAMERA_ISSUE`;
  - `Priority`: `LOG`, `INFO`, `MEDIUM`, `HIGH` *(QA#17)*;
  - `EventCode`: đủ 14 mã của catalog event-engine.md §5;
  - `ActivityLevel` (`LOW`, `NORMAL`, `HIGH`), `RestStatus` (`RESTING`, `ACTIVE`, `UNKNOWN`), `FaceStatus` (như `FaceObservation.status`) *(event-engine.md §5 "Trạng thái hiển thị")*.
  - Enum dùng `StrEnum`, giá trị IN HOA *(api-conventions.md "Enum")*.
- **R3.** `KeypointName` là danh sách tên trung lập với model *(event-engine.md §2; PDF §10)*: `nose`, `left_eye`, `right_eye`, `left_ear`, `right_ear`, `left_shoulder`, `right_shoulder`, `left_elbow`, `right_elbow`, `left_wrist`, `right_wrist`, `left_hip`, `right_hip`, `left_knee`, `right_knee`, `left_ankle`, `right_ankle`, `left_heel`, `right_heel`, `left_foot_index`, `right_foot_index` *(giả định: 17 điểm kiểu COCO + gót + mũi bàn chân; đủ cho các đặc trưng ở event-engine.md §3 và ánh xạ được từ MediaPipe; RTMPose bản toàn thân cũng có các điểm này)*.
- **R4.** JSON round-trip: `Model.model_validate_json(x.model_dump_json()) == x` cho mọi schema ở R1 *(event-engine.md §2; testing.md §2 "Fixture từ video thật")*. Đây là định dạng của `observations.jsonl` (F12) và fixture test.
- **R5.** Catalog ở `postcare/schemas/events.py`: mỗi `EventCode` có `default_priority` và `creates_alert` (true khi MEDIUM/HIGH) *(event-engine.md §5: "Nguồn sự thật trong code là `postcare/schemas/events.py`"; QA#17)*. Với `FACE_ATTENTION`, mức mặc định là `MEDIUM`; việc nâng lên `HIGH` do rule F26 quyết định.
- **R6.** Có test so catalog trong code với bảng §5 của `docs/02-architecture/event-engine.md` (đọc file Markdown, lấy cột Code và mã mức ưu tiên đầu tiên của cột Priority) *(event-engine.md §5: "F10 có test kiểm tra")*.
- **R7.** `EngineConfig` *(QA#22; event-engine.md §6)*:
  - model Pydantic khớp cấu trúc `config/engine.default.yaml` (`version`, `pose`, `quality`, `target`, `smoothing`, `posture`, `location`, `min_duration_s`, `posture_change`, `debounce`, `activity`, `abnormal_movement`, `face`, `rest`);
  - `EngineConfig.load(path, overrides=None)` đọc YAML, hợp nhất sâu override theo camera (`cameras.thresholds` hoặc `config/cameras/<setup>.yaml`), rồi validate;
  - sai kiểu, thiếu khóa bắt buộc, hoặc **khóa lạ** → lỗi rõ ràng nêu đường dẫn khóa (ví dụ `posture.sitting_enter_deg`) *(giả định: cấm khóa lạ để bắt lỗi gõ nhầm)*;
  - `config_hash()`: sha256 của cấu hình đã hợp nhất ở dạng JSON chuẩn (khóa sắp xếp, không khoảng trắng thừa) *(event-engine.md §6)*.
- **R8.** Vị trí `EngineConfig`: `postcare/schemas/engine_config.py`, để `engine`, `worker`, `replay` và `api` (F08 kiểm tra override) cùng dùng *(giả định: `api` không được import `engine`, overview.md §3)*. Việc đọc YAML cần PyYAML trong `schemas`; cập nhật cột "Được import" của `schemas` trong overview.md cùng PR *(giả định)*.
- **R9.** `Engine(config: EngineConfig, roi: RoiPolygon)` và `Engine.process(obs: FrameObservation) -> EngineOutput` là API duy nhất mà worker và replay gọi *(event-engine.md §3; giả định: ROI truyền vào lúc khởi tạo vì `FrameObservation` không chứa ROI)*.
- **R10.** Trạng thái khởi tạo là `NO_OBSERVATION` *(event-engine.md §4)*. Ở F10:
  - observation không có người (`persons = []`) → `body_state = NO_OBSERVATION`, `observation_quality = NO_PERSON`, `events = []`;
  - `source_ok = false` → `NO_OBSERVATION`, `CAMERA_ISSUE` *(giả định)*;
  - các bước pipeline (event-engine.md §3) là các hàm/lớp rỗng có chữ ký sẵn để F13–F27 điền.
- **R11.** Engine xác định và không đọc đồng hồ hệ thống: chỉ dùng `obs.ts_ms` *(event-engine.md §1; AGENTS.md quy tắc 5)*. `ts_ms` không tăng ngặt so với observation trước → `ValueError` rõ ràng *(giả định)*.
- **R12.** mypy strict chạy xanh cho `postcare.schemas` và `postcare.engine` trong `make typecheck` *(coding-standards.md §2)*. Import-linter của F00 vẫn xanh.
- **R13.** `config/engine.default.yaml` đúng nội dung event-engine.md §6, có `version: 1` *(event-engine.md §6)*.

## 4. Thiết kế liên quan

- **Module / file dự kiến:**
  - `server/src/postcare/schemas/observation.py` (`FrameObservation`, `PersonPose`, `Keypoint`, `KeypointName`, `FaceObservation`).
  - `server/src/postcare/schemas/state.py` (`BodyState`, `ObservationQuality`, `ActivityLevel`, `RestStatus`, `FaceStatus`, `FaceSignals`, `BodyStateSnapshot`).
  - `server/src/postcare/schemas/events.py` (`EventCode`, `Priority`, `EVENT_CATALOG`, `EngineEvent`, `EngineOutput`).
  - `server/src/postcare/schemas/engine_config.py` (`EngineConfig`, `load`, `config_hash`).
  - `server/src/postcare/schemas/roi.py` (`RoiPolygon`; dùng chung với F08).
  - `server/src/postcare/engine/engine.py` (`Engine`), `engine/pipeline.py` (khai báo các bước) *(giả định tên file)*.
  - `server/tests/schemas/test_roundtrip.py`, `test_catalog_matches_doc.py`, `test_engine_config.py`; `server/tests/engine/test_engine_core.py`.
  - `config/engine.default.yaml`.
- **Dữ liệu:** không có bảng mới.
- **API:** không có endpoint mới.
- **UI:** không có.
- **Cấu hình:** `config/engine.default.yaml` (xem [event-engine.md §6](../02-architecture/event-engine.md#6-cấu-hình-và-ngưỡng-mặc-định)).

## 5. Acceptance criteria

- [ ] **AC1.** `postcare/schemas` có `FrameObservation`, `PersonPose` (keypoint có tên trung lập, toạ độ chuẩn hóa, visibility), `FaceObservation`, `FaceSignals`, `EngineOutput`, `EventCode`, `Priority`; mọi schema JSON round-trip đúng. *(PDF §10)* — *Kiểm chứng:* test `test_frame_observation_roundtrip`, `test_engine_output_roundtrip`, `test_keypoint_rejects_out_of_range`.
- [ ] **AC2.** `EngineConfig.load()` đọc `config/engine.default.yaml` và override theo camera; sai kiểu hoặc khóa lạ → lỗi rõ ràng có đường dẫn khóa; `config_hash` ổn định. *(QA#22)* — *Kiểm chứng:* test `test_load_default_config`, `test_override_deep_merge`, `test_wrong_type_error_mentions_key`, `test_unknown_key_rejected`, `test_config_hash_stable_and_changes_with_override`.
- [ ] **AC3.** `Engine.process(obs)` với observation không có người → trạng thái `NO_OBSERVATION`, chất lượng `NO_PERSON`, không có sự kiện. *(PDF §4.3 (tr.6))* — *Kiểm chứng:* test `test_empty_observation_gives_no_observation`, `test_source_not_ok_gives_camera_issue`, `test_engine_is_deterministic`, `test_non_increasing_ts_raises`.
- [ ] **AC4.** Catalog `EventCode → Priority` khớp bảng §5 của event-engine.md (có test). mypy strict xanh cho `schemas` và `engine`. *(event-engine.md §5; coding-standards.md §2)* — *Kiểm chứng:* test `test_catalog_matches_event_engine_doc`, `test_creates_alert_only_medium_high`; lệnh `make typecheck`.

## 6. Kế hoạch test

| AC | Loại test | Tên / mô tả | Ca âm tính |
|---|---|---|---|
| AC1 | unit | `test_roundtrip.py` cho từng schema | Toạ độ ngoài [0, 1] hoặc visibility âm → `ValidationError`; tên keypoint lạ → lỗi |
| AC2 | unit | `test_engine_config.py` | Sai kiểu, khóa lạ, thiếu khóa → lỗi nêu đường dẫn khóa; override rỗng giữ nguyên hash |
| AC3 | unit | `test_engine_core.py` | `ts_ms` không tăng → `ValueError`; chạy 2 lần cùng chuỗi → output giống hệt |
| AC4 | unit + lệnh | `test_catalog_matches_doc.py`; `make typecheck` | Thêm tạm một mã không có trong doc → test đỏ |

## 7. Giả định

- *(giả định)* Giữ cả `FaceObservation` (đầu vào từ adapter) và `FaceSignals` (tín hiệu engine suy ra, trong state).
- *(giả định)* Tập `KeypointName` ở R3.
- *(giả định)* `EngineConfig` đặt ở `postcare/schemas/engine_config.py` và dùng PyYAML; cập nhật overview.md cùng PR.
- *(giả định)* `EngineConfig` cấm khóa lạ.
- *(giả định)* ROI truyền vào `Engine` lúc khởi tạo; đổi ROI thì worker tạo `Engine` mới.
- *(giả định)* `source_ok = false` → `CAMERA_ISSUE`.
- *(giả định)* `ts_ms` không tăng ngặt → `ValueError`.
- *(giả định)* Test catalog đọc trực tiếp bảng Markdown trong `docs/02-architecture/event-engine.md`.
- *(giả định, F10 plan)* Engine nhận `EngineContext(camera_id, roi_polygon)` lúc khởi tạo, đúng tên ở event-engine.md §2 (R9 gọi là `roi: RoiPolygon`). `obs.camera_id` khác `context.camera_id` → `ValueError`.
- *(giả định, F10 plan)* `RoiPolygon` ở F10 chỉ kiểm tra ≥3 điểm, toạ độ ∈ [0, 1]. Kiểm tra tự cắt (`validate_roi_polygon`) là của F08.
- *(giả định, F10 plan)* Enum giữ ở `schemas/enums.py` (đã có từ prototype, nhiều module đang import); `schemas/state.py` import lại để không có hai nguồn. `ActivityLevel` giữ thêm `UNKNOWN` theo event-engine.md §5.
- *(giả định, F10 plan)* Giá trị `KeypointName` viết thường (`left_shoulder`), khớp R3 và `pose.required_keypoints` trong YAML; ngoại lệ so với quy ước enum IN HOA.
- *(giả định, F10 plan)* `EngineEvent` kiểm tra `priority` thuộc các mức cho phép của mã trong catalog, `occurred_at_ms ≤ detected_at_ms`, `explanation.rule_id` là chuỗi không rỗng.
- *(giả định, F10 plan)* Khi có người trong khung hình mà chưa có F13, chất lượng tạm là `LOW_CONFIDENCE` và trạng thái giữ `NO_OBSERVATION` (không bao giờ kết luận khi chưa đủ căn cứ). F13 thay bước này.
- *(giả định, F10 plan)* `state_changed = true` ở output đầu tiên của một instance `Engine` (để worker gửi trạng thái ban đầu), sau đó `true` khi `BodyStateSnapshot` khác lần trước.
- *(giả định, F10 plan)* `EngineConfig` dùng chế độ strict của Pydantic (không ép `"55"` thành số); lỗi gói trong `EngineConfigError(ValueError)` có đường dẫn khóa dạng `posture.sitting_enter_deg`.
- *(giả định, F10 plan)* F10 chưa cần numpy nên chưa thêm; F13 thêm khi tính đặc trưng.

## 8. Câu hỏi mở

- (Không)

## 9. Kế hoạch triển khai

Khảo sát: `schemas/enums.py` đã có `BodyState`, `ObservationQuality`, `ActivityLevel`, `RestStatus`, `FaceStatus`, `Priority`; `schemas/events.py` đã có `EventCode`, `EVENT_CATALOG` (`EventSpec.allowed_priorities`, `api_generated`), `ALERT_PRIORITIES`, `default_priority()` và đang được `domain`, `db`, `api`, `cli` import. Giữ nguyên API cũ, chỉ thêm. `config/engine.default.yaml` đã khớp event-engine.md §6 (`test_tooling.py` kiểm tra). overview.md §3 đã ghi `schemas` được import pyyaml.

1. **Phụ thuộc:** chuyển `pyyaml` từ nhóm dev sang `dependencies` trong `server/pyproject.toml`, `uv lock`; cập nhật tech-stack.md. Commit `build(F10): move pyyaml to main dependencies`.
2. **Test trước (đỏ):** `server/tests/schemas/__init__.py`, `test_roundtrip.py` (`test_frame_observation_roundtrip`, `test_engine_output_roundtrip`, round-trip `FaceObservation`/`FaceSignals`/`BodyStateSnapshot`/`EngineEvent`/`RoiPolygon`/`EngineContext`; âm tính: `test_keypoint_rejects_out_of_range`, tên keypoint lạ, visibility âm, blendshape > 1, priority không hợp lệ cho mã, thiếu `rule_id`, schema frozen); `test_engine_config.py` (`test_load_default_config`, `test_override_deep_merge`, `test_wrong_type_error_mentions_key`, `test_unknown_key_rejected`, `test_missing_key_rejected`, `test_config_hash_stable_and_changes_with_override`, hash bỏ qua `privacy.*`, override rỗng giữ hash, override từ file YAML); `test_catalog_matches_doc.py` (`test_catalog_matches_event_engine_doc`, `test_creates_alert_only_medium_high`, đủ 14 mã); `server/tests/engine/__init__.py`, `test_engine_core.py` (`test_empty_observation_gives_no_observation`, `test_source_not_ok_gives_camera_issue`, `test_engine_is_deterministic`, `test_non_increasing_ts_raises`, `test_engine_does_not_read_clock`, `test_persons_without_f13_stay_no_observation`, `test_state_changed_only_when_snapshot_changes`, `test_camera_id_mismatch_raises`). Chạy pytest, xác nhận đỏ vì thiếu module/kiểu. Commit `test(F10): add failing tests for schemas, config and engine core`.
3. **Schema:** `schemas/observation.py` (`KeypointName`, `Keypoint`, `PersonPose`, `FaceObservation`, `FrameObservation`), `schemas/state.py` (`FaceSignals`, `BodyStateSnapshot`, import lại enum), `schemas/roi.py` (`RoiPolygon`), `schemas/events.py` (thêm `EventSpec.default_priority`, `creates_alert`, `EngineEvent`, `EngineOutput`), `schemas/context.py` (`EngineContext`). Commit `feat(F10): add observation, state and event schemas`.
4. **Cấu hình:** `schemas/engine_config.py` (`EngineConfig` + model con theo từng khối YAML, `extra="forbid"`, strict; `load(path, overrides)` với deep merge, `EngineConfigError`, `config_hash()` bỏ `privacy`). Commit `feat(F10): load and hash engine config`.
5. **Engine:** `engine/pipeline.py` (bước rỗng có chữ ký: `TargetSelector` F13, `QualityAssessor` F13, `StateMachine` F14, `RuleSet` F15+), `engine/engine.py` (`Engine(config, context)`, `process(obs)`, kiểm tra `ts_ms` tăng ngặt và `camera_id`), `engine/__init__.py` xuất `Engine`. Commit `feat(F10): add engine skeleton with process()`.
6. **Doc:** event-engine.md §2 (tên kiểu, `RoiPolygon`, quy tắc `ts_ms`, `state_changed`, `EngineConfigError`), §3 (`engine/pipeline.py`); overview.md §3 nếu lệch. Commit `docs(F10): …`.
7. **Kiểm chứng:** `make check` và `scripts\dev.ps1 check` exit 0; ghi bằng chứng §10, tick AC.

Không có migration, endpoint, `make gen-api-types`. Rủi ro: mypy strict với plugin pydantic cho model frozen chứa dict; khóa `min_duration_s` IN HOA (tên trường trùng tên trạng thái) có thể vướng ruff `N815` — dùng alias nếu cần.

## 10. Ghi chú bàn giao

> Ghi kết quả kiểm chứng thủ công, kết quả review, ngày hoàn thành, điều người sau cần biết.

## 11. Definition of Done

- [ ] Mọi AC đã tick, kèm bằng chứng (test hoặc ghi chú kiểm chứng).
- [ ] `make check` xanh; với feature vision đã chạy `make test-vision` hoặc replay.
- [ ] Doc liên quan đã cập nhật cùng PR.
- [ ] Review theo [review.md](../ai/workflows/review.md): Đạt.
- [ ] `docs/progress/` đã cập nhật ([update-progress.md](../ai/workflows/update-progress.md)).
