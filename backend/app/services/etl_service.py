"""
ETL Service for WhatsApp logs processing

Handles:
- Parsing raw WhatsApp export files
- Sentiment analysis
- Topic extraction
- Response time calculation
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import hashlib

from app import db
from app.models.customer import Customer
from app.models.feedback import FeedbackRaw, FeedbackClean
from app.utils.auth import hash_phone_number

logger = logging.getLogger(__name__)


class ETLService:
    """
    ETL Service for WhatsApp message processing
    
    Flow:
    1. Parse raw WhatsApp export
    2. Match messages to customers (by phone hash)
    3. Analyze sentiment and extract topics
    4. Calculate response times
    5. Store in feedback_raw and feedback_clean tables
    """
    
    # WhatsApp message pattern: [DD/MM/YY, HH:MM:SS] Sender: Message
    WA_PATTERN = r'\[(\d{1,2}/\d{1,2}/\d{2,4}),\s(\d{1,2}:\d{2}(?::\d{2})?)\]\s([^:]+):\s(.+)'
    
    def __init__(self):
        self.sentiment_analyzer = None
    
    def _get_sentiment_analyzer(self):
        """Lazy load sentiment analyzer"""
        if self.sentiment_analyzer is None:
            from textblob import TextBlob
            self.sentiment_analyzer = TextBlob
        return self.sentiment_analyzer
    
    def process_whatsapp_file(
        self, 
        file_path: str,
        admin_name: str = "Mamina"
    ) -> Dict[str, int]:
        """
        Process WhatsApp export file
        
        Args:
            file_path: Path to WhatsApp export file
            admin_name: Name of admin/business in chat
            
        Returns:
            Dict with processing statistics
        """
        stats = {
            "total_lines": 0,
            "messages_parsed": 0,
            "messages_stored": 0,
            "customers_created": 0,
            "errors": 0
        }
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file: {e}")
            return {"error": str(e)}
        
        # Parse messages
        messages = self._parse_whatsapp_content(content, admin_name)
        stats["total_lines"] = len(content.split('\n'))
        stats["messages_parsed"] = len(messages)
        
        # Group by sender (phone/name)
        grouped = self._group_by_sender(messages)
        
        # Process each conversation
        for sender, sender_messages in grouped.items():
            try:
                self._process_conversation(sender, sender_messages, admin_name)
                stats["messages_stored"] += len(sender_messages)
            except Exception as e:
                logger.error(f"Error processing {sender}: {e}")
                stats["errors"] += 1
        
        db.session.commit()
        
        return stats
    
    def _parse_whatsapp_content(
        self, 
        content: str,
        admin_name: str
    ) -> List[Dict[str, Any]]:
        """Parse WhatsApp export content"""
        messages = []
        
        for match in re.finditer(self.WA_PATTERN, content):
            date_str, time_str, sender, text = match.groups()
            
            # Parse datetime
            try:
                # Handle different date formats
                if len(date_str.split('/')[-1]) == 2:
                    date_format = "%d/%m/%y"
                else:
                    date_format = "%d/%m/%Y"
                
                if ':' in time_str and time_str.count(':') == 2:
                    time_format = "%H:%M:%S"
                else:
                    time_format = "%H:%M"
                
                timestamp = datetime.strptime(
                    f"{date_str} {time_str}", 
                    f"{date_format} {time_format}"
                )
            except ValueError as e:
                logger.warning(f"Failed to parse datetime: {date_str} {time_str}")
                continue
            
            # Determine direction
            direction = "outbound" if admin_name.lower() in sender.lower() else "inbound"
            
            messages.append({
                "sender": sender.strip(),
                "text": text.strip(),
                "timestamp": timestamp,
                "direction": direction
            })
        
        return messages
    
    def _group_by_sender(
        self, 
        messages: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group messages by sender (excluding admin)"""
        grouped = {}
        
        for msg in messages:
            if msg["direction"] == "inbound":
                sender = msg["sender"]
                if sender not in grouped:
                    grouped[sender] = []
                grouped[sender].append(msg)
        
        return grouped
    
    def _process_conversation(
        self, 
        sender: str,
        messages: List[Dict[str, Any]],
        admin_name: str
    ) -> None:
        """Process a single customer's conversation"""
        # Find or create customer
        phone_hash = hash_phone_number(sender)
        
        customer = Customer.query.filter_by(phone_hash=phone_hash).first()
        if not customer:
            customer = Customer(
                name=sender,  # Use sender as name initially
                phone_hash=phone_hash,
                consent_given=False  # Needs explicit consent
            )
            db.session.add(customer)
            db.session.flush()  # Get customer_id
        
        # Process each message
        for msg in messages:
            self._store_message(customer.customer_id, msg)
    
    def _store_message(
        self, 
        customer_id: str,
        msg: Dict[str, Any]
    ) -> None:
        """Store raw and cleaned message"""
        # Store raw
        raw = FeedbackRaw(
            customer_id=customer_id,
            direction=msg["direction"],
            text=msg["text"],
            timestamp=msg["timestamp"],
            raw_meta={"sender": msg["sender"]}
        )
        db.session.add(raw)
        db.session.flush()
        
        # Analyze and store clean
        sentiment = self._analyze_sentiment(msg["text"])
        topics = self._extract_topics(msg["text"])
        emotions = self._extract_emotions(msg["text"])
        
        clean = FeedbackClean(
            msg_id=raw.msg_id,
            customer_id=customer_id,
            sentiment_score=sentiment["score"],
            sentiment_label=sentiment["label"],
            topic_labels=topics,
            keywords_emotion=emotions
        )
        db.session.add(clean)
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text
        
        Returns:
            Dict with score (-1 to 1) and label
        """
        try:
            TextBlob = self._get_sentiment_analyzer()
            blob = TextBlob(text)
            score = blob.sentiment.polarity
            
            if score > 0.1:
                label = "positive"
            elif score < -0.1:
                label = "negative"
            else:
                label = "neutral"
            
            return {"score": score, "label": label}
            
        except Exception as e:
            logger.warning(f"Sentiment analysis failed: {e}")
            return {"score": 0, "label": "neutral"}
    
    def _extract_topics(self, text: str) -> List[str]:
        """
        Extract topics from text using keyword matching
        
        Returns:
            List of topic labels
        """
        topics = []
        text_lower = text.lower()
        
        # Topic keywords (Indonesian context)
        topic_keywords = {
            "jadwal": ["jadwal", "waktu", "jam", "booking", "book"],
            "harga": ["harga", "biaya", "tarif", "bayar", "price"],
            "layanan": ["layanan", "service", "pijat", "spa", "baby"],
            "komplain": ["komplain", "kecewa", "buruk", "jelek", "marah", "complaint"],
            "promo": ["promo", "diskon", "potongan", "murah"],
            "terima_kasih": ["terima kasih", "thanks", "makasih", "thank"],
            "tanya": ["tanya", "info", "informasi", "gimana", "bagaimana"]
        }
        
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        
        return topics if topics else ["general"]
    
    def _extract_emotions(self, text: str) -> Dict[str, float]:
        """
        Extract emotion keywords with intensity
        
        Returns:
            Dict of emotion -> intensity
        """
        emotions = {}
        text_lower = text.lower()
        
        # Emotion keywords with base intensity
        emotion_keywords = {
            "happy": ["senang", "bahagia", "suka", "bagus", "mantap", "😊", "😀"],
            "angry": ["marah", "kesal", "jengkel", "😠", "😡"],
            "sad": ["sedih", "kecewa", "😢", "😭"],
            "grateful": ["terima kasih", "makasih", "🙏"],
            "worried": ["khawatir", "takut", "cemas"]
        }
        
        for emotion, keywords in emotion_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    # Simple presence = 0.5 intensity
                    emotions[emotion] = emotions.get(emotion, 0) + 0.5
        
        # Normalize to 0-1
        if emotions:
            max_val = max(emotions.values())
            emotions = {k: min(1.0, v / max_val) for k, v in emotions.items()}
        
        return emotions
    
    def calculate_response_times(self, customer_id: str) -> int:
        """
        Calculate and update response times for customer messages
        
        Returns:
            Number of messages updated
        """
        # Get all messages for customer, ordered by time
        messages = FeedbackRaw.query.filter_by(
            customer_id=customer_id
        ).order_by(FeedbackRaw.timestamp).all()
        
        updated = 0
        
        for i, msg in enumerate(messages):
            if msg.direction == "inbound":
                # Find next outbound message
                for next_msg in messages[i+1:]:
                    if next_msg.direction == "outbound":
                        response_time = (next_msg.timestamp - msg.timestamp).total_seconds()
                        
                        # Update clean record
                        clean = FeedbackClean.query.filter_by(msg_id=msg.msg_id).first()
                        if clean:
                            clean.response_time_secs = int(response_time)
                            updated += 1
                        break
        
        db.session.commit()
        return updated
