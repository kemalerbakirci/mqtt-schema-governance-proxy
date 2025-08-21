"""
Metrics Exporter Module

This module provides Prometheus-compatible metrics for the MQTT Schema Governance Proxy.
Exports metrics about message processing, validation, and quarantine statistics.
"""

import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from threading import Lock
import asyncio

from prometheus_client import Counter, Histogram, Gauge, start_http_server, CollectorRegistry, REGISTRY
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, HistogramMetricFamily


@dataclass
class MetricsConfig:
    """Configuration for metrics exporter."""
    port: int = 9100
    host: str = "0.0.0.0"
    path: str = "/metrics"
    enabled: bool = True


class MetricsExporter:
    """
    Prometheus metrics exporter for MQTT Schema Governance Proxy.
    
    Exposes metrics about:
    - Total messages processed (valid/invalid)
    - Quarantine statistics
    - Validation latency
    - Topic and schema usage patterns
    """
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        self.config = config or MetricsConfig()
        self.logger = logging.getLogger(__name__)
        
        # Thread safety
        self._lock = Lock()
        
        # HTTP server handle
        self._http_server = None
        
        # Custom registry for isolation
        self.registry = CollectorRegistry()
        
        # Initialize metrics
        self._init_metrics()
        
        # Internal counters for custom metrics
        self._topic_counts: Dict[str, int] = {}
        self._schema_counts: Dict[str, int] = {}
        self._validation_times: Dict[str, float] = {}
        
    def _init_metrics(self):
        """Initialize Prometheus metrics."""
        # Message counters
        self.messages_total = Counter(
            'mqtt_messages_total',
            'Total number of MQTT messages processed',
            ['status'],  # 'valid' or 'invalid'
            registry=self.registry
        )
        
        # Quarantine counter
        self.quarantine_count = Counter(
            'mqtt_quarantine_total',
            'Total number of messages quarantined',
            registry=self.registry
        )
        
        # Current quarantine size (gauge)
        self.quarantine_size = Gauge(
            'mqtt_quarantine_size',
            'Current number of unprocessed quarantined messages',
            registry=self.registry
        )
        
        # Validation latency histogram
        self.validation_latency = Histogram(
            'mqtt_validation_latency_seconds',
            'Time spent validating messages',
            ['validation_type'],  # 'topic' or 'schema'
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
            registry=self.registry
        )
        
        # Topic usage counter
        self.topic_usage = Counter(
            'mqtt_topic_usage_total',
            'Number of messages per topic pattern',
            ['topic_pattern'],
            registry=self.registry
        )
        
        # Schema usage counter
        self.schema_usage = Counter(
            'mqtt_schema_usage_total',
            'Number of messages per schema',
            ['schema_id'],
            registry=self.registry
        )
        
        # Processing time per message
        self.message_processing_time = Histogram(
            'mqtt_message_processing_seconds',
            'Total time to process each message',
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        # Validation errors by type
        self.validation_errors = Counter(
            'mqtt_validation_errors_total',
            'Number of validation errors by type',
            ['error_type'],  # 'topic_invalid', 'schema_missing', 'schema_invalid', etc.
            registry=self.registry
        )
        
        # Connection status
        self.connection_status = Gauge(
            'mqtt_connection_status',
            'MQTT broker connection status (1=connected, 0=disconnected)',
            ['connection_type'],  # 'subscriber' or 'publisher'
            registry=self.registry
        )
        
        # Proxy uptime
        self.proxy_uptime = Gauge(
            'mqtt_proxy_uptime_seconds',
            'Proxy uptime in seconds',
            registry=self.registry
        )
        
        # Message size histogram
        self.message_size = Histogram(
            'mqtt_message_size_bytes',
            'Size of MQTT messages in bytes',
            buckets=[64, 256, 1024, 4096, 16384, 65536, 262144, 1048576],
            registry=self.registry
        )
        
        self.logger.info("Prometheus metrics initialized")
    
    async def start(self):
        """Start the metrics HTTP server."""
        if not self.config.enabled:
            self.logger.info("Metrics exporter disabled")
            return
        
        try:
            # Start HTTP server for metrics
            self._http_server = start_http_server(
                self.config.port,
                addr=self.config.host,
                registry=self.registry
            )
            
            # Set initial uptime
            self._start_time = time.time()
            
            self.logger.info(f"Metrics server started on {self.config.host}:{self.config.port}{self.config.path}")
            
            # Start background metric updates
            asyncio.create_task(self._update_runtime_metrics())
            
        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")
            raise
    
    async def stop(self):
        """Stop the metrics HTTP server."""
        if self._http_server:
            # Note: prometheus_client doesn't provide a clean shutdown method
            # The server will stop when the process exits
            self.logger.info("Metrics server shutdown requested")
    
    async def _update_runtime_metrics(self):
        """Update runtime metrics periodically."""
        while True:
            try:
                # Update uptime
                if hasattr(self, '_start_time'):
                    uptime = time.time() - self._start_time
                    self.proxy_uptime.set(uptime)
                
                # Sleep for 30 seconds before next update
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error updating runtime metrics: {e}")
                await asyncio.sleep(30)
    
    def increment_messages_total(self, status: str):
        """Increment total messages counter."""
        with self._lock:
            self.messages_total.labels(status=status).inc()
    
    def increment_quarantine_count(self):
        """Increment quarantine counter."""
        with self._lock:
            self.quarantine_count.inc()
    
    def set_quarantine_size(self, size: int):
        """Set current quarantine size."""
        with self._lock:
            self.quarantine_size.set(size)
    
    def record_validation_latency(self, validation_type: str, latency_seconds: float):
        """Record validation latency."""
        with self._lock:
            self.validation_latency.labels(validation_type=validation_type).observe(latency_seconds)
    
    def increment_topic_usage(self, topic_pattern: str):
        """Increment topic usage counter."""
        with self._lock:
            # Sanitize topic pattern for Prometheus label
            sanitized_pattern = self._sanitize_label(topic_pattern)
            self.topic_usage.labels(topic_pattern=sanitized_pattern).inc()
    
    def increment_schema_usage(self, schema_id: str):
        """Increment schema usage counter."""
        with self._lock:
            # Sanitize schema ID for Prometheus label
            sanitized_schema = self._sanitize_label(schema_id)
            self.schema_usage.labels(schema_id=sanitized_schema).inc()
    
    def record_message_processing_time(self, processing_time_seconds: float):
        """Record message processing time."""
        with self._lock:
            self.message_processing_time.observe(processing_time_seconds)
    
    def increment_validation_errors(self, error_type: str):
        """Increment validation errors counter."""
        with self._lock:
            self.validation_errors.labels(error_type=error_type).inc()
    
    def set_connection_status(self, connection_type: str, connected: bool):
        """Set connection status."""
        with self._lock:
            status = 1 if connected else 0
            self.connection_status.labels(connection_type=connection_type).set(status)
    
    def record_message_size(self, size_bytes: int):
        """Record message size."""
        with self._lock:
            self.message_size.observe(size_bytes)
    
    def _sanitize_label(self, label: str) -> str:
        """Sanitize label value for Prometheus."""
        # Replace problematic characters with underscores
        import re
        sanitized = re.sub(r'[^a-zA-Z0-9_:]', '_', label)
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"_{sanitized}"
        return sanitized[:100]  # Limit length
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of current metrics."""
        with self._lock:
            summary = {
                'messages_processed': {
                    'valid': self.messages_total.labels(status='valid')._value._value,
                    'invalid': self.messages_total.labels(status='invalid')._value._value
                },
                'quarantine': {
                    'total_quarantined': self.quarantine_count._value._value,
                    'current_size': self.quarantine_size._value._value
                },
                'connections': {
                    'subscriber': self.connection_status.labels(connection_type='subscriber')._value._value,
                    'publisher': self.connection_status.labels(connection_type='publisher')._value._value
                },
                'uptime_seconds': self.proxy_uptime._value._value if hasattr(self.proxy_uptime, '_value') else 0
            }
            
            return summary
    
    # Context manager for timing operations
    class TimingContext:
        """Context manager for timing operations."""
        
        def __init__(self, exporter: 'MetricsExporter', metric_name: str, **labels):
            self.exporter = exporter
            self.metric_name = metric_name
            self.labels = labels
            self.start_time = None
        
        def __enter__(self):
            self.start_time = time.time()
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.start_time is not None:
                duration = time.time() - self.start_time
                
                if self.metric_name == 'validation_latency':
                    self.exporter.record_validation_latency(
                        self.labels.get('validation_type', 'unknown'),
                        duration
                    )
                elif self.metric_name == 'message_processing':
                    self.exporter.record_message_processing_time(duration)
    
    def time_validation(self, validation_type: str):
        """Context manager for timing validation operations."""
        return self.TimingContext(self, 'validation_latency', validation_type=validation_type)
    
    def time_message_processing(self):
        """Context manager for timing message processing."""
        return self.TimingContext(self, 'message_processing')


# Utility function to get metrics in text format
def get_metrics_text(exporter: MetricsExporter) -> str:
    """Get metrics in Prometheus text format."""
    from prometheus_client import generate_latest
    return generate_latest(exporter.registry).decode('utf-8')


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def test_metrics():
        # Create metrics exporter
        config = MetricsConfig(port=9100)
        exporter = MetricsExporter(config)
        
        # Start metrics server
        await exporter.start()
        
        # Simulate some metrics
        exporter.increment_messages_total('valid')
        exporter.increment_messages_total('valid')
        exporter.increment_messages_total('invalid')
        
        exporter.increment_quarantine_count()
        exporter.set_quarantine_size(5)
        
        exporter.record_validation_latency('topic', 0.001)
        exporter.record_validation_latency('schema', 0.005)
        
        exporter.increment_topic_usage('sensor/+/temperature')
        exporter.increment_schema_usage('temperature:v1')
        
        exporter.set_connection_status('subscriber', True)
        exporter.set_connection_status('publisher', True)
        
        # Use timing context
        with exporter.time_message_processing():
            await asyncio.sleep(0.01)  # Simulate processing
        
        # Print summary
        summary = exporter.get_metrics_summary()
        print("Metrics Summary:")
        for category, values in summary.items():
            print(f"  {category}: {values}")
        
        print(f"\nMetrics available at: http://localhost:{config.port}/metrics")
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await exporter.stop()
    
    # Run test
    asyncio.run(test_metrics())
