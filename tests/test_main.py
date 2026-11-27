import logging
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pytest import LogCaptureFixture
from ruamel.yaml import YAML
from typer import Typer
from typer.testing import CliRunner, Result

from mex.artificial.main import (
    _log_to_stderr,
    anonymize_command,
    mapping_command,
    merged_command,
)
from mex.common.logging import logger
from mex.common.models import (
    AccessPlatformMapping,
    AnyMappingModel,
    PersonMapping,
    ResourceMapping,
)


def _invoke(command: Callable[..., None], *args: Any, exit_code: int = 0) -> Result:  # noqa: ANN401
    app = Typer()
    app.command()(command)
    result = CliRunner().invoke(app, [str(arg) for arg in args])
    assert result.exit_code == exit_code, result.output
    return result


def _error_text(result: Result) -> str:
    return " ".join(re.sub(r"[│╭╮╰╯─]", " ", result.output).split())


def _load(path: Path) -> Any:  # noqa: ANN401
    return YAML(typ="safe").load(path.read_text(encoding="utf-8"))


def _generate_mapping(stem_type: str, out_file: Path) -> None:
    _invoke(mapping_command, "--stem-type", stem_type, "--path", out_file)


def test_main(caplog: LogCaptureFixture) -> None:
    _invoke(merged_command, "--count", 30)
    assert "artificial data generation done" in caplog.text


def test_mapping() -> None:
    doc = YAML(typ="safe").load(
        _invoke(mapping_command, "--stem-type", "Person").stdout
    )
    assert "fullName" in doc
    assert "entityType" not in doc


def test_mapping_invalid_stem_type() -> None:
    _invoke(mapping_command, "--stem-type", "Nope", exit_code=2)


def test_mapping_path(tmp_path: Path) -> None:
    out_file = tmp_path / "nested" / "mapping.yaml"
    _invoke(mapping_command, "--stem-type", "Activity", "--path", out_file)
    doc = _load(out_file)
    assert "title" in doc
    assert "entityType" not in doc


def test_anonymize(tmp_path: Path) -> None:
    generated = tmp_path / "Person_generated.yaml"
    _generate_mapping("Person", generated)
    in_file = tmp_path / "Person_with-comments.yaml"
    in_file.write_text(
        "# secret comment\n" + generated.read_text(encoding="utf-8"), encoding="utf-8"
    )

    result = _invoke(anonymize_command, in_file)
    assert "#" not in result.stdout
    assert "comment:" not in result.stdout
    PersonMapping.model_validate(YAML(typ="safe").load(result.stdout))

    out_file = tmp_path / "out" / "anonymized.yaml"
    assert _invoke(anonymize_command, in_file, "--path", out_file).stdout == ""
    PersonMapping.model_validate(_load(out_file))

    out_dir = tmp_path / "out"
    _invoke(anonymize_command, in_file, "--path", out_dir)
    PersonMapping.model_validate(_load(out_dir / in_file.name))


@pytest.mark.parametrize(
    ("file_name", "content", "message"),
    [
        ("Nope_mapping.yaml", "title: []\n", "does not start with any mapping stem"),
        ("Resource_list.yaml", "- a list\n", "does not contain a YAML mapping"),
    ],
)
def test_anonymize_invalid_file(
    tmp_path: Path, file_name: str, content: str, message: str
) -> None:
    in_file = tmp_path / file_name
    in_file.write_text(content, encoding="utf-8")
    assert message in _error_text(_invoke(anonymize_command, in_file, exit_code=2))


def test_log_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)
    try:
        with _log_to_stderr():
            logger.warning("to stderr")
        logger.warning("to stdout")
    finally:
        logger.removeHandler(handler)
    captured = capsys.readouterr()
    assert "to stderr" in captured.err
    assert "to stderr" not in captured.out
    assert "to stdout" in captured.out
    assert handler.stream is sys.stdout


def test_anonymize_folder(tmp_path: Path) -> None:
    in_dir = tmp_path / "mappings"
    models: dict[str, type[AnyMappingModel]] = {
        "Resource_one.yaml": ResourceMapping,
        "a/b/access-platform.yaml": AccessPlatformMapping,
        "nested/person_two.yml": PersonMapping,
    }
    for relative, model in models.items():
        _generate_mapping(model.stemType, in_dir / relative)
    (in_dir / "filters").mkdir()
    (in_dir / "filters" / "activity_filter.yaml").write_text(
        "# yaml comment\nfields:\n  - filterRules: [{rule: r}]\n    comment: c\n",
        encoding="utf-8",
    )
    (in_dir / "Unknown_three.yaml").write_text("title: []\n", encoding="utf-8")
    (in_dir / "Resource_list.yaml").write_text("- not a mapping\n", encoding="utf-8")
    (in_dir / "README.md").write_text("# not yaml\n", encoding="utf-8")

    out_dir = tmp_path / "anonymized"
    _invoke(anonymize_command, in_dir, "--path", out_dir)

    written = sorted(
        p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file()
    )
    assert written == sorted([*models, "filters/activity_filter.yaml"])
    assert _load(out_dir / "filters" / "activity_filter.yaml") == {
        "fields": [{"filterRules": [{"rule": "r"}]}]
    }
    for relative, model in models.items():
        output = (out_dir / relative).read_text(encoding="utf-8")
        assert output != (in_dir / relative).read_text(encoding="utf-8")
        model.model_validate(YAML(typ="safe").load(output))


@pytest.mark.parametrize(
    ("make_path", "message"),
    [
        (lambda tmp: None, "is required when anonymizing a folder"),
        (lambda tmp: tmp / "mappings", "must not be the input folder"),
        (lambda tmp: tmp / "mappings" / "out", "must not be the input folder"),
        (lambda tmp: tmp / "file.yaml", "must be a folder when anonymizing"),
    ],
    ids=["missing", "same", "inside", "file"],
)
def test_anonymize_folder_invalid_path(
    tmp_path: Path, make_path: Callable[[Path], Path | None], message: str
) -> None:
    in_dir = tmp_path / "mappings"
    in_dir.mkdir()
    (tmp_path / "file.yaml").write_text("", encoding="utf-8")
    path = make_path(tmp_path)
    args = [in_dir, "--path", path] if path else [in_dir]
    result = _invoke(anonymize_command, *args, exit_code=2)
    assert message in _error_text(result)
