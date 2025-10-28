import json
from collections import defaultdict
from collections.abc import Generator, Iterable, Mapping, Sequence
from itertools import count, islice
from os import PathLike
from pathlib import Path
from typing import cast

from faker import Faker
from faker.typing import SeedType
from rich.progress import track

from mex.artificial.provider import (
    BuilderProvider,
    LinkProvider,
    NumerifyPatternsProvider,
    ReferenceProvider,
    TemporalEntityProvider,
    TextProvider,
)
from mex.artificial.types import LocaleType
from mex.common.merged.main import create_merged_item
from mex.common.models import (
    MEX_PRIMARY_SOURCE_IDENTIFIER,
    MEX_PRIMARY_SOURCE_IDENTIFIER_IN_PRIMARY_SOURCE,
    MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
    AnyExtractedModel,
    AnyMergedModel,
    AnyRuleSetResponse,
    ExtractedPrimarySource,
)
from mex.common.transform import MExEncoder
from mex.common.types import AnyMergedIdentifier, Validation

MEX_PRIMARY_SOURCE = ExtractedPrimarySource.model_construct(
    hadPrimarySource=MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
    identifier=MEX_PRIMARY_SOURCE_IDENTIFIER,
    identifierInPrimarySource=MEX_PRIMARY_SOURCE_IDENTIFIER_IN_PRIMARY_SOURCE,
    stableTargetId=MEX_PRIMARY_SOURCE_STABLE_TARGET_ID,
)


def create_faker(locale: LocaleType | list[str], seed: SeedType) -> Faker:
    """Create and initialize a new faker instance with the given locale and seed."""
    faker = Faker(locale=locale)
    faker.seed_instance(seed=seed)
    return faker


def register_factories(faker: Faker, chattiness: int) -> None:
    """Create faker providers and register them on each factory."""
    for factory in faker.factories:
        factory.add_provider(ReferenceProvider(factory))
        factory.add_provider(LinkProvider(factory))
        factory.add_provider(NumerifyPatternsProvider(factory))
        factory.add_provider(BuilderProvider(factory))
        factory.add_provider(TextProvider(factory, chattiness))
        factory.add_provider(TemporalEntityProvider(factory))


def create_artificial_merged_item(
    extracted_item: AnyExtractedModel | None,
    rule_set: AnyRuleSetResponse | None,
) -> AnyMergedModel | None:
    """Create a merged item from the given extracted item and rule-set."""
    return create_merged_item(
        next(i.stableTargetId for i in (extracted_item, rule_set) if i),
        [extracted_item] if extracted_item else [],
        rule_set,
        validation=Validation.IGNORE,
    )


def generate_artificial_extracted_items(
    locale: LocaleType,
    seed: SeedType,
    chattiness: int,
    stem_types: Sequence[str],
) -> Generator[AnyExtractedModel, None, None]:
    """Generate artificial extracted items for the given settings."""
    faker = create_faker(locale, seed)
    register_factories(faker, chattiness)
    ids_by_type: Mapping[str, set[AnyMergedIdentifier]] = defaultdict(
        set, {MEX_PRIMARY_SOURCE.stemType: {MEX_PRIMARY_SOURCE.stableTargetId}}
    )
    yield MEX_PRIMARY_SOURCE
    while True:
        item = cast("AnyExtractedModel", faker.extracted_item(stem_types, ids_by_type))
        ids_by_type[item.stemType].add(item.stableTargetId)
        yield item


def generate_artificial_items_and_rule_sets(
    locale: LocaleType,
    seed: SeedType,
    chattiness: int,
    stem_types: Sequence[str],
) -> Generator[tuple[AnyExtractedModel | None, AnyRuleSetResponse | None], None, None]:
    """Generate artificial extracted items and rule-sets for the settings."""
    faker = create_faker(locale, seed)
    register_factories(faker, chattiness)
    ids_by_type: Mapping[str, set[AnyMergedIdentifier]] = defaultdict(
        set, {MEX_PRIMARY_SOURCE.stemType: {MEX_PRIMARY_SOURCE.stableTargetId}}
    )
    yield (MEX_PRIMARY_SOURCE, None)
    for index in count():
        match faker.random_int(0, 2):
            case 0:
                item = faker.extracted_item(stem_types, ids_by_type)
                ids_by_type[item.stemType].add(item.stableTargetId)
                yield (item, None)
            case 1:
                rule_set = faker.standalone_rule_set(stem_types, index, ids_by_type)
                ids_by_type[rule_set.stemType].add(rule_set.stableTargetId)
                yield (None, rule_set)
            case 2:
                item = faker.extracted_item(stem_types, ids_by_type)
                rule_set = faker.rule_set_for_item(item, ids_by_type)
                yield (item, rule_set)


def generate_artificial_merged_items(
    locale: LocaleType,
    seed: SeedType,
    chattiness: int,
    stem_types: Sequence[str],
) -> Generator[AnyMergedModel, None, None]:
    """Generate artificial merged items for the given settings."""
    for extracted_item, rule_set in generate_artificial_items_and_rule_sets(
        locale, seed, chattiness, stem_types
    ):
        if merged_item := create_artificial_merged_item(extracted_item, rule_set):
            yield merged_item


def write_merged_items(
    items: Iterable[AnyMergedModel],
    count: int,
    out_path: PathLike[str],
) -> None:
    """Write the desired number of items from the incoming stream to an NDJSON file."""
    with (Path(out_path) / "publisher.ndjson").open("w", encoding="utf-8") as fh:
        for item in track(islice(items, count), total=count, description="working..."):
            line = json.dumps(item, ensure_ascii=False, sort_keys=True, cls=MExEncoder)
            fh.write(f"{line}\n")
