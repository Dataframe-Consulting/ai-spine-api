from fastapi import APIRouter, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Dict, Any, Optional
import structlog
from datetime import datetime
import jsonschema
import json

from src.core.models import (
    ToolInfo, ToolRegistration, ToolUpdate, ToolResponse,
    ToolTestRequest, ToolTestResponse, ToolSchema, ToolSchemaCreate,
    ToolSchemaResponse, ToolExecution, ToolExecutionCreate,
    ToolExecutionResponse, ToolCategory, ToolSearchRequest, 
    ToolSearchResponse, ToolType, ComprehensiveToolRegistration,
    ToolInfoWithSchemas, ComprehensiveToolResponse
)
from src.core.auth import optional_api_key
from src.core.supabase_client import get_supabase_db

# Security scheme for extracting API key as string
security = HTTPBearer(auto_error=False)

async def get_api_key_string(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> str:
    """Extract API key as plain string for endpoints that need it"""
    if not credentials:
        return "anonymous"
    return credentials.credentials

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])

def validate_json_schema(schema_data: ToolSchema) -> bool:
    """Validate that a ToolSchema represents a valid JSON Schema"""
    try:
        # Convert ToolSchema to JSON Schema format
        json_schema = {
            "$schema": schema_data.schema_version,
            "type": schema_data.type,
            "properties": {},
            "required": schema_data.required_properties,
            "additionalProperties": schema_data.additional_properties
        }
        
        # Add artifact_config if present
        if hasattr(schema_data, 'artifact_config') and schema_data.artifact_config:
            json_schema["artifact_config"] = schema_data.artifact_config
        
        # Convert properties
        for prop in schema_data.properties:
            property_schema = {
                "type": prop.type,
                "description": prop.description
            }
            
            # Add validations based on type
            if prop.format:
                property_schema["format"] = prop.format
            if prop.pattern:
                property_schema["pattern"] = prop.pattern
            if prop.enum_values:
                property_schema["enum"] = prop.enum_values
            if prop.minimum is not None:
                property_schema["minimum"] = prop.minimum
            if prop.maximum is not None:
                property_schema["maximum"] = prop.maximum
            if prop.min_length is not None:
                property_schema["minLength"] = prop.min_length
            if prop.max_length is not None:
                property_schema["maxLength"] = prop.max_length
            
            # Handle array properties
            if prop.type == "array" and prop.array_item_type:
                items_schema = {"type": prop.array_item_type}
                if prop.array_item_format:
                    items_schema["format"] = prop.array_item_format
                if prop.array_item_enum:
                    items_schema["enum"] = prop.array_item_enum
                property_schema["items"] = items_schema
                
                if prop.min_items is not None:
                    property_schema["minItems"] = prop.min_items
                if prop.max_items is not None:
                    property_schema["maxItems"] = prop.max_items
            
            # Handle object properties
            if prop.type == "object" and prop.object_properties:
                object_properties = {}
                object_required = []
                
                for obj_prop in prop.object_properties:
                    obj_prop_schema = {
                        "type": obj_prop.type,
                        "description": obj_prop.description
                    }
                    if obj_prop.format:
                        obj_prop_schema["format"] = obj_prop.format
                    
                    object_properties[obj_prop.property_name] = obj_prop_schema
                    if obj_prop.required:
                        object_required.append(obj_prop.property_name)
                
                property_schema["properties"] = object_properties
                if object_required:
                    property_schema["required"] = object_required
            
            json_schema["properties"][prop.property_name] = property_schema
        
        # Validate the schema structure
        jsonschema.Draft7Validator.check_schema(json_schema)
        return True
        
    except Exception as e:
        logger.warning("JSON Schema validation failed", error=str(e))
        return False

@router.get("", response_model=Dict[str, Any])
async def list_tools(api_key: Optional[str] = Depends(optional_api_key)):
    """List tools (system tools for all, plus own tools if authenticated)"""
    try:
        # Get all tools from database
        db = get_supabase_db()

        # Get all active tools (no user filtering for now until created_by column exists)
        all_tools = db.client.table("tools")\
            .select("*")\
            .eq("is_active", True)\
            .execute()

        tools_data = all_tools.data if all_tools.data else []

        # Convert to ToolInfo objects
        tools = []
        for tool_data in tools_data:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

                tool = ToolInfo(**tool_data)
                tools.append(tool)
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue

        return {
            "tools": [tool.dict() for tool in tools],
            "count": len(tools),
            "authenticated": api_key is not None and api_key != "anonymous"
        }
    except Exception as e:
        logger.error("Failed to list tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-tools", response_model=Dict[str, Any])
async def get_my_tools(api_key: str = Depends(optional_api_key)):
    """Get only the authenticated user's tools (placeholder - returns all tools for now)"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        # For now, return all active tools since created_by column doesn't exist
        db = get_supabase_db()
        all_tools = db.client.table("tools")\
            .select("*")\
            .eq("is_active", True)\
            .execute()

        # Convert to ToolInfo objects
        tools = []
        for tool_data in all_tools.data if all_tools.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

                tool = ToolInfo(**tool_data)
                tools.append(tool)
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue

        return {
            "tools": [tool.dict() for tool in tools],
            "count": len(tools),
            "user_id": "placeholder"  # TODO: Implement when created_by exists
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active", response_model=Dict[str, Any])
async def list_active_tools():
    """List all active tools"""
    try:
        db = get_supabase_db()
        active_tools = db.client.table("tools")\
            .select("*")\
            .eq("is_active", True)\
            .execute()

        # Convert to ToolInfo objects
        tools = []
        for tool_data in active_tools.data if active_tools.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

                tool = ToolInfo(**tool_data)
                tools.append(tool)
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue

        return {
            "tools": [tool.dict() for tool in tools],
            "count": len(tools)
        }
    except Exception as e:
        logger.error("Failed to list active tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=ComprehensiveToolResponse)
async def register_comprehensive_tool(
    tool_data: ComprehensiveToolRegistration,
    api_key: str = Depends(get_api_key_string)
):
    """Register a complete tool with schemas and type assignments"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required to register tools")

    try:
        # Get user_id from API key
        user_id = None
        if api_key.startswith("sk_"):
            db = get_supabase_db()
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            print(result)
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Check if tool_id already exists
        db = get_supabase_db()
        existing = db.client.table("tools")\
            .select("tool_id")\
            .eq("tool_id", tool_data.tool_id)\
            .execute()

        if existing.data and len(existing.data) > 0:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_data.tool_id}' already exists")

        # Validate schemas if provided
        if tool_data.input_schema and not validate_json_schema(tool_data.input_schema):
            raise HTTPException(status_code=400, detail="Invalid input schema format")
        
        if tool_data.output_schema and not validate_json_schema(tool_data.output_schema):
            raise HTTPException(status_code=400, detail="Invalid output schema format")
            
        if tool_data.config_schema and not validate_json_schema(tool_data.config_schema):
            raise HTTPException(status_code=400, detail="Invalid config schema format")

        # Start transaction
        now = datetime.utcnow()
        
        # 1. Create the main tool record with created_by field
        new_tool = {
            "tool_id": tool_data.tool_id,
            "name": tool_data.name,
            "description": tool_data.description,
            "endpoint": tool_data.endpoint,
            "is_active": tool_data.is_active if hasattr(tool_data, 'is_active') else True,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "created_by": user_id
        }

        tool_result = db.client.table("tools").insert(new_tool).execute()
        if not tool_result.data:
            raise HTTPException(status_code=500, detail="Failed to create tool")

        created_tool = tool_result.data[0]
        tool_uuid = created_tool["id"]

        # 2. Create tool type assignments
        assigned_categories = []
        if tool_data.tool_type:
            # Get tool_type IDs from type names - ensure they are string types
            type_names = []
            for t in tool_data.tool_type:
                if isinstance(t, str):
                    type_names.append(t.upper())
                elif hasattr(t, 'value'):
                    type_names.append(t.value.upper())
                else:
                    type_names.append(str(t).upper())
            
            types_result = db.client.table("tool_types")\
                .select("id, type_name, description, created_at")\
                .in_("type_name", type_names)\
                .execute()
            
            if types_result.data:
                assignments = []
                for tool_type in types_result.data:
                    assignments.append({
                        "tool_id": tool_uuid,
                        "tool_type_id": tool_type["id"],
                        "created_at": now.isoformat()
                    })
                    
                    # Add to response categories
                    assigned_categories.append(ToolCategory(
                        id=tool_type["id"],
                        type_name=tool_type["type_name"],
                        description=tool_type.get("description"),
                        created_at=datetime.fromisoformat(tool_type["created_at"].replace("Z", "+00:00"))
                            if isinstance(tool_type.get("created_at"), str)
                            else tool_type.get("created_at", datetime.utcnow())
                    ))

                if assignments:
                    db.client.table("tool_type_assignments").insert(assignments).execute()

        # 3. Create tool schemas including schema_properties
        schemas_created = {
            "input_schema": None,
            "output_schema": None,
            "config_schema": None
        }
        
        for schema_type, schema_data in [
            ("input", tool_data.input_schema),
            ("output", tool_data.output_schema),
            ("config", tool_data.config_schema)
        ]:
            if schema_data:
                schema_record = {
                    "tool_id": tool_uuid,
                    "schema_type": schema_type,
                    "schema_data": schema_data.dict(),
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }
                
                schema_result = db.client.table("tool_schemas").insert(schema_record).execute()
                if schema_result.data:
                    schemas_created[f"{schema_type}_schema"] = schema_data
                    schema_id = schema_result.data[0]["id"]
                    
                    # Create schema_properties entries for each property
                    if hasattr(schema_data, 'properties') and schema_data.properties:
                        properties_to_insert = []
                        for prop in schema_data.properties:
                            prop_dict = prop.dict() if hasattr(prop, 'dict') else prop
                            property_record = {
                                "schema_id": schema_id,
                                "property_name": prop_dict.get("property_name"),
                                "property_type": prop_dict.get("type"),
                                "description": prop_dict.get("description"),
                                "is_required": prop_dict.get("required", False),
                                "is_sensitive": prop_dict.get("sensitive", False) if schema_type == "config" else False,
                                "default_value": prop_dict.get("default_value"),
                                "format_type": prop_dict.get("format"),
                                "validation_rules": {
                                    "minimum": prop_dict.get("minimum"),
                                    "maximum": prop_dict.get("maximum"),
                                    "min_length": prop_dict.get("min_length"),
                                    "max_length": prop_dict.get("max_length"),
                                    "pattern": prop_dict.get("pattern"),
                                    "enum_values": prop_dict.get("enum_values"),
                                    "min_items": prop_dict.get("min_items"),
                                    "max_items": prop_dict.get("max_items"),
                                    "array_item_type": prop_dict.get("array_item_type"),
                                    "array_item_format": prop_dict.get("array_item_format"),
                                    "array_item_enum": prop_dict.get("array_item_enum")
                                },
                                "created_at": now.isoformat()
                            }
                            
                            # Remove None values from validation_rules
                            property_record["validation_rules"] = {
                                k: v for k, v in property_record["validation_rules"].items() 
                                if v is not None
                            }
                            
                            properties_to_insert.append(property_record)
                        
                        if properties_to_insert:
                            db.client.table("schema_properties").insert(properties_to_insert).execute()

        # 4. Build complete response
        tool_with_schemas = ToolInfoWithSchemas(
            id=created_tool["id"],
            tool_id=created_tool["tool_id"],
            name=created_tool["name"],
            description=created_tool["description"],
            endpoint=created_tool["endpoint"],
            tool_type=[],  # Will be populated from assigned_categories
            custom_fields=[],  # Legacy field
            is_active=created_tool["is_active"],
            metadata=tool_data.metadata if hasattr(tool_data, 'metadata') and tool_data.metadata else {},
            created_at=now,
            updated_at=now,
            created_by=user_id,
            **schemas_created
        )

        return ComprehensiveToolResponse(
            success=True,
            tool=tool_with_schemas,
            assigned_types=assigned_categories,
            message=f"Tool '{tool_data.tool_id}' registered successfully with {len(assigned_categories)} type(s) and {sum(1 for s in schemas_created.values() if s)} schema(s)"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to register comprehensive tool", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    tool_update: ToolUpdate,
    api_key: str = Depends(optional_api_key)
):
    """Update a tool"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required to update tools")

    try:
        # Get user_id from API key
        user_id = None
        if api_key.startswith("sk_"):
            db = get_supabase_db()
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Check if tool exists and user owns it
        db = get_supabase_db()
        existing = db.client.table("tools")\
            .select("*")\
            .eq("tool_id", tool_id)\
            .execute()

        if not existing.data or len(existing.data) == 0:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

        existing_tool = existing.data[0]

        # TODO: Check ownership when created_by column exists
        # if existing_tool.get("created_by") and existing_tool["created_by"] != user_id:
        #     raise HTTPException(status_code=403, detail="You can only update your own tools")

        # Build update data
        update_data = {"updated_at": datetime.utcnow().isoformat()}

        if tool_update.name is not None:
            update_data["name"] = tool_update.name
        if tool_update.description is not None:
            update_data["description"] = tool_update.description
        if tool_update.endpoint is not None:
            update_data["endpoint"] = tool_update.endpoint
        if tool_update.tool_type is not None:
            update_data["tool_type"] = [t.value for t in tool_update.tool_type]
        if tool_update.custom_fields is not None:
            update_data["custom_fields"] = [field.dict() for field in tool_update.custom_fields]
        if tool_update.is_active is not None:
            update_data["is_active"] = tool_update.is_active
        if tool_update.metadata is not None:
            update_data["metadata"] = tool_update.metadata

        # Update tool
        result = db.client.table("tools")\
            .update(update_data)\
            .eq("tool_id", tool_id)\
            .execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="Failed to update tool")

        # Return updated tool
        updated_tool_data = result.data[0]
        if isinstance(updated_tool_data.get("created_at"), str):
            updated_tool_data["created_at"] = datetime.fromisoformat(updated_tool_data["created_at"].replace("Z", "+00:00"))
        if isinstance(updated_tool_data.get("updated_at"), str):
            updated_tool_data["updated_at"] = datetime.fromisoformat(updated_tool_data["updated_at"].replace("Z", "+00:00"))

        tool = ToolInfo(**updated_tool_data)

        return ToolResponse(
            success=True,
            tool=tool,
            message=f"Tool '{tool_id}' updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{tool_id}", response_model=Dict[str, str])
async def delete_tool(
    tool_id: str,
    api_key: str = Depends(optional_api_key)
):
    """Delete a tool"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required to delete tools")

    try:
        # Get user_id from API key
        user_id = None
        if api_key.startswith("sk_"):
            db = get_supabase_db()
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Check if tool exists and user owns it
        db = get_supabase_db()
        existing = db.client.table("tools")\
            .select("*")\
            .eq("tool_id", tool_id)\
            .execute()

        if not existing.data or len(existing.data) == 0:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

        existing_tool = existing.data[0]

        # TODO: Check ownership when created_by column exists
        # if existing_tool.get("created_by") and existing_tool["created_by"] != user_id:
        #     raise HTTPException(status_code=403, detail="You can only delete your own tools")

        # Delete tool
        result = db.client.table("tools")\
            .delete()\
            .eq("tool_id", tool_id)\
            .execute()

        return {"message": f"Tool '{tool_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories", response_model=List[ToolCategory])
async def get_tool_categories():
    """Get all tool categories"""
    try:
        db = get_supabase_db()
        result = db.client.table("tool_types").select("*").order("type_name").execute()
        
        categories = []
        for cat_data in result.data if result.data else []:
            categories.append(ToolCategory(
                id=cat_data["id"],
                type_name=cat_data["type_name"],
                description=cat_data.get("description"),
                created_at=datetime.fromisoformat(cat_data["created_at"].replace("Z", "+00:00"))
                    if isinstance(cat_data.get("created_at"), str)
                    else cat_data.get("created_at", datetime.utcnow())
            ))
        
        return categories
    except Exception as e:
        logger.error("Failed to get tool categories", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/categories", response_model=ToolCategory)
async def create_tool_category(
    type_name: str,
    description: Optional[str] = None,
    api_key: str = Depends(optional_api_key)
):
    """Create a new tool category (admin only)"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        db = get_supabase_db()
        
        # Check if category already exists
        existing = db.client.table("tool_types").select("id").eq("type_name", type_name.upper()).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail=f"Tool type '{type_name}' already exists")
        
        # Create new category
        now = datetime.utcnow()
        new_category = {
            "type_name": type_name.upper(),
            "description": description,
            "created_at": now.isoformat()
        }
        
        result = db.client.table("tool_types").insert(new_category).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create tool category")
        
        category_data = result.data[0]
        category_data["created_at"] = now
        
        return ToolCategory(**category_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create tool category", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/categories/{category_id}", response_model=ToolCategory)
async def update_tool_category(
    category_id: int,
    type_name: Optional[str] = None,
    description: Optional[str] = None,
    api_key: str = Depends(optional_api_key)
):
    """Update a tool category (admin only)"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        db = get_supabase_db()
        
        # Check if category exists
        existing = db.client.table("tool_types").select("*").eq("id", category_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Tool category not found")
        
        # Build update data
        update_data = {}
        if type_name is not None:
            # Check if new name conflicts
            name_check = db.client.table("tool_types").select("id").eq("type_name", type_name.upper()).neq("id", category_id).execute()
            if name_check.data:
                raise HTTPException(status_code=400, detail=f"Tool type '{type_name}' already exists")
            update_data["type_name"] = type_name.upper()
        
        if description is not None:
            update_data["description"] = description
        
        if not update_data:
            # No changes
            category_data = existing.data[0]
            if isinstance(category_data.get("created_at"), str):
                category_data["created_at"] = datetime.fromisoformat(category_data["created_at"].replace("Z", "+00:00"))
            return ToolCategory(**category_data)
        
        # Update category
        result = db.client.table("tool_types").update(update_data).eq("id", category_id).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to update tool category")
        
        category_data = result.data[0]
        if isinstance(category_data.get("created_at"), str):
            category_data["created_at"] = datetime.fromisoformat(category_data["created_at"].replace("Z", "+00:00"))
        
        return ToolCategory(**category_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tool category", category_id=category_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/categories/{category_id}")
async def delete_tool_category(
    category_id: int,
    api_key: str = Depends(optional_api_key)
):
    """Delete a tool category (admin only)"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        db = get_supabase_db()
        
        # Check if category exists
        existing = db.client.table("tool_types").select("id").eq("id", category_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Tool category not found")
        
        # Check if category is in use
        in_use = db.client.table("tool_type_assignments").select("id").eq("tool_type_id", category_id).limit(1).execute()
        if in_use.data:
            raise HTTPException(status_code=400, detail="Cannot delete tool category: it is being used by tools")
        
        # Delete category
        result = db.client.table("tool_types").delete().eq("id", category_id).execute()
        
        return {"message": f"Tool category deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete tool category", category_id=category_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tool_id}/types", response_model=List[ToolCategory])
async def get_tool_types(tool_id: str):
    """Get all types assigned to a specific tool"""
    try:
        db = get_supabase_db()
        
        # First check if tool exists
        tool_result = db.client.table("tools").select("id").eq("tool_id", tool_id).execute()
        if not tool_result.data:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        
        tool_uuid = tool_result.data[0]["id"]
        
        # Get assigned types
        result = db.client.table("tool_type_assignments")\
            .select("tool_types(id, type_name, description, created_at)")\
            .eq("tool_id", tool_uuid)\
            .execute()
        
        types = []
        for assignment in result.data if result.data else []:
            type_data = assignment["tool_types"]
            if type_data:
                types.append(ToolCategory(
                    id=type_data["id"],
                    type_name=type_data["type_name"],
                    description=type_data.get("description"),
                    created_at=datetime.fromisoformat(type_data["created_at"].replace("Z", "+00:00"))
                        if isinstance(type_data.get("created_at"), str)
                        else type_data.get("created_at", datetime.utcnow())
                ))
        
        return types
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tool types", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{tool_id}/types/{type_id}")
async def assign_tool_type(
    tool_id: str,
    type_id: int,
    api_key: str = Depends(optional_api_key)
):
    """Assign a type to a tool"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        db = get_supabase_db()
        
        # Check if tool exists
        tool_result = db.client.table("tools").select("id").eq("tool_id", tool_id).execute()
        if not tool_result.data:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        
        tool_uuid = tool_result.data[0]["id"]
        
        # Check if type exists
        type_result = db.client.table("tool_types").select("id").eq("id", type_id).execute()
        if not type_result.data:
            raise HTTPException(status_code=404, detail=f"Tool type with id {type_id} not found")
        
        # Check if assignment already exists
        existing = db.client.table("tool_type_assignments")\
            .select("id")\
            .eq("tool_id", tool_uuid)\
            .eq("tool_type_id", type_id)\
            .execute()
        
        if existing.data:
            raise HTTPException(status_code=400, detail="Tool type already assigned to this tool")
        
        # Create assignment
        assignment = {
            "tool_id": tool_uuid,
            "tool_type_id": type_id,
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = db.client.table("tool_type_assignments").insert(assignment).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to assign tool type")
        
        return {"message": "Tool type assigned successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to assign tool type", tool_id=tool_id, type_id=type_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{tool_id}/types/{type_id}")
async def unassign_tool_type(
    tool_id: str,
    type_id: int,
    api_key: str = Depends(optional_api_key)
):
    """Remove a type assignment from a tool"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        db = get_supabase_db()
        
        # Check if tool exists
        tool_result = db.client.table("tools").select("id").eq("tool_id", tool_id).execute()
        if not tool_result.data:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        
        tool_uuid = tool_result.data[0]["id"]
        
        # Check if assignment exists
        existing = db.client.table("tool_type_assignments")\
            .select("id")\
            .eq("tool_id", tool_uuid)\
            .eq("tool_type_id", type_id)\
            .execute()
        
        if not existing.data:
            raise HTTPException(status_code=404, detail="Tool type assignment not found")
        
        # Delete assignment
        result = db.client.table("tool_type_assignments")\
            .delete()\
            .eq("tool_id", tool_uuid)\
            .eq("tool_type_id", type_id)\
            .execute()
        
        return {"message": "Tool type assignment removed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unassign tool type", tool_id=tool_id, type_id=type_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search", response_model=ToolSearchResponse)
async def search_tools(
    search_request: ToolSearchRequest,
    api_key: Optional[str] = Depends(optional_api_key)
):
    """Search tools with filters"""
    try:
        db = get_supabase_db()
        
        # Get user_id if authenticated
        user_id = None
        if api_key and api_key != "anonymous" and api_key.startswith("sk_"):
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]
        
        # Build query
        query = db.client.table("tools").select("*")
        
        # Apply filters
        if search_request.is_active is not None:
            query = query.eq("is_active", search_request.is_active)
        
        # TODO: User filtering when created_by column exists
        # For now, show all tools
        
        # Text search in name and description
        if search_request.query:
            query = query.or_(f"name.ilike.%{search_request.query}%,description.ilike.%{search_request.query}%")
        
        # Get total count first
        count_result = query.execute()
        total_count = len(count_result.data) if count_result.data else 0
        
        # Apply pagination
        query = query.range(search_request.offset, search_request.offset + search_request.limit - 1)
        query = query.order("created_at", desc=True)
        
        result = query.execute()
        
        # Convert to ToolInfo objects
        tools = []
        for tool_data in result.data if result.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))
                
                tool = ToolInfo(**tool_data)
                tools.append(tool)
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue
        
        return ToolSearchResponse(
            tools=tools,
            total_count=total_count,
            limit=search_request.limit,
            offset=search_request.offset,
            has_more=(search_request.offset + search_request.limit) < total_count
        )
    except Exception as e:
        logger.error("Failed to search tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{tool_id}/schemas", response_model=ToolSchemaResponse)
async def create_tool_schemas(
    tool_id: str,
    schema_data: ToolSchemaCreate,
    api_key: str = Depends(optional_api_key)
):
    """Create or update tool schemas (input, output, config)"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Verify tool exists and user owns it
        db = get_supabase_db()
        
        # Get user_id
        user_id = None
        if api_key.startswith("sk_"):
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Check tool exists
        tool_result = db.client.table("tools").select("id").eq("tool_id", tool_id).execute()
        if not tool_result.data:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        
        tool_data = tool_result.data[0]
        # TODO: Check ownership when created_by column exists
        
        # Insert or update schemas
        tool_db_id = tool_data["id"]
        now = datetime.utcnow()
        
        schemas_to_create = []
        if schema_data.input_schema:
            schemas_to_create.append(("input", schema_data.input_schema.dict()))
        if schema_data.output_schema:
            schemas_to_create.append(("output", schema_data.output_schema.dict()))
        if schema_data.config_schema:
            schemas_to_create.append(("config", schema_data.config_schema.dict()))
        
        for schema_type, schema_json in schemas_to_create:
            # Delete existing schema of this type
            db.client.table("tool_schemas").delete().eq("tool_id", tool_db_id).eq("schema_type", schema_type).execute()
            
            # Insert new schema
            db.client.table("tool_schemas").insert({
                "tool_id": tool_db_id,
                "schema_type": schema_type,
                "schema_data": schema_json,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }).execute()
        
        # Return the schemas
        return ToolSchemaResponse(
            tool_id=tool_id,
            input_schema=schema_data.input_schema,
            output_schema=schema_data.output_schema,
            config_schema=schema_data.config_schema
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create tool schemas", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tool_id}/schemas", response_model=ToolSchemaResponse)
async def get_tool_schemas(tool_id: str):
    """Get tool schemas (input, output, config)"""
    try:
        db = get_supabase_db()
        
        # Get tool ID
        tool_result = db.client.table("tools").select("id").eq("tool_id", tool_id).execute()
        if not tool_result.data:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        
        tool_db_id = tool_result.data[0]["id"]
        
        # Get all schemas for this tool
        schemas_result = db.client.table("tool_schemas").select("*").eq("tool_id", tool_db_id).execute()
        
        schemas = {
            "input_schema": None,
            "output_schema": None,
            "config_schema": None
        }
        
        for schema_data in schemas_result.data if schemas_result.data else []:
            schema_type = schema_data["schema_type"]
            schema_json = schema_data["schema_data"]
            
            if schema_type in ["input", "output", "config"]:
                try:
                    schemas[f"{schema_type}_schema"] = ToolSchema(**schema_json)
                except Exception as e:
                    logger.warning(f"Failed to parse {schema_type} schema", tool_id=tool_id, error=str(e))
        
        return ToolSchemaResponse(
            tool_id=tool_id,
            **schemas
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tool schemas", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{tool_id}/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    tool_id: str,
    execution_request: ToolExecutionCreate,
    api_key: Optional[str] = Depends(optional_api_key)
):
    """Execute a tool with given input and config"""
    try:
        import httpx
        import time
        
        db = get_supabase_db()
        
        # Get user_id if authenticated
        user_id = None
        if api_key and api_key != "anonymous" and api_key.startswith("sk_"):
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]
        
        # Get tool info
        tool_result = db.client.table("tools").select("*").eq("tool_id", tool_id).execute()
        if not tool_result.data:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        
        tool_data = tool_result.data[0]
        if not tool_data["is_active"]:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_id}' is not active")
        
        # Create execution record
        execution = ToolExecution(
            tool_id=tool_data["id"],
            agent_id=execution_request.agent_id,
            execution_id=execution_request.execution_id,
            input_data=execution_request.input_data,
            config_data=execution_request.config_data,
            status="pending",
            # created_by=user_id  # TODO: Add when column exists
        )
        
        # Save execution to database
        now = datetime.utcnow()
        execution_data = {
            "id": execution.id,
            "tool_id": tool_data["id"],
            "agent_id": execution.agent_id,
            "execution_id": execution.execution_id,
            "input_data": execution.input_data,
            "config_data": execution.config_data,
            "status": "running",
            "started_at": now.isoformat(),
            "created_at": execution.created_at.isoformat(),
            # "created_by": user_id  # TODO: Add when column exists
        }
        
        db.client.table("tool_executions").insert(execution_data).execute()
        
        try:
            # Execute tool via HTTP
            start_time = time.time()
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {
                    "execution_id": execution.execution_id or execution.id,
                    "input": execution.input_data,
                    "config": execution.config_data
                }
                
                response = await client.post(
                    f"{tool_data['endpoint']}/execute",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code == 200:
                    result_data = response.json()
                    
                    # Update execution record - SUCCESS
                    execution.status = "success"
                    execution.output_data = result_data.get("output", {})
                    execution.execution_time_ms = execution_time_ms
                    execution.completed_at = datetime.utcnow()
                    
                    db.client.table("tool_executions").update({
                        "status": "success",
                        "output_data": execution.output_data,
                        "execution_time_ms": execution_time_ms,
                        "completed_at": execution.completed_at.isoformat()
                    }).eq("id", execution.id).execute()
                    
                    return ToolExecutionResponse(
                        execution=execution,
                        success=True,
                        message="Tool executed successfully"
                    )
                else:
                    error_msg = f"Tool execution failed with status {response.status_code}"
                    
                    # Update execution record - ERROR
                    execution.status = "error"
                    execution.error_message = error_msg
                    execution.execution_time_ms = execution_time_ms
                    execution.completed_at = datetime.utcnow()
                    
                    db.client.table("tool_executions").update({
                        "status": "error",
                        "error_message": error_msg,
                        "execution_time_ms": execution_time_ms,
                        "completed_at": execution.completed_at.isoformat()
                    }).eq("id", execution.id).execute()
                    
                    return ToolExecutionResponse(
                        execution=execution,
                        success=False,
                        message=error_msg
                    )
                    
        except httpx.TimeoutException:
            error_msg = "Tool execution timed out"
            
            # Update execution record - TIMEOUT
            execution.status = "timeout"
            execution.error_message = error_msg
            execution.completed_at = datetime.utcnow()
            
            db.client.table("tool_executions").update({
                "status": "timeout",
                "error_message": error_msg,
                "completed_at": execution.completed_at.isoformat()
            }).eq("id", execution.id).execute()
            
            return ToolExecutionResponse(
                execution=execution,
                success=False,
                message=error_msg
            )
            
        except Exception as e:
            error_msg = f"Tool execution error: {str(e)}"
            
            # Update execution record - ERROR
            execution.status = "error"
            execution.error_message = error_msg
            execution.completed_at = datetime.utcnow()
            
            db.client.table("tool_executions").update({
                "status": "error",
                "error_message": error_msg,
                "completed_at": execution.completed_at.isoformat()
            }).eq("id", execution.id).execute()
            
            return ToolExecutionResponse(
                execution=execution,
                success=False,
                message=error_msg
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to execute tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/executions/{execution_id}", response_model=ToolExecution)
async def get_tool_execution(
    execution_id: str,
    api_key: Optional[str] = Depends(optional_api_key)
):
    """Get tool execution details"""
    try:
        db = get_supabase_db()
        
        # Get user_id if authenticated
        user_id = None
        if api_key and api_key != "anonymous" and api_key.startswith("sk_"):
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]
        
        # Get execution
        query = db.client.table("tool_executions").select("*").eq("id", execution_id)
        
        # TODO: Filter by user when created_by column exists
        # For now, show all executions
        
        result = query.execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Tool execution not found")
        
        execution_data = result.data[0]
        
        # Convert datetime strings
        for field in ["created_at", "started_at", "completed_at"]:
            if execution_data.get(field) and isinstance(execution_data[field], str):
                execution_data[field] = datetime.fromisoformat(execution_data[field].replace("Z", "+00:00"))
        
        return ToolExecution(**execution_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tool execution", execution_id=execution_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test", response_model=ToolTestResponse)
async def test_tool_connection(test_request: ToolTestRequest):
    """Test connection to a tool endpoint"""
    try:
        import httpx
        from time import time

        start_time = time()

        async with httpx.AsyncClient(timeout=test_request.timeout) as client:
            try:
                # Try to hit the health endpoint
                response = await client.get(f"{test_request.endpoint}/health")
                response_time = int((time() - start_time) * 1000)

                if response.status_code == 200:
                    return ToolTestResponse(
                        success=True,
                        connected=True,
                        response_time_ms=response_time,
                        endpoint=test_request.endpoint
                    )
                else:
                    return ToolTestResponse(
                        success=False,
                        connected=False,
                        response_time_ms=response_time,
                        error=f"HTTP {response.status_code}",
                        endpoint=test_request.endpoint
                    )
            except httpx.TimeoutException:
                return ToolTestResponse(
                    success=False,
                    connected=False,
                    error="Connection timeout",
                    endpoint=test_request.endpoint
                )
            except Exception as e:
                return ToolTestResponse(
                    success=False,
                    connected=False,
                    error=str(e),
                    endpoint=test_request.endpoint
                )
    except Exception as e:
        logger.error("Failed to test tool connection", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tool_id}", response_model=ToolInfo)
async def get_tool(tool_id: str):
    """Get a specific tool"""
    try:
        db = get_supabase_db()
        result = db.client.table("tools")\
            .select("*")\
            .eq("tool_id", tool_id)\
            .execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

        tool_data = result.data[0]

        # Handle datetime conversion
        if isinstance(tool_data.get("created_at"), str):
            tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
        if isinstance(tool_data.get("updated_at"), str):
            tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

        return ToolInfo(**tool_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))