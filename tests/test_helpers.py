import json
from collections.abc import Callable, Iterable, Iterator, Sequence
from itertools import islice
from pathlib import Path
from typing import Any

import pytest
from faker import Faker
from faker.providers.lorem.de_DE import Provider as GermanLorem
from faker.providers.lorem.en_US import Provider as EnglishLorem
from faker.typing import SeedType
from pydantic import BaseModel
from ruamel.yaml import YAML

from mex.artificial.constants import DEFAULT_LOCALE, DEFAULT_MODELS
from mex.artificial.helpers import (
    anonymize_mapping,
    create_artificial_extracted_items,
    create_artificial_items_and_rule_sets,
    create_artificial_mapping_item,
    create_artificial_merged_items,
    create_faker,
    dump_mapping_item,
    dump_yaml,
    generate_artificial_extracted_items,
    generate_artificial_items_and_rule_sets,
    generate_artificial_merged_items,
    stem_type_from_path,
    write_merged_items,
)
from mex.artificial.types import LocaleType
from mex.common.models import (
    MAPPING_MODEL_CLASSES,
    MAPPING_MODEL_CLASSES_BY_NAME,
    PersonMapping,
)

TEST_DATA_PATH = Path(__file__).parent / "test_data"


def test_faker() -> None:
    faker = create_faker(["en_US", "de_DE"], 42, 1)
    assert isinstance(faker, Faker)
    assert faker.locales == ["en_US", "de_DE"]
    assert faker.text_string() == "site"


@pytest.mark.parametrize(
    ("generator_func", "expected_file"),
    [
        (
            generate_artificial_extracted_items,
            "extracted_items.json",
        ),
        (
            generate_artificial_items_and_rule_sets,
            "extracted_items_and_rule_sets.json",
        ),
        (
            generate_artificial_merged_items,
            "merged_items.json",
        ),
    ],
    ids=["extracted_items", "items_and_rule_sets", "merged_items"],
)
def test_generate_artificial_items(
    generator_func: Callable[
        [LocaleType, SeedType, int, Sequence[str]], Iterable[BaseModel]
    ],
    expected_file: str,
) -> None:
    gen = generator_func(DEFAULT_LOCALE, 42, 5, DEFAULT_MODELS)
    items = list(islice(gen, 10))
    output = [item.model_dump(mode="json") for item in items]

    expected_path = TEST_DATA_PATH / expected_file
    with expected_path.open(encoding="utf-8") as fh:
        expected = json.load(fh)

    assert output == expected


@pytest.mark.parametrize(
    ("creator_func", "expected_file"),
    [
        (
            create_artificial_extracted_items,
            "extracted_items.json",
        ),
        (
            create_artificial_items_and_rule_sets,
            "extracted_items_and_rule_sets.json",
        ),
        (
            create_artificial_merged_items,
            "merged_items.json",
        ),
    ],
    ids=["extracted_items", "items_and_rule_sets", "merged_items"],
)
def test_create_artificial_items(
    creator_func: Callable[
        [LocaleType, SeedType, int, Sequence[str], int], list[BaseModel]
    ],
    expected_file: str,
) -> None:
    items = creator_func(DEFAULT_LOCALE, 42, 5, DEFAULT_MODELS, 10)
    output = [item.model_dump(mode="json") for item in items]

    expected_path = TEST_DATA_PATH / expected_file
    with expected_path.open(encoding="utf-8") as fh:
        expected = json.load(fh)

    assert output == expected


def test_write_merged_items(tmp_path: Path) -> None:
    gen = generate_artificial_merged_items(DEFAULT_LOCALE, 42, 5, DEFAULT_MODELS)
    write_merged_items(gen, 23, tmp_path)

    output_file = tmp_path / "publisher.ndjson"
    assert output_file.exists()

    with output_file.open(encoding="utf-8") as fh:
        lines = fh.readlines()

    assert len(lines) == 23
    for line in lines:
        item = json.loads(line)
        assert "identifier" in item
        assert "entityType" in item


def test_create_artificial_mapping_item() -> None:
    item = create_artificial_mapping_item("Person", DEFAULT_LOCALE, 42, 5)
    assert isinstance(item, PersonMapping)
    assert item == create_artificial_mapping_item("Person", DEFAULT_LOCALE, 42, 5)


def test_dump_mapping_item() -> None:
    item = create_artificial_mapping_item("Person", DEFAULT_LOCALE, 42, 5)
    output = dump_mapping_item(item)
    assert not output.startswith("---")
    assert "\n  - " in output  # list items are indented below their key
    assert "entityType" not in output
    assert "null" not in output
    assert "[]" not in output
    assert PersonMapping.model_validate(YAML(typ="safe").load(output)) == item


def _without(data: object, keys: set[str]) -> object:
    if isinstance(data, dict):
        return {k: _without(v, keys) for k, v in data.items() if k not in keys}
    if isinstance(data, list):
        return [_without(item, keys) for item in data]
    return data


def _set_values_pairs(
    original: object,
    anonymized: Any,  # noqa: ANN401
) -> Iterator[tuple[Any, Any]]:
    if isinstance(original, dict):
        for key, value in original.items():
            if key == "setValues":
                yield value, anonymized[key]
            else:
                yield from _set_values_pairs(value, anonymized[key])
    elif isinstance(original, list):
        for o, a in zip(original, anonymized, strict=True):
            yield from _set_values_pairs(o, a)


@pytest.mark.parametrize(
    "stem_type", sorted(model.stemType for model in MAPPING_MODEL_CLASSES)
)
def test_anonymize_generated_mapping(stem_type: str) -> None:
    mapping_class = MAPPING_MODEL_CLASSES_BY_NAME[f"{stem_type}Mapping"]
    for seed in range(3):
        # use the artificial mapping generator to create realistic input files
        generated = create_artificial_mapping_item(stem_type, DEFAULT_LOCALE, seed)
        text = f"# secret comment\n{dump_mapping_item(generated)}# trailing\n"
        original = YAML(typ="safe").load(text)
        anonymized = anonymize_mapping(original, stem_type, DEFAULT_LOCALE, seed)

        # still a valid mapping and dumps without any comments
        mapping_class.model_validate(anonymized)
        output = dump_yaml(anonymized)
        assert "#" not in output
        assert "comment" not in output

        # everything except comments and setValues is kept as is
        assert _without(anonymized, {"setValues"}) == _without(
            original, {"comment", "setValues"}
        )

        # setValues keep their type, length and shape
        pairs = list(_set_values_pairs(_without(original, {"comment"}), anonymized))
        for before, after in pairs:
            assert type(after) is type(before)
            if isinstance(before, list):
                assert len(after) == len(before)
                items = list(zip(before, after, strict=True))
            else:
                items = [(before, after)]
            for item_before, item_after in items:
                assert type(item_after) is type(item_before)
                if isinstance(item_before, dict):
                    assert item_after.keys() == item_before.keys()
                    assert item_after.get("language") == item_before.get("language")
                if isinstance(item_before, dict) and "value" in item_before:
                    # texts are replaced and roughly keep their length
                    assert item_after["value"] != item_before["value"]
                    assert (
                        len(item_before["value"])
                        <= len(item_after["value"])
                        <= len(item_before["value"]) + 25
                    )


def _generated_raw_mapping(stem_type: str, seed: int = 0) -> dict[str, Any]:
    """Load a mapping generated by `artificial-mapping` like a YAML file."""
    item = create_artificial_mapping_item(stem_type, DEFAULT_LOCALE, seed)
    raw = YAML(typ="safe").load(dump_mapping_item(item))
    assert isinstance(raw, dict)
    return raw


def test_anonymize_mapping_drops_comments_and_keeps_unknown_keys() -> None:
    raw = _generated_raw_mapping("Resource")
    # add a key that the model does not know about
    raw["unknownField"] = [
        {"comment": "c", "mappingRules": [{"setValues": ["secret", 42, True]}]}
    ]
    anonymized = anonymize_mapping(raw, "Resource", DEFAULT_LOCALE, 0)
    assert "comment" not in dump_yaml(anonymized)
    (unknown,) = anonymized["unknownField"]
    assert unknown.keys() == {"mappingRules"}
    values = unknown["mappingRules"][0]["setValues"]
    assert [type(v) for v in values] == [str, int, bool]
    assert values[0] != "secret"
    assert 10 <= values[1] <= 99


def test_anonymize_mapping_does_not_add_keys() -> None:
    raw = _generated_raw_mapping("Resource")
    # drop the language from all generated texts, validation would detect one
    texts = [
        text
        for field in raw["title"]
        for rule in field["mappingRules"]
        for text in rule.get("setValues") or []
    ]
    assert texts
    for text in texts:
        text.pop("language", None)
    anonymized = anonymize_mapping(raw, "Resource", DEFAULT_LOCALE, 0)
    for field in anonymized["title"]:
        for rule in field["mappingRules"]:
            for text in rule.get("setValues") or []:
                assert text.keys() == {"value"}


def test_anonymize_mapping_invalid_set_values(caplog: pytest.LogCaptureFixture) -> None:
    raw = _generated_raw_mapping("Resource")
    # replace generated setValues with values of the wrong type and an empty value
    raw["title"] = [
        {
            "mappingRules": [
                {"setValues": [12345]},
                {"setValues": None},
                {"setValues": ["plain string text"]},
            ]
        }
    ]
    anonymized = anonymize_mapping(raw, "Resource", DEFAULT_LOCALE, 0)
    invalid, empty, shorthand = anonymized["title"][0]["mappingRules"]
    (number,) = invalid["setValues"]
    assert 10000 <= number <= 99999
    assert empty["setValues"] is None
    # plain strings are valid texts, but stay plain strings
    (text,) = shorthand["setValues"]
    assert isinstance(text, str)
    assert text != "plain string text"
    assert "anonymizing invalid setValues of title" in caplog.text


@pytest.mark.parametrize(
    ("file_name", "expected"),
    [
        ("Resource_grippeweb-plus.yaml", "Resource"),
        ("resource.yaml", "Resource"),
        ("access-platform_mock.yaml", "AccessPlatform"),
        ("OrganizationalUnit_foo_bar.yml", "OrganizationalUnit"),
    ],
)
def test_stem_type_from_path(file_name: str, expected: str) -> None:
    assert stem_type_from_path(Path("some", "dir", file_name)) == expected


def test_stem_type_from_path_error() -> None:
    with pytest.raises(ValueError, match="`Nope` does not match"):
        stem_type_from_path(Path("Nope_resource.yaml"))


def _reversed_keys(data: object) -> object:
    if isinstance(data, dict):
        return {k: _reversed_keys(data[k]) for k in reversed(list(data))}
    if isinstance(data, list):
        return [_reversed_keys(item) for item in data]
    return data


def _key_orders(data: object, path: str = "") -> Iterator[tuple[str, list[str]]]:
    if isinstance(data, dict):
        yield path, list(data)
        for key, value in data.items():
            yield from _key_orders(value, f"{path}.{key}")
    elif isinstance(data, list):
        for index, item in enumerate(data):
            yield from _key_orders(item, f"{path}[{index}]")


@pytest.mark.parametrize(
    "stem_type", sorted(model.stemType for model in MAPPING_MODEL_CLASSES)
)
def test_anonymize_mapping_keeps_key_order(stem_type: str) -> None:
    # reverse all keys, so the input order differs from the model field order
    original = _reversed_keys(_generated_raw_mapping(stem_type))
    assert isinstance(original, dict)
    text = dump_yaml(original)

    anonymized = anonymize_mapping(
        YAML(typ="safe").load(text), stem_type, DEFAULT_LOCALE, 0
    )
    output = dump_yaml(anonymized)

    expected = list(_key_orders(_without(original, {"comment"})))
    assert list(_key_orders(anonymized)) == expected
    assert list(_key_orders(YAML(typ="safe").load(output))) == expected
    # top-level fields appear in the output text in the input order
    top_level = [
        line.split(":")[0] for line in output.splitlines() if line[:1].isalpha()
    ]
    assert top_level == [k for k in original if k != "comment"]


def test_anonymize_mapping_keeps_text_languages() -> None:
    words_by_language = {
        "de": set(GermanLorem.word_list),
        "en": set(EnglishLorem.word_list),
    }
    checked = 0
    for seed in range(5):
        original = _generated_raw_mapping("Resource", seed)
        anonymized = anonymize_mapping(original, "Resource", ["de_DE", "en_US"], seed)
        for before, after in _set_values_pairs(
            _without(original, {"comment"}), anonymized
        ):
            for item_before, item_after in zip(
                before if isinstance(before, list) else [before],
                after if isinstance(after, list) else [after],
                strict=True,
            ):
                if not isinstance(item_before, dict):
                    continue
                language = item_before.get("language")
                text = item_after.get("value") or item_after.get("title")
                if language in words_by_language and text:
                    assert item_after.get("language") == language
                    assert set(text.split()) <= words_by_language[language], text
                    checked += 1
    assert checked > 10
