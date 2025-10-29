from pathlib import Path
from typing import Annotated

import typer

from mex.artificial.constants import (
    DEFAULT_CHATTINESS,
    DEFAULT_COUNT,
    DEFAULT_LOCALE,
    DEFAULT_MODELS,
    DEFAULT_SEED,
)
from mex.artificial.helpers import generate_artificial_merged_items, write_merged_items
from mex.common.logging import logger


def artificial(  # noqa: PLR0913
    count: Annotated[
        int,
        typer.Option(
            help="Number of artificial items to approximately create.",
            min=1,
            max=int(10e6 - 1),
        ),
    ] = DEFAULT_COUNT,
    chattiness: Annotated[
        int,
        typer.Option(
            help="Maximum number of words to approximately produce for text fields.",
            min=2,
            max=100,
        ),
    ] = DEFAULT_CHATTINESS,
    seed: Annotated[
        int,
        typer.Option(
            help="The seed value for faker randomness.",
        ),
    ] = DEFAULT_SEED,
    locale: Annotated[
        list[str] | None,
        typer.Option(
            help="The locale to use for faker.",
            show_default=DEFAULT_LOCALE,
        ),
    ] = None,
    models: Annotated[
        list[str] | None,
        typer.Option(
            help="The names of models to use for faker.",
            show_default=DEFAULT_MODELS,
        ),
    ] = None,
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
    path = path or Path.cwd()
    locale = locale or DEFAULT_LOCALE
    models = models or DEFAULT_MODELS
    item_gen = generate_artificial_merged_items(locale, seed, chattiness, models)
    write_merged_items(item_gen, count, path)
    logger.info("artificial data generation done")


def main() -> None:  # pragma: no cover
    """Wrap entrypoint in typer."""
    typer.run(artificial)
