import re
from collections import OrderedDict
from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import datetime
from enum import Enum
from functools import partial
from types import NoneType, UnionType
from typing import Any, TypeVar, Union, cast, get_args, get_origin

from annotated_types import MaxLen, MinLen
from faker import Generator as FakerFactory
from faker.providers import BaseProvider as BaseFakerProvider
from faker.providers.internet import Provider as InternetFakerProvider
from faker.providers.python import Provider as PythonFakerProvider
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ValidationError
from pydantic.fields import FieldInfo

from mex.artificial.constants import (
    DEFAULT_GENERATION_ATTEMPTS,
    DEFAULT_MAPPING_EXTRA_ITEMS,
    DEFAULT_RULE_VALUE_PROBABILITY,
    DEFAULT_SEED,
)
from mex.artificial.models import RandomFieldInfo
from mex.common.fields import LITERAL_FIELDS_BY_CLASS_NAME
from mex.common.identity import get_provider
from mex.common.models import (
    ADDITIVE_MODEL_CLASSES_BY_NAME,
    EXTRACTED_MODEL_CLASSES_BY_NAME,
    MAPPING_MODEL_CLASSES_BY_NAME,
    MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
    PREVENTIVE_MODEL_CLASSES_BY_NAME,
    RULE_SET_RESPONSE_CLASSES_BY_NAME,
    SUBTRACTIVE_MODEL_CLASSES_BY_NAME,
    WORKFLOW_MODEL_CLASSES_BY_NAME,
    AnyAdditiveModel,
    AnyExtractedModel,
    AnyMappingModel,
    AnyPreventiveModel,
    AnyRuleModel,
    AnyRuleSetResponse,
    AnySubtractiveModel,
    AnyWorkflowModel,
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


def _strip_optional(annotation: Any) -> Any:  # noqa: ANN401
    """Unwrap `X | None` into `X`, leave all other annotations untouched."""
    if get_origin(annotation) in (Union, UnionType):
        args = [arg for arg in get_args(annotation) if arg is not NoneType]
        if len(args) == 1:
            return args[0]
    return annotation


def _contains_type_var(annotation: Any) -> bool:  # noqa: ANN401
    """Check whether the annotation is or contains an unbound type variable."""
    if isinstance(annotation, TypeVar):
        return True
    return any(_contains_type_var(arg) for arg in get_args(annotation))


def _leaf_field_info(field: FieldInfo) -> RandomFieldInfo:
    """Build the field info for a field without any type arguments."""
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


def get_all_field_infos(field: FieldInfo) -> list[RandomFieldInfo]:
    """Return the field infos for all types a field can hold, unpacking unions."""
    if args := get_args(field.annotation):
        return [
            info
            for type_ in args
            if type_ is not NoneType
            for info in get_all_field_infos(field.from_annotation(type_))
        ]
    return [_leaf_field_info(field)]


class BuilderProvider(PythonFakerProvider):
    """Faker provider that deals with interpreting pydantic model fields."""

    def min_max_for_field(self, field: FieldInfo) -> tuple[int, int]:
        """Return a min and max item count for a field."""
        if get_origin(field.annotation) is Sequence:
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
        return _leaf_field_info(field)

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
    ) -> Sequence[Any]:
        """Get a list of artificial values for the given field and identity."""
        field_info = self.get_random_field_info(field)
        factory = self.field_value_factory(field_info, ids_by_type)
        return list(
            dict.fromkeys(
                value
                for _ in range(self.pyint(*self.min_max_for_field(field)))
                if (value := factory()) is not None
            )
        )

    def extracted_item(
        self,
        stem_types: Sequence[str],
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        _attempts_left: int = DEFAULT_GENERATION_ATTEMPTS,
    ) -> AnyExtractedModel:
        """Generate a single extracted item from the given stem types."""
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
        for name in sorted(model_class.model_fields):
            if name not in raw_data:
                raw_data[name] = self.field_value(
                    model_class.model_fields[name], ids_by_type
                )
        try:
            model = model_class.model_validate(raw_data)
        except ValidationError:
            if _attempts_left > 0:  # if again you don't succeed, try, try again
                return self.extracted_item(
                    stem_types, ids_by_type, _attempts_left=_attempts_left - 1
                )
            raise
        return model

    def mapping_value(
        self,
        mapping_field: FieldInfo,
        extracted_field: FieldInfo,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        is_list: bool,
    ) -> Any:  # noqa: ANN401
        """Generate a value for a field of a mapping model, mapping field or rule.

        The value is derived from the field's annotation alone, so fields added to
        the mapping models later on are populated without further code changes:
        - mapping lists (e.g. `MappingFieldList`, `MappingRuleList`) are filled with
          nested mapping models, respecting the `min_length` constraint
        - generic value slots (e.g. `setValues`, `exampleOutputs`) are filled with
          values matching the corresponding extracted field
        - plain strings and lists of strings are filled with random text

        Args:
            mapping_field: Field of a mapping model, mapping field or mapping rule
            extracted_field: Extracted model field that the mapping targets
            ids_by_type: Available identifiers by stem type for references
            is_list: Whether the targeted extracted value is a list

        Returns:
            Raw value for the field, or `None` if no value could be generated
        """
        annotation = _strip_optional(mapping_field.annotation)
        if item_type := getattr(get_origin(annotation), "_item_type", None):
            # `MappingFieldList[list[X]]` vs `MappingFieldList[X]`, nested mapping
            # lists are still parametrized with a type variable though
            if not _contains_type_var(value_type := get_args(annotation)[0]):
                is_list = get_origin(value_type) is list
            min_items = next(
                (m.min_length for m in mapping_field.metadata if isinstance(m, MinLen)),
                0,
            )
            return [
                self.mapping_model(
                    item_type, extracted_field, ids_by_type, is_list=is_list
                )
                for _ in range(
                    self.pyint(min_items, min_items + DEFAULT_MAPPING_EXTRA_ITEMS)
                )
            ]
        if _contains_type_var(annotation):
            values = self.field_value(extracted_field, ids_by_type)
            if is_list:
                return values or None
            return values[0] if values else None
        if get_origin(annotation) is list:
            return [
                self.generator.text_string()
                for _ in range(self.pyint(1, 1 + DEFAULT_MAPPING_EXTRA_ITEMS))
            ]
        if annotation is str:
            return self.generator.text_string()
        msg = f"Cannot create fake mapping data for {mapping_field.annotation}"
        raise RuntimeError(msg)

    def mapping_model(
        self,
        model_class: type[PydanticBaseModel],
        extracted_field: FieldInfo,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        is_list: bool,
    ) -> dict[str, Any]:
        """Generate raw data for a nested mapping model, e.g. a field or rule."""
        raw_data: dict[str, Any] = {}
        for name, field in model_class.model_fields.items():
            if not field.is_required() and not self.pybool():
                continue
            value = self.mapping_value(
                field, extracted_field, ids_by_type, is_list=is_list
            )
            # skip empty values, they are indistinguishable from the default
            if value is not None:
                raw_data[name] = value
        if not raw_data:
            # avoid empty models, e.g. rules with neither `forValues` nor `setValues`
            for name in self.random_sample(
                list(model_class.model_fields), len(model_class.model_fields)
            ):
                value = self.mapping_value(
                    model_class.model_fields[name],
                    extracted_field,
                    ids_by_type,
                    is_list=is_list,
                )
                if value is not None:
                    raw_data[name] = value
                    break
        return raw_data

    def mapping_item(
        self,
        stem_type: str,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        _attempts_left: int = DEFAULT_GENERATION_ATTEMPTS,
    ) -> AnyMappingModel:
        """Generate a single mapping for the given stem type."""
        entity_type = ensure_postfix(stem_type, "Mapping")
        mapping_class = MAPPING_MODEL_CLASSES_BY_NAME[entity_type]
        extracted_class = EXTRACTED_MODEL_CLASSES_BY_NAME[
            ensure_prefix(stem_type, "Extracted")
        ]
        raw_data: dict[str, Any] = {}
        for name in sorted(mapping_class.model_fields):
            if name not in extracted_class.model_fields or name == "entityType":
                continue
            mapping_field = mapping_class.model_fields[name]
            if not mapping_field.is_required() and not self.pybool():
                continue
            raw_data[name] = self.mapping_value(
                mapping_field,
                extracted_class.model_fields[name],
                ids_by_type,
                is_list=False,
            )
        try:
            model = mapping_class.model_validate(raw_data)
        except ValidationError:
            if _attempts_left > 0:  # if again you don't succeed, try, try again
                return self.mapping_item(
                    stem_type, ids_by_type, _attempts_left=_attempts_left - 1
                )
            raise
        return model

    def additive_rule(
        self,
        stem_type: str,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        value_probability: float = DEFAULT_RULE_VALUE_PROBABILITY,
    ) -> AnyAdditiveModel:
        """Generate an artificial additive rule."""
        class_name = ensure_prefix(stem_type, "Additive")
        additive_class = ADDITIVE_MODEL_CLASSES_BY_NAME[class_name]
        raw_data = {
            name: self.field_value(additive_class.model_fields[name], ids_by_type)
            for name in sorted(additive_class.model_fields)
            if name not in LITERAL_FIELDS_BY_CLASS_NAME[class_name]
            and self.random_int() < value_probability * 1e4
        }
        return additive_class.model_validate(raw_data)

    def subtractive_rule(
        self,
        extracted_item: AnyExtractedModel,
        *,
        value_probability: float = DEFAULT_RULE_VALUE_PROBABILITY,
    ) -> AnySubtractiveModel:
        """Generate an artificial subtractive rule."""
        class_name = ensure_prefix(extracted_item.stemType, "Subtractive")
        subtractive_class = SUBTRACTIVE_MODEL_CLASSES_BY_NAME[class_name]
        raw_data = {
            name: self.random_sample(
                extracted_values,
                length=self.pyint(
                    1,
                    min(
                        len(extracted_values),
                        self.min_max_for_field(subtractive_class.model_fields[name])[1],
                    ),
                ),
            )
            for name in sorted(subtractive_class.model_fields)
            if name not in LITERAL_FIELDS_BY_CLASS_NAME[class_name]
            and self.random_int() < value_probability * 1e4
            and (extracted_values := ensure_list(getattr(extracted_item, name)))
        }
        return subtractive_class.model_validate(raw_data)

    def preventive_rule(
        self,
        extracted_item: AnyExtractedModel,
        *,
        value_probability: float = DEFAULT_RULE_VALUE_PROBABILITY,
    ) -> AnyPreventiveModel:
        """Generate an artificial preventive rule."""
        class_name = ensure_prefix(extracted_item.stemType, "Preventive")
        preventive_class = PREVENTIVE_MODEL_CLASSES_BY_NAME[class_name]
        weighted_options = OrderedDict(
            {
                (): 1 - value_probability,
                (extracted_item.hadPrimarySource,): value_probability,
            }
        )
        raw_data = {
            name: list(self.random_element(weighted_options))
            for name in preventive_class.model_fields
            if name not in LITERAL_FIELDS_BY_CLASS_NAME[class_name]
        }
        return preventive_class.model_validate(raw_data)

    def workflow_rule(
        self,
        stem_type: str,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        value_probability: float = DEFAULT_RULE_VALUE_PROBABILITY,
    ) -> AnyWorkflowModel:
        """Generate an artificial workflow rule."""
        class_name = ensure_prefix(stem_type, "Workflow")
        workflow_class = WORKFLOW_MODEL_CLASSES_BY_NAME[class_name]
        raw_data = {
            name: self.field_value(workflow_class.model_fields[name], ids_by_type)
            for name in sorted(workflow_class.model_fields)
            if name not in LITERAL_FIELDS_BY_CLASS_NAME[class_name]
            and self.random_int() < value_probability * 1e4
        }
        return workflow_class.model_validate(raw_data)

    def standalone_rule_set(
        self,
        stem_types: Sequence[str],
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        identifier_seed: int = DEFAULT_SEED,
        *,
        value_probability: float = DEFAULT_RULE_VALUE_PROBABILITY,
        _attempts_left: int = DEFAULT_GENERATION_ATTEMPTS,
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
        raw_data["additive"] = self.additive_rule(
            stem_type, ids_by_type, value_probability=value_probability
        )
        try:
            model = rule_set_class.model_validate(raw_data)
        except ValidationError:
            if _attempts_left > 0:  # if again you don't succeed, try, try again
                return self.standalone_rule_set(
                    stem_types,
                    ids_by_type,
                    identifier_seed,
                    _attempts_left=_attempts_left - 1,
                )
            raise
        return model

    def rule_set_for_item(
        self,
        extracted_item: AnyExtractedModel,
        ids_by_type: Mapping[str, Collection[AnyMergedIdentifier]],
        *,
        value_probability: float = DEFAULT_RULE_VALUE_PROBABILITY,
        _attempts_left: int = DEFAULT_GENERATION_ATTEMPTS,
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
                    partial(
                        self.additive_rule,
                        stem_type,
                        ids_by_type,
                        value_probability=value_probability,
                    ),
                ),
                (
                    "preventive",
                    partial(
                        self.preventive_rule,
                        extracted_item,
                        value_probability=value_probability,
                    ),
                ),
                (
                    "subtractive",
                    partial(
                        self.subtractive_rule,
                        extracted_item,
                        value_probability=value_probability,
                    ),
                ),
                (
                    "workflow",
                    partial(
                        self.workflow_rule,
                        stem_type,
                        ids_by_type,
                        value_probability=value_probability,
                    ),
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
        title: str | None = None
        language: LinkLanguage | None = None
        if self.pybool():
            title = self.domain_word().replace("-", " ").title()
            if self.pybool():
                language = self.random_element(list(LinkLanguage))
        return Link(url=self.url(), title=title, language=language)


class TemporalEntityProvider(PythonFakerProvider):
    """Faker provider that can return a custom TemporalEntity with random precision."""

    def temporal_entity(
        self,
        allowed_precision_levels: list[TemporalEntityPrecision],
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


def _given_language(original: Text | Link, raw: Any) -> str | None:  # noqa: ANN401
    """Return the language code given for a text or link before validation."""
    if raw is None:
        language = original.language
    elif isinstance(raw, dict):
        language = raw.get("language")
    else:  # e.g. plain strings as shorthand for texts
        language = None
    if isinstance(language, Enum):
        return str(language.value)
    return language if isinstance(language, str) else None


class AnonymizationProvider(PythonFakerProvider):
    """Faker provider that replaces values with dummy values of the same shape."""

    def __init__(
        self,
        factory: FakerFactory,
        factories_by_language: Mapping[str, FakerFactory] | None = None,
    ) -> None:
        """Configure the faker factories to use for each text language.

        Args:
            factory: The faker factory this provider is added to
            factories_by_language: Factories by language code, e.g. `de`
        """
        super().__init__(factory)
        self._factories_by_language = dict(factories_by_language or {})

    def factory_for_language(self, language: str | None) -> FakerFactory:
        """Return the factory for the given language, or roll a die if unknown."""
        if language and (factory := self._factories_by_language.get(language)):
            return factory
        if self._factories_by_language:
            return self.random_element(list(self._factories_by_language.values()))
        return cast("FakerFactory", self.generator)

    def similar_text(self, original: str, language: str | None = None) -> str:
        """Return random words with roughly the same length as the original.

        Args:
            original: Text to match the length of
            language: Language code of the words, e.g. `de`, random if unknown

        Returns:
            Random words in the given language
        """
        factory = self.factory_for_language(language)
        words: list[str] = []
        while original and len(" ".join(words)) < len(original):
            words.append(str(factory.format("word")))
        return " ".join(words)

    def similar_int(self, original: int) -> int:
        """Return a random integer with the same sign and number of digits."""
        digits = len(str(abs(original)))
        value = self.random_int(10 ** (digits - 1) if digits > 1 else 0, 10**digits - 1)
        return -value if original < 0 else value

    def anonymous_string(
        self, original: str, field_infos: list[RandomFieldInfo]
    ) -> str:
        """Return a dummy string, adhering to a pattern if the original matches one."""
        for info in field_infos:
            if info.inner_type is not str or not any(
                re.match(pattern, original) for pattern in info.regex_patterns
            ):
                continue
            candidates: list[str | None] = []
            if info.numerify_patterns:
                candidates.append(
                    self.generator.numerify_patterns(
                        info.numerify_patterns, info.regex_patterns
                    )
                )
            if re.search(r"[0-9]", original):
                candidates.append(
                    self.generator.numerify_patterns(
                        [re.sub(r"[0-9]", "#", original)], info.regex_patterns
                    )
                )
            if string_examples := [e for e in info.examples if isinstance(e, str)]:
                candidates.append(self.random_element(string_examples))
            if anonymized := next((c for c in candidates if c), None):
                return anonymized
            msg = f"Cannot anonymize string matching {info.regex_patterns}"
            raise RuntimeError(msg)
        return self.similar_text(original)

    def anonymous_value(  # noqa: PLR0911
        self,
        original: Any,  # noqa: ANN401
        field_infos: list[RandomFieldInfo],
        raw: Any = None,  # noqa: ANN401
    ) -> Any:  # noqa: ANN401
        """Return a dummy value of the same type and shape as the validated original.

        Args:
            original: Value validated against its mex-common type
            field_infos: Infos for all types of the corresponding extracted field
            raw: The original before validation, to look up the given languages,
                because validation would detect a language for texts without one

        Returns:
            Dummy value of the same type, lists keep their length
        """
        if isinstance(original, list):
            raw_items = raw if isinstance(raw, list) else [None] * len(original)
            return [
                self.anonymous_value(item, field_infos, raw_item)
                for item, raw_item in zip(original, raw_items, strict=True)
            ]
        if isinstance(original, Text | Link):
            language = _given_language(original, raw)
            if isinstance(original, Text):
                return Text(
                    value=self.similar_text(original.value, language),
                    language=original.language,
                )
            return Link(
                url=self.generator.url(),
                title=self.similar_text(original.title, language)
                if original.title
                else None,
                language=original.language,
            )
        if isinstance(original, Identifier):
            return type(original).generate(self.random_int(0, 2**31))
        if isinstance(original, TemporalEntity):
            return type(original)(
                self.generator.temporal_entity([original.precision]),
                precision=original.precision,
            )
        if isinstance(original, Enum):
            return self.random_element(list(type(original)))
        if isinstance(original, bool):
            return self.pybool()
        if isinstance(original, int):
            return self.similar_int(original)
        if isinstance(original, str):
            return self.anonymous_string(original, field_infos)
        return self.anonymous_raw_value(original)

    def anonymous_raw_value(  # noqa: PLR0911
        self,
        original: Any,  # noqa: ANN401
        language: str | None = None,
    ) -> Any:  # noqa: ANN401
        """Return a dummy value of the same shape for raw, untyped data.

        This is the fallback for values that do not validate against their type.
        Language keys of text-like dictionaries are kept as they are and texts
        within these dictionaries are generated in that language.
        """
        if isinstance(original, list):
            return [self.anonymous_raw_value(item, language) for item in original]
        if isinstance(original, dict):
            if isinstance(given := original.get("language"), str):
                language = given
            return {
                key: value
                if key == "language"
                else self.anonymous_raw_value(value, language)
                for key, value in original.items()
            }
        if isinstance(original, bool):
            return self.pybool()
        if isinstance(original, int):
            return self.similar_int(original)
        if isinstance(original, float):
            return self.pyfloat()
        if isinstance(original, str):
            return self.similar_text(original, language)
        return original
