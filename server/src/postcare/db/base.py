"""Lớp gốc của model SQLAlchemy, quy ước đặt tên constraint và kiểu cột dùng chung."""

from enum import StrEnum

from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import DeclarativeBase

# Tên constraint cố định để migration sau (alter/drop) tham chiếu được.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def pg_enum(cls: type[StrEnum], name: str) -> ENUM:
    """Enum native của PostgreSQL, giá trị lấy từ enum trong `postcare.schemas` (R4).

    `create_type=False`: kiểu enum do migration tạo và xóa, không tạo ngầm.
    """
    return ENUM(
        cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        create_type=False,
    )
