import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from settings import SMTPSettings

PORTS = (465, 587, 1127, 1126, 2525)
MODES = ("tls", "starttls", "none")
LEGACY = (None, True, False)


def make_settings(values, source: str, monkeypatch: pytest.MonkeyPatch) -> SMTPSettings:
    if source == "env":
        for key, value in values.items():
            monkeypatch.setenv(key, str(value).lower() if isinstance(value, bool) else str(value))
        # Pydantic's mypy constructor signature omits BaseSettings' _env_file option.
        return SMTPSettings(_env_file=None)  # type: ignore[call-arg]
    return SMTPSettings(_env_file=None, **values)  # type: ignore[call-arg]


@pytest.mark.parametrize("source", ("init", "env"))
@pytest.mark.parametrize("port", PORTS)
@pytest.mark.parametrize("legacy", LEGACY)
def test_legacy_matrix(port, legacy, source, monkeypatch):
    values = {"SMTP_PORT": port}
    if legacy is not None:
        values["SMTP_USE_TLS"] = legacy
    if legacy is False or (legacy is None and port not in (465, 587)):
        with pytest.raises(ValidationError):
            make_settings(values, source, monkeypatch)
    else:
        config = make_settings(values, source, monkeypatch)
        assert config.effective_tls_mode == ("starttls" if port == 587 else "tls")


def test_default_transport():
    config = SMTPSettings(_env_file=None)
    assert config.smtp_port == 587
    assert config.smtp_use_tls is None
    assert config.smtp_tls_mode is None
    assert config.effective_tls_mode == "starttls"


@pytest.mark.parametrize("source", ("init", "env"))
@pytest.mark.parametrize("port", PORTS)
@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("legacy", LEGACY)
def test_explicit_legacy_matrix(port, mode, legacy, source, monkeypatch):
    values = {"SMTP_PORT": port, "SMTP_TLS_MODE": mode}
    if legacy is not None:
        values["SMTP_USE_TLS"] = legacy
    if legacy is not None and legacy != (mode != "none"):
        with pytest.raises(ValidationError):
            make_settings(values, source, monkeypatch)
    else:
        assert make_settings(values, source, monkeypatch).effective_tls_mode == mode


@pytest.mark.parametrize("source", ("init", "env"))
@pytest.mark.parametrize(
    ("key", "value"),
    [
        *(("SMTP_TLS_MODE", value) for value in ("", " ", "TLS", "auto", "false", " tls", "tls ")),
        *(("SMTP_USE_TLS", value) for value in ("", " ", "invalid", "none", "2")),
    ],
)
def test_invalid_transport_inputs(key, value, source, monkeypatch):
    with pytest.raises(ValidationError):
        make_settings({key: value}, source, monkeypatch)


@pytest.mark.parametrize("value", ("true", "True", "1", "on", "yes", "t", "y"))
def test_legacy_true_parsing(value):
    assert SMTPSettings(SMTP_PORT=1127, SMTP_USE_TLS=value, _env_file=None).effective_tls_mode == "tls"


@pytest.mark.parametrize("value", ("false", "False", "0", "off", "no", "f", "n"))
def test_legacy_false_parsing(value):
    assert SMTPSettings(SMTP_TLS_MODE="none", SMTP_USE_TLS=value, _env_file=None).effective_tls_mode == "none"
    with pytest.raises(ValidationError):
        SMTPSettings(SMTP_USE_TLS=value, _env_file=None)


@pytest.mark.parametrize(
    "transport",
    [
        {"SMTP_TLS_MODE": "tls", "SMTP_USE_TLS": False},
        {"SMTP_TLS_MODE": "SECRET_MODE_MARKER"},
        {"SMTP_USE_TLS": "SECRET_BOOLEAN_MARKER"},
        {"SMTP_PORT": "SECRET_PORT_MARKER"},
    ],
)
def test_safe_configuration_error(transport):
    with pytest.raises(ValidationError) as caught:
        SMTPSettings(
            SMTP_PASSWORD="SECRET_PASSWORD_MARKER",
            SMTP_USER="SECRET_KEY_MARKER",
            _env_file=None,
            **transport,
        )
    message = str(caught.value)
    assert "SMTP_" in message
    assert "SECRET_" not in message


@pytest.mark.parametrize("scenario", ("default", "conflict", "ambiguous", "explicit"))
def test_isolated_settings_sources(scenario):
    # Run before singleton imports; forbid both eager dotenv reads and source calls.
    service = Path(__file__).resolve().parents[2]
    script = """
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
from pydantic import ValidationError
from pydantic_settings import DotEnvSettingsSource, SecretsSettingsSource

service, scenario = Path(sys.argv[1]), sys.argv[2]
def forbidden(*args, **kwargs):
    raise AssertionError("credential source invoked")
with patch("pydantic_settings.sources.providers.dotenv.dotenv_values", forbidden), \\
     patch.object(DotEnvSettingsSource, "__call__", forbidden), \\
     patch.object(SecretsSettingsSource, "__call__", forbidden):
    runpy.run_path(str(service / "tests/conftest.py"))
    assert "SMTP_PASSWORD" not in os.environ
    if scenario == "conflict":
        os.environ.update(SMTP_TLS_MODE="tls", SMTP_USE_TLS="false")
    elif scenario == "ambiguous":
        os.environ.update(SMTP_PORT="1127")
    elif scenario == "explicit":
        os.environ.update(SMTP_PORT="1126", SMTP_TLS_MODE="starttls")
    try:
        import settings
    except ValidationError:
        assert scenario in ("conflict", "ambiguous")
    else:
        assert scenario in ("default", "explicit")
        assert settings.smtp_settings.effective_tls_mode == "starttls"
print("ISOLATED")
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(service), scenario],
        cwd=service,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(service / "src"),
            # Deliberately hostile synthetic parent env must be discarded.
            "SMTP_PASSWORD": "SYNTHETIC_PARENT_MARKER",
            "SMTP_USE_TLS": "invalid",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    # Do not dump subprocess stderr/settings on failure.
    assert result.returncode == 0, "settings isolation subprocess failed"
    assert result.stdout.strip() == "ISOLATED"
    assert not result.stderr


def test_field_names_match_aliases():
    config = SMTPSettings(smtp_port=1126, smtp_tls_mode="starttls", smtp_use_tls=True, _env_file=None)
    assert config.effective_tls_mode == "starttls"
    # Safe serialization only of the resolved mode, never the settings model.
    assert json.dumps(config.effective_tls_mode) == '"starttls"'
