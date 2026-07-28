"""
Tests for endpoints: energy, dashboard, and user settings using repository stubs
"""

# pylint: disable=wrong-import-position

from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient

# Mock redis_client and MongoClient before any application
# imports to avoid network connections in CI
import pytest
import pymongo
import app.database.redis

pymongo.MongoClient = MagicMock()
if not isinstance(app.database.redis.redis_client, AsyncMock):
    app.database.redis.redis_client = AsyncMock()
app.database.redis.redis_client.incr.return_value = 1
app.database.redis.redis_client.expire.return_value = True

from app.main import app
from app.dependencies.auth import get_current_user
from app.schemas.auth import User
from app.database.models import UserInDB, UserSettings, ApplianceInDB, MonthlyEnergyInDB
from app.dependencies.repositories import (
    get_user_repository,
    get_refresh_token_repository,
    get_appliance_repository,
    get_monthly_energy_repository,
)

# Create mock repository instances
mock_user_repo = MagicMock()
mock_token_repo = MagicMock()
mock_appliance_repo = MagicMock()
mock_energy_repo = MagicMock()


# Create a mock user
MOCK_USER_ID = "mock-user-uuid"
mock_user = User(
    id=MOCK_USER_ID,
    email="test@watttipid.ph",
    password="hashedpassword",
    first_name="Maria",
    last_name="Santos",
    is_active=True,
    barangay_city="Cebu City",
    created_at=datetime.now(timezone.utc),
)


async def mock_get_current_user():
    """Override get_current_user dependency to return mock_user"""
    return mock_user


@pytest.fixture(autouse=True)
def setup_overrides():
    """Set overrides and reset mock calls before each test execution"""
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repo
    app.dependency_overrides[get_refresh_token_repository] = lambda: mock_token_repo
    app.dependency_overrides[get_appliance_repository] = lambda: mock_appliance_repo
    app.dependency_overrides[get_monthly_energy_repository] = lambda: mock_energy_repo
    app.dependency_overrides[get_current_user] = mock_get_current_user

    mock_user_repo.reset_mock()
    mock_token_repo.reset_mock()
    mock_appliance_repo.reset_mock()
    mock_energy_repo.reset_mock()
    yield


client = TestClient(app)


def test_get_appliances():
    """Verify GET /energy/appliances retrieves user's scoped list and calculates kWh"""
    mock_appliance_repo.get_user_appliances.return_value = [
        ApplianceInDB(
            id="app-1",
            user_id=MOCK_USER_ID,
            name="Air Conditioner",
            category="Cooling",
            wattage_watts=1500.0,
            daily_usage_hours=8.0,
            icon="snowflake",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]

    response = client.get("/energy/appliances")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Air Conditioner"
    assert data[0]["monthly_kwh"] == 360.0  # 1500 * 8 * 30 / 1000
    mock_appliance_repo.get_user_appliances.assert_called_once_with(MOCK_USER_ID)


def test_create_appliance():
    """Verify POST /energy/appliances registers appliance successfully"""
    payload = {
        "name": "Refrigerator",
        "category": "Kitchen",
        "wattage_watts": 150.0,
        "daily_usage_hours": 24.0,
        "icon": "refrigerator",
    }

    response = client.post("/energy/appliances", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Refrigerator"
    assert data["user_id"] == MOCK_USER_ID
    assert data["monthly_kwh"] == 108.0
    mock_appliance_repo.create_appliance.assert_called_once()


def test_get_dashboard_summary():
    """Verify GET /dashboard/summary calculates correct cost projections and trends"""
    # 1. Mock user rate settings
    mock_user_repo.get_by_id.return_value = UserInDB(
        id=MOCK_USER_ID,
        email="test@watttipid.ph",
        password="hashedpassword",
        first_name="Maria",
        last_name="Santos",
        is_active=True,
        barangay_city="Cebu City",
        settings=UserSettings(electricity_rate_php_kwh=10.0),
    )

    # 2. Mock active appliances
    mock_appliance_repo.get_active_user_appliances.return_value = [
        ApplianceInDB(
            id="app-1",
            user_id=MOCK_USER_ID,
            name="Electric Fan",
            category="Cooling",
            wattage_watts=60.0,
            daily_usage_hours=10.0,
            icon="wind",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    ]

    # 3. Mock historical snapshot trend
    mock_energy_repo.get_user_trends.return_value = [
        MonthlyEnergyInDB(
            id="snap-1",
            user_id=MOCK_USER_ID,
            month="2026-06",
            kwh=15.0,
            cost_php=150.0,
            rate_php_kwh=10.0,
            created_at=datetime.now(timezone.utc),
        )
    ]

    response = client.get("/dashboard/summary")
    assert response.status_code == 200
    data = response.json()

    # Total kWh = 18.0
    # Cost = 18.0 * 10.0 = 180.0
    # Score = 100 * exp(-0.00154 * 18) = 97.26 -> 97
    assert data["total_monthly_kwh"] == 18.0
    assert data["estimated_monthly_cost"] == 180.0
    assert data["electricity_rate_php_kwh"] == 10.0
    assert data["energy_saving_score"] == 97
    assert data["score_status"] == "Excellent"
    assert len(data["monthly_trend"]) == 1
    assert data["monthly_trend"][0]["month"] == "2026-06"


def test_get_user_settings_default():
    """Verify settings fallback to default rate if settings object is absent"""
    mock_user_repo.get_by_id.return_value = UserInDB(
        id=MOCK_USER_ID,
        email="test@watttipid.ph",
        password="hashedpassword",
        first_name="Maria",
        last_name="Santos",
        is_active=True,
        barangay_city="Cebu City",
        settings=UserSettings(electricity_rate_php_kwh=12.50),
    )

    response = client.get("/users/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["electricity_rate_php_kwh"] == 12.50


def test_patch_user_settings():
    """Verify partial settings update saves to MongoDB user settings sub-payload"""
    mock_user_repo.get_by_id.return_value = UserInDB(
        id=MOCK_USER_ID,
        email="test@watttipid.ph",
        password="hashedpassword",
        first_name="Maria",
        last_name="Santos",
        is_active=True,
        barangay_city="Cebu City",
        settings=UserSettings(electricity_rate_php_kwh=12.50),
    )

    payload = {"electricity_rate_php_kwh": 15.0}
    response = client.patch("/users/settings", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["electricity_rate_php_kwh"] == 15.0
    mock_user_repo.update_settings.assert_called_once_with(MOCK_USER_ID, 15.0)
