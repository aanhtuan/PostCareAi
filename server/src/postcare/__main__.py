"""`python -m postcare …` = lệnh `postcare` (F31: launcher gọi worker bằng `sys.executable`)."""

from postcare.cli.main import app

if __name__ == "__main__":
    app(prog_name="postcare")
