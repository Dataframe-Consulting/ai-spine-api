# Diseño de Base de Datos para Sistema de Agentes AI

## Análisis del Formulario AgentEditorForm

Basado en el análisis del formulario `AgentEditorForm.tsx` y sus componentes, se ha identificado la siguiente estructura de datos:

### Estructura de Datos del Formulario

```typescript
interface AgentFormData {
  // Información Básica
  agent_id: string;              // ID único (validación: /^[a-z0-9-]+$/, 3-50 chars)
  name: string;                  // Nombre del agente (3-100 characters)
  description: string;           // Descripción (10-500 characters)
  agent_type: 'custom' | 'system'; // Tipo de agente

  // Configuración del Modelo LLM
  model: string;                 // Modelo de IA (requerido, de lista predefinida)
  system_prompt: string;         // Prompt del sistema (50-10000 characters)
  temperature: number;           // Temperatura calculada (0.1-2.0)
  max_tokens: number;           // Tokens máximos calculados (100-4000)
  max_turns: number;            // Turnos máximos (5-100)
  timeout: number;              // Timeout en segundos (30-300)
  enable_memory: boolean;        // Habilitar memoria

  // Herramientas y Configuración
  available_tools: string[];     // Array de tool_ids
  tool_configurations: {        // Configuraciones por herramienta
    [tool_id: string]: {
      [property_name: string]: {
        value: any;
        is_encrypted: boolean;
      }
    }
  };
  llm_api_key: string;          // Clave API del LLM (requerido)
}
```

## Diseño de Base de Datos Recomendado

### 1. Tabla Principal: `agents`

```sql
CREATE TABLE agents (
    -- Identificadores
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id VARCHAR(50) UNIQUE NOT NULL,

    -- Información básica
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL CHECK (length(description) >= 10 AND length(description) <= 500),
    agent_type VARCHAR(10) NOT NULL CHECK (agent_type IN ('custom', 'system')),

    -- Configuración del modelo
    model VARCHAR(100) NOT NULL,
    system_prompt TEXT NOT NULL CHECK (length(system_prompt) >= 50 AND length(system_prompt) <= 10000),
    temperature DECIMAL(3,2) NOT NULL CHECK (temperature >= 0.1 AND temperature <= 2.0),
    max_tokens INTEGER NOT NULL CHECK (max_tokens >= 100 AND max_tokens <= 4000),
    max_turns INTEGER NOT NULL CHECK (max_turns >= 5 AND max_turns <= 100),
    timeout_seconds INTEGER NOT NULL CHECK (timeout_seconds >= 30 AND timeout_seconds <= 300),
    enable_memory BOOLEAN NOT NULL DEFAULT true,

    -- Seguridad y encriptación
    llm_api_key_encrypted TEXT NOT NULL,
    encryption_key_id VARCHAR(50), -- Referencia a la clave de encriptación usada

    -- Estado y metadatos
    is_active BOOLEAN NOT NULL DEFAULT true,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error')),

    -- Auditoría
    created_by UUID REFERENCES api_users(id) ON DELETE SET NULL, -- ID del usuario que creó el agente
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Validaciones adicionales
    CONSTRAINT valid_agent_id CHECK (agent_id ~ '^[a-z0-9-]+$'),
    CONSTRAINT name_length CHECK (length(name) >= 3 AND length(name) <= 100)
);

-- Índices para optimización
CREATE INDEX idx_agents_agent_id ON agents(agent_id);
CREATE INDEX idx_agents_created_by ON agents(created_by);
CREATE INDEX idx_agents_type_status ON agents(agent_type, status);
CREATE INDEX idx_agents_active ON agents(is_active) WHERE is_active = true;
```

### 2. Tabla de Relación: `agent_tools`

```sql
CREATE TABLE agent_tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,

    -- Auditoría
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE(agent_id, tool_id)
);

CREATE INDEX idx_agent_tools_agent_id ON agent_tools(agent_id);
CREATE INDEX idx_agent_tools_tool_id ON agent_tools(tool_id);
```

### 3. Tabla de Configuraciones: `agent_tool_configurations`

```sql
CREATE TABLE agent_tool_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,

    -- Clave y valor de la configuración
    property_name VARCHAR(100) NOT NULL,
    property_value TEXT, -- Valor no encriptado
    property_value_encrypted TEXT, -- Valor encriptado para datos sensibles
    is_encrypted BOOLEAN NOT NULL DEFAULT false,

    -- Auditoría
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE(agent_id, tool_id, property_name),

    -- Validación: solo uno de los dos valores debe estar presente
    CONSTRAINT value_xor_encrypted CHECK (
        (property_value IS NOT NULL AND property_value_encrypted IS NULL AND is_encrypted = false) OR
        (property_value IS NULL AND property_value_encrypted IS NOT NULL AND is_encrypted = true)
    )
);

CREATE INDEX idx_agent_tool_configs_agent_tool ON agent_tool_configurations(agent_id, tool_id);
CREATE INDEX idx_agent_tool_configs_encrypted ON agent_tool_configurations(is_encrypted) WHERE is_encrypted = true;
```


## Consideraciones de Seguridad

### 1. Encriptación de Datos Sensibles

La encriptación de campos sensibles (como `llm_api_key` y configuraciones de herramientas marcadas con `is_encrypted: true`) se maneja en el backend de la aplicación, no en la base de datos.

**Ventajas de esta implementación:**
- Mayor flexibilidad para cambiar algoritmos de encriptación
- Mejor manejo de claves de encriptación mediante variables de entorno
- Portabilidad entre diferentes sistemas de base de datos
- Facilita testing y debugging

### 2. Control de Acceso

El control de acceso a los agentes se maneja en el backend de la aplicación a través de los endpoints de la API. Esto proporciona mayor flexibilidad y facilita el mantenimiento.

**Implementación actual:**
- Los usuarios autenticados ven sus propios agentes + agentes del sistema (`created_by IS NULL`)
- Los usuarios no autenticados solo ven agentes del sistema
- La lógica está implementada en los endpoints `/api/v1/agents` del backend

## Triggers para Auditoría

```sql
-- Trigger para actualizar timestamp de modificación
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agents_updated_at
    BEFORE UPDATE ON agents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

```