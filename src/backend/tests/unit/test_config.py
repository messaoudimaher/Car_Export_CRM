"""Unit tests for Application Settings & Configuration Validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_default_settings_initialization() -> None:
    """Verify default settings load with expected attributes in development mode."""
    settings = get_settings()
    assert settings.APP_NAME == "Car-Export-CRM"
    assert settings.ENVIRONMENT in {"development", "staging", "production", "test"}
    assert settings.DATABASE_POOL_SIZE == 5
    assert len(settings.JWT_SECRET) >= 32
    assert settings.is_development is True or settings.ENVIRONMENT == "development"


def test_environment_helper_properties() -> None:
    """Verify environment boolean helper flags."""
    dev_settings = Settings(ENVIRONMENT="development")
    assert dev_settings.is_development is True
    assert dev_settings.is_production is False
    assert dev_settings.is_staging is False
    assert dev_settings.is_test is False

    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET="prod_super_secure_jwt_secret_key_1234567890",  # noqa: S106
        META_WEBHOOK_APP_SECRET="prod_meta_secret_99999",  # noqa: S106
        LLM_PROVIDER_API_KEY="prod_llm_key_88888",  # noqa: S106
    )
    assert prod_settings.is_production is True
    assert prod_settings.is_development is False

    test_settings = Settings(ENVIRONMENT="test")
    assert test_settings.is_test is True


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


def test_invalid_database_url_validation() -> None:
    """Verify invalid database URL format raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL="mysql://user:pass@localhost:3306/db")
    assert "Database URL must start with" in str(exc_info.value)


def test_invalid_database_migrator_url_validation() -> None:
    """Verify invalid database migrator URL format raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_MIGRATOR_URL="sqlite:///test.db")
    assert "Database URL must start with" in str(exc_info.value)


def test_database_migrator_url_default() -> None:
    """Verify DATABASE_MIGRATOR_URL uses car_export_migrator credentials."""
    settings = Settings()
    assert "car_export_migrator" in settings.DATABASE_MIGRATOR_URL


def test_invalid_redis_url_validation() -> None:
    """Verify invalid redis URL format raises validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(REDIS_URL="memcached://localhost:11211")
    assert "REDIS_URL must start with" in str(exc_info.value)


def test_production_environment_rejects_dev_placeholder_secrets() -> None:
    """Verify production mode rejects default development placeholder secrets."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="dev_jwt_secret_key_change_me_in_production_min_32_bytes_long",  # noqa: S106
        )
    assert "Insecure default JWT_SECRET is forbidden in production environment" in str(
        exc_info.value
    )


def test_production_environment_accepts_valid_secrets() -> None:
    """Verify production mode succeeds when valid non-placeholder secrets are provided."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        JWT_SECRET="prod_super_secure_jwt_secret_key_1234567890",  # noqa: S106
        META_WEBHOOK_APP_SECRET="prod_meta_app_secret_value_12345",  # noqa: S106
        LLM_PROVIDER_API_KEY="prod_llm_provider_api_key_67890",  # noqa: S106
    )
    assert prod_settings.is_production is True


def test_jwt_secret_key_alias_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify JWT_SECRET_KEY environment variable populates canonical JWT_SECRET attribute."""
    monkeypatch.setenv("JWT_SECRET_KEY", "alias_secret_key_environment_variable_32_bytes")
    monkeypatch.delenv("JWT_SECRET", raising=False)

    settings = Settings()
    assert settings.JWT_SECRET == "alias_secret_key_environment_variable_32_bytes"  # noqa: S105
