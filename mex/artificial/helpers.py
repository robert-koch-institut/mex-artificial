import json
from collections import OrderedDict, defaultdict
from collections.abc import Generator, Iterable, Mapping, Sequence
from itertools import count, islice
from os import PathLike
from pathlib import Path
from typing import cast

from faker import Faker
from faker.typing import SeedType
from rich.progress import track

from mex.artificial.constants import (
    DEFAULT_CHATTINESS,
    DEFAULT_COUNT,
    DEFAULT_LOCALE,
    DEFAULT_MODELS,
    DEFAULT_SEED,
    MEX_PRIMARY_SOURCE,
)
from mex.artificial.models import ExtractedItemAndRuleSet
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
from mex.common.models import AnyExtractedModel, AnyMergedModel
from mex.common.transform import MExEncoder
from mex.common.types import AnyMergedIdentifier, Validation


def create_faker(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
) -> Faker:
    """Create and initialize a new faker instance with the given settings."""
    Faker.seed(seed)
    faker = Faker(locale=locale)
    for factory in faker.factories:
        factory.add_provider(ReferenceProvider(factory))
        factory.add_provider(LinkProvider(factory))
        factory.add_provider(NumerifyPatternsProvider(factory))
        factory.add_provider(BuilderProvider(factory))
        factory.add_provider(TextProvider(factory, chattiness))
        factory.add_provider(TemporalEntityProvider(factory))
    return faker


def generate_artificial_extracted_items(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
) -> Generator[AnyExtractedModel, None, None]:
    """Generate artificial extracted items for the given settings."""
    faker = create_faker(locale, seed, chattiness)
    ids_by_type: Mapping[str, OrderedDict[AnyMergedIdentifier, None]] = defaultdict(
        OrderedDict,
        {
            MEX_PRIMARY_SOURCE.stemType: OrderedDict(
                {MEX_PRIMARY_SOURCE.stableTargetId: None}
            )
        },
    )
    yield MEX_PRIMARY_SOURCE
    while True:
        item = cast("AnyExtractedModel", faker.extracted_item(stem_types, ids_by_type))
        ids_by_type[item.stemType][item.stableTargetId] = None
        yield item


def generate_artificial_items_and_rule_sets(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
) -> Generator[ExtractedItemAndRuleSet, None, None]:
    """Generate artificial extracted items and rule-sets for the settings."""
    faker = create_faker(locale, seed, chattiness)
    ids_by_type: Mapping[str, OrderedDict[AnyMergedIdentifier, None]] = defaultdict(
        OrderedDict,
        {
            MEX_PRIMARY_SOURCE.stemType: OrderedDict(
                {MEX_PRIMARY_SOURCE.stableTargetId: None}
            )
        },
    )
    yield ExtractedItemAndRuleSet(extracted_item=MEX_PRIMARY_SOURCE)
    for index in count():
        match faker.random_int(0, 2):
            case 0:
                item = faker.extracted_item(stem_types, ids_by_type)
                ids_by_type[item.stemType][item.stableTargetId] = None
                yield ExtractedItemAndRuleSet(extracted_item=item)
            case 1:
                rule_set = faker.standalone_rule_set(stem_types, ids_by_type, index)
                ids_by_type[rule_set.stemType][rule_set.stableTargetId] = None
                yield ExtractedItemAndRuleSet(rule_set=rule_set)
            case 2:
                item = faker.extracted_item(stem_types, ids_by_type)
                rule_set = faker.rule_set_for_item(item, ids_by_type)
                yield ExtractedItemAndRuleSet(extracted_item=item, rule_set=rule_set)


def generate_artificial_merged_items(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
) -> Generator[AnyMergedModel, None, None]:
    """Generate artificial merged items for the given settings."""
    for item_combination in generate_artificial_items_and_rule_sets(
        locale, seed, chattiness, stem_types
    ):
        identifier = next(
            i.stableTargetId
            for i in (item_combination.extracted_item, item_combination.rule_set)
            if i
        )
        if merged_item := create_merged_item(
            identifier,
            [item_combination.extracted_item]
            if item_combination.extracted_item
            else [],
            item_combination.rule_set,
            validation=Validation.IGNORE,
        ):
            yield merged_item


def write_merged_items(
    items: Iterable[AnyMergedModel],
    count: int = DEFAULT_COUNT,
    out_path: PathLike[str] | None = None,
) -> None:
    """Write the desired number of items from the incoming stream to an NDJSON file."""
    file_path = Path(out_path or Path.cwd()) / "publisher.ndjson"
    with file_path.open("w", encoding="utf-8") as fh:
        for item in track(islice(items, count), total=count, description="working..."):
            line = json.dumps(item, ensure_ascii=False, sort_keys=True, cls=MExEncoder)
            fh.write(f"{line}\n")
