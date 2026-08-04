"""
Constants and configuration for AI Agent
"""
from app.schemas.agent import ToolActivityConfig

TOOL_ACTIVITY_CONFIG: dict[str, ToolActivityConfig] = {
    "get_user_appliances": {
        "id": "act-appliances",
        "started": "Reviewing your appliances",
        "completed": "Reviewed your appliances",
    },
    "get_user_energy_summary": {
        "id": "act-summary",
        "started": "Analyzing your energy usage",
        "completed": "Analyzed your energy usage",
    },
}
