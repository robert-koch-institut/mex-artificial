from typing import Any

from pydantic import BaseModel

from mex.common.types import AnyPrimitiveType


class RandomFieldInfo(BaseModel):
    """Randomized pick of matching inner type and patterns for a field."""

    inner_type: Any
    numerify_patterns: list[str] = []
    regex_patterns: list[str] = []
    examples: list[AnyPrimitiveType | dict[str, AnyPrimitiveType]] = []
