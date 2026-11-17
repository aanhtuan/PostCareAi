"""`GET /api/v1/health`: kiểm tra API còn sống (không cần đăng nhập, không chạm DB)."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
