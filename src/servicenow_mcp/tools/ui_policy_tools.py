"""
UI Policy tools for the ServiceNow MCP server.
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class CreateUiPolicyParams(BaseModel):
    """Parameters for creating a UI Policy."""

    table: str = Field(..., description="Table name, e.g., sc_cat_item")
    short_description: str = Field(..., description="Short description of the UI policy")
    active: bool = Field(True, description="Whether the policy is active")
    order: int = Field(100, description="Execution order")
    conditions: Optional[str] = Field(None, description="Encoded query for when the policy applies")


class CreateUiPolicyActionParams(BaseModel):
    """Parameters for creating a UI Policy action."""

    ui_policy_id: str = Field(..., description="Sys_id of the UI Policy")
    field: str = Field(..., description="Field name the action applies to")
    mandatory: Optional[bool] = Field(None, description="Set field mandatory")
    visible: Optional[bool] = Field(None, description="Set field visible")
    read_only: Optional[bool] = Field(None, description="Set field read-only")


def create_ui_policy(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateUiPolicyParams,
) -> Dict[str, Any]:
    """Create a UI Policy (sys_ui_policy)."""

    url = f"{config.instance_url}/api/now/table/sys_ui_policy"
    data = {
        "table": params.table,
        "short_description": params.short_description,
        "active": str(params.active).lower(),
        "order": params.order,
    }
    if params.conditions:
        data["conditions"] = params.conditions

    try:
        response = requests.post(
            url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        return {
            "success": True,
            "message": "UI policy created successfully",
            "result": response.json().get("result", {}),
        }
    except requests.RequestException as e:
        logger.error(f"Failed to create UI policy: {e}")
        return {
            "success": False,
            "message": f"Failed to create UI policy: {str(e)}",
        }


def create_ui_policy_action(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateUiPolicyActionParams,
) -> Dict[str, Any]:
    """Create a UI Policy action (sys_ui_policy_action)."""

    url = f"{config.instance_url}/api/now/table/sys_ui_policy_action"
    data = {
        "ui_policy": params.ui_policy_id,
        "field": params.field,
    }
    if params.mandatory is not None:
        data["mandatory"] = str(params.mandatory).lower()
    if params.visible is not None:
        data["visible"] = str(params.visible).lower()
    if params.read_only is not None:
        data["readonly"] = str(params.read_only).lower()

    try:
        response = requests.post(
            url,
            json=data,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        return {
            "success": True,
            "message": "UI policy action created successfully",
            "result": response.json().get("result", {}),
        }
    except requests.RequestException as e:
        logger.error(f"Failed to create UI policy action: {e}")
        return {
            "success": False,
            "message": f"Failed to create UI policy action: {str(e)}",
        }
