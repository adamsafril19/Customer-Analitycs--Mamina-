"""
Message Feature Extraction Service

Extracts STATISTICAL signals from linked messages.
Creates FeedbackFeatures ONLY for messages that have FeedbackLinked.

IMPORTANT: Features must be derivable WITHOUT understanding meaning.
- Length, punctuation, timing = OK
- Complaint detection, sentiment = NOT OK (goes to SemanticService)
"""
import logging
from datetime import datetime
from typing import Optional, List

from app import db
from app.models.feedback import FeedbackRaw, FeedbackLinked, FeedbackFeatures

logger = logging.getLogger(__name__)

# Minimum confidence to extract features
MIN_CONFIDENCE = 0.7


class MessageFeatureService:
    """
    Extract STATISTICAL features from linked messages
    
    Only processes messages that have been linked with sufficient confidence.
    
    IMPORTANT: No semantic features here (complaint detection, refund detection).
    Those go to SemanticService to prevent ML from learning our own rules.
    """
    
    def __init__(self):
        self._embedding_service = None
    
    @property
    def embedding_service(self):
        if self._embedding_service is None:
            from app.services.embedding_service import EmbeddingService
            self._embedding_service = EmbeddingService()
            if not self._embedding_service.is_model_loaded():
                self._embedding_service.load_model()
        return self._embedding_service
    
    def process_unprocessed_messages(self, generate_embeddings: bool = True) -> dict:
        """
        Extract features for linked messages that don't have FeedbackFeatures yet.
        
        Only processes high-confidence links (>= MIN_CONFIDENCE).
        """
        # Find linked messages without features
        unprocessed = db.session.query(FeedbackLinked, FeedbackRaw).join(
            FeedbackRaw, FeedbackLinked.msg_id == FeedbackRaw.msg_id
        ).outerjoin(
            FeedbackFeatures, FeedbackLinked.link_id == FeedbackFeatures.link_id
        ).filter(
            FeedbackFeatures.feature_id == None,
            FeedbackLinked.match_confidence >= MIN_CONFIDENCE
        ).all()
        
        stats = {"total": len(unprocessed), "processed": 0, "skipped": 0}
        
        for linked, raw in unprocessed:
            result = self.extract_features(linked, raw, generate_embeddings)
            if result:
                stats["processed"] += 1
            else:
                stats["skipped"] += 1
        
        db.session.commit()
        return stats
    
    def extract_features(
        self, 
        linked: FeedbackLinked, 
        raw: FeedbackRaw,
        generate_embeddings: bool = True
    ) -> Optional[FeedbackFeatures]:
        """
        Extract STATISTICAL features from a single message.
        
        ONLY statistical signals - NO semantic interpretation:
        - msg_length: character count
        - num_exclamations: punctuation pattern
        - num_questions: punctuation pattern
        - embedding: vector representation (if enabled)
        
        REMOVED (moved to SemanticService):
        - has_complaint: uses keyword detection (semantic)
        - has_refund_request: uses keyword detection (semantic)
        """
        # Check if already has features
        existing = FeedbackFeatures.query.filter_by(link_id=linked.link_id).first()
        if existing:
            return existing
        
        text = raw.text or ""
        
        # === STATISTICAL SIGNALS ONLY (safe for ML) ===
        features = FeedbackFeatures(
            link_id=linked.link_id,
            customer_id=linked.customer_id,  # Denormalized from linked
            msg_length=len(text),
            num_exclamations=text.count("!"),
            num_questions=text.count("?"),
            # REMOVED: has_complaint and has_refund_request (semantic leakage)
            processed_at=datetime.utcnow()
        )
        
        # Embedding (SEMANTIC representation, requires verified identity)
        # Note: EmbeddingService returns None for empty text, not zero vector
        if generate_embeddings and text.strip():
            try:
                embedding = self.embedding_service.encode(text)
                if embedding is not None:  # Only store if valid
                    features.embedding = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        db.session.add(features)
        return features

