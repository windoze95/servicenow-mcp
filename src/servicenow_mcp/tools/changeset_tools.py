"""
Changeset tools for the ServiceNow MCP server.

This module provides tools for managing changesets in ServiceNow.
"""

import logging
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import requests
from pydantic import BaseModel, Field

from servicenow_mcp.auth.auth_manager import AuthManager
from servicenow_mcp.utils.config import AuthType, ServerConfig

logger = logging.getLogger(__name__)

# Type variable for Pydantic models
T = TypeVar('T', bound=BaseModel)


class ListChangesetsParams(BaseModel):
    """Parameters for listing changesets."""

    limit: Optional[int] = Field(10, description="Maximum number of records to return")
    offset: Optional[int] = Field(0, description="Offset to start from")
    state: Optional[str] = Field(None, description="Filter by state")
    application: Optional[str] = Field(None, description="Filter by application")
    developer: Optional[str] = Field(None, description="Filter by developer")
    timeframe: Optional[str] = Field(None, description="Filter by timeframe (recent, last_week, last_month)")
    query: Optional[str] = Field(None, description="Additional query string")


class GetChangesetDetailsParams(BaseModel):
    """Parameters for getting changeset details."""

    changeset_id: str = Field(..., description="Changeset ID or sys_id")


class CreateChangesetParams(BaseModel):
    """Parameters for creating a changeset."""

    name: str = Field(..., description="Name of the changeset")
    description: Optional[str] = Field(None, description="Description of the changeset")
    application: str = Field(..., description="Application the changeset belongs to")
    developer: Optional[str] = Field(None, description="Developer responsible for the changeset")


class UpdateChangesetParams(BaseModel):
    """Parameters for updating a changeset."""

    changeset_id: str = Field(..., description="Changeset ID or sys_id")
    name: Optional[str] = Field(None, description="Name of the changeset")
    description: Optional[str] = Field(None, description="Description of the changeset")
    state: Optional[str] = Field(None, description="State of the changeset")
    developer: Optional[str] = Field(None, description="Developer responsible for the changeset")


class CommitChangesetParams(BaseModel):
    """Parameters for committing a changeset."""

    changeset_id: str = Field(..., description="Changeset ID or sys_id")
    commit_message: Optional[str] = Field(None, description="Commit message")


class PublishChangesetParams(BaseModel):
    """Parameters for publishing a changeset."""

    changeset_id: str = Field(..., description="Changeset ID or sys_id")
    publish_notes: Optional[str] = Field(None, description="Notes for publishing")


class AddFileToChangesetParams(BaseModel):
    """Parameters for adding a file to a changeset."""

    changeset_id: str = Field(..., description="Changeset ID or sys_id")
    file_path: str = Field(..., description="Path of the file to add")
    file_content: str = Field(..., description="Content of the file")


class SetCurrentChangesetParams(BaseModel):
    """Parameters for setting the current changeset (update set) preference."""

    changeset_id: str = Field(..., description="Changeset ID or sys_id to set as current")
    user_sys_id: Optional[str] = Field(
        None, description="User sys_id to set the preference for"
    )
    user_name: Optional[str] = Field(
        None, description="User name to set the preference for (if user_sys_id not provided)"
    )
    create_if_missing: bool = Field(
        True, description="Create the preference record if it does not exist"
    )


def _unwrap_and_validate_params(
    params: Union[Dict[str, Any], BaseModel], 
    model_class: Type[T], 
    required_fields: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Unwrap and validate parameters.

    Args:
        params: The parameters to unwrap and validate. Can be a dictionary or a Pydantic model.
        model_class: The Pydantic model class to validate against.
        required_fields: List of fields that must be present.

    Returns:
        A dictionary with success status and validated parameters or error message.
    """
    try:
        # Handle case where params is already a Pydantic model
        if isinstance(params, BaseModel):
            # If it's already the correct model class, use it directly
            if isinstance(params, model_class):
                model_instance = params
            # Otherwise, convert to dict and create new instance
            else:
                model_instance = model_class(**params.dict())
        # Handle dictionary case
        else:
            # Create model instance
            model_instance = model_class(**params)
        
        # Check required fields
        if required_fields:
            missing_fields = []
            for field in required_fields:
                if getattr(model_instance, field, None) is None:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "success": False,
                    "message": f"Missing required fields: {', '.join(missing_fields)}",
                }
        
        return {
            "success": True,
            "params": model_instance,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Invalid parameters: {str(e)}",
        }


def _get_instance_url(auth_manager: AuthManager, server_config: ServerConfig) -> Optional[str]:
    """
    Get the instance URL from either auth_manager or server_config.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.

    Returns:
        The instance URL or None if not found.
    """
    # Try to get instance_url from server_config
    if hasattr(server_config, 'instance_url'):
        return server_config.instance_url
    
    # Try to get instance_url from auth_manager
    if hasattr(auth_manager, 'instance_url'):
        return auth_manager.instance_url
    
    # If neither has instance_url, check if auth_manager is actually a ServerConfig
    # and server_config is actually an AuthManager (parameters swapped)
    if hasattr(server_config, 'get_headers') and not hasattr(auth_manager, 'get_headers'):
        if hasattr(auth_manager, 'instance_url'):
            return auth_manager.instance_url
    
    logger.error("Cannot find instance_url in either auth_manager or server_config")
    return None


def _get_headers(auth_manager: AuthManager, server_config: ServerConfig) -> Optional[Dict[str, str]]:
    """
    Get the headers from either auth_manager or server_config.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.

    Returns:
        The headers or None if not found.
    """
    # Try to get headers from auth_manager
    if hasattr(auth_manager, 'get_headers'):
        return auth_manager.get_headers()
    
    # Try to get headers from server_config
    if hasattr(server_config, 'get_headers'):
        return server_config.get_headers()
    
    # If neither has get_headers, check if auth_manager is actually a ServerConfig
    # and server_config is actually an AuthManager (parameters swapped)
    if hasattr(server_config, 'get_headers') and not hasattr(auth_manager, 'get_headers'):
        return server_config.get_headers()
    
    logger.error("Cannot find get_headers method in either auth_manager or server_config")
    return None


def list_changesets(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Union[Dict[str, Any], ListChangesetsParams],
) -> Dict[str, Any]:
    """
    List changesets from ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for listing changesets. Can be a dictionary or a ListChangesetsParams object.

    Returns:
        A list of changesets.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(params, ListChangesetsParams)
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Build query parameters
    query_params = {
        "sysparm_limit": validated_params.limit,
        "sysparm_offset": validated_params.offset,
    }
    
    # Build sysparm_query
    query_parts = []
    
    if validated_params.state:
        query_parts.append(f"state={validated_params.state}")
    
    if validated_params.application:
        query_parts.append(f"application={validated_params.application}")
    
    if validated_params.developer:
        query_parts.append(f"developer={validated_params.developer}")
    
    if validated_params.timeframe:
        if validated_params.timeframe == "recent":
            query_parts.append("sys_created_onONLast 7 days@javascript:gs.beginningOfLast7Days()@javascript:gs.endOfToday()")
        elif validated_params.timeframe == "last_week":
            query_parts.append("sys_created_onONLast week@javascript:gs.beginningOfLastWeek()@javascript:gs.endOfLastWeek()")
        elif validated_params.timeframe == "last_month":
            query_parts.append("sys_created_onONLast month@javascript:gs.beginningOfLastMonth()@javascript:gs.endOfLastMonth()")
    
    if validated_params.query:
        query_parts.append(validated_params.query)
    
    if query_parts:
        query_params["sysparm_query"] = "^".join(query_parts)
    
    # Make the API request
    url = f"{instance_url}/api/now/table/sys_update_set"
    
    try:
        response = requests.get(url, params=query_params, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "changesets": result.get("result", []),
            "count": len(result.get("result", [])),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error listing changesets: {e}")
        return {
            "success": False,
            "message": f"Error listing changesets: {str(e)}",
        }


def get_changeset_details(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Union[Dict[str, Any], GetChangesetDetailsParams],
) -> Dict[str, Any]:
    """
    Get detailed information about a specific changeset.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for getting changeset details. Can be a dictionary or a GetChangesetDetailsParams object.

    Returns:
        Detailed information about the changeset.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        GetChangesetDetailsParams, 
        required_fields=["changeset_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Make the API request
    url = f"{instance_url}/api/now/table/sys_update_set/{validated_params.changeset_id}"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        # Get the changeset details
        changeset = result.get("result", {})
        
        # Get the changes in this changeset
        changes_url = f"{instance_url}/api/now/table/sys_update_xml"
        changes_params = {
            "sysparm_query": f"update_set={validated_params.changeset_id}",
        }
        
        changes_response = requests.get(changes_url, params=changes_params, headers=headers)
        changes_response.raise_for_status()
        
        changes_result = changes_response.json()
        changes = changes_result.get("result", [])
        
        return {
            "success": True,
            "changeset": changeset,
            "changes": changes,
            "change_count": len(changes),
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting changeset details: {e}")
        return {
            "success": False,
            "message": f"Error getting changeset details: {str(e)}",
        }


def create_changeset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Union[Dict[str, Any], CreateChangesetParams],
) -> Dict[str, Any]:
    """
    Create a new changeset in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for creating a changeset. Can be a dictionary or a CreateChangesetParams object.

    Returns:
        The created changeset.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        CreateChangesetParams, 
        required_fields=["name", "application"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Prepare the request data
    data = {
        "name": validated_params.name,
        "application": validated_params.application,
    }
    
    # Add optional fields if provided
    if validated_params.description:
        data["description"] = validated_params.description
    if validated_params.developer:
        data["developer"] = validated_params.developer
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Make the API request
    url = f"{instance_url}/api/now/table/sys_update_set"
    
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "message": "Changeset created successfully",
            "changeset": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error creating changeset: {e}")
        return {
            "success": False,
            "message": f"Error creating changeset: {str(e)}",
        }


def update_changeset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Union[Dict[str, Any], UpdateChangesetParams],
) -> Dict[str, Any]:
    """
    Update an existing changeset in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for updating a changeset. Can be a dictionary or a UpdateChangesetParams object.

    Returns:
        The updated changeset.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        UpdateChangesetParams, 
        required_fields=["changeset_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Prepare the request data
    data = {}
    
    # Add optional fields if provided
    if validated_params.name:
        data["name"] = validated_params.name
    if validated_params.description:
        data["description"] = validated_params.description
    if validated_params.state:
        data["state"] = validated_params.state
    if validated_params.developer:
        data["developer"] = validated_params.developer
    
    # If no fields to update, return error
    if not data:
        return {
            "success": False,
            "message": "No fields to update",
        }
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Make the API request
    url = f"{instance_url}/api/now/table/sys_update_set/{validated_params.changeset_id}"
    
    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "message": "Changeset updated successfully",
            "changeset": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating changeset: {e}")
        return {
            "success": False,
            "message": f"Error updating changeset: {str(e)}",
        }


def commit_changeset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Union[Dict[str, Any], CommitChangesetParams],
) -> Dict[str, Any]:
    """
    Commit a changeset in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for committing a changeset. Can be a dictionary or a CommitChangesetParams object.

    Returns:
        The committed changeset.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        CommitChangesetParams, 
        required_fields=["changeset_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Prepare the request data
    data = {
        "state": "complete",
    }
    
    # Add commit message if provided
    if validated_params.commit_message:
        data["description"] = validated_params.commit_message
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Make the API request
    url = f"{instance_url}/api/now/table/sys_update_set/{validated_params.changeset_id}"
    
    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "message": "Changeset committed successfully",
            "changeset": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error committing changeset: {e}")
        return {
            "success": False,
            "message": f"Error committing changeset: {str(e)}",
        }


def publish_changeset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Union[Dict[str, Any], PublishChangesetParams],
) -> Dict[str, Any]:
    """
    Publish a changeset in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for publishing a changeset. Can be a dictionary or a PublishChangesetParams object.

    Returns:
        The published changeset.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        PublishChangesetParams, 
        required_fields=["changeset_id"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Prepare the request data for the publish action
    data = {
        "state": "published",
    }
    
    # Add publish notes if provided
    if validated_params.publish_notes:
        data["description"] = validated_params.publish_notes
    
    # Make the API request
    url = f"{instance_url}/api/now/table/sys_update_set/{validated_params.changeset_id}"
    
    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "message": "Changeset published successfully",
            "changeset": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error publishing changeset: {e}")
        return {
            "success": False,
            "message": f"Error publishing changeset: {str(e)}",
        }


def add_file_to_changeset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Union[Dict[str, Any], AddFileToChangesetParams],
) -> Dict[str, Any]:
    """
    Add a file to a changeset in ServiceNow.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for adding a file to a changeset. Can be a dictionary or a AddFileToChangesetParams object.

    Returns:
        The result of the add file operation.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params, 
        AddFileToChangesetParams, 
        required_fields=["changeset_id", "file_path", "file_content"]
    )
    
    if not result["success"]:
        return result
    
    validated_params = result["params"]
    
    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }
    
    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }
    
    # Add Content-Type header
    headers["Content-Type"] = "application/json"
    
    # Prepare the request data for adding a file
    data = {
        "update_set": validated_params.changeset_id,
        "name": validated_params.file_path,
        "payload": validated_params.file_content,
        "type": "file",
    }
    
    # Make the API request
    url = f"{instance_url}/api/now/table/sys_update_xml"
    
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        
        return {
            "success": True,
            "message": "File added to changeset successfully",
            "file": result["result"],
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error adding file to changeset: {e}")
        return {
            "success": False,
            "message": f"Error adding file to changeset: {str(e)}",
        }


def _infer_user_name_from_auth(auth_manager: AuthManager) -> Optional[str]:
    """Infer a user name from the auth configuration when possible."""
    try:
        auth_config = auth_manager.config
    except Exception:
        return None

    if auth_config.type == AuthType.BASIC and auth_config.basic:
        return auth_config.basic.username
    if auth_config.type == AuthType.OAUTH and auth_config.oauth:
        return auth_config.oauth.username

    return None


def set_current_changeset(
    auth_manager: AuthManager,
    server_config: ServerConfig,
    params: Union[Dict[str, Any], SetCurrentChangesetParams],
) -> Dict[str, Any]:
    """
    Set the current changeset (update set) for a user by updating sys_user_preference.

    Args:
        auth_manager: The authentication manager.
        server_config: The server configuration.
        params: The parameters for setting the current changeset.

    Returns:
        The result of the update set preference operation.
    """
    # Unwrap and validate parameters
    result = _unwrap_and_validate_params(
        params,
        SetCurrentChangesetParams,
        required_fields=["changeset_id"],
    )

    if not result["success"]:
        return result

    validated_params = result["params"]

    # Get the instance URL
    instance_url = _get_instance_url(auth_manager, server_config)
    if not instance_url:
        return {
            "success": False,
            "message": "Cannot find instance_url in either server_config or auth_manager",
        }

    # Get the headers
    headers = _get_headers(auth_manager, server_config)
    if not headers:
        return {
            "success": False,
            "message": "Cannot find get_headers method in either auth_manager or server_config",
        }

    # Add Content-Type header
    headers["Content-Type"] = "application/json"

    # Validate changeset exists
    changeset_url = f"{instance_url}/api/now/table/sys_update_set/{validated_params.changeset_id}"
    try:
        changeset_response = requests.get(changeset_url, headers=headers)
        if changeset_response.status_code == 404:
            return {
                "success": False,
                "message": (
                    "Changeset not found. Provide the sys_id of an existing update set."
                ),
            }
        changeset_response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error validating changeset: {e}")
        return {
            "success": False,
            "message": f"Error validating changeset: {str(e)}",
        }

    # Resolve user sys_id
    user_sys_id = validated_params.user_sys_id
    user_name = validated_params.user_name

    if not user_sys_id:
        if not user_name:
            user_name = _infer_user_name_from_auth(auth_manager)

        if not user_name:
            return {
                "success": False,
                "message": (
                    "User not provided and cannot infer from auth config. "
                    "Provide user_sys_id or user_name."
                ),
            }

        user_lookup_url = f"{instance_url}/api/now/table/sys_user"
        user_params = {
            "sysparm_query": f"user_name={user_name}",
            "sysparm_limit": 1,
            "sysparm_fields": "sys_id,user_name,name",
        }
        try:
            user_response = requests.get(user_lookup_url, params=user_params, headers=headers)
            user_response.raise_for_status()
            user_result = user_response.json().get("result", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error looking up user: {e}")
            return {
                "success": False,
                "message": f"Error looking up user: {str(e)}",
            }

        if not user_result:
            return {
                "success": False,
                "message": f"User not found for user_name: {user_name}",
            }

        user_sys_id = user_result[0].get("sys_id")

    # Query existing preference
    preference_url = f"{instance_url}/api/now/table/sys_user_preference"
    preference_query = f"name=sys_update_set^user={user_sys_id}"
    preference_params = {
        "sysparm_query": preference_query,
        "sysparm_limit": 1,
    }

    try:
        preference_response = requests.get(
            preference_url, params=preference_params, headers=headers
        )
        preference_response.raise_for_status()
        preference_result = preference_response.json().get("result", [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error querying user preference: {e}")
        return {
            "success": False,
            "message": f"Error querying user preference: {str(e)}",
        }

    # Update or create preference
    try:
        if preference_result:
            preference_sys_id = preference_result[0].get("sys_id")
            update_url = f"{preference_url}/{preference_sys_id}"
            update_payload = {"value": validated_params.changeset_id}
            update_response = requests.patch(
                update_url, json=update_payload, headers=headers
            )
            update_response.raise_for_status()
            updated = update_response.json().get("result", {})
            return {
                "success": True,
                "message": "Update set preference updated successfully",
                "preference": updated,
            }

        if not validated_params.create_if_missing:
            return {
                "success": False,
                "message": "Update set preference not found and create_if_missing is False",
            }

        create_payload = {
            "name": "sys_update_set",
            "user": user_sys_id,
            "value": validated_params.changeset_id,
        }
        create_response = requests.post(
            preference_url, json=create_payload, headers=headers
        )
        create_response.raise_for_status()
        created = create_response.json().get("result", {})
        return {
            "success": True,
            "message": "Update set preference created successfully",
            "preference": created,
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error updating user preference: {e}")
        return {
            "success": False,
            "message": f"Error updating user preference: {str(e)}",
        }
