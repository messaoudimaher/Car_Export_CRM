from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.config import settings


def test_alembic_config_initialization() -> None:
    """Verify alembic.ini config loads script location and target migration URL."""
    alembic_cfg = Config("alembic.ini")
    assert alembic_cfg.get_main_option("script_location") == "alembic"

    url = alembic_cfg.get_main_option("sqlalchemy.url")
    assert url is not None
    assert "car_export_migrator" in url


def test_alembic_target_metadata_binding() -> None:
    """Verify Alembic env.py sets target_metadata to Base.metadata."""
    with open("alembic/env.py", encoding="utf-8") as f:
        content = f.read()
    assert "target_metadata = Base.metadata" in content


def test_alembic_script_directory_structure() -> None:
    """Verify Alembic script directory initializes cleanly without errors."""
    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    assert script is not None
    assert script.dir == "alembic"


def test_migration_environment_settings_override() -> None:
    """Verify Alembic migration environment uses DATABASE_MIGRATOR_URL."""
    assert settings.DATABASE_MIGRATOR_URL is not None
    assert "car_export_migrator" in settings.DATABASE_MIGRATOR_URL
