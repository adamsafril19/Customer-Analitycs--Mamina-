"""
Feature Engineering Service — v3.0.0 (Smoothed Trend + Magnitude + Volatility)

DESIGN PRINCIPLES (3 dimensi perilaku):
  1. TREND      — Arah perubahan aktivitas (smoothed, de-noised)
  2. MAGNITUDE  — Tingkat aktivitas absolut & relatif
  3. VOLATILITY — Stabilitas / konsistensi aktivitas

Tambahan:
  - INTERACTION — Trend × Magnitude (penurunan user aktif > penurunan user pasif)
  - SMOOTHING   — Moving Average (SMA/EMA) pada time series aktivitas

KEY CHANGES from v2:
  - Raw ratio trends (frequency_trend, spend_trend, msg_trend) → REPLACED with
    smoothed slope (frequency_trend_smoothed, spend_trend_smoothed, msg_trend_smoothed)
  - NEW: activity_mean, recent_activity_avg (Magnitude)
  - NEW: activity_std, activity_cv, spend_volatility_cv (Volatility)
  - NEW: trend_magnitude_interaction (Interaction)
  - Configurable parameters via FeatureConfig (structured, not .env)

Features must be:
  - Temporal-safe (no future leakage)
  - From VERIFIED linked records only
  - Deviation-normalized per user
  - Smoothed to reduce noise
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
from app.services.feature_config import FeatureConfig

logger = logging.getLogger(__name__)

# ML only uses verified identity (human-validated)
LINK_STATUS_FOR_ML = ['verified']

# Dashboard can use probable
LINK_STATUS_FOR_DASHBOARD = ['verified', 'probable']


class FeatureService:
    """
    Feature Engineering Service (Behavioral Risk Scoring v3)

    Output: 20 features = Trend(5) + Context(5) + Magnitude(2) + Volatility(3) + Interaction(1) + NLP(4)

    Configuration:
        config = FeatureConfig()  # defaults
        svc = FeatureService(config=config)
        # Or override for experimentation:
        svc = FeatureService(config=FeatureConfig(smoothing_method='ema'))
    """

    # =====================================================================
    # FEATURE SCHEMA v3 — ORDER MATTERS!
    # =====================================================================
    FEATURE_SCHEMA = [
        # === TREND (smoothed, de-noised) ===
        ("recency_ratio", "numeric"),                  # recency_days / avg_interpurchase_days
        ("frequency_trend_smoothed", "numeric"),       # slope of smoothed tx count series
        ("spend_trend_smoothed", "numeric"),           # slope of smoothed spend series
        ("msg_trend_smoothed", "numeric"),             # slope of smoothed msg count series
        ("sentiment_trend", "numeric"),                # sentiment_30d - sentiment_prior_30d
        # === ABSOLUTE CONTEXT ===
        ("recency_days", "numeric"),                   # days since last transaction
        ("tx_count_90d", "numeric"),                   # transaction count in 90 days
        ("spend_90d", "numeric"),                      # total spending in 90 days
        ("avg_tx_value", "numeric"),                   # average transaction value
        ("tenure_days", "numeric"),                    # customer lifetime in days
        # === MAGNITUDE (activity level) ===
        ("activity_mean", "numeric"),                  # mean tx count per window (3 windows)
        ("recent_activity_avg", "numeric"),            # tx count in most recent window
        # === VOLATILITY (stability) ===
        ("activity_std", "numeric"),                   # std of tx count per window
        ("activity_cv", "numeric"),                    # coefficient of variation (std/mean, capped)
        ("spend_volatility_cv", "numeric"),            # CV of spend per window
        # === INTERACTION ===
        ("trend_magnitude_interaction", "numeric"),    # frequency_trend_smoothed × activity_mean
        # === NLP / COMMUNICATION ===
        ("avg_sentiment_score", "numeric"),            # mean sentiment valence 30d
        ("complaint_ratio", "numeric"),                # complaint messages / total messages 30d
        ("msg_volatility", "numeric"),                 # std dev of daily message count
        ("response_delay_mean", "numeric"),            # mean admin response time (seconds)
    ]

    # Schema version — increment when feature set changes
    FEATURE_SCHEMA_VERSION = "v3.0.0"

    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize FeatureService with configuration.

        Args:
            config: FeatureConfig instance. If None, uses defaults.
                    For Flask integration:
                        config = FeatureConfig.from_dict(app.config.get('FEATURE_CONFIG', {}))
        """
        self.config = config or FeatureConfig()

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

        NOTE: This persists the BASE columns (recency_days, tx_count, spend, etc.).
        Derived features (smoothed trends, magnitude, volatility) are computed
        on-the-fly in get_ml_feature_vector() — not stored in DB.
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
    # ML Feature Assembly (v3 — smoothed trend + magnitude + volatility)
    # =========================================================================

    def get_ml_feature_vector(self, customer_id: str, as_of_date: Optional[date] = None) -> Optional[List[float]]:
        """
        Assemble 20-feature vector for ML (v3 risk scoring).

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

        # Compute derived values
        avg_ipt = self._compute_avg_interpurchase_days(customer_id, as_of_dt)
        sentiment = self._compute_sentiment_features(customer_id, as_of_date)

        # === NEW: Windowed activity series ===
        tx_series = self._compute_windowed_series(customer_id, as_of_date, metric="tx_count")
        spend_series = self._compute_windowed_series(customer_id, as_of_date, metric="spend")
        msg_series = self._compute_windowed_msg_series(customer_id, as_of_date)

        # === SMOOTHING ===
        tx_smoothed = self._apply_smoothing(tx_series)
        spend_smoothed = self._apply_smoothing(spend_series)
        msg_smoothed = self._apply_smoothing(msg_series)

        # === TREND (slope of smoothed series) ===
        freq_trend = self._compute_trend_slope(tx_smoothed)
        spend_trend = self._compute_trend_slope(spend_smoothed)
        msg_trend = self._compute_trend_slope(msg_smoothed)

        # === MAGNITUDE ===
        magnitude = self._compute_magnitude_features(tx_series)

        # === VOLATILITY ===
        volatility = self._compute_volatility_features(tx_series, spend_series)

        # === INTERACTION ===
        trend_mag_interaction = freq_trend * magnitude["activity_mean"]

        # Assemble vector (order MUST match FEATURE_SCHEMA)
        return [
            # === TREND ===
            self._safe_ratio(recency_days, avg_ipt),
            freq_trend,
            spend_trend,
            msg_trend,
            sentiment["sentiment_trend"],
            # === ABSOLUTE CONTEXT ===
            recency_days,
            float(numeric.tx_count_90d or 0),
            numeric.spend_90d or 0.0,
            numeric.avg_tx_value or 0.0,
            float(numeric.tenure_days or 0),
            # === MAGNITUDE ===
            magnitude["activity_mean"],
            magnitude["recent_activity_avg"],
            # === VOLATILITY ===
            volatility["activity_std"],
            volatility["activity_cv"],
            volatility["spend_volatility_cv"],
            # === INTERACTION ===
            trend_mag_interaction,
            # === NLP / COMMUNICATION ===
            sentiment["avg_sentiment_score"],
            signals.complaint_rate_30d or 0.0 if signals else 0.0,
            signals.msg_volatility or 0.0 if signals else 0.0,
            signals.response_delay_mean or 0.0 if signals else 0.0,
        ]

    def get_ml_feature_dict(self, customer_id: str, as_of_date: Optional[date] = None) -> Optional[Dict[str, float]]:
        """Get feature dict with names for SHAP (v3 schema)"""
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
        PURE FUNCTION: Build v3 feature vector from VERIFIED evidence only.

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
        cfg = self.config
        total_lookback = cfg.total_lookback_days  # e.g., 90 days for 3 windows × 30d

        thirty_days_ago = datetime.combine(as_of_date - timedelta(days=cfg.window_size_days), datetime.min.time())
        lookback_start = datetime.combine(as_of_date - timedelta(days=total_lookback), datetime.min.time())

        # === TRANSACTION FEATURES ===
        last_tx = db.session.query(func.max(Transaction.tx_date)).filter(
            Transaction.customer_id == customer_id,
            Transaction.status == "completed",
            Transaction.tx_date <= as_of_dt
        ).scalar()
        recency_days = (as_of_date - last_tx.date()).days if last_tx else 999

        tx_count_90d = db.session.query(func.count(Transaction.tx_id)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= lookback_start, Transaction.tx_date <= as_of_dt
        ).scalar() or 0

        spend_90d = float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.customer_id == customer_id, Transaction.status == "completed",
            Transaction.tx_date >= lookback_start, Transaction.tx_date <= as_of_dt
        ).scalar() or 0)

        avg_tx_value = spend_90d / tx_count_90d if tx_count_90d else 0.0

        customer = db.session.query(Customer.created_at).filter(
            Customer.customer_id == customer_id
        ).first()
        tenure_days = (as_of_date - customer.created_at.date()).days if customer and customer.created_at else 0

        # === AVG INTERPURCHASE TIME ===
        avg_ipt = self._compute_avg_interpurchase_days(customer_id, as_of_dt)

        # === WINDOWED ACTIVITY SERIES ===
        tx_series = self._compute_windowed_series(customer_id, as_of_date, metric="tx_count")
        spend_series = self._compute_windowed_series(customer_id, as_of_date, metric="spend")
        msg_series = self._compute_windowed_msg_series_verified(customer_id, as_of_date)

        # === SMOOTHING ===
        tx_smoothed = self._apply_smoothing(tx_series)
        spend_smoothed = self._apply_smoothing(spend_series)
        msg_smoothed = self._apply_smoothing(msg_series)

        # === TREND (slope of smoothed) ===
        freq_trend = self._compute_trend_slope(tx_smoothed)
        spend_trend = self._compute_trend_slope(spend_smoothed)
        msg_trend = self._compute_trend_slope(msg_smoothed)

        # === MAGNITUDE ===
        magnitude = self._compute_magnitude_features(tx_series)

        # === VOLATILITY ===
        volatility = self._compute_volatility_features(tx_series, spend_series)

        # === INTERACTION ===
        trend_mag_interaction = freq_trend * magnitude["activity_mean"]

        # === TEXT SIGNALS (from VERIFIED feedback, most recent window) ===
        verified_features_current = db.session.query(FeedbackFeatures).join(
            FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
        ).filter(
            FeedbackLinked.customer_id == customer_id,
            FeedbackLinked.link_status == 'verified',
            FeedbackFeatures.processed_at >= thirty_days_ago,
            FeedbackFeatures.processed_at <= as_of_dt
        ).order_by(FeedbackFeatures.feature_id).all()

        msg_count_30d = len(verified_features_current)

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
            # Trend
            "recency_ratio": self._safe_ratio(float(recency_days), avg_ipt),
            "frequency_trend_smoothed": freq_trend,
            "spend_trend_smoothed": spend_trend,
            "msg_trend_smoothed": msg_trend,
            "sentiment_trend": sentiment["sentiment_trend"],
            # Context
            "recency_days": float(recency_days),
            "tx_count_90d": float(tx_count_90d),
            "spend_90d": spend_90d,
            "avg_tx_value": avg_tx_value,
            "tenure_days": float(tenure_days),
            # Magnitude
            "activity_mean": magnitude["activity_mean"],
            "recent_activity_avg": magnitude["recent_activity_avg"],
            # Volatility
            "activity_std": volatility["activity_std"],
            "activity_cv": volatility["activity_cv"],
            "spend_volatility_cv": volatility["spend_volatility_cv"],
            # Interaction
            "trend_magnitude_interaction": trend_mag_interaction,
            # NLP
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
            "feature_config": self.config.to_dict(),
            "verified_feedback_count": verified_count,
            "verified_feedback_used": msg_count_30d,
            "feature_window_days": self.config.window_size_days,
            "as_of": as_of.isoformat(),
            "as_of_date": as_of_date.isoformat()
        }

    # =========================================================================
    # SMOOTHING ENGINE
    # =========================================================================

    def _apply_smoothing(self, series: List[float]) -> List[float]:
        """
        Apply smoothing to a time series.

        Supports SMA (Simple Moving Average) and EMA (Exponential Moving Average).
        Method and parameters controlled by self.config.

        Args:
            series: Raw time series values (oldest → newest)

        Returns:
            Smoothed series (same length)

        Behavioral meaning:
            Smoothing de-noises the activity signal so that trend computation
            is not overly sensitive to single-period fluctuations.
        """
        if len(series) <= 1:
            return series[:]

        if self.config.smoothing_method == "sma":
            return self._apply_sma(series, self.config.smoothing_window)
        elif self.config.smoothing_method == "ema":
            return self._apply_ema(series, self.config.get_ema_alpha())
        else:
            # Fallback to SMA (should not reach here due to config validation)
            return self._apply_sma(series, self.config.smoothing_window)

    @staticmethod
    def _apply_sma(series: List[float], window: int) -> List[float]:
        """
        Simple Moving Average.

        Definisi: SMA_t = mean(series[max(0,t-w+1):t+1])
        Untuk awal series dimana data < window, gunakan semua data yang tersedia.

        Args:
            series: Time series (oldest → newest)
            window: Window size

        Returns:
            Smoothed series (same length, leading values use available data)
        """
        if not series:
            return []
        result = []
        for i in range(len(series)):
            start = max(0, i - window + 1)
            result.append(float(np.mean(series[start:i + 1])))
        return result

    @staticmethod
    def _apply_ema(series: List[float], alpha: float) -> List[float]:
        """
        Exponential Moving Average.

        Definisi: EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
        EMA_0 = x_0

        Args:
            series: Time series (oldest → newest)
            alpha: Smoothing factor (0 < alpha <= 1). Higher = less smoothing.

        Returns:
            Smoothed series (same length)
        """
        if not series:
            return []
        result = [series[0]]
        for i in range(1, len(series)):
            ema_val = alpha * series[i] + (1 - alpha) * result[i - 1]
            result.append(ema_val)
        return result

    # =========================================================================
    # WINDOWED ACTIVITY SERIES
    # =========================================================================

    def _compute_windowed_series(
        self,
        customer_id: str,
        as_of_date: date,
        metric: str = "tx_count"
    ) -> List[float]:
        """
        Compute per-window activity series for a customer.

        Splits the lookback period into N windows of W days each.
        Windows are ordered oldest → newest.

        Args:
            customer_id: Customer UUID
            as_of_date: Reference date
            metric: "tx_count" or "spend"

        Returns:
            List of per-window values (oldest → newest), length = activity_windows

        Example (3 windows × 30d, as_of_date = 2026-04-01):
            Window 0: [2026-01-01, 2026-01-31)  ← oldest
            Window 1: [2026-01-31, 2026-03-02)
            Window 2: [2026-03-02, 2026-04-01]  ← newest (most recent)
        """
        cfg = self.config
        series = []

        for i in range(cfg.activity_windows):
            # Windows are indexed from oldest (i=0) to newest (i=N-1)
            window_idx = cfg.activity_windows - 1 - i
            window_end_date = as_of_date - timedelta(days=window_idx * cfg.window_size_days)
            window_start_date = window_end_date - timedelta(days=cfg.window_size_days)

            window_start = datetime.combine(window_start_date, datetime.min.time())
            window_end = datetime.combine(window_end_date, datetime.max.time())

            if metric == "tx_count":
                value = db.session.query(func.count(Transaction.tx_id)).filter(
                    Transaction.customer_id == customer_id,
                    Transaction.status == "completed",
                    Transaction.tx_date >= window_start,
                    Transaction.tx_date <= window_end
                ).scalar() or 0
                series.append(float(value))
            elif metric == "spend":
                value = db.session.query(
                    func.coalesce(func.sum(Transaction.amount), 0)
                ).filter(
                    Transaction.customer_id == customer_id,
                    Transaction.status == "completed",
                    Transaction.tx_date >= window_start,
                    Transaction.tx_date <= window_end
                ).scalar() or 0
                series.append(float(value))

        return series

    def _compute_windowed_msg_series(
        self,
        customer_id: str,
        as_of_date: date
    ) -> List[float]:
        """
        Compute per-window message count series (any link status for non-verified path).

        Args:
            customer_id: Customer UUID
            as_of_date: Reference date

        Returns:
            List of per-window message counts (oldest → newest)
        """
        cfg = self.config
        series = []

        for i in range(cfg.activity_windows):
            window_idx = cfg.activity_windows - 1 - i
            window_end_date = as_of_date - timedelta(days=window_idx * cfg.window_size_days)
            window_start_date = window_end_date - timedelta(days=cfg.window_size_days)

            window_start = datetime.combine(window_start_date, datetime.min.time())
            window_end = datetime.combine(window_end_date, datetime.max.time())

            count = db.session.query(func.count(FeedbackFeatures.feature_id)).join(
                FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
            ).filter(
                FeedbackLinked.customer_id == customer_id,
                FeedbackLinked.link_status.in_(LINK_STATUS_FOR_ML),
                FeedbackFeatures.processed_at >= window_start,
                FeedbackFeatures.processed_at <= window_end
            ).scalar() or 0

            series.append(float(count))

        return series

    def _compute_windowed_msg_series_verified(
        self,
        customer_id: str,
        as_of_date: date
    ) -> List[float]:
        """
        Compute per-window message count series (VERIFIED only, for build_verified_features).
        """
        cfg = self.config
        series = []

        for i in range(cfg.activity_windows):
            window_idx = cfg.activity_windows - 1 - i
            window_end_date = as_of_date - timedelta(days=window_idx * cfg.window_size_days)
            window_start_date = window_end_date - timedelta(days=cfg.window_size_days)

            window_start = datetime.combine(window_start_date, datetime.min.time())
            window_end = datetime.combine(window_end_date, datetime.max.time())

            count = db.session.query(func.count(FeedbackFeatures.feature_id)).join(
                FeedbackLinked, FeedbackFeatures.link_id == FeedbackLinked.link_id
            ).filter(
                FeedbackLinked.customer_id == customer_id,
                FeedbackLinked.link_status == 'verified',
                FeedbackFeatures.processed_at >= window_start,
                FeedbackFeatures.processed_at <= window_end
            ).scalar() or 0

            series.append(float(count))

        return series

    # =========================================================================
    # TREND COMPUTATION
    # =========================================================================

    @staticmethod
    def _compute_trend_slope(smoothed_series: List[float]) -> float:
        """
        Compute trend slope via linear regression on smoothed series.

        Definisi matematis:
            slope = Σ((t - t̄)(y - ȳ)) / Σ((t - t̄)²)
            dimana t = index waktu, y = nilai smoothed

        Tujuan:
            Mengukur arah perubahan aktivitas. Positif = meningkat, negatif = menurun.
            Menggunakan data smoothed agar tidak sensitif terhadap fluktuasi single-period.

        Args:
            smoothed_series: Smoothed time series (oldest → newest)

        Returns:
            Slope value. 0.0 if series is too short.
        """
        n = len(smoothed_series)
        if n < 2:
            return 0.0

        # Simple linear regression: slope = cov(t, y) / var(t)
        t = np.arange(n, dtype=float)
        y = np.array(smoothed_series, dtype=float)

        t_mean = t.mean()
        y_mean = y.mean()

        numerator = np.sum((t - t_mean) * (y - y_mean))
        denominator = np.sum((t - t_mean) ** 2)

        if denominator == 0:
            return 0.0

        return float(numerator / denominator)

    # =========================================================================
    # MAGNITUDE FEATURES
    # =========================================================================

    def _compute_magnitude_features(self, tx_series: List[float]) -> Dict[str, float]:
        """
        Compute magnitude (activity level) features.

        Features:
            activity_mean: Mean tx count across all windows.
                Definisi: mean(tx_count per window)
                Tujuan: Representasi "seberapa aktif" customer secara keseluruhan.
                Alasan: Model perlu konteks absolute activity level agar penurunan
                        pada user aktif diperlakukan berbeda dari user pasif.

            recent_activity_avg: Tx count in most recent window.
                Definisi: tx_count di window terakhir (paling baru)
                Tujuan: Representasi aktivitas terkini.
                Alasan: User yang baru saja aktif berbeda risikonya dari user
                        yang sudah lama tidak aktif, meskipun mean-nya sama.

        NOTE: activity_total (sum of all windows) TIDAK ditambahkan karena
              secara semantik identik dengan tx_count_90d (3 windows × 30d = 90d).
              Menambahkannya akan redundan tanpa informasi baru.

        Args:
            tx_series: Per-window transaction counts (oldest → newest)

        Returns:
            Dict with activity_mean, recent_activity_avg
        """
        if not tx_series:
            return {"activity_mean": 0.0, "recent_activity_avg": 0.0}

        return {
            "activity_mean": float(np.mean(tx_series)),
            "recent_activity_avg": float(tx_series[-1])  # Most recent window
        }

    # =========================================================================
    # VOLATILITY FEATURES
    # =========================================================================

    def _compute_volatility_features(
        self,
        tx_series: List[float],
        spend_series: List[float]
    ) -> Dict[str, float]:
        """
        Compute volatility (stability) features.

        Features:
            activity_std: Standard deviation of tx count per window.
                Definisi: std(tx_count per window)
                Tujuan: Mengukur seberapa stabil pola transaksi customer.
                Alasan: Customer dengan aktivitas stabil (std rendah) memiliki
                        pola yang predictable, sedangkan volatil (std tinggi)
                        menunjukkan perilaku tidak konsisten.

            activity_cv: Coefficient of Variation = std / mean.
                Definisi: activity_std / activity_mean (capped, zero-safe)
                Tujuan: Volatilitas relatif terhadap tingkat aktivitas.
                Alasan: std = 2 berarti berbeda untuk user dengan mean = 10 (CV = 0.2)
                        vs mean = 2 (CV = 1.0). CV menormalisasi volatilitas.
                Edge case: Jika mean < min_activity_threshold → CV = 0.0
                           (user sangat tidak aktif = bukan volatile, tapi dormant)

            spend_volatility_cv: CV of spend per window.
                Definisi: std(spend per window) / mean(spend per window) (capped)
                Tujuan: Stabilitas pola belanja.
                Alasan: Pelengkap activity_cv. Customer bisa stabil dalam frekuensi
                        tapi volatile dalam nominal belanja (atau sebaliknya).

        Args:
            tx_series: Per-window transaction counts
            spend_series: Per-window spend amounts

        Returns:
            Dict with activity_std, activity_cv, spend_volatility_cv
        """
        cfg = self.config

        # Activity volatility
        if len(tx_series) >= 2:
            activity_std = float(np.std(tx_series, ddof=0))
            activity_mean = float(np.mean(tx_series))
            if activity_mean >= cfg.min_activity_threshold:
                activity_cv = min(cfg.cv_cap, activity_std / activity_mean)
            else:
                # User sangat tidak aktif → bukan volatile, tapi dormant
                activity_cv = 0.0
        else:
            activity_std = 0.0
            activity_cv = 0.0

        # Spend volatility
        if len(spend_series) >= 2:
            spend_std = float(np.std(spend_series, ddof=0))
            spend_mean = float(np.mean(spend_series))
            if spend_mean >= cfg.min_activity_threshold:
                spend_volatility_cv = min(cfg.cv_cap, spend_std / spend_mean)
            else:
                spend_volatility_cv = 0.0
        else:
            spend_volatility_cv = 0.0

        return {
            "activity_std": activity_std,
            "activity_cv": activity_cv,
            "spend_volatility_cv": spend_volatility_cv
        }

    # =========================================================================
    # Private Helpers (preserved from v2, updated where needed)
    # =========================================================================

    def _safe_ratio(self, current: float, prior: float,
                    default: Optional[float] = None,
                    cap: Optional[float] = None) -> float:
        """
        Safe division for trend/ratio features.
        - Both zero → default (no change)
        - Prior zero, current > 0 → cap (new activity emerged)
        - Normal → current / prior, capped
        """
        _default = default if default is not None else self.config.ratio_default
        _cap = cap if cap is not None else self.config.ratio_cap

        if prior == 0:
            if current == 0:
                return _default
            return _cap
        return min(_cap, current / prior)

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
