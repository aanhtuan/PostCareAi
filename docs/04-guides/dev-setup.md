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
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
make setup                  # uv sync, npm ci, cài hook pre-commit và pre-push
make seed                   # dữ liệu mẫu SQLite của prototype (tới khi F01 có db-upgrade/db-seed)
make db-upgrade             # chạy migration (từ F01; hiện là target giữ chỗ, exit 1)
make db-seed                # dữ liệu mẫu (từ F01; hiện là target giữ chỗ, exit 1)
make models                 # tải model MediaPipe (từ F11; hiện là target giữ chỗ, exit 1)
make check                  # phải xanh
```

Chạy hệ thống khi phát triển:

```bash
make dev                    # API + web (honcho, Procfile.dev)
make worker CAMERA=1        # worker cho camera id 1 (terminal riêng)
```

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

Trong `.env`: `DATABASE_URL=postgresql+psycopg://postcare:postcare@localhost:5432/postcare`.

Các lần sau chỉ cần `docker start postcare-db`. Dữ liệu nằm trong volume `postcare-pgdata`; xóa hẳn bằng `docker rm -f postcare-db` rồi `docker volume rm postcare-pgdata`.

## 5. Dùng điện thoại làm camera

HS §4.2 có nhắc DroidCam; IP Webcam (Android) là một lựa chọn tương tự.

1. Cài app trên điện thoại; điện thoại và laptop chung mạng Wi-Fi.
2. Mở app, ghi lại địa chỉ hiển thị. *(Giả định A14)* Thường có dạng:
   - DroidCam: `http://<ip-điện-thoại>:4747/video`
   - IP Webcam: `http://<ip-điện-thoại>:8080/video`
3. Kiểm tra (trong `server/`): `uv run postcare probe --source http://<ip>:4747/video` (F05). Lệnh in độ phân giải, FPS thực, số khung bỏ, số lần mất kết nối; không mở được nguồn thì exit 1.
   - Tùy chọn: `--seconds N` (mặc định 10), `--max-fps N` (mặc định 15, A03).
   - Loại nguồn đoán theo `--source`: số nguyên → webcam (`--source 0`); `http://`, `https://`, `rtsp://` → URL; còn lại → file video (`--source D:/PostCareAi/data/raw/clip.mp4`).
   - Với file, `probe` đọc nhanh hết mức (không phát theo tốc độ thực) và dừng khi hết file.
   - Đang `probe` mà tắt app điện thoại: dòng `Trạng thái: OFFLINE` hiện ra, lệnh tự kết nối lại sau 1, 2, 4… tối đa 10 s.
4. Khai báo camera trong màn hình "Quản lý giường": loại nguồn `URL`, địa chỉ ở bước 2.
5. Cách khác: dùng DroidCam client trên máy tính để tạo webcam ảo, rồi khai báo loại `WEBCAM` với index tương ứng.

Cài đặt điện thoại nên có:
- luôn cắm sạc;
- tắt khóa màn hình;
- tắt thông báo hoặc bật chế độ máy bay + chỉ Wi-Fi;
- khóa xoay ngang.

Xem thêm [camera-setup.md](camera-setup.md).

## 6. Sự cố thường gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `uv sync` báo không có wheel mediapipe | Kiểm tra Python là 3.12 (`uv run python -V`) |
| `cv2` lỗi xung đột | Chỉ dùng `opencv-contrib-python` đi kèm mediapipe; gỡ `opencv-python` nếu lỡ cài |
| `make: command not found` trên Windows | Cài GNU Make (mục 1), mở lại terminal |
| `uv` / `npm` báo "is not recognized" dù đã cài | Terminal (nhất là trong VS Code) giữ PATH cũ. Tạm thời: `$env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.local\node\node-v24.21.0-win-x64;$env:Path"` (dán vào mỗi terminal PowerShell mới). Lâu dài: đóng toàn bộ VS Code rồi mở lại |
| Hook pre-commit đổi file CRLF | Đặt `core.autocrlf false`, chạy `git add --renormalize .` |
| Commit bị hook chặn (`ruff format --check`, `prettier --check`, `eslint`) | Chạy `make format` (hoặc `scripts\dev.ps1 format`), sửa lỗi eslint, `git add` lại rồi commit |
| Hook báo `make` / `uv` not found khi push hoặc commit | Thêm thư mục chứa `make`, `uv`, `node` vào PATH người dùng, mở lại terminal/IDE |
| `npm ci` báo `EPERM ... rolldown-binding...node` trên Windows | Một tiến trình Vite/Vitest đang chạy giữ file. Dừng `make dev-web` rồi chạy lại `make setup` |
| Không đọc được URL điện thoại | Ping IP, kiểm tra cùng mạng, thử mở URL trong trình duyệt laptop |
