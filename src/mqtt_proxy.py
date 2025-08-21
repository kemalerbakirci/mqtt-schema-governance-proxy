"""
MQTT Proxy Module

This module implements the core MQTT proxy functionality that intercepts,
validates, and forwards MQTT messages based on configured rules.
"""

import asyncio
import json
import logging
import os
import ssl
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from contextlib import asynccontextmanager

import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTTMessage

from config_loader import ProxyConfig as LoadedProxyConfig
from topic_validator import TopicValidator
from schema_validator import SchemaValidator
from quarantine_store import QuarantineStore
from audit_logger import AuditLogger
from metrics_exporter import MetricsExporter


@dataclass
class BrokerConfig:
    """MQTT broker connection configuration."""
    host: str = "localhost"
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    use_tls: bool = False
    ca_cert: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None
    keepalive: int = 60
    clean_session: bool = True


@dataclass
class ProxyConfig:
    """Proxy-specific configuration."""
    listen_host: str = "0.0.0.0"
    listen_port: int = 1884
    upstream_host: str = "localhost"
    upstream_port: int = 1883
    client_id_prefix: str = "schema-proxy"
    max_message_size: int = 1024 * 1024  # 1MB
    validation_timeout: float = 5.0


class MQTTProxy:
    """
    MQTT Schema Governance Proxy
    
    Acts as an MQTT broker proxy that validates incoming messages
    against configured topic and schema rules before forwarding.
    """
    
    def __init__(
        self,
        config: LoadedProxyConfig,
        quarantine_store: QuarantineStore,
        audit_logger: AuditLogger,
        metrics_exporter: MetricsExporter,
        dry_run: bool = False
    ):
        self.config = config
        self.quarantine_store = quarantine_store
        self.audit_logger = audit_logger
        self.metrics_exporter = metrics_exporter
        self.dry_run = dry_run
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize validators
        self.topic_validator = TopicValidator(config)
        self.schema_validator = SchemaValidator(config)
        
        # MQTT clients
        self.subscriber_client: Optional[mqtt.Client] = None
        self.publisher_client: Optional[mqtt.Client] = None
        
        # Configuration
        self.broker_config = self._load_broker_config()
        self.proxy_config = self._load_proxy_config()
        
        # State
        self.is_running = False
        self.connected_upstream = False
        
    def _load_broker_config(self) -> BrokerConfig:
        """Load broker configuration from config and environment."""
        broker_cfg = self.config.broker_config if hasattr(self.config, 'broker_config') else {}
        
        return BrokerConfig(
            host=broker_cfg.get('host', os.getenv('MQTT_BROKER_HOST', 'localhost')),
            port=broker_cfg.get('port', int(os.getenv('MQTT_BROKER_PORT', '1883'))),
            username=broker_cfg.get('username', os.getenv('MQTT_USERNAME')),
            password=broker_cfg.get('password', os.getenv('MQTT_PASSWORD')),
            use_tls=broker_cfg.get('use_tls', os.getenv('MQTT_USE_TLS', '').lower() == 'true'),
            ca_cert=broker_cfg.get('ca_cert', os.getenv('MQTT_TLS_CA')),
            client_cert=broker_cfg.get('client_cert', os.getenv('MQTT_TLS_CERT')),
            client_key=broker_cfg.get('client_key', os.getenv('MQTT_TLS_KEY')),
            keepalive=broker_cfg.get('keepalive', 60),
            clean_session=broker_cfg.get('clean_session', True)
        )
    
    def _load_proxy_config(self) -> ProxyConfig:
        """Load proxy configuration."""
        proxy_cfg = self.config.proxy_config if hasattr(self.config, 'proxy_config') else {}
        
        return ProxyConfig(
            listen_host=proxy_cfg.get('listen_host', '0.0.0.0'),
            listen_port=proxy_cfg.get('listen_port', 1884),
            upstream_host=proxy_cfg.get('upstream_host', self.broker_config.host),
            upstream_port=proxy_cfg.get('upstream_port', self.broker_config.port),
            client_id_prefix=proxy_cfg.get('client_id_prefix', 'schema-proxy'),
            max_message_size=proxy_cfg.get('max_message_size', 1024 * 1024),
            validation_timeout=proxy_cfg.get('validation_timeout', 5.0)
        )
    
    async def start(self):
        """Start the MQTT proxy."""
        if self.is_running:
            raise RuntimeError("Proxy is already running")
        
        try:
            self.logger.info("Starting MQTT Schema Governance Proxy...")
            
            # Initialize MQTT clients
            await self._setup_clients()
            
            # Connect to upstream broker
            await self._connect_upstream()
            
            # Subscribe to configured topics
            await self._subscribe_to_topics()
            
            self.is_running = True
            self.logger.info("MQTT proxy started successfully")
            
            # Keep running until stopped
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Failed to start proxy: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        """Stop the MQTT proxy."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping MQTT proxy...")
        self.is_running = False
        
        if self.subscriber_client:
            self.subscriber_client.disconnect()
            self.subscriber_client.loop_stop()
        
        if self.publisher_client:
            self.publisher_client.disconnect()
            self.publisher_client.loop_stop()
        
        self.logger.info("MQTT proxy stopped")
    
    async def _setup_clients(self):
        """Initialize MQTT clients for subscribing and publishing."""
        # Subscriber client (receives messages to validate)
        self.subscriber_client = mqtt.Client(
            client_id=f"{self.proxy_config.client_id_prefix}-subscriber",
            clean_session=self.broker_config.clean_session
        )
        
        # Publisher client (forwards valid messages)
        self.publisher_client = mqtt.Client(
            client_id=f"{self.proxy_config.client_id_prefix}-publisher",
            clean_session=self.broker_config.clean_session
        )
        
        # Configure TLS if enabled
        if self.broker_config.use_tls:
            self._configure_tls(self.subscriber_client)
            self._configure_tls(self.publisher_client)
        
        # Configure authentication
        if self.broker_config.username and self.broker_config.password:
            self.subscriber_client.username_pw_set(
                self.broker_config.username,
                self.broker_config.password
            )
            self.publisher_client.username_pw_set(
                self.broker_config.username,
                self.broker_config.password
            )
        
        # Set callbacks
        self.subscriber_client.on_connect = self._on_subscriber_connect
        self.subscriber_client.on_message = self._on_message_received
        self.subscriber_client.on_disconnect = self._on_subscriber_disconnect
        
        self.publisher_client.on_connect = self._on_publisher_connect
        self.publisher_client.on_disconnect = self._on_publisher_disconnect
    
    def _configure_tls(self, client: mqtt.Client):
        """Configure TLS for MQTT client."""
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        
        if self.broker_config.ca_cert:
            context.load_verify_locations(self.broker_config.ca_cert)
        
        if self.broker_config.client_cert and self.broker_config.client_key:
            context.load_cert_chain(
                self.broker_config.client_cert,
                self.broker_config.client_key
            )
        
        client.tls_set_context(context)
    
    async def _connect_upstream(self):
        """Connect to upstream MQTT broker."""
        try:
            # Connect subscriber
            self.subscriber_client.loop_start()
            result = self.subscriber_client.connect(
                self.broker_config.host,
                self.broker_config.port,
                self.broker_config.keepalive
            )
            
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(f"Failed to connect subscriber: {mqtt.error_string(result)}")
            
            # Connect publisher
            self.publisher_client.loop_start()
            result = self.publisher_client.connect(
                self.broker_config.host,
                self.broker_config.port,
                self.broker_config.keepalive
            )
            
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(f"Failed to connect publisher: {mqtt.error_string(result)}")
            
            # Wait for connections
            await asyncio.sleep(1)
            
            if not self.subscriber_client.is_connected() or not self.publisher_client.is_connected():
                raise ConnectionError("Failed to establish connection to upstream broker")
            
            self.connected_upstream = True
            self.logger.info(f"Connected to upstream broker at {self.broker_config.host}:{self.broker_config.port}")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to upstream broker: {e}")
            raise
    
    async def _subscribe_to_topics(self):
        """Subscribe to configured topic patterns."""
        for pattern in self.config.topic_patterns:
            result, mid = self.subscriber_client.subscribe(pattern, qos=1)
            if result != mqtt.MQTT_ERR_SUCCESS:
                self.logger.error(f"Failed to subscribe to {pattern}: {mqtt.error_string(result)}")
            else:
                self.logger.info(f"Subscribed to topic pattern: {pattern}")
    
    def _on_subscriber_connect(self, client, userdata, flags, rc):
        """Callback for subscriber connection."""
        if rc == 0:
            self.logger.info("Subscriber connected to broker")
        else:
            self.logger.error(f"Subscriber connection failed with code {rc}")
    
    def _on_subscriber_disconnect(self, client, userdata, rc):
        """Callback for subscriber disconnection."""
        if rc != 0:
            self.logger.warning("Subscriber disconnected unexpectedly")
        else:
            self.logger.info("Subscriber disconnected")
    
    def _on_publisher_connect(self, client, userdata, flags, rc):
        """Callback for publisher connection."""
        if rc == 0:
            self.logger.info("Publisher connected to broker")
        else:
            self.logger.error(f"Publisher connection failed with code {rc}")
    
    def _on_publisher_disconnect(self, client, userdata, rc):
        """Callback for publisher disconnection."""
        if rc != 0:
            self.logger.warning("Publisher disconnected unexpectedly")
        else:
            self.logger.info("Publisher disconnected")
    
    def _on_message_received(self, client, userdata, message: MQTTMessage):
        """Handle received MQTT message."""
        try:
            # Run validation in async context
            asyncio.create_task(self._process_message(message))
        except Exception as e:
            self.logger.error(f"Error processing message: {e}")
    
    async def _process_message(self, message: MQTTMessage):
        """Process and validate an MQTT message."""
        topic = message.topic
        payload = message.payload
        
        try:
            # Check message size
            if len(payload) > self.proxy_config.max_message_size:
                await self._handle_invalid_message(
                    topic, payload, f"Message too large: {len(payload)} bytes"
                )
                return
            
            # Validate topic
            topic_valid, topic_reason = self.topic_validator.validate(topic)
            
            if not topic_valid:
                await self._handle_invalid_message(topic, payload, f"Topic validation failed: {topic_reason}")
                return
            
            # Get schema for topic
            schema_id = self.config.get_schema_for_topic(topic)
            if not schema_id:
                await self._handle_invalid_message(topic, payload, "No schema mapping found for topic")
                return
            
            # Validate payload against schema
            schema_valid, schema_reason = self.schema_validator.validate(schema_id, payload)
            
            if not schema_valid:
                await self._handle_invalid_message(topic, payload, f"Schema validation failed: {schema_reason}")
                return
            
            # Message is valid - forward it
            await self._handle_valid_message(topic, payload, schema_id)
            
        except asyncio.TimeoutError:
            await self._handle_invalid_message(topic, payload, "Validation timeout")
        except Exception as e:
            self.logger.error(f"Error processing message for topic {topic}: {e}")
            await self._handle_invalid_message(topic, payload, f"Processing error: {str(e)}")
    
    async def _handle_valid_message(self, topic: str, payload: bytes, schema_id: str):
        """Handle a valid message by forwarding it."""
        try:
            # Log successful validation
            await self.audit_logger.log_message(
                topic=topic,
                schema_id=schema_id,
                status="valid",
                payload_size=len(payload)
            )
            
            # Update metrics
            self.metrics_exporter.increment_messages_total("valid")
            
            # Forward message if not in dry run mode
            if not self.dry_run:
                result = self.publisher_client.publish(topic, payload, qos=1)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    self.logger.error(f"Failed to publish message to {topic}: {mqtt.error_string(result.rc)}")
                else:
                    self.logger.debug(f"Forwarded valid message to {topic}")
            else:
                self.logger.info(f"DRY RUN: Would forward valid message to {topic}")
            
        except Exception as e:
            self.logger.error(f"Error handling valid message: {e}")
    
    async def _handle_invalid_message(self, topic: str, payload: bytes, reason: str):
        """Handle an invalid message by quarantining it."""
        try:
            # Store in quarantine
            await self.quarantine_store.store(topic, payload, reason)
            
            # Log rejection
            await self.audit_logger.log_message(
                topic=topic,
                schema_id=None,
                status="invalid",
                reason=reason,
                payload_size=len(payload)
            )
            
            # Update metrics
            self.metrics_exporter.increment_messages_total("invalid")
            self.metrics_exporter.increment_quarantine_count()
            
            self.logger.warning(f"Message quarantined - Topic: {topic}, Reason: {reason}")
            
        except Exception as e:
            self.logger.error(f"Error handling invalid message: {e}")


if __name__ == "__main__":
    # Example usage
    import sys
    sys.path.append('..')
    
    from config_loader import load_config
    
    async def main():
        config = load_config("../config/rules.yaml")
        quarantine_store = QuarantineStore()
        audit_logger = AuditLogger()
        metrics_exporter = MetricsExporter()
        
        proxy = MQTTProxy(config, quarantine_store, audit_logger, metrics_exporter)
        
        try:
            await proxy.start()
        except KeyboardInterrupt:
            await proxy.stop()
    
    asyncio.run(main())
