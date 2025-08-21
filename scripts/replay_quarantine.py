#!/usr/bin/env python3
"""
Quarantine Replay Script

This script processes quarantined messages and attempts to re-validate them
using current rules and schemas. Valid messages can be forwarded to the broker.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from quarantine_store import QuarantineStore, QuarantinedMessage
from config_loader import ConfigLoader
from topic_validator import TopicValidator
from schema_validator import SchemaValidator
from mqtt_proxy import MQTTProxy
import paho.mqtt.client as mqtt


class QuarantineReplayManager:
    """Manages replay of quarantined messages."""
    
    def __init__(
        self,
        config_path: str,
        quarantine_db: str = "quarantine.sqlite3",
        dry_run: bool = False,
        max_retries: int = 3
    ):
        self.config_path = config_path
        self.quarantine_db = quarantine_db
        self.dry_run = dry_run
        self.max_retries = max_retries
        
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.config = None
        self.quarantine_store = None
        self.topic_validator = None
        self.schema_validator = None
        self.mqtt_client = None
        
        # Statistics
        self.stats = {
            'processed': 0,
            'valid': 0,
            'invalid': 0,
            'forwarded': 0,
            'errors': 0
        }
    
    async def initialize(self):
        """Initialize all components."""
        try:
            # Load configuration
            config_loader = ConfigLoader(self.config_path)
            self.config = config_loader.load()
            
            # Initialize quarantine store
            self.quarantine_store = QuarantineStore(self.quarantine_db)
            
            # Initialize validators
            self.topic_validator = TopicValidator(self.config)
            self.schema_validator = SchemaValidator(self.config)
            
            # Initialize MQTT client for forwarding
            if not self.dry_run:
                await self._setup_mqtt_client()
            
            self.logger.info("Quarantine replay manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            raise
    
    async def _setup_mqtt_client(self):
        """Setup MQTT client for message forwarding."""
        self.mqtt_client = mqtt.Client(client_id="quarantine-replay")
        
        # Configure connection based on config
        broker_config = getattr(self.config, 'broker_config', {})
        host = broker_config.get('host', 'localhost')
        port = broker_config.get('port', 1883)
        username = broker_config.get('username')
        password = broker_config.get('password')
        
        if username and password:
            self.mqtt_client.username_pw_set(username, password)
        
        # Connect to broker
        try:
            self.mqtt_client.connect(host, port, 60)
            self.mqtt_client.loop_start()
            self.logger.info(f"Connected to MQTT broker at {host}:{port}")
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    async def replay_all_unprocessed(self, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Replay all unprocessed quarantined messages.
        
        Args:
            limit: Maximum number of messages to process
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Get unprocessed messages
            messages = await self.quarantine_store.get_unprocessed(limit or 1000)
            
            if not messages:
                self.logger.info("No unprocessed quarantined messages found")
                return self.stats
            
            self.logger.info(f"Found {len(messages)} unprocessed quarantined messages")
            
            # Process each message
            for message in messages:
                await self._process_message(message)
            
            # Print summary
            self._print_summary()
            
            return self.stats
            
        except Exception as e:
            self.logger.error(f"Error during replay: {e}")
            raise
    
    async def replay_by_id(self, message_ids: List[str]) -> Dict[str, int]:
        """
        Replay specific messages by ID.
        
        Args:
            message_ids: List of message IDs to replay
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            for message_id in message_ids:
                # Search for the message
                messages = await self.quarantine_store.search_messages(
                    limit=1
                )
                
                # Find matching message
                target_message = None
                for msg in messages:
                    if msg.id == message_id:
                        target_message = msg
                        break
                
                if target_message:
                    await self._process_message(target_message)
                else:
                    self.logger.warning(f"Message not found: {message_id}")
                    self.stats['errors'] += 1
            
            self._print_summary()
            return self.stats
            
        except Exception as e:
            self.logger.error(f"Error during replay: {e}")
            raise
    
    async def replay_by_criteria(
        self,
        topic_pattern: Optional[str] = None,
        reason_pattern: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> Dict[str, int]:
        """
        Replay messages matching specific criteria.
        
        Args:
            topic_pattern: SQL LIKE pattern for topic filtering
            reason_pattern: SQL LIKE pattern for reason filtering
            start_date: Start date for date range
            end_date: End date for date range
            limit: Maximum number of messages to process
            
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Search for matching messages
            messages = await self.quarantine_store.search_messages(
                topic_pattern=topic_pattern,
                reason_pattern=reason_pattern,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )
            
            if not messages:
                self.logger.info("No messages found matching criteria")
                return self.stats
            
            self.logger.info(f"Found {len(messages)} messages matching criteria")
            
            # Process each message
            for message in messages:
                await self._process_message(message)
            
            self._print_summary()
            return self.stats
            
        except Exception as e:
            self.logger.error(f"Error during replay: {e}")
            raise
    
    async def _process_message(self, message: QuarantinedMessage):
        """Process a single quarantined message."""
        try:
            self.stats['processed'] += 1
            
            self.logger.debug(f"Processing message {message.id}: {message.topic}")
            
            # Validate topic
            topic_valid, topic_reason = await self.topic_validator.validate(message.topic)
            
            if not topic_valid:
                self.logger.info(f"Message {message.id} still invalid - Topic: {topic_reason}")
                await self._handle_still_invalid(message, f"Topic validation: {topic_reason}")
                return
            
            # Get schema for topic
            schema_id = self.config.get_schema_for_topic(message.topic)
            if not schema_id:
                self.logger.info(f"Message {message.id} still invalid - No schema mapping")
                await self._handle_still_invalid(message, "No schema mapping found")
                return
            
            # Validate payload against schema
            schema_valid, schema_reason = await self.schema_validator.validate(
                schema_id, message.payload
            )
            
            if not schema_valid:
                self.logger.info(f"Message {message.id} still invalid - Schema: {schema_reason}")
                await self._handle_still_invalid(message, f"Schema validation: {schema_reason}")
                return
            
            # Message is now valid
            self.stats['valid'] += 1
            self.logger.info(f"Message {message.id} is now valid - forwarding")
            
            # Forward message if not in dry run mode
            if not self.dry_run and self.mqtt_client:
                try:
                    result = self.mqtt_client.publish(message.topic, message.payload, qos=1)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        self.stats['forwarded'] += 1
                        self.logger.info(f"Forwarded message {message.id} to {message.topic}")
                    else:
                        self.logger.error(f"Failed to forward message {message.id}: {mqtt.error_string(result.rc)}")
                        self.stats['errors'] += 1
                        return
                except Exception as e:
                    self.logger.error(f"Error forwarding message {message.id}: {e}")
                    self.stats['errors'] += 1
                    return
            else:
                self.logger.info(f"DRY RUN: Would forward message {message.id} to {message.topic}")
                self.stats['forwarded'] += 1
            
            # Mark message as processed
            await self.quarantine_store.mark_processed(message.id)
            
        except Exception as e:
            self.logger.error(f"Error processing message {message.id}: {e}")
            self.stats['errors'] += 1
    
    async def _handle_still_invalid(self, message: QuarantinedMessage, reason: str):
        """Handle a message that is still invalid after re-validation."""
        self.stats['invalid'] += 1
        
        # Increment retry count
        if message.retry_count < self.max_retries:
            await self.quarantine_store.increment_retry_count(message.id)
            self.logger.debug(f"Incremented retry count for message {message.id} (now {message.retry_count + 1})")
        else:
            self.logger.warning(f"Message {message.id} exceeded max retries ({self.max_retries})")
    
    def _print_summary(self):
        """Print processing summary."""
        print("\n" + "="*50)
        print("QUARANTINE REPLAY SUMMARY")
        print("="*50)
        print(f"Messages processed: {self.stats['processed']}")
        print(f"Now valid:          {self.stats['valid']}")
        print(f"Still invalid:      {self.stats['invalid']}")
        print(f"Forwarded:          {self.stats['forwarded']}")
        print(f"Errors:             {self.stats['errors']}")
        
        if self.stats['processed'] > 0:
            success_rate = (self.stats['valid'] / self.stats['processed']) * 100
            print(f"Success rate:       {success_rate:.1f}%")
        
        print("="*50)
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        if self.quarantine_store:
            self.quarantine_store.close()


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def parse_date(date_str: str) -> datetime:
    """Parse date string to datetime object."""
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except ValueError:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid date format: {date_str}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Replay quarantined MQTT messages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Replay all unprocessed messages
  %(prog)s --limit 50                        # Replay first 50 unprocessed messages
  %(prog)s --id msg1 msg2                    # Replay specific messages by ID
  %(prog)s --topic "sensor/%%"               # Replay messages with topics starting with 'sensor/'
  %(prog)s --reason "%%schema%%"             # Replay messages with schema-related failures
  %(prog)s --start-date 2023-12-01           # Replay messages from Dec 1, 2023
  %(prog)s --dry-run                         # Validate only, don't forward messages
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        default='config/rules.yaml',
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--quarantine-db', '-q',
        default='quarantine.sqlite3',
        help='Path to quarantine database'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        help='Maximum number of messages to process'
    )
    
    parser.add_argument(
        '--id',
        nargs='+',
        help='Specific message IDs to replay'
    )
    
    parser.add_argument(
        '--topic',
        help='Topic pattern to filter messages (SQL LIKE syntax)'
    )
    
    parser.add_argument(
        '--reason',
        help='Reason pattern to filter messages (SQL LIKE syntax)'
    )
    
    parser.add_argument(
        '--start-date',
        type=parse_date,
        help='Start date for message filtering (YYYY-MM-DD or ISO format)'
    )
    
    parser.add_argument(
        '--end-date',
        type=parse_date,
        help='End date for message filtering (YYYY-MM-DD or ISO format)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate messages but do not forward to broker'
    )
    
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Maximum retry attempts for failed messages'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Create and initialize replay manager
    manager = QuarantineReplayManager(
        config_path=args.config,
        quarantine_db=args.quarantine_db,
        dry_run=args.dry_run,
        max_retries=args.max_retries
    )
    
    try:
        await manager.initialize()
        
        # Determine replay mode and execute
        if args.id:
            await manager.replay_by_id(args.id)
        elif any([args.topic, args.reason, args.start_date, args.end_date]):
            await manager.replay_by_criteria(
                topic_pattern=args.topic,
                reason_pattern=args.reason,
                start_date=args.start_date,
                end_date=args.end_date,
                limit=args.limit or 100
            )
        else:
            await manager.replay_all_unprocessed(args.limit)
        
    except KeyboardInterrupt:
        print("\nReplay interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        await manager.cleanup()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
