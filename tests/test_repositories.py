"""
Unit tests for repositories
"""

from unittest.mock import MagicMock
from datetime import datetime, timezone
from app.repositories.user import UserRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.appliance import ApplianceRepository
from app.repositories.monthly_energy import MonthlyEnergyRepository
from app.schemas.energy import ApplianceUpdate


def test_user_repository_get_by_email():
    """Verify UserRepository correctly maps and strips _id"""
    mock_coll = MagicMock()
    mock_coll.find_one.return_value = {
        "_id": "object-id",
        "id": "user-123",
        "email": "test@watttipid.ph",
        "password": "hashedpassword",
        "first_name": "Maria",
        "last_name": "Santos",
        "is_active": True,
        "barangay_city": "Cebu City",
        "settings": {"electricity_rate_php_kwh": 12.50},
    }

    repo = UserRepository(mock_coll)
    user = repo.get_by_email("test@watttipid.ph")

    assert user is not None
    assert user.id == "user-123"
    assert user.email == "test@watttipid.ph"
    assert user.settings.electricity_rate_php_kwh == 12.50  # pylint: disable=no-member
    mock_coll.find_one.assert_called_once_with({"email": "test@watttipid.ph"})


def test_refresh_token_repository_get_by_hash():
    """Verify RefreshTokenRepository fetches and maps refresh tokens"""
    mock_coll = MagicMock()
    mock_coll.find_one.return_value = {
        "_id": "object-id",
        "id": "token-123",
        "user_id": "user-123",
        "token_hash": "tokenhash",
        "expires_at": datetime.now(timezone.utc),
        "revoked": False,
        "created_at": datetime.now(timezone.utc),
    }

    repo = RefreshTokenRepository(mock_coll)
    token = repo.get_by_hash("tokenhash")

    assert token is not None
    assert token.id == "token-123"
    assert token.revoked is False
    mock_coll.find_one.assert_called_once_with({"token_hash": "tokenhash"})


def test_appliance_repository_get_user_appliances():
    """Verify ApplianceRepository converts multiple cursor documents to list of models"""
    mock_coll = MagicMock()
    mock_coll.find.return_value = [
        {
            "_id": "object-id-1",
            "id": "app-1",
            "user_id": "user-123",
            "name": "Fan",
            "category": "Cooling",
            "wattage_watts": 50.0,
            "daily_usage_hours": 5.0,
            "icon": "wind",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    ]

    repo = ApplianceRepository(mock_coll)
    appliances = repo.get_user_appliances("user-123")

    assert len(appliances) == 1
    assert appliances[0].id == "app-1"
    assert appliances[0].name == "Fan"
    mock_coll.find.assert_called_once_with({"user_id": "user-123"})


def test_appliance_repository_update_appliance():
    """Verify ApplianceRepository builds correct update payloads"""
    mock_coll = MagicMock()
    mock_coll.update_one.return_value = MagicMock(modified_count=1)

    repo = ApplianceRepository(mock_coll)
    update_data = ApplianceUpdate(name="New Fan Name", wattage_watts=60.0)

    success = repo.update_appliance("app-1", "user-123", update_data)

    assert success is True
    # Verify update_one was called with user_id context and the updated fields
    mock_coll.update_one.assert_called_once()
    args, _ = mock_coll.update_one.call_args
    assert args[0] == {"id": "app-1", "user_id": "user-123"}
    assert "name" in args[1]["$set"]
    assert "wattage_watts" in args[1]["$set"]
    assert args[1]["$set"]["name"] == "New Fan Name"
    assert args[1]["$set"]["wattage_watts"] == 60.0


def test_monthly_energy_repository_get_user_trends():
    """Verify MonthlyEnergyRepository queries and sorts historical snapshots"""
    mock_coll = MagicMock()
    mock_coll.find.return_value.sort.return_value = [
        {
            "_id": "object-id",
            "user_id": "user-123",
            "month": "2026-05",
            "kwh": 100.0,
            "cost_php": 1000.0,
        }
    ]

    repo = MonthlyEnergyRepository(mock_coll)
    trends = repo.get_user_trends("user-123")

    assert len(trends) == 1
    assert trends[0].month == "2026-05"
    mock_coll.find.assert_called_once_with({"user_id": "user-123"})
    mock_coll.find.return_value.sort.assert_called_once_with("month", 1)
