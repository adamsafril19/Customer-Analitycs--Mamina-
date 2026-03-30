"""
Feature Engineering Service

ML FEATURE LAYER ONLY - No semantic, no embedding, no interpretation.

Features must be:
- Purely statistical/behavioral
- From VERIFIED linked records only (not probable!)
- No latent semantic representations

CRITICAL: ML only uses link_status='verified' (human-validated identity).
'probable' is phone-match which ≠ identity truth in WhatsApp Indonesia.

RFM (r_score, f_score, m_score) is calculated but NOT included in ML feature vector.
RFM is for dashboard display only.
"""
import hashlib
import json
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy import func
import numpy as np

from app import db
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.feedback import FeedbackLinked, FeedbackFeatures
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_signals import CustomerTextSignals

logger = logging.getLogger(__name__)

# ML only uses verified identity (human-validated)
# probable = phone match ≠ identity truth
LINK_STATUS_FOR_ML = ['verified']

# Dashboard can use probable
LINK_STATUS_FOR_DASHBOARD = ['verified', 'probable']


class FeatureService:
    """
    Feature Engineering Service (ML ONLY)
    
    Rules:
    - No embedding (that's semantic)
    - No sentiment/topic (that's interpretation)
    - All queries start from FeedbackLinked, not FeedbackFeatures
    - RFM is computed but NOT in feature vector
    - build_verified_features() is PURE (no DB writes)
    """
    
    # Schema version - increment when feature set changes
    FEATURE_SCHEMA_VERSION = "v1.0.0"
    
    # Feature definition (order matters!)
    FEATURE_SCHEMA = [
        ("recency_days", "numeric"),
        ("tx_count_30d", "numeric"),
        ("tx_count_90d", "numeric"),
        ("spend_30d", "numeric"),
        ("spend_90d", "numeric"),
        ("avg_tx_value", "numeric"),
        ("tenure_days", "numeric"),
        ("msg_count_7d", "numeric"),
        ("msg_count_30d", "numeric"),
        ("msg_volatility", "numeric"),
        ("avg_msg_length_30d", "numeric"),
        ("complaint_rate_30d", "numeric"),
        ("response_delay_mean", "numeric"),
    ]
    
    @classmethod
    def get_feature_schema_hash(cls) -> str:
        """Get hash of feature schema for validation"""
        schema_str = json.dumps(cls.FEATURE_SCHEMA, sort_keys=True)
        return hashlib.sha256(schema_str.encode()).hexdigest()[:16]
    
    @classmethod
    def get_feature_names(cls) -> List[str]:
        """Get ordered list of feature names"""
        return [name for name, _ in cls.FEATURE_SCHEMA]
    
    @classmethod
    def expected_feature_count(cls) -> int:
        """Get expected feature count"""
        return len(cls.FEATURE_SCHEMA)
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def populate_all_features(self, customer_id: str, as_of_date: Optional[date] = None) -> Dict[str, Any]:
        """Populate all ML feature tables"""
        if as_of_date is None:
            as_of_date = date.today()
        return {
            "numeric_features": self.populate_numeric_features(customer_id, as_of_date),
            "text_signals": self.populate_text_signals(customer_id, as_of_date)
        }
    
    def populate_numeric_features(self, customer_id: str, as_of_date: Optional[date] = None) -> CustomerNumericFeatures:
        """
        Calculate transaction features
        
        ML vector: recency_days, tx_count_30d/90d, spend_30d/90d, avg_tx_value, tenure_days
        Dashboard only: r_score, f_score, m_score (NOT in feature vector)
        """
        if as_of_date is None:
            as_of_date = date.today()
        
        existing = CustomerNumericFeatures.query.filter_by(
            customer_id=customer_id, as_of_date=as_of_date
        ).first()
        
        feature = existing or CustomerNumericFeatures(customer_id=customer_id, as_of_date=as_of_date)
        if not existing:
            db.session.add(feature)
        
        as_of_dt = datetime.combine(as_of_date, datetime.max.time())
        thirty_days_ago = datetime.combine(as_of_date - timedelta(days=30), datetime.min.time())
        ninety_days_ago = datetime.combine(as_of_date - timedelta(days=90), datetime.min.time())
        
        # === RAW TRANSACTION SIGNALS (ML uses) ===
        
        # CRITICAL: last_tx must be filtered by as_of_date (no future leakage)
        last_tx = db.session.query(func.max(Transaction.tx_date)).filter(
            Transaction.customer_id == customer_id, 
            Transaction.status == "completed",
            Transaction.tx_date <= as_of_dt  # TIME-TRAVEL SAFE
        ).scalar()
        feature.recency_days = (as_of_date - last_tx.date()).days if last_tx else 999
        
        feature.tx_count_30d = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= thirty_days_ago, Transaction.tx_date <= as_of_dt
        ).scalar() or 0
        
        feature.tx_count_90d = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= ninety_days_ago, Transaction.tx_date <= as_of_dt
        ).scalar() or 0
        
        feature.spend_30d = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= thirty_days_ago, Transaction.tx_date <= as_of_dt
        ).scalar() or 0)
        
        feature.spend_90d = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= ninety_days_ago, Transaction.tx_date <= as_of_dt
        ).scalar() or 0)
        
        feature.avg_tx_value = feature.spend_90d / feature.tx_count_90d if feature.tx_count_90d else 0.0
        
        # CRITICAL: tenure_days - customer must exist before as_of_date
        customer = db.session.query(Customer.created_at).filter(Customer.customer_id == customer_id).first()
        if customer and customer.created_at:
            created_date = customer.created_at.date() if hasattr(customer.created_at, 'date') else customer.created_at
            if created_date <= as_of_date:
                # Customer existed at observation time
                feature.tenure_days = (as_of_date - created_date).days
            else:
                # Customer didn't exist yet - should not happen in proper training
                feature.tenure_days = 0
                logger.warning(f"Customer {customer_id} created after as_of_date {as_of_date}")
        else:
            feature.tenure_days = 0
        
        # === DERIVED RFM (Dashboard only - NOT in feature vector) ===
        feature.r_score = round(max(0.0, 5.0 - (feature.recency_days / 36.0)), 2)
        feature.f_score = round(min(5.0, float(feature.tx_count_90d or 0) / 2), 2)
        feature.m_score = round(min(5.0, (feature.spend_90d or 0) / 1_000_000), 2)
        
        db.session.commit()
        return feature
    
    def populate_text_signals(self, customer_id: str, as_of_date: Optional[date] = None) -> CustomerTextSignals:
        """
        Behavioral signals (ML sees)
        
        CRITICAL: 
        - Query starts from FeedbackLinked (source of truth)
        - Filter by link_status IN LINK_STATUS_FOR_ML (only verified!)
        - NO embedding (that's semantic)
        """
        if as_of_date is None:
            as_of_date = date.today()
        
        thirty_days_ago = as_of_date - timedelta(days=30)
        seven_days_ago = as_of_date - timedelta(days=7)
        end_dt = datetime.combine(as_of_date, datetime.max.time())
        start_dt_30 = datetime.combine(thirty_days_ago, datetime.min.time())
        start_dt_7 = datetime.combine(seven_days_ago, datetime.min.time())
        
        existing = CustomerTextSignals.query.filter_by(
            customer_id=customer_id, as_of_date=as_of_date
        ).first()
        
        signals = existing or CustomerTextSignals(customer_id=customer_id, as_of_date=as_of_date)
        if not existing:
            db.session.add(signals)
        
        # CRITICAL: Only use VERIFIED links for ML (not probable!)
        # probable = phone match ≠ identity truth
        verified_features = db.session.query(FeedbackFeatures, FeedbackLinked).join(
            FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
        ).filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status.in_(LINK_STATUS_FOR_ML),  # Only verified!
            FeedbackFeatures.processed_at >= start_dt_30,
            FeedbackFeatures.processed_at <= end_dt
        ).all()
        
        features_30d = [f for f, _ in verified_features]
        
        signals.msg_count_30d = len(features_30d)
        signals.msg_count_7d = len([f for f in features_30d if f.processed_at >= start_dt_7])
        
        if features_30d:
            complaint_count = len([f for f in features_30d if f.has_complaint])
            signals.complaint_rate_30d = complaint_count / len(features_30d)
            
            lengths = [f.msg_length for f in features_30d if f.msg_length]
            signals.avg_msg_length_30d = float(np.mean(lengths)) if lengths else 0.0
            
            delays = [f.response_time_secs for f in features_30d if f.response_time_secs]
            signals.response_delay_mean = float(np.mean(delays)) if delays else 0.0
            
            # Volatility from same filtered dataset
            signals.msg_volatility = self._calculate_msg_volatility_from_features(
                features_30d, thirty_days_ago, as_of_date
            )
        else:
            signals.complaint_rate_30d = 0.0
            signals.avg_msg_length_30d = 0.0
            signals.response_delay_mean = 0.0
            signals.msg_volatility = 0.0
        
        # NO embedding - that's semantic!
        # signals.avg_embedding = None  # Removed from model
        # signals.embedding_count_30d = 0  # Removed from model
        
        db.session.commit()
        return signals
    
    # =========================================================================
    # ML Feature Assembly
    # =========================================================================
    
    def get_ml_feature_vector(self, customer_id: str, as_of_date: Optional[date] = None) -> Optional[List[float]]:
        """Assemble feature vector for ML (raw signals only, NO RFM)"""
        if as_of_date is None:
            as_of_date = date.today()
        
        numeric = CustomerNumericFeatures.query.filter_by(customer_id=customer_id, as_of_date=as_of_date).first()
        signals = CustomerTextSignals.query.filter_by(customer_id=customer_id, as_of_date=as_of_date).first()
        
        if not numeric or not signals:
            return None
        
        # Raw signals only - NO RFM (that's derived)
        return [
            float(numeric.recency_days or 0),
            float(numeric.tx_count_30d or 0),
            float(numeric.tx_count_90d or 0),
            numeric.spend_30d or 0.0,
            numeric.spend_90d or 0.0,
            numeric.avg_tx_value or 0.0,
            float(numeric.tenure_days or 0),
            float(signals.msg_count_7d or 0),
            float(signals.msg_count_30d or 0),
            signals.msg_volatility or 0.0,
            signals.avg_msg_length_30d or 0.0,
            signals.complaint_rate_30d or 0.0,
            signals.response_delay_mean or 0.0
        ]
    
    def get_ml_feature_dict(self, customer_id: str, as_of_date: Optional[date] = None) -> Optional[Dict[str, float]]:
        """Get feature dict with names for SHAP (raw signals only, NO RFM)"""
        if as_of_date is None:
            as_of_date = date.today()
        
        numeric = CustomerNumericFeatures.query.filter_by(customer_id=customer_id, as_of_date=as_of_date).first()
        signals = CustomerTextSignals.query.filter_by(customer_id=customer_id, as_of_date=as_of_date).first()
        
        if not numeric or not signals:
            return None
        
        return {
            # RAW transaction signals (not RFM)
            "recency_days": float(numeric.recency_days or 0),
            "tx_count_30d": float(numeric.tx_count_30d or 0),
            "tx_count_90d": float(numeric.tx_count_90d or 0),
            "spend_30d": numeric.spend_30d or 0.0,
            "spend_90d": numeric.spend_90d or 0.0,
            "avg_tx_value": numeric.avg_tx_value or 0.0,
            "tenure_days": float(numeric.tenure_days or 0),
            # Text signals (behavioral, not semantic)
            "msg_count_7d": float(signals.msg_count_7d or 0),
            "msg_count_30d": float(signals.msg_count_30d or 0),
            "msg_volatility": signals.msg_volatility or 0.0,
            "avg_msg_length_30d": signals.avg_msg_length_30d or 0.0,
            "complaint_rate_30d": signals.complaint_rate_30d or 0.0,
            "response_delay_mean": signals.response_delay_mean or 0.0
        }
    
    def build_verified_features(
        self, 
        customer_id: str, 
        as_of: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        PURE FUNCTION: Build feature vector from VERIFIED evidence only.
        
        NO SIDE EFFECTS:
        - No database writes
        - No cache mutations
        - Deterministic for given as_of timestamp
        
        Args:
            customer_id: Customer UUID
            as_of: Explicit temporal anchor (defaults to now)
                   Pass same value for reproducibility
            
        Returns:
            Dict with features, schema info, and verified count
            
        Raises:
            PermissionError: If customer has no verified feedback
        """
        # Explicit temporal anchor for reproducibility
        if as_of is None:
            as_of = datetime.utcnow()
        
        as_of_date = as_of.date() if hasattr(as_of, 'date') else as_of
        
        # === IDENTITY ENFORCEMENT ===
        # Only count feedback that existed at as_of time
        verified_feedback = FeedbackLinked.query.filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status == 'verified',
            FeedbackLinked.linked_at <= as_of  # Temporal constraint
        )
        verified_count = verified_feedback.count()
        
        if verified_count == 0:
            total = FeedbackLinked.query.filter_by(customer_id=customer_id).count()
            raise PermissionError(
                f"Cannot build features: customer {customer_id} has {total} feedback links "
                f"but ZERO are 'verified' as of {as_of.isoformat()}. ML requires verified identity."
            )
        
        # === PURE COMPUTATION - NO DB WRITES ===
        as_of_dt = datetime.combine(as_of_date, datetime.max.time())
        thirty_days_ago = datetime.combine(as_of_date - timedelta(days=30), datetime.min.time())
        ninety_days_ago = datetime.combine(as_of_date - timedelta(days=90), datetime.min.time())
        seven_days_ago = datetime.combine(as_of_date - timedelta(days=7), datetime.min.time())
        
        # --- Numeric features (from transactions) ---
        last_tx = db.session.query(func.max(Transaction.tx_date)).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date <= as_of_dt
        ).scalar()
        recency_days = (as_of_date - last_tx.date()).days if last_tx else 999
        
        tx_count_30d = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date >= thirty_days_ago,
            Transaction.tx_date <= as_of_dt
        ).scalar() or 0
        
        tx_count_90d = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date >= ninety_days_ago,
            Transaction.tx_date <= as_of_dt
        ).scalar() or 0
        
        spend_30d = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date >= thirty_days_ago,
            Transaction.tx_date <= as_of_dt
        ).scalar() or 0)
        
        spend_90d = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date >= ninety_days_ago,
            Transaction.tx_date <= as_of_dt
        ).scalar() or 0)
        
        avg_tx_value = spend_90d / tx_count_90d if tx_count_90d else 0.0
        
        customer = db.session.query(Customer.created_at).filter(
            Customer.customer_id == customer_id
        ).first()
        tenure_days = (as_of_date - customer.created_at.date()).days if customer and customer.created_at else 0
        
        # --- Text signals (from VERIFIED feedback only) ---
        # ORDER BY explicit for deterministic aggregation across DB engines
        verified_features = db.session.query(FeedbackFeatures).join(
            FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
        ).filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status == 'verified',
            FeedbackFeatures.processed_at >= thirty_days_ago,
            FeedbackFeatures.processed_at <= as_of_dt
        ).order_by(
            FeedbackFeatures.feature_id  # Deterministic order
        ).all()
        
        msg_count_30d = len(verified_features)
        msg_count_7d = len([f for f in verified_features if f.processed_at >= seven_days_ago])
        
        if verified_features:
            complaint_count = len([f for f in verified_features if f.has_complaint])
            complaint_rate_30d = complaint_count / msg_count_30d
            
            lengths = [f.msg_length for f in verified_features if f.msg_length]
            avg_msg_length_30d = float(np.mean(lengths)) if lengths else 0.0
            
            delays = [f.response_time_secs for f in verified_features if f.response_time_secs]
            response_delay_mean = float(np.mean(delays)) if delays else 0.0
            
            # Volatility
            daily_counts = {}
            for f in verified_features:
                if f.processed_at:
                    day = f.processed_at.date()
                    daily_counts[day] = daily_counts.get(day, 0) + 1
            counts = list(daily_counts.values()) if daily_counts else [0]
            msg_volatility = float(np.std(counts)) if len(counts) > 1 else 0.0
        else:
            complaint_rate_30d = 0.0
            avg_msg_length_30d = 0.0
            response_delay_mean = 0.0
            msg_volatility = 0.0
        
        # === BUILD FEATURE MAP (explicit, not positional) ===
        feature_map = {
            "recency_days": float(recency_days),
            "tx_count_30d": float(tx_count_30d),
            "tx_count_90d": float(tx_count_90d),
            "spend_30d": spend_30d,
            "spend_90d": spend_90d,
            "avg_tx_value": avg_tx_value,
            "tenure_days": float(tenure_days),
            "msg_count_7d": float(msg_count_7d),
            "msg_count_30d": float(msg_count_30d),
            "msg_volatility": msg_volatility,
            "avg_msg_length_30d": avg_msg_length_30d,
            "complaint_rate_30d": complaint_rate_30d,
            "response_delay_mean": response_delay_mean,
        }
        
        # === ENFORCED ORDER from FEATURE_SCHEMA ===
        # This guarantees vector order matches schema definition
        features = [feature_map[name] for name, _ in self.FEATURE_SCHEMA]
        
        # === VALIDATE SCHEMA ===
        expected = self.expected_feature_count()
        if len(features) != expected:
            raise RuntimeError(
                f"Feature schema mismatch: computed {len(features)}, expected {expected}"
            )
        
        # How many verified feedbacks actually used in text signals
        verified_used = len(verified_features)
        
        return {
            "features": features,
            "feature_names": self.get_feature_names(),
            "feature_schema_hash": self.get_feature_schema_hash(),
            "feature_service_version": self.FEATURE_SCHEMA_VERSION,
            "verified_feedback_count": verified_count,
            "verified_feedback_used": verified_used,
            "feature_window_days": 30,
            "as_of": as_of.isoformat(),  # Full timestamp for reproducibility
            "as_of_date": as_of_date.isoformat()
        }
    
    # =========================================================================
    # Private Methods
    # =========================================================================
    
    def _calculate_msg_volatility_from_features(
        self, 
        features: List[FeedbackFeatures], 
        start_date: date, 
        end_date: date
    ) -> float:
        """
        Calculate std dev of daily message count FROM FILTERED FEATURES
        
        Not from DB query - uses already filtered high-confidence data.
        """
        if not features:
            return 0.0
        
        # Group by date
        daily_counts = {}
        for f in features:
            if f.processed_at:
                day = f.processed_at.date()
                daily_counts[day] = daily_counts.get(day, 0) + 1
        
        # Fill missing days with 0
        total_days = (end_date - start_date).days
        counts = []
        current = start_date
        while current <= end_date:
            counts.append(daily_counts.get(current, 0))
            current += timedelta(days=1)
        
        return float(np.std(counts)) if counts else 0.0
