"""Hash mật khẩu bằng pwdlib/bcrypt (PRD NFR06)."""

from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

_hasher = PasswordHash((BcryptHasher(),))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except Exception:
        return False
