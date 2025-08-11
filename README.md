# AI Spine - Multi-Agent Infrastructure

Infraestructura completa para sistemas multiagente coordinados, flexibles, trazables y escalables.

## 🎯 Objetivo

AI Spine es una infraestructura que permite que múltiples agentes especializados trabajen juntos de forma coordinada. En lugar de programar agentes individuales, proporciona el **sistema de orquestación** que los conecta y coordina.

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway  │    │   Orchestrator  │    │   Agent Registry│
│   (FastAPI)    │◄──►│   (Flow Engine) │◄──►│   (Dynamic)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Monitoring    │    │   Communication │    │   Memory Store  │
│   (Logs/Metrics)│    │   (Redis/Celery)│    │   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## ✨ Características

- **🔄 Orquestación de Flujos**: Define flujos como DAGs (grafos acíclicos dirigidos)
- **📋 Registro Dinámico**: Agrega/quita agentes sin reiniciar el sistema
- **💬 Comunicación Desacoplada**: Mensajería entre agentes vía Redis/Celery
- **💾 Persistencia Robusta**: Almacenamiento en PostgreSQL + cache en Redis
- **📊 Observabilidad**: Logs estructurados, métricas y trazabilidad completa
- **🔌 API REST**: Interfaz completa para gestión y monitoreo
- **⚡ Escalabilidad**: Arquitectura modular y extensible

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
cp config.env.example config.env
# Editar config.env con tus configuraciones
```

### 4. Iniciar la Infraestructura

```bash
python start.py
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
ai_spine/
├── core/                    # Núcleo de la infraestructura
│   ├── orchestrator/       # Motor de orquestación
│   ├── registry/          # Registro dinámico de agentes
│   ├── communication/     # Sistema de mensajería
│   └── memory/           # Persistencia y memoria
├── flows/                 # Definiciones de flujos (YAML)
├── agents/               # Agentes existentes
├── api/                  # API REST
├── monitoring/           # Observabilidad
└── config/              # Configuraciones
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

### Flujos
- `POST /flows/execute` - Ejecutar un flujo
- `GET /flows` - Listar flujos disponibles
- `GET /flows/{flow_id}` - Obtener flujo específico

### Agentes
- `GET /agents` - Listar agentes registrados
- `POST /agents` - Registrar nuevo agente
- `DELETE /agents/{agent_id}` - Desregistrar agente

### Ejecuciones
- `GET /executions/{execution_id}` - Estado de ejecución
- `POST /executions/{execution_id}/cancel` - Cancelar ejecución

### Monitoreo
- `GET /health` - Health check
- `GET /metrics` - Métricas del sistema
- `GET /status` - Estado general

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

### Variables de Entorno Principales

```bash
# Base de datos
DATABASE_URL=postgresql://user:pass@localhost/ai_spine

# Redis
REDIS_URL=redis://localhost:6379

# API
API_HOST=0.0.0.0
API_PORT=8000

# Agentes
ZOE_ENDPOINT=http://localhost:8001/zoe
EDDIE_ENDPOINT=http://localhost:8002/eddie
```

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

## 🚀 Roadmap

- [ ] Dashboard web con visualización de flujos
- [ ] WebSockets para actualizaciones en tiempo real
- [ ] Autenticación y autorización
- [ ] Integración con LangGraph
- [ ] Soporte para agentes con memoria
- [ ] Métricas avanzadas (Prometheus/Grafana)
- [ ] Despliegue con Docker/Kubernetes

## 🤝 Contribuir

1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para detalles.

---

**AI Spine** - Infraestructura para el futuro de los sistemas multiagente 🤖✨ 