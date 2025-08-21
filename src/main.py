#!/usr/bin/env python3
"""
MQTT Schema Governance Proxy - Main Entry Point

This module provides the CLI entry point for the MQTT Schema Governance Proxy.
It loads configuration, initializes components, and manages the proxy lifecycle.
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

from config_loader import load_config
from mqtt_proxy import MQTTProxy
from metrics_exporter import MetricsExporter
from quarantine_store import QuarantineStore
from audit_logger import AuditLogger


class ProxyManager:
    """Manages the lifecycle of the MQTT Schema Governance Proxy."""
    
    def __init__(self, config_path: str, dry_run: bool = False):
        self.config_path = config_path
        self.dry_run = dry_run
        self.proxy: Optional[MQTTProxy] = None
        self.metrics_exporter: Optional[MetricsExporter] = None
        self.quarantine_store: Optional[QuarantineStore] = None
        self.audit_logger: Optional[AuditLogger] = None
        self.shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize all components."""
        try:
            # Load configuration
            config = load_config(self.config_path)
            
            # Initialize components
            self.quarantine_store = QuarantineStore()
            self.audit_logger = AuditLogger()
            self.metrics_exporter = MetricsExporter()
            
            # Initialize MQTT proxy
            self.proxy = MQTTProxy(
                config=config,
                quarantine_store=self.quarantine_store,
                audit_logger=self.audit_logger,
                metrics_exporter=self.metrics_exporter,
                dry_run=self.dry_run
            )
            
            logging.info("All components initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize components: {e}")
            raise
    
    async def start(self):
        """Start all services."""
        if not self.proxy:
            raise RuntimeError("Proxy not initialized")
            
        try:
            # Start metrics exporter
            await self.metrics_exporter.start()
            logging.info("Metrics exporter started")
            
            # Start MQTT proxy
            await self.proxy.start()
            logging.info("MQTT proxy started")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            logging.error(f"Error during proxy operation: {e}")
            raise
    
    async def shutdown(self):
        """Gracefully shutdown all components."""
        logging.info("Initiating graceful shutdown...")
        
        if self.proxy:
            await self.proxy.stop()
            logging.info("MQTT proxy stopped")
            
        if self.metrics_exporter:
            await self.metrics_exporter.stop()
            logging.info("Metrics exporter stopped")
            
        if self.quarantine_store:
            self.quarantine_store.close()
            logging.info("Quarantine store closed")
            
        logging.info("Shutdown complete")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logging.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown_event.set()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/proxy.log', mode='a')
        ]
    )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MQTT Schema Governance Proxy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Use default config
  %(prog)s --config custom_rules.yaml        # Use custom config
  %(prog)s --dry-run                         # Validate only, don't forward
  %(prog)s --verbose                         # Enable debug logging
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/rules.yaml',
        help='Path to configuration file (default: config/rules.yaml)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate messages but do not forward to upstream broker'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='MQTT Schema Governance Proxy 1.0.0'
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Ensure logs directory exists
    Path('logs').mkdir(exist_ok=True)
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Validate config file exists
    if not Path(args.config).exists():
        logging.error(f"Configuration file not found: {args.config}")
        sys.exit(1)
    
    # Create proxy manager
    manager = ProxyManager(args.config, args.dry_run)
    
    # Setup signal handlers
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, manager.signal_handler)
    
    try:
        # Initialize and start
        await manager.initialize()
        
        if args.dry_run:
            logging.info("Running in DRY RUN mode - messages will not be forwarded")
        
        logging.info("Starting MQTT Schema Governance Proxy...")
        await manager.start()
        
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        await manager.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
