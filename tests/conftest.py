import pytest

from mex.extractors.settings import Settings

pytest_plugins = ("mex.common.testing.plugin",)


@pytest.fixture(autouse=True)
def settings() -> Settings:
    """Load the settings for this pytest session."""
    return Settings.get()
