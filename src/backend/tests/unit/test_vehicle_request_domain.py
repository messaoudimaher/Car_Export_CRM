"""Unit Test Suite for Vehicle Request Domain Model & Validation Engine (Phase 1)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from app.models.vehicle_request import VehicleRequest, VehicleRequestStatus, check_fcr_compliance
from app.schemas.vehicle_request_state import (
    VehicleRequestCriteria,
    validate_vehicle_criteria,
)


def test_fcr_5_year_age_compliance_rule():
    """Verify Tunisia FCR 5-year maximum vehicle age rule (BR-004)."""
    current_year = 2026
    # 2026 - 5 = 2021 (valid min year)
    assert check_fcr_compliance(min_year=2026, reference_year=current_year) is True
    assert check_fcr_compliance(min_year=2023, reference_year=current_year) is True
    assert check_fcr_compliance(min_year=2021, reference_year=current_year) is True
    # 2020 is 6 years old -> non-compliant
    assert check_fcr_compliance(min_year=2020, reference_year=current_year) is False
    assert check_fcr_compliance(max_year=2019, reference_year=current_year) is False


def test_vehicle_request_initial_incomplete_state():
    """Verify newly created VehicleRequest defaults to Pending and is NOT qualified."""
    tenant_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    vreq = VehicleRequest(
        tenant_id=tenant_id,
        customer_id=cust_id,
        make="Volkswagen",
        model="Golf 8",
        min_year=2022,
        fuel_type="Diesel",
        budget_eur=Decimal("24000.00"),
    )

    assert vreq.status == "Pending"
    assert vreq.confirmed_at is None
    assert vreq.is_qualified is False
    assert vreq.fcr_compatible is True


def test_vehicle_request_mark_as_qualified():
    """Verify marking VehicleRequest as qualified sets status and timestamp."""
    tenant_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    vreq = VehicleRequest(
        tenant_id=tenant_id,
        customer_id=cust_id,
        make="BMW",
        model="X5",
        min_year=2023,
        fuel_type="Diesel",
        transmission="Automatic",
        budget_eur=Decimal("45000.00"),
        color="Black",
        additional_requirements="M-Sport Package, Panoramic Sunroof",
    )

    assert vreq.is_qualified is False
    now = datetime.now(UTC)
    vreq.mark_as_qualified(confirmed_at=now)

    assert vreq.status == VehicleRequestStatus.QUALIFIED
    assert vreq.confirmed_at == now
    assert vreq.is_qualified is True
    assert vreq.color == "Black"
    assert "M-Sport" in (vreq.additional_requirements or "")


def test_validate_vehicle_criteria_complete_input():
    """Verify validation engine passes when all required fields are present."""
    raw = {
        "make": "mercedes-benz",
        "model": "C200",
        "year": 2022,
        "fuel_type": "diesel",
        "transmission": "auto",
        "budget_eur": 32000.0,
        "color": "Grey",
    }
    state = validate_vehicle_criteria(raw)

    assert state.is_complete is True
    assert len(state.missing_fields) == 0
    assert state.criteria.make == "Mercedes-Benz"
    assert state.criteria.fuel_type == "Diesel"
    assert state.criteria.transmission == "Automatic"
    assert state.criteria.budget_eur == 32000.0
    assert state.fcr_compliant is True


def test_validate_vehicle_criteria_partial_input():
    """Verify validation engine accurately identifies missing required fields."""
    raw = {
        "make": "Audi",
        "model": "A4",
    }
    state = validate_vehicle_criteria(raw, required_fields=["make", "model", "year", "budget_eur"])

    assert state.is_complete is False
    assert "year" in state.missing_fields
    assert "budget_eur" in state.missing_fields
    assert "make" not in state.missing_fields
    assert "model" not in state.missing_fields


def test_validate_vehicle_criteria_invalid_year_and_budget_sanitization():
    """Verify unrealistic years (<2010 or >2027) and negative budgets are sanitized to None."""
    raw = {
        "make": "Peugeot",
        "model": "208",
        "year": 1995,  # Out of realistic export bounds
        "budget_eur": -5000.0,  # Invalid negative budget
    }
    state = validate_vehicle_criteria(raw)

    assert state.criteria.year is None
    assert state.criteria.budget_eur is None
    assert "year" in state.missing_fields
    assert "budget_eur" in state.missing_fields
