import re
from collections.abc import Sequence
from typing import Annotated, Any

import pytest
from faker import Faker
from faker.providers.lorem.de_DE import Provider as GermanLorem
from faker.providers.lorem.en_US import Provider as EnglishLorem
from pydantic import BaseModel, Field, ValidationError
from pydantic.fields import FieldInfo
from pytest import MonkeyPatch

from mex.artificial.constants import DEFAULT_MODELS
from mex.artificial.dummy import (
    DUMMY_ORGANIZATIONAL_UNITS,
    DUMMY_ORGANIZATIONS,
    DUMMY_PERSONS,
)
from mex.artificial.helpers import create_faker
from mex.artificial.models import RandomFieldInfo
from mex.artificial.provider import (
    BuilderProvider,
    adapt_format,
    format_shape,
    format_similarity,
)
from mex.common.models import MappingRule
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
    no_min: Sequence[str] = []
    has_min: Sequence[bytes] = Field([], min_length=2)
    has_max: Sequence[bytes] = Field([], max_length=5)
    is_required: int
    is_optional: bool | None = None
    is_union: float | Sequence[float]
    is_inner_union: Sequence[float | int] = []
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
    is_nested_pattern: Sequence[
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
        "fullName": ["four popular"],
        "givenName": ["assume support", "tree near", "whole address better"],
        "isniId": [
            "https://isni.org/isni/9163457923022584",
            "https://isni.org/isni/9753513933287115",
        ],
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
        "affiliation": ["PrimarySource00000007"],
        "email": ["PrimarySource00000007"],
        "familyName": ["PrimarySource00000007"],
        "givenName": ["PrimarySource00000007"],
        "isniId": ["PrimarySource00000007"],
    }


def test_builder_provider_workflow_rule(
    faker: Faker, ids_by_type: dict[str, list[str]]
) -> None:
    rule = faker.workflow_rule(
        "Person",
        ids_by_type,
        value_probability=0.75,
    )
    assert rule.model_dump(exclude_defaults=True) == {
        "forbiddenPublishingTarget": ["datenkompass"],
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
    inner_type = Sequence[MergedPrimarySourceIdentifier | MergedOrganizationIdentifier]
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


@pytest.mark.parametrize(
    "stem_type",
    sorted(
        set(DEFAULT_MODELS) | {"Consent", "Location", "PrimarySource", "ResourceSeries"}
    ),
)
def test_builder_provider_mapping_item(
    faker: Faker, ids_by_type: dict[str, list[str]], stem_type: str
) -> None:
    mapping = faker.mapping_item(stem_type, ids_by_type)
    assert mapping.entityType == f"{stem_type}Mapping"
    assert mapping.hadPrimarySource
    assert mapping.identifierInPrimarySource
    for field in mapping.hadPrimarySource:
        assert field.mappingRules


def test_builder_provider_mapping_item_populates_all_rule_fields(
    faker: Faker, ids_by_type: dict[str, list[str]]
) -> None:
    rules = [
        rule
        for _ in range(5)
        for field in faker.mapping_item("Resource", ids_by_type).title
        for rule in field.mappingRules
    ]
    for name in MappingRule.model_fields:
        assert any(getattr(rule, name) is not None for rule in rules), name


def test_builder_provider_mapping_item_no_empty_models(
    faker: Faker, ids_by_type: dict[str, list[str]]
) -> None:
    for _ in range(5):
        mapping = faker.mapping_item("Person", ids_by_type)
        for field in mapping.fullName:
            assert field.model_dump(exclude_none=True)
            for rule in field.mappingRules:
                assert rule.model_dump(exclude_none=True)


def test_builder_provider_mapping_value_error(faker: Faker) -> None:
    with pytest.raises(RuntimeError, match="Cannot create fake mapping data"):
        faker.mapping_value(
            FieldInfo.from_annotation(float),
            FieldInfo.from_annotation(str),
            {},
            is_list=False,
        )


def test_builder_provider_mapping_item_error(
    faker: Faker, ids_by_type: dict[str, list[str]], monkeypatch: MonkeyPatch
) -> None:
    calls: list[int] = []

    def invalid_mapping_model(*_: object, **__: object) -> dict[str, Any]:
        calls.append(1)
        return {"mappingRules": []}  # violates `min_length=1`

    monkeypatch.setattr(BuilderProvider, "mapping_model", invalid_mapping_model)
    with pytest.raises(ValidationError):
        faker.mapping_item("Person", ids_by_type, _attempts_left=2)
    assert len(calls) >= 3


@pytest.mark.parametrize("original", ["", "a", "Testbeschreibung", "x" * 200])
def test_anonymization_provider_similar_text(faker: Faker, original: str) -> None:
    text = faker.similar_text(original)
    assert len(original) <= len(text) <= len(original) + 25
    assert bool(text) is bool(original)


@pytest.mark.parametrize("original", [0, 7, 42, -1234, 10**9])
def test_anonymization_provider_similar_int(faker: Faker, original: int) -> None:
    value = faker.similar_int(original)
    assert len(str(abs(value))) == len(str(abs(original)))
    assert (value < 0) is (original < 0)


def test_anonymization_provider_anonymous_string(faker: Faker) -> None:
    pattern = r"^https://orcid\.org/[-X0-9]{9,21}$"
    infos = [
        RandomFieldInfo(
            inner_type=str,
            numerify_patterns=["https://orcid.org/####-####-####-####"],
            regex_patterns=[pattern],
            examples=["https://orcid.org/0000-0002-9079-593X"],
        )
    ]
    original = "https://orcid.org/0000-0003-2300-3928"
    anonymized = faker.anonymous_string(original, infos)
    assert re.match(pattern, anonymized)
    assert anonymized != original
    # strings not matching any pattern become text of similar length
    assert re.match(r"^[^/]+$", faker.anonymous_string("plain text", infos))


def test_anonymization_provider_anonymous_string_numerify_original(
    faker: Faker,
) -> None:
    pattern = r"^https://www\.geonames\.org/[0-9]+$"
    infos = [RandomFieldInfo(inner_type=str, regex_patterns=[pattern])]
    original = "https://www.geonames.org/2950159"
    anonymized = faker.anonymous_string(original, infos)
    assert re.match(pattern, anonymized)
    assert len(anonymized) == len(original)


def test_anonymization_provider_anonymous_string_error(faker: Faker) -> None:
    infos = [RandomFieldInfo(inner_type=str, regex_patterns=[r"^[a-z]+$"])]
    with pytest.raises(RuntimeError, match="Cannot anonymize string"):
        faker.anonymous_string("secret", infos)


def test_anonymization_provider_anonymous_value(faker: Faker) -> None:
    original = [
        Text(value="Hallo Welt", language=TextLanguage.DE),
        Link(url="https://secret.example", title="Secret", language=None),
        MergedOrganizationIdentifier("bFQoRhcVH5DHU6"),
        YearMonthDay("2020-01-02"),
        APIType["REST"],
        True,
        123,
        2.5,
    ]
    anonymized = faker.anonymous_value(original, [])
    assert [type(v) for v in anonymized] == [type(v) for v in original]
    text, link, identifier, date, _, _, number, raw_float = anonymized
    assert text.language == TextLanguage.DE
    assert text.value != "Hallo Welt"
    assert link.url != "https://secret.example"
    assert link.title
    assert identifier != original[2]
    assert date.precision == TemporalEntityPrecision.DAY
    assert 100 <= number <= 999
    assert isinstance(raw_float, float)


def test_anonymization_provider_anonymous_raw_value(faker: Faker) -> None:
    anonymized = faker.anonymous_raw_value(
        {"value": "Deutschland", "language": "de", "n": [1, None]}
    )
    assert anonymized["language"] == "de"
    assert anonymized["value"] != "Deutschland"
    assert anonymized["n"][1] is None


GERMAN_WORDS = set(GermanLorem.word_list)
ENGLISH_WORDS = set(EnglishLorem.word_list)


@pytest.mark.parametrize(
    ("language", "words"),
    [("de", GERMAN_WORDS), ("en", ENGLISH_WORDS)],
    ids=["german", "english"],
)
def test_anonymization_provider_similar_text_language(
    language: str, words: set[str]
) -> None:
    faker = create_faker(["de_DE", "en_US"], 0, 5)
    for _ in range(20):
        text = faker.similar_text("ein ganz normaler satz mit worten", language)
        assert set(text.split()) <= words


def test_anonymization_provider_similar_text_rolls_die_without_language() -> None:
    faker = create_faker(["de_DE", "en_US"], 0, 5)
    texts = [faker.similar_text("one two three four", None) for _ in range(30)]
    # unknown languages also roll a die, as there is no `fr_FR` locale
    texts += [faker.similar_text("one two three four", "fr") for _ in range(30)]
    assert any(set(text.split()) <= GERMAN_WORDS - ENGLISH_WORDS for text in texts)
    assert any(set(text.split()) <= ENGLISH_WORDS - GERMAN_WORDS for text in texts)


def test_anonymization_provider_anonymous_value_language() -> None:
    faker = create_faker(["de_DE", "en_US"], 0, 5)
    original = [
        Text(value="ein deutscher satz mit worten", language=TextLanguage.DE),
        Text(value="an english sentence with words", language=TextLanguage.EN),
        Link(url="https://a.b", title="ein deutscher titel", language="de"),
        Link(url="https://a.b", title="an english title", language="en"),
    ]
    for _ in range(10):
        de_text, en_text, de_link, en_link = faker.anonymous_value(original, [])
        assert set(de_text.value.split()) <= GERMAN_WORDS
        assert set(en_text.value.split()) <= ENGLISH_WORDS
        assert set(de_link.title.split()) <= GERMAN_WORDS
        assert set(en_link.title.split()) <= ENGLISH_WORDS


def test_anonymization_provider_anonymous_value_raw_language() -> None:
    faker = create_faker(["de_DE", "en_US"], 0, 5)
    # validation detected `en` for this text, but the raw input had no language
    original = [Text(value="an english sentence", language=TextLanguage.EN)]
    texts = [
        faker.anonymous_value(original, [], [{"value": "an english sentence"}])[0]
        for _ in range(30)
    ]
    assert any(set(t.value.split()) <= GERMAN_WORDS - ENGLISH_WORDS for t in texts)
    # the raw input language wins over the detected language
    (text,) = faker.anonymous_value(
        original, [], [{"value": "an english sentence", "language": "de"}]
    )
    assert set(text.value.split()) <= GERMAN_WORDS


def test_anonymization_provider_anonymous_raw_value_language() -> None:
    faker = create_faker(["de_DE", "en_US"], 0, 5)
    for _ in range(10):
        anonymized = faker.anonymous_raw_value(
            [{"value": "Deutschland ist ein Land", "language": "de"}]
        )
        assert set(anonymized[0]["value"].split()) <= GERMAN_WORDS


@pytest.mark.parametrize(
    ("value", "collapsed", "full"),
    [
        ("FG 99", "a 9", "AA 99"),
        ("fg31", "a9", "aa99"),
        ("Felicitás, Juturna", "a, a", "Aaaaaaaaa, Aaaaaaa"),
        ("resolvedr@rki.de", "a@a.a", "aaaaaaaaa@aaa.aa"),
    ],
)
def test_format_shape(value: str, collapsed: str, full: str) -> None:
    assert format_shape(value, collapse=True) == collapsed
    assert format_shape(value) == full


def test_format_similarity() -> None:
    assert format_similarity("fg 31", "FG 99") > format_similarity("fg 31", "C1")
    assert format_similarity("fg 31", "C1") > format_similarity("fg 31", "child-unit")
    assert format_similarity("a@b.c", "x@y.z") == 3.5


@pytest.mark.parametrize(
    ("value", "original", "expected"),
    [
        ("C1", "fg 31", "c 1"),
        ("FG 99", "fg31", "fg99"),
        ("Robert Koch-Institut", "PAUL-EHRLICH-INSTITUT", "ROBERT KOCH-INSTITUT"),
        ("Resolved, Roland", "Mustermann, Max", "Resolved, Roland"),
        ("FG 99", "Q", "FG 99"),
    ],
)
def test_adapt_format(value: str, original: str, expected: str) -> None:
    assert adapt_format(value, original) == expected


def test_anonymization_provider_similar_synonym(faker: Faker) -> None:
    results = {
        faker.similar_synonym("fg 31", [DUMMY_ORGANIZATIONAL_UNITS]) for _ in range(30)
    }
    # a random unit is picked, then its most similarly formatted synonym
    assert results == {"c 1", "fg 99"}
    # the group with the most similarly formatted synonyms is picked
    groups = [DUMMY_ORGANIZATIONS, DUMMY_PERSONS]
    for _ in range(10):
        assert faker.similar_synonym("x.y@rki.de", groups).endswith(
            ("@rki.de", "@mail.tld")
        )
