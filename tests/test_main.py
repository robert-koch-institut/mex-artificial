from pytest import LogCaptureFixture
from typer import Typer
from typer.testing import CliRunner

from mex.artificial.main import artificial


def test_main(caplog: LogCaptureFixture) -> None:
    runner = CliRunner()
    app = Typer()
    app.command()(artificial)
    result = runner.invoke(app, ["--count", "30"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "artificial data generation done" in caplog.text
