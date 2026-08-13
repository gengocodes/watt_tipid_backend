"""
Unit tests for SavingTipRepository and SavingTipService following AGENTS.md.
"""

# pylint: disable=wrong-import-position

from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock
import pytest

import app.database.redis

if not isinstance(app.database.redis.redis_client, AsyncMock):
    app.database.redis.redis_client = AsyncMock()
app.database.redis.redis_client.incr.return_value = 1
app.database.redis.redis_client.expire.return_value = True

from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.database.models import (
    ApplianceInDB,
    SavingTipInDB,
    UserInDB,
    UserSettings,
    TipType,
    TipStatus,
    PriorityLevel,
    EffortLevel,
    ApplianceAnalysisStatus,
)
from app.repositories.saving_tip import SavingTipRepository
from app.schemas.saving_tip import (
    AISavingTipItem,
    ApplianceEvaluationItem,
    HouseholdEvaluationResult,
    SavingTipsSummaryResponse,
)
from app.services.saving_tip_service import SavingTipService
from app.utils.household_snapshot import generate_household_snapshot_version
from app.main import app
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_saving_tip_service


@pytest.fixture
def mock_collection():
    """Fixture for a mock MongoDB collection."""
    return MagicMock()


@pytest.fixture
def saving_tip_repo(mock_collection):
    """Fixture for SavingTipRepository using a mock collection."""
    return SavingTipRepository(mock_collection)


def test_enum_validation():
    """Test that the enums have the expected string values."""
    assert TipType.CALCULATED == "CALCULATED"
    assert TipType.REFERENCE == "REFERENCE"
    assert TipStatus.ACTIVE == "active"
    assert PriorityLevel.HIGH == "HIGH"
    assert EffortLevel.LOW == "LOW"


def test_repository_to_model(saving_tip_repo):
    """Test that the repository can convert a document to a model."""
    now = datetime.now(timezone.utc)
    doc = {
        "_id": "mongo_id_123",
        "id": "tip-1",
        "user_id": "user-1",
        "appliance_id": "app-1",
        "appliance_name": "Air Conditioner",
        "appliance_category": "Cooling",
        "appliance_wattage_watts": 1200.0,
        "appliance_daily_usage_hours": 8.0,
        "appliance_monthly_kwh": 288.0,
        "title": "Reduce AC usage",
        "description": "Your 1,200W Air Conditioner running 8 hours/day consumes 288 kWh/mo.",
        "priority": "HIGH",
        "effort_level": "LOW",
        "recommended_daily_usage_reduction_hours": 1.0,
        "estimated_monthly_savings": 360.0,
        "tip_type": "CALCULATED",
        "source_url": None,
        "source_name": None,
        "status": "active",
        "generated_at": now,
        "created_at": now,
        "updated_at": now,
    }
    model = saving_tip_repo._to_model(doc)
    assert model is not None
    assert model.id == "tip-1"
    assert model.appliance_name == "Air Conditioner"
    assert model.appliance_wattage_watts == 1200.0
    assert model.priority == PriorityLevel.HIGH
    assert model.estimated_monthly_savings == 360.0


@pytest.mark.anyio
async def test_run_household_analysis_async_success():
    """Test that the service can run a successful household analysis."""
    mock_session_repo = MagicMock()
    mock_tip_repo = MagicMock()
    mock_app_repo = MagicMock()
    mock_user_repo = MagicMock()
    mock_web_search = AsyncMock()
    mock_model = MagicMock()

    now = datetime.now(timezone.utc)
    user = UserInDB(
        id="user-1",
        email="test@example.com",
        password="pass",
        first_name="Test",
        last_name="User",
        barangay_city="Manila",
        settings=UserSettings(electricity_rate_php_kwh=12.0),
        created_at=now,
    )
    mock_user_repo.get_by_id.return_value = user

    target_app = ApplianceInDB(
        id="app-ac",
        user_id="user-1",
        name="Air Conditioner",
        category="Cooling",
        wattage_watts=1500.0,
        daily_usage_hours=8.0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    mock_app_repo.get_active_user_appliances.return_value = [target_app]
    mock_app_repo.get_user_appliances.return_value = [target_app]

    eval_result = HouseholdEvaluationResult(
        evaluations=[
            ApplianceEvaluationItem(
                appliance_id="app-ac",
                analysis_status=ApplianceAnalysisStatus.HAS_RECOMMENDATIONS,
                tips=[
                    AISavingTipItem(
                        title="Optimize AC Operating Hours",
                        description="Your Air Conditioner is rated at 1,500W and "
                        "currently runs 8 hours/day.",
                        tip_type=TipType.CALCULATED,
                        effort_level=EffortLevel.LOW,
                        recommended_daily_usage_reduction_hours=2.0,
                        requires_source=True,
                        source_query="DOE Philippines air conditioner efficiency guide",
                    )
                ],
            )
        ]
    )

    mock_structured_model = AsyncMock()
    mock_structured_model.ainvoke.return_value = eval_result
    mock_model.with_structured_output.return_value = mock_structured_model

    mock_web_search_res = MagicMock()
    mock_web_search_res.success = True
    mock_web_search_res.data.results = [
        MagicMock(title="DOE Philippines AC Guide", url="https://doe.gov.ph/ac-guide")
    ]
    mock_web_search.search.return_value = mock_web_search_res

    service = SavingTipService(
        mock_session_repo,
        mock_tip_repo,
        mock_app_repo,
        mock_user_repo,
        mock_web_search,
        mock_model,
    )

    snapshot_v = generate_household_snapshot_version([target_app])

    await service.run_household_analysis_async("session-1", "user-1", snapshot_v)

    mock_tip_repo.create_tips.assert_called_once()
    tips_created = mock_tip_repo.create_tips.call_args[0][0]
    assert len(tips_created) == 1
    tip = tips_created[0]
    # Savings formula: (1500/1000) * 2.0 * 30 * 12.0 = 1080.0 PHP
    assert tip.estimated_monthly_savings == 1080.0
    assert tip.priority == PriorityLevel.HIGH
    assert tip.source_name == "DOE Philippines AC Guide"
    assert tip.source_url == "https://doe.gov.ph/ac-guide"

    mock_app_repo.bulk_update_appliance_analysis_statuses.assert_called_once_with(
        user_id="user-1",
        evaluated_status_map={"app-ac": ApplianceAnalysisStatus.HAS_RECOMMENDATIONS},
        session_id="session-1",
    )
    mock_session_repo.complete_session.assert_called_once()


@pytest.mark.anyio
async def test_run_household_analysis_async_household_changed():
    """Test that the service can handle a household configuration change."""
    mock_session_repo = MagicMock()
    mock_tip_repo = MagicMock()
    mock_app_repo = MagicMock()
    mock_user_repo = MagicMock()
    mock_web_search = AsyncMock()
    mock_model = MagicMock()

    now = datetime.now(timezone.utc)
    app1 = ApplianceInDB(
        id="app-1",
        user_id="user-1",
        name="AC",
        category="Cooling",
        wattage_watts=1200.0,
        daily_usage_hours=8.0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    app2 = ApplianceInDB(
        id="app-2",
        user_id="user-1",
        name="Fridge",
        category="Refrigeration",
        wattage_watts=200.0,
        daily_usage_hours=24.0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    mock_app_repo.get_active_user_appliances.return_value = [app1]
    mock_app_repo.get_user_appliances.return_value = [app1, app2]

    eval_result = HouseholdEvaluationResult(evaluations=[])
    mock_structured_model = AsyncMock()
    mock_structured_model.ainvoke.return_value = eval_result
    mock_model.with_structured_output.return_value = mock_structured_model

    service = SavingTipService(
        mock_session_repo,
        mock_tip_repo,
        mock_app_repo,
        mock_user_repo,
        mock_web_search,
        mock_model,
    )

    await service.run_household_analysis_async(
        "session-1", "user-1", "old-snapshot-version"
    )

    mock_session_repo.mark_session_outdated.assert_called_once_with(
        "session-1", "user-1", "Household configuration changed during analysis"
    )
    mock_tip_repo.create_tips.assert_not_called()
    mock_session_repo.complete_session.assert_not_called()


def test_router_get_saving_tips_summary():
    """Test that the router can return a summary of saving tips."""
    now = datetime.now(timezone.utc)
    mock_user = UserInDB(
        id="user-1",
        email="test@example.com",
        password="pass",
        first_name="Test",
        last_name="User",
        barangay_city="Manila",
        created_at=now,
    )
    mock_service = MagicMock()
    mock_service.get_user_tips_summary.return_value = SavingTipsSummaryResponse(
        total_potential_monthly_savings=100.0,
        total_yearly_savings=1200.0,
        total_tips_count=1,
        easy_wins_count=1,
        percentage_bill_reduction=10.0,
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_saving_tip_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get("/saving-tips/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["total_potential_monthly_savings"] == 100.0
    mock_service.get_user_tips_summary.assert_called_once_with("user-1")

    app.dependency_overrides.clear()


def test_update_tip_status_prevents_stale_tip_completion():
    """Test that the service prevents the completion of stale stale tips."""
    mock_session_repo = MagicMock()
    mock_tip_repo = MagicMock()
    mock_app_repo = MagicMock()
    mock_user_repo = MagicMock()
    mock_web_search = AsyncMock()
    mock_model = MagicMock()

    now = datetime.now(timezone.utc)
    stale_tip = SavingTipInDB(
        id="tip-stale",
        user_id="user-1",
        session_id="session-1",
        appliance_id="app-deleted",
        appliance_name="Deleted AC",
        appliance_category="Cooling",
        appliance_wattage_watts=1500.0,
        appliance_daily_usage_hours=8.0,
        appliance_monthly_kwh=360.0,
        title="AC tip",
        description="AC tip desc",
        priority=PriorityLevel.HIGH,
        effort_level=EffortLevel.LOW,
        tip_type=TipType.CALCULATED,
        status=TipStatus.STALE,
        generated_at=now,
        created_at=now,
        updated_at=now,
    )
    mock_tip_repo.get_by_id_and_user.return_value = stale_tip

    service = SavingTipService(
        mock_session_repo,
        mock_tip_repo,
        mock_app_repo,
        mock_user_repo,
        mock_web_search,
        mock_model,
    )
    with pytest.raises(HTTPException) as e:
        service.update_tip_status("user-1", "tip-stale", "completed")

    assert e.value.status_code == 400
    assert "cannot be marked as completed" in e.value.detail
