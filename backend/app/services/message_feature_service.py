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
TRUSTED_LINK_STATUSES = ("verified", "probable")
_LOOKUP_EXISTING = object()

SERVICE_CONTEXT_PATTERNS = [
    r"\b(mamina|admin|pelayanan|layanan|service|servis|staff|staf|terapis|therapis|bidan|treatment|fasilitas|ruangan|tempat|sop)\b",
]

INTAKE_FORM_PATTERNS = [
    r"\breservasi\s+(homecare|outlet)\b",
    r"\bmohon\s+diisi\b",
    r"\bnama\s+bunda\b",
    r"\bnama\s+(bayi|panggilan\s+bayi)\b",
    r"\busia\s+bayi\b",
    r"\bjenis\s+treatment\b",
    r"\balamat\s+lengkap\b",
    r"\bkeluhan\s*:",
]

CONSULTATION_PATTERNS = [
    r"\b(asi|laktasi|menyusu|menyusui|payudara|puting)\b",
    r"\b(bayi|anak|mpasi|gumoh|kolik|rewel|demam|batuk|pilek|flu)\b",
    r"\b(bab|susah\s+bab|tidur\s+kurang\s+nyenyak|motorik|tumbuh\s+kembang)\b",
]

CUSTOMER_SELF_DELAY_PATTERNS = [
    r"\b(saya|aku|kami|kita)\s+(otw|on\s+the\s+way)\b",
    r"\b(ijin|izin|maaf)?\s*(agak|sedikit)?\s*(telat|terlambat)\b.*\b(saya|aku|kami|kita|macet|hujan|dijalan|di\s+jalan|grab|anak|adek|nunggu)\b",
    r"\b(saya|aku|kami|kita)\b.*\b(telat|terlambat)\b",
    r"\bmasih\s+(di\s+)?jalan\b",
]

SERVICE_DELAY_PATTERNS = [
    r"\b(admin|terapis|therapis|bidan)\b.*\b(telat|terlambat|lambat|lama)\b",
    r"\b(respon|respons|balas|dibalas|direspon)\b.*\b(lama|lambat)\b",
    r"\b(belum)\s+(datang|dateng|sampai|nyampe)\b",
    r"\bnunggu\s+lama\b",
    r"\bmenunggu\s+lama\b",
    r"\blama\s+banget\b",
]

SERVICE_COMPLAINT_PATTERNS = [
    r"\bkomplain\b.*\b(pelayanan|layanan|service|admin|staff|staf|terapis|therapis|bidan|treatment|fasilitas|sop|mamina)\b",
    r"\b(keluhan|mengeluh)\b.*\b(pelayanan|layanan|service|admin|staff|staf|terapis|therapis|bidan|treatment|fasilitas|sop|mamina)\b",
    r"\bkecewa\b.*\b(pelayanan|layanan|service|admin|staff|staf|terapis|therapis|bidan|treatment|fasilitas|sop|mamina)\b",
    r"\b(pelayanan|layanan|service|admin|staff|staf|terapis|therapis|bidan|fasilitas)\s+(buruk|parah|jelek|kasar|tidak\s+ramah|kurang\s+ramah)\b",
    r"\b(tidak|nggak|gak|ga|kurang)\s+(puas|sesuai|bagus|baik|nyaman|bersih|ramah)\b.*\b(pelayanan|layanan|service|admin|staff|staf|terapis|therapis|bidan|treatment|fasilitas|sop|mamina)\b",
    r"\b(treatment|oralcare|potong\s+kuku|pijat|baby\s+spa)\b.*\b(tidak|nggak|gak|ga|kurang)\s+(sesuai|bersih|rapi|benar|nyaman)\b",
    r"\b(tidak|nggak|gak|ga)\s+cuci\s+tangan\b",
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

MONEY_RETURN_PATTERNS = REFUND_PATTERNS[:5]


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
        progress_callback: Optional[callable] = None,
    ) -> dict:
        """
        Extract features for linked messages that don't have FeedbackFeatures yet.
        
        Only processes high-confidence links (>= MIN_CONFIDENCE).
        If refresh_existing is true, also recomputes deterministic fields for
        existing FeedbackFeatures rows so old NLP runs can be repaired.
        """
        query = db.session.query(
            FeedbackLinked,
            FeedbackRaw,
            FeedbackFeatures,
        ).join(
            FeedbackRaw, FeedbackLinked.msg_id == FeedbackRaw.msg_id
        ).outerjoin(
            FeedbackFeatures, FeedbackLinked.link_id == FeedbackFeatures.link_id
        ).filter(
            FeedbackLinked.link_status.in_(TRUSTED_LINK_STATUSES),
            FeedbackLinked.match_confidence >= MIN_CONFIDENCE,
        )

        if not refresh_existing:
            query = query.filter(FeedbackFeatures.feature_id == None)

        messages = query.all()
        
        stats = {"total": len(messages), "processed": 0, "skipped": 0, "refreshed": 0}
        
        pending_embeddings = []
        embedding_version = None

        total_messages = max(1, len(messages))
        for index, (linked, raw, existing) in enumerate(messages):
            if progress_callback and index % max(1, total_messages // 20) == 0:
                progress_callback(int(50 * index / total_messages))
            existed = existing is not None
            result = self.extract_features(
                linked,
                raw,
                generate_embeddings=False,
                refresh_existing=refresh_existing,
                existing=existing,
            )
            if result:
                stats["processed"] += 1
                if existed:
                    stats["refreshed"] += 1
                if generate_embeddings and (raw.text or "").strip():
                    pending_embeddings.append((result, raw.text))
            else:
                stats["skipped"] += 1

        if pending_embeddings:
            if progress_callback:
                progress_callback(50)
            stats["embedding_failed"] = self._assign_batch_embeddings(
                pending_embeddings,
                progress_callback=progress_callback,
                progress_start=50,
                progress_end=100,
            )
        elif progress_callback:
            progress_callback(100)
        
        db.session.commit()
        return stats

    def _assign_batch_embeddings(
        self,
        pending_embeddings: list,
        progress_callback: Optional[callable] = None,
        progress_start: int = 0,
        progress_end: int = 100,
        batch_size: int = 64,
    ) -> int:
        """Encode pending message texts in one batch and persist model lineage."""
        try:
            embedding_version = self.embedding_service.get_model_version()
            failed = 0
            total = len(pending_embeddings)
            for start in range(0, total, batch_size):
                if progress_callback:
                    pct = progress_start + int(
                        (progress_end - progress_start) * start / max(1, total)
                    )
                    progress_callback(pct)

                batch = pending_embeddings[start:start + batch_size]
                vectors = self.embedding_service.encode_batch(
                    [text for _, text in batch],
                    batch_size=batch_size,
                )
                for (features, _), vector in zip(batch, vectors):
                    if vector is None:
                        failed += 1
                        continue
                    features.embedding = vector
                    features.embedding_model_version = embedding_version
                failed += max(0, len(batch) - len(vectors))

            if progress_callback:
                progress_callback(progress_end)
            return failed
        except Exception as exc:
            logger.warning("Batch embedding generation failed: %s", exc)
            return len(pending_embeddings)

    def unload_embedding_model(self) -> None:
        """Release the sentence encoder after message-level extraction."""
        if self._embedding_service is not None:
            self._embedding_service.unload_model()
            self._embedding_service = None
    
    def extract_features(
        self, 
        linked: FeedbackLinked, 
        raw: FeedbackRaw,
        generate_embeddings: bool = True,
        refresh_existing: bool = False,
        existing=_LOOKUP_EXISTING,
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
        if existing is _LOOKUP_EXISTING:
            existing = FeedbackFeatures.query.filter_by(
                link_id=linked.link_id
            ).first()
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
        features.has_complaint = (
            self.detect_complaint(text) if raw.direction == "inbound" else False
        )
        features.has_refund_request = self.detect_refund_request(text)
        features.processed_at = datetime.utcnow()
        
        # Embedding (SEMANTIC representation, requires verified identity)
        # Note: EmbeddingService returns None for empty text, not zero vector
        if generate_embeddings and text.strip():
            try:
                embedding = self.embedding_service.encode(text)
                if embedding is not None:  # Only store if valid
                    features.embedding = embedding
                    features.embedding_model_version = (
                        self.embedding_service.get_model_version()
                    )
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        if not existing:
            db.session.add(features)
        return features

    @staticmethod
    def detect_complaint(text: str) -> bool:
        """Detect explicit service complaints with deterministic context rules."""
        text_lower = MessageFeatureService._normalize_text(text)
        if not text_lower:
            return False

        if MessageFeatureService._matches_any(text_lower, MONEY_RETURN_PATTERNS):
            return True

        has_form_context = MessageFeatureService._matches_any(
            text_lower, INTAKE_FORM_PATTERNS
        )
        has_service_context = MessageFeatureService._matches_any(
            text_lower, SERVICE_CONTEXT_PATTERNS
        )

        # "Keluhan" inside reservation/intake forms describes customer/baby
        # conditions, not dissatisfaction toward Mamina's service.
        if has_form_context and not re.search(
            r"\b(komplain|kecewa|tidak\s+puas|nggak\s+puas|gak\s+puas|ga\s+puas|refund)\b",
            text_lower,
        ):
            return False

        if MessageFeatureService._matches_any(text_lower, CUSTOMER_SELF_DELAY_PATTERNS):
            return False

        if MessageFeatureService._matches_any(text_lower, SERVICE_DELAY_PATTERNS):
            return True

        if MessageFeatureService._matches_any(text_lower, SERVICE_COMPLAINT_PATTERNS):
            return True

        if (
            MessageFeatureService._matches_any(text_lower, CONSULTATION_PATTERNS)
            and not has_service_context
        ):
            return False

        return False

    @staticmethod
    def detect_refund_request(text: str) -> bool:
        """Detect refund or cancellation requests with deterministic rules."""
        text_lower = MessageFeatureService._normalize_text(text)
        return MessageFeatureService._matches_any(text_lower, REFUND_PATTERNS)

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize WhatsApp text before deterministic rule matching."""
        return re.sub(r"\s+", " ", (text or "").lower()).strip()

    @staticmethod
    def _matches_any(text: str, patterns: list) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)
