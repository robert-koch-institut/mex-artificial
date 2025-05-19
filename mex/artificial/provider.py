import re
from collections.abc import Sequence
from datetime import datetime
from enum import Enum
from functools import partial
from typing import Any, cast, get_args, get_origin

from annotated_types import MaxLen, MinLen
from faker import Generator as FakerFactory
from faker.providers import BaseProvider as BaseFakerProvider
from faker.providers.internet import Provider as InternetFakerProvider
from faker.providers.python import Provider as PythonFakerProvider
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from mex.artificial.types import IdentityMap
from mex.common.identity import Identity
from mex.common.models import EXTRACTED_MODEL_CLASSES_BY_NAME, AnyExtractedModel
from mex.common.transform import ensure_prefix
from mex.common.types import (
    TEMPORAL_ENTITY_FORMATS_BY_PRECISION,
    UTC,
    Email,
    Identifier,
    Link,
    LinkLanguage,
    TemporalEntity,
    TemporalEntityPrecision,
    Text,
)


class RandomFieldInfo(BaseModel):
    """Randomized pick of matching inner type and patterns for a field."""

    inner_type: Any
    numerify_patterns: list[str] = []
    regex_patterns: list[str] = []


class BuilderProvider(PythonFakerProvider):
    """Faker provider that deals with interpreting pydantic model fields."""

    def min_max_for_field(self, field: FieldInfo) -> tuple[int, int]:
        """Return a min and max item count for a field."""
        if get_origin(field.annotation) is list:
            # calculate the item counts based on field annotations
            min_items = 0
            max_items = self.pyint(1, 3)
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

    def ensure_list(self, values: object) -> list[object]:
        """Wrap single object in list, replace None with [] and return list as is."""
        if values is None:
            return []
        if isinstance(values, list):
            return values
        return [values]

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
                for e in self.ensure_list(field.examples)
                if isinstance(e, str)
            ],
            regex_patterns=[m.pattern for m in field.metadata if hasattr(m, "pattern")],
        )

    def field_value(
        self,
        field: FieldInfo,
        identity: Identity,
    ) -> list[Any]:
        """Get a single artificial value for the given field and identity."""
        field_info = self.get_random_field_info(field)
        if field_info.regex_patterns and field_info.numerify_patterns:
            factory = partial(
                self.generator.numerify_patterns,
                field_info.numerify_patterns,
                field_info.regex_patterns,
            )
        elif issubclass(field_info.inner_type, Identifier):
            factory = partial(
                self.generator.reference, field_info.inner_type, exclude=identity
            )
        elif issubclass(field_info.inner_type, Link):
            factory = self.generator.link
        elif issubclass(field_info.inner_type, Email):
            factory = self.generator.email
        elif issubclass(field_info.inner_type, Text):
            factory = self.generator.text_object
        elif issubclass(field_info.inner_type, TemporalEntity):
            factory = partial(
                self.generator.temporal_entity,
                field_info.inner_type.ALLOWED_PRECISION_LEVELS,
            )
        elif issubclass(field_info.inner_type, Enum):
            factory = partial(self.random_element, field_info.inner_type)
        elif issubclass(field_info.inner_type, str):
            factory = self.generator.text_string
        elif issubclass(field_info.inner_type, int):
            factory = self.generator.random_int
        else:
            msg = f"Cannot create fake data for {field}"
            raise RuntimeError(msg)
        return [
            value
            for _ in range(self.pyint(*self.min_max_for_field(field)))
            if (value := factory()) is not None
        ]

    def extracted_items(self, stem_types: Sequence[str]) -> list[AnyExtractedModel]:
        """Get a list of extracted items for the given model classes."""
        items = []
        for stem_type in stem_types:
            entity_type = ensure_prefix(stem_type, "Extracted")
            model = EXTRACTED_MODEL_CLASSES_BY_NAME[entity_type]
            for identity in cast("list[Identity]", self.generator.identities(model)):
                # manually set identity related fields
                payload: dict[str, Any] = {
                    "identifier": identity.identifier,
                    "hadPrimarySource": identity.hadPrimarySource,
                    "identifierInPrimarySource": identity.identifierInPrimarySource,
                    "stableTargetId": identity.stableTargetId,
                    "entityType": entity_type,
                }
                # dynamically populate all other fields
                for name, field in model.model_fields.items():
                    if name not in payload:
                        payload[name] = self.field_value(field, identity)
                items.append(model.model_validate(payload))
        return items


class IdentityProvider(BaseFakerProvider):
    """Faker provider that creates identities and helps with referencing them."""

    def __init__(self, factory: FakerFactory, identities: IdentityMap) -> None:
        """Create and persist identities for all entity types."""
        super().__init__(factory)
        self._identities = identities

    def identities(self, model: type[AnyExtractedModel]) -> list[Identity]:
        """Return a list of identities for the given model class."""
        return self._identities[model.__name__.removeprefix("Extracted")]

    def reference(
        self,
        inner_type: type[Identifier],
        exclude: Identity,
    ) -> Identifier | None:
        """Return ID for random identity of given type (that is not excluded)."""
        if choices := [
            identity
            for entity_type in re.findall(
                r"Merged([A-Za-z]+)Identifier", str(inner_type)
            )
            for identity in self._identities[entity_type]
            # avoid self-references by skipping excluded ids
            if identity.stableTargetId != exclude.stableTargetId
        ]:
            return Identifier(self.random_element(choices).stableTargetId)
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
        return " ".join(self.generator.word() for _ in range(self.pyint(1, 3)))

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
