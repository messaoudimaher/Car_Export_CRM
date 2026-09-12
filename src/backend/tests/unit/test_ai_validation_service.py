"""Unit tests for Layer 2 Pydantic Schema Validation Engine (ADR 0012, BR-010)."""

from enum import StrEnum
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field

from app.adapters.llm_demo import DemoLLMAdapter
from app.core.errors import AISchemaValidationException
from app.ports.llm import LLMCompletionResponse
from app.services.ai_validation_service import AIValidationService, clean_json_payload


class FuelType(StrEnum):
    DIESEL = "Diesel"
    PETROL = "Petrol"
    HYBRID = "Hybrid"
    ELECTRIC = "Electric"


class SampleVehicleRequest(BaseModel):
    make: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    min_year: int = Field(..., ge=2000, le=2030)
    max_year: int = Field(..., ge=2000, le=2030)
    fuel_type: FuelType
    max_budget_eur: float = Field(..., gt=0)


def test_clean_json_payload_utility() -> None:
    assert clean_json_payload("") == ""
    assert clean_json_payload("   ") == ""
    assert clean_json_payload('{"key": "value"}') == '{"key": "value"}'

    markdown_wrapped = '```json\n{"make": "BMW", "model": "Series 3"}\n```'
    assert clean_json_payload(markdown_wrapped) == '{"make": "BMW", "model": "Series 3"}'

    conversational = (
        'Here is the extracted vehicle request:\n{"make": "Audi", "model": "A4"}\nHope this helps!'
    )
    assert clean_json_payload(conversational) == '{"make": "Audi", "model": "A4"}'


@pytest.mark.asyncio
async def test_validate_response_valid_json() -> None:
    service = AIValidationService()
    valid_raw = """
    {
        "make": "Volkswagen",
        "model": "Golf 8",
        "min_year": 2021,
        "max_year": 2023,
        "fuel_type": "Diesel",
        "max_budget_eur": 22000.00
    }
    """
    result = await service.validate_response(valid_raw, SampleVehicleRequest)
    assert isinstance(result, SampleVehicleRequest)
    assert result.make == "Volkswagen"
    assert result.model == "Golf 8"
    assert result.fuel_type == FuelType.DIESEL
    assert result.max_budget_eur == 22000.00


@pytest.mark.asyncio
async def test_validate_response_markdown_codeblock() -> None:
    service = AIValidationService()
    markdown_raw = """```json
    {
        "make": "Mercedes-Benz",
        "model": "C-Class",
        "min_year": 2020,
        "max_year": 2022,
        "fuel_type": "Petrol",
        "max_budget_eur": 35000.00
    }
    ```"""
    result = await service.validate_response(markdown_raw, SampleVehicleRequest)
    assert result.make == "Mercedes-Benz"
    assert result.fuel_type == FuelType.PETROL


@pytest.mark.asyncio
async def test_validate_response_raw_freeform_text() -> None:
    service = AIValidationService()
    freeform_raw = "I think the customer is looking for a nice red car under 20k euros."

    with pytest.raises(AISchemaValidationException) as exc_info:
        await service.validate_response(freeform_raw, SampleVehicleRequest, max_retries=0)

    exc = exc_info.value
    assert exc.attempts == 1
    assert (
        "Raw output contains no valid JSON object structure" in exc.detail or "failed" in exc.detail
    )
    assert exc.raw_output == freeform_raw


@pytest.mark.asyncio
async def test_validate_response_malformed_json_syntax() -> None:
    service = AIValidationService()
    malformed_json = '{"make": "BMW", "model": "X5", "min_year": 2021,}'  # trailing comma

    with pytest.raises(AISchemaValidationException) as exc_info:
        await service.validate_response(malformed_json, SampleVehicleRequest, max_retries=0)

    assert exc_info.value.attempts == 1
    assert "Invalid JSON format" in exc_info.value.detail or "failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_validate_response_missing_required_field() -> None:
    service = AIValidationService()
    missing_field_raw = """
    {
        "make": "Peugeot",
        "min_year": 2019,
        "max_year": 2022,
        "fuel_type": "Diesel",
        "max_budget_eur": 15000.00
    }
    """  # Missing 'model'

    with pytest.raises(AISchemaValidationException) as exc_info:
        await service.validate_response(missing_field_raw, SampleVehicleRequest, max_retries=0)

    exc = exc_info.value
    assert exc.attempts == 1
    assert exc.invalid_params is not None
    assert any(param["name"] == "model" for param in exc.invalid_params)


@pytest.mark.asyncio
async def test_validate_response_wrong_field_types() -> None:
    service = AIValidationService()
    invalid_types_raw = """
    {
        "make": "Renault",
        "model": "Clio",
        "min_year": "invalid_year_string",
        "max_year": 2022,
        "fuel_type": "Diesel",
        "max_budget_eur": -500.00
    }
    """

    with pytest.raises(AISchemaValidationException) as exc_info:
        await service.validate_response(invalid_types_raw, SampleVehicleRequest, max_retries=0)

    exc = exc_info.value
    assert exc.invalid_params is not None
    assert len(exc.invalid_params) >= 1


@pytest.mark.asyncio
async def test_validate_response_invalid_enum_value() -> None:
    service = AIValidationService()
    invalid_enum_raw = """
    {
        "make": "Tesla",
        "model": "Model 3",
        "min_year": 2021,
        "max_year": 2023,
        "fuel_type": "Nuclear",
        "max_budget_eur": 40000.00
    }
    """

    with pytest.raises(AISchemaValidationException) as exc_info:
        await service.validate_response(invalid_enum_raw, SampleVehicleRequest, max_retries=0)

    exc = exc_info.value
    assert exc.invalid_params is not None
    assert any(param["name"] == "fuel_type" for param in exc.invalid_params)


@pytest.mark.asyncio
async def test_validate_response_retry_success(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_llm = DemoLLMAdapter()
    valid_retry_json = """
    {
        "make": "Toyota",
        "model": "RAV4",
        "min_year": 2021,
        "max_year": 2024,
        "fuel_type": "Hybrid",
        "max_budget_eur": 30000.00
    }
    """
    mock_generate = AsyncMock(
        return_value=LLMCompletionResponse(
            content=valid_retry_json,
            model="demo-llm",
        )
    )
    monkeypatch.setattr(mock_llm, "generate_text", mock_generate)

    service = AIValidationService(llm_provider=mock_llm)
    invalid_first_raw = '{"make": "Toyota"}'  # missing required fields

    result = await service.validate_response(invalid_first_raw, SampleVehicleRequest, max_retries=1)
    assert result.make == "Toyota"
    assert result.model == "RAV4"
    assert result.fuel_type == FuelType.HYBRID
    assert mock_generate.call_count == 1


@pytest.mark.asyncio
async def test_validate_response_retry_persistent_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_llm = DemoLLMAdapter()
    invalid_retry_json = '{"make": "Toyota", "model": "Corolla"}'
    mock_generate = AsyncMock(
        return_value=LLMCompletionResponse(
            content=invalid_retry_json,
            model="demo-llm",
        )
    )
    monkeypatch.setattr(mock_llm, "generate_text", mock_generate)

    service = AIValidationService(llm_provider=mock_llm)
    invalid_first_raw = "Not JSON at all"

    with pytest.raises(AISchemaValidationException) as exc_info:
        await service.validate_response(invalid_first_raw, SampleVehicleRequest, max_retries=1)

    exc = exc_info.value
    assert exc.attempts == 2
    assert exc.raw_output == invalid_retry_json
    assert mock_generate.call_count == 1
