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
│   │   ├── main.py       # Main FastAPI application with core endpoints
│   │   ├── agents.py     # Agent management endpoints (/api/v1/agents)
│   │   ├── flows.py      # Flow management endpoints (/api/v1/flows)
│   │   ├── executions.py # Execution monitoring endpoints (/api/v1/executions)
│   │   ├── users.py      # User management endpoints (/api/v1/users)
│   │   ├── user_keys.py  # Legacy user key management
│   │   ├── user_keys_secure.py # JWT-based user account management
│   │   └── marketplace_simple.py # Marketplace endpoints (/api/v1/marketplace)
│   └── core/              # Core business logic
│       ├── orchestrator.py # Flow execution engine with DAG validation
│       ├── registry.py    # Agent registry with health checks and DB persistence
│       ├── communication.py # Inter-agent messaging (Redis/Celery)
│       ├── memory.py      # Hybrid persistence layer (in-memory + Supabase)
│       ├── auth.py        # Multi-tier authentication (master + user API keys)
│       ├── user_auth_supabase.py # Supabase-based user authentication
│       ├── supabase_auth.py # Supabase auth integration
│       ├── supabase_client.py # Supabase client wrapper
│       └── models.py      # Pydantic data models (no SQLAlchemy)
├── flows/                  # Flow definitions (YAML)
│   ├── credit_analysis.yaml
│   └── credit_analysis_with_system_prompt.yaml
├── docs/                  # Documentation
│   └── agent_spec.md     # Agent HTTP contract specification
├── examples/              # Example scripts
│   └── demo_credit_analysis.py
├── .env.local            # Local environment config
├── .env.local.example    # Example config
├── requirements.txt      # Python dependencies
├── main.py              # Single entry point
├── start.py            # Legacy start script
├── railway.json         # Railway deployment config
├── Dockerfile          # Container configuration
├── test_integration.py  # Integration tests
├── test_startup.py     # Startup tests
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

# Or use the legacy start script
python start.py
```

### Database Operations

```bash
# Initialize database (production mode)
python setup_database.py

# Run migrations
alembic upgrade head

# Create new migration
alembic revision -m "description"
```

### Testing

```bash
# Run integration tests
python test_integration.py

# Test startup sequence
python test_startup.py

# Run demo
python examples/demo_credit_analysis.py
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

1. **Main Application** (`src/api/main.py`)
   - FastAPI application with CORS middleware
   - Structured logging with JSON output
   - Startup/shutdown event handling
   - Router integration for modular endpoints
   - Health check and system status endpoints

2. **Orchestrator** (`src/core/orchestrator.py`)
   - DAG-based workflow execution engine
   - NetworkX for graph validation and dependency management
   - Async execution with timeout and cancellation support
   - Flow definition loading from YAML files
   - Node result tracking and execution context management

3. **Agent Registry** (`src/core/registry.py`)
   - Dynamic agent registration with database persistence
   - Automatic health checking with configurable intervals
   - Capability indexing for efficient agent discovery
   - Agent loading from database on startup
   - User-scoped agent management

4. **Memory Store** (`src/core/memory.py`)
   - Hybrid persistence: in-memory (dev) + Supabase (production)
   - Execution context and message storage
   - Metrics collection and system monitoring
   - Lazy database initialization

5. **Communication** (`src/core/communication.py`)
   - Async inter-agent message passing
   - Redis/Celery integration for distributed messaging
   - Event-driven architecture support

6. **Authentication System**
   - **Multi-tier Auth** (`src/core/auth.py`): Master API key + user API keys
   - **Supabase Integration** (`src/core/supabase_auth.py`): JWT-based user authentication
   - **User Management** (`src/core/user_auth_supabase.py`): Account creation and management
   - Rate limiting, credit tracking, and usage analytics

7. **Data Models** (`src/core/models.py`)
   - Pydantic models for request/response validation
   - No SQLAlchemy dependencies - pure Supabase integration
   - Comprehensive type definitions for all API endpoints
   - Enum definitions for agent types, capabilities, and execution status

### API Endpoints

#### Core
- `GET /health` - Health check
- `GET /status` - System status
- `GET /metrics` - Prometheus metrics
- `GET /docs` - Swagger documentation

#### Agents
- `GET /api/v1/agents` - List agents (system + user's own agents if authenticated)
- `GET /api/v1/agents/my-agents` - Get authenticated user's agents only
- `GET /api/v1/agents/active` - List all active agents
- `GET /api/v1/agents/{agent_id}` - Get specific agent details
- `POST /api/v1/agents` - Register new agent (requires authentication)
- `DELETE /api/v1/agents/{agent_id}` - Unregister agent

#### Flows
- `GET /api/v1/flows` - List all available flows
- `GET /api/v1/flows/{flow_id}` - Get specific flow details
- `POST /api/v1/flows` - Create new flow definition
- `PUT /api/v1/flows/{flow_id}` - Update existing flow
- `DELETE /api/v1/flows/{flow_id}` - Delete flow
- `POST /api/v1/flows/execute` - Execute flow with input data

#### Executions
- `GET /api/v1/executions/{execution_id}` - Get execution status and context
- `GET /api/v1/executions` - List executions with optional filtering
- `GET /api/v1/executions/{execution_id}/results` - Get detailed node execution results
- `POST /api/v1/executions/{execution_id}/cancel` - Cancel running execution
- `GET /api/v1/messages/{execution_id}` - Get execution messages

#### Users (Master Key Required)
- `POST /api/v1/users/create` - Create new user with API key
- `GET /api/v1/users/me` - Get current user info
- `POST /api/v1/users/regenerate-key` - Regenerate user's API key
- `POST /api/v1/users/add-credits` - Add credits to user account
- `GET /api/v1/users/{id}` - Get user by ID

#### User Account Management (JWT)
- `POST /api/v1/user-account/register` - Register new user account
- `POST /api/v1/user-account/login` - Login user and get JWT token
- `GET /api/v1/user-account/profile` - Get user profile
- `PUT /api/v1/user-account/profile` - Update user profile

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

All agents must implement the universal HTTP contract (see `docs/agent_spec.md`):

#### Health Check Endpoint
```http
GET /health
Authorization: Bearer <api_key>

Response:
{
  "agent_id": "string",
  "version": "string",
  "capabilities": ["conversation", "credit_analysis"],
  "ready": true,
  "endpoint": "https://agent.com/execute",
  "agent_type": "input|processor|output|conditional"
}
```

#### Execution Endpoint
```http
POST /execute
Authorization: Bearer <api_key>
Content-Type: application/json

Request:
{
  "execution_id": "uuid",
  "node_id": "string",
  "input": {...},
  "config": {
    "system_prompt": "optional",
    "timeout": 30,
    "max_retries": 3
  }
}

Response:
{
  "status": "success|error",
  "output": {...},
  "execution_id": "uuid",
  "error_message": "string (if error)",
  "execution_time_ms": 1500
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

# Database (Production)
DATABASE_URL=postgresql://user:pass@host/db

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

The API implements a sophisticated multi-tier authentication system:

#### 1. **Master Key Authentication**
- Set via `API_KEY` environment variable
- Required for administrative operations:
  - Creating/managing user accounts
  - System-level agent registration
  - Global system metrics and monitoring
- Used by your backend application to manage user lifecycle

#### 2. **User API Keys** (Legacy System)
- Generated when creating users via master key
- Format: `sk_[random_string]`
- Stored in Supabase `api_users` table
- Tracks usage, credits, and rate limits per user
- Supports user-scoped agent registration and management

#### 3. **JWT-based Authentication** (New System)
- Modern authentication via `/api/v1/user-account/` endpoints
- JWT tokens for secure session management
- Supabase Auth integration for scalable user management
- Profile management and secure credential handling

#### Agent Ownership Model
- **System Agents**: No `created_by` field, visible to all users
- **User Agents**: Associated with specific user IDs, only visible to owner
- Anonymous users see only system agents
- Authenticated users see system agents + their own agents

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

### Database Tables

- **users** - Stores user accounts with API keys, credits, limits
- **usage_logs** - Tracks all API calls for analytics and billing

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

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure project root is in Python path
2. **Database connection**: Check `DATABASE_URL` format
3. **Port conflicts**: Change `API_PORT` in `.env.local`
4. **Agent unreachable**: Verify agent endpoints

### Railway Deployment Troubleshooting

1. **Build failures**: 
   - Verify `requirements.txt` includes all dependencies
   - Check Python version compatibility
   - Ensure `main.py` exists as entry point

2. **Runtime crashes**:
   - Set required environment variables:
     ```bash
     DEV_MODE=false
     DATABASE_URL=${PGDATABASE_URL}  # Railway auto-provides
     API_HOST=0.0.0.0
     PORT=${PORT}  # Railway auto-provides
     ```
   - Check Supabase connection if using database features
   - Verify API_KEY is set for authentication

3. **Database connection issues**:
   - Ensure Supabase project is configured
   - Check `DATABASE_URL` format: `postgresql://user:pass@host/db`
   - Verify network connectivity to Supabase

4. **Authentication problems**:
   - Set `API_KEY_REQUIRED=true` for production
   - Generate secure `API_KEY` for master operations
   - Test endpoints with proper Bearer tokens

## Current Implementation Status

### ✅ Completed Features
- **Multi-tenant Authentication**: Master key + user API keys + JWT support
- **Agent Registry**: Dynamic registration with health checks and user ownership
- **Flow Execution**: DAG-based orchestration with NetworkX validation
- **Database Integration**: Supabase with hybrid in-memory fallback
- **API Endpoints**: Complete REST API with structured logging
- **Error Handling**: Comprehensive error boundaries and HTTP exception handling
- **Development Tools**: Integration tests, startup validation, demo scripts
- **Deployment**: Railway-ready with Docker support

### 🚧 Current Architecture Highlights
- **Hybrid Storage**: In-memory development mode + Supabase production persistence
- **Multi-auth Support**: Backwards-compatible legacy keys + modern JWT tokens
- **User-scoped Resources**: Agents and executions tied to specific users
- **Health Monitoring**: Automatic agent health checking with configurable intervals
- **Structured Logging**: JSON logs with execution context and correlation IDs

The system is **production-ready** with a robust, scalable architecture suitable for multi-tenant SaaS deployment.