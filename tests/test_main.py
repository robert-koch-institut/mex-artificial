import logging
import re
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from pytest import LogCaptureFixture
from ruamel.yaml import YAML
from typer import Typer
from typer.testing import CliRunner

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


def test_main(caplog: LogCaptureFixture) -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(merged_command)
    result = runner.invoke(app, ["--count", "30"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "artificial data generation done" in caplog.text


def test_mapping() -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(mapping_command)
    result = runner.invoke(app, ["--stem-type", "Person"], catch_exceptions=False)
    assert result.exit_code == 0
    doc = YAML(typ="safe").load(result.stdout)
    assert "fullName" in doc
    assert "entityType" not in doc


def test_mapping_invalid_stem_type() -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(mapping_command)
    result = runner.invoke(app, ["--stem-type", "Nope"])
    assert result.exit_code == 2


def test_mapping_path(tmp_path: Path) -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(mapping_command)
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
    app.command()(mapping_command)
    generated = tmp_path / "Person_generated.yaml"
    runner.invoke(
        app, ["--stem-type", "Person", "--path", str(generated)], catch_exceptions=False
    )
    in_file = tmp_path / "Person_with-comments.yaml"
    in_file.write_text(
        "# secret comment\n" + generated.read_text(encoding="utf-8"), encoding="utf-8"
    )

    app = Typer()
    app.command()(anonymize_command)
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
    app.command()(anonymize_command)
    result = CliRunner().invoke(app, [str(in_file)])
    assert result.exit_code == 2
    output = " ".join(re.sub(r"[│╭╮╰╯─]", " ", result.output).split())
    assert "does not start with any mapping stem type" in output


def test_anonymize_invalid_yaml_content(tmp_path: Path) -> None:
    in_file = tmp_path / "Resource_list.yaml"
    in_file.write_text("- just\n- a list\n", encoding="utf-8")
    app = Typer()
    app.command()(anonymize_command)
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
    app.command()(mapping_command)
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
    YAML().dump({key: raw[key] for key in order}, in_file)

    app = Typer()
    app.command()(anonymize_command)
    result = runner.invoke(app, [str(in_file)], catch_exceptions=False)
    assert result.exit_code == 0
    assert list(YAML(typ="safe").load(result.stdout)) == order


def _generate_mapping(runner: CliRunner, stem_type: str, out_file: Path) -> None:
    app = Typer()
    app.command()(mapping_command)
    result = runner.invoke(
        app,
        ["--stem-type", stem_type, "--path", str(out_file)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0


def test_anonymize_folder(tmp_path: Path) -> None:
    runner = CliRunner()
    in_dir = tmp_path / "mappings"
    _generate_mapping(runner, "Resource", in_dir / "Resource_one.yaml")
    _generate_mapping(runner, "Person", in_dir / "nested" / "person_two.yml")
    _generate_mapping(
        runner, "AccessPlatform", in_dir / "a" / "b" / "access-platform.yaml"
    )
    (in_dir / "filters" / "activity_filter.yaml").parent.mkdir()
    (in_dir / "filters" / "activity_filter.yaml").write_text(
        "# yaml comment\nfields:\n  - filterRules: [{rule: r}]\n    comment: c\n",
        encoding="utf-8",
    )
    (in_dir / "Unknown_three.yaml").write_text("title: []\n", encoding="utf-8")
    (in_dir / "Resource_list.yaml").write_text("- not a mapping\n", encoding="utf-8")
    (in_dir / "README.md").write_text("# not yaml\n", encoding="utf-8")

    app = Typer()
    app.command()(anonymize_command)
    out_dir = tmp_path / "anonymized"
    result = runner.invoke(
        app, [str(in_dir), "--path", str(out_dir)], catch_exceptions=False
    )
    assert result.exit_code == 0

    written = sorted(
        p.relative_to(out_dir).as_posix() for p in out_dir.rglob("*") if p.is_file()
    )
    assert written == [
        "Resource_one.yaml",
        "a/b/access-platform.yaml",
        "filters/activity_filter.yaml",
        "nested/person_two.yml",
    ]
    filter_output = (out_dir / "filters" / "activity_filter.yaml").read_text(
        encoding="utf-8"
    )
    assert YAML(typ="safe").load(filter_output) == {
        "fields": [{"filterRules": [{"rule": "r"}]}]
    }
    assert "comment" not in filter_output
    models: list[tuple[str, type[AnyMappingModel]]] = [
        ("Resource_one.yaml", ResourceMapping),
        ("nested/person_two.yml", PersonMapping),
        ("a/b/access-platform.yaml", AccessPlatformMapping),
    ]
    for relative, model in models:
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
    app = Typer()
    app.command()(anonymize_command)
    args = [str(in_dir)] + (["--path", str(path)] if path else [])
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 2
    output = " ".join(re.sub(r"[│╭╮╰╯─]", " ", result.output).split())
    assert message in output


def test_anonymize_file_into_folder(tmp_path: Path) -> None:
    runner = CliRunner()
    in_file = tmp_path / "Person_x.yaml"
    _generate_mapping(runner, "Person", in_file)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    app = Typer()
    app.command()(anonymize_command)
    result = runner.invoke(
        app, [str(in_file), "--path", str(out_dir)], catch_exceptions=False
    )
    assert result.exit_code == 0
    PersonMapping.model_validate(
        YAML(typ="safe").load((out_dir / "Person_x.yaml").read_text(encoding="utf-8"))
    )
