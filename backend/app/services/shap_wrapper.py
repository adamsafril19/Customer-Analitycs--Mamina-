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
