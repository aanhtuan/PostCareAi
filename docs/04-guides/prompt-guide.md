# Hướng dẫn prompt cho AI agent

Các prompt mẫu dưới đây copy và dùng được với **mọi AI tool** (Claude Code, Codex, Cursor, Copilot, Gemini CLI). Thay `Fxx`, `<…>` bằng giá trị thật.

> **Nguyên tắc chung:**
> - Luôn bắt đầu bằng "Đọc AGENTS.md".
> - Mỗi phiên chỉ làm **một** feature, **một** bước.
> - Luôn kết thúc phiên bằng prompt cập nhật tiến độ (mục 6).

## 1. Bắt đầu một phiên mới

Dùng ở đầu mọi phiên, nhất là khi đổi sang AI khác:

```text
Đọc AGENTS.md, docs/progress/TASKS.md và entry mới nhất trong docs/progress/session-log.md.
Tóm tắt cho tôi: đang làm feature nào, đang ở bước nào, bước tiếp theo là gì, có blocker không.
Chưa sửa file nào.
```

## 2. Thêm feature mới (chưa có trong F00–F35)

### 2.1. Tạo spec (chưa code)

```text
Đọc AGENTS.md, docs/01-product/PRD.md, docs/03-features/README.md và docs/progress/ROADMAP.md.

Tôi muốn thêm feature mới: <mô tả ý tưởng, ai dùng, giải quyết việc gì>.

Hãy làm theo thứ tự:
1. Kiểm tra ý tưởng có trùng với spec nào sẵn có không (kể cả F31–F35). Nếu trùng, đề xuất mở rộng spec đó rồi dừng.
2. Kiểm tra có thuộc mục "Ngoài phạm vi" của PRD không. Nếu có, giải thích và dừng.
3. Nếu thiếu thông tin quan trọng (mục tiêu, vai trò dùng, MVP hay sau MVP, tiêu chí hoàn thành), hỏi tôi trước.
4. Tạo spec docs/03-features/F<số tiếp theo>-<slug-tieng-anh>.md theo đúng _TEMPLATE.md:
   - Nguồn: trích HS/PDF nếu có; nếu không thì ghi "Yêu cầu người dùng (<ngày>)"; phần tự suy luận ghi "(giả định)".
   - 3–5 acceptance criteria kiểm chứng được, mỗi AC có cách kiểm chứng.
   - Ghi rõ phụ thuộc, milestone, nhánh code (A/B/C).
   - Mục 4: liệt kê doc kiến trúc cần cập nhật khi triển khai (data-model, api-conventions, event-engine, tech-stack, ADR).
   - Mục 9, 10 để trống; Trạng thái: Todo.
5. Thêm 1 dòng vào docs/03-features/README.md, docs/progress/ROADMAP.md, và Backlog trong docs/progress/TASKS.md.
6. Ghi entry vào docs/progress/session-log.md.

KHÔNG viết code. Dừng lại và tóm tắt spec để tôi duyệt.
```

### 2.2. Sửa spec sau khi review

```text
Sửa spec docs/03-features/Fxx-*.md theo góp ý sau: <góp ý>.
Giữ đúng cấu trúc _TEMPLATE.md; cập nhật lại mục Giả định và Câu hỏi mở nếu cần. Không viết code.
```

Spec được duyệt thì làm tiếp theo mục 3 như một feature có sẵn.

## 3. Làm một feature đã có spec

Mỗi bước nên chạy trong **một phiên riêng**. Với Claude Code, có thể dùng lệnh tắt ở cột phải.

| Bước | Prompt | Claude Code |
|---|---|---|
| Plan | mục 3.1 | `/plan-feature Fxx` |
| Implement | mục 3.2 | `/implement-feature Fxx` |
| Review | mục 3.3 | `/review Fxx` |
| Cập nhật tiến độ | mục 6 | `/update-progress Fxx` |

### 3.1. Lập kế hoạch

```text
Đọc AGENTS.md rồi làm đúng theo docs/ai/workflows/plan-feature.md cho Fxx,
với vai trò trong docs/ai/roles/planner.md.
Kiểm tra mọi phụ thuộc đã Done trong ROADMAP. Nếu chưa thì dừng và báo tôi.
Chỉ ghi vào mục "Kế hoạch triển khai" của spec và docs/progress/. Không viết code.
Điểm nào mơ hồ thì hỏi tôi, không tự đoán.
```

### 3.2. Triển khai

```text
Đọc AGENTS.md rồi làm đúng theo docs/ai/workflows/implement-feature.md cho Fxx.
Làm theo "Kế hoạch triển khai" trong spec, từng bước một:
viết test trước (theo docs/ai/roles/test-writer.md), rồi code, rồi chạy make check, rồi commit nhỏ.
Không làm gì ngoài spec. Cần thêm thư viện hoặc đổi phạm vi thì hỏi tôi trước.
```

### 3.3. Review (nên dùng phiên khác hoặc AI khác)

```text
Đọc AGENTS.md rồi làm đúng theo docs/ai/workflows/review.md cho Fxx,
với vai trò trong docs/ai/roles/code-reviewer.md.
Chạy make check, xem git diff main...HEAD, đối chiếu từng acceptance criteria và checklist.
Không sửa code. Ghi kết quả vào mục "Ghi chú bàn giao" của spec và kết luận Đạt hoặc Cần sửa.
```

### 3.4. Sửa theo review

```text
Đọc mục "Ghi chú bàn giao" trong spec Fxx, sửa từng vấn đề reviewer đã ghi.
Mỗi vấn đề: thêm hoặc sửa test chứng minh đã sửa, chạy make check, commit.
```

## 4. Sửa lỗi (bug)

```text
Đọc AGENTS.md. Lỗi: <mô tả, cách tái hiện, kết quả mong đợi, kết quả thực tế>.
Feature liên quan: Fxx.
1. Tìm nguyên nhân và báo cho tôi trước khi sửa.
2. Viết test tái hiện lỗi (phải fail), sửa code cho test pass, chạy make check.
3. Commit dạng fix(Fxx): <mô tả>, ghi entry vào session-log.
Không sửa gì ngoài phạm vi lỗi.
```

## 5. Hỏi đáp, không sửa file

```text
Đọc AGENTS.md và các doc liên quan. Trả lời câu hỏi: <câu hỏi>.
Trích đường dẫn file làm căn cứ. Không sửa file nào.
```

Ví dụ câu hỏi: "Sự kiện BED_EXIT được sinh ra theo điều kiện nào?", "Feature nào nên làm tiếp?".

## 6. Kết thúc phiên / bàn giao (bắt buộc)

```text
Làm theo docs/ai/workflows/update-progress.md cho Fxx:
cập nhật spec, docs/progress/ROADMAP.md, TASKS.md và thêm entry vào session-log.md
(đã làm gì, đang dở gì, bước tiếp theo cụ thể tới mức lệnh, blocker).
Commit phần tài liệu.
```

## 7. Mẹo để AI làm đúng

- **Nói rõ bước:** "chỉ plan, không code" hoặc "chỉ review, không sửa". AI hay làm quá phần được giao.
- **Một feature mỗi lần.** Feature lớn hơn 3 phiên thì yêu cầu AI tách thành 2 spec.
- **Đòi bằng chứng:** "Cho tôi xem kết quả make check" thay vì tin câu "đã xong".
- **Khi AI tự thêm yêu cầu:** hỏi "Yêu cầu này có nguồn ở đâu (HS/PDF/QA)?". Không có nguồn thì phải ghi *(giả định)* hoặc bỏ đi.
- **Khi đổi AI giữa chừng:** luôn chạy prompt ở mục 1 trước.
- **Tránh** prompt mơ hồ kiểu "làm tiếp đi" hay "code hết phần còn lại". Hãy nêu mã feature và bước cụ thể.
