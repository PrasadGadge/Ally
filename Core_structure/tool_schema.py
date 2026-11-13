# ==========================================
# Core_structure/tool_schema.py
# Generates OpenAI-style function schemas
# ==========================================

from Core_structure.tool_manifest import get_all_tools

def build_function_schemas() -> list:
    """
    Build OpenAI-style function calling schemas for all registered tools.
    Returns a list of schema dictionaries.
    """
    schemas = []
    tools = get_all_tools()
    
    for tool_name, tool_class in tools.items():
        if not tool_class.enabled:
            continue
            
        schema = {
            "type": "function",
            "function": {
                "name": tool_class.action_type,
                "description": tool_class.description,
                "parameters": tool_class.parameters
            }
        }
        schemas.append(schema)
        
    return schemas
