from re import Pattern
from typing import Annotated, Any
from unittest.mock import Mock

import pytest
from faker import Faker
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from mex.artificial.provider import RandomFieldInfo
from mex.common.models import ExtractedPrimarySource
from mex.common.testing import Joker
from mex.common.types import (
    APIType,
    Email,
    Identifier,
    Link,
    LinkLanguage,
    MergedPrimarySourceIdentifier,
    TemporalEntity,
    TemporalEntityPrecision,
    Text,
    TextLanguage,
)


class DummyModel(BaseModel):
    no_min: list[str] = []
    has_min: list[bytes] = Field([], min_length=2)
    has_max: list[bytes] = Field([], max_length=5)
    is_required: int
    is_optional: bool | None = None
    is_union: float | list[float]
    is_inner_union: list[float | int] = []
    is_union_with_pattern: (
        Annotated[
            str,
            Field(
                pattern=r"^https://wikidata\.org/entity/[PQ0-9]{2,64}$",
                examples=[
                    "http://wikidata.org/entity/Q679041",
                    "http://wikidata.org/entity/P123",
                ],
            ),
        ]
        | None
    ) = None
    is_nested_pattern: list[
        Annotated[
            str,
            Field(
                pattern=r"^https://dfg\.de/foobar/[0-9]{1,64}$",
                examples=["https://dfg.de/foobar/10179"],
            ),
        ]
    ] = []


def test_builder_provider_min_max_for_field(faker: Faker) -> None:
    min_max = {
        name: faker.min_max_for_field(field)
        for name, field in DummyModel.model_fields.items()
    }
    assert min_max == {
        "has_max": (0, 5),
        "has_min": (2, 3),
        "is_inner_union": (0, 1),
        "is_nested_pattern": (0, 3),
        "is_optional": (0, 1),
        "is_required": (1, 1),
        "is_union": (1, 1),
        "is_union_with_pattern": (0, 1),
        "no_min": (0, 3),
    }


def test_builder_provider_get_random_field_info(faker: Faker) -> None:
    random_field_info = {
        name: faker.get_random_field_info(field)
        for name, field in DummyModel.model_fields.items()
    }
    assert random_field_info == {
        "no_min": RandomFieldInfo(inner_type=str),
        "has_min": RandomFieldInfo(inner_type=bytes),
        "has_max": RandomFieldInfo(inner_type=bytes),
        "is_required": RandomFieldInfo(inner_type=int),
        "is_optional": RandomFieldInfo(inner_type=bool),
        "is_union": RandomFieldInfo(inner_type=float),
        "is_inner_union": RandomFieldInfo(inner_type=int),
        "is_union_with_pattern": RandomFieldInfo(
            inner_type=str,
            numerify_patterns=[
                "http://wikidata.org/entity/Q######",
                "http://wikidata.org/entity/P###",
            ],
            regex_patterns=[r"^https://wikidata\.org/entity/[PQ0-9]{2,64}$"],
        ),
        "is_nested_pattern": RandomFieldInfo(
            inner_type=str,
            numerify_patterns=["https://dfg.de/foobar/#####"],
            regex_patterns=[r"^https://dfg\.de/foobar/[0-9]{1,64}$"],
        ),
    }


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (
            Link,
            [
                Link(
                    language=LinkLanguage.DE, title="Pratt", url="https://turner.com/"
                ),
            ],
        ),
        (Email, ["lindathomas@example.net"]),
        (
            Text,
            [
                Text(
                    value="Language ball floor meet usually board necessary.",
                    language=TextLanguage.EN,
                )
            ],
        ),
        (TemporalEntity, [TemporalEntity("2003-06-21T16:11:41Z")]),
        (APIType, [APIType["SOAP"]]),
        (
            Annotated[
                Pattern,
                Field(
                    pattern=r"^https://foo\.example/[a-z0-9]{9}$",
                    examples=["https://foo.example/01k5qnb77"],
                ),
            ],
            ["https://foo.example/87k1qnb15"],
        ),
        (
            Annotated[
                str,
                Field(
                    pattern=r"^http://bar\.batz/[A-Z0-9]{2,64}$",
                    examples=["http://bar.batz/D001604"],
                ),
            ],
            ["http://bar.batz/D871158"],
        ),
        (
            str,
            ["suggest"],
        ),
    ],
)
def test_builder_provider_field_value(
    faker: Faker,
    annotation: Any,  # noqa: ANN401
    expected: Any,  # noqa: ANN401
) -> None:
    field = FieldInfo.from_annotation(annotation)
    identity = Mock(stableTargetId="00000000001234")

    assert faker.field_value(field, identity) == expected


def test_builder_provider_field_value_reference(faker: Faker) -> None:
    field = FieldInfo.from_annotation(MergedPrimarySourceIdentifier)
    identity = Mock(stableTargetId="00000000001234")
    reference = faker.field_value(field, identity)

    assert set(reference) < {
        i.stableTargetId for i in faker.identities(ExtractedPrimarySource)
    }


def test_builder_provider_field_value_error(faker: Faker) -> None:
    field = FieldInfo.from_annotation(object)
    identity = Mock(stableTargetId="00000000001234")

    with pytest.raises(RuntimeError, match="Cannot create fake data"):
        faker.field_value(field, identity)


def test_builder_provider_extracted_items(faker: Faker) -> None:
    models = faker.extracted_items(["ContactPoint"])
    assert models[0].model_dump(exclude_defaults=True) == {
        "email": ["udavis@example.net"],
        "hadPrimarySource": Joker(),
        "identifier": Joker(),
        "identifierInPrimarySource": "ContactPoint-4181830114",
        "stableTargetId": Joker(),
    }


def test_identity_provider_identities(faker: Faker) -> None:
    primary_sources = faker.identities(ExtractedPrimarySource)
    assert len(primary_sources) == 2
    assert primary_sources[0].model_dump() == {
        "hadPrimarySource": MergedPrimarySourceIdentifier("00000000000000"),
        "identifier": Joker(),
        "identifierInPrimarySource": "PrimarySource-2516530558",
        "stableTargetId": Joker(),
    }


def test_identity_provider_reference(faker: Faker) -> None:
    identities = list(faker.identities(ExtractedPrimarySource))

    for identity in identities:
        reference = faker.reference(MergedPrimarySourceIdentifier, identity)
        assert reference != identity.stableTargetId
        assert reference in [i.stableTargetId for i in identities]

    assert faker.reference([], Identifier("00000000000000")) is None


def test_link_provider(faker: Faker) -> None:
    assert faker.link() == Link(language=None, title=None, url="http://www.pratt.com/")


def test_temporal_entity_provider(faker: Faker) -> None:
    assert faker.temporal_entity([TemporalEntityPrecision.DAY]) == TemporalEntity(
        "2014-08-30"
    )


def test_text_provider_string(faker: Faker) -> None:
    assert faker.text_string() == "doctor edge suggest"


def test_text_provider_text(faker: Faker) -> None:
    assert faker.text_object() == Text(
        value=(
            "Sound central myself before year. Your majority feeling fact by four two. "
            "White owner onto knowledge other. First drug contain start almost wonder."
        ),
        language=TextLanguage.EN,
    )
