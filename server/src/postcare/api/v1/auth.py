from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from postcare.api.deps import create_token, get_current_user, get_db, get_settings_dep
from postcare.db.models import User
from postcare.domain.dto import LoginIn, LoginOut, UserOut, user_out
from postcare.domain.users import authenticate
from postcare.settings import Settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginOut)
def login(
    body: LoginIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings_dep),
) -> LoginOut:
    user = authenticate(db, body.username, body.password)
    return LoginOut(access_token=create_token(user, settings), user=user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return user_out(user)
