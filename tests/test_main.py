import logging
import re
import sys
from io import StringIO
from pathlib import Path

import pytest
from pytest import LogCaptureFixture
from ruamel.yaml import YAML
from typer import Typer
from typer.testing import CliRunner

from mex.artificial.main import _log_to_stderr, anonymize, artificial, mapping
from mex.common.logging import logger
from mex.common.models import PersonMapping


def test_main(caplog: LogCaptureFixture) -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(artificial)
    result = runner.invoke(app, ["--count", "30"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "artificial data generation done" in caplog.text


def test_mapping() -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(mapping)
    result = runner.invoke(app, ["--stem-type", "Person"], catch_exceptions=False)
    assert result.exit_code == 0
    doc = YAML(typ="safe").load(result.stdout)
    assert "fullName" in doc
    assert "entityType" not in doc


def test_mapping_invalid_stem_type() -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(mapping)
    result = runner.invoke(app, ["--stem-type", "Nope"])
    assert result.exit_code == 2


def test_mapping_path(tmp_path: Path) -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(mapping)
    out_file = tmp_path / "nested" / "mapping.yaml"
    result = runner.invoke(
        app,
        ["--stem-type", "Activity", "--path", str(out_file)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert result.stdout == ""
    doc = YAML(typ="safe").load(out_file.read_text(encoding="utf-8"))
    assert "title" in doc
    assert "entityType" not in doc


def test_anonymize(tmp_path: Path) -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(mapping)
    generated = tmp_path / "Person_generated.yaml"
    runner.invoke(
        app, ["--stem-type", "Person", "--path", str(generated)], catch_exceptions=False
    )
    in_file = tmp_path / "Person_with-comments.yaml"
    in_file.write_text(
        "# secret comment\n" + generated.read_text(encoding="utf-8"), encoding="utf-8"
    )

    app = Typer()
    app.command()(anonymize)
    result = runner.invoke(app, [str(in_file)], catch_exceptions=False)
    assert result.exit_code == 0
    assert "#" not in result.stdout
    assert "comment:" not in result.stdout
    PersonMapping.model_validate(YAML(typ="safe").load(result.stdout))

    out_file = tmp_path / "out" / "anonymized.yaml"
    result = runner.invoke(
        app, [str(in_file), "--path", str(out_file)], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert result.stdout == ""
    PersonMapping.model_validate(
        YAML(typ="safe").load(out_file.read_text(encoding="utf-8"))
    )


def test_anonymize_invalid_file_name(tmp_path: Path) -> None:
    in_file = tmp_path / "Nope_mapping.yaml"
    in_file.write_text("title: []\n", encoding="utf-8")
    app = Typer()
    app.command()(anonymize)
    result = CliRunner().invoke(app, [str(in_file)])
    assert result.exit_code == 2
    output = " ".join(re.sub(r"[│╭╮╰╯─]", " ", result.output).split())
    assert "does not match any mapping stem type" in output


def test_anonymize_invalid_yaml_content(tmp_path: Path) -> None:
    in_file = tmp_path / "Resource_list.yaml"
    in_file.write_text("- just\n- a list\n", encoding="utf-8")
    app = Typer()
    app.command()(anonymize)
    result = CliRunner().invoke(app, [str(in_file)])
    assert result.exit_code == 2
    output = " ".join(re.sub(r"[│╭╮╰╯─]", " ", result.output).split())
    assert "does not contain a YAML mapping" in output


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


def test_anonymize_keeps_field_order(tmp_path: Path) -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(mapping)
    generated = tmp_path / "Resource_generated.yaml"
    runner.invoke(
        app,
        ["--stem-type", "Resource", "--path", str(generated)],
        catch_exceptions=False,
    )
    # write the generated fields in reversed order, unlike the model field order
    raw = YAML(typ="safe").load(generated.read_text(encoding="utf-8"))
    order = list(reversed(list(raw)))
    in_file = tmp_path / "Resource_reordered.yaml"
    stream = StringIO()
    in_file.write_text(
        YAML().dump({key: raw[key] for key in order}, stream),
        encoding="utf-8",
    )

    app = Typer()
    app.command()(anonymize)
    result = runner.invoke(app, [str(in_file)], catch_exceptions=False)
    assert result.exit_code == 0
    assert list(YAML(typ="safe").load(result.stdout)) == order
