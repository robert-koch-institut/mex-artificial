from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer

from mex.artificial.helpers import generate_artificial_merged_items, write_merged_items
from mex.common.logging import logger
from mex.common.models import EXTRACTED_MODEL_CLASSES


def artificial(  # noqa: PLR0913
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
    seed: Annotated[
        int,
        typer.Option(
            help="The seed value for faker randomness.",
        ),
    ] = 0,
    locale: Annotated[
        Sequence[str],
        typer.Option(
            help="The locale to use for faker.",
        ),
    ] = (
        "de_DE",
        "en_US",
    ),
    models: Annotated[
        Sequence[str],
        typer.Option(
            help="The names of models to use for faker.",
        ),
    ] = (
        "AccessPlatform",
        "Activity",
        "BibliographicResource",
        "ContactPoint",
        "Distribution",
        "Organization",
        "OrganizationalUnit",
        "Person",
        "Resource",
        "Variable",
        "VariableGroup",
    ),
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
    logger.info("starting artificial data generation")
    write_merged_items(
        generate_artificial_merged_items(locale, seed, count, chattiness, models),
        path or Path.cwd(),
    )
    logger.info("artificial data generation done")


def cli() -> None:  # pragma: no cover
    """Wrap cli in typer."""
    typer.run(artificial)
