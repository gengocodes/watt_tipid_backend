"""
Dashboard service layer
"""

from datetime import datetime, timezone
from fastapi import HTTPException, status
from app.repositories.appliance import ApplianceRepository
from app.repositories.monthly_energy import MonthlyEnergyRepository
from app.repositories.user import UserRepository
from app.schemas.energy import (
    EnergySummaryResponse,
    CategoryShare,
    MonthlyTrendItem,
    MonthlyTrendCreate,
    ApplianceResponse,
)
from app.utils.energy_calc import (
    calculate_appliance_kwh,
    calculate_saving_score,
    map_score_status,
    calculate_category_shares,
)


class DashboardService:
    """Orchestrates query and aggregation logic for user energy summaries"""

    def __init__(
        self,
        appliance_repo: ApplianceRepository,
        monthly_energy_repo: MonthlyEnergyRepository,
        user_repo: UserRepository,
    ):
        self.appliance_repo = appliance_repo
        self.monthly_energy_repo = monthly_energy_repo
        self.user_repo = user_repo

    def get_dashboard_summary(self, user_id: str) -> EnergySummaryResponse:
        """
        Calculate active projections and retrieve historical snapshot trends.
        Strictly read-only and idempotent.
        """
        # 1. Fetch user's settings (for electricity rate)
        user_db = self.user_repo.get_by_id(user_id)
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found",
            )
        rate = user_db.settings.electricity_rate_php_kwh

        # 2. Fetch active appliances
        active_appliances = self.appliance_repo.get_active_user_appliances(user_id)
        appliances = [
            ApplianceResponse(
                id=app.id,
                user_id=app.user_id,
                name=app.name,
                category=app.category,
                wattage_watts=app.wattage_watts,
                daily_usage_hours=app.daily_usage_hours,
                icon=app.icon,
                is_active=app.is_active,
                monthly_kwh=calculate_appliance_kwh(
                    app.wattage_watts, app.daily_usage_hours
                ),
                created_at=app.created_at,
                updated_at=app.updated_at,
            )
            for app in active_appliances
        ]

        # 3. Calculate projections
        total_kwh = sum(app.monthly_kwh for app in appliances)

        estimated_cost = total_kwh * rate
        saving_score = calculate_saving_score(total_kwh)
        status_tag = map_score_status(saving_score)

        # 4. Category breakdown
        raw_shares = calculate_category_shares(appliances)
        category_shares = [
            CategoryShare(
                category=s["category"], kwh=s["kwh"], percentage=s["percentage"]
            )
            for s in raw_shares
        ]

        # 5. Fetch historical trend logs from monthly_energy
        trends = self.monthly_energy_repo.get_user_trends(user_id)
        monthly_trend = [
            MonthlyTrendItem(month=t.month, kwh=t.kwh, cost=t.cost_php) for t in trends
        ]

        # Automatically include current month's calculated projection if not explicitly logged
        current_month_str = datetime.now(timezone.utc).strftime("%Y-%m")
        if not any(t.month == current_month_str for t in monthly_trend):
            monthly_trend.append(
                MonthlyTrendItem(
                    month=current_month_str,
                    kwh=round(total_kwh, 2),
                    cost=round(estimated_cost, 2),
                )
            )

        monthly_trend.sort(key=lambda item: item.month)

        # 6. Apply rounding ONLY immediately before return
        return EnergySummaryResponse(
            estimated_monthly_cost=round(estimated_cost, 2),
            total_monthly_kwh=round(total_kwh, 2),
            appliance_count=len(appliances),
            electricity_rate_php_kwh=round(rate, 2),
            energy_saving_score=int(round(saving_score)),
            score_status=status_tag,
            category_shares=category_shares,
            monthly_trend=monthly_trend,
        )

    def log_monthly_trend(
        self, user_id: str, data: MonthlyTrendCreate
    ) -> MonthlyTrendItem:
        """Log or update a historical monthly energy record for the user"""
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if data.month > current_month:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot log monthly energy data for future months",
            )

        user_db = self.user_repo.get_by_id(user_id)
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found",
            )

        rate = user_db.settings.electricity_rate_php_kwh
        resolved_cost = (
            data.cost_php if data.cost_php is not None else (data.kwh * rate)
        )

        record = self.monthly_energy_repo.upsert_trend(
            user_id=user_id,
            month=data.month,
            kwh=data.kwh,
            cost_php=resolved_cost,
            rate_php_kwh=rate,
        )

        return MonthlyTrendItem(
            month=record.month, kwh=record.kwh, cost=record.cost_php
        )

    def delete_monthly_trend(self, user_id: str, month: str) -> bool:
        """Delete a monthly energy trend record for the user"""
        deleted = self.monthly_energy_repo.delete_trend(user_id, month)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Monthly energy record for {month} not found",
            )
        return True
