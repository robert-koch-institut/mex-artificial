from typing import Annotated, Any

import pytest
from faker import Faker
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from mex.artificial.models import RandomFieldInfo
from mex.common.types import (
    APIType,
    Link,
    MergedOrganizationIdentifier,
    MergedPrimarySourceIdentifier,
    TemporalEntity,
    TemporalEntityPrecision,
    Text,
    TextLanguage,
    YearMonth,
    YearMonthDay,
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
        "no_min": (0, 4),
        "has_min": (2, 6),
        "has_max": (0, 5),
        "is_required": (1, 1),
        "is_optional": (0, 1),
        "is_union": (1, 1),
        "is_inner_union": (0, 3),
        "is_union_with_pattern": (0, 1),
        "is_nested_pattern": (0, 5),
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
            examples=[
                "http://wikidata.org/entity/Q679041",
                "http://wikidata.org/entity/P123",
            ],
        ),
        "is_nested_pattern": RandomFieldInfo(
            inner_type=str,
            numerify_patterns=["https://dfg.de/foobar/#####"],
            regex_patterns=[r"^https://dfg\.de/foobar/[0-9]{1,64}$"],
            examples=["https://dfg.de/foobar/10179"],
        ),
    }


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        (
            Annotated[
                str,
                Field(
                    pattern=r"^https://foo\.example/[a-z0-9]{9}$",
                    examples=["https://foo.example/01k5qnb77"],
                ),
            ],
            ["https://foo.example/48k7qnb64"],
        ),
        (
            Annotated[
                str,
                Field(
                    examples=["info@rki.de"],
                    pattern="^[^@ \\t\\r\\n]+@[^@ \\t\\r\\n]+\\.[^@ \\t\\r\\n]+$",
                    json_schema_extra={"format": "email"},
                ),
            ],
            ["info@rki.de"],
        ),
        (
            MergedPrimarySourceIdentifier,
            ["PrimarySource00000007"],
        ),
        (
            Link,
            [
                Link(url="https://www.sheppard-tucker.com/"),
            ],
        ),
        (
            Text,
            [
                Text(
                    value="Whole magazine truth stop whose. On traditional measure "
                    "example sense peace.",
                    language=TextLanguage.EN,
                )
            ],
        ),
        (
            YearMonthDay | YearMonth,
            [TemporalEntity("1996-09")],
        ),
        (
            APIType,
            [APIType["OTHER"]],
        ),
        (
            str,
            ["amount event"],
        ),
        (
            int,
            [6890],
        ),
    ],
)
def test_builder_provider_field_value(
    faker: Faker,
    ids_by_type: dict[str, list[str]],
    annotation: Any,  # noqa: ANN401
    expected: Any,  # noqa: ANN401
) -> None:
    field = FieldInfo.from_annotation(annotation)
    assert faker.field_value(field, ids_by_type) == expected


def test_builder_provider_field_value_error(faker: Faker) -> None:
    field = FieldInfo.from_annotation(object)

    with pytest.raises(RuntimeError, match="Cannot create fake data"):
        faker.field_value(field, {})


def test_builder_provider_extracted_item(
    faker: Faker, ids_by_type: dict[str, list[str]]
) -> None:
    extracted_item = faker.extracted_item(
        ["ContactPoint"],
        ids_by_type,
    )
    assert extracted_item.model_dump(exclude_defaults=True) == {
        "hadPrimarySource": "PrimarySource00000007",
        "identifierInPrimarySource": "ContactPoint_8",
        "email": ["info@rki.de"],
        "identifier": "fVWC01006cQWIynNJ526b3",
        "stableTargetId": "htOot14HcSLqexpYQsMKwj",
    }


def test_builder_provider_additive_rule(
    faker: Faker, ids_by_type: dict[str, list[str]]
) -> None:
    rule = faker.additive_rule(
        "Person",
        ids_by_type,
        value_probability=1,
    )
    assert rule.model_dump(exclude_defaults=True) == {
        "affiliation": ["Organization000000008"],
        "email": ["info@rki.de"],
        "familyName": ["season take play"],
        "isniId": ["https://isni.org/isni/7840801609753513"],
    }


def test_builder_provider_subtractive_rule(
    faker: Faker, ids_by_type: dict[str, list[str]]
) -> None:
    extracted_item = faker.extracted_item(["Person"], ids_by_type)
    rule = faker.subtractive_rule(
        extracted_item,
        value_probability=1,
    )
    assert rule.model_dump(exclude_defaults=True) == {
        "affiliation": [
            "Organization000000008",
            "Organization000000005",
            "Organization000000007",
        ],
        "email": ["info@rki.de"],
        "fullName": ["show"],
        "givenName": ["me level tree"],
        "memberOf": ["OrganizationalUnit008", "OrganizationalUnit001"],
        "orcidId": ["https://orcid.org/8711-5871-4841-858X"],
    }


def test_builder_provider_preventive_rule(
    faker: Faker, ids_by_type: dict[str, list[str]]
) -> None:
    extracted_item = faker.extracted_item(["Person"], ids_by_type)
    rule = faker.preventive_rule(
        extracted_item,
        value_probability=0.75,
    )
    assert rule.model_dump(exclude_defaults=True) == {
        "email": ["PrimarySource00000007"],
        "familyName": ["PrimarySource00000007"],
        "givenName": ["PrimarySource00000007"],
        "isniId": ["PrimarySource00000007"],
        "orcidId": ["PrimarySource00000007"],
    }


def test_builder_provider_standalone_rule_set(
    faker: Faker, ids_by_type: dict[str, list[str]]
) -> None:
    rule_set = faker.standalone_rule_set(
        ["Person"],
        ids_by_type,
        identifier_seed=42,
        value_probability=0.75,
    )
    assert rule_set.model_dump(exclude_defaults=True) == {
        "additive": {
            "affiliation": [
                "Organization000000007",
                "Organization000000005",
                "Organization000000008",
            ],
            "email": ["info@rki.de"],
            "familyName": ["season take play", "force"],
            "fullName": [
                "opportunity blood",
                "leader four",
                "push while democratic",
                "me level tree",
                "ever assume support",
            ],
            "isniId": [
                "https://isni.org/isni/9753513933287115",
                "https://isni.org/isni/1484185839894719",
                "https://isni.org/isni/9342320947112201",
                "https://isni.org/isni/8483396947751591",
                "https://isni.org/isni/3304135256012309",
                "https://isni.org/isni/0139916151090321",
            ],
        },
        "stableTargetId": "b3wrW78ASMOyBrXF6ikQAO",
    }


def test_reference_provider(faker: Faker, ids_by_type: dict[str, list[str]]) -> None:
    inner_type = list[MergedPrimarySourceIdentifier | MergedOrganizationIdentifier]
    assert faker.reference(inner_type, ids_by_type) == "Organization000000005"
    assert faker.reference(dict[str, str], ids_by_type) is None


def test_link_provider(faker: Faker) -> None:
    assert faker.link() == Link(
        language=None, title="Williams Sheppard", url="https://howard-snow.com/"
    )


def test_temporal_entity_provider(faker: Faker) -> None:
    assert faker.temporal_entity([TemporalEntityPrecision.DAY]) == TemporalEntity(
        "2024-01-31"
    )


def test_text_provider_string(faker: Faker) -> None:
    assert faker.text_string() == "son voice"


def test_text_provider_text(faker: Faker) -> None:
    assert faker.text_object() == Text(
        value="Else memory if. Whose group through despite cause. Sense peace economy "
        "travel. Total financial role together range line beyond its.",
        language=TextLanguage.EN,
    )
