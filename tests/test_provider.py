from typing import Annotated, Any

import pytest
from faker import Faker
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

from mex.artificial.models import RandomFieldInfo
from mex.common.models import (
    ExtractedPrimarySource,
)
from mex.common.types import (
    APIType,
    Identifier,
    Link,
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
        "familyName": ["force", "season take play"],
        "givenName": ["me level tree"],
        "isniId": ["https://isni.org/isni/9753513933287115"],
        "memberOf": ["OrganizationalUnit002", "OrganizationalUnit006"],
        "orcidId": [
            "https://orcid.org/8339-6947-7515-9179",
            "https://orcid.org/3304-1352-5601-2309",
            "https://orcid.org/4232-0947-1122-0186",
        ],
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
        "affiliation": ["Organization000000005"],
        "familyName": ["show", "way"],
        "fullName": ["support", "whole address better"],
        "givenName": ["gas score truth"],
        "isniId": ["https://isni.org/isni/8711587148418583"],
        "memberOf": ["OrganizationalUnit006"],
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
        "familyName": ["PrimarySource00000007"],
        "fullName": ["PrimarySource00000007"],
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
            "familyName": [
                "push while democratic",
                "ever assume support",
                "opportunity blood",
                "leader four",
                "me level tree",
            ],
            "givenName": [
                "truth at cut",
                "doctor edge suggest",
                "line benefit be",
                "suggest",
                "type movie",
            ],
            "memberOf": [
                "OrganizationalUnit007",
                "OrganizationalUnit008",
                "OrganizationalUnit002",
                "OrganizationalUnit005",
            ],
        },
        "stableTargetId": "b3wrW78ASMOyBrXF6ikQAO",
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
