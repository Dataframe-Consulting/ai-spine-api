# AI Spine Agent Specification

This document defines the universal contract that all marketplace agents must follow to be compatible with AI Spine.

## Overview

All marketplace agents must expose HTTP endpoints that follow this specification. This ensures compatibility and allows AI Spine to orchestrate agents from different providers seamlessly.

## Endpoints

### 1. Health Check Endpoint

**Endpoint:** `GET /health`

**Purpose:** Verify agent availability and capabilities

**Response:**
```json
{
  "agent_id": "string",
  "version": "string",
  "capabilities": ["llm", "tools", "function_calling"],
  "ready": true,
  "endpoint": "https://agent-service.com/execute",
  "rate_limit": {
    "requests_per_minute": 100,
    "requests_per_hour": 1000
  }
}
```

**Fields:**
- `agent_id`: Unique identifier for the agent
- `version`: Semantic version (e.g., "v1.0.0")
- `capabilities`: Array of supported capabilities
- `ready`: Boolean indicating if agent is ready to process requests
- `endpoint`: The execution endpoint URL
- `rate_limit`: Rate limiting information

### 2. Execution Endpoint

**Endpoint:** `POST /execute`

**Purpose:** Process agent requests and return results

**Request Payload:**
```json
{
  "execution_id": "uuid-string",
  "node_id": "string",
  "input": {
    "user_message": "string",
    "context": {},
    "previous_messages": []
  },
  "config": {
    "system_prompt": "string",
    "max_tokens": 1000,
    "temperature": 0.7,
    "timeout": 30
  }
}
```

**Response Payload:**
```json
{
  "status": "success" | "error",
  "output": {
    "message": "string",
    "data": {},
    "metadata": {
      "tokens_used": 150,
      "processing_time": 2.5
    }
  },
  "error_message": "string (optional)",
  "execution_id": "uuid-string"
}
```

## Error Handling

### HTTP Status Codes

- `200 OK`: Successful execution
- `400 Bad Request`: Invalid request payload
- `401 Unauthorized`: Invalid API key
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Agent processing error
- `503 Service Unavailable`: Agent temporarily unavailable

### Error Response Format

```json
{
  "status": "error",
  "error_message": "Detailed error description",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "execution_id": "uuid-string"
}
```

## Rate Limiting

Agents should implement rate limiting and return appropriate headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## Security

### API Key Authentication

All requests must include an API key in the header:

```
Authorization: Bearer <api_key>
```

### Input Validation

Agents must validate all input fields and return appropriate error messages for invalid data.

## Testing

### Health Check Test

```bash
curl -X GET https://agent-service.com/health
```

### Execution Test

```bash
curl -X POST https://agent-service.com/execute \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "execution_id": "test-123",
    "node_id": "test_node",
    "input": {
      "user_message": "Hello, test message"
    },
    "config": {
      "system_prompt": "You are a helpful assistant."
    }
  }'
```

## Implementation Guidelines

1. **Stateless Design**: Agents should be stateless and handle each request independently
2. **Idempotency**: Multiple requests with same execution_id should return same result
3. **Timeout Handling**: Respect timeout configuration and return error if exceeded
4. **Logging**: Log all requests for debugging and monitoring
5. **Metrics**: Track usage, performance, and error rates

## Versioning

Agents should support versioning through the `/health` endpoint. Breaking changes require a new version number.

## Marketplace Integration

When publishing to AI Spine marketplace:

1. Agent must pass health check validation
2. Execution endpoint must be publicly accessible
3. Rate limiting must be reasonable (min 10 req/min)
4. Response time should be under 30 seconds
5. Error rate should be under 5%

## Example Implementations

### Python FastAPI Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid

app = FastAPI()

class ExecuteRequest(BaseModel):
    execution_id: str
    node_id: str
    input: dict
    config: dict

class ExecuteResponse(BaseModel):
    status: str
    output: dict
    error_message: str = None
    execution_id: str

@app.get("/health")
async def health_check():
    return {
        "agent_id": "my-agent",
        "version": "v1.0.0",
        "capabilities": ["llm", "text_processing"],
        "ready": True,
        "endpoint": "https://my-agent.com/execute",
        "rate_limit": {
            "requests_per_minute": 100,
            "requests_per_hour": 1000
        }
    }

@app.post("/execute")
async def execute(request: ExecuteRequest):
    try:
        # Process the request
        result = process_request(request)
        
        return ExecuteResponse(
            status="success",
            output=result,
            execution_id=request.execution_id
        )
    except Exception as e:
        return ExecuteResponse(
            status="error",
            output={},
            error_message=str(e),
            execution_id=request.execution_id
        )
```

### Node.js Express Example

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.get('/health', (req, res) => {
  res.json({
    agent_id: 'my-agent',
    version: 'v1.0.0',
    capabilities: ['llm', 'text_processing'],
    ready: true,
    endpoint: 'https://my-agent.com/execute',
    rate_limit: {
      requests_per_minute: 100,
      requests_per_hour: 1000
    }
  });
});

app.post('/execute', (req, res) => {
  const { execution_id, node_id, input, config } = req.body;
  
  try {
    // Process the request
    const result = processRequest(input, config);
    
    res.json({
      status: 'success',
      output: result,
      execution_id
    });
  } catch (error) {
    res.status(500).json({
      status: 'error',
      output: {},
      error_message: error.message,
      execution_id
    });
  }
});
``` 