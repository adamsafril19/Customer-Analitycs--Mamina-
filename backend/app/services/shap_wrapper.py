"""Pickle-safe callables used by saved SHAP explainers."""
from typing import Any

import numpy as np
import pandas as pd


def coerce_numeric_array(values: Any) -> np.ndarray:
    """Convert feature matrix to a pure float array for XGBoost/SHAP."""
    df = pd.DataFrame(values)
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.strip("[]")
                .replace({"": np.nan, "None": np.nan, "nan": np.nan})
            )
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.fillna(0.0).to_numpy(dtype=np.float32)


class RiskProbabilityModel:
    """Callable wrapper returning the positive-class risk probability."""

    def __init__(self, model, neutralized_indices=None):
        self.model = model
        self.neutralized_indices = neutralized_indices or []

    def __call__(self, values):
        features = coerce_numeric_array(values)
        for idx in self.neutralized_indices:
            if idx < features.shape[1]:
                features[:, idx] = 0.0
        return self.model.predict_proba(features)[:, 1]


class GatedRiskModel:
    """Composite estimator: transaction XGBoost plus logistic communication adjustment."""

    META_FEATURE_NAMES = (
        "base_risk_score",
        "complaint_ratio",
        "msg_trend_smoothed",
        "log_response_delay_mean",
    )

    def __init__(
        self,
        base_model,
        adjuster,
        feature_names,
        base_neutralized_features,
        adjustment_enabled=True,
    ):
        self.base_model = base_model
        self.adjuster = adjuster
        self.feature_names = list(feature_names)
        self.base_neutralized_indices = [
            self.feature_names.index(name)
            for name in base_neutralized_features
            if name in self.feature_names
        ]
        self.gate_index = self.feature_names.index("has_communication_90d")
        self.complaint_index = self.feature_names.index("complaint_ratio")
        self.message_trend_index = self.feature_names.index("msg_trend_smoothed")
        self.response_delay_index = self.feature_names.index("response_delay_mean")
        self.adjustment_enabled = bool(adjustment_enabled and adjuster is not None)
        self.classes_ = np.asarray([0, 1])
        self.n_features_in_ = len(self.feature_names)

    def _base_features(self, values):
        features = coerce_numeric_array(values)
        base_features = features.copy()
        for idx in self.base_neutralized_indices:
            base_features[:, idx] = 0.0
        return features, base_features

    def build_meta_features(self, values, base_scores=None):
        features, base_features = self._base_features(values)
        if base_scores is None:
            base_scores = self.base_model.predict_proba(base_features)[:, 1]
        response_delay = np.log1p(
            np.maximum(features[:, self.response_delay_index], 0.0)
        )
        return np.column_stack(
            [
                np.asarray(base_scores, dtype=float),
                features[:, self.complaint_index],
                features[:, self.message_trend_index],
                response_delay,
            ]
        )

    def predict_proba(self, values):
        features, base_features = self._base_features(values)
        base_scores = self.base_model.predict_proba(base_features)[:, 1]
        final_scores = base_scores.copy()

        if self.adjustment_enabled:
            gate = features[:, self.gate_index] >= 0.5
            if np.any(gate):
                meta_features = self.build_meta_features(
                    features[gate],
                    base_scores=base_scores[gate],
                )
                final_scores[gate] = self.adjuster.predict_proba(meta_features)[:, 1]

        final_scores = np.clip(final_scores, 0.0, 1.0)
        return np.column_stack([1.0 - final_scores, final_scores])

    def predict(self, values):
        return (self.predict_proba(values)[:, 1] >= 0.5).astype(int)

    @property
    def feature_importances_(self):
        values = np.asarray(
            getattr(self.base_model, "feature_importances_", np.zeros(self.n_features_in_)),
            dtype=float,
        ).copy()
        for idx in self.base_neutralized_indices:
            if idx < len(values):
                values[idx] = 0.0
        return values
