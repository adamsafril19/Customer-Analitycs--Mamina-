"""
Feature Engineering Configuration — v3.0.0

DESIGN PRINCIPLES:
- Defaults live IN CODE for reproducibility & auditability
- Override via Flask app.config['FEATURE_CONFIG'] or constructor injection
- NOT purely .env — modeling parameters need structure
- Immutable after creation (dataclass frozen=True)

Usage:
    # Default config (recommended for production)
    config = FeatureConfig()

    # Override for experimentation
    config = FeatureConfig(smoothing_window=5, smoothing_method='ema')

    # Override from Flask config dict
    config = FeatureConfig.from_dict(app.config.get('FEATURE_CONFIG', {}))
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FeatureConfig:
    """
    Immutable configuration for feature engineering parameters.

    All parameters have sensible defaults. Override for experimentation only.
    """

    # =========================================================================
    # SMOOTHING PARAMETERS
    # =========================================================================

    # Smoothing method: 'sma' (Simple Moving Average) or 'ema' (Exponential Moving Average)
    # Default SMA for stability and interpretability
    smoothing_method: str = "sma"

    # Window size for smoothing (number of periods to average)
    # For SMA: rolling window of this size
    # For EMA: span parameter (higher = smoother)
    smoothing_window: int = 3

    # EMA alpha (smoothing factor). If None, computed from smoothing_window as 2/(window+1)
    # Only used when smoothing_method='ema'
    ema_alpha: Optional[float] = None

    # =========================================================================
    # ACTIVITY WINDOW PARAMETERS
    # =========================================================================

    # Number of historical windows for activity statistics (mean, std, trend)
    activity_windows: int = 3

    # Size of each activity window in days
    window_size_days: int = 30

    # =========================================================================
    # VOLATILITY / CV PARAMETERS
    # =========================================================================

    # Floor for CV denominator to avoid division-by-zero
    # If mean < threshold, CV defaults to 0.0 (inactive user = not volatile)
    min_activity_threshold: float = 0.01

    # Cap for coefficient of variation (prevent extreme outliers)
    cv_cap: float = 10.0

    # =========================================================================
    # TREND PARAMETERS
    # =========================================================================

    # Cap for safe ratio computation (prevents extreme values)
    ratio_cap: float = 10.0

    # Default value when both numerator and denominator are zero
    ratio_default: float = 1.0

    # =========================================================================
    # FEATURE SCHEMA VERSION
    # =========================================================================

    schema_version: str = "v3.0.0"

    def __post_init__(self):
        """Validate configuration after creation."""
        if self.smoothing_method not in ("sma", "ema"):
            raise ValueError(
                f"smoothing_method must be 'sma' or 'ema', got '{self.smoothing_method}'"
            )
        if self.smoothing_window < 1:
            raise ValueError(f"smoothing_window must be >= 1, got {self.smoothing_window}")
        if self.activity_windows < 2:
            raise ValueError(f"activity_windows must be >= 2, got {self.activity_windows}")
        if self.window_size_days < 1:
            raise ValueError(f"window_size_days must be >= 1, got {self.window_size_days}")
        if self.min_activity_threshold < 0:
            raise ValueError(f"min_activity_threshold must be >= 0, got {self.min_activity_threshold}")
        if self.ema_alpha is not None and not (0 < self.ema_alpha <= 1):
            raise ValueError(f"ema_alpha must be in (0, 1], got {self.ema_alpha}")

    @classmethod
    def from_dict(cls, d: dict) -> "FeatureConfig":
        """
        Create FeatureConfig from a dictionary.

        Ignores unknown keys (safe for Flask config merge).
        Only applies keys that exist as fields.

        Usage:
            config = FeatureConfig.from_dict(app.config.get('FEATURE_CONFIG', {}))
        """
        import dataclasses
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        return cls(**filtered)

    def get_ema_alpha(self) -> float:
        """Get EMA alpha, computing from window if not explicitly set."""
        if self.ema_alpha is not None:
            return self.ema_alpha
        return 2.0 / (self.smoothing_window + 1)

    @property
    def total_lookback_days(self) -> int:
        """Total lookback period = activity_windows * window_size_days."""
        return self.activity_windows * self.window_size_days

    def to_dict(self) -> dict:
        """Serialize to dict for metadata/logging."""
        import dataclasses
        return dataclasses.asdict(self)
