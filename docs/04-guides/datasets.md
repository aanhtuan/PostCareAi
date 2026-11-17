# Dữ liệu ngoài cho phát triển và kiểm thử

Nguồn: HS §7.2, §8.1; PDF §13. Liên quan: [evaluation.md](evaluation.md) (§3 bộ kịch bản, §4 định dạng file, §8 dữ liệu ngoài).

Mục đích: có video của **nhiều tình huống khác nhau** để chạy replay và eval **trong lúc nhóm chưa quay tình nguyện viên**. Dữ liệu ngoài **không thay thế** tập đánh giá chính thức (evaluation.md §1, §6) và **không dùng để train model** (AGENTS.md, quy tắc 2).

## 1. Quy tắc chung

- Mọi file tải về nằm trong `data/external/<nguồn>/` (gitignore). **Không commit** video, ảnh, archive.
- `data/external/SOURCES.md` (chỉ ở máy, không commit) ghi cho từng file/thư mục: URL nguồn, giấy phép, được trình chiếu hay không, ngày tải.
- `data/eval/manifest.csv` và `data/eval/truth.csv` (không commit) có thêm cột nguồn và nguồn nhãn, xem [evaluation.md §8](evaluation.md#8-dữ-liệu-ngoài).
- Chỉ giải nén và đọc file. **Không chạy** bất kỳ script hay chương trình nào đi kèm archive.
- Video stock (Pexels, Mixkit) là **diễn viên**, không phải bệnh nhân. Khi chiếu trong slide/demo phải ghi rõ trên màn hình: **"Stock footage – diễn viên"**.
- Kết quả đánh giá trên dữ liệu ngoài phải ghi rõ nguồn nhãn (`dataset` hay `manual`) và tên dataset. Không gộp chung với kết quả trên tập quay của nhóm.

## 2. Bảng nguồn

| Nguồn | URL | Giấy phép | Trình chiếu công khai | Phần đã tải | Kích thước | Split |
|---|---|---|---|---|---|---|
| URFD (UR Fall Detection) | https://fenix.ur.edu.pl/~mkepski/ds/uf.html | CC BY-NC-SA 4.0 | Được, kèm ghi nguồn, phi thương mại | 30 ngã × 2 camera (cam0 ngang, cam1 trần) + 40 ADL cam0, bản xem trước mp4; CSV gia tốc, `fall-XX-data.csv`, `urfall-cam0-*.csv` | ~118 MB gốc + ~20 MB bản cắt RGB | dev |
| GMDCSA24 | https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos , bản Zenodo https://zenodo.org/records/12921216 | MIT | Được, kèm ghi nguồn (giữ thông báo MIT) | Toàn bộ v2.0: 4 người, 79 ngã + 81 ADL; `Fall.csv`/`ADL.csv` có mốc thời gian lấy từ GitHub | 1,1 GB zip + 1,1 GB giải nén | Subject 1–2: dev; Subject 3–4: test |
| CAUCAFall | https://data.mendeley.com/datasets/7w7fccy7ky (v5) | CC BY 4.0 | Được, kèm ghi nguồn | 100 video `.avi` (10 người × 10 hoạt động) + nhãn txt từng frame của 50 video ngã + `Dataset details.xlsx` | ~141 MB | test |
| Pexels (stock) | https://www.pexels.com/license/ | Pexels License | Được, ghi "Stock footage – diễn viên" (nên ghi tên tác giả) | 14 clip 720p | ~57 MB | 9 dev, 5 test |
| Mixkit (stock) | https://mixkit.co/license/#videoFree | Mixkit Stock Video Free License | Được, ghi "Stock footage – diễn viên" | 5 clip 720p | ~25 MB | test |
| Le2i | https://imvia.ube.fr/?p=346 | Không rõ | **KHÔNG** (chỉ dev nội bộ, nếu có) | **Không tải**: trang gốc chờ link mới; mirror Hugging Face chỉ có frame trích hoặc nhãn, không có video | 0 | — |

Tổng dung lượng trên đĩa: khoảng 2,5 GB, gồm cả bản giải nén (dưới mức 6 GB đặt ra). Lượng tải về khoảng 1,4 GB.

### Phần bỏ qua có chủ đích

- URFD: không tải các zip PNG độ phân giải đầy đủ (`*-cam0-rgb.zip`, `*-cam1-rgb.zip`, ~60 MB mỗi file, ~6 GB tổng) và zip depth (`*-d.zip`). Bản mp4 xem trước đã đủ cho replay ở 320×240.
- CAUCAFall: không tải ~20.000 ảnh PNG (8,2 GB) và nhãn txt của video ADL (toàn lớp "no-fall"). Video `.avi` đã chứa cùng nội dung.

## 3. Cách tải lại (cho thành viên khác)

Chạy trong Git Bash (Windows) hoặc bash (Linux), từ thư mục gốc repo. Cần `curl` và Python 3. Mỗi nguồn một thư mục mới.

### 3.1 URFD

```bash
mkdir -p data/external/urfd && cd data/external/urfd
curl -sL https://fenix.ur.edu.pl/~mkepski/ds/uf.html -o /tmp/urfd.html
grep -oE '"\./data/[^"]+"' /tmp/urfd.html | tr -d '"' | sort -u | grep -vE '\.zip$' \
  | sed 's#^\./#https://fenix.ur.edu.pl/~mkepski/ds/#' > /tmp/urfd_urls.txt
xargs -P 6 -n 1 curl -sfL --retry 3 -O < /tmp/urfd_urls.txt   # 242 file
cd ../../..
```

Mỗi mp4 rộng 640×240: **nửa trái là ảnh depth, nửa phải là RGB 320×240**. Trước khi replay, cắt lấy nửa phải (x từ 320 đến 640) vào `data/external/urfd/rgb_crop/<tên>-rgb.mp4`, ví dụ bằng OpenCV (`frame[:, 320:640]`, giữ 30 fps). Có thể chạy tạm qua `uv run --no-project --with opencv-python-headless python <script>`; không thêm OpenCV vào phụ thuộc dự án chỉ vì bước này.

### 3.2 GMDCSA24

```bash
mkdir -p data/external/gmdcsa24 && cd data/external/gmdcsa24
curl -fL --retry 3 -o GMDCSA24-v2.0.zip \
  "https://zenodo.org/records/12921216/files/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos-v2.0.zip?download=1"
# kiểm tra: 1.107.543.412 byte
mkdir -p extracted && unzip -q GMDCSA24-v2.0.zip -d extracted
cd ../../..
```

CSV trong zip Zenodo v2.0 **không có mốc thời gian** của từng lớp. Bản CSV trên nhánh `master` của GitHub (commit `5abac76`, 2024-08-21) có cột `Classes`, ví dụ `Falling (SW)[3.4 to 6]; Sitting[0 to 3.4]`. Tải riêng 8 file này:

```bash
B=https://raw.githubusercontent.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos/master
for s in 1 2 3 4; do
  mkdir -p "data/external/gmdcsa24/labels_github/Subject $s"
  for k in Fall ADL; do
    curl -sfL -o "data/external/gmdcsa24/labels_github/Subject $s/$k.csv" "$B/Subject%20$s/$k.csv"
  done
done
```

Nhãn gốc có vài lỗi gõ: `Subject 4/Fall.csv` dòng `09.mp4` viết `[2.3 6]` (thiếu `to`), dòng `15.mp4` thiếu khoảng của lớp Falling (truth dùng thời điểm kết thúc lớp Sitting trước đó, 1,7 s).

### 3.3 CAUCAFall

Mendeley không có một file zip duy nhất. Lấy danh sách file từ API công khai rồi tải bằng curl (Python `urllib` bị chặn 403, curl thì không):

```bash
mkdir -p data/external/caucafall
curl -s "https://data.mendeley.com/public-api/datasets/7w7fccy7ky" -o /tmp/cauca.json
python -I - /tmp/cauca.json data/external/caucafall > /tmp/cauca_curl.cfg <<'EOF'
import json, re, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); out = sys.argv[2]
avi = {f["folder_id"]: f["filename"] for f in d["files"] if f["filename"].endswith(".avi")}
for f in d["files"]:
    fn, fid, url = f["filename"], f.get("folder_id"), f["content_details"]["download_url"]
    p = None
    if fn.endswith(".avi"):
        m = re.match(r"(.+?)S(\d+)\.avi", fn); p = f"{out}/Subject{m[2]}/{m[1]}/{fn}"
    elif fn.endswith(".txt") and avi.get(fid, "").startswith("Fall"):
        m = re.match(r"(.+?)S(\d+)\.avi", avi[fid]); p = f"{out}/Subject{m[2]}/{m[1]}/labels/{fn}"
    elif fn.endswith(".xlsx"):
        p = f"{out}/{fn}"
    if p:
        print(f'url = "{url}"\noutput = "{p}"')
EOF
curl -sL --create-dirs --parallel --parallel-max 24 --retry 3 -K /tmp/cauca_curl.cfg   # 9.820 file
```

Nhãn: mỗi frame một file txt dạng YOLO `lớp cx cy w h`; lớp `1` = fall, `0` = no-fall. Video 720×480, 20 fps.

### 3.4 Stock footage (Pexels, Mixkit)

Trang Pexels chặn client không giống trình duyệt; dùng `curl -A "Mozilla/5.0"`. Link file trực tiếp (bản 720p) đã dùng:

```bash
mkdir -p data/external/pexels data/external/mixkit
for u in \
  6010961/6010961-hd_1280_720_25fps 6130226/6130226-hd_720_1280_30fps \
  9902443/9902443-hd_1366_720_25fps 6010768/6010768-hd_1280_720_25fps \
  8090730/8090730-hd_1280_720_24fps 4049556/4049556-hd_1280_720_30fps \
  8090735/8090735-hd_1280_720_24fps 8860232/8860232-hd_1366_720_25fps \
  3753707/3753707-hd_1280_720_50fps 6944081/6944081-hd_1366_720_25fps \
  4052924/4052924-hd_1280_720_50fps 6130026/6130026-hd_1280_720_30fps \
  6130032/6130032-hd_1280_720_30fps 8090346/8090346-hd_1366_720_24fps; do
  id=${u%%/*}
  curl -sfL -A "Mozilla/5.0" -o data/external/pexels/pexels-$id.mp4 \
    "https://videos.pexels.com/video-files/$u.mp4"
done
for id in 48202 5568 29966 5496 5457; do
  curl -sfL -A "Mozilla/5.0" -o data/external/mixkit/mixkit-$id.mp4 \
    "https://assets.mixkit.co/videos/$id/$id-720.mp4"
done
```

Nếu link file đổi, mở trang `https://www.pexels.com/video/<slug>-<id>/` và chọn bản HD 720p.

| File | Trang gốc | Tác giả | Nội dung quan sát | Kịch bản | Split |
|---|---|---|---|---|---|
| pexels-8090735 | pexels.com/video/a-woman-getting-out-of-bed-8090735/ | PNW Production | Nửa nằm → ngồi mép → đứng → đi khỏi (7,7 s) | S06 | dev |
| pexels-8090730 | pexels.com/video/a-person-getting-out-of-bed-8090730/ | PNW Production | Chỉ thấy chân: ngồi mép → đứng → đi khỏi | S06, S10 | dev |
| pexels-3753707 | pexels.com/video/footage-of-a-man-getting-out-of-bed-3753707/ | Ba Tik | Ngồi mép giường thấy qua gương, có thân người tiền cảnh | S04, S08 | dev |
| pexels-4052924 | pexels.com/video/man-waking-up-smiling-walking-away-from-bed-4052924/ | Katrin Bolovtsova | Nằm → ngồi dậy → ngồi mép → đứng → đi khỏi | S06 | dev |
| pexels-6944081 | pexels.com/video/man-having-trouble-sleeping-6944081/ | cottonbro studio | Nằm → ngồi dậy ~40 s → nằm lại, đèn mờ | S03 | dev |
| pexels-8860232 | pexels.com/video/an-elderly-man-sitting-on-a-bed-8860232/ | cottonbro studio | Ngồi tựa đầu giường, tối, bị rèm che | S10, S11 | dev |
| pexels-6130226 | pexels.com/video/a-female-patient-lying-in-a-hospital-bed-6130226/ | RDNE Stock project | Nằm yên, cận cảnh, khung dọc, cầm tay | S01, S13 | dev |
| pexels-6130032 | pexels.com/video/patient-in-hospital-bed-6130032/ | RDNE Stock project | Nằm yên, cận cảnh | S01 | dev |
| pexels-6130026 | pexels.com/video/nurse-checking-the-patient-6130026/ | RDNE Stock project | Điều dưỡng đứng cạnh giường | S09 | dev |
| pexels-4049556 | pexels.com/video/a-woman-getting-out-of-bed-4049556/ | Martina Tomšič | Nằm → ngồi dậy → ngồi mép → đứng → đi khỏi | S06 | test |
| pexels-6010768 | pexels.com/video/a-nervous-person-sitting-on-a-hospital-bed-6010768/ | Tima Miroshnichenko | Ngồi mép giường bệnh suốt clip, nhìn thẳng từ trên | S04 | test |
| pexels-6010961 | pexels.com/video/a-cancer-patient-lying-on-bed-and-female-doctor-by-her-side-6010961/ | Tima Miroshnichenko | Bệnh nhân nửa nằm, bác sĩ bước vào che khuất, camera lia | S09, S10 | test |
| pexels-9902443 | pexels.com/video/a-man-sitting-on-his-bed-9902443/ | Ron Lach | Nhổm dậy khỏi gối rồi ngồi gần camera, đèn mờ | S03 | test |
| pexels-8090346 | pexels.com/video/woman-sitting-on-bed-8090346/ | Yaroslav Shuraev | Ngồi xếp bằng trên giường, không đổi tư thế | âm tính | test |
| mixkit-29966 | mixkit.co/free-stock-video/woman-getting-out-of-bed-in-the-morning-29966/ | Mixkit | Nằm → ngồi dậy, camera di chuyển | S03 | test |
| mixkit-48202 | mixkit.co/free-stock-video/patient-lying-on-a-bed-48202/ | Mixkit | Chỉ thấy mặt nạ oxy, không thấy thân người | S10 | test |
| mixkit-5568 | mixkit.co/free-stock-video/nurse-talks-with-woman-laying-in-hospital-bed-5568/ | Mixkit | Điều dưỡng ngồi cạnh giường | S09 | test |
| mixkit-5496 | mixkit.co/free-stock-video/elderly-woman-laying-on-bed-in-nursing-home-5496/ | Mixkit | Nằm yên, camera lia chậm | S01 | test |
| mixkit-5457 | mixkit.co/free-stock-video/sick-elderly-man-lays-on-hospital-bed-in-home-care-5457/ | Mixkit | Nằm yên | S01 | test |

Đã loại khi chọn: clip có trẻ em hoặc người có thể chưa thành niên ("girl", "young girl") và clip 4K.

### 3.5 Cách sinh `manifest.csv` / `truth.csv`

Quy tắc suy nhãn (để người khác tạo lại cùng kết quả):

| Nguồn | `video_id` | Truth |
|---|---|---|
| URFD | `urfd_fallNN_cam0`, `urfd_fallNN_cam1`, `urfd_adlNN_cam0` | `ABNORMAL_MOVEMENT`: `start_s` = (frame đầu tiên nhãn `0` − 1) / 30, `end_s` = (frame đầu tiên nhãn `1` − 1) / 30, theo `urfall-cam0-falls.csv`. cam1 dùng chung mốc (đồng bộ frame). ADL không có dòng truth. |
| GMDCSA24 | `gmd_s<n>_fall_<NN>`, `gmd_s<n>_adl_<NN>` | `ABNORMAL_MOVEMENT`: `start_s` = `end_s` = đầu khoảng lớp `Fall`/`Falling`. ADL mô tả có "bed" và có `Sleeping[a to b]` trước `Sitting[c to d]` → `SIT_UP` từ `b` đến `c`. |
| CAUCAFall | `cauca_s<NN>_<hoạt động>` | `ABNORMAL_MOVEMENT`: `start_s` = `end_s` = (số frame của file txt đầu tiên có lớp `1` − 1) / 20. Số frame là 5 chữ số cuối tên file. |
| Stock | `stock_pexels_<id>`, `stock_mixkit_<id>` | Gán tay từ contact sheet 1 frame/giây (`label_source=manual`), mốc ở bảng dưới. Clip không có dòng truth là ca âm tính cho các mã trong `eval_codes`. |

Mốc gán tay cho clip stock (giây, `start–end`, sai số khoảng 0,5–1 s):

| Clip | SIT_UP | BED_EDGE | STAND_UP | BED_EXIT |
|---|---|---|---|---|
| pexels-8090735 | 0,5–1,5 | 2,0–4,5 | 4,5–5,5 | 6,0–7,0 |
| pexels-8090730 | — | 5,0–9,5 | 9,5–10,5 | 12,0–13,0 |
| pexels-3753707 | — | 4,0–21,4 | — | — |
| pexels-4052924 | 1,0–3,0 | 20,0–22,5 | 22,5–24,0 | 25,0–26,5 |
| pexels-6944081 | 2,0–4,0 | — | — | — |
| pexels-4049556 | 5,0–6,5 | 7,0–13,5 | 13,5–14,5 | 15,5–16,5 |
| pexels-6010768 | — | 0,0–25,1 | — | — |
| pexels-9902443 | 1,0–3,0 | — | — | — |
| mixkit-29966 | 6,0–9,0 | — | — | — |

Các clip stock còn lại không có sự kiện trong `eval_codes`.

Thời lượng (`duration_s`) đọc bằng OpenCV (số frame / fps).

**Cột `camera_config`** (thêm khi hiệu chỉnh dev 18/11/2026, [calibration-2026-11-18.md](calibration-2026-11-18.md)). Cột cuối của `manifest.csv`, đường dẫn tính từ gốc repo. Gán theo quy tắc sau, chỉ dựa vào `video_id` và `eval_codes`, không dựa vào kết quả eval:

| Dòng manifest | `camera_config` |
|---|---|
| `urfd_*_cam0` (ngã + ADL) | `config/cameras/urfd-cam0.yaml` |
| `urfd_*_cam1` | `config/cameras/urfd-cam1.yaml` |
| `gmd_s1_adl_01` … `gmd_s1_adl_06` (cảnh có giường của Subject 1) | `config/cameras/gmdcsa24-subject1.yaml` |
| `gmd_*` khác có `eval_codes=ABNORMAL_MOVEMENT` (dev và test) | `config/cameras/gmdcsa24-room.yaml` (ROI gần trọn khung) |
| `gmd_*` có `SIT_UP` trong `eval_codes` ở tập test (1 dòng) | để trống: F29 vẽ ROI giường trước khi chạy, không xem kết quả |
| `cauca_*` (test) | `config/cameras/caucafall.yaml` (có từ F23) |
| `stock_pexels_<id>` tập dev | `config/cameras/pexels-<id>.yaml` |
| Clip stock tập test | để trống (eval tự dùng `config/cameras/<tên file video>.yaml` nếu có, ví dụ `mixkit-29966.yaml`) |

ROI của các file `pexels-*.yaml` (dev) vẽ bằng mắt trên khung hình có lưới 0,1 tại các mốc ghi trong comment của từng file *(giả định)*. Không xem khung hình hay kết quả của clip tập test. Bản manifest trước khi thêm cột không đổi ở các cột khác; thêm lại bằng một script nhỏ theo bảng trên.

## 4. Kịch bản được bao phủ

| Kịch bản | Nguồn | Ghi chú |
|---|---|---|
| S01 Nằm yên | Stock (5 clip) | Phần lớn camera cầm tay hoặc lia, không cố định |
| S03 Ngồi dậy rồi nằm lại / không rời giường | Stock (4 clip), GMDCSA24 ADL "sleeping → sitting on the bed" | GMDCSA24 suy SIT_UP từ nhãn lớp |
| S04 Ngồi ở mép giường | Stock (2 clip) | |
| S06 Rời giường | Stock (4 clip) | Góc thấp, ngắn; không phải camera cố định cạnh giường bệnh |
| S08 Người khác / hình phản chiếu | Stock (1 clip) | |
| S09 Điều dưỡng gần giường | Stock (3 clip) | |
| S10 Che khuất / không thấy thân | Stock (4 clip) | |
| S11 Ánh sáng yếu | Stock, CAUCAFall (có cảnh tối, đèn nhân tạo) | |
| S13 Nhắm mắt kéo dài | Stock (1 clip, cận cảnh) | Chưa có nhãn mắt |
| S15 Chuyển động nhanh xuống thấp | URFD (60 video), GMDCSA24 (79), CAUCAFall (50) | **Ngã xuống sàn**, không phải xuống nệm an toàn; dùng để kiểm tra ABNORMAL_MOVEMENT |
| Âm tính cho ABNORMAL_MOVEMENT | URFD ADL (40), GMDCSA24 ADL (81), CAUCAFall ADL (50) | Đi, ngồi xuống ghế, cúi nhặt đồ, quỳ, nằm lên giường/sofa |

Chưa có nguồn: S02 (trở mình), S05 riêng lẻ, S07 (quay lại giường), S12, S14, S16.

## 5. Giới hạn đã biết

- **Không có video công khai nào quay rời giường bệnh bằng camera cố định đặt theo [camera-setup.md](camera-setup.md).** Các clip stock là cảnh quay điện ảnh, góc thấp, nhiều clip cầm tay hoặc lia, cắt ngắn. Metric BED_EDGE / STAND_UP / BED_EXIT trên dữ liệu ngoài chỉ để tham khảo và **còn yếu cho tới khi nhóm quay tình nguyện viên** theo evaluation.md §2–§3.
- Số clip stock nhỏ (19), mỗi nhóm tác giả chỉ có 1–3 clip; không đủ để chốt ngưỡng.
- Nhãn stock là **gán tay** từ contact sheet 1 frame/giây, sai số khoảng 0,5–1 s.
- Dataset ngã quay ngã xuống sàn trong phòng/văn phòng, không có giường bệnh; chỉ dùng cho ABNORMAL_MOVEMENT và kiểm tra cảnh báo giả. Một số ADL của GMDCSA24 và URFD có nằm/ngồi trên giường nhưng không được gán nhãn BED_EDGE/BED_EXIT.
- URFD bản mp4 chỉ có RGB 320×240; landmark ở người xa camera có thể kém.
- Mốc ngã của GMDCSA24 và CAUCAFall là **một thời điểm** (đầu đoạn "Falling" hoặc frame đầu tiên gán "fall"); với CAUCAFall, pha rơi xảy ra ngay trước mốc này. Mốc của URFD là khoảng frame "đang ngã" (nhãn 0).
- Truth của mỗi video chỉ đầy đủ với các mã ghi trong `eval_codes` (cột `notes` của manifest).

## 6. Dataset không dùng

| Dataset | Lý do |
|---|---|
| NTU RGB+D 60/120 | Phải đăng ký, giấy phép hạn chế, cấm phân phối lại |
| Toyota Smarthome | Phải ký thỏa thuận, chỉ cho nghiên cứu, hạn chế trình chiếu |
| ETRI-Activity3D | Phải xin phép, giấy phép hạn chế |
| SLP (Simultaneously-collected multimodal Lying Pose) | Phải đăng ký, điều khoản chưa xác minh |
| CMDFall | Phải xin quyền truy cập, điều khoản chưa xác minh |
| Montreal (Multiple Cameras Fall Dataset) | Giấy phép chưa xác minh |
| Le2i | Giấy phép gốc không rõ, link gốc đang hỏng; chỉ dùng dev nội bộ, **không trình chiếu**, nếu sau này tải được |
