from pathlib import Path
from typing import Annotated

import typer

from mex.artificial.helpers import create_factories, create_faker
from mex.artificial.identity import create_identities
from mex.artificial.load import write_merged_items
from mex.artificial.settings import ArtificialSettings
from mex.common.logging import logger
from mex.common.merged.main import create_merged_item
from mex.common.models import EXTRACTED_MODEL_CLASSES


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
    settings = ArtificialSettings.get()
    settings.count = count
    settings.chattiness = chattiness
    settings.work_dir = path or Path.cwd()
    logger.info("starting artificial data generation")
    faker = create_faker(settings.locale, settings.seed)
    identities = create_identities(faker, settings.count)
    factories = create_factories(faker, identities)
    extracted_items = [
        m for c in EXTRACTED_MODEL_CLASSES for m in factories.extracted_items(c)
    ]
    merged_items = [
        create_merged_item(m.stableTargetId, [m], None, validate_cardinality=True)
        for m in extracted_items
    ]
    write_merged_items(merged_items)
    logger.info("artificial data generation done")


def cli() -> None:  # pragma: no cover
    """Wrap cli in typer."""
    typer.run(artificial)
