# AI Spine - Multi-Agent Infrastructure

Infraestructura completa para sistemas multiagente coordinados, flexibles, trazables y escalables.

## 🎯 Objetivo

AI Spine es una infraestructura que permite que múltiples agentes especializados trabajen juntos de forma coordinada. En lugar de programar agentes individuales, proporciona el **sistema de orquestación** que los conecta y coordina.

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │   Orchestrator  │    │   Agent Registry│
│   (main.py)     │◄──►│   (DAG Engine)  │◄──►│   (Multi-user)  │
│   + Routers     │    │   + NetworkX    │    │   + Health Check│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Multi-Auth    │    │   Memory Store  │    │   Supabase DB   │
│   Master+User   │    │   (Hybrid)      │    │   (Production)  │
│   JWT Support   │    │   In-mem + DB   │    │   + Auth        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## ✨ Características Clave

- **🔄 Orquestación DAG**: Flujos como grafos dirigidos con NetworkX para validación
- **👥 Multi-tenancy**: Usuarios con API keys, créditos, y agentes privados
- **📋 Registro Dinámico**: Agentes con health checks automáticos cada 30s
- **💾 Almacenamiento Híbrido**: In-memory (dev) + Supabase (producción)
- **🔐 Autenticación Triple**: Master key + User API keys + JWT tokens
- **📊 Observabilidad**: Logs JSON estructurados con contexto de ejecución
- **🔌 API REST Completa**: Endpoints versioned con /api/v1/ prefix
- **🏗️ Modular**: Routers separados por funcionalidad (agents, flows, users)
- **⚡ Async**: FastAPI completamente asíncrono con manejo de errores robusto
- **🚀 Railway-ready**: Configuración lista para deploy en Railway

## 🚀 Quick Start

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar Base de Datos

```bash
# PostgreSQL
createdb ai_spine

# Redis (opcional, para desarrollo)
redis-server
```

### 3. Configurar Variables de Entorno

```bash
cp .env.local.example .env.local
# Editar .env.local con tus configuraciones
```

### 4. Iniciar la Infraestructura

```bash
python main.py
```

### 5. Verificar Funcionamiento

```bash
# Health check
curl http://localhost:8000/health

# Documentación API
open http://localhost:8000/docs
```

## 📁 Estructura del Proyecto

```
ai-spine-api/
├── src/
│   ├── api/                   # API endpoints y routers
│   │   ├── main.py           # FastAPI app principal + core endpoints
│   │   ├── agents.py         # Gestión de agentes multi-usuario
│   │   ├── flows.py          # Gestión de flujos y ejecución
│   │   ├── executions.py     # Monitoreo de ejecuciones
│   │   ├── users.py          # Gestión de usuarios (master key)
│   │   └── user_keys*.py     # Auth de usuarios (legacy + JWT)
│   └── core/                  # Lógica de negocio central
│       ├── orchestrator.py   # Motor DAG con NetworkX
│       ├── registry.py       # Registro con health checks
│       ├── memory.py         # Storage híbrido (mem + Supabase)
│       ├── auth.py           # Sistema multi-auth
│       ├── models.py         # Modelos Pydantic (sin SQLAlchemy)
│       └── supabase_*.py     # Integración Supabase
├── flows/                     # Definiciones YAML
├── docs/
│   └── agent_spec.md         # Contrato HTTP para agentes
├── examples/
│   └── demo_credit_analysis.py
├── main.py                   # Entry point único
├── requirements.txt          # Dependencias Python
└── railway.json             # Config deployment
```

## 🔄 Flujos

Los flujos se definen en YAML:

```yaml
# flows/credit_analysis.yaml
flow_id: credit_analysis
name: "Análisis de Crédito"
description: "Zoe recolecta info → Eddie analiza → Resultado"

nodes:
  - id: zoe
    agent_id: zoe
    type: input
    config:
      max_turns: 5

  - id: eddie
    agent_id: eddie
    type: processor
    depends_on: [zoe]
    config:
      timeout: 30

  - id: result
    type: output
    depends_on: [eddie]
```

## 🤖 Agentes

Los agentes se registran dinámicamente:

```python
# Registrar un agente
registry.register_agent(
    agent_id="zoe",
    name="Zoe Assistant",
    description="Asistente conversacional",
    endpoint="http://localhost:8001/zoe",
    capabilities=["conversation", "information_gathering"],
    agent_type="input"
)
```

## 📊 API Endpoints

### 🔐 Usuarios y Autenticación
**Master Key requerida para gestión de usuarios:**
- `POST /api/v1/users/create` - Crear usuario con API key
- `GET /api/v1/users/me` - Info del usuario actual
- `POST /api/v1/users/regenerate-key` - Regenerar API key
- `POST /api/v1/users/add-credits` - Añadir créditos

**JWT Authentication (moderno):**
- `POST /api/v1/user-account/register` - Registro con JWT
- `POST /api/v1/user-account/login` - Login y obtener token
- `GET /api/v1/user-account/profile` - Perfil del usuario

### 🤖 Agentes (Multi-usuario)
- `GET /api/v1/agents` - Agentes del sistema + propios (si auth)
- `GET /api/v1/agents/my-agents` - Solo agentes del usuario
- `GET /api/v1/agents/active` - Agentes activos
- `GET /api/v1/agents/{agent_id}` - Detalles de agente específico
- `POST /api/v1/agents` - Registrar agente (requiere auth)
- `DELETE /api/v1/agents/{agent_id}` - Desregistrar agente

### 🔄 Flujos y Ejecución
- `GET /api/v1/flows` - Listar flujos disponibles
- `GET /api/v1/flows/{flow_id}` - Detalles de flujo
- `POST /api/v1/flows` - Crear nuevo flujo
- `PUT /api/v1/flows/{flow_id}` - Actualizar flujo
- `DELETE /api/v1/flows/{flow_id}` - Eliminar flujo
- `POST /api/v1/flows/execute` - Ejecutar flujo con input

### 📈 Monitoreo y Ejecuciones
- `GET /api/v1/executions/{execution_id}` - Estado y contexto
- `GET /api/v1/executions` - Lista con filtros opcionales
- `GET /api/v1/executions/{id}/results` - Resultados detallados
- `POST /api/v1/executions/{id}/cancel` - Cancelar ejecución
- `GET /api/v1/messages/{execution_id}` - Mensajes de ejecución

### 🔍 Sistema
- `GET /health` - Health check básico
- `GET /status` - Estado completo del sistema
- `GET /metrics` - Métricas de ejecución
- `GET /docs` - Documentación Swagger automática

## 🧪 Demo

Ejecuta el script de demostración:

```bash
python examples/demo_credit_analysis.py
```

Este script:
1. Verifica la salud del sistema
2. Lista flujos y agentes disponibles
3. Ejecuta el flujo de análisis de crédito
4. Monitorea la ejecución
5. Muestra resultados

## 🔧 Configuración

### Variables de Entorno Clave

```bash
# === MODO DE OPERACIÓN ===
DEV_MODE=false  # true = in-memory, false = Supabase

# === BASE DE DATOS ===
DATABASE_URL=postgresql://user:pass@host/db  # Supabase/Neon/Railway
# Railway auto-provee: DATABASE_URL=${PGDATABASE_URL}

# === AUTENTICACIÓN ===
API_KEY_REQUIRED=true
API_KEY=master-key-ultra-secreta  # Para operaciones admin

# === API CONFIGURATION ===
API_HOST=0.0.0.0
PORT=8000  # Railway auto-provee ${PORT}
API_DEBUG=false  # true para desarrollo

# === REDIS (Opcional) ===
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://host:6379/0

# === ENDPOINTS DE AGENTES ===
ZOE_ENDPOINT=http://localhost:8001/zoe
EDDIE_ENDPOINT=http://localhost:8002/eddie

# === CORS (Desarrollo) ===
CORS_ORIGINS=["http://localhost:3000","https://tu-frontend.com"]
```

### Configuración para Railway

```bash
# railway.json automáticamente usa:
DEV_MODE=false
DATABASE_URL=${PGDATABASE_URL}
PORT=${PORT}
API_HOST=0.0.0.0

# Solo necesitas configurar:
API_KEY=tu-master-key-secreta
API_KEY_REQUIRED=true
```

## 🔐 Sistema de Autenticación Multi-tenant

### Arquitectura de Autenticación Triple

AI Spine implementa un sistema sofisticado con tres niveles:

#### 1. **Master Key** (Administración)
```bash
# Variable de entorno
API_KEY=tu-master-key-super-secreta
```
Usada por tu backend para:
- Crear/gestionar usuarios
- Operaciones administrativas
- Acceso completo al sistema

#### 2. **User API Keys** (Legacy)
```python
# Crear usuario (desde tu backend con Master Key)
headers = {"Authorization": f"Bearer {MASTER_KEY}"}
response = requests.post("/api/v1/users/create", headers=headers, json={
    "email": "user@example.com",
    "name": "John Doe",
    "organization": "Acme Corp",
    "credits": 1000
})
user_api_key = response.json()["api_key"]  # sk_...
```

#### 3. **JWT Tokens** (Moderno)
```python
# Usuario se registra directamente
response = requests.post("/api/v1/user-account/register", json={
    "email": "user@example.com",
    "password": "secure_password"
})

# Login para obtener JWT
auth_response = requests.post("/api/v1/user-account/login", json={
    "email": "user@example.com",
    "password": "secure_password"
})
jwt_token = auth_response.json()["access_token"]
```

### Uso de la API

#### Registrar Agente (Usuario)
```python
headers = {"Authorization": f"Bearer {user_api_key}"}
response = requests.post("/api/v1/agents", headers=headers, json={
    "agent_id": "my_custom_agent",
    "name": "My Analysis Agent",
    "endpoint": "https://my-agent.com/execute",
    "capabilities": ["analysis", "reporting"],
    "agent_type": "processor"
})
```

#### Ejecutar Flujo
```python
headers = {"Authorization": f"Bearer {user_api_key}"}
response = requests.post("/api/v1/flows/execute", headers=headers, json={
    "flow_id": "credit_analysis",
    "input_data": {
        "customer_data": {"income": 50000, "age": 30},
        "loan_amount": 25000
    }
})
execution = response.json()
print(f"Execution ID: {execution['execution_id']}")
```

### Modelo de Propiedad
- **Agentes del Sistema**: Visibles para todos (created_by = null)
- **Agentes de Usuario**: Solo visibles para el propietario
- **Filtrado Automático**: La API filtra automáticamente por usuario
- **Créditos y Límites**: Tracking automático de uso por usuario

## 🔄 Extensibilidad

### Agregar Nuevo Agente

1. **Implementar el agente** (servicio independiente)
2. **Registrar en el sistema**:
   ```python
   registry.register_agent(
       agent_id="nuevo_agente",
       name="Mi Nuevo Agente",
       endpoint="http://localhost:8003/nuevo_agente",
       capabilities=["mi_capacidad"],
       agent_type="processor"
   )
   ```

### Crear Nuevo Flujo

1. **Definir en YAML** (`flows/mi_flujo.yaml`)
2. **El sistema lo carga automáticamente**
3. **Ejecutar vía API**:
   ```bash
   curl -X POST http://localhost:8000/flows/execute \
     -H "Content-Type: application/json" \
     -d '{"flow_id": "mi_flujo", "input_data": {...}}'
   ```

## 📈 Monitoreo

### Logs Estructurados

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "execution_id": "uuid",
  "node_id": "zoe",
  "message": "Node execution started"
}
```

### Métricas Disponibles

- Total de ejecuciones
- Tiempo promedio de ejecución
- Tasa de éxito/fallo
- Agentes activos
- Uso de recursos

## 🛠️ Desarrollo

### Estructura de Datos

```python
# Ejecución
ExecutionContext(
    execution_id=UUID,
    flow_id="credit_analysis",
    status=ExecutionStatus.RUNNING,
    input_data={...},
    output_data={...}
)

# Mensaje entre agentes
AgentMessage(
    execution_id=UUID,
    from_agent="zoe",
    to_agent="eddie",
    payload={...}
)
```

### Patrones de Diseño

- **Registry Pattern**: Registro dinámico de agentes
- **Observer Pattern**: Monitoreo de ejecuciones
- **Factory Pattern**: Creación de flujos
- **Strategy Pattern**: Diferentes tipos de agentes

## 🚀 Estado Actual y Roadmap

### ✅ Completado (Agosto 2025)
- ✅ **Sistema Multi-tenant**: Master key + User API keys + JWT
- ✅ **Registro de Agentes**: Con health checks y propiedad por usuario
- ✅ **Ejecución DAG**: NetworkX para validación y orquestación
- ✅ **Base de Datos**: Integración Supabase con fallback in-memory
- ✅ **API Completa**: Endpoints versioned con documentación Swagger
- ✅ **Error Handling**: Manejo robusto con logs estructurados JSON
- ✅ **Railway Deploy**: Configuración lista para producción
- ✅ **Testing**: Scripts de integración y validación de startup

### 🚧 En Desarrollo
- 🔄 **Dashboard Web**: Visualización de flujos y monitoreo en tiempo real
- 🔄 **WebSockets**: Updates live de ejecuciones
- 🔄 **Métricas Avanzadas**: Prometheus/Grafana integration

### 📋 Roadmap Próximo
- **Q3 2025**:
  - [ ] Nodos condicionales y loops en flujos
  - [ ] Cache de resultados para optimización
  - [ ] Rate limiting por usuario
  - [ ] Audit logs completos
- **Q4 2025**:
  - [ ] Marketplace de agentes con ratings
  - [ ] SDK oficial de JavaScript/Python
  - [ ] Integración LangGraph/LangChain
  - [ ] Soporte multi-región

### 🎯 Características Técnicas Destacadas
- **Hybrid Storage**: Desarrollo sin BD, producción con Supabase
- **Multi-Auth**: Tres niveles de autenticación simultáneos
- **User-scoped**: Recursos aislados por usuario automáticamente
- **Health Monitoring**: Monitoreo continuo cada 30 segundos
- **Structured Logs**: Contexto completo de ejecución en JSON

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para detalles.

## 🔍 Recursos de Desarrollo

### Archivos Clave del Sistema
- **`src/api/main.py`**: Aplicación FastAPI principal con middleware
- **`src/api/agents.py`**: Gestión multi-usuario de agentes
- **`src/core/registry.py`**: Registry con health checks automáticos
- **`src/core/orchestrator.py`**: Motor DAG con NetworkX
- **`src/core/memory.py`**: Sistema híbrido de persistencia
- **`src/core/auth.py`**: Autenticación multi-nivel
- **`src/core/models.py`**: Modelos Pydantic sin SQLAlchemy

### Prueba el Sistema
```bash
# 1. Clonar y configurar
git clone <repo>
cp .env.local.example .env.local
pip install -r requirements.txt

# 2. Iniciar en modo desarrollo
DEV_MODE=true python main.py

# 3. Probar health check
curl http://localhost:8000/health

# 4. Ver documentación
open http://localhost:8000/docs

# 5. Ejecutar demo completo
python examples/demo_credit_analysis.py
```

### Contrato de Agentes
Todos los agentes deben implementar:
- `GET /health` - Health check con capabilities
- `POST /execute` - Ejecución con input/output estandarizado
- Autenticación Bearer token
- Manejo de errores HTTP

Ver especificación completa en `docs/agent_spec.md`

---

**AI Spine** - Infraestructura de producción para sistemas multiagente 🤖⚡

*Sistema completo multi-tenant con autenticación robusta, registro dinámico de agentes, y orquestación DAG. Listo para deploy en Railway.* 