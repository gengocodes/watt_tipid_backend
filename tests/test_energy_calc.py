"""
Tests for app.utils.energy_calc
"""

from datetime import datetime, timezone
from app.utils.energy_calc import (
    calculate_appliance_kwh,
    calculate_saving_score,
    map_score_status,
    calculate_category_shares,
)
from app.schemas.energy import ApplianceResponse


def test_calculate_appliance_kwh():
    """Verify math precision of monthly kWh calculations"""
    # 1500W AC for 8 hours/day should be 360 kWh/month
    assert calculate_appliance_kwh(1500, 8) == 360.0

    # 150W fridge for 24 hours/day should be 108 kWh/month
    assert calculate_appliance_kwh(150, 24) == 108.0

    # 60W fan for 10 hours/day should be 18 kWh/month
    assert calculate_appliance_kwh(60, 10) == 18.0

    # 15W smartphone charger for 8 hours/day should be 3.6 kWh/month (precision)
    assert calculate_appliance_kwh(15, 8) == 3.6


def test_calculate_saving_score():
    """Verify exponential decay scores on various consumption profiles"""
    # 0 kWh should yield 100
    assert calculate_saving_score(0) == 100.0
    assert calculate_saving_score(-10) == 100.0

    # 517 kWh should yield approx 45
    score_517 = calculate_saving_score(517)
    assert 44.5 <= score_517 <= 45.5

    # Very high consumption should clamp to 5.0
    assert calculate_saving_score(5000) == 5.0


def test_map_score_status():
    """Verify score status mappings"""
    assert map_score_status(85) == "Excellent"
    assert map_score_status(70) == "Good"
    assert map_score_status(55) == "Fair"
    assert map_score_status(45) == "Needs Work"
    assert map_score_status(5) == "Needs Work"


def test_calculate_category_shares():
    """Verify aggregation by category and share percentages"""
    now = datetime.now(timezone.utc)
    appliances = [
        ApplianceResponse(
            id="app-1",
            user_id="user-1",
            name="Aircon",
            category="Cooling",
            wattage_watts=1500.0,
            daily_usage_hours=8.0,
            icon="snowflake",
            is_active=True,
            monthly_kwh=360.0,
            created_at=now,
            updated_at=now,
        ),
        ApplianceResponse(
            id="app-2",
            user_id="user-1",
            name="Fan",
            category="Cooling",
            wattage_watts=60.0,
            daily_usage_hours=10.0,
            icon="wind",
            is_active=True,
            monthly_kwh=18.0,
            created_at=now,
            updated_at=now,
        ),
        ApplianceResponse(
            id="app-3",
            user_id="user-1",
            name="Fridge",
            category="Kitchen",
            wattage_watts=150.0,
            daily_usage_hours=24.0,
            icon="refrigerator",
            is_active=True,
            monthly_kwh=108.0,
            created_at=now,
            updated_at=now,
        ),
    ]
    # Total kWh = 486.0
    # Cooling: 378.0 kWh -> 378/486 = 77.777% -> 77.8%
    # Kitchen: 108.0 kWh -> 108/486 = 22.222% -> 22.2%

    shares = calculate_category_shares(appliances)
    assert len(shares) == 2
    assert shares[0]["category"] == "Cooling"
    assert shares[0]["kwh"] == 378.0
    assert 77.7 <= shares[0]["percentage"] <= 77.9

    assert shares[1]["category"] == "Kitchen"
    assert shares[1]["kwh"] == 108.0
    assert 22.1 <= shares[1]["percentage"] <= 22.3
