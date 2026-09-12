from enum import StrEnum

from sqlalchemy import Enum


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
