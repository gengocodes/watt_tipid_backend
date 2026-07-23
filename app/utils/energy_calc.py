"""
Energy calculations utility module
"""

import math
from typing import List, Dict, Any
from app.schemas.energy import ApplianceResponse

# The exponential decay constant used for mapping total monthly kWh to a 0-100 score.
# This value was derived to match the figma mockup where a monthly consumption of
# 517 kWh yields a score of exactly 45.
#
# Derivation:
#   Score(x) = 100 * exp(-k * x)
#   45 = 100 * exp(-k * 517)
#   0.45 = exp(-k * 517)
#   ln(0.45) = -k * 517
#   k = -ln(0.45) / 517
#   k ≈ 0.798507 / 517
#   k ≈ 0.0015445 (rounded to 0.00154)
# TODO: move to config.py
SCORE_DECAY_RATE = 0.00154


def calculate_appliance_kwh(wattage_watts: float, daily_usage_hours: float) -> float:
    """
    Calculate the monthly kWh of an appliance with full precision.
    Formula: (wattage_watts * daily_usage_hours * 30) / 1000
    """
    return (wattage_watts * daily_usage_hours * 30.0) / 1000.0


def calculate_saving_score(total_kwh: float) -> float:
    """
    Calculate the energy saving score (0-100) using exponential decay.
    Formula: max(5.0, min(100.0, 100.0 * exp(-SCORE_DECAY_RATE * total_kwh)))
    """
    if total_kwh <= 0:
        return 100.0
    val = 100.0 * math.exp(-SCORE_DECAY_RATE * total_kwh)
    return max(5.0, min(100.0, val))


def map_score_status(score: float) -> str:
    """
    Maps energy saving score to descriptive status tags
    """
    if score >= 80.0:
        return "Excellent"
    if score >= 65.0:
        return "Good"
    if score >= 50.0:
        return "Fair"
    return "Needs Work"


def calculate_category_shares(
    appliances: List[ApplianceResponse],
) -> List[Dict[str, Any]]:
    """
    Calculate the energy share of each appliance category.
    Returns list of dicts with category, kwh, and percentage share.
    """
    shares: Dict[str, float] = {}
    total_kwh = 0.0

    for app in appliances:
        wattage = app.wattage_watts
        usage = app.daily_usage_hours
        kwh = calculate_appliance_kwh(wattage, usage)
        category = app.category

        shares[category] = shares.get(category, 0.0) + kwh
        total_kwh += kwh

    result = []
    for cat, kwh in shares.items():
        percentage = (kwh / total_kwh * 100.0) if total_kwh > 0 else 0.0
        result.append(
            {
                "category": cat,
                "kwh": round(kwh, 2),
                "percentage": round(percentage, 1),
            }
        )

    # Sort by kwh usage descending
    result.sort(key=lambda x: x["kwh"], reverse=True)
    return result
