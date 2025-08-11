# AI Spine - Technical Design Document

## 🏗️ Arquitectura General

AI Spine es una infraestructura multiagente que proporciona orquestación, comunicación, persistencia y observabilidad para sistemas de agentes de IA. La arquitectura está diseñada para ser:

- **Modular**: Componentes independientes y reutilizables
- **Escalable**: Horizontal y verticalmente
- **Extensible**: Fácil agregar nuevos agentes y flujos
- **Observable**: Logs estructurados y métricas completas
- **Resiliente**: Manejo de errores y recuperación automática

## 📦 Componentes Core

### 1. Registry (core/registry.py)

**Responsabilidad**: Gestión dinámica de agentes

**Características**:
- Registro/desregistro dinámico de agentes
- Health checking automático
- Indexado por capacidades
- Discovery de agentes

**Interfaz principal**:
```python
class AgentRegistry:
    async def start() -> None
    def register_agent(agent_id, name, description, endpoint, capabilities, agent_type) -> AgentInfo
    def get_agent(agent_id) -> Optional[AgentInfo]
    def get_agents_by_capability(capability) -> List[AgentInfo]
    async def health_check_agent(agent_id) -> bool
```

### 2. Communication Manager (core/communication.py)

**Responsabilidad**: Comunicación entre agentes

**Características**:
- Mensajería síncrona y asíncrona
- Pub/Sub con Redis
- Colas con Celery
- Persistencia de mensajes
- Broadcast a múltiples agentes

**Interfaz principal**:
```python
class CommunicationManager:
    async def send_message(message: AgentMessage, use_async: bool = False) -> bool
    async def receive_message(agent_id: str, timeout: float = 5.0) -> Optional[AgentMessage]
    async def broadcast_message(execution_id, from_agent, payload, metadata) -> List[bool]
    async def get_message_history(execution_id, limit: int = 100) -> List[AgentMessage]
```

### 3. Memory Store (core/memory.py)

**Responsabilidad**: Persistencia y almacenamiento

**Características**:
- Cache en Redis (rápido)
- Persistencia en PostgreSQL
- Historial de ejecuciones
- Métricas y estadísticas
- Almacenamiento de mensajes

**Interfaz principal**:
```python
class MemoryStore:
    async def store_execution(context: ExecutionContext) -> bool
    async def get_execution(execution_id: UUID) -> Optional[ExecutionContext]
    async def store_message(message: AgentMessage) -> bool
    async def get_messages(execution_id: UUID, limit: int = 100) -> List[AgentMessage]
    async def get_metrics(flow_id: Optional[str] = None) -> Metrics
```

### 4. Flow Orchestrator (core/orchestrator.py)

**Responsabilidad**: Orquestación de flujos multiagente

**Características**:
- Carga de definiciones YAML
- Validación de grafos (DAG)
- Ejecución topológica
- Manejo de dependencias
- Invocación de agentes HTTP
- Monitoreo de ejecución

**Interfaz principal**:
```python
class FlowOrchestrator:
    async def execute_flow(request: ExecutionRequest) -> ExecutionResponse
    async def get_execution_status(execution_id: UUID) -> Optional[ExecutionContext]
    async def cancel_execution(execution_id: UUID) -> bool
    def get_available_flows() -> List[Dict[str, Any]]
```

## 🔄 Flujo de Datos

### 1. Inicio de Ejecución

```
Usuario → API → Orchestrator → Registry → Memory Store
```

1. **Usuario** hace request a `/flows/execute`
2. **API** valida request y crea `ExecutionContext`
3. **Orchestrator** carga definición de flujo
4. **Registry** verifica agentes disponibles
5. **Memory Store** persiste contexto inicial

### 2. Ejecución de Nodos

```
Orchestrator → Agent Invocation → Communication → Memory Store
```

1. **Orchestrator** determina orden de ejecución (topológico)
2. **Agent Invocation** llama agente vía HTTP
3. **Communication** maneja mensajes entre agentes
4. **Memory Store** persiste resultados

### 3. Finalización

```
Orchestrator → Memory Store → API → Usuario
```

1. **Orchestrator** actualiza estado final
2. **Memory Store** persiste resultado completo
3. **API** retorna respuesta al usuario

## 📊 Modelos de Datos

### ExecutionContext
```python
class ExecutionContext:
    execution_id: UUID
    flow_id: str
    status: ExecutionStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    node_results: Dict[str, Any]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
```

### AgentMessage
```python
class AgentMessage:
    message_id: UUID
    execution_id: UUID
    from_agent: str
    to_agent: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
```

### FlowDefinition
```python
class FlowDefinition:
    flow_id: str
    name: str
    description: str
    version: str
    nodes: List[FlowNode]
    entry_point: str
    exit_points: List[str]
    metadata: Dict[str, Any]
```

## 🔧 Configuración de Agentes

### Registro de Agente
```python
registry.register_agent(
    agent_id="zoe",
    name="Zoe Assistant",
    description="Conversational assistant",
    endpoint="http://localhost:8001/zoe",
    capabilities=["conversation", "information_gathering"],
    agent_type="input"
)
```

### Interfaz de Agente
Los agentes deben exponer un endpoint HTTP con:

**POST /process**
```json
{
  "input": {
    "user_query": "...",
    "context": {...}
  },
  "config": {
    "timeout": 30,
    "max_turns": 5
  }
}
```

**Response:**
```json
{
  "output": {
    "response": "...",
    "collected_data": {...},
    "status": "completed"
  }
}
```

## 📈 Observabilidad

### Logs Estructurados
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info",
  "logger": "core.orchestrator",
  "execution_id": "uuid-here",
  "node_id": "zoe",
  "message": "Node execution completed",
  "execution_time": 2.5
}
```

### Métricas
- Tiempo de ejecución por agente
- Tasa de éxito/fallo
- Throughput de mensajes
- Uso de recursos
- Latencia de comunicación

### Endpoints de Monitoreo
- `/monitoring/stats` - Estadísticas del sistema
- `/monitoring/executions` - Métricas de ejecución
- `/executions/{id}/messages` - Mensajes de ejecución

## 🚀 Escalabilidad

### Escalado Horizontal
- Múltiples instancias del orquestador
- Load balancing de agentes
- Particionamiento de flujos

### Escalado Vertical
- Agentes pueden escalar independientemente
- Cache distribuido con Redis
- Base de datos optimizada

### Patrones de Resiliencia
- Circuit breaker para agentes
- Retry automático con backoff
- Fallback a agentes alternativos
- Timeout configurables

## 🔒 Seguridad

### Autenticación
- API keys para agentes
- JWT para usuarios
- Rate limiting

### Autorización
- Roles por agente
- Permisos por flujo
- Auditoría de acciones

### Encriptación
- TLS para comunicación
- Encriptación de datos sensibles
- Hashing de credenciales

## 🛠️ Extensibilidad

### Nuevos Tipos de Agentes
1. Implementar interfaz HTTP
2. Registrar en registry
3. Definir capacidades
4. Crear flujos que lo usen

### Nuevos Tipos de Comunicación
1. Extender `CommunicationManager`
2. Implementar protocolo específico
3. Configurar en agentes

### Nuevos Stores
1. Implementar interfaz `MemoryStore`
2. Configurar en orquestador
3. Migrar datos existentes

## 📋 Roadmap

### Fase 1 (Actual)
- ✅ Orquestación básica
- ✅ Comunicación HTTP/Redis
- ✅ Persistencia PostgreSQL
- ✅ API REST

### Fase 2
- 🔄 Dashboard web
- 🔄 WebSocket para tiempo real
- 🔄 Retry automático
- 🔄 Métricas avanzadas

### Fase 3
- 📋 Kubernetes deployment
- 📋 Service mesh
- 📋 ML pipeline integration
- 📋 Advanced security

### Fase 4
- 📋 Edge computing
- 📋 Federated learning
- 📋 Blockchain integration
- 📋 Quantum computing prep

## 🧪 Testing

### Unit Tests
```bash
pytest tests/unit/
```

### Integration Tests
```bash
pytest tests/integration/
```

### Load Tests
```bash
pytest tests/load/
```

### E2E Tests
```bash
pytest tests/e2e/
```

## 📚 Referencias

- [LangGraph](https://github.com/langchain-ai/langgraph) - Inspiración para orquestación
- [Celery](https://celeryproject.org/) - Task queue para async
- [FastAPI](https://fastapi.tiangolo.com/) - API framework
- [Redis](https://redis.io/) - Cache y pub/sub
- [PostgreSQL](https://www.postgresql.org/) - Base de datos principal 