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
│   │   └── marketplace*.py # Marketplace endpoints
│   └── core/              # Core business logic
│       ├── orchestrator.py # Flow execution engine
│       ├── registry.py    # Agent registry
│       ├── communication.py # Inter-agent messaging
│       ├── memory.py      # Persistence layer
│       ├── database.py    # Database management
│       ├── auth.py        # Authentication
│       └── models.py      # Data models
├── flows/                  # Flow definitions (YAML)
├── alembic/               # Database migrations
├── docs/                  # Documentation
├── examples/              # Example scripts
├── tests/                 # Test files
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

1. **Orchestrator** (`src/core/orchestrator.py`)
   - DAG-based workflow execution
   - NetworkX for graph validation
   - Async execution management

2. **Registry** (`src/core/registry.py`)
   - Dynamic agent registration
   - Health checking
   - Capability tracking

3. **Memory Store** (`src/core/memory.py`)
   - In-memory storage (dev mode)
   - PostgreSQL persistence (production)
   - Execution context management

4. **Communication** (`src/core/communication.py`)
   - Async message passing
   - Redis/Celery support
   - Event-driven architecture

5. **Database** (`src/core/database.py`)
   - SQLAlchemy async sessions
   - Connection pooling
   - Alembic migrations

6. **Auth** (`src/core/auth.py`)
   - API key authentication
   - Bearer token support
   - Optional enforcement

### API Endpoints

#### Core
- `GET /health` - Health check
- `GET /status` - System status
- `GET /metrics` - Prometheus metrics
- `GET /docs` - Swagger documentation

#### Agents
- `GET /agents` - List all agents
- `GET /agents/active` - List active agents
- `POST /agents` - Register new agent
- `DELETE /agents/{id}` - Deregister agent

#### Flows
- `GET /flows` - List all flows
- `GET /flows/{id}` - Get flow details
- `POST /flows` - Create new flow
- `POST /flows/execute` - Execute flow

#### Executions
- `GET /executions/{id}` - Get execution status
- `POST /executions/{id}/cancel` - Cancel execution
- `GET /messages/{execution_id}` - Get messages

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

### Railway Specific

1. **Build fails**: Check `requirements.txt`
2. **App crashes**: Check environment variables
3. **Database issues**: Ensure PostgreSQL addon is attached
4. **Port binding**: Use `PORT` environment variable