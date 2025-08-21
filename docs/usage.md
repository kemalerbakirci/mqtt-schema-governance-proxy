# MQTT Schema Governance Proxy - Usage Guide

[![Guide](https://img.shields.io/badge/guide-comprehensive-green.svg)](#)
[![Examples](https://img.shields.io/badge/examples-included-blue.svg)](#)
[![Support](https://img.shields.io/badge/support-community-yellow.svg)](#)

## 🚀 Quick Start

### **1. Installation**

```bash
# Clone the repository
git clone https://github.com/yourusername/mqtt-schema-governance-proxy.git
cd mqtt-schema-governance-proxy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### **2. Basic Configuration**

Create your configuration file:

```bash
cp config/rules.yaml config/my-rules.yaml
```

Edit `config/my-rules.yaml`:

```yaml
global:
  proxy_mode: "production"
  log_level: "INFO"

brokers:
  subscriber:
    host: "localhost"
    port: 1883
    client_id: "schema-proxy-sub"
  
  publisher:
    host: "localhost"
    port: 1883
    client_id: "schema-proxy-pub"

validation:
  topic_patterns:
    - "devices/+/telemetry"
    - "sensors/temperature/+"
  
  schema_mappings:
    "devices/+/telemetry": "telemetry_v2"
    "sensors/temperature/+": "temperature_v1"
  
  schema_files:
    telemetry_v2:
      type: "protobuf"
      path: "schemas/telemetry_v2.proto"
    temperature_v1:
      type: "json"
      path: "schemas/temperature_v1.json"
```

### **3. Run the Proxy**

```bash
python src/main.py --config config/my-rules.yaml
```

## 📋 Detailed Configuration

### **Global Settings**

```yaml
global:
  proxy_mode: "production"          # production, development, testing
  log_level: "INFO"                 # DEBUG, INFO, WARNING, ERROR
  max_message_size: 1048576         # 1MB default
  message_timeout: 30               # seconds
  dry_run: false                    # true = validate only, don't forward
```

### **Broker Configuration**

#### **Basic MQTT**
```yaml
brokers:
  subscriber:
    host: "mqtt.example.com"
    port: 1883
    client_id: "proxy-subscriber"
    username: "user"
    password: "pass"
    keepalive: 60
    
  publisher:
    host: "mqtt-upstream.example.com"
    port: 1883
    client_id: "proxy-publisher"
```

#### **Secure MQTT (TLS/SSL)**
```yaml
brokers:
  subscriber:
    host: "secure-mqtt.example.com"
    port: 8883
    ssl: true
    ca_certs: "/path/to/ca.pem"
    certfile: "/path/to/client.crt"
    keyfile: "/path/to/client.key"
    tls_version: "TLSv1.2"
    ciphers: "HIGH:!aNULL:!eNULL:!EXPORT:!DES:!RC4:!MD5:!PSK:!SRP:!CAMELLIA"
```

#### **WebSocket MQTT**
```yaml
brokers:
  subscriber:
    host: "ws-mqtt.example.com"
    port: 9001
    transport: "websockets"
    websocket_path: "/mqtt"
    websocket_headers:
      "Authorization": "Bearer token123"
```

### **Topic Validation Rules**

#### **MQTT Wildcards**
```yaml
validation:
  topic_patterns:
    - "devices/+/telemetry"          # Single level wildcard
    - "sensors/#"                    # Multi level wildcard
    - "alerts/critical/+"            # Specific path with wildcard
    - "logs/application/+/errors"    # Wildcard in middle
```

#### **Client-Specific Rules**
```yaml
validation:
  client_rules:
    "iot-device-001":
      allowed_topics:
        - "devices/iot-device-001/telemetry"
        - "devices/iot-device-001/status"
    
    "sensor-gateway":
      allowed_topics:
        - "sensors/+/temperature"
        - "sensors/+/humidity"
        - "gateways/sensor-gateway/health"
```

### **Schema Configuration**

#### **JSON Schema**
```yaml
validation:
  schema_files:
    temperature_sensor:
      type: "json"
      path: "schemas/temperature.json"
      strict: true                   # Enforce additional properties
      draft: "draft7"               # JSON Schema draft version
```

Example JSON Schema (`schemas/temperature.json`):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "deviceId": {
      "type": "string",
      "pattern": "^[A-Z0-9-]+$"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    },
    "temperature": {
      "type": "number",
      "minimum": -50,
      "maximum": 100
    },
    "unit": {
      "type": "string",
      "enum": ["celsius", "fahrenheit"]
    }
  },
  "required": ["deviceId", "timestamp", "temperature", "unit"],
  "additionalProperties": false
}
```

#### **Protocol Buffers**
```yaml
validation:
  schema_files:
    telemetry_data:
      type: "protobuf"
      path: "schemas/telemetry.proto"
      message_type: "TelemetryMessage"
```

Example Protocol Buffer schema (`schemas/telemetry.proto`):
```protobuf
syntax = "proto3";

message TelemetryMessage {
  string device_id = 1;
  int64 timestamp = 2;
  map<string, double> metrics = 3;
  repeated string tags = 4;
  
  message Location {
    double latitude = 1;
    double longitude = 2;
    double altitude = 3;
  }
  
  Location location = 5;
}
```

### **Storage Configuration**

#### **SQLite (Default)**
```yaml
storage:
  quarantine:
    driver: "sqlite"
    path: "data/quarantine.db"
    max_size: "10GB"
    cleanup_days: 30
    
  payloads:
    path: "data/payloads"
    compression: "gzip"
    max_file_size: "100MB"
```

#### **PostgreSQL (Enterprise)**
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
    ssl_mode: "require"
```

### **Monitoring Configuration**

```yaml
monitoring:
  metrics:
    enabled: true
    port: 9100
    path: "/metrics"
    update_interval: 5              # seconds
    
  health_check:
    enabled: true
    port: 8080
    path: "/health"
    
  audit:
    enabled: true
    format: "json"                  # json, text, syslog
    destination: "file"             # file, stdout, syslog
    file_path: "logs/audit.log"
    rotation: "daily"
    retention_days: 90
```

## 🔧 Command Line Usage

### **Basic Commands**

```bash
# Start with default configuration
python src/main.py

# Start with custom configuration
python src/main.py --config /path/to/config.yaml

# Dry run mode (validate only, don't forward)
python src/main.py --dry-run

# Increase logging verbosity
python src/main.py --log-level DEBUG

# Validate configuration without starting
python src/main.py --validate-config --config config.yaml
```

### **Advanced Options**

```bash
# Override configuration values
python src/main.py \
  --config config.yaml \
  --override global.log_level=DEBUG \
  --override brokers.subscriber.host=localhost

# Run with specific modules disabled
python src/main.py --disable-metrics --disable-audit

# Performance testing mode
python src/main.py --performance-test --test-duration 60

# Schema validation test
python src/main.py --test-schema schemas/temperature.json
```

## 📊 Monitoring & Observability

### **Prometheus Metrics**

Access metrics at `http://localhost:9100/metrics`:

```bash
# View all metrics
curl http://localhost:9100/metrics

# Key metrics to monitor
curl -s http://localhost:9100/metrics | grep -E "(mqtt_messages|validation_errors|quarantine_count)"
```

**Important Metrics:**
- `mqtt_messages_total`: Total messages processed
- `mqtt_messages_valid_total`: Successfully validated messages
- `mqtt_messages_invalid_total`: Failed validation messages
- `mqtt_validation_duration_seconds`: Validation latency
- `mqtt_quarantine_size_bytes`: Quarantine storage usage

### **Health Checks**

```bash
# Basic health check
curl http://localhost:8080/health

# Detailed health status
curl http://localhost:8080/health/detailed

# Component-specific health
curl http://localhost:8080/health/mqtt
curl http://localhost:8080/health/storage
curl http://localhost:8080/health/validation
```

### **Log Analysis**

**Structured JSON Logs:**
```bash
# Follow live logs
tail -f logs/proxy.log | jq '.'

# Filter validation errors
cat logs/proxy.log | jq 'select(.level == "ERROR" and .component == "validator")'

# Analyze message volume by topic
cat logs/audit.log | jq -r '.topic' | sort | uniq -c | sort -nr
```

## 🧪 Testing & Validation

### **Unit Testing**

```bash
# Run all tests
python -m pytest tests/

# Run specific test module
python -m pytest tests/test_schema_validator.py

# Run with coverage
python -m pytest --cov=src tests/

# Run performance tests
python -m pytest tests/test_performance.py --benchmark-only
```

### **Integration Testing**

```bash
# Test with real MQTT broker
python tests/integration/test_full_flow.py --broker-host localhost

# Load testing
python tests/load/generate_traffic.py --rate 1000 --duration 60

# Schema validation testing
python scripts/test_schemas.py --schema-dir schemas/
```

### **Manual Testing**

**Send Test Messages:**
```bash
# Install MQTT client
pip install paho-mqtt

# Send valid message
python -c "
import paho.mqtt.client as mqtt
import json

client = mqtt.Client()
client.connect('localhost', 1883, 60)

payload = json.dumps({
    'deviceId': 'TEMP-001',
    'timestamp': '2024-01-15T10:30:00Z',
    'temperature': 23.5,
    'unit': 'celsius'
})

client.publish('devices/TEMP-001/telemetry', payload)
client.disconnect()
"

# Send invalid message (will be quarantined)
python -c "
import paho.mqtt.client as mqtt
import json

client = mqtt.Client()
client.connect('localhost', 1883, 60)

payload = json.dumps({
    'deviceId': 'INVALID',
    'temperature': 'not-a-number'
})

client.publish('devices/INVALID/telemetry', payload)
client.disconnect()
"
```

## 🔄 Operational Procedures

### **Daily Operations**

**Monitor System Health:**
```bash
# Check process status
ps aux | grep "main.py"

# Monitor resource usage
htop -p $(pgrep -f "main.py")

# Check log for errors
tail -100 logs/proxy.log | grep -i error
```

**Review Quarantine:**
```bash
# List quarantined messages
python scripts/replay_quarantine.py --list --days 1

# Export quarantine summary
python scripts/quarantine_report.py --format csv --output daily_report.csv
```

### **Troubleshooting**

**Common Issues:**

1. **High Memory Usage**
   ```bash
   # Check schema cache size
   curl http://localhost:8080/debug/cache-stats
   
   # Clear schema cache
   curl -X POST http://localhost:8080/debug/clear-cache
   ```

2. **MQTT Connection Issues**
   ```bash
   # Test MQTT connectivity
   python -c "
   import paho.mqtt.client as mqtt
   client = mqtt.Client()
   result = client.connect('broker-host', 1883, 10)
   print('Connected' if result == 0 else 'Failed')
   "
   ```

3. **Schema Validation Failures**
   ```bash
   # Validate schema files
   python scripts/validate_schemas.py --schema-dir schemas/
   
   # Test specific schema
   python scripts/test_schema.py --schema schemas/temperature.json --data test_data.json
   ```

### **Maintenance**

**Database Cleanup:**
```bash
# Clean old quarantine data (older than 30 days)
python scripts/cleanup_quarantine.py --days 30

# Optimize database
python scripts/optimize_database.py

# Backup quarantine data
python scripts/backup_quarantine.py --output backup_$(date +%Y%m%d).sql
```

**Log Rotation:**
```bash
# Manual log rotation
logrotate --force config/logrotate.conf

# Compress old logs
gzip logs/proxy.log.*
```

## 🚀 Production Deployment

### **Docker Deployment**

```bash
# Build image
docker build -t mqtt-schema-proxy .

# Run container
docker run -d \
  --name mqtt-proxy \
  -p 9100:9100 \
  -p 8080:8080 \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/schemas:/app/schemas \
  -v $(pwd)/data:/app/data \
  mqtt-schema-proxy
```

### **Docker Compose**

```yaml
version: '3.8'
services:
  mqtt-proxy:
    build: .
    ports:
      - "9100:9100"
      - "8080:8080"
    volumes:
      - ./config:/app/config
      - ./schemas:/app/schemas
      - ./data:/app/data
    environment:
      - PYTHONPATH=/app
    restart: unless-stopped
    
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-storage:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  grafana-storage:
```

### **Kubernetes Deployment**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mqtt-schema-proxy
spec:
  replicas: 3
  selector:
    matchLabels:
      app: mqtt-schema-proxy
  template:
    metadata:
      labels:
        app: mqtt-schema-proxy
    spec:
      containers:
      - name: proxy
        image: mqtt-schema-proxy:latest
        ports:
        - containerPort: 9100
          name: metrics
        - containerPort: 8080
          name: health
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: schemas
          mountPath: /app/schemas
      volumes:
      - name: config
        configMap:
          name: mqtt-proxy-config
      - name: schemas
        configMap:
          name: mqtt-proxy-schemas
---
apiVersion: v1
kind: Service
metadata:
  name: mqtt-schema-proxy
spec:
  selector:
    app: mqtt-schema-proxy
  ports:
  - name: metrics
    port: 9100
    targetPort: 9100
  - name: health
    port: 8080
    targetPort: 8080
```

## 📈 Performance Tuning

### **Optimization Settings**

```yaml
performance:
  message_buffer_size: 10000        # Buffer for incoming messages
  validation_cache_size: 1000       # Schema validation cache
  connection_pool_size: 10          # MQTT connection pool
  worker_threads: 4                 # Validation worker threads
  batch_size: 100                   # Batch processing size
  
  timeouts:
    mqtt_connect: 10                # seconds
    validation: 5                   # seconds
    database_write: 2               # seconds
```

### **Resource Monitoring**

```bash
# Monitor proxy performance
watch -n 1 'curl -s http://localhost:9100/metrics | grep -E "(duration|rate)"'

# System resource usage
watch -n 1 'ps -o pid,ppid,cmd,%mem,%cpu -p $(pgrep -f main.py)'

# Network connections
netstat -an | grep :1883
```

---

This comprehensive usage guide should help you get the most out of your MQTT Schema Governance Proxy deployment. For additional support, consult the API documentation or reach out to the community.
