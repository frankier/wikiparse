from dataclasses import fields
from typing import TypeVar


Self = TypeVar("Self")


class MergeMixin:
    def merge(self: Self, other: Self):
        for self_field in fields(self):
            getattr(self, self_field.name).extend(getattr(other, self_field.name))
