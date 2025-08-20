# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Spine is a multi-agent orchestration infrastructure that enables coordinated work between specialized AI agents. It provides a complete system for defining, executing, and monitoring agent workflows through a FastAPI-based REST API. Ready for deployment on Railway.

## Project Structure

```
ai-spine-api/
├── src/                    # Source code
│   ├── __init__.py
│   ├── api/               # API routes and endpoints
│   │   ├── main.py       # FastAPI application
│   │   ├── agents.py     # Agent management endpoints
│   │   ├── flows.py      # Flow management endpoints  
│   │   ├── executions.py # Execution monitoring endpoints
│   │   ├── users.py      # User management endpoints
│   │   ├── user_keys.py  # Legacy API key endpoints
│   │   ├── user_keys_secure.py # Secure user account endpoints
│   │   └── marketplace_simple.py # Marketplace endpoints (MOCK)
│   └── core/              # Core business logic
│       ├── orchestrator.py # Flow execution engine (SEQUENTIAL)
│       ├── registry.py    # Agent registry
│       ├── communication.py # Inter-agent messaging
│       ├── memory.py      # Persistence layer (Supabase)
│       ├── supabase_client.py # Supabase database client
│       ├── supabase_auth.py # Supabase auth middleware
│       ├── user_auth_supabase.py # User management with Supabase
│       ├── auth.py        # API key authentication
│       └── models.py      # Data models
├── flows/                  # Flow definitions (YAML)
├── scripts/               # Test and utility scripts
├── docs/                  # Documentation
├── examples/              # Example scripts
├── .env.local            # Local environment config
├── .env.local.example    # Example config
├── requirements.txt      # Python dependencies
├── main.py              # Single entry point
├── railway.json         # Railway deployment config
└── README.md
```

## Common Development Commands

### Starting the Application

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.local.example .env.local
# Edit .env.local with your settings

# Start the application
python main.py
```

### Database Operations

```bash
# No migrations needed - Supabase handles schema
# Tables are created via Supabase dashboard
# Use Supabase Studio for database management
```

### Testing

```bash
# Test authentication and basic API
python scripts/test_auth_simple.py

# Test flow execution and parallelization
python scripts/test_execution.py

# Run demo
python examples/demo_credit_analysis.py

# Legacy tests (may not work)
python test_integration.py
python test_startup.py
```

## Railway Deployment

### Automatic Deployment
The project includes `railway.json` configuration. Simply connect your GitHub repo to Railway and it will:
1. Auto-detect Python project
2. Install dependencies from `requirements.txt`
3. Run `python main.py`

### Required Environment Variables
Set these in Railway dashboard:

```bash
# Required for production
DEV_MODE=false
DATABASE_URL=${PGDATABASE_URL}  # Railway provides this

# API Configuration
API_HOST=0.0.0.0
PORT=${PORT}  # Railway provides this

# Optional
API_KEY_REQUIRED=true
API_KEY=your-secure-key
REDIS_URL=${REDIS_URL}  # If using Redis addon
```

### Railway CLI Deployment
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link project
railway login
railway link

# Deploy
railway up
```

## Architecture

### Core Components

1. **Orchestrator** (`src/core/orchestrator.py`)
   - DAG-based workflow execution
   - NetworkX for graph validation
   - **SEQUENTIAL EXECUTION ONLY** (no parallelization yet)
   - Executes nodes in topological order one by one

2. **Registry** (`src/core/registry.py`)
   - Dynamic agent registration
   - Basic health checking (30s intervals)
   - Capability tracking
   - Loads agents from Supabase on startup

3. **Memory Store** (`src/core/memory.py`)
   - Supabase persistence (production)
   - Stores flows, agents, executions
   - User-scoped data access

4. **Communication** (`src/core/communication.py`)
   - Async message passing
   - Redis/Celery support
   - Event-driven architecture

5. **Database** (`src/core/supabase_client.py`)
   - Supabase client for all DB operations
   - Tables: api_users, agents, flows, executions
   - No migrations needed (managed in Supabase)

6. **Auth** (Multiple systems - NEEDS CONSOLIDATION)
   - `auth.py`: API key authentication (master + user keys)
   - `supabase_auth.py`: Supabase JWT tokens
   - `user_auth_supabase.py`: User management with Supabase
   - Mixed authentication strategies in endpoints
   - Usage tracking and credits system

### API Endpoints

#### Core
- `GET /health` - Health check
- `GET /status` - System status
- `GET /metrics` - Prometheus metrics
- `GET /docs` - Swagger documentation

#### Agents
- `GET /api/v1/agents` - List agents (filtered by user)
- `GET /api/v1/agents/my-agents` - User's own agents
- `POST /api/v1/agents` - Register new agent
- `DELETE /api/v1/agents/{id}` - Deregister agent

#### Flows  
- `GET /api/v1/flows` - List flows (system + user's)
- `GET /api/v1/flows/my-flows` - User's own flows
- `GET /api/v1/flows/{id}` - Get flow details
- `POST /api/v1/flows` - Create new flow
- `POST /flows/execute` - Execute flow (OLD endpoint)

#### Executions
- `GET /api/v1/executions/{id}` - Get execution status
- `GET /api/v1/executions` - List executions
- `POST /api/v1/executions/{id}/cancel` - Cancel execution
- `GET /api/v1/messages/{execution_id}` - Get messages

#### Users (Multiple endpoints - NEEDS CONSOLIDATION)
- `GET /api/v1/users/me` - Get current user info
- `POST /api/v1/users/create` - Create new user (Master Key Required)
- `POST /api/v1/users/regenerate-key` - Regenerate API key
- `POST /api/v1/users/add-credits` - Add credits
- `GET /api/v1/users/{id}` - Get user by ID
- `POST /api/v1/user-keys/create` - Legacy endpoint
- `POST /api/v1/user-account/create` - Secure endpoint with JWT

#### Marketplace (MOCK ONLY)
- `GET /api/v1/marketplace/agents` - List mock agents
- `GET /api/v1/marketplace/agents/{id}` - Get mock agent
- `POST /api/v1/marketplace/agents/{id}/test` - Test mock agent
- `GET /api/v1/marketplace/categories` - Get categories
- `GET /api/v1/marketplace/stats` - Get mock stats

### Flow Definition Format

```yaml
flow_id: unique_identifier
name: "Human Readable Name"
description: "Flow description"
version: "1.0.0"
nodes:
  - id: node_id
    agent_id: registered_agent_id
    type: input|processor|output
    depends_on: [predecessor_node_ids]
    config:
      system_prompt: "Optional prompt"
      timeout: 30
      max_retries: 3
entry_point: first_node_id
exit_points: [final_node_ids]
metadata:
  author: "name"
  tags: ["tag1", "tag2"]
```

### Agent Contract

Agents must implement (see `docs/agent_spec.md`):

```python
# GET /health
{
  "agent_id": "string",
  "version": "string",
  "capabilities": ["llm", "tools"],
  "ready": true,
  "endpoint": "https://agent.com/execute"
}

# POST /execute
Request: {
  "execution_id": "uuid",
  "node_id": "string",
  "input": {...},
  "config": {...}
}

Response: {
  "status": "success|error",
  "output": {...},
  "execution_id": "uuid"
}
```

## Environment Variables

```bash
# Mode Configuration
DEV_MODE=true|false              # Development vs Production

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000                    # Use PORT for Railway
API_DEBUG=true|false

# Supabase (Required)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_xxxxx
SUPABASE_ANON_KEY=sb_publishable_xxxxx

# Redis (Optional)
REDIS_URL=redis://host:6379
CELERY_BROKER_URL=redis://host:6379/0
CELERY_RESULT_BACKEND=redis://host:6379/0

# Security
API_KEY_REQUIRED=true|false
API_KEY=your-api-key
CORS_ORIGINS=["*"]

# Agent Endpoints
ZOE_ENDPOINT=http://agent-url/zoe
EDDIE_ENDPOINT=http://agent-url/eddie

# Performance
MAX_CONCURRENT_EXECUTIONS=10
EXECUTION_TIMEOUT=300
HEALTH_CHECK_INTERVAL=30

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
```

## Development Workflow

1. **Local Development**
   - Use `DEV_MODE=true` for in-memory storage
   - No external dependencies required
   - Hot reload with `API_DEBUG=true`

2. **Database Development**
   - Set `DEV_MODE=false`
   - Configure `DATABASE_URL`
   - Run migrations with Alembic

3. **Testing**
   - Run `test_integration.py` for full system test
   - Use `test_startup.py` to verify imports
   - Check `/health` endpoint

4. **Deployment**
   - Push to main branch
   - Railway auto-deploys
   - Monitor logs in Railway dashboard

## Import Convention

All imports use absolute paths with `src` prefix:

```python
# Correct
from src.core.models import ExecutionRequest
from src.api.agents import router
from src.core.orchestrator import orchestrator

# Incorrect (don't use)
from .models import ExecutionRequest
from ..core.models import ExecutionRequest
from core.models import ExecutionRequest  # Missing src prefix
```

## Authentication System

### Multi-tenant Architecture

The API uses a two-tier authentication system:

1. **Master Key** - For admin operations (creating users, managing system)
   - Set via `API_KEY` environment variable
   - Required for `/api/v1/users/*` endpoints
   - Used by your website backend

2. **User API Keys** - For end users
   - Generated when creating users via master key
   - Format: `sk_[random_string]`
   - Tracks usage, credits, and rate limits
   - Stored in `users` table in database

### Usage Examples

```python
# Admin creating a user
headers = {"Authorization": f"Bearer {MASTER_KEY}"}
response = requests.post("/api/v1/users/create", 
    headers=headers,
    json={"email": "user@example.com", "credits": 1000})
user_api_key = response.json()["api_key"]

# User making requests
headers = {"Authorization": f"Bearer {user_api_key}"}
response = requests.post("/api/v1/flows/execute",
    headers=headers,
    json={"flow_id": "credit_analysis", "input_data": {...}})
```

### Database Tables (Supabase)

- **api_users** - User accounts with API keys, credits, limits
- **usage_logs** - Tracks all API calls for analytics and billing
- **agents** - Registered agents with metadata
- **flows** - Flow definitions and ownership
- **execution_contexts** - Execution history and status
- **node_results** - Individual node execution results
- **agent_messages** - Inter-agent communication logs

## Common Tasks

### Adding a New Agent
1. Implement agent following `docs/agent_spec.md`
2. Add endpoint to `.env.local`
3. Register via API or startup code

### Creating a New Flow
1. Create YAML file in `flows/`
2. Define nodes and dependencies
3. Test with `POST /flows/execute`

### Debugging
- Check JSON logs
- Monitor `/status` endpoint
- Review `/metrics`
- Check execution messages

## Error Handling

- Structured error responses
- Automatic retries
- Graceful degradation
- Comprehensive logging

## Performance

- Async I/O throughout
- Connection pooling
- Configurable limits
- Redis caching (optional)

## Security

- API key authentication (optional)
- CORS configuration
- Environment-based secrets
- No hardcoded credentials

## Current State & Known Issues

### ✅ What Works
- Basic API with health checks
- Multi-tenant authentication (master key + user keys)
- Agent registration and listing
- Flow creation and listing
- Supabase persistence

### ⚠️ Known Issues
1. **NO PARALLELIZATION** - All nodes execute sequentially
2. **Marketplace is MOCK** - Returns hardcoded data
3. **Execution Error** - `'UserInfo' object is not subscriptable` when executing flows
4. **Mixed Auth Systems** - Both Supabase JWT and API keys used inconsistently
5. **No Webhooks/SSE** - No real-time updates implemented
6. **No Retry Logic** - Flows fail completely if any node fails
7. **No Circuit Breaker** - No protection against failing agents

### 🔧 Troubleshooting

1. **Import errors**: Ensure project root is in Python path
2. **Supabase connection**: Check `SUPABASE_URL` and keys
3. **Port conflicts**: Change `API_PORT` in `.env.local`
4. **Agent unreachable**: Verify agent endpoints
5. **Execution fails**: Check agent health and endpoint availability

### Railway Specific

1. **Build fails**: Check `requirements.txt`
2. **App crashes**: Check environment variables
3. **Database issues**: Ensure Supabase keys are set
4. **Port binding**: Use `PORT` environment variable