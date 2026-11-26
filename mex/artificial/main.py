import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from ruamel.yaml import YAML

from mex.artificial.constants import (
    DEFAULT_CHATTINESS,
    DEFAULT_COUNT,
    DEFAULT_LOCALE,
    DEFAULT_MODELS,
    DEFAULT_SEED,
)
from mex.artificial.helpers import (
    anonymize_mapping_file,
    create_artificial_mapping_item,
    dump_mapping_item,
    find_mapping_files,
    generate_artificial_merged_items,
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


def merged_command(  # noqa: PLR0913, PLR0917
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


def mapping_command(
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


def anonymize_command(  # noqa: C901, PLR0912
    file: Annotated[
        Path,
        typer.Argument(
            help=(
                "Mapping or filter YAML file, or folder of such files, to anonymize. "
                "The stem type is derived from the start of the file name, e.g. "
                "`Resource_grippeweb-plus.yaml` or `variable-group_foo.yaml`. "
                "Files ending in `_filter` or `-filter` are treated as filters, "
                "e.g. `activity_filter.yaml`. Folders are searched recursively."
            ),
            exists=True,
            file_okay=True,
            dir_okay=True,
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
            help=(
                "Where to write the anonymized YAML. For a single file: a file or "
                "folder, defaults to stdout. For a folder: a folder outside of it, "
                "that mirrors its structure, required."
            ),
            file_okay=True,
            dir_okay=True,
            writable=True,
            resolve_path=True,
        ),
    ] = None,
) -> None:
    """Anonymize mapping and filter YAML files.

    Comments are dropped from both, setValues are only replaced in mappings.
    """
    locale = locale or DEFAULT_LOCALE
    if file.is_dir():
        if not path:
            msg = "is required when anonymizing a folder"
            raise typer.BadParameter(msg, param_hint="--path")
        if path.is_file():
            msg = "must be a folder when anonymizing a folder"
            raise typer.BadParameter(msg, param_hint="--path")
        if path.is_relative_to(file):
            msg = "must not be the input folder or inside of it"
            raise typer.BadParameter(msg, param_hint="--path")
        written = 0
        for in_file in find_mapping_files(file):
            relative = in_file.relative_to(file)
            try:
                output = anonymize_mapping_file(in_file, locale, seed)
            except ValueError as error:
                logger.warning("skipping %s: %s", relative, error)
                continue
            out_file = path / relative
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(output, encoding="utf-8")
            written += 1
        logger.info("wrote %s anonymized mappings to %s", written, path)
        return
    if path and path.is_dir():
        path /= file.name
    try:
        if path:
            output = anonymize_mapping_file(file, locale, seed)
        else:
            with _log_to_stderr():
                output = anonymize_mapping_file(file, locale, seed)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="FILE") from error
    raw_mapping = YAML(typ="safe").load(file)
    if not isinstance(raw_mapping, dict):
        msg = "file does not contain a YAML mapping"
        raise typer.BadParameter(msg, param_hint="FILE")
    locale = locale or DEFAULT_LOCALE
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(output, encoding="utf-8")
        logger.info("wrote anonymized mapping to %s", path)
    else:
        typer.echo(output, nl=False)


def merged() -> None:  # pragma: no cover
    """Wrap merged items entrypoint in typer."""
    typer.run(merged_command)


def mapping() -> None:  # pragma: no cover
    """Wrap mapping entrypoint in typer."""
    typer.run(mapping_command)


def anonymize() -> None:  # pragma: no cover
    """Wrap anonymize entrypoint in typer."""
    typer.run(anonymize_command)
