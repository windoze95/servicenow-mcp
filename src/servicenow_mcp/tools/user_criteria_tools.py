"""
User Criteria tools for the ServiceNow MCP server.
"""

import logging
from typing import Any, Dict, Optional

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class CreateUserCriteriaParams(BaseModel):
    """Parameters for creating user criteria."""

    name: str = Field(..., description="Name of the user criteria")
    active: bool = Field(True, description="Whether the criteria is active")
    description: Optional[str] = Field(None, description="Description")
    role: Optional[str] = Field(None, description="Role sys_id(s) to include")
    group: Optional[str] = Field(None, description="Group sys_id(s) to include")
    user: Optional[str] = Field(None, description="User sys_id(s) to include")


class CreateUserCriteriaConditionParams(BaseModel):
    """Parameters for creating a condition for user criteria."""

    user_criteria_id: str = Field(..., description="Sys_id of the user criteria")
    field: str = Field(..., description="Field name")
    operator: str = Field(..., description="Operator, e.g., =, !=, IN")
    value: str = Field(..., description="Value for the condition")


def create_user_criteria(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateUserCriteriaParams,
) -> Dict[str, Any]:
    """Create user criteria (user_criteria table)."""

    url = f"{config.instance_url}/api/now/table/user_criteria"
    data = {
        "name": params.name,
        "active": str(params.active).lower(),
    }
    if params.description:
        data["description"] = params.description
    if params.role:
        data["roles"] = params.role
    if params.group:
        data["groups"] = params.group
    if params.user:
        data["users"] = params.user

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
            "message": "User criteria created successfully",
            "result": response.json().get("result", {}),
        }
    except requests.RequestException as e:
        logger.error(f"Failed to create user criteria: {e}")
        return {
            "success": False,
            "message": f"Failed to create user criteria: {str(e)}",
        }


def create_user_criteria_condition(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: CreateUserCriteriaConditionParams,
) -> Dict[str, Any]:
    """Create a condition for user criteria (user_criteria_condition)."""

    url = f"{config.instance_url}/api/now/table/user_criteria_condition"
    data = {
        "user_criteria": params.user_criteria_id,
        "field": params.field,
        "operator": params.operator,
        "value": params.value,
    }

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
            "message": "User criteria condition created successfully",
            "result": response.json().get("result", {}),
        }
    except requests.RequestException as e:
        logger.error(f"Failed to create user criteria condition: {e}")
        return {
            "success": False,
            "message": f"Failed to create user criteria condition: {str(e)}",
        }
