import re
from collections import OrderedDict
from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import datetime
from enum import Enum
from functools import partial
from typing import Any, cast, get_args, get_origin

from annotated_types import MaxLen, MinLen
from faker import Generator as FakerFactory
from faker.providers import BaseProvider as BaseFakerProvider
from faker.providers.internet import Provider as InternetFakerProvider
from faker.providers.python import Provider as PythonFakerProvider
from pydantic import ValidationError
from pydantic.fields import FieldInfo

from mex.artificial.models import RandomFieldInfo
from mex.common.fields import LITERAL_FIELDS_BY_CLASS_NAME
from mex.common.identity import get_provider
from mex.common.models import (
    ADDITIVE_MODEL_CLASSES_BY_NAME,
    EXTRACTED_MODEL_CLASSES_BY_NAME,
    MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
    PREVENTIVE_MODEL_CLASSES_BY_NAME,
    RULE_SET_RESPONSE_CLASSES_BY_NAME,
    SUBTRACTIVE_MODEL_CLASSES_BY_NAME,
    AnyAdditiveModel,
    AnyExtractedModel,
    AnyPreventiveModel,
    AnyRuleModel,
    AnyRuleSetResponse,
    AnySubtractiveModel,
    ExtractedPrimarySource,
)
from mex.common.transform import ensure_postfix, ensure_prefix
from mex.common.types import (
    TEMPORAL_ENTITY_FORMATS_BY_PRECISION,
    UTC,
    AnyMergedIdentifier,
    Identifier,
    Link,
    LinkLanguage,
    TemporalEntity,
    TemporalEntityPrecision,
    Text,
)
from mex.common.utils import ensure_list


class BuilderProvider(PythonFakerProvider):
    """Faker provider that deals with interpreting pydantic model fields."""

    def min_max_for_field(self, field: FieldInfo) -> tuple[int, int]:
        """Return a min and max item count for a field."""
        if get_origin(field.annotation) is list:
            # calculate the item counts based on field annotations
            min_items = 0
            max_items = self.random_element(  # set probabilities for max items
                OrderedDict({1: 0.42, 2: 0.28, 3: 0.16, 4: 0.08, 5: 0.04, 10: 0.02})
            )
            if min_lengths := [x for x in field.metadata if isinstance(x, MinLen)]:
                min_items = min_lengths[0].min_length
                max_items += min_items  # the max should be higher than the min
            if max_lengths := [x for x in field.metadata if isinstance(x, MaxLen)]:
                max_items = max_lengths[0].max_length
        else:
            # required fields need at least 1 item, optional fields 0
            min_items = int(field.is_required())
            # a list with length 1 will be unpacked by `fix_listyness`
            max_items = 1
        return min_items, max_items

    def get_random_field_info(self, field: FieldInfo) -> RandomFieldInfo:
        """Randomly pick a matching type and patterns for a given field."""
        # determine field type and unpack unions, lists, and other types with args
        if args := get_args(field.annotation):
            # mixed types are not yet supported
            return self.random_element(
                [
                    self.get_random_field_info(field.from_annotation(type_))
                    for type_ in args
                    if type_ is not type(None)
                ]
            )
        return RandomFieldInfo(
            inner_type=field.annotation,
            numerify_patterns=[
                re.sub(r"[0-9]", "#", e)
                for e in ensure_list(field.examples)
                if isinstance(e, str) and not any(char in e for char in "#%$!@")
            ],
            regex_patterns=[m.pattern for m in field.metadata if hasattr(m, "pattern")],
            examples=ensure_list(field.examples),
        )

    def field_value_factory(  # noqa: PLR0911
        self,
        field_info: RandomFieldInfo,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
    ) -> Callable[[], Any]:
        """Get a factory for creating a single value for the given field."""
        if field_info.regex_patterns and field_info.numerify_patterns:
            return partial(
                self.generator.numerify_patterns,
                field_info.numerify_patterns,
                field_info.regex_patterns,
            )
        if field_info.regex_patterns and field_info.examples:
            return partial(self.random_element, field_info.examples)
        if issubclass(field_info.inner_type, Identifier):
            return partial(
                self.generator.reference,
                field_info.inner_type,
                ids_by_type,
            )
        if issubclass(field_info.inner_type, Link):
            return partial(self.generator.link)
        if issubclass(field_info.inner_type, Text):
            return partial(self.generator.text_object)
        if issubclass(field_info.inner_type, TemporalEntity):
            return partial(
                self.generator.temporal_entity,
                field_info.inner_type.ALLOWED_PRECISION_LEVELS,
            )
        if issubclass(field_info.inner_type, Enum):
            return partial(self.random_element, field_info.inner_type)
        if issubclass(field_info.inner_type, str):
            return partial(self.generator.text_string)
        if issubclass(field_info.inner_type, int):
            return partial(self.generator.random_int)
        msg = f"Cannot create fake data for {field_info.inner_type}"
        raise RuntimeError(msg)

    def field_value(
        self,
        field: FieldInfo,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
    ) -> list[Any]:
        """Get a list of artificial values for the given field and identity."""
        field_info = self.get_random_field_info(field)
        factory = self.field_value_factory(field_info, ids_by_type)
        values = [
            value
            for _ in range(self.pyint(*self.min_max_for_field(field)))
            if (value := factory()) is not None
        ]
        return list(set(values))

    def extracted_item(
        self,
        stem_types: Sequence[str],
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        _attempts_left: int = 10,
    ) -> AnyExtractedModel:
        """Generate a single extracted items for the given stem types."""
        stem_type = self.random_element(stem_types)
        entity_type = ensure_prefix(stem_type, "Extracted")
        model_class = EXTRACTED_MODEL_CLASSES_BY_NAME[entity_type]
        # manually set provenance fields
        had_primary_source: AnyMergedIdentifier = self.random_element(
            ids_by_type[ExtractedPrimarySource.stemType]
        )
        index = len(ids_by_type[model_class.stemType])
        raw_data: dict[str, Any] = {
            "hadPrimarySource": had_primary_source,
            "identifierInPrimarySource": f"{model_class.stemType}_{index}",
            "entityType": entity_type,
        }
        # dynamically populate all other fields
        for name, field in model_class.model_fields.items():
            if name not in raw_data:
                raw_data[name] = self.field_value(field, ids_by_type)
        try:
            model = model_class.model_validate(raw_data)
        except ValidationError:
            if _attempts_left > 0:  # if again you don't succeed, try, try again
                return self.extracted_item(
                    stem_types, ids_by_type, _attempts_left=_attempts_left - 1
                )
            raise
        return model

    def additive_rule(
        self,
        stem_type: str,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
    ) -> AnyAdditiveModel:
        """Generate an artificial additive rule."""
        class_name = ensure_prefix(stem_type, "Additive")
        additive_class = ADDITIVE_MODEL_CLASSES_BY_NAME[class_name]
        return additive_class.model_validate(
            {
                name: self.field_value(field, ids_by_type)
                for name, field in additive_class.model_fields.items()
                if name not in LITERAL_FIELDS_BY_CLASS_NAME[class_name]
            }
        )

    def subtractive_rule(
        self,
        stem_type: str,
        extracted_item: AnyExtractedModel,
        value_probability: float = 0.33,
    ) -> AnySubtractiveModel:
        """Generate an artificial subtractive rule."""
        class_name = ensure_prefix(stem_type, "Subtractive")
        subtractive_class = SUBTRACTIVE_MODEL_CLASSES_BY_NAME[class_name]
        return subtractive_class.model_validate(
            {
                name: self.random_sample(
                    extracted_values,
                    length=self.pyint(
                        1, min(len(extracted_values), self.min_max_for_field(field)[1])
                    ),
                )
                for name, field in subtractive_class.model_fields.items()
                if name not in LITERAL_FIELDS_BY_CLASS_NAME[class_name]
                and self.random_int() < value_probability * 1e4
                and (extracted_values := ensure_list(getattr(extracted_item, name)))
            }
        )

    def preventive_rule(
        self,
        stem_type: str,
        extracted_item: AnyExtractedModel,
        value_probability: float = 0.33,
    ) -> AnyPreventiveModel:
        """Generate an artificial preventive rule."""
        class_name = ensure_prefix(stem_type, "Preventive")
        preventive_class = PREVENTIVE_MODEL_CLASSES_BY_NAME[class_name]
        weighted_options = OrderedDict(
            {
                (): 1 - value_probability,
                (extracted_item.hadPrimarySource,): value_probability,
            }
        )
        return preventive_class.model_validate(
            {
                name: list(self.random_element(weighted_options))
                for name in preventive_class.model_fields
                if name not in LITERAL_FIELDS_BY_CLASS_NAME[class_name]
            }
        )

    def standalone_rule_set(
        self,
        stem_types: Sequence[str],
        identifier_seed: int,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        _attempts_left: int = 10,
    ) -> AnyRuleSetResponse:
        """Generate a single standalone rule-set."""
        # manually set provenance fields
        stem_type = self.random_element(stem_types)
        rule_set_class = RULE_SET_RESPONSE_CLASSES_BY_NAME[
            ensure_postfix(stem_type, "RuleSetResponse")
        ]
        identity = get_provider().assign(
            MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
            f"artificial-rule-set-{identifier_seed}",
        )
        raw_data: dict[str, Any] = {
            "stableTargetId": identity.stableTargetId,
            "entityType": ensure_postfix(stem_type, "RuleSetResponse"),
        }
        # dynamically populate additive fields
        raw_data["additive"] = self.additive_rule(stem_type, ids_by_type)
        try:
            model = rule_set_class.model_validate(raw_data)
        except ValidationError:
            if _attempts_left > 0:  # if again you don't succeed, try, try again
                return self.standalone_rule_set(
                    stem_types,
                    identifier_seed,
                    ids_by_type,
                    _attempts_left=_attempts_left - 1,
                )
            raise
        return model

    def rule_set_for_item(
        self,
        extracted_item: AnyExtractedModel,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        _attempts_left: int = 10,
    ) -> AnyRuleSetResponse:
        """Generate a single rule-set for the given extracted item."""
        # manually set provenance fields
        stem_type = extracted_item.stemType
        rule_set_class = RULE_SET_RESPONSE_CLASSES_BY_NAME[
            ensure_postfix(stem_type, "RuleSetResponse")
        ]
        raw_data: dict[str, Any] = {
            "stableTargetId": extracted_item.stableTargetId,
            "entityType": ensure_postfix(stem_type, "RuleSetResponse"),
        }
        # randomize which rules to populate, could be: none, some or all
        rule_names_and_factories = self.random_sample(
            [
                (
                    "additive",
                    partial(self.additive_rule, stem_type, ids_by_type),
                ),
                (
                    "preventive",
                    partial(self.preventive_rule, stem_type, extracted_item),
                ),
                (
                    "subtractive",
                    partial(self.subtractive_rule, stem_type, extracted_item),
                ),
            ]
        )
        # dynamically populate selected rule fields
        for rule_name, factory in rule_names_and_factories:
            raw_data[rule_name] = cast("Callable[[], AnyRuleModel]", factory)()
        try:
            model = rule_set_class.model_validate(raw_data)
        except ValidationError:
            if _attempts_left > 0:  # if again you don't succeed, try, try again
                return self.rule_set_for_item(
                    extracted_item, ids_by_type, _attempts_left=_attempts_left - 1
                )
            raise
        return model


class ReferenceProvider(BaseFakerProvider):
    """Faker provider that creates references to other items."""

    def reference(
        self,
        inner_type: type[Identifier],
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
    ) -> AnyMergedIdentifier | None:
        """Return random merged item identifier picked from available mapping."""
        if choices := [
            identifier
            for stem_type in re.findall(r"Merged([A-Za-z]+)Identifier", str(inner_type))
            for identifier in ids_by_type[stem_type]
        ]:
            return self.random_element(choices)
        return None


class LinkProvider(InternetFakerProvider, PythonFakerProvider):
    """Faker provider that can return links with optional title and language."""

    def link(self) -> Link:
        """Return a link with optional title and language."""
        title, language = None, None
        if self.pybool():
            title = self.domain_word().replace("-", " ").title()
            if self.pybool():
                language = self.random_element(LinkLanguage)
        return Link(url=self.url(), title=title, language=language)


class TemporalEntityProvider(PythonFakerProvider):
    """Faker provider that can return a custom TemporalEntity with random precision."""

    def temporal_entity(
        self, allowed_precision_levels: list[TemporalEntityPrecision]
    ) -> TemporalEntity:
        """Return a custom temporal entity with random date, time and precision."""
        return TemporalEntity(
            datetime.fromtimestamp(
                self.pyint(int(8e8), int(datetime.now(tz=UTC).timestamp())), tz=UTC
            ).strftime(
                TEMPORAL_ENTITY_FORMATS_BY_PRECISION[
                    self.random_element(allowed_precision_levels)
                ]
            )
        )


class TextProvider(PythonFakerProvider):
    """Faker provider that handles custom text related requirements."""

    def __init__(self, factory: FakerFactory, chattiness: int) -> None:
        """Configure the chattiness of generated text."""
        super().__init__(factory)
        self._chattiness = chattiness

    def text_string(self) -> str:
        """Return a randomized sequence of words as a string."""
        return " ".join(
            self.generator.word()
            for _ in range(self.pyint(1, max(int(self._chattiness / 5), 3)))
        )

    def text_object(self) -> Text:
        """Return a random text paragraph with an auto-detected language."""
        return Text(value=self.generator.paragraph(self.pyint(1, self._chattiness)))


class NumerifyPatternsProvider(PythonFakerProvider):
    """Faker provider that tries to numerify a pattern until it matches a regex."""

    def numerify_patterns(
        self,
        numerify_patterns: list[str],
        regex_patterns: list[str],
    ) -> str | None:
        """Try to numerify a pattern in 10 turns until it validates, or bail out."""
        for _ in range(10):
            numerify_pattern = self.random_element(numerify_patterns)
            regex_pattern = self.random_element(regex_patterns)
            numerified = self.numerify(numerify_pattern)
            if re.match(regex_pattern, numerified):
                return numerified
        return None
