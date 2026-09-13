"""Application Configuration Module using Pydantic Settings."""

from typing import Literal, Self

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Type-safe application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General Application Settings
    APP_NAME: str = Field(default="Car-Export-CRM", description="Application Name")
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = Field(
        default="development", description="Deployment Environment"
    )
    LOG_LEVEL: str = Field(default="INFO", description="Logging Threshold Level")
    DEBUG: bool = Field(default=False, description="Debug Mode Status")

    # Database Configuration (PostgreSQL + asyncpg)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://car_export_app:local_dev_password@localhost:5432/car_export_crm",
        description="Async PostgreSQL Connection URI for application backend",
    )
    DATABASE_MIGRATOR_URL: str = Field(
        default="postgresql+asyncpg://car_export_migrator:local_migrator_password@localhost:5432/car_export_crm",
        description="Async PostgreSQL Migration Connection URI for DDL execution",
    )
    DATABASE_POOL_SIZE: int = Field(default=5, ge=1, le=50, description="SQLAlchemy Pool Size")
    DATABASE_MAX_OVERFLOW: int = Field(
        default=10, ge=0, le=100, description="SQLAlchemy Max Overflow"
    )

    # Redis Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0", description="Redis Connection URI")

    # Security & Token Authentication
    JWT_SECRET: str = Field(
        default="dev_jwt_secret_key_change_me_in_production_min_32_bytes_long",
        validation_alias=AliasChoices("JWT_SECRET", "JWT_SECRET_KEY"),
        description="Secret key used for signing JWT tokens",
    )
    JWT_ALGORITHM: str = Field(default="HS256", description="JWT Signing Algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=60, ge=5, description="JWT Token Validity Expiration in Minutes"
    )

    # External Provider Configuration Placeholders
    META_WEBHOOK_APP_SECRET: str = Field(
        default="dev_meta_app_secret_placeholder",
        description="Meta WhatsApp Webhook HMAC App Secret",
    )
    META_WEBHOOK_VERIFY_TOKEN: str = Field(
        default="dev_meta_verify_token_placeholder",
        description="Meta WhatsApp Webhook Verification Challenge Token",
    )

    # AI / LLM Configuration
    LLM_PROVIDER: str = Field(default="openai", description="Default LLM Provider Vendor")
    LLM_DEFAULT_MODEL: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("LLM_DEFAULT_MODEL", "OPENAI_MODEL"),
        description="Default LLM model name",
    )
    LLM_PROVIDER_API_KEY: str = Field(
        default="dev_llm_key_placeholder",
        validation_alias=AliasChoices("LLM_PROVIDER_API_KEY", "OPENAI_API_KEY"),
        description="LLM Vendor Provider API Key",
    )
    EMBEDDING_PROVIDER_API_KEY: str = Field(
        default="dev_embedding_key_placeholder", description="Embedding Provider API Key"
    )

    @property
    def OPENAI_MODEL(self) -> str:
        """Alias for LLM_DEFAULT_MODEL for OpenAI adapter compatibility."""
        return self.LLM_DEFAULT_MODEL

    @property
    def OPENAI_API_KEY(self) -> str:
        """Alias for LLM_PROVIDER_API_KEY for OpenAI adapter compatibility."""
        return self.LLM_PROVIDER_API_KEY

    # Object Storage Configuration (S3)
    OBJECT_STORAGE_BUCKET: str = Field(
        default="car-export-crm-dev-storage",
        validation_alias=AliasChoices("OBJECT_STORAGE_BUCKET", "S3_BUCKET_NAME"),
        description="Private S3 Object Storage Bucket",
    )
    S3_ENDPOINT_URL: str | None = Field(
        default=None, description="Optional custom S3 / MinIO endpoint URL"
    )
    S3_ACCESS_KEY_ID: str = Field(
        default="dev_s3_key_id_placeholder",
        validation_alias=AliasChoices("S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"),
        description="S3 Access Key ID",
    )
    S3_SECRET_ACCESS_KEY: str = Field(
        default="dev_s3_secret_access_key_placeholder",
        validation_alias=AliasChoices("S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"),
        description="S3 Secret Access Key",
    )
    DEV_AUTO_PASS_FILE_SCANS: bool = Field(
        default=False,
        description=(
            "Development-only flag to auto-pass document security scans during upload completion. "
            "MUST be False in production/staging."
        ),
    )

    @property
    def S3_BUCKET_NAME(self) -> str:
        """Alias for OBJECT_STORAGE_BUCKET for compatibility."""
        return self.OBJECT_STORAGE_BUCKET

    @property
    def is_production(self) -> bool:
        """Check if current environment is production."""
        return self.ENVIRONMENT == "production"

    @property
    def is_staging(self) -> bool:
        """Check if current environment is staging."""
        return self.ENVIRONMENT == "staging"

    @property
    def is_development(self) -> bool:
        """Check if current environment is development."""
        return self.ENVIRONMENT == "development"

    @property
    def is_test(self) -> bool:
        """Check if current environment is test."""
        return self.ENVIRONMENT == "test"

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level string."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{v}'")
        return upper_v

    @field_validator("JWT_SECRET")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Ensure JWT secret meets minimum length requirements."""
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters long for security.")
        return v

    @field_validator("DATABASE_URL", "DATABASE_MIGRATOR_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database connection URIs are valid PostgreSQL connection strings."""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError(
                "Database URL must start with 'postgresql://' or 'postgresql+asyncpg://'"
            )
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Ensure REDIS_URL is a valid Redis connection URI."""
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must start with 'redis://' or 'rediss://'")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Self:
        """Prevent default development placeholder secrets in production or staging environments."""
        if self.ENVIRONMENT in ("production", "staging"):
            if self.DEV_AUTO_PASS_FILE_SCANS:
                msg = (
                    "DEV_AUTO_PASS_FILE_SCANS is strictly forbidden in "
                    f"{self.ENVIRONMENT} environment."
                )
                raise ValueError(msg)
            if "dev_" in self.JWT_SECRET:
                msg = f"Insecure default JWT_SECRET is forbidden in {self.ENVIRONMENT} environment."
                raise ValueError(msg)
            if "dev_" in self.META_WEBHOOK_APP_SECRET:
                msg = (
                    "Insecure default META_WEBHOOK_APP_SECRET is forbidden in "
                    f"{self.ENVIRONMENT} environment."
                )
                raise ValueError(msg)
            if "dev_" in self.LLM_PROVIDER_API_KEY:
                msg = (
                    "Insecure default LLM_PROVIDER_API_KEY is forbidden in "
                    f"{self.ENVIRONMENT} environment."
                )
                raise ValueError(msg)
            if "minioadmin" in self.S3_ACCESS_KEY_ID or "dev_" in self.S3_ACCESS_KEY_ID:
                msg = (
                    "Insecure default S3_ACCESS_KEY_ID is forbidden in "
                    f"{self.ENVIRONMENT} environment."
                )
                raise ValueError(msg)
            if "minioadmin" in self.S3_SECRET_ACCESS_KEY or "dev_" in self.S3_SECRET_ACCESS_KEY:
                msg = (
                    "Insecure default S3_SECRET_ACCESS_KEY is forbidden in "
                    f"{self.ENVIRONMENT} environment."
                )
                raise ValueError(msg)
        if self.LLM_PROVIDER.lower() == "openai" and self.ENVIRONMENT in ("production", "staging"):
            if (
                not self.OPENAI_API_KEY
                or "dev_" in self.OPENAI_API_KEY
                or not self.OPENAI_API_KEY.strip()
            ):
                msg = (
                    "LLM_PROVIDER is set to 'openai' but OPENAI_API_KEY is missing or invalid in "
                    f"{self.ENVIRONMENT} environment."
                )
                raise ValueError(msg)
        return self


def get_settings() -> Settings:
    """Return an initialized application settings instance."""
    return Settings()


# Singleton instance for easy import across modules
settings = get_settings()
