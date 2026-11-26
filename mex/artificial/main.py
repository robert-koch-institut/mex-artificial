import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
import yaml

from mex.artificial.constants import (
    DEFAULT_CHATTINESS,
    DEFAULT_COUNT,
    DEFAULT_LOCALE,
    DEFAULT_MODELS,
    DEFAULT_SEED,
)
from mex.artificial.helpers import (
    anonymize_mapping,
    create_artificial_mapping_item,
    dump_mapping_item,
    dump_yaml,
    generate_artificial_merged_items,
    stem_type_from_path,
    write_merged_items,
)
from mex.common.logging import logger
from mex.common.models import MAPPING_MODEL_CLASSES


@contextmanager
def _log_to_stderr() -> Generator[None, None, None]:
    """Temporarily send log output to stderr, to keep stdout clean for data."""
    handlers = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout
    ]
    for handler in handlers:
        handler.setStream(sys.stderr)
    try:
        yield
    finally:
        for handler in handlers:
            handler.setStream(sys.stdout)


def artificial(  # noqa: PLR0913, PLR0917
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


MAPPING_STEM_TYPES = sorted(m.stemType for m in MAPPING_MODEL_CLASSES)


def _validate_mapping_stem_type(value: str) -> str:
    """Ensure the given stem type has a corresponding mapping model."""
    if value not in MAPPING_STEM_TYPES:
        msg = f"must be one of: {', '.join(MAPPING_STEM_TYPES)}"
        raise typer.BadParameter(msg)
    return value


def mapping(
    stem_type: Annotated[
        str,
        typer.Option(
            "--stem-type",
            help="The stem type of the mapping to create, e.g. `Person`.",
            callback=_validate_mapping_stem_type,
        ),
    ],
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
    path: Annotated[
        Path | None,
        typer.Option(
            help="File to write the YAML mapping to, instead of stdout.",
            file_okay=True,
            dir_okay=False,
            writable=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Generate an artificial mapping and write it as YAML to stdout or a file."""
    locale = locale or DEFAULT_LOCALE
    item = create_artificial_mapping_item(stem_type, locale, seed, chattiness)
    output = dump_mapping_item(item)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
        logger.info("wrote %s to %s", item.entityType, path)
    else:
        typer.echo(output, nl=False)


def anonymize(
    file: Annotated[
        Path,
        typer.Argument(
            help=(
                "Mapping YAML file to anonymize, the stem type is derived from the "
                "file name prefix, e.g. `Resource_grippeweb-plus.yaml`."
            ),
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
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
    path: Annotated[
        Path | None,
        typer.Option(
            help="File to write the anonymized YAML mapping to, instead of stdout.",
            file_okay=True,
            dir_okay=False,
            writable=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Anonymize a mapping YAML file: drop comments and replace all setValues."""
    try:
        stem_type = stem_type_from_path(file)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="FILE") from error
    raw_mapping = yaml.safe_load(file.read_text(encoding="utf-8"))
    if not isinstance(raw_mapping, dict):
        msg = "file does not contain a YAML mapping"
        raise typer.BadParameter(msg, param_hint="FILE")
    locale = locale or DEFAULT_LOCALE
    if path:
        output = dump_yaml(anonymize_mapping(raw_mapping, stem_type, locale, seed))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
        logger.info("wrote anonymized %sMapping to %s", stem_type, path)
    else:
        with _log_to_stderr():
            output = dump_yaml(anonymize_mapping(raw_mapping, stem_type, locale, seed))
        typer.echo(output, nl=False)


def main() -> None:  # pragma: no cover
    """Wrap entrypoint in typer."""
    typer.run(artificial)


def mapping_main() -> None:  # pragma: no cover
    """Wrap mapping entrypoint in typer."""
    typer.run(mapping)


def anonymize_main() -> None:  # pragma: no cover
    """Wrap anonymize entrypoint in typer."""
    typer.run(anonymize)
