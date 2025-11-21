from typing import Any

from pydantic import BaseModel

from mex.common.models import AnyExtractedModel, AnyRuleSetResponse
from mex.common.types import AnyPrimitiveType


class RandomFieldInfo(BaseModel):
    """Randomized pick of matching inner type and patterns for a field."""

    inner_type: Any
    numerify_patterns: list[str] = []
    regex_patterns: list[str] = []
    examples: list[AnyPrimitiveType | dict[str, AnyPrimitiveType]] = []


class ExtractedItemAndRuleSet(BaseModel):
    """A combination of an extracted item and a rule-set (both optional)."""

    extracted_item: AnyExtractedModel | None = None
    rule_set: AnyRuleSetResponse | None = None
