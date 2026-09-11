"""Unit tests for Application Settings & Configuration Validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_default_settings_initialization() -> None:
    """Verify default settings load with expected attributes."""
    settings = get_settings()
    assert settings.APP_NAME == "Car-Export-CRM"
    assert settings.ENVIRONMENT in {"development", "staging", "production", "test"}
    assert settings.DATABASE_POOL_SIZE == 5
    assert len(settings.JWT_SECRET) >= 32


def test_log_level_validation() -> None:
    """Verify invalid log level raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(LOG_LEVEL="SUPER_VERBOSE")
    assert "LOG_LEVEL must be one of" in str(exc_info.value)


def test_short_jwt_secret_validation() -> None:
    """Verify short JWT secret raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(JWT_SECRET="too_short")  # noqa: S106
    assert "JWT_SECRET must be at least 32 characters long" in str(exc_info.value)
