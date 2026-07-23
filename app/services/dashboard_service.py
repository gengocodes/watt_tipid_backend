"""
Dashboard service layer
"""

from app.database.mongodb import appliances_collection, monthly_energy_collection
from app.schemas.energy import EnergySummaryResponse, CategoryShare, MonthlyTrendItem, ApplianceResponse
from app.services.user_settings_service import UserSettingsService
from app.utils.energy_calc import (
    calculate_appliance_kwh,
    calculate_saving_score,
    map_score_status,
    calculate_category_shares,
)


class DashboardService:
    """Orchestrates query and aggregation logic for user energy summaries"""

    @staticmethod
    def get_dashboard_summary(user_id: str) -> EnergySummaryResponse:
        """
        Calculate active projections and retrieve historical snapshot trends.
        Strictly read-only and idempotent.
        """
        # 1. Fetch user's settings (for electricity rate)
        settings = UserSettingsService.get_settings(user_id)
        rate = settings.electricity_rate_php_kwh

        # 2. Fetch active appliances
        cursor = appliances_collection.find({"user_id": user_id, "is_active": True})
        appliances = [
            ApplianceResponse(
                id=doc["id"],
                user_id=doc["user_id"],
                name=doc["name"],
                category=doc["category"],
                wattage_watts=doc["wattage_watts"],
                daily_usage_hours=doc["daily_usage_hours"],
                icon=doc["icon"],
                is_active=doc.get("is_active", True),
                monthly_kwh=calculate_appliance_kwh(
                    doc.get("wattage_watts", 0.0), doc.get("daily_usage_hours", 0.0)
                ),
                created_at=doc["created_at"],
                updated_at=doc["updated_at"],
            )
            for doc in cursor
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
        trend_cursor = monthly_energy_collection.find({"user_id": user_id}).sort(
            "month", 1
        )
        monthly_trend = [
            MonthlyTrendItem(month=doc["month"], kwh=doc["kwh"], cost=doc["cost_php"])
            for doc in trend_cursor
        ]

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
