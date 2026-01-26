"""
System log tools for the ServiceNow MCP server.
"""

import logging
from typing import Any, Dict

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import ServerConfig

logger = logging.getLogger(__name__)


class ListSyslogEntriesParams(BaseModel):
    """Parameters for listing syslog entries."""

    limit: int = Field(20, description="Maximum number of syslog entries to return")
    offset: int = Field(0, description="Offset for pagination")
    query: str = Field("", description="Encoded sysparm_query for filtering logs")


class GetSyslogEntryParams(BaseModel):
    """Parameters for retrieving a specific syslog entry."""

    sys_id: str = Field(..., description="Sys_id of the syslog entry")


def list_syslog_entries(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: ListSyslogEntriesParams,
) -> Dict[str, Any]:
    """List syslog entries from ServiceNow."""

    url = f"{config.instance_url}/api/now/table/syslog"
    query_params = {
        "sysparm_limit": params.limit,
        "sysparm_offset": params.offset,
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
        "sysparm_fields": "sys_id,level,message,source,category,sys_created_on,sys_created_by",
    }
    if params.query:
        query_params["sysparm_query"] = params.query

    try:
        response = requests.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        result = response.json().get("result", [])
        return {
            "success": True,
            "message": f"Retrieved {len(result)} syslog entries",
            "entries": result,
            "total": len(result),
            "limit": params.limit,
            "offset": params.offset,
        }
    except requests.RequestException as e:
        logger.error(f"Failed to list syslog entries: {e}")
        return {
            "success": False,
            "message": f"Failed to list syslog entries: {str(e)}",
            "entries": [],
            "total": 0,
            "limit": params.limit,
            "offset": params.offset,
        }


def get_syslog_entry(
    config: ServerConfig,
    auth_manager: AuthManager,
    params: GetSyslogEntryParams,
) -> Dict[str, Any]:
    """Get a single syslog entry by sys_id."""

    url = f"{config.instance_url}/api/now/table/syslog/{params.sys_id}"
    query_params = {
        "sysparm_display_value": "true",
        "sysparm_exclude_reference_link": "true",
    }

    try:
        response = requests.get(
            url,
            params=query_params,
            headers=auth_manager.get_headers(),
            timeout=config.timeout,
        )
        response.raise_for_status()
        result = response.json().get("result")
        if not result:
            return {"success": False, "message": "Syslog entry not found"}
        return {
            "success": True,
            "message": "Syslog entry retrieved",
            "entry": result,
        }
    except requests.RequestException as e:
        logger.error(f"Failed to get syslog entry: {e}")
        return {
            "success": False,
            "message": f"Failed to get syslog entry: {str(e)}",
        }
