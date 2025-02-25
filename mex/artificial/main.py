from pathlib import Path
from typing import Annotated

import typer
from faker import Faker

from mex.common.logging import logger
from mex.common.merged.main import create_merged_item
from mex.common.models import (
    EXTRACTED_MODEL_CLASSES,
    AnyExtractedModel,
    AnyMergedModel,
    ItemsContainer,
    PaginatedItemsContainer,
)
from mex.extractors.artificial.identity import IdentityMap, restore_identities
from mex.extractors.pipeline import asset, run_job_in_process
from mex.extractors.publisher.filter import filter_merged_items
from mex.extractors.publisher.load import write_merged_items
from mex.extractors.settings import Settings


@asset(group_name="merged_artificial")
def extracted_items(
    factories: Faker, identities: IdentityMap
) -> ItemsContainer[AnyExtractedModel]:
    """Create artificial extracted items."""
    restore_identities(identities)  # restore state of memory identity provider
    return ItemsContainer[AnyExtractedModel](
        items=[m for c in EXTRACTED_MODEL_CLASSES for m in factories.extracted_items(c)]
    )


@asset(group_name="merged_artificial")
def merged_items(
    extracted_items: ItemsContainer[AnyExtractedModel],
) -> PaginatedItemsContainer[AnyMergedModel]:
    """Transform artificial extracted items into merged items."""
    return PaginatedItemsContainer[AnyMergedModel](
        items=[
            create_merged_item(m.stableTargetId, [m], None, validate_cardinality=True)
            for m in extracted_items.items
        ],
        total=len(extracted_items.items),
    )


@asset(group_name="merged_artificial")
def filtered_items(
    merged_items: PaginatedItemsContainer[AnyMergedModel],
) -> PaginatedItemsContainer[AnyMergedModel]:
    """Filter to be published items by allow list."""
    return PaginatedItemsContainer[AnyMergedModel](
        items=list(filter_merged_items(merged_items.items)),
        total=len(merged_items.items),
    )


@asset(group_name="merged_artificial")
def load(filtered_items: PaginatedItemsContainer[AnyMergedModel]) -> None:
    """Write the filtered items into a new-line delimited JSON file."""
    write_merged_items(filtered_items.items)


def artificial(
    count: Annotated[
        int,
        typer.Option(
            help="Number of artificial items to approximately create.",
            min=len(EXTRACTED_MODEL_CLASSES) * 2,
            max=int(10e6 - 1),
        ),
    ] = 100,
    chattiness: Annotated[
        int,
        typer.Option(
            help="Maximum number of words to approximately produce for text fields.",
            min=2,
            max=100,
        ),
    ] = 10,
    path: Annotated[
        Path | None,
        typer.Option(
            help="Where to write the resulting `publisher.ndjson` file.",
            show_default=str(Path.cwd()),
            file_okay=False,
            dir_okay=True,
            writable=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:  # pragma: no cover
    """Generate merged artificial items."""
    settings = Settings.get()
    settings.artificial.count = count
    settings.artificial.chattiness = chattiness
    settings.work_dir = path or Path.cwd()
    logger.info("starting artificial data generation")
    run_job_in_process("merged_artificial")
    logger.info("artificial data generation done")


def cli() -> None:  # pragma: no cover
    """Wrap cli in typer."""
    typer.run(artificial)
