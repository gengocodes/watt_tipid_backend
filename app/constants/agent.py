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
    "add_user_appliance": {
        "id": "act-add-appliance",
        "started": "Adding an appliance",
        "completed": "Added an appliance",
    },
    "update_user_appliance": {
        "id": "act-update-appliance",
        "started": "Updating an appliance",
        "completed": "Updated an appliance",
    },
    "delete_user_appliance": {
        "id": "act-delete-appliance",
        "started": "Deleting an appliance",
        "completed": "Deleted an appliance",
    },
}
