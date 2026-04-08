"""
Feature Engineering Service — v2.0.0 (Behavioral Risk Scoring)

RISK SCORING FEATURES: Deviation-based + contextual + NLP signals.

Key changes from v1:
- Fitur deviasi (recency_ratio, frequency_trend, spend_trend, msg_trend)
- Sentiment features masuk ke ML (avg_sentiment_score, sentiment_trend)
- complaint_ratio tetap ada
- Fitur absolut tetap ada sebagai konteks (recency_days, tx_count_90d, dll.)

Features must be:
- Temporal-safe (no future leakage)
- From VERIFIED linked records only
- Deviation-normalized per user (bukan threshold global)
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
from app.models.feedback import FeedbackRaw, FeedbackLinked, FeedbackFeatures
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_signals import CustomerTextSignals

logger = logging.getLogger(__name__)

# ML only uses verified identity (human-validated)
LINK_STATUS_FOR_ML = ['verified']

# Dashboard can use probable
LINK_STATUS_FOR_DASHBOARD = ['verified', 'probable']


class FeatureService:
    """
    Feature Engineering Service (Behavioral Risk Scoring v2)

    Output: 14 features combining deviation signals, absolute context, and NLP.
    """

    # Schema version — increment when feature set changes
    FEATURE_SCHEMA_VERSION = "v2.0.0"

    # =====================================================================
    # FEATURE SCHEMA v2 — ORDER MATTERS!
    # =====================================================================
    FEATURE_SCHEMA = [
        # === DEVIATION / TREND (core behavioral change signals) ===
        ("recency_ratio", "numeric"),       # recency_days / avg_interpurchase_days
        ("frequency_trend", "numeric"),     # tx_count_30d / tx_count_prior_30d
        ("spend_trend", "numeric"),         # spend_30d / spend_prior_30d
        ("msg_trend", "numeric"),           # msg_count_30d / msg_count_prior_30d
        ("sentiment_trend", "numeric"),     # sentiment_30d - sentiment_prior_30d
        # === ABSOLUTE CONTEXT ===
        ("recency_days", "numeric"),        # days since last transaction
        ("tx_count_90d", "numeric"),        # transaction count in 90 days
        ("spend_90d", "numeric"),           # total spending in 90 days
        ("avg_tx_value", "numeric"),        # average transaction value
        ("tenure_days", "numeric"),         # customer lifetime in days
        # === NLP / COMMUNICATION ===
        ("avg_sentiment_score", "numeric"), # mean sentiment valence 30d
        ("complaint_ratio", "numeric"),     # complaint messages / total messages 30d
        ("msg_volatility", "numeric"),      # std dev of daily message count
        ("response_delay_mean", "numeric"), # mean admin response time (seconds)
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
    # PUBLIC API — Feature Persistence (writes to DB, same schema as before)
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
        Calculate and persist transaction features to DB.

        NOTE: This persists the BASE columns (recency_days, tx_count_30d, etc.).
        Derived features (recency_ratio, trends) are computed on-the-fly
        in get_ml_feature_vector() — not stored in DB until migration.
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

        # === RAW TRANSACTION SIGNALS ===
        last_tx = db.session.query(func.max(Transaction.tx_date)).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date <= as_of_dt
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

        customer = db.session.query(Customer.created_at).filter(Customer.customer_id == customer_id).first()
        if customer and customer.created_at:
            created_date = customer.created_at.date() if hasattr(customer.created_at, 'date') else customer.created_at
            feature.tenure_days = (as_of_date - created_date).days if created_date <= as_of_date else 0
        else:
            feature.tenure_days = 0

        # === DERIVED RFM (Dashboard only — NOT in ML feature vector) ===
        feature.r_score = round(max(0.0, 5.0 - (feature.recency_days / 36.0)), 2)
        feature.f_score = round(min(5.0, float(feature.tx_count_90d or 0) / 2), 2)
        feature.m_score = round(min(5.0, (feature.spend_90d or 0) / 1_000_000), 2)

        db.session.commit()
        return feature

    def populate_text_signals(self, customer_id: str, as_of_date: Optional[date] = None) -> CustomerTextSignals:
        """
        Behavioral signals from text (ML sees).
        Only VERIFIED links. NO embedding.
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

        verified_features = db.session.query(FeedbackFeatures, FeedbackLinked).join(
            FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
        ).filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status.in_(LINK_STATUS_FOR_ML),
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

            signals.msg_volatility = self._calculate_msg_volatility_from_features(
                features_30d, thirty_days_ago, as_of_date
            )
        else:
            signals.complaint_rate_30d = 0.0
            signals.avg_msg_length_30d = 0.0
            signals.response_delay_mean = 0.0
            signals.msg_volatility = 0.0

        db.session.commit()
        return signals

    # =========================================================================
    # ML Feature Assembly (v2 — with deviation + sentiment)
    # =========================================================================

    def get_ml_feature_vector(self, customer_id: str, as_of_date: Optional[date] = None) -> Optional[List[float]]:
        """
        Assemble 14-feature vector for ML (v2 risk scoring).

        Reads persisted base features + computes derived features on-the-fly.
        """
        if as_of_date is None:
            as_of_date = date.today()

        numeric = CustomerNumericFeatures.query.filter_by(
            customer_id=customer_id, as_of_date=as_of_date
        ).first()
        signals = CustomerTextSignals.query.filter_by(
            customer_id=customer_id, as_of_date=as_of_date
        ).first()

        if not numeric:
            return None

        as_of_dt = datetime.combine(as_of_date, datetime.max.time())

        # Base values from persisted tables
        recency_days = float(numeric.recency_days or 0)
        tx_count_30d = float(numeric.tx_count_30d or 0)
        spend_30d = numeric.spend_30d or 0.0
        msg_count_30d = float(signals.msg_count_30d or 0) if signals else 0.0

        # Compute derived values
        avg_ipt = self._compute_avg_interpurchase_days(customer_id, as_of_dt)
        prior = self._compute_prior_period_stats(customer_id, as_of_date)
        sentiment = self._compute_sentiment_features(customer_id, as_of_date)

        # Assemble vector (order MUST match FEATURE_SCHEMA)
        return [
            # === DEVIATION / TREND ===
            self._safe_ratio(recency_days, avg_ipt),
            self._safe_ratio(tx_count_30d, prior["tx_count_prior_30d"]),
            self._safe_ratio(spend_30d, prior["spend_prior_30d"]),
            self._safe_ratio(msg_count_30d, prior["msg_count_prior_30d"]),
            sentiment["sentiment_trend"],
            # === ABSOLUTE CONTEXT ===
            recency_days,
            float(numeric.tx_count_90d or 0),
            numeric.spend_90d or 0.0,
            numeric.avg_tx_value or 0.0,
            float(numeric.tenure_days or 0),
            # === NLP / COMMUNICATION ===
            sentiment["avg_sentiment_score"],
            signals.complaint_rate_30d or 0.0 if signals else 0.0,
            signals.msg_volatility or 0.0 if signals else 0.0,
            signals.response_delay_mean or 0.0 if signals else 0.0,
        ]

    def get_ml_feature_dict(self, customer_id: str, as_of_date: Optional[date] = None) -> Optional[Dict[str, float]]:
        """Get feature dict with names for SHAP (v2 schema)"""
        if as_of_date is None:
            as_of_date = date.today()

        vector = self.get_ml_feature_vector(customer_id, as_of_date)
        if vector is None:
            return None

        names = self.get_feature_names()
        return dict(zip(names, vector))

    def build_verified_features(
        self,
        customer_id: str,
        as_of: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        PURE FUNCTION: Build v2 feature vector from VERIFIED evidence only.

        NO SIDE EFFECTS: No DB writes, deterministic for given as_of.
        """
        if as_of is None:
            as_of = datetime.utcnow()

        as_of_date = as_of.date() if hasattr(as_of, 'date') else as_of

        # === IDENTITY ENFORCEMENT ===
        verified_feedback = FeedbackLinked.query.filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status == 'verified',
            FeedbackLinked.linked_at <= as_of
        )
        verified_count = verified_feedback.count()

        if verified_count == 0:
            total = FeedbackLinked.query.filter_by(customer_id=customer_id).count()
            raise PermissionError(
                f"Cannot build features: customer {customer_id} has {total} feedback links "
                f"but ZERO are 'verified' as of {as_of.isoformat()}. ML requires verified identity."
            )

        # === TIME BOUNDARIES ===
        as_of_dt = datetime.combine(as_of_date, datetime.max.time())
        thirty_days_ago = datetime.combine(as_of_date - timedelta(days=30), datetime.min.time())
        sixty_days_ago = datetime.combine(as_of_date - timedelta(days=60), datetime.min.time())
        ninety_days_ago = datetime.combine(as_of_date - timedelta(days=90), datetime.min.time())
        thirty_ago_end = datetime.combine(as_of_date - timedelta(days=30), datetime.max.time())

        # === TRANSACTION FEATURES ===
        last_tx = db.session.query(func.max(Transaction.tx_date)).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date <= as_of_dt
        ).scalar()
        recency_days = (as_of_date - last_tx.date()).days if last_tx else 999

        tx_count_30d = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= thirty_days_ago, Transaction.tx_date <= as_of_dt
        ).scalar() or 0

        tx_count_90d = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= ninety_days_ago, Transaction.tx_date <= as_of_dt
        ).scalar() or 0

        spend_30d = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= thirty_days_ago, Transaction.tx_date <= as_of_dt
        ).scalar() or 0)

        spend_90d = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= ninety_days_ago, Transaction.tx_date <= as_of_dt
        ).scalar() or 0)

        avg_tx_value = spend_90d / tx_count_90d if tx_count_90d else 0.0

        customer = db.session.query(Customer.created_at).filter(
            Customer.customer_id == customer_id
        ).first()
        tenure_days = (as_of_date - customer.created_at.date()).days if customer and customer.created_at else 0

        # === PRIOR PERIOD (for trends) ===
        tx_count_prior = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= sixty_days_ago, Transaction.tx_date <= thirty_ago_end
        ).scalar() or 0

        spend_prior = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= sixty_days_ago, Transaction.tx_date <= thirty_ago_end
        ).scalar() or 0)

        # === AVG INTERPURCHASE TIME ===
        avg_ipt = self._compute_avg_interpurchase_days(customer_id, as_of_dt)

        # === TEXT SIGNALS (from VERIFIED feedback) ===
        verified_features_current = db.session.query(FeedbackFeatures).join(
            FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
        ).filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status == 'verified',
            FeedbackFeatures.processed_at >= thirty_days_ago,
            FeedbackFeatures.processed_at <= as_of_dt
        ).order_by(FeedbackFeatures.feature_id).all()

        verified_features_prior = db.session.query(FeedbackFeatures).join(
            FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
        ).filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status == 'verified',
            FeedbackFeatures.processed_at >= sixty_days_ago,
            FeedbackFeatures.processed_at <= thirty_ago_end
        ).order_by(FeedbackFeatures.feature_id).all()

        msg_count_30d = len(verified_features_current)
        msg_count_prior = len(verified_features_prior)

        if verified_features_current:
            complaint_count = len([f for f in verified_features_current if f.has_complaint])
            complaint_ratio = complaint_count / msg_count_30d

            delays = [f.response_time_secs for f in verified_features_current if f.response_time_secs]
            response_delay_mean = float(np.mean(delays)) if delays else 0.0

            daily_counts = {}
            for f in verified_features_current:
                if f.processed_at:
                    day = f.processed_at.date()
                    daily_counts[day] = daily_counts.get(day, 0) + 1
            counts = list(daily_counts.values()) if daily_counts else [0]
            msg_volatility = float(np.std(counts)) if len(counts) > 1 else 0.0
        else:
            complaint_ratio = 0.0
            response_delay_mean = 0.0
            msg_volatility = 0.0

        # === SENTIMENT FEATURES ===
        sentiment = self._compute_sentiment_features(customer_id, as_of_date)

        # === BUILD FEATURE MAP ===
        feature_map = {
            "recency_ratio": self._safe_ratio(float(recency_days), avg_ipt),
            "frequency_trend": self._safe_ratio(float(tx_count_30d), float(tx_count_prior)),
            "spend_trend": self._safe_ratio(spend_30d, spend_prior),
            "msg_trend": self._safe_ratio(float(msg_count_30d), float(msg_count_prior)),
            "sentiment_trend": sentiment["sentiment_trend"],
            "recency_days": float(recency_days),
            "tx_count_90d": float(tx_count_90d),
            "spend_90d": spend_90d,
            "avg_tx_value": avg_tx_value,
            "tenure_days": float(tenure_days),
            "avg_sentiment_score": sentiment["avg_sentiment_score"],
            "complaint_ratio": complaint_ratio,
            "msg_volatility": msg_volatility,
            "response_delay_mean": response_delay_mean,
        }

        # === ENFORCED ORDER from FEATURE_SCHEMA ===
        features = [feature_map[name] for name, _ in self.FEATURE_SCHEMA]

        expected = self.expected_feature_count()
        if len(features) != expected:
            raise RuntimeError(
                f"Feature schema mismatch: computed {len(features)}, expected {expected}"
            )

        return {
            "features": features,
            "feature_names": self.get_feature_names(),
            "feature_schema_hash": self.get_feature_schema_hash(),
            "feature_service_version": self.FEATURE_SCHEMA_VERSION,
            "verified_feedback_count": verified_count,
            "verified_feedback_used": msg_count_30d,
            "feature_window_days": 30,
            "as_of": as_of.isoformat(),
            "as_of_date": as_of_date.isoformat()
        }

    # =========================================================================
    # Private Helpers
    # =========================================================================

    @staticmethod
    def _safe_ratio(current: float, prior: float, default: float = 1.0, cap: float = 10.0) -> float:
        """
        Safe division for trend/ratio features.
        - Both zero → 1.0 (no change)
        - Prior zero, current > 0 → cap (new activity emerged)
        - Normal → current / prior, capped
        """
        if prior == 0:
            if current == 0:
                return default
            return cap
        return min(cap, current / prior)

    def _compute_avg_interpurchase_days(self, customer_id: str, as_of_dt: datetime) -> float:
        """Compute average days between consecutive transactions (personal baseline)."""
        tx_dates = db.session.query(Transaction.tx_date).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date <= as_of_dt
        ).order_by(Transaction.tx_date).all()

        dates = [t[0] for t in tx_dates]
        if len(dates) < 2:
            return 0.0

        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        return float(np.mean(gaps)) if gaps else 0.0

    def _compute_prior_period_stats(self, customer_id: str, as_of_date: date) -> dict:
        """Compute transaction + message stats for the prior 30-day window [t-60, t-30]."""
        prior_end = datetime.combine(as_of_date - timedelta(days=30), datetime.max.time())
        prior_start = datetime.combine(as_of_date - timedelta(days=60), datetime.min.time())

        tx_count_prior = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= prior_start, Transaction.tx_date <= prior_end
        ).scalar() or 0

        spend_prior = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= prior_start, Transaction.tx_date <= prior_end
        ).scalar() or 0)

        msg_count_prior = db.session.query(func.count(FeedbackFeatures.feature_id)).join(
            FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
        ).filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status.in_(LINK_STATUS_FOR_ML),
            FeedbackFeatures.processed_at >= prior_start,
            FeedbackFeatures.processed_at <= prior_end
        ).scalar() or 0

        return {
            "tx_count_prior_30d": tx_count_prior,
            "spend_prior_30d": spend_prior,
            "msg_count_prior_30d": msg_count_prior
        }

    def _compute_sentiment_features(self, customer_id: str, as_of_date: date) -> dict:
        """
        Compute sentiment features.
        Priority: 1) Pre-computed semantics table  2) Live SentimentService  3) Default 0.0
        """
        avg_score = 0.0
        prior_score = 0.0

        try:
            from app.models.text_semantics import CustomerTextSemantics

            # Current period
            current_sem = CustomerTextSemantics.query.filter_by(
                customer_id=customer_id, as_of_date=as_of_date
            ).first()

            if current_sem and current_sem.avg_sentiment_score is not None:
                avg_score = float(current_sem.avg_sentiment_score)

                # Prior period (closest entry <= 30 days ago)
                prior_date = as_of_date - timedelta(days=30)
                prior_sem = CustomerTextSemantics.query.filter(
                    CustomerTextSemantics.customer_id == customer_id,
                    CustomerTextSemantics.as_of_date <= prior_date
                ).order_by(CustomerTextSemantics.as_of_date.desc()).first()

                if prior_sem and prior_sem.avg_sentiment_score is not None:
                    prior_score = float(prior_sem.avg_sentiment_score)
            else:
                # Fallback: compute live using SentimentService
                avg_score, prior_score = self._compute_live_sentiment(customer_id, as_of_date)

        except Exception as e:
            logger.warning(f"Sentiment feature computation failed: {e}")

        return {
            "avg_sentiment_score": avg_score,
            "sentiment_trend": avg_score - prior_score
        }

    def _compute_live_sentiment(self, customer_id: str, as_of_date: date) -> tuple:
        """Fallback: compute sentiment on-the-fly when semantics table is empty."""
        try:
            from app.services.sentiment_service import SentimentService

            svc = SentimentService()
            if not svc.is_model_loaded():
                try:
                    svc.load_model()
                except Exception:
                    return 0.0, 0.0

            end_dt = datetime.combine(as_of_date, datetime.max.time())
            thirty_ago = datetime.combine(as_of_date - timedelta(days=30), datetime.min.time())
            sixty_ago = datetime.combine(as_of_date - timedelta(days=60), datetime.min.time())
            thirty_ago_end = datetime.combine(as_of_date - timedelta(days=30), datetime.max.time())

            def _avg_sentiment_for_period(start, end):
                msgs = db.session.query(FeedbackRaw).join(
                    FeedbackLinked, FeedbackRaw.msg_id == FeedbackLinked.msg_id
                ).filter(
                    FeedbackLinked.customer_id == customer_id,
                    FeedbackLinked.link_status.in_(LINK_STATUS_FOR_ML),
                    FeedbackRaw.timestamp >= start,
                    FeedbackRaw.timestamp <= end,
                    FeedbackRaw.direction == 'inbound'
                ).limit(20).all()

                scores = []
                for m in msgs:
                    if m.text:
                        try:
                            _, score = svc.predict(m.text)
                            scores.append(score)
                        except Exception:
                            pass
                return float(np.mean(scores)) if scores else 0.0

            avg_current = _avg_sentiment_for_period(thirty_ago, end_dt)
            avg_prior = _avg_sentiment_for_period(sixty_ago, thirty_ago_end)
            return avg_current, avg_prior

        except Exception as e:
            logger.warning(f"Live sentiment computation failed: {e}")
            return 0.0, 0.0

    def _calculate_msg_volatility_from_features(
        self,
        features: List[FeedbackFeatures],
        start_date: date,
        end_date: date
    ) -> float:
        """Calculate std dev of daily message count from pre-filtered features."""
        if not features:
            return 0.0

        daily_counts = {}
        for f in features:
            if f.processed_at:
                day = f.processed_at.date()
                daily_counts[day] = daily_counts.get(day, 0) + 1

        total_days = (end_date - start_date).days
        counts = []
        current = start_date
        while current <= end_date:
            counts.append(daily_counts.get(current, 0))
            current += timedelta(days=1)

        return float(np.std(counts)) if counts else 0.0
