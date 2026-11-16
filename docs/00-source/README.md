# Nguồn yêu cầu

Thư mục này chứa tài liệu gốc của đề tài. **Không sửa nội dung các file nguồn.** Mọi diễn giải hoặc quyết định được ghi ở `docs/01-product/` và `docs/02-architecture/`.

## Danh sách file

| File | Nội dung | Ký hiệu khi trích dẫn |
|---|---|---|
| [ho-so-so-loai-2026.md](ho-so-so-loai-2026.md) | Hồ sơ ý tưởng vòng sơ loại DANANG AI4LIFE 2026, bản mới nhất của nhóm | **HS §x** (theo số mục) |
| [de-tai.pdf](de-tai.pdf) | Báo cáo ý tưởng AI for Life, bản gốc 21 trang | **PDF §x (tr.y)** |
| [de-tai.md](de-tai.md) | Bản Markdown của PDF, có dấu `<!-- Trang N -->` | dùng chung ký hiệu PDF |
| [conflicts.md](conflicts.md) | Các điểm khác nhau giữa PDF và HS, kèm cách giải quyết | — |
| [assets/](assets/) | Hình tham khảo bố trí camera do nhóm cung cấp | — |

Câu trả lời cho 30 câu hỏi làm rõ nằm ở [../01-product/qa-decisions.md](../01-product/qa-decisions.md), ký hiệu **QA#n**.

## Thứ tự ưu tiên khi xung đột

1. **HS**: hồ sơ sơ loại (bản mới nhất).
2. **PDF**: báo cáo ý tưởng.
3. **QA#n**: quyết định đã ghi trong `qa-decisions.md`.
4. Suy luận của người viết tài liệu. **Bắt buộc gắn nhãn *(giả định)***.

## Quy tắc trích dẫn

- Mỗi yêu cầu trong PRD hoặc spec feature phải ghi ít nhất một nguồn: `HS §5.2`, `PDF §7.2 (tr.9)` hoặc `QA#16`.
- Yêu cầu không có nguồn thì phải ghi *(giả định)* và nêu lý do.
- Ghi chú về chất lượng nguồn:
  - Các khối `<!-- Start of picture text -->` trong HS là chữ OCR từ hình, bị lỗi dấu. Chỉ dùng phần chú thích hình (*Hình 1–3*) làm nguồn.
  - Các bảng trang 10, 15, 19 trong `de-tai.md` đã được dựng lại. Nếu nghi ngờ, đối chiếu với PDF.
