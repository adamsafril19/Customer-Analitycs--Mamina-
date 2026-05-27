"""
Message Feature Extraction Service

Extracts STATISTICAL signals from linked messages.
Creates FeedbackFeatures ONLY for messages that have FeedbackLinked.

IMPORTANT: Message-level flags here are deterministic rules, not model outputs.
Sentiment and topic interpretation still belong to SemanticService.
"""
import logging
import re
from datetime import datetime
from typing import Optional

from app import db
from app.models.feedback import FeedbackRaw, FeedbackLinked, FeedbackFeatures

logger = logging.getLogger(__name__)

# Minimum confidence to extract features
MIN_CONFIDENCE = 0.7

COMPLAINT_PATTERNS = [
    r"\bkomplain\b",
    r"\bkeluhan\b",
    r"\bkecewa\b",
    r"\bburuk\b",
    r"\bparah\b",
    r"\btidak\s+(puas|sesuai|bagus|baik)\b",
    r"\bnggak\s+(puas|sesuai|bagus|baik)\b",
    r"\bgak\s+(puas|sesuai|bagus|baik)\b",
    r"\bkurang\s+(puas|bagus|baik|bersih|ramah)\b",
    r"\brusak\b",
    r"\bcacat\b",
    r"\bjelek\b",
    r"\btelat\b",
    r"\bterlambat\b",
    r"\blambat\b",
    r"\blama\s+banget\b",
    r"\bkasar\b",
]

REFUND_PATTERNS = [
    r"\brefund\b",
    r"\buang\s+kembali\b",
    r"\bkembali(?:kan)?\s+uang\b",
    r"\bbalikin\s+uang\b",
    r"\bdana\s+kembali\b",
    r"\bcancel\s+booking\b",
    r"\bbatal(?:kan)?\s+booking\b",
]


class MessageFeatureService:
    """
    Extract STATISTICAL features from linked messages
    
    Only processes messages that have been linked with sufficient confidence.
    
    Complaint/refund flags are rule-based operational signals. Sentiment and
    topic modeling remain isolated in SemanticService.
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
    
    def process_unprocessed_messages(
        self,
        generate_embeddings: bool = True,
        refresh_existing: bool = False,
    ) -> dict:
        """
        Extract features for linked messages that don't have FeedbackFeatures yet.
        
        Only processes high-confidence links (>= MIN_CONFIDENCE).
        If refresh_existing is true, also recomputes deterministic fields for
        existing FeedbackFeatures rows so old NLP runs can be repaired.
        """
        query = db.session.query(FeedbackLinked, FeedbackRaw).join(
            FeedbackRaw, FeedbackLinked.msg_id == FeedbackRaw.msg_id
        ).filter(
            FeedbackLinked.match_confidence >= MIN_CONFIDENCE
        )

        if not refresh_existing:
            query = query.outerjoin(
                FeedbackFeatures, FeedbackLinked.link_id == FeedbackFeatures.link_id
            ).filter(FeedbackFeatures.feature_id == None)

        messages = query.all()
        
        stats = {"total": len(messages), "processed": 0, "skipped": 0, "refreshed": 0}
        
        for linked, raw in messages:
            existed = FeedbackFeatures.query.filter_by(link_id=linked.link_id).first() is not None
            result = self.extract_features(
                linked,
                raw,
                generate_embeddings=generate_embeddings,
                refresh_existing=refresh_existing,
            )
            if result:
                stats["processed"] += 1
                if existed:
                    stats["refreshed"] += 1
            else:
                stats["skipped"] += 1
        
        db.session.commit()
        return stats
    
    def extract_features(
        self, 
        linked: FeedbackLinked, 
        raw: FeedbackRaw,
        generate_embeddings: bool = True,
        refresh_existing: bool = False,
    ) -> Optional[FeedbackFeatures]:
        """
        Extract deterministic features from a single message.
        
        - msg_length: character count
        - num_exclamations: punctuation pattern
        - num_questions: punctuation pattern
        - has_complaint: rule-based operational flag
        - has_refund_request: rule-based operational flag
        - embedding: vector representation (if enabled)
        """
        existing = FeedbackFeatures.query.filter_by(link_id=linked.link_id).first()
        if existing and not refresh_existing:
            return existing
        
        text = raw.text or ""
        features = existing or FeedbackFeatures(
            link_id=linked.link_id,
            msg_id=raw.msg_id,
            customer_id=linked.customer_id,
        )
        features.msg_id = raw.msg_id
        features.customer_id = linked.customer_id
        features.msg_length = len(text)
        features.num_exclamations = text.count("!")
        features.num_questions = text.count("?")
        features.has_complaint = self.detect_complaint(text)
        features.has_refund_request = self.detect_refund_request(text)
        features.processed_at = datetime.utcnow()
        
        # Embedding (SEMANTIC representation, requires verified identity)
        # Note: EmbeddingService returns None for empty text, not zero vector
        if generate_embeddings and text.strip():
            try:
                embedding = self.embedding_service.encode(text)
                if embedding is not None:  # Only store if valid
                    features.embedding = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        if not existing:
            db.session.add(features)
        return features

    @staticmethod
    def detect_complaint(text: str) -> bool:
        """Detect obvious complaint wording with deterministic Indonesian rules."""
        text_lower = (text or "").lower()
        if MessageFeatureService.detect_refund_request(text_lower):
            return True
        return any(re.search(pattern, text_lower) for pattern in COMPLAINT_PATTERNS)

    @staticmethod
    def detect_refund_request(text: str) -> bool:
        """Detect refund or cancellation requests with deterministic rules."""
        text_lower = (text or "").lower()
        return any(re.search(pattern, text_lower) for pattern in REFUND_PATTERNS)
