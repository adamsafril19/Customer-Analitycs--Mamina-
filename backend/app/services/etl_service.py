"""
ETL Service for WhatsApp logs processing

REVISED: Only writes to FeedbackRaw with phone_number.
NO customer_id assignment - that's done by LinkingService.
NO feature extraction - that's done by MessageFeatureService.

Pipeline:
1. ETLService.process_whatsapp_export() → FeedbackRaw (phone_number)
2. LinkingService.link_unlinked_messages() → FeedbackLinked (confidence)
3. MessageFeatureService.process_unprocessed_messages() → FeedbackFeatures
"""
import re
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from app import db
from app.models.feedback import FeedbackRaw
from app.utils.auth import hash_phone_number

logger = logging.getLogger(__name__)


class ETLService:
    """
    ETL Service for WhatsApp message ingestion
    
    ONLY responsibility: parse WhatsApp export → FeedbackRaw (phone_number)
    
    Does NOT:
    - Assign customer_id (LinkingService does that)
    - Extract features (MessageFeatureService does that)
    - Run sentiment/topic (SemanticService does that)
    """
    
    # WhatsApp message pattern: [DD/MM/YY, HH:MM:SS] Sender: Message
    WA_PATTERN = r'\[(\d{1,2}/\d{1,2}/\d{2,4}),\s(\d{1,2}:\d{2}(?::\d{2})?)\]\s([^:]+):\s(.+)'
    
    def process_whatsapp_export(
        self, 
        content: str, 
        admin_name: str = "Mamina"
    ) -> Dict[str, Any]:
        """
        Process WhatsApp export file content
        
        Only creates FeedbackRaw records with phone_number.
        Identity resolution and feature extraction happen separately.
        
        Returns processing stats.
        """
        # Parse messages
        messages = self._parse_messages(content, admin_name)
        
        stats = {
            "total_messages": len(messages),
            "new_messages": 0,
            "duplicate_messages": 0,
            "unique_senders": 0
        }
        
        # Group by sender
        grouped = self._group_by_sender(messages)
        stats["unique_senders"] = len(grouped)
        
        # Store each message
        for sender, sender_messages in grouped.items():
            for msg in sender_messages:
                result = self._store_raw_message(sender, msg, admin_name)
                if result == "new":
                    stats["new_messages"] += 1
                else:
                    stats["duplicate_messages"] += 1
        
        db.session.commit()
        
        logger.info(
            f"ETL complete: {stats['new_messages']} new messages, "
            f"{stats['unique_senders']} senders"
        )
        
        return stats
    
    def _parse_messages(
        self, 
        content: str, 
        admin_name: str
    ) -> List[Dict[str, Any]]:
        """
        Parse WhatsApp export into message dicts
        
        Handles multiline messages by detecting line continuation.
        WhatsApp format: [DD/MM/YY, HH:MM:SS] Sender: Message
        Lines without this pattern are continuations of previous message.
        """
        messages = []
        pattern = re.compile(self.WA_PATTERN)
        lines = content.split('\n')
        
        current_message = None
        stats = {"total_lines": len(lines), "skipped_system": 0, "multiline_merged": 0}
        
        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue
            
            # Skip system messages
            if '<Media omitted>' in line or 'Messages and calls are end-to-end encrypted' in line:
                stats["skipped_system"] += 1
                continue
            
            match = pattern.match(line)
            
            if match:
                # Save previous message if exists
                if current_message:
                    messages.append(current_message)
                
                date_str, time_str, sender, text = match.groups()
                
                # Parse datetime
                try:
                    date_format = "%d/%m/%y" if len(date_str.split("/")[-1]) == 2 else "%d/%m/%Y"
                    time_format = "%H:%M:%S" if time_str.count(":") == 2 else "%H:%M"
                    
                    timestamp = datetime.strptime(
                        f"{date_str} {time_str}", 
                        f"{date_format} {time_format}"
                    )
                except ValueError:
                    logger.warning(f"Failed to parse datetime: {date_str} {time_str}")
                    continue
                
                # Determine direction
                direction = "outbound" if admin_name.lower() in sender.lower() else "inbound"
                
                current_message = {
                    "sender": sender.strip(),
                    "text": text.strip(),
                    "timestamp": timestamp,
                    "direction": direction
                }
            elif current_message:
                # This is a continuation line - append to current message
                current_message["text"] += "\n" + line.strip()
                stats["multiline_merged"] += 1
        
        # Don't forget the last message
        if current_message:
            messages.append(current_message)
        
        logger.info(f"ETL parsed: {len(messages)} messages, {stats['multiline_merged']} multiline merges, {stats['skipped_system']} system msgs skipped")
        
        return messages
    
    def _group_by_sender(
        self, 
        messages: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group messages by sender"""
        grouped = {}
        
        for msg in messages:
            sender = msg["sender"]
            if sender not in grouped:
                grouped[sender] = []
            grouped[sender].append(msg)
        
        return grouped
    
    def _store_raw_message(
        self, 
        sender: str,
        msg: Dict[str, Any],
        admin_name: str
    ) -> str:
        """
        Store raw message to FeedbackRaw
        
        Returns "new" or "duplicate"
        """
        # Hash the phone/sender
        phone_hash = hash_phone_number(sender)
        
        # Check for duplicate
        existing = FeedbackRaw.query.filter_by(
            phone_number=phone_hash,
            timestamp=msg["timestamp"],
            text=msg["text"]
        ).first()
        
        if existing:
            return "duplicate"
        
        # Store raw - NO customer_id here!
        raw = FeedbackRaw(
            phone_number=phone_hash,
            direction=msg["direction"],
            text=msg["text"],
            timestamp=msg["timestamp"],
            raw_meta={"sender": sender}
        )
        db.session.add(raw)
        
        return "new"
    
    def get_pipeline_stats(self) -> dict:
        """Get stats about the ETL pipeline state"""
        from app.models.feedback import FeedbackLinked, FeedbackFeatures
        
        total_raw = FeedbackRaw.query.count()
        total_linked = FeedbackLinked.query.count()
        total_features = FeedbackFeatures.query.count()
        
        return {
            "raw_messages": total_raw,
            "linked_messages": total_linked,
            "unlinked_messages": total_raw - total_linked,
            "feature_extracted": total_features,
            "pending_features": total_linked - total_features
        }
