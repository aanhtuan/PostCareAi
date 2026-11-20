# Cài đặt môi trường phát triển

Hỗ trợ **Windows 10/11 / Windows Server** và **Linux (Ubuntu)**. Chỉ cần CPU (HS §7.2). GPU NVIDIA là tùy chọn, chỉ dùng khi benchmark CPU không đạt (QA#35).

> Các lệnh cài bằng `winget` / `choco` dưới đây là *(giả định)* tên gói phổ biến. Kiểm tra lại khi chạy. Nếu tên gói khác, cập nhật file này.

## 1. Công cụ cần có

| Công cụ | Phiên bản | Windows | Ubuntu |
|---|---|---|---|
| Git | ≥ 2.40 | `winget install Git.Git` | `sudo apt install git` |
| GNU Make | ≥ 4 | `winget install ezwinports.make` hoặc `choco install make`. Không có winget: tải `make-4.4.1-without-guile-w32-bin.zip` từ SourceForge ezwinports, so SHA1 với trang tải, giải nén vào `%USERPROFILE%\.local\make` và thêm `bin` vào PATH | `sudo apt install make` |
| Docker | mới nhất | Docker Desktop | `sudo apt install docker.io` |
| GitHub CLI | mới nhất | `winget install GitHub.cli`, hoặc zip `gh_<ver>_windows_amd64.zip` từ GitHub Releases, kiểm tra với `checksums.txt` | `sudo apt install gh` |
| uv | mới nhất | `powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python 3.12 | qua uv | `uv python install 3.12` | `uv python install 3.12` |
| Node.js | 24 LTS (hoặc 22 LTS) | `winget install OpenJS.NodeJS.LTS` | dùng nvm hoặc NodeSource |
| PostgreSQL | 16 | **Docker (mục 4, mặc định, QA#34)**; hoặc `winget install PostgreSQL.PostgreSQL.16` | Docker (mục 4) hoặc `sudo apt install postgresql-16` |
| pre-commit | qua uv | cài tự động bởi `make setup` | như Windows |

**Lưu ý trên Windows:**
- Máy có thể đã có Python khác (ví dụ 3.15). Không sao: uv tự dùng 3.12 theo `server/.python-version`.
- Chạy `make` từ PowerShell hoặc Git Bash đều được. Recipe trong Makefile chỉ gọi `uv` và `npm`.
- Cấu hình Git: `git config --global core.autocrlf false` (repo dùng LF qua `.gitattributes`).

## 2. Tạo database

```sql
-- chạy bằng psql với user postgres
CREATE USER postcare WITH PASSWORD 'postcare';
CREATE DATABASE postcare OWNER postcare;
CREATE DATABASE postcare_test OWNER postcare;
```

## 3. Thiết lập dự án

```bash
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env (bắt buộc, xem dưới)
make setup                  # uv sync, npm ci, cài hook pre-commit và pre-push
# PostgreSQL phải đang chạy (mục 4)
make db-upgrade             # alembic upgrade head trên DATABASE_URL
make db-seed                # dữ liệu mẫu nền (postcare seed), chạy lại an toàn
make seed                   # tùy chọn, prototype: XÓA hết, migrate lại, thêm dữ liệu demo
make models                 # tải model MediaPipe (pose lite/full/heavy + face_landmarker) vào models/, kiểm tra sha256
make check                  # phải xanh
```

`JWT_SECRET` và `WORKER_TOKEN` (F02): API **từ chối khởi động** nếu một trong hai còn là giá trị mặc định (`change-me…`) hoặc ngắn hơn 32 byte, kèm thông báo lỗi chỉ cách sửa. `.env.example` có sẵn giá trị chỉ dùng cho dev (tiền tố `dev-only-`); chạy demo trong LAN thì tạo giá trị mới:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

API, worker và giả lập cùng đọc `.env` ở thư mục gốc nên `WORKER_TOKEN` tự khớp. Test (`make check`) không cần `.env`: fixture tự đặt giá trị đủ mạnh.

Chạy hệ thống khi phát triển:

```bash
make dev                    # API + web (honcho, Procfile.dev)
make worker CAMERA=1        # worker cho camera id 1 (terminal riêng)
make worker CAMERA=1 VIDEO=D:/clip.mp4   # phát file video như camera (nhịp thời gian thật)
make workers CAMERAS="1 2" VIDEOS="2=D:/clip.mp4"   # F31: mỗi camera một tiến trình, Ctrl+C dừng hết
```

Worker (F06, `postcare worker --camera-id N`) đọc `API_BASE_URL`, `WORKER_TOKEN` từ `.env`, cần model pose (`make models`, hoặc `POSTCARE_MODELS_DIR`) và camera đã có ROI giường. Chu kỳ đặt trong settings: `WORKER_HEARTBEAT_INTERVAL_S` (2), `WORKER_CONFIG_POLL_S` (5), `WORKER_FRAME_FPS` (5), `WORKER_JPEG_MAX_SIDE` (960), `WORKER_JPEG_QUALITY` (70), `WORKER_MAX_FPS` (15); API: `FRAME_MAX_BYTES` (2 MB). Không có camera/model thì dùng giả lập `make simulate`.

Nếu `make dev` (honcho) lỗi trên Windows, mở 2 terminal và chạy riêng `make dev-api`, `make dev-web`.

Git hook do `make setup` cài (`.pre-commit-config.yaml`):
- **pre-commit:** `ruff format --check`, `ruff check` (file trong `server/`), `prettier --check`, `eslint` (file trong `web/`). Hook chỉ kiểm tra, không tự sửa: bị chặn thì chạy `make format`, `git add` lại rồi commit.
- **pre-push:** `make check`.
- Hook gọi `uv`, `node` và `make` qua PATH. Trên Windows, Git chạy hook bằng bash của Git for Windows: `uv`, `node` và `make` phải có trong PATH **của người dùng** (không chỉ trong terminal đang mở), nếu không hook báo không tìm thấy lệnh.
- Không dùng `--no-verify`.

## 4. PostgreSQL bằng Docker (mặc định, Windows và Linux)

Mở Docker Desktop (Windows) trước, rồi chạy một lần:

```bash
docker run -d --name postcare-db -e POSTGRES_USER=postcare -e POSTGRES_PASSWORD=postcare \
  -e POSTGRES_DB=postcare -p 5432:5432 -v postcare-pgdata:/var/lib/postgresql/data postgres:16
docker exec -it postcare-db createdb -U postcare postcare_test
```

Giá trị mặc định (không cần `.env`): `DATABASE_URL=postgresql+psycopg://postcare:postcare@localhost:5432/postcare`, `TEST_DATABASE_URL=postgresql+psycopg://postcare:postcare@localhost:5432/postcare_test`. Test chỉ chạy trên DB có tên kết thúc bằng `_test` và tự chạy migration trên đó; DB test không kết nối được thì test lỗi (không skip), nên `make check` cần container đang chạy.

Các lần sau chỉ cần `docker start postcare-db`. Dữ liệu nằm trong volume `postcare-pgdata`; xóa hẳn bằng `docker rm -f postcare-db` rồi `docker volume rm postcare-pgdata`.

## 5. Dùng điện thoại làm camera

HS §4.2 có nhắc DroidCam. Với Android, có thể dùng DroidCam hoặc IP Webcam theo các bước sau. Với iPhone, xem hai hướng dẫn bên dưới.

1. Cài app trên điện thoại; điện thoại và laptop chung mạng Wi-Fi.
2. Mở app, ghi lại địa chỉ hiển thị. *(Giả định A14)* Thường có dạng:
   - DroidCam: `http://<ip-điện-thoại>:4747/video`
   - IP Webcam: `http://<ip-điện-thoại>:8080/video`
3. Kiểm tra (trong `server/`): `uv run postcare probe --source http://<ip>:4747/video` (F05). Lệnh in độ phân giải, FPS thực, số khung bỏ, số lần mất kết nối; không mở được nguồn thì exit 1.
   - Tùy chọn: `--seconds N` (mặc định 10), `--max-fps N` (mặc định 15, A03).
   - Loại nguồn đoán theo `--source`: số nguyên → webcam (`--source 0`); `http://`, `https://`, `rtsp://` → URL; còn lại → file video (`--source D:/PostCareAi/data/raw/clip.mp4`).
   - Với file, `probe` đọc nhanh hết mức (không phát theo tốc độ thực) và dừng khi hết file.
   - Đang `probe` mà tắt app điện thoại: dòng `Trạng thái: OFFLINE` hiện ra, lệnh tự kết nối lại sau 1, 2, 4… tối đa 10 s.
4. Đăng nhập quản trị viên, vào **Theo dõi trực tiếp**, chọn giường, bấm **Kết nối camera** và chọn **Địa chỉ stream (URL)**. Dán địa chỉ ở bước 2, rồi bấm **Lưu và kết nối**. Giường đã có camera sẽ dùng lại bản ghi hiện tại. Trước khi đổi nguồn, giường cần ở trạng thái chưa có phiên theo dõi đang mở.
5. Nếu chưa tải model, chạy `make models`. Chạy `make worker CAMERA=<id>` trên máy kết nối camera theo số ID trong thông báo. Worker đang chạy bản mới sẽ tự tải cấu hình. Nếu worker đang phát clip qua `VIDEO=...` hoặc chạy bản cũ, dừng rồi chạy lại lệnh trên. Chờ hai khung xuất hiện, rồi kiểm tra lại vùng giường trong **Quản lý giường → Camera → Cấu hình** nếu vị trí hoặc góc quay thay đổi.

### iPhone qua Wi-Fi nội bộ trên Fedora

1. Kết nối iPhone và máy chạy worker vào cùng mạng nội bộ cho phép hai thiết bị liên lạc. Mở [IP Camera Lite](https://apps.apple.com/vn/app/ip-camera-lite/id1013455241), cấp quyền camera và mạng nội bộ nếu được hỏi, bật **IP Camera Server** và lấy URL **RTSP** của luồng. Bản Lite có watermark. Giữ app mở khi thử.
2. Từ thư mục gốc, kiểm tra bằng `uv --directory server run postcare probe --source '<URL RTSP của iPhone>' --seconds 30`. Nếu có hình, nhập cùng URL vào **Địa chỉ stream (URL)** theo bước 4 ở trên.
3. Dùng mạng thử nghiệm riêng và người đóng vai, tắt ghi hình trong app. Tránh nhập URL chứa mật khẩu hoặc token vì cấu hình nguồn hiện được hiển thị trong danh mục và lưu trong audit. Nếu app yêu cầu nhúng mật khẩu vào URL, dùng DroidCam qua Wi-Fi theo phương án webcam ảo bên dưới, chọn IP của iPhone trong client.

### iPhone qua cáp USB trên Fedora

1. Cài [DroidCam Webcam & OBS Camera](https://apps.apple.com/vn/app/droidcam-webcam-obs-camera/id1510258102) trên iPhone. Trên Fedora, làm theo [hướng dẫn DroidCam cho Linux](https://www.droidcam.app/linux/) để cài bản Linux Client và `v4l2loopback` từ RPM Fusion. Chạy `sudo dnf install usbmuxd v4l-utils` để cài công cụ nhận iPhone qua USB và liệt kê webcam. Sau khi cài module, nếu chưa nạp module thì chạy `sudo modprobe v4l2loopback exclusive_caps=1 card_label=DroidCam devices=1`.
2. Cắm cáp có truyền dữ liệu, mở khóa iPhone, chọn **Tin cậy** nếu được hỏi và mở DroidCam. Trong Linux Client, chọn **Add → DroidCam → Refresh Device List**, chọn iPhone qua USB và kiểm tra hình. Nếu chưa thấy iPhone, kiểm tra dịch vụ bằng `systemctl status usbmuxd`, chạy `sudo systemctl start usbmuxd` nếu dịch vụ chưa chạy. Xem [thiết lập iOS qua USB của DroidCam](https://droidcam.app/help/#ios-usb-setup).
3. Khi Linux Client đã có hình, chạy `v4l2-ctl --list-devices` để thấy camera ảo và đường dẫn, ví dụ `/dev/video2`. Kiểm tra với `uv --directory server run postcare probe --source 2 --seconds 10`, thay `2` bằng số thiết bị thực tế. Dừng probe trước khi worker mở thiết bị.
4. Trong **Theo dõi trực tiếp → Kết nối camera**, chọn **Webcam**, nhập số vừa thử và bấm **Lưu và kết nối**. Giữ DroidCam mở trong lúc theo dõi.

Cài đặt điện thoại nên có:
- luôn cắm sạc;
- tắt khóa màn hình;
- tắt thông báo hoặc bật chế độ máy bay + chỉ Wi-Fi;
- khóa xoay ngang.

Xem thêm [camera-setup.md](camera-setup.md).

## 6. Sự cố thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `make models` báo sha256 không khớp | File tải về bị hỏng hoặc URL trong `config/models.yaml` đã đổi bản: chạy lại; vẫn lỗi thì kiểm tra URL (phải có số phiên bản, không `latest`) rồi cập nhật sha256 |
| Adapter báo không tìm thấy model (`Chạy make models`) | Chạy `make models` (Windows chưa có make: `scripts\dev.ps1 models`); model nằm ở `models/`, không commit |
| `uv sync` báo không có wheel mediapipe | Kiểm tra Python là 3.12 (`uv run python -V`) |
| `cv2` lỗi xung đột | Chỉ dùng `opencv-contrib-python` đi kèm mediapipe; gỡ `opencv-python` nếu lỡ cài |
| `make: command not found` trên Windows | Cài GNU Make (mục 1), mở lại terminal |
| `uv` / `npm` báo "is not recognized" dù đã cài | Terminal (nhất là trong VS Code) giữ PATH cũ. Tạm thời: `$env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.local\node\node-v24.21.0-win-x64;$env:Path"` (dán vào mỗi terminal PowerShell mới). Lâu dài: đóng toàn bộ VS Code rồi mở lại |
| Hook pre-commit đổi file CRLF | Đặt `core.autocrlf false`, chạy `git add --renormalize .` |
| Commit bị hook chặn (`ruff format --check`, `prettier --check`, `eslint`) | Chạy `make format` (hoặc `scripts\dev.ps1 format`), sửa lỗi eslint, `git add` lại rồi commit |
| Hook báo `make` / `uv` not found khi push hoặc commit | Thêm thư mục chứa `make`, `uv`, `node` vào PATH người dùng, mở lại terminal/IDE |
| `npm ci` báo `EPERM ... rolldown-binding...node` trên Windows | Một tiến trình Vite/Vitest đang chạy giữ file. Dừng `make dev-web` rồi chạy lại `make setup` |
| Không đọc được URL điện thoại | Ping IP, kiểm tra cùng mạng, thử mở URL trong trình duyệt laptop |

## 7. Replay video và cắt fixture (F12)

Chạy trong `server/` (đường dẫn tương đối tính từ `server/`). Video nằm ngoài git (`data/`); kết quả ghi vào `runs/<id>/` (gitignore). Replay không gọi API, không cần DB.

```bash
# Video → pose MediaPipe → engine (cùng pipeline với worker). Cần model (make models).
uv run postcare replay --video ../data/external/pexels/pexels-8090735.mp4 \
  --camera-config ../config/cameras/pexels-8090735.yaml --out ../runs/pexels-8090735 --preview

# Chạy lại chỉ engine (không cần MediaPipe, xác định từng byte), ví dụ sau khi chỉnh ngưỡng
uv run postcare replay --from-observations ../runs/pexels-8090735/observations.jsonl \
  --camera-config ../config/cameras/pexels-8090735.yaml --out ../runs/pexels-8090735-b

# Cắt đoạn 2–6 s làm fixture test (chỉ toạ độ) + sự kiện kỳ vọng
uv run postcare replay --from-observations ../runs/pexels-8090735/observations.jsonl \
  --camera-config ../config/cameras/pexels-8090735.yaml --start-s 2 --end-s 6 \
  --save-observations tests/fixtures/s06_pexels_exit.jsonl --save-expected
```

- `--out` đã có dữ liệu → lỗi, thêm `--overwrite` để ghi đè.
- `--max-fps` (mặc định 15, A03) chọn khung theo thời gian video; `0` = mọi khung. `--model lite|full|heavy` (mặc định theo `config/models.yaml`). `--models-dir` mặc định là `POSTCARE_MODELS_DIR` nếu đặt, không thì `models/` (tiện khi chạy trong git worktree).
- Nhánh face (F25) chạy khi `face.enabled: true` (mặc định); tắt để so FPS bằng `thresholds: {face: {enabled: false}}` trong cấu hình camera. Thiếu `face_landmarker.task` thì replay vẫn chạy, `face.status = NOT_VISIBLE` và có cảnh báo. Kết quả face nằm ở trường `face` của `observations.jsonl` (`null` ở frame không chạy face); `run.json` có `face_enabled`, `face_errors`. `postcare eval` chỉ chạy pose + engine (sự kiện cơ thể không phụ thuộc face).
- `--preview` ghi `preview.mp4` (skeleton mọi người, ROI, `body_state | observation_quality`, nhãn sự kiện 2 s). Đây là công cụ dev, nhãn dùng mã nội bộ; chỉ dùng với `--video`. Không đưa `preview.mp4` ra ngoài nhóm nếu video có người thật.
- `--display-mode RAW|BLUR|SKELETON` (F28, mặc định `BLUR`): khung của `preview.mp4` được render như worker gửi lên dashboard rồi mới vẽ lớp debug. Chỉ đổi video preview; `events.jsonl`/`frames.jsonl` giống nhau ở cả ba chế độ.
- File `.expected.json` do lệnh sinh từ engine hiện tại: xem lại so với ground truth trước khi commit (testing.md §2).
- Cấu hình camera: [evaluation.md §4](evaluation.md#4-định-dạng-file).
