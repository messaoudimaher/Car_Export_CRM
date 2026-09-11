# Car-Export-CRM Backend Engine

FastAPI & Async SQLAlchemy 2.0 Backend for Car-Export-CRM.

## Quick Start (with `uv`)

```bash
# Create virtual environment & install dependencies
uv venv
uv pip install -e .[dev]

# Run tests
uv run pytest

# Run type checker & linter
uv run mypy .
uv run ruff check .
uv run ruff format --check .

# Start development server
uv run uvicorn app.main:app --reload
```
