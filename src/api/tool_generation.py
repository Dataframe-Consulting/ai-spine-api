from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
import structlog
from uuid import uuid4
from pydantic import BaseModel, Field
import anthropic
import re
import json
import os

from src.core.auth import optional_api_key

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/ai-tools", tags=["ai-tools"])

# Models for tool generation
class ToolGenerationRequest(BaseModel):
    prompt: str = Field(..., description="User prompt describing the tool to generate")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)

class ToolGenerationResponse(BaseModel):
    success: bool
    tool_config: Optional[Dict[str, Any]] = None
    generated_code: Optional[str] = None
    error: Optional[str] = None
    conversation_id: Optional[str] = None

# Tool Generation with Claude API
LANGGRAPH_TOOL_TEMPLATE = """
You are an expert at creating LangGraph-compatible tools. Create a tool based on the user's requirements.

IMPORTANT: The tool must be compatible with LangGraph using the `tool` function from "@langchain/core/tools".

Here's the template structure you must follow:

```typescript
import { tool } from "@langchain/core/tools";
import { z } from "zod";

export const {tool_name} = tool(
  async (input: {InputType}) => {
    // Tool implementation here
    // Return the result as a string or object
    return "Tool execution result";
  },
  {
    name: "{tool_name}",
    description: "{tool_description}",
    schema: z.object({
      // Define input schema here using Zod
      // Example: text: z.string().describe("Input text to process")
    })
  }
);
```

{conversation_context}

User Request: {user_prompt}

Please create a complete LangGraph-compatible tool based on this request. Your response should include:

1. The complete TypeScript code with proper imports
2. A clear description of what the tool does
3. Proper input/output schema using Zod validation
4. Any necessary error handling

Make sure the tool follows the exact structure shown above and is ready to use with LangGraph.
"""

def get_anthropic_client() -> anthropic.Anthropic:
    """Get configured Anthropic client"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")

    return anthropic.Anthropic(api_key=api_key)

def parse_generated_tool(response_text: str) -> Dict[str, Any]:
    """Parse Claude's response to extract tool configuration and code"""
    try:
        logger.info("Parsing generated tool response", response_length=len(response_text))

        # Extract TypeScript code from markdown code blocks
        code_match = re.search(r'```(?:typescript|ts|javascript|js)?\n(.*?)\n```', response_text, re.DOTALL)
        if not code_match:
            raise ValueError("No code block found in response")

        generated_code = code_match.group(1).strip()

        # Extract tool name from export statement
        name_match = re.search(r'export const (\w+) = tool', generated_code)
        tool_name = name_match.group(1) if name_match else "generatedTool"

        # Extract description from tool definition
        desc_match = re.search(r'description:\s*["\']([^"\']+)["\']', generated_code)
        description = desc_match.group(1) if desc_match else "AI generated tool"

        # Extract schema definition (simplified - full parsing would be more complex)
        # For now, we'll extract basic field information
        schema_match = re.search(r'schema:\s*z\.object\(\{([^}]+)\}\)', generated_code, re.DOTALL)
        input_schema = {}

        if schema_match:
            schema_content = schema_match.group(1)
            # Parse field definitions (simplified)
            field_matches = re.findall(r'(\w+):\s*z\.(\w+)\([^)]*\)(?:\.describe\(["\']([^"\']+)["\']\))?', schema_content)

            for field_name, field_type, field_desc in field_matches:
                input_schema[field_name] = {
                    "type": field_type,
                    "description": field_desc or f"{field_name} parameter"
                }

        tool_config = {
            "name": tool_name,
            "description": description,
            "input_schema": input_schema,
            "output_format": "string or object"
        }

        logger.info("Tool parsing successful", tool_name=tool_name, schema_fields=len(input_schema))

        return {
            "tool_config": tool_config,
            "generated_code": generated_code,
            "summary": f"Generated {tool_name}: {description}"
        }

    except Exception as e:
        logger.error("Failed to parse generated tool", error=str(e))
        raise ValueError(f"Failed to parse generated tool: {str(e)}")

@router.post("/generate", response_model=ToolGenerationResponse)
async def generate_tool_with_claude(
    request: ToolGenerationRequest,
    api_key: str = Depends(optional_api_key)
):
    """Generate a LangGraph-compatible tool using Claude API"""
    try:
        logger.info("Generating tool with Claude", api_key=api_key[:8] + "..." if api_key else "none", prompt_length=len(request.prompt))

        # Get Anthropic client
        client = get_anthropic_client()

        # Build conversation context
        conversation_context = ""
        if request.conversation_history:
            conversation_context = "Previous conversation:\n"
            for msg in request.conversation_history[-5:]:  # Last 5 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation_context += f"{role}: {content}\n"
            conversation_context += "\nContinue the conversation and improve/modify the tool based on the new request.\n"

        # Prepare the prompt
        full_prompt = LANGGRAPH_TOOL_TEMPLATE.format(
            user_prompt=request.prompt,
            conversation_context=conversation_context,
            tool_name="generatedTool",
            tool_description="AI generated tool",
        )

        logger.info("Calling Claude API", prompt_length=len(full_prompt))

        # Call Claude API
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2000,
            messages=[{"role": "user", "content": full_prompt}]
        )

        response_text = response.content[0].text
        logger.info("Claude API responded", response_length=len(response_text))

        # Parse the response
        conversation_id = f"conv_{uuid4().hex[:8]}"
        parsed_result = parse_generated_tool(response_text)

        logger.info("Tool generation successful", conversation_id=conversation_id)

        return ToolGenerationResponse(
            success=True,
            tool_config=parsed_result["tool_config"],
            generated_code=parsed_result["generated_code"],
            conversation_id=conversation_id
        )

    except Exception as e:
        logger.error("Tool generation failed", error=str(e), api_key=api_key[:8] + "..." if api_key else "none")
        return ToolGenerationResponse(
            success=False,
            error=str(e)
        )

@router.get("/test")
async def test_endpoint():
    """Simple test endpoint to verify router is working"""
    return {"message": "AI Tools router works!", "status": "success"}