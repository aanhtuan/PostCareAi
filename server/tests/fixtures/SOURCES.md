# Nguồn fixture

Fixture chỉ chứa toạ độ keypoint (`FrameObservation`, F12), không có ảnh hay video.

| Fixture | Nguồn | Giấy phép |
|---|---|---|
| `synthetic_sit_occluded` | Tổng hợp bằng builder (`tests/engine/builders.py`) | Của dự án |
| `gmd_s1_fall12_abnormal_movement` | GMDCSA24, Subject 1, `Fall/12.mp4` (pose MediaPipe, F23) | MIT |
| `gmd_s1_adl06_sit_read_negative` | GMDCSA24, Subject 1, `ADL/06.mp4` (pose MediaPipe, F23) | MIT |

GMDCSA24: Ekram Alam và cộng sự, "GMDCSA24: A Dataset for Human Fall Detection in Videos",
https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos
(bản Zenodo https://zenodo.org/records/12921216). Phát hành theo giấy phép MIT; khi phân phối
lại phải giữ thông báo bản quyền và giấy phép MIT của tác giả (xem `docs/04-guides/datasets.md`).
