"""
Semantic Service

DASHBOARD ONLY - ML does NOT use this.

Populates CustomerTextSemantics from raw text on-the-fly.
Uses SentimentService and TopicService.

This is completely isolated from FeatureService to prevent leakage.
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from collections import Counter

import numpy as np

from app import db
from app.models.feedback import FeedbackRaw, FeedbackLinked
from app.models.text_semantics import CustomerTextSemantics

logger = logging.getLogger(__name__)

# Minimum match confidence for semantic aggregation
MIN_CONFIDENCE = 0.7


class SemanticService:
    """
    Semantic interpretation service (DASHBOARD ONLY)
    
    This service is completely isolated from ML pipeline.
    FeatureService has no knowledge of this service.
    """
    
    def __init__(self):
        self._sentiment_service = None
        self._topic_service = None
    
    @property
    def sentiment_service(self):
        if self._sentiment_service is None:
            from app.services.sentiment_service import SentimentService
            self._sentiment_service = SentimentService()
        return self._sentiment_service
    
    @property
    def topic_service(self):
        if self._topic_service is None:
            from app.services.topic_service import TopicService
            self._topic_service = TopicService()
        return self._topic_service
    
    def populate_text_semantics(
        self, 
        customer_id: str, 
        as_of_date: Optional[date] = None
    ) -> CustomerTextSemantics:
        """
        Compute semantic features from raw text on-the-fly
        
        DASHBOARD ONLY - ML does NOT see this.
        Uses proper identity resolution through FeedbackLinked.
        """
        if as_of_date is None:
            as_of_date = date.today()
        
        thirty_days_ago = as_of_date - timedelta(days=30)
        end_dt = datetime.combine(as_of_date, datetime.max.time())
        start_dt_30 = datetime.combine(thirty_days_ago, datetime.min.time())
        
        existing = CustomerTextSemantics.query.filter_by(
            customer_id=customer_id, as_of_date=as_of_date
        ).first()
        
        semantics = existing or CustomerTextSemantics(
            customer_id=customer_id, as_of_date=as_of_date
        )
        if not existing:
            db.session.add(semantics)
        
        # CORRECT: Use FeedbackLinked to get raw messages with proper identity resolution
        linked_messages = db.session.query(FeedbackRaw, FeedbackLinked).join(
            FeedbackLinked, FeedbackRaw.msg_id == FeedbackLinked.msg_id
        ).filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.match_confidence >= MIN_CONFIDENCE,
            FeedbackRaw.timestamp >= start_dt_30,
            FeedbackRaw.timestamp <= end_dt,
            FeedbackRaw.direction == 'inbound'
        ).order_by(FeedbackRaw.timestamp.desc()).all()
        
        raw_messages = [raw for raw, linked in linked_messages]
        
        # Include timestamp for auditability (dashboard can verify "last 10" is same)
        semantics.last_n_msg_ids = [
            {"msg_id": str(m.msg_id), "timestamp": m.timestamp.isoformat() if m.timestamp else None}
            for m in raw_messages[:10]
        ]
        
        if not raw_messages:
            semantics.sentiment_dist = None
            semantics.avg_sentiment_score = None
            semantics.top_topic_counts = None
            semantics.avg_topic_confidence = None
            semantics.top_keywords = None
            semantics.top_complaint_types = None
            db.session.commit()
            return semantics
        
        # === SENTIMENT (on-the-fly) ===
        sentiment_counts = Counter()
        sentiment_scores = []
        for msg in raw_messages:
            if msg.text:
                try:
                    # Contract: returns (label, score) tuple
                    label, score = self.sentiment_service.predict(msg.text)
                    sentiment_counts[label] += 1
                    sentiment_scores.append(score)
                except Exception as e:
                    logger.warning(f"Sentiment failed for msg {msg.msg_id}: {e}")
        semantics.sentiment_dist = dict(sentiment_counts) if sentiment_counts else None
        semantics.avg_sentiment_score = float(np.mean(sentiment_scores)) if sentiment_scores else None
        # Store model version for semantic continuity
        semantics.sentiment_model_version = self.sentiment_service.get_model_version() if self.sentiment_service.is_model_loaded() else None
        
        # === TOPIC (on-the-fly) ===
        topic_counts = Counter()
        topic_similarities = []  # NOTE: This is cosine similarity, NOT probability
        texts = [msg.text for msg in raw_messages if msg.text]
        if texts:
            try:
                # Contract: predict_batch returns list of (topic_idx, similarity) tuples
                results = self.topic_service.predict_batch(texts)
                for topic_id, similarity in results:
                    if topic_id is not None:
                        topic_counts[str(topic_id)] += 1
                        if similarity is not None:
                            topic_similarities.append(similarity)
            except Exception as e:
                logger.warning(f"Topic prediction failed: {e}")
        semantics.top_topic_counts = dict(topic_counts.most_common(5)) if topic_counts else None
        # NOTE: This measures embedding clustering, NOT topic certainty
        semantics.avg_topic_similarity = float(np.mean(topic_similarities)) if topic_similarities else None
        # Store model version for semantic continuity
        semantics.topic_model_version = self.topic_service.get_model_version() if self.topic_service.is_model_loaded() else None
        
        # === KEYWORDS (simple extraction) ===
        word_counter = Counter()
        stop_words = {'yang', 'di', 'dan', 'ke', 'dari', 'ini', 'itu', 'untuk', 'dengan', 'adalah', 'saya', 'aku', 'kamu', 'dia'}
        for msg in raw_messages:
            if msg.text:
                words = [w for w in msg.text.lower().split() if len(w) > 3 and w not in stop_words]
                word_counter.update(words)
        semantics.top_keywords = dict(word_counter.most_common(10)) if word_counter else None
        
        # === COMPLAINT TYPES (rule-based) ===
        complaint_types = Counter()
        rules = {
            'refund': ['refund', 'uang kembali', 'balikin'],
            'delivery': ['lambat', 'telat', 'lama', 'kirim'],
            'product': ['rusak', 'cacat', 'jelek'],
            'service': ['pelayanan', 'staff', 'kasar']
        }
        for msg in raw_messages:
            if msg.text:
                text_lower = msg.text.lower()
                for ctype, keywords in rules.items():
                    if any(kw in text_lower for kw in keywords):
                        complaint_types[ctype] += 1
        semantics.top_complaint_types = dict(complaint_types) if complaint_types else None
        
        db.session.commit()
        return semantics
