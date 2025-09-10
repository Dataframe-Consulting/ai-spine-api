# Esquema de Base de Datos para el Registro de Tools

Este documento define la estructura de las tablas necesarias para almacenar las herramientas (tools) según el formulario de registro implementado en la aplicación AI Spine.

## Tabla Principal: `tools`

La tabla principal que almacena la información básica de cada herramienta registrada.

```sql
CREATE TABLE tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id VARCHAR(255) UNIQUE NOT NULL,           -- ID único de la herramienta (ej: "ocr-document-reader")
    name VARCHAR(255) NOT NULL,                     -- Nombre display de la herramienta
    description TEXT,                               -- Descripción de la herramienta
    endpoint TEXT NOT NULL,                         -- URL del endpoint de la herramienta
    is_active BOOLEAN DEFAULT TRUE,                 -- Estado activo/inactivo
    metadata JSONB DEFAULT '{}',                    -- Metadatos adicionales de la herramienta
    created_by UUID REFERENCES api_users(id) ON DELETE SET NULL,  -- Usuario que creó la herramienta
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para optimizar consultas
CREATE INDEX idx_tools_tool_id ON tools(tool_id);
CREATE INDEX idx_tools_is_active ON tools(is_active);
CREATE INDEX idx_tools_created_by ON tools(created_by);
CREATE INDEX idx_tools_created_at ON tools(created_at);
```

## Tabla: `tool_types`

Define los tipos de herramientas disponibles según el enum del formulario.

```sql
CREATE TABLE tool_types (
    id SERIAL PRIMARY KEY,
    type_name VARCHAR(50) UNIQUE NOT NULL,          -- OCR, DOCUMENT_GENERATION, etc.
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Datos iniciales
INSERT INTO tool_types (type_name, description) VALUES
('OCR', 'Optical Character Recognition tools'),
('DOCUMENT_GENERATION', 'Tools for generating documents'),
('WEB_SCRAPING', 'Web scraping and data extraction tools'),
('API_INTEGRATION', 'API integration and connectivity tools'),
('MEETING_SCHEDULER', 'Meeting scheduling and calendar tools'),
('EMAIL_AUTOMATION', 'Email automation and messaging tools'),
('DATA_ANALYSIS', 'Data analysis and processing tools'),
('TRANSLATION', 'Language translation tools'),
('IMAGE_PROCESSING', 'Image processing and manipulation tools'),
('DATABASE_QUERY', 'Database query and management tools');
```

## Tabla Relacional: `tool_type_assignments`

Relaciona las herramientas con sus tipos (relación many-to-many).

```sql
CREATE TABLE tool_type_assignments (
    id SERIAL PRIMARY KEY,
    tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    tool_type_id INTEGER NOT NULL REFERENCES tool_types(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Prevenir duplicados
    UNIQUE(tool_id, tool_type_id)
);

-- Índices
CREATE INDEX idx_tool_type_assignments_tool_id ON tool_type_assignments(tool_id);
CREATE INDEX idx_tool_type_assignments_tool_type_id ON tool_type_assignments(tool_type_id);
```


## Tabla: `tool_schemas`

Almacena los esquemas JSON para input, output y configuración.

```sql
CREATE TABLE tool_schemas (
    id SERIAL PRIMARY KEY,
    tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    schema_type VARCHAR(20) NOT NULL CHECK (schema_type IN ('input', 'output', 'config')),
    schema_data JSONB NOT NULL,                     -- El esquema JSON completo
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Un tool puede tener solo un esquema de cada tipo
    UNIQUE(tool_id, schema_type)
);

-- Índices
CREATE INDEX idx_tool_schemas_tool_id ON tool_schemas(tool_id);
CREATE INDEX idx_tool_schemas_schema_type ON tool_schemas(schema_type);
CREATE INDEX idx_tool_schemas_schema_data ON tool_schemas USING GIN (schema_data);
```

## Tabla: `schema_properties`

Detalle de las propiedades de cada esquema para consultas más eficientes.

```sql
CREATE TABLE schema_properties (
    id SERIAL PRIMARY KEY,
    schema_id INTEGER NOT NULL REFERENCES tool_schemas(id) ON DELETE CASCADE,
    property_name VARCHAR(255) NOT NULL,
    property_type VARCHAR(50) NOT NULL,              -- string, integer, number, boolean, array, object
    description TEXT,
    is_required BOOLEAN DEFAULT FALSE,
    is_sensitive BOOLEAN DEFAULT FALSE,              -- Solo para config schema
    default_value TEXT,
    format_type VARCHAR(100),                        -- email, uri, date-time, etc.
    validation_rules JSONB DEFAULT '{}',             -- min, max, pattern, enum, etc.
    parent_property_id INTEGER REFERENCES schema_properties(id) ON DELETE CASCADE, -- Para propiedades anidadas
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices
CREATE INDEX idx_schema_properties_schema_id ON schema_properties(schema_id);
CREATE INDEX idx_schema_properties_property_name ON schema_properties(property_name);
CREATE INDEX idx_schema_properties_parent_property_id ON schema_properties(parent_property_id);
CREATE INDEX idx_schema_properties_validation_rules ON schema_properties USING GIN (validation_rules);
```

## Tabla: `tool_executions` (para auditoria)

Registro de las ejecuciones de herramientas para análisis y debugging.

```sql
CREATE TABLE tool_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id UUID NOT NULL REFERENCES tools(id),
    agent_id UUID,                                  -- ID del agente que ejecutó la tool
    execution_id UUID,                              -- ID de la ejecución del flujo
    input_data JSONB,                              -- Datos de entrada
    output_data JSONB,                             -- Datos de salida
    config_data JSONB,                             -- Configuración utilizada
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'running', 'success', 'error', 'timeout')),
    error_message TEXT,
    execution_time_ms INTEGER,                      -- Tiempo de ejecución en milisegundos
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para análisis de performance
CREATE INDEX idx_tool_executions_tool_id ON tool_executions(tool_id);
CREATE INDEX idx_tool_executions_agent_id ON tool_executions(agent_id);
CREATE INDEX idx_tool_executions_execution_id ON tool_executions(execution_id);
CREATE INDEX idx_tool_executions_status ON tool_executions(status);
CREATE INDEX idx_tool_executions_started_at ON tool_executions(started_at);
CREATE INDEX idx_tool_executions_input_data ON tool_executions USING GIN (input_data);
CREATE INDEX idx_tool_executions_output_data ON tool_executions USING GIN (output_data);
```

## Ejemplos de Datos del Formulario

### Ejemplo de Tool Completa: OCR Document Reader

```sql
-- 1. Insertar la herramienta principal
INSERT INTO tools (tool_id, name, description, endpoint) VALUES (
    'ocr-document-reader',
    'OCR Document Reader',
    'Extracts text from images and PDF documents using advanced OCR technology',
    'https://api.example.com/ocr'
);

-- 2. Asignar tipos de herramienta
INSERT INTO tool_type_assignments (tool_id, tool_type_id) 
SELECT t.id, tt.id 
FROM tools t, tool_types tt 
WHERE t.tool_id = 'ocr-document-reader' 
AND tt.type_name IN ('OCR', 'DOCUMENT_GENERATION');

-- 3. Input Schema
INSERT INTO tool_schemas (tool_id, schema_type, schema_data) 
SELECT id, 'input', '{
  "schema_version": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": [
    {
      "property_name": "file_data",
      "type": "string",
      "description": "Base64 encoded file data or file URL",
      "required": true,
      "format": "base64"
    },
    {
      "property_name": "language",
      "type": "string", 
      "description": "Language for OCR recognition",
      "required": false,
      "default_value": "en",
      "enum_values": ["en", "es", "fr", "de"]
    },
    {
      "property_name": "output_format",
      "type": "string",
      "description": "Desired output format",
      "required": false,
      "default_value": "text",
      "enum_values": ["text", "json", "markdown"]
    }
  ],
  "required_properties": ["file_data"],
  "additional_properties": false
}'::jsonb 
FROM tools WHERE tool_id = 'ocr-document-reader';

-- 4. Output Schema
INSERT INTO tool_schemas (tool_id, schema_type, schema_data)
SELECT id, 'output', '{
  "schema_version": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": [
    {
      "property_name": "extracted_text",
      "type": "string",
      "description": "The extracted text from the document",
      "required": true
    },
    {
      "property_name": "confidence_score",
      "type": "number",
      "description": "OCR confidence score between 0 and 1",
      "required": true,
      "minimum": 0,
      "maximum": 1
    },
    {
      "property_name": "processing_time_ms",
      "type": "integer",
      "description": "Processing time in milliseconds",
      "required": false
    }
  ],
  "required_properties": ["extracted_text", "confidence_score"],
  "additional_properties": false,
  "artifact_config": {
    "enabled": true
  }
}'::jsonb
FROM tools WHERE tool_id = 'ocr-document-reader';

-- 5. Config Schema  
INSERT INTO tool_schemas (tool_id, schema_type, schema_data)
SELECT id, 'config', '{
  "schema_version": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": [
    {
      "property_name": "tesseract_api_key",
      "type": "api_key",
      "description": "API key for Tesseract OCR service",
      "required": true,
      "sensitive": true
    },
    {
      "property_name": "max_file_size_mb",
      "type": "number",
      "description": "Maximum file size in megabytes",
      "required": false,
      "default_value": "10"
    }
  ],
  "required_properties": ["tesseract_api_key"],
  "additional_properties": false
}'::jsonb
FROM tools WHERE tool_id = 'ocr-document-reader';
```

## Consultas Útiles

### Obtener herramienta completa con esquemas

```sql
SELECT 
    t.*,
    array_agg(DISTINCT tt.type_name) as tool_types,
    (SELECT schema_data FROM tool_schemas WHERE tool_id = t.id AND schema_type = 'input') as input_schema,
    (SELECT schema_data FROM tool_schemas WHERE tool_id = t.id AND schema_type = 'output') as output_schema,
    (SELECT schema_data FROM tool_schemas WHERE tool_id = t.id AND schema_type = 'config') as config_schema
FROM tools t
LEFT JOIN tool_type_assignments tta ON t.id = tta.tool_id
LEFT JOIN tool_types tt ON tta.tool_type_id = tt.id
WHERE t.tool_id = 'ocr-document-reader'
GROUP BY t.id;
```

### Buscar herramientas por tipo

```sql
SELECT DISTINCT t.*
FROM tools t
JOIN tool_type_assignments tta ON t.id = tta.tool_id
JOIN tool_types tt ON tta.tool_type_id = tt.id
WHERE tt.type_name = 'OCR' AND t.is_active = true;
```

### Estadísticas de uso de herramientas

```sql
SELECT 
    t.name,
    t.tool_id,
    COUNT(te.id) as total_executions,
    COUNT(CASE WHEN te.status = 'success' THEN 1 END) as successful_executions,
    COUNT(CASE WHEN te.status = 'error' THEN 1 END) as failed_executions,
    ROUND(AVG(te.execution_time_ms), 2) as avg_execution_time_ms
FROM tools t
LEFT JOIN tool_executions te ON t.id = te.tool_id
WHERE te.created_at >= NOW() - INTERVAL '30 days'
GROUP BY t.id, t.name, t.tool_id
ORDER BY total_executions DESC;
```

## Notas Importantes

1. **Esquemas JSON**: Los esquemas se almacenan como JSONB para flexibilidad y consultas eficientes.

2. **Validación**: Se incluyen constraints para garantizar la integridad de los datos.

3. **Escalabilidad**: Los índices están optimizados para consultas frecuentes.

4. **Auditoria**: La tabla `tool_executions` permite tracking completo del uso de herramientas.

5. **Seguridad**: Los campos sensibles están marcados para manejo especial en la aplicación.

6. **Flexibilidad**: El uso de JSONB permite evolución del esquema sin cambios en la estructura de la base de datos.

Esta estructura soporta completamente todos los campos del formulario de registro de herramientas y permite consultas eficientes para la gestión y análisis de las tools en el sistema AI Spine.

## Migraciones

### Migración 1: Agregar relación con usuarios

Para relacionar las herramientas con los usuarios, se necesita agregar una columna `created_by` a la tabla `tools` que haga referencia a los usuarios del sistema.

```sql
-- Agregar columna created_by a la tabla tools (referencia a api_users)
ALTER TABLE tools ADD COLUMN created_by UUID REFERENCES api_users(id) ON DELETE SET NULL;

-- Crear índice para optimizar consultas por usuario
CREATE INDEX idx_tools_created_by ON tools(created_by);
```

### Migración 2: Agregar created_by a tool_executions

Para tracking completo, también agregar la referencia de usuario a las ejecuciones:

```sql
-- Agregar columna created_by a la tabla tool_executions (referencia a api_users)
ALTER TABLE tool_executions ADD COLUMN created_by UUID REFERENCES api_users(id) ON DELETE SET NULL;

-- Crear índice para consultas por usuario
CREATE INDEX idx_tool_executions_created_by ON tool_executions(created_by);

-- Alternativa si prefieres agregar la foreign key después:
-- ALTER TABLE tool_executions ADD COLUMN created_by UUID;
-- ALTER TABLE tool_executions ADD CONSTRAINT fk_tool_executions_created_by 
-- FOREIGN KEY (created_by) REFERENCES api_users(id) ON DELETE SET NULL;
```

### Migración 3: Actualizar datos existentes (opcional)

Si hay herramientas existentes que no tienen usuario asignado, se pueden marcar como herramientas del sistema:

```sql
-- Marcar herramientas existentes sin usuario como herramientas del sistema
-- (created_by = NULL indica herramientas del sistema)
UPDATE tools SET created_by = NULL WHERE created_by IS NULL;

-- O asignar a un usuario administrador específico
-- UPDATE tools SET created_by = 'admin-user-uuid' WHERE created_by IS NULL;
```

### Migración 4: Datos iniciales para tool_types

Insertar los tipos de herramientas base en la tabla:

```sql
-- Insertar tipos de herramientas si no existen
INSERT INTO tool_types (type_name, description) VALUES
('OCR', 'Optical Character Recognition tools'),
('DOCUMENT_GENERATION', 'Tools for generating documents'),
('WEB_SCRAPING', 'Web scraping and data extraction tools'),
('API_INTEGRATION', 'API integration and connectivity tools'),
('MEETING_SCHEDULER', 'Meeting scheduling and calendar tools'),
('EMAIL_AUTOMATION', 'Email automation and messaging tools'),
('DATA_ANALYSIS', 'Data analysis and processing tools'),
('TRANSLATION', 'Language translation tools'),
('IMAGE_PROCESSING', 'Image processing and manipulation tools'),
('DATABASE_QUERY', 'Database query and management tools')
ON CONFLICT (type_name) DO NOTHING;
```

### Consultas actualizadas con relaciones de usuario

Una vez aplicadas las migraciones, las consultas pueden filtrar por usuario:

```sql
-- Obtener herramientas de un usuario específico
SELECT * FROM tools 
WHERE created_by = 'user-uuid' 
OR created_by IS NULL  -- Incluir herramientas del sistema
ORDER BY created_at DESC;

-- Obtener solo herramientas del sistema
SELECT * FROM tools 
WHERE created_by IS NULL 
ORDER BY created_at DESC;

-- Estadísticas de uso por usuario
SELECT 
    u.email,
    COUNT(t.id) as total_tools,
    COUNT(CASE WHEN t.is_active THEN 1 END) as active_tools,
    COUNT(te.id) as total_executions
FROM api_users u
LEFT JOIN tools t ON u.id = t.created_by
LEFT JOIN tool_executions te ON t.id = te.tool_id
GROUP BY u.id, u.email
ORDER BY total_tools DESC;
```

### Script de migración completo

```sql
-- Migración completa para relacionar tools con usuarios
BEGIN;

-- 1. Verificar que la tabla api_users existe
-- SELECT 1 FROM information_schema.tables WHERE table_name = 'api_users';

-- 2. Agregar columnas de usuario con referencias
ALTER TABLE tools ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES api_users(id) ON DELETE SET NULL;
ALTER TABLE tool_executions ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES api_users(id) ON DELETE SET NULL;

-- 3. Crear índices
CREATE INDEX IF NOT EXISTS idx_tools_created_by ON tools(created_by);
CREATE INDEX IF NOT EXISTS idx_tool_executions_created_by ON tool_executions(created_by);

-- 4. Crear tabla tool_types si no existe
CREATE TABLE IF NOT EXISTS tool_types (
    id SERIAL PRIMARY KEY,
    type_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. Insertar tipos de herramientas
INSERT INTO tool_types (type_name, description) VALUES
('OCR', 'Optical Character Recognition tools'),
('DOCUMENT_GENERATION', 'Tools for generating documents'),
('WEB_SCRAPING', 'Web scraping and data extraction tools'),
('API_INTEGRATION', 'API integration and connectivity tools'),
('MEETING_SCHEDULER', 'Meeting scheduling and calendar tools'),
('EMAIL_AUTOMATION', 'Email automation and messaging tools'),
('DATA_ANALYSIS', 'Data analysis and processing tools'),
('TRANSLATION', 'Language translation tools'),
('IMAGE_PROCESSING', 'Image processing and manipulation tools'),
('DATABASE_QUERY', 'Database query and management tools')
ON CONFLICT (type_name) DO NOTHING;

-- 6. Crear tablas relacionales si no existen
CREATE TABLE IF NOT EXISTS tool_type_assignments (
    id SERIAL PRIMARY KEY,
    tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    tool_type_id INTEGER NOT NULL REFERENCES tool_types(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tool_id, tool_type_id)
);

CREATE TABLE IF NOT EXISTS tool_schemas (
    id SERIAL PRIMARY KEY,
    tool_id UUID NOT NULL REFERENCES tools(id) ON DELETE CASCADE,
    schema_type VARCHAR(20) NOT NULL CHECK (schema_type IN ('input', 'output', 'config')),
    schema_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tool_id, schema_type)
);

-- 7. Crear índices adicionales
CREATE INDEX IF NOT EXISTS idx_tool_type_assignments_tool_id ON tool_type_assignments(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_type_assignments_tool_type_id ON tool_type_assignments(tool_type_id);
CREATE INDEX IF NOT EXISTS idx_tool_schemas_tool_id ON tool_schemas(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_schemas_schema_type ON tool_schemas(schema_type);

COMMIT;
```

## Notas sobre las Migraciones

1. **Herramientas del Sistema**: Las herramientas con `created_by = NULL` se consideran herramientas del sistema, visibles para todos los usuarios.

2. **Herramientas de Usuario**: Las herramientas con `created_by` asignado solo son visibles para su creador y administradores.

3. **Backward Compatibility**: Las herramientas existentes se pueden mantener como herramientas del sistema hasta que se asignen a usuarios específicos.

4. **Foreign Keys**: Se recomienda agregar las foreign keys solo si la tabla `api_users` está completamente configurada y estable.

5. **Índices**: Los índices en `created_by` son esenciales para consultas eficientes de herramientas por usuario.