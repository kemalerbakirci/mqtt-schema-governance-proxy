# MQTT Schema Governance Proxy - Configuration Specification

[![Configuration](https://img.shields.io/badge/config-yaml-blue.svg)](#)
[![Validation](https://img.shields.io/badge/validation-strict-green.svg)](#)
[![Schema](https://img.shields.io/badge/schema-documented-orange.svg)](#)

## 📋 Configuration Overview

The MQTT Schema Governance Proxy uses YAML configuration files to define all operational parameters. This document provides a complete specification of all configuration options, their types, default values, and validation rules.

## 🗂️ Configuration File Structure

```yaml
# Root configuration structure
global: {...}           # Global proxy settings
brokers: {...}          # MQTT broker configurations  
validation: {...}       # Message validation rules
storage: {...}          # Data storage settings
monitoring: {...}       # Observability configuration
security: {...}         # Security and authentication
performance: {...}      # Performance optimization
```

## 🌐 Global Configuration

### **Schema Definition**

```yaml
global:
  proxy_mode: string              # Required: Operational mode
  log_level: string              # Optional: Logging verbosity  
  max_message_size: integer      # Optional: Message size limit
  message_timeout: integer       # Optional: Processing timeout
  dry_run: boolean              # Optional: Validation-only mode
  config_reload: boolean        # Optional: Hot config reloading
  instance_id: string           # Optional: Unique instance identifier
```

### **Detailed Specification**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `proxy_mode` | `string` | ✅ | - | `production\|development\|testing` | Operational mode affecting logging and error handling |
| `log_level` | `string` | ❌ | `INFO` | `DEBUG\|INFO\|WARNING\|ERROR\|CRITICAL` | Python logging level |
| `max_message_size` | `integer` | ❌ | `1048576` | `1024 <= x <= 104857600` | Maximum MQTT message size in bytes (1KB-100MB) |
| `message_timeout` | `integer` | ❌ | `30` | `1 <= x <= 300` | Message processing timeout in seconds |
| `dry_run` | `boolean` | ❌ | `false` | `true\|false` | When true, validates but doesn't forward messages |
| `config_reload` | `boolean` | ❌ | `true` | `true\|false` | Enable automatic configuration reloading |
| `instance_id` | `string` | ❌ | `auto-generated` | `^[a-zA-Z0-9-_]{1,64}$` | Unique identifier for this proxy instance |

### **Example Configuration**

```yaml
global:
  proxy_mode: "production"
  log_level: "INFO"
  max_message_size: 2097152        # 2MB
  message_timeout: 45
  dry_run: false
  config_reload: true
  instance_id: "proxy-east-01"
```

## 🔌 Broker Configuration

### **Schema Definition**

```yaml
brokers:
  subscriber:                     # Required: Incoming message broker
    host: string                 # Required: Broker hostname
    port: integer               # Required: Broker port
    client_id: string           # Required: MQTT client ID
    username: string            # Optional: Authentication username
    password: string            # Optional: Authentication password  
    keepalive: integer          # Optional: Keep-alive interval
    ssl: boolean               # Optional: Enable SSL/TLS
    ca_certs: string           # Optional: CA certificate path
    certfile: string           # Optional: Client certificate path
    keyfile: string            # Optional: Private key path
    tls_version: string        # Optional: TLS protocol version
    ciphers: string            # Optional: Allowed cipher suites
    transport: string          # Optional: Transport protocol
    websocket_path: string     # Optional: WebSocket path
    websocket_headers: object  # Optional: WebSocket headers
    
  publisher:                     # Required: Outgoing message broker
    # Same fields as subscriber
```

### **Detailed Specification**

#### **Connection Settings**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `host` | `string` | ✅ | - | Valid hostname/IP | MQTT broker hostname or IP address |
| `port` | `integer` | ✅ | - | `1 <= x <= 65535` | MQTT broker port number |
| `client_id` | `string` | ✅ | - | `^[a-zA-Z0-9-_]{1,23}$` | MQTT client identifier (max 23 chars) |
| `username` | `string` | ❌ | `null` | Any string | MQTT authentication username |
| `password` | `string` | ❌ | `null` | Any string | MQTT authentication password |
| `keepalive` | `integer` | ❌ | `60` | `10 <= x <= 65535` | Keep-alive interval in seconds |

#### **SSL/TLS Settings**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `ssl` | `boolean` | ❌ | `false` | `true\|false` | Enable SSL/TLS encryption |
| `ca_certs` | `string` | ❌ | `null` | Valid file path | Path to CA certificate file |
| `certfile` | `string` | ❌ | `null` | Valid file path | Path to client certificate file |
| `keyfile` | `string` | ❌ | `null` | Valid file path | Path to private key file |
| `tls_version` | `string` | ❌ | `TLSv1.2` | `TLSv1.2\|TLSv1.3` | TLS protocol version |
| `ciphers` | `string` | ❌ | `HIGH:!aNULL` | Valid cipher string | Allowed cipher suites |

#### **Transport Settings**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `transport` | `string` | ❌ | `tcp` | `tcp\|websockets` | MQTT transport protocol |
| `websocket_path` | `string` | ❌ | `/mqtt` | Valid URL path | WebSocket endpoint path |
| `websocket_headers` | `object` | ❌ | `{}` | Key-value pairs | Additional WebSocket headers |

### **Example Configurations**

#### **Basic MQTT**
```yaml
brokers:
  subscriber:
    host: "mqtt.example.com"
    port: 1883
    client_id: "proxy-sub-001"
    username: "proxy_user"
    password: "secure_password"
    keepalive: 60
    
  publisher:
    host: "mqtt-upstream.example.com"  
    port: 1883
    client_id: "proxy-pub-001"
```

#### **Secure MQTT with TLS**
```yaml
brokers:
  subscriber:
    host: "secure-mqtt.example.com"
    port: 8883
    client_id: "proxy-sub-secure"
    ssl: true
    ca_certs: "/etc/ssl/certs/ca.pem"
    certfile: "/etc/ssl/certs/client.crt"
    keyfile: "/etc/ssl/private/client.key"
    tls_version: "TLSv1.3"
    ciphers: "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
```

#### **WebSocket MQTT**
```yaml
brokers:
  subscriber:
    host: "ws-mqtt.example.com"
    port: 9001
    client_id: "proxy-ws-001"
    transport: "websockets"
    websocket_path: "/mqtt"
    websocket_headers:
      "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
      "X-Client-Version": "1.0.0"
```

## ✅ Validation Configuration

### **Schema Definition**

```yaml
validation:
  topic_patterns: array           # Required: Allowed topic patterns
  schema_mappings: object         # Required: Topic to schema mapping
  schema_files: object           # Required: Schema file definitions
  client_rules: object          # Optional: Client-specific rules
  validation_mode: string       # Optional: Validation behavior
  cache_size: integer          # Optional: Validation cache size
  strict_mode: boolean         # Optional: Strict validation mode
```

### **Topic Patterns**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `topic_patterns` | `array[string]` | ✅ | - | Valid MQTT topics | List of allowed topic patterns with wildcards |

**MQTT Wildcard Support:**
- `+` - Single level wildcard (matches one topic level)
- `#` - Multi-level wildcard (matches zero or more topic levels)

**Examples:**
```yaml
validation:
  topic_patterns:
    - "devices/+/telemetry"        # devices/{device_id}/telemetry
    - "sensors/#"                  # sensors/temperature/room1, sensors/humidity/...
    - "alerts/critical/+"          # alerts/critical/{alert_type}
    - "logs/application/+/errors"  # logs/application/{app_name}/errors
```

### **Schema Mappings**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `schema_mappings` | `object` | ✅ | - | Key: topic pattern, Value: schema ID | Maps topic patterns to schema identifiers |

```yaml
validation:
  schema_mappings:
    "devices/+/telemetry": "telemetry_v2"
    "sensors/temperature/+": "temperature_v1"
    "sensors/humidity/+": "humidity_v1"
    "alerts/critical/+": "alert_schema"
```

### **Schema Files**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `schema_files` | `object` | ✅ | - | Schema file configuration | Schema file definitions and settings |

**Schema File Configuration:**
```yaml
validation:
  schema_files:
    schema_id:
      type: string               # Required: json|protobuf
      path: string              # Required: File path
      message_type: string      # Optional: For protobuf schemas
      strict: boolean          # Optional: Strict JSON validation
      draft: string           # Optional: JSON Schema draft version
```

#### **Schema File Fields**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `type` | `string` | ✅ | - | `json\|protobuf` | Schema format type |
| `path` | `string` | ✅ | - | Valid file path | Path to schema file |
| `message_type` | `string` | ❌ | - | Valid protobuf type | Message type for protobuf schemas |
| `strict` | `boolean` | ❌ | `true` | `true\|false` | Enforce strict JSON Schema validation |
| `draft` | `string` | ❌ | `draft7` | `draft4\|draft6\|draft7` | JSON Schema draft version |

**Examples:**
```yaml
validation:
  schema_files:
    telemetry_v2:
      type: "protobuf"
      path: "schemas/telemetry_v2.proto"
      message_type: "TelemetryMessage"
      
    temperature_v1:
      type: "json"
      path: "schemas/temperature_v1.json"
      strict: true
      draft: "draft7"
      
    alert_schema:
      type: "json"
      path: "schemas/alerts.json"
      strict: false
```

### **Client Rules**

```yaml
validation:
  client_rules:
    client_id:
      allowed_topics: array      # Optional: Client-specific allowed topics
      rate_limit: integer       # Optional: Messages per second limit
      max_message_size: integer # Optional: Client-specific size limit
```

**Example:**
```yaml
validation:
  client_rules:
    "iot-device-001":
      allowed_topics:
        - "devices/iot-device-001/telemetry"
        - "devices/iot-device-001/status"
      rate_limit: 10
      max_message_size: 512000
      
    "sensor-gateway":
      allowed_topics:
        - "sensors/+/temperature"
        - "sensors/+/humidity"
        - "gateways/sensor-gateway/health"
      rate_limit: 100
```

### **Additional Validation Settings**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `validation_mode` | `string` | ❌ | `strict` | `strict\|lenient\|warn_only` | Validation behavior mode |
| `cache_size` | `integer` | ❌ | `1000` | `10 <= x <= 10000` | Schema validation cache size |
| `strict_mode` | `boolean` | ❌ | `true` | `true\|false` | Enable strict validation mode |

## 💾 Storage Configuration

### **Schema Definition**

```yaml
storage:
  quarantine:                    # Required: Quarantine storage settings
    driver: string              # Required: Storage driver type
    path: string               # Required: Storage path/connection
    max_size: string          # Optional: Maximum storage size
    cleanup_days: integer     # Optional: Data retention period
    compression: string       # Optional: Data compression
    backup: object           # Optional: Backup configuration
    
  payloads:                     # Optional: Payload storage settings
    path: string              # Required: Payload storage path
    max_file_size: string    # Optional: Maximum file size
    compression: string      # Optional: Compression algorithm
    retention_days: integer  # Optional: File retention period
```

### **Quarantine Storage**

#### **SQLite Configuration**
```yaml
storage:
  quarantine:
    driver: "sqlite"
    path: "data/quarantine.db"
    max_size: "10GB"
    cleanup_days: 30
    backup:
      enabled: true
      interval: "24h"
      location: "backups/"
      retention: 7
```

#### **PostgreSQL Configuration**
```yaml
storage:
  quarantine:
    driver: "postgresql"
    host: "db.example.com"
    port: 5432
    database: "mqtt_proxy"
    username: "proxy_user"
    password: "secure_password"
    pool_size: 10
    max_overflow: 20
    ssl_mode: "require"
    cleanup_days: 90
```

#### **MySQL Configuration**
```yaml
storage:
  quarantine:
    driver: "mysql"
    host: "mysql.example.com"
    port: 3306
    database: "mqtt_proxy"
    username: "proxy_user"
    password: "secure_password"
    charset: "utf8mb4"
    pool_size: 10
    cleanup_days: 60
```

### **Storage Field Specifications**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `driver` | `string` | ✅ | - | `sqlite\|postgresql\|mysql` | Database driver type |
| `path` | `string` | ✅ | - | Valid path | Database file path (SQLite) or connection string |
| `max_size` | `string` | ❌ | `1GB` | Size format (KB/MB/GB/TB) | Maximum storage size |
| `cleanup_days` | `integer` | ❌ | `30` | `1 <= x <= 3650` | Data retention in days |
| `compression` | `string` | ❌ | `gzip` | `none\|gzip\|lz4\|zstd` | Data compression algorithm |

## 📊 Monitoring Configuration

### **Schema Definition**

```yaml
monitoring:
  metrics:                       # Optional: Metrics collection
    enabled: boolean            # Optional: Enable metrics
    port: integer              # Optional: Metrics server port
    path: string               # Optional: Metrics endpoint path
    update_interval: integer   # Optional: Metrics update frequency
    custom_labels: object      # Optional: Custom metric labels
    
  health_check:                 # Optional: Health check endpoint
    enabled: boolean           # Optional: Enable health checks
    port: integer             # Optional: Health check port
    path: string              # Optional: Health check path
    timeout: integer          # Optional: Health check timeout
    
  audit:                        # Optional: Audit logging
    enabled: boolean          # Optional: Enable audit logging
    format: string           # Optional: Log format
    destination: string      # Optional: Log destination
    file_path: string       # Optional: Log file path
    rotation: string        # Optional: Log rotation policy
    retention_days: integer # Optional: Log retention period
```

### **Metrics Configuration**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `enabled` | `boolean` | ❌ | `true` | `true\|false` | Enable Prometheus metrics |
| `port` | `integer` | ❌ | `9100` | `1024 <= x <= 65535` | Metrics server port |
| `path` | `string` | ❌ | `/metrics` | Valid URL path | Metrics endpoint path |
| `update_interval` | `integer` | ❌ | `5` | `1 <= x <= 60` | Metrics update interval (seconds) |

**Example:**
```yaml
monitoring:
  metrics:
    enabled: true
    port: 9100
    path: "/metrics"
    update_interval: 5
    custom_labels:
      environment: "production"
      region: "us-east-1"
      version: "1.0.0"
```

### **Health Check Configuration**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `enabled` | `boolean` | ❌ | `true` | `true\|false` | Enable health check endpoint |
| `port` | `integer` | ❌ | `8080` | `1024 <= x <= 65535` | Health check server port |
| `path` | `string` | ❌ | `/health` | Valid URL path | Health check endpoint path |
| `timeout` | `integer` | ❌ | `5` | `1 <= x <= 30` | Health check timeout (seconds) |

### **Audit Logging Configuration**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `enabled` | `boolean` | ❌ | `true` | `true\|false` | Enable audit logging |
| `format` | `string` | ❌ | `json` | `json\|text\|syslog` | Log format |
| `destination` | `string` | ❌ | `file` | `file\|stdout\|syslog` | Log destination |
| `file_path` | `string` | ❌ | `logs/audit.log` | Valid file path | Log file path |
| `rotation` | `string` | ❌ | `daily` | `hourly\|daily\|weekly` | Log rotation policy |
| `retention_days` | `integer` | ❌ | `90` | `1 <= x <= 3650` | Log retention period |

## 🔒 Security Configuration

### **Schema Definition**

```yaml
security:
  authentication:               # Optional: Authentication settings
    enabled: boolean           # Optional: Enable authentication
    method: string            # Optional: Authentication method
    ldap: object             # Optional: LDAP configuration
    jwt: object              # Optional: JWT configuration
    
  authorization:               # Optional: Authorization settings
    enabled: boolean          # Optional: Enable authorization
    rules: array             # Optional: Authorization rules
    
  encryption:                 # Optional: Encryption settings
    payload_encryption: boolean # Optional: Encrypt message payloads
    key_management: object      # Optional: Key management settings
    
  rate_limiting:              # Optional: Rate limiting
    enabled: boolean          # Optional: Enable rate limiting
    global_limit: integer     # Optional: Global rate limit
    per_client_limit: integer # Optional: Per-client rate limit
    window_size: integer      # Optional: Rate limiting window
```

### **Authentication Configuration**

**LDAP Authentication:**
```yaml
security:
  authentication:
    enabled: true
    method: "ldap"
    ldap:
      server: "ldap://ldap.example.com"
      port: 389
      bind_dn: "cn=admin,dc=example,dc=com"
      bind_password: "admin_password"
      base_dn: "ou=users,dc=example,dc=com"
      user_filter: "(uid={username})"
      ssl: false
```

**JWT Authentication:**
```yaml
security:
  authentication:
    enabled: true
    method: "jwt"
    jwt:
      secret_key: "your-secret-key"
      algorithm: "HS256"
      expiration: 3600
      issuer: "mqtt-proxy"
      audience: "mqtt-clients"
```

### **Rate Limiting Configuration**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `enabled` | `boolean` | ❌ | `false` | `true\|false` | Enable rate limiting |
| `global_limit` | `integer` | ❌ | `10000` | `1 <= x <= 1000000` | Global messages per second |
| `per_client_limit` | `integer` | ❌ | `100` | `1 <= x <= 10000` | Per-client messages per second |
| `window_size` | `integer` | ❌ | `60` | `1 <= x <= 3600` | Rate limiting window (seconds) |

## ⚡ Performance Configuration

### **Schema Definition**

```yaml
performance:
  message_buffer_size: integer   # Optional: Message buffer size
  validation_cache_size: integer # Optional: Validation cache size
  connection_pool_size: integer  # Optional: Connection pool size
  worker_threads: integer        # Optional: Worker thread count
  batch_size: integer           # Optional: Batch processing size
  
  timeouts:                     # Optional: Timeout settings
    mqtt_connect: integer       # Optional: MQTT connection timeout
    validation: integer         # Optional: Validation timeout
    database_write: integer     # Optional: Database write timeout
    
  memory:                       # Optional: Memory settings
    max_heap_size: string      # Optional: Maximum heap size
    gc_threshold: integer      # Optional: Garbage collection threshold
```

### **Performance Field Specifications**

| Field | Type | Required | Default | Validation | Description |
|-------|------|----------|---------|------------|-------------|
| `message_buffer_size` | `integer` | ❌ | `10000` | `100 <= x <= 100000` | Internal message buffer size |
| `validation_cache_size` | `integer` | ❌ | `1000` | `10 <= x <= 10000` | Schema validation cache entries |
| `connection_pool_size` | `integer` | ❌ | `10` | `1 <= x <= 100` | MQTT connection pool size |
| `worker_threads` | `integer` | ❌ | `4` | `1 <= x <= 32` | Validation worker threads |
| `batch_size` | `integer` | ❌ | `100` | `1 <= x <= 1000` | Message batch processing size |

## 📝 Configuration Validation

### **Validation Rules**

The configuration loader performs comprehensive validation:

1. **Required Field Validation**: Ensures all required fields are present
2. **Type Validation**: Validates field types against schema
3. **Range Validation**: Checks numeric values are within valid ranges  
4. **Format Validation**: Validates string formats (URLs, paths, patterns)
5. **Cross-Field Validation**: Validates relationships between fields
6. **File Existence**: Checks that referenced files exist
7. **Network Connectivity**: Validates broker connectivity (optional)

### **Example Validation Script**

```bash
# Validate configuration file
python src/config_loader.py --validate config/rules.yaml

# Validate and test broker connections
python src/config_loader.py --validate --test-connections config/rules.yaml

# Generate configuration schema
python src/config_loader.py --schema > config-schema.json
```

### **Common Validation Errors**

1. **Missing Required Fields**
   ```
   ValidationError: Missing required field 'global.proxy_mode'
   ```

2. **Invalid Field Types**
   ```
   ValidationError: Field 'global.max_message_size' must be integer, got string
   ```

3. **Out of Range Values**
   ```
   ValidationError: Field 'brokers.subscriber.port' must be between 1 and 65535
   ```

4. **Invalid File Paths**
   ```
   ValidationError: Schema file 'schemas/missing.json' does not exist
   ```

5. **Invalid Topic Patterns**
   ```
   ValidationError: Topic pattern 'devices/+/+/telemetry/+' contains too many wildcards
   ```

## 📁 Configuration Templates

### **Minimal Configuration**
```yaml
global:
  proxy_mode: "production"

brokers:
  subscriber:
    host: "localhost"
    port: 1883
    client_id: "proxy-sub"
  publisher:
    host: "localhost"
    port: 1883
    client_id: "proxy-pub"

validation:
  topic_patterns:
    - "devices/+/telemetry"
  schema_mappings:
    "devices/+/telemetry": "simple_telemetry"
  schema_files:
    simple_telemetry:
      type: "json"
      path: "schemas/simple.json"
```

### **Production Configuration**
```yaml
global:
  proxy_mode: "production"
  log_level: "INFO"
  max_message_size: 2097152
  message_timeout: 30
  instance_id: "proxy-prod-01"

brokers:
  subscriber:
    host: "mqtt-internal.company.com"
    port: 8883
    client_id: "schema-proxy-sub-01"
    username: "proxy_service"
    password: "${MQTT_PASSWORD}"
    ssl: true
    ca_certs: "/etc/ssl/certs/ca.pem"
    certfile: "/etc/ssl/certs/client.crt"
    keyfile: "/etc/ssl/private/client.key"
    tls_version: "TLSv1.3"
    
  publisher:
    host: "mqtt-upstream.company.com"
    port: 8883
    client_id: "schema-proxy-pub-01"
    ssl: true

validation:
  topic_patterns:
    - "devices/+/telemetry"
    - "sensors/+/+"
    - "alerts/critical/+"
    - "logs/application/+/errors"
    
  schema_mappings:
    "devices/+/telemetry": "device_telemetry_v2"
    "sensors/temperature/+": "temperature_v1"
    "sensors/humidity/+": "humidity_v1"
    "alerts/critical/+": "critical_alert_v1"
    
  schema_files:
    device_telemetry_v2:
      type: "protobuf"
      path: "schemas/device_telemetry_v2.proto"
      message_type: "DeviceTelemetry"
    temperature_v1:
      type: "json"
      path: "schemas/temperature_v1.json"
    humidity_v1:
      type: "json"
      path: "schemas/humidity_v1.json"
    critical_alert_v1:
      type: "json"
      path: "schemas/critical_alert_v1.json"
      
  validation_mode: "strict"
  cache_size: 2000

storage:
  quarantine:
    driver: "postgresql"
    host: "db.company.com"
    port: 5432
    database: "mqtt_proxy"
    username: "proxy_db_user"
    password: "${DB_PASSWORD}"
    pool_size: 20
    ssl_mode: "require"
    cleanup_days: 90
    
  payloads:
    path: "/data/mqtt-proxy/payloads"
    compression: "lz4"
    max_file_size: "100MB"
    retention_days: 30

monitoring:
  metrics:
    enabled: true
    port: 9100
    path: "/metrics"
    update_interval: 5
    custom_labels:
      environment: "production"
      datacenter: "us-east-1"
      
  health_check:
    enabled: true
    port: 8080
    path: "/health"
    timeout: 5
    
  audit:
    enabled: true
    format: "json"
    destination: "file"
    file_path: "/var/log/mqtt-proxy/audit.log"
    rotation: "daily"
    retention_days: 365

security:
  authentication:
    enabled: true
    method: "jwt"
    jwt:
      secret_key: "${JWT_SECRET}"
      algorithm: "HS256"
      expiration: 3600
      
  rate_limiting:
    enabled: true
    global_limit: 50000
    per_client_limit: 500
    window_size: 60

performance:
  message_buffer_size: 50000
  validation_cache_size: 5000
  connection_pool_size: 20
  worker_threads: 8
  batch_size: 200
  
  timeouts:
    mqtt_connect: 15
    validation: 10
    database_write: 5
    
  memory:
    max_heap_size: "2GB"
    gc_threshold: 1000
```

---

This configuration specification provides complete documentation for all available options in the MQTT Schema Governance Proxy. Use it as a reference when setting up your deployment.
