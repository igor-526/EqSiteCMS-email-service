"""Disable credential-bearing settings sources before any application imports."""

import os
from unittest.mock import patch

import pytest
from pydantic_settings import BaseSettings, DotEnvSettingsSource, PydanticBaseSettingsSource


def isolated_settings_sources(
    cls: type[BaseSettings],
    settings_cls: type[BaseSettings],
    init_settings: PydanticBaseSettingsSource,
    env_settings: PydanticBaseSettingsSource,
    dotenv_settings: PydanticBaseSettingsSource,
    file_secret_settings: PydanticBaseSettingsSource,
) -> tuple[PydanticBaseSettingsSource, ...]:
    return init_settings, env_settings


# Preserve only process/tool locations, never application configuration.
_environment = patch.dict(
    os.environ,
    {
        **{key: os.environ[key] for key in ("PATH", "HOME", "LANG", "VIRTUAL_ENV") if key in os.environ},
        "ENVIRONMENT": "test",
        "SENTRY_ENABLED": "false",
    },
    clear=True,
)
_sources = pytest.MonkeyPatch()
_environment.start()
# DotEnvSettingsSource eagerly reads files in __init__, before source selection.
_sources.setattr(DotEnvSettingsSource, "_read_env_files", lambda self: {})
_sources.setattr(BaseSettings, "settings_customise_sources", classmethod(isolated_settings_sources))


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    _sources.undo()
    _environment.stop()
