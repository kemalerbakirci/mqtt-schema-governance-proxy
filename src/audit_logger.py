"""
Audit Logger Module

This module provides structured logging for all MQTT message processing events.
Logs are emitted in JSON format for easy ingestion by log aggregation systems.
"""

import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import asyncio

from pythonjsonlogger import jsonlogger


@dataclass
class MessageEvent:
    """Represents a message processing event."""
    timestamp: str
    event_type: str  # 'message_received', 'validation_success', 'validation_failed', 'quarantined'
    topic: str
    client_id: Optional[str] = None
    schema_id: Optional[str] = None
    status: str = "unknown"  # 'valid', 'invalid', 'processing'
    reason: Optional[str] = None
    payload_size: int = 0
    processing_time_ms: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class AuditLogger:
    """
    Structured audit logger for MQTT Schema Governance Proxy.
    
    Logs all message processing events in JSON format with consistent structure
    for monitoring, alerting, and compliance purposes.
    """
    
    def __init__(
        self,
        log_file: str = "logs/audit.jsonl",
        console_output: bool = True,
        log_level: str = "INFO"
    ):
        self.log_file = Path(log_file)
        self.console_output = console_output
        
        # Ensure log directory exists
        self.log_file.parent.mkdir(exist_ok=True)
        
        # Setup structured logger
        self.logger = self._setup_logger(log_level)
        
        # Performance tracking
        self._start_times: Dict[str, float] = {}
        
    def _setup_logger(self, log_level: str) -> logging.Logger:
        """Setup JSON structured logger."""
        # Create logger
        logger = logging.getLogger(f"{__name__}.audit")
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # JSON formatter
        json_formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            timestamp=True
        )
        
        # File handler
        file_handler = logging.FileHandler(self.log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(json_formatter)
        logger.addHandler(file_handler)
        
        # Console handler (optional)
        if self.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(json_formatter)
            logger.addHandler(console_handler)
        
        # Prevent propagation to avoid duplicate logs
        logger.propagate = False
        
        return logger
    
    async def log_message(
        self,
        topic: str,
        schema_id: Optional[str] = None,
        status: str = "unknown",
        reason: Optional[str] = None,
        client_id: Optional[str] = None,
        payload_size: int = 0,
        processing_time_ms: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a message processing event.
        
        Args:
            topic: MQTT topic
            schema_id: Schema identifier used for validation
            status: Processing status ('valid', 'invalid', 'processing')
            reason: Reason for status (especially for failures)
            client_id: MQTT client ID (if available)
            payload_size: Size of message payload in bytes
            processing_time_ms: Processing time in milliseconds
            metadata: Additional metadata
        """
        try:
            event = MessageEvent(
                timestamp=datetime.utcnow().isoformat() + "Z",
                event_type=self._determine_event_type(status),
                topic=topic,
                client_id=client_id,
                schema_id=schema_id,
                status=status,
                reason=reason,
                payload_size=payload_size,
                processing_time_ms=processing_time_ms,
                metadata=metadata or {}
            )
            
            # Convert to dict and log
            event_dict = asdict(event)
            
            # Remove None values to keep logs clean
            event_dict = {k: v for k, v in event_dict.items() if v is not None}
            
            # Log the event
            self.logger.info("message_event", extra=event_dict)
            
        except Exception as e:
            # Fallback logging - don't let audit logging break the main flow
            self.logger.error(f"Failed to log message event: {e}")
    
    def _determine_event_type(self, status: str) -> str:
        """Determine event type based on status."""
        if status == "valid":
            return "validation_success"
        elif status == "invalid":
            return "validation_failed"
        elif status == "quarantined":
            return "message_quarantined"
        elif status == "processing":
            return "message_processing"
        else:
            return "message_received"
    
    async def log_system_event(
        self,
        event_type: str,
        message: str,
        level: str = "INFO",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log a system-level event.
        
        Args:
            event_type: Type of system event
            message: Event description
            level: Log level
            metadata: Additional metadata
        """
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": event_type,
                "message": message,
                "metadata": metadata or {}
            }
            
            # Log with appropriate level
            log_method = getattr(self.logger, level.lower(), self.logger.info)
            log_method("system_event", extra=event_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log system event: {e}")
    
    async def log_validation_details(
        self,
        topic: str,
        schema_id: str,
        validation_type: str,  # 'topic' or 'schema'
        success: bool,
        details: Optional[Dict[str, Any]] = None,
        processing_time_ms: Optional[float] = None
    ):
        """
        Log detailed validation information.
        
        Args:
            topic: MQTT topic
            schema_id: Schema identifier
            validation_type: Type of validation performed
            success: Whether validation succeeded
            details: Detailed validation results
            processing_time_ms: Time taken for validation
        """
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": "validation_detail",
                "topic": topic,
                "schema_id": schema_id,
                "validation_type": validation_type,
                "success": success,
                "processing_time_ms": processing_time_ms,
                "details": details or {}
            }
            
            self.logger.debug("validation_detail", extra=event_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log validation details: {e}")
    
    async def log_quarantine_event(
        self,
        message_id: str,
        topic: str,
        reason: str,
        action: str,  # 'stored', 'processed', 'retry'
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log quarantine-related events.
        
        Args:
            message_id: Unique message identifier
            topic: MQTT topic
            reason: Reason for quarantine
            action: Action taken
            metadata: Additional metadata
        """
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": f"quarantine_{action}",
                "message_id": message_id,
                "topic": topic,
                "reason": reason,
                "metadata": metadata or {}
            }
            
            self.logger.info("quarantine_event", extra=event_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log quarantine event: {e}")
    
    async def log_performance_metrics(
        self,
        metrics: Dict[str, Any]
    ):
        """
        Log performance metrics.
        
        Args:
            metrics: Dictionary of performance metrics
        """
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": "performance_metrics",
                "metrics": metrics
            }
            
            self.logger.info("performance_metrics", extra=event_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log performance metrics: {e}")
    
    def start_timing(self, operation_id: str):
        """Start timing an operation."""
        self._start_times[operation_id] = time.time()
    
    def end_timing(self, operation_id: str) -> Optional[float]:
        """End timing an operation and return duration in milliseconds."""
        if operation_id in self._start_times:
            duration_ms = (time.time() - self._start_times[operation_id]) * 1000
            del self._start_times[operation_id]
            return duration_ms
        return None
    
    # Context manager for timing operations
    class TimingContext:
        """Context manager for timing operations."""
        
        def __init__(self, audit_logger: 'AuditLogger', operation_id: str):
            self.audit_logger = audit_logger
            self.operation_id = operation_id
            self.duration_ms = None
        
        def __enter__(self):
            self.audit_logger.start_timing(self.operation_id)
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.duration_ms = self.audit_logger.end_timing(self.operation_id)
        
        def get_duration(self) -> Optional[float]:
            """Get the measured duration in milliseconds."""
            return self.duration_ms
    
    def time_operation(self, operation_id: str):
        """Context manager for timing operations."""
        return self.TimingContext(self, operation_id)
    
    async def log_configuration_change(
        self,
        config_type: str,
        changes: Dict[str, Any],
        user: Optional[str] = None
    ):
        """
        Log configuration changes.
        
        Args:
            config_type: Type of configuration changed
            changes: Dictionary of changes made
            user: User who made the changes (if available)
        """
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": "configuration_change",
                "config_type": config_type,
                "changes": changes,
                "user": user
            }
            
            self.logger.warning("configuration_change", extra=event_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log configuration change: {e}")
    
    async def log_security_event(
        self,
        event_type: str,
        description: str,
        client_id: Optional[str] = None,
        source_ip: Optional[str] = None,
        severity: str = "medium",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log security-related events.
        
        Args:
            event_type: Type of security event
            description: Event description
            client_id: MQTT client ID involved
            source_ip: Source IP address
            severity: Event severity level
            metadata: Additional metadata
        """
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": f"security_{event_type}",
                "description": description,
                "client_id": client_id,
                "source_ip": source_ip,
                "severity": severity,
                "metadata": metadata or {}
            }
            
            # Log as warning for security events
            self.logger.warning("security_event", extra=event_data)
            
        except Exception as e:
            self.logger.error(f"Failed to log security event: {e}")
    
    def get_log_file_path(self) -> str:
        """Get the current log file path."""
        return str(self.log_file)
    
    def rotate_log(self, backup_suffix: Optional[str] = None):
        """
        Rotate the current log file.
        
        Args:
            backup_suffix: Suffix for backup file (defaults to timestamp)
        """
        try:
            if not self.log_file.exists():
                return
            
            if backup_suffix is None:
                backup_suffix = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            
            backup_path = self.log_file.with_suffix(f".{backup_suffix}.jsonl")
            self.log_file.rename(backup_path)
            
            # Create new log file
            self.log_file.touch()
            
            self.logger.info(f"Log file rotated to {backup_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to rotate log file: {e}")


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def test_audit_logger():
        # Create audit logger
        audit_logger = AuditLogger("test_audit.jsonl")
        
        # Log various events
        await audit_logger.log_message(
            topic="sensor/room1/temperature",
            schema_id="temperature:v1",
            status="valid",
            payload_size=64,
            processing_time_ms=1.5
        )
        
        await audit_logger.log_message(
            topic="invalid/topic",
            status="invalid",
            reason="Topic validation failed",
            payload_size=32
        )
        
        await audit_logger.log_system_event(
            "proxy_started",
            "MQTT Schema Governance Proxy started successfully",
            metadata={"version": "1.0.0"}
        )
        
        # Test timing
        with audit_logger.time_operation("test_operation") as timer:
            await asyncio.sleep(0.1)  # Simulate work
        
        print(f"Operation took {timer.get_duration():.2f}ms")
        
        await audit_logger.log_quarantine_event(
            "msg-123",
            "faulty/topic",
            "Schema validation failed",
            "stored"
        )
        
        await audit_logger.log_security_event(
            "unauthorized_access",
            "Client attempted to publish to restricted topic",
            client_id="unknown_client",
            source_ip="192.168.1.100",
            severity="high"
        )
        
        print(f"Audit log written to: {audit_logger.get_log_file_path()}")
    
    # Run test
    asyncio.run(test_audit_logger())
