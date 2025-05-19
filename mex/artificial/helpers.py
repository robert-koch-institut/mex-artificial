import json
from collections.abc import Iterable, Sequence
from os import PathLike
from pathlib import Path
from typing import cast

from faker import Faker
from faker.typing import SeedType

from mex.artificial.identity import create_identities
from mex.artificial.provider import (
    BuilderProvider,
    IdentityProvider,
    LinkProvider,
    NumerifyPatternsProvider,
    TemporalEntityProvider,
    TextProvider,
)
from mex.artificial.types import IdentityMap, LocaleType
from mex.common.logging import logger
from mex.common.merged.main import create_merged_item
from mex.common.models import AnyExtractedModel, AnyMergedModel
from mex.common.transform import MExEncoder


def create_faker(locale: LocaleType | list[str], seed: SeedType) -> Faker:
    """Create and initialize a new faker instance with the given locale and seed."""
    faker = Faker(locale=locale)
    faker.seed_instance(seed=seed)
    return faker


def register_factories(faker: Faker, identities: IdentityMap, chattiness: int) -> None:
    """Create faker providers and register them on each factory."""
    for factory in faker.factories:
        factory.add_provider(IdentityProvider(factory, identities))
        factory.add_provider(LinkProvider(factory))
        factory.add_provider(NumerifyPatternsProvider(factory))
        factory.add_provider(BuilderProvider(factory))
        factory.add_provider(TextProvider(factory, chattiness))
        factory.add_provider(TemporalEntityProvider(factory))


def create_merged_items(
    extracted_items: list[AnyExtractedModel],
) -> list[AnyMergedModel]:
    """Create merged items for a list of extracted items."""
    return [
        create_merged_item(m.stableTargetId, [m], None, validate_cardinality=True)
        for m in extracted_items
    ]


def generate_artificial_extracted_items(
    locale: LocaleType,
    seed: SeedType,
    count: int,
    chattiness: int,
    stem_types: Sequence[str],
) -> list[AnyExtractedModel]:
    """Generate a list of artificial extracted items for the given settings."""
    faker = create_faker(locale, seed)
    identities = create_identities(faker, count)
    register_factories(faker, identities, chattiness)
    return cast("list[AnyExtractedModel]", faker.extracted_items(stem_types))


def generate_artificial_merged_items(
    locale: LocaleType,
    seed: SeedType,
    count: int,
    chattiness: int,
    stem_types: Sequence[str],
) -> list[AnyMergedModel]:
    """Generate a list of artificial merged items for the given settings."""
    extracted_items = generate_artificial_extracted_items(
        locale, seed, count, chattiness, stem_types
    )
    return create_merged_items(extracted_items)


def write_merged_items(
    items: Iterable[AnyMergedModel], out_path: PathLike[str]
) -> None:
    """Write the incoming items into a new-line delimited JSON file."""
    logging_counter = 0
    with (Path(out_path) / "publisher.ndjson").open("w", encoding="utf-8") as fh:
        for item in items:
            line = json.dumps(item, ensure_ascii=False, sort_keys=True, cls=MExEncoder)
            fh.write(f"{line}\n")
            logging_counter += 1
    logger.info("%s merged items were written", logging_counter)
