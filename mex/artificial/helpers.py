import json
from collections import OrderedDict, defaultdict
from collections.abc import Generator, Iterable, Mapping, Sequence
from itertools import count, islice
from os import PathLike
from pathlib import Path
from typing import Any, cast, get_args

import yaml
from faker import Faker
from faker.typing import SeedType
from pydantic import TypeAdapter, ValidationError
from rich.progress import track

from mex.artificial.constants import (
    DEFAULT_CHATTINESS,
    DEFAULT_COUNT,
    DEFAULT_LOCALE,
    DEFAULT_MAPPING_REFERENCE_COUNT,
    DEFAULT_MODELS,
    DEFAULT_SEED,
    MEX_PRIMARY_SOURCE,
)
from mex.artificial.models import ExtractedItemAndRuleSet
from mex.artificial.provider import (
    AnonymizationProvider,
    BuilderProvider,
    LinkProvider,
    NumerifyPatternsProvider,
    ReferenceProvider,
    TemporalEntityProvider,
    TextProvider,
    get_all_field_infos,
)
from mex.artificial.types import LocaleType
from mex.common.logging import logger
from mex.common.merged.main import create_merged_item
from mex.common.models import (
    EXTRACTED_MODEL_CLASSES,
    EXTRACTED_MODEL_CLASSES_BY_NAME,
    MAPPING_MODEL_CLASSES,
    MAPPING_MODEL_CLASSES_BY_NAME,
    AnyExtractedModel,
    AnyMappingModel,
    AnyMergedModel,
)
from mex.common.transform import MExEncoder, ensure_postfix, ensure_prefix
from mex.common.types import AnyMergedIdentifier, Identifier, Validation


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
        factory.add_provider(AnonymizationProvider(factory))
    return faker


def generate_artificial_extracted_items(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
) -> Generator[AnyExtractedModel, None, None]:
    """Infinitely generate extracted items for the given settings."""
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


def create_artificial_extracted_items(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
    count: int = DEFAULT_COUNT,
) -> list[AnyExtractedModel]:
    """Create a list of extracted items for the given settings."""
    return list(
        islice(
            generate_artificial_extracted_items(locale, seed, chattiness, stem_types),
            count,
        )
    )


def generate_artificial_items_and_rule_sets(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
) -> Generator[ExtractedItemAndRuleSet, None, None]:
    """Infinitely generate artificial extracted items and rule-sets."""
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
            case 0:  # only extracted item
                item = faker.extracted_item(stem_types, ids_by_type)
                ids_by_type[item.stemType][item.stableTargetId] = None
                yield ExtractedItemAndRuleSet(extracted_item=item)
            case 1:  # only rule set
                rule_set = faker.standalone_rule_set(stem_types, ids_by_type, index)
                ids_by_type[rule_set.stemType][rule_set.stableTargetId] = None
                yield ExtractedItemAndRuleSet(rule_set=rule_set)
            case 2:  # extracted item and rule set
                item = faker.extracted_item(stem_types, ids_by_type)
                rule_set = faker.rule_set_for_item(item, ids_by_type)
                ids_by_type[item.stemType][item.stableTargetId] = None
                yield ExtractedItemAndRuleSet(extracted_item=item, rule_set=rule_set)


def create_artificial_items_and_rule_sets(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
    count: int = DEFAULT_COUNT,
) -> list[ExtractedItemAndRuleSet]:
    """Create a list of artificial extracted items and rule-sets."""
    return list(
        islice(
            generate_artificial_items_and_rule_sets(
                locale, seed, chattiness, stem_types
            ),
            count,
        )
    )


def generate_artificial_merged_items(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
) -> Generator[AnyMergedModel, None, None]:
    """Infinitely generate merged items for the given settings."""
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


def create_artificial_merged_items(
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
    stem_types: Sequence[str] = DEFAULT_MODELS,
    count: int = DEFAULT_COUNT,
) -> list[AnyMergedModel]:
    """Create a list of merged items for the given settings."""
    return list(
        islice(
            generate_artificial_merged_items(locale, seed, chattiness, stem_types),
            count,
        )
    )


def create_artificial_mapping_item(
    stem_type: str,
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
    chattiness: int = DEFAULT_CHATTINESS,
) -> AnyMappingModel:
    """Create a single mapping item of the given stem type."""
    faker = create_faker(locale, seed, chattiness)
    ids_by_type: Mapping[str, list[AnyMergedIdentifier]] = {
        model.stemType: [
            cast("AnyMergedIdentifier", Identifier.generate(faker.random_int()))
            for _ in range(DEFAULT_MAPPING_REFERENCE_COUNT)
        ]
        for model in EXTRACTED_MODEL_CLASSES
    }
    return cast("AnyMappingModel", faker.mapping_item(stem_type, ids_by_type))


class _IndentedSafeDumper(yaml.SafeDumper):
    """YAML dumper that indents list items and writes `None` as an empty value."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:  # noqa: ARG002, FBT001, FBT002
        """Never emit indentless sequences."""
        super().increase_indent(flow, False)  # noqa: FBT003


_IndentedSafeDumper.add_representer(
    type(None),
    lambda dumper, _: dumper.represent_scalar("tag:yaml.org,2002:null", ""),
)


def dump_yaml(data: object) -> str:
    """Dump the given data into a formatted YAML string."""
    return yaml.dump(
        data,
        Dumper=_IndentedSafeDumper,
        allow_unicode=True,
        default_flow_style=False,
        indent=2,
        sort_keys=False,
        width=88,
    )


def dump_mapping_item(item: AnyMappingModel) -> str:
    """Dump a mapping item into a formatted YAML string."""
    return dump_yaml(
        item.model_dump(
            mode="json",
            exclude={"entityType"},
            exclude_defaults=True,
            exclude_none=True,
        )
    )


def stem_type_from_path(path: PathLike[str]) -> str:
    """Derive the mapping stem type from the prefix of a mapping file name.

    The prefix is the part of the file name before the first underscore, matched
    case-insensitively and ignoring dashes, e.g. `Resource_grippeweb-plus.yaml`,
    `resource.yaml` and `access-platform_mock.yaml` are all supported.

    Raises:
        ValueError: If the prefix does not match any mapping stem type
    """
    prefix = Path(path).stem.split("_", 1)[0]
    normalized = prefix.replace("-", "").lower()
    for model in MAPPING_MODEL_CLASSES:
        if model.stemType.lower() == normalized:
            return model.stemType
    msg = f"File name prefix `{prefix}` does not match any mapping stem type"
    raise ValueError(msg)


def _drop_comments(data: Any) -> Any:  # noqa: ANN401
    """Recursively remove all `comment` keys from the given data."""
    if isinstance(data, dict):
        return {k: _drop_comments(v) for k, v in data.items() if k != "comment"}
    if isinstance(data, list):
        return [_drop_comments(item) for item in data]
    return data


def _match_shape(anonymized: Any, original: Any) -> Any:  # noqa: ANN401
    """Restrict dictionaries to the keys (and key order) of the original data.

    Validation can add keys, e.g. a detected `language` for texts without one, or
    turn strings into texts, so the anonymized data is brought back into shape.
    """
    if isinstance(anonymized, dict) and isinstance(original, dict):
        return {
            k: _match_shape(anonymized[k], v) if k in anonymized else v
            for k, v in original.items()
        }
    if (
        isinstance(anonymized, dict)
        and isinstance(original, str)
        and isinstance(anonymized.get("value"), str)
    ):
        # plain strings are valid shorthands for texts, keep them as strings
        return anonymized["value"]
    if isinstance(anonymized, list) and isinstance(original, list):
        return [_match_shape(a, o) for a, o in zip(anonymized, original, strict=True)]
    return anonymized


def anonymize_mapping(
    raw_mapping: dict[str, Any],
    stem_type: str,
    locale: LocaleType = DEFAULT_LOCALE,
    seed: SeedType = DEFAULT_SEED,
) -> dict[str, Any]:
    """Anonymize a raw mapping, as loaded from a mapping YAML file.

    All `comment` keys are removed and all `setValues` are replaced with dummy
    values of the same type, as defined by the mex-common models. Lists keep their
    length and texts roughly keep their length. All other keys are kept as is.
    Values that do not validate against their type are anonymized by their shape.

    Args:
        raw_mapping: Mapping data loaded from YAML, need not be a valid model
        stem_type: Stem type of the mapping, e.g. `Resource`
        locale: Faker locale for the dummy values
        seed: Faker seed for the dummy values

    Returns:
        Anonymized copy of the raw mapping
    """
    faker = create_faker(locale, seed)
    mapping_class = MAPPING_MODEL_CLASSES_BY_NAME[ensure_postfix(stem_type, "Mapping")]
    extracted_class = EXTRACTED_MODEL_CLASSES_BY_NAME[
        ensure_prefix(stem_type, "Extracted")
    ]

    def anonymize_set_values(field_name: str, set_values: Any) -> Any:  # noqa: ANN401
        if set_values is None:
            return None
        if (mapping_field := mapping_class.model_fields.get(field_name)) and (
            extracted_field := extracted_class.model_fields.get(field_name)
        ):
            # `MappingFieldList[X]` holds setValues of type `X`
            adapter: TypeAdapter[Any] = TypeAdapter(
                get_args(mapping_field.annotation)[0]
            )
            try:
                typed = adapter.validate_python(set_values)
            except ValidationError:
                logger.warning("anonymizing invalid setValues of %s", field_name)
            else:
                dummy = faker.anonymous_value(
                    typed, get_all_field_infos(extracted_field)
                )
                return _match_shape(
                    adapter.dump_python(dummy, mode="json", exclude_none=True),
                    set_values,
                )
        else:
            logger.warning("anonymizing setValues of unknown field %s", field_name)
        return faker.anonymous_raw_value(set_values)

    def walk(field_name: str, data: Any) -> Any:  # noqa: ANN401
        if isinstance(data, dict):
            return {
                key: anonymize_set_values(field_name, value)
                if key == "setValues"
                else walk(field_name, value)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [walk(field_name, item) for item in data]
        return data

    return {
        name: walk(name, value) for name, value in _drop_comments(raw_mapping).items()
    }


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
