"""
Quarantine Store Module

This module handles storage and management of rejected MQTT messages.
Messages that fail validation are stored for later analysis and potential replay.
"""

import json
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import asyncio
from dataclasses import dataclass, asdict
import aiosqlite


@dataclass
class QuarantinedMessage:
    """Represents a quarantined message."""
    id: str
    received_at: datetime
    topic: str
    payload: bytes
    reason: str
    retry_count: int = 0
    processed: bool = False
    processed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class QuarantineStore:
    """
    Manages storage of quarantined MQTT messages.
    
    Uses SQLite for structured storage and optionally writes individual
    files to a quarantine directory for backup and analysis.
    """
    
    def __init__(
        self,
        db_path: str = "quarantine.sqlite3",
        quarantine_dir: str = "quarantine",
        write_files: bool = True,
        max_payload_size: int = 1024 * 1024  # 1MB
    ):
        self.db_path = db_path
        self.quarantine_dir = Path(quarantine_dir)
        self.write_files = write_files
        self.max_payload_size = max_payload_size
        
        self.logger = logging.getLogger(__name__)
        
        # Create quarantine directory if needed
        if self.write_files:
            self.quarantine_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database with required tables."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS quarantined_messages (
                    id TEXT PRIMARY KEY,
                    received_at TIMESTAMP NOT NULL,
                    topic TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    reason TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0,
                    processed BOOLEAN DEFAULT FALSE,
                    processed_at TIMESTAMP NULL,
                    metadata TEXT NULL,
                    payload_size INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better query performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_received_at 
                ON quarantined_messages(received_at)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_topic 
                ON quarantined_messages(topic)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_processed 
                ON quarantined_messages(processed)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_retry_count 
                ON quarantined_messages(retry_count)
            ''')
            
            conn.commit()
            conn.close()
            
            self.logger.info(f"Quarantine database initialized: {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize quarantine database: {e}")
            raise
    
    async def store(
        self,
        topic: str,
        payload: bytes,
        reason: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store a quarantined message.
        
        Args:
            topic: MQTT topic
            payload: Message payload
            reason: Reason for quarantine
            metadata: Optional metadata dictionary
            
        Returns:
            Unique message ID
        """
        # Generate unique ID
        message_id = str(uuid.uuid4())
        received_at = datetime.utcnow()
        
        # Check payload size
        if len(payload) > self.max_payload_size:
            self.logger.warning(f"Payload too large for storage: {len(payload)} bytes, truncating")
            payload = payload[:self.max_payload_size]
            if metadata is None:
                metadata = {}
            metadata['truncated'] = True
            metadata['original_size'] = len(payload)
        
        try:
            # Store in database
            await self._store_in_db(
                message_id, received_at, topic, payload, reason, metadata
            )
            
            # Write to file if enabled
            if self.write_files:
                await self._write_to_file(
                    message_id, received_at, topic, payload, reason, metadata
                )
            
            self.logger.info(f"Quarantined message {message_id}: {topic} - {reason}")
            return message_id
            
        except Exception as e:
            self.logger.error(f"Failed to store quarantined message: {e}")
            raise
    
    async def _store_in_db(
        self,
        message_id: str,
        received_at: datetime,
        topic: str,
        payload: bytes,
        reason: str,
        metadata: Optional[Dict[str, Any]]
    ):
        """Store message in SQLite database."""
        metadata_json = json.dumps(metadata) if metadata else None
        
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO quarantined_messages 
                (id, received_at, topic, payload, reason, payload_size, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                message_id,
                received_at.isoformat(),
                topic,
                payload,
                reason,
                len(payload),
                metadata_json
            ))
            await db.commit()
    
    async def _write_to_file(
        self,
        message_id: str,
        received_at: datetime,
        topic: str,
        payload: bytes,
        reason: str,
        metadata: Optional[Dict[str, Any]]
    ):
        """Write quarantined message to individual file."""
        try:
            # Create filename with timestamp and ID
            timestamp_str = received_at.strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp_str}_{message_id}.json"
            file_path = self.quarantine_dir / filename
            
            # Prepare file content
            file_content = {
                'id': message_id,
                'received_at': received_at.isoformat(),
                'topic': topic,
                'reason': reason,
                'payload_size': len(payload),
                'metadata': metadata or {},
                'payload_base64': payload.hex(),  # Store as hex for binary safety
                'payload_text': self._safe_decode_payload(payload)
            }
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(file_content, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Wrote quarantine file: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to write quarantine file for {message_id}: {e}")
            # Don't raise here - database storage is more important
    
    def _safe_decode_payload(self, payload: bytes) -> Optional[str]:
        """Safely decode payload to text for file storage."""
        try:
            return payload.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return payload.decode('latin-1')
            except:
                return None  # Binary data that can't be decoded
    
    async def get_unprocessed(self, limit: int = 100) -> List[QuarantinedMessage]:
        """
        Get unprocessed quarantined messages.
        
        Args:
            limit: Maximum number of messages to return
            
        Returns:
            List of QuarantinedMessage objects
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                
                cursor = await db.execute('''
                    SELECT * FROM quarantined_messages 
                    WHERE processed = FALSE 
                    ORDER BY received_at ASC 
                    LIMIT ?
                ''', (limit,))
                
                rows = await cursor.fetchall()
                
                messages = []
                for row in rows:
                    metadata = json.loads(row['metadata']) if row['metadata'] else None
                    
                    message = QuarantinedMessage(
                        id=row['id'],
                        received_at=datetime.fromisoformat(row['received_at']),
                        topic=row['topic'],
                        payload=row['payload'],
                        reason=row['reason'],
                        retry_count=row['retry_count'],
                        processed=bool(row['processed']),
                        processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None,
                        metadata=metadata
                    )
                    messages.append(message)
                
                return messages
                
        except Exception as e:
            self.logger.error(f"Failed to get unprocessed messages: {e}")
            return []
    
    async def mark_processed(self, message_id: str) -> bool:
        """
        Mark a message as processed.
        
        Args:
            message_id: Message ID to mark as processed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE quarantined_messages 
                    SET processed = TRUE, processed_at = ? 
                    WHERE id = ?
                ''', (datetime.utcnow().isoformat(), message_id))
                
                await db.commit()
                
                # Check if update was successful
                cursor = await db.execute(
                    'SELECT changes()'
                )
                changes = await cursor.fetchone()
                
                if changes and changes[0] > 0:
                    self.logger.debug(f"Marked message {message_id} as processed")
                    return True
                else:
                    self.logger.warning(f"Message {message_id} not found for processing")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Failed to mark message {message_id} as processed: {e}")
            return False
    
    async def increment_retry_count(self, message_id: str) -> bool:
        """
        Increment retry count for a message.
        
        Args:
            message_id: Message ID to increment retry count
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE quarantined_messages 
                    SET retry_count = retry_count + 1 
                    WHERE id = ?
                ''', (message_id,))
                
                await db.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to increment retry count for {message_id}: {e}")
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get quarantine statistics."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                stats = {}
                
                # Total messages
                cursor = await db.execute('SELECT COUNT(*) FROM quarantined_messages')
                result = await cursor.fetchone()
                stats['total_messages'] = result[0] if result else 0
                
                # Processed messages
                cursor = await db.execute('SELECT COUNT(*) FROM quarantined_messages WHERE processed = TRUE')
                result = await cursor.fetchone()
                stats['processed_messages'] = result[0] if result else 0
                
                # Unprocessed messages
                cursor = await db.execute('SELECT COUNT(*) FROM quarantined_messages WHERE processed = FALSE')
                result = await cursor.fetchone()
                stats['unprocessed_messages'] = result[0] if result else 0
                
                # Messages by reason
                cursor = await db.execute('''
                    SELECT reason, COUNT(*) as count 
                    FROM quarantined_messages 
                    GROUP BY reason 
                    ORDER BY count DESC
                ''')
                rows = await cursor.fetchall()
                stats['messages_by_reason'] = {row[0]: row[1] for row in rows}
                
                # Recent activity (last 24 hours)
                cursor = await db.execute('''
                    SELECT COUNT(*) FROM quarantined_messages 
                    WHERE received_at > datetime('now', '-1 day')
                ''')
                result = await cursor.fetchone()
                stats['messages_last_24h'] = result[0] if result else 0
                
                return stats
                
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {}
    
    async def cleanup_old_messages(self, days_old: int = 30) -> int:
        """
        Clean up old processed messages.
        
        Args:
            days_old: Delete processed messages older than this many days
            
        Returns:
            Number of messages deleted
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    DELETE FROM quarantined_messages 
                    WHERE processed = TRUE 
                    AND processed_at < datetime('now', '-{} days')
                '''.format(days_old))
                
                await db.commit()
                deleted_count = cursor.rowcount
                
                self.logger.info(f"Cleaned up {deleted_count} old quarantined messages")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to cleanup old messages: {e}")
            return 0
    
    async def search_messages(
        self,
        topic_pattern: Optional[str] = None,
        reason_pattern: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[QuarantinedMessage]:
        """
        Search quarantined messages with filters.
        
        Args:
            topic_pattern: SQL LIKE pattern for topic filtering
            reason_pattern: SQL LIKE pattern for reason filtering
            start_date: Start date for date range
            end_date: End date for date range
            limit: Maximum number of results
            
        Returns:
            List of matching QuarantinedMessage objects
        """
        try:
            query = 'SELECT * FROM quarantined_messages WHERE 1=1'
            params = []
            
            if topic_pattern:
                query += ' AND topic LIKE ?'
                params.append(topic_pattern)
            
            if reason_pattern:
                query += ' AND reason LIKE ?'
                params.append(reason_pattern)
            
            if start_date:
                query += ' AND received_at >= ?'
                params.append(start_date.isoformat())
            
            if end_date:
                query += ' AND received_at <= ?'
                params.append(end_date.isoformat())
            
            query += ' ORDER BY received_at DESC LIMIT ?'
            params.append(limit)
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(query, params)
                rows = await cursor.fetchall()
                
                messages = []
                for row in rows:
                    metadata = json.loads(row['metadata']) if row['metadata'] else None
                    
                    message = QuarantinedMessage(
                        id=row['id'],
                        received_at=datetime.fromisoformat(row['received_at']),
                        topic=row['topic'],
                        payload=row['payload'],
                        reason=row['reason'],
                        retry_count=row['retry_count'],
                        processed=bool(row['processed']),
                        processed_at=datetime.fromisoformat(row['processed_at']) if row['processed_at'] else None,
                        metadata=metadata
                    )
                    messages.append(message)
                
                return messages
                
        except Exception as e:
            self.logger.error(f"Failed to search messages: {e}")
            return []
    
    def close(self):
        """Close database connections and cleanup."""
        # Async cleanup would be called here if needed
        self.logger.info("Quarantine store closed")


if __name__ == "__main__":
    # Example usage
    async def test_quarantine_store():
        store = QuarantineStore("test_quarantine.sqlite3", "test_quarantine")
        
        # Store a test message
        test_payload = b'{"test": "message", "value": 123}'
        message_id = await store.store(
            topic="test/topic",
            payload=test_payload,
            reason="Test quarantine",
            metadata={"test": True}
        )
        
        print(f"Stored message: {message_id}")
        
        # Get unprocessed messages
        unprocessed = await store.get_unprocessed(10)
        print(f"Unprocessed messages: {len(unprocessed)}")
        
        for msg in unprocessed:
            print(f"  {msg.id}: {msg.topic} - {msg.reason}")
            
            # Mark as processed
            await store.mark_processed(msg.id)
        
        # Get statistics
        stats = await store.get_statistics()
        print(f"Statistics: {stats}")
        
        store.close()
    
    # Run test
    asyncio.run(test_quarantine_store())
