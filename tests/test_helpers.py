import json
from collections.abc import Callable, Iterable, Sequence
from itertools import islice
from pathlib import Path

import pytest
from faker import Faker
from faker.typing import SeedType
from pydantic import BaseModel

from mex.artificial.constants import DEFAULT_LOCALE, DEFAULT_MODELS
from mex.artificial.helpers import (
    create_faker,
    generate_artificial_extracted_items,
    generate_artificial_items_and_rule_sets,
    generate_artificial_merged_items,
    register_factories,
    write_merged_items,
)
from mex.artificial.types import LocaleType

TEST_DATA_PATH = Path(__file__).parent / "test_data"


def test_faker() -> None:
    faker = create_faker(["en_US", "de_DE"], 42)
    register_factories(faker, 1)
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
