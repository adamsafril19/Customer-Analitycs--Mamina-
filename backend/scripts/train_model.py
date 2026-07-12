#!/usr/bin/env python
"""
Churn Model Training Script

REFACTORED: Uses correct ontology (numeric + text_signals only)
ML model does NOT see semantic features (topic, sentiment)

Feature vector: [r_score, f_score, m_score, tenure_days,
                 msg_count_7d, msg_count_30d, msg_volatility,
                 avg_msg_length_30d, complaint_rate_30d, response_delay_mean]

Usage:
    python -m scripts.train_model --cutoff-date 2026-01-01
"""
import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional, Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    precision_score, recall_score, f1_score, 
    accuracy_score, roc_auc_score, average_precision_score
)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import func
import xgboost as xgb

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.customer import Customer
from app.models.text_signals import CustomerTextSignals
from app.models.transaction import Transaction
from app.models.topic import ModelVersion
from app.services.feature_service import FeatureService
from app.services.shap_wrapper import (
    GatedRiskModel,
    RiskProbabilityModel,
    coerce_numeric_array,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_CHURN_WINDOW_DAYS = 90
DEFAULT_OBSERVATION_WINDOW_DAYS = 90
BASE_NEUTRALIZED_MODEL_FEATURES = [
    "tenure_days",
    "avg_sentiment_score",
    "sentiment_trend",
]
COMMUNICATION_FEATURES = [
    "msg_trend_smoothed",
    "complaint_ratio",
    "msg_volatility",
    "response_delay_mean",
    "has_communication_90d",
]
MIN_TEXT_TRAINING_COVERAGE = 0.05
NEUTRALIZED_MODEL_FEATURES = list(BASE_NEUTRALIZED_MODEL_FEATURES)
XGB_PRODUCTION_PARAMS = {
    "n_estimators": 200,
    "max_depth": 3,
    "learning_rate": 0.03,
    "subsample": 1.0,
    "colsample_bytree": 1.0,
    "min_child_weight": 5,
    "gamma": 0.1,
    "reg_alpha": 0.1,
    "reg_lambda": 2.0,
}
SCALE_POS_WEIGHT_MULTIPLIER = 1.25


def get_operating_threshold() -> float:
    """Return the production low/at-risk boundary used for binary metrics."""
    return float(os.getenv("RISK_LOW_THRESHOLD", "0.39"))


def get_threshold_grid(operating_threshold: Optional[float] = None) -> List[float]:
    threshold = get_operating_threshold() if operating_threshold is None else operating_threshold
    return sorted({0.3, round(float(threshold), 2), 0.4, 0.5, 0.6, 0.7})

# Feature configuration (25 features: v3.2.0 schema).
# MULTIMODAL_FEATURE_NAMES must match FeatureService.FEATURE_SCHEMA exactly
# because it is the production inference schema.
MULTIMODAL_FEATURE_NAMES = [
    # === TREND (smoothed, de-noised) ===
    "recency_ratio",
    "frequency_trend_smoothed",
    "spend_trend_smoothed",
    "msg_trend_smoothed",
    "sentiment_trend",
    # === ABSOLUTE CONTEXT ===
    "recency_days",
    "tx_count_90d",
    "spend_90d",
    "avg_tx_value",
    "tenure_days",
    # === MAGNITUDE ===
    "activity_mean",
    "recent_activity_avg",
    # === VOLATILITY ===
    "activity_std",
    "activity_cv",
    "spend_volatility_cv",
    # === INTERACTION ===
    "trend_magnitude_interaction",
    # === NLP / COMMUNICATION ===
    "avg_sentiment_score",
    "complaint_ratio",
    "msg_volatility",
    "response_delay_mean",
    "has_communication_90d",
    # === v3.1: TRANSACTION CHANNEL MIX ===
    "homecare_tx_ratio_90d",
    "last_tx_is_homecare",
    # === v3.1: TRANSACTION QUALITY ===
    "zero_amount_tx_count_90d",
    # === v3.1: LIFETIME VALUE ===
    "lifetime_tx_count",
]

BASELINE_FEATURE_NAMES = [
    name for name in MULTIMODAL_FEATURE_NAMES
    if name not in {
        "avg_sentiment_score",
        "complaint_ratio",
        "msg_volatility",
        "response_delay_mean",
        "has_communication_90d",
        "sentiment_trend",
        "msg_trend_smoothed",
    }
]

FEATURE_NAMES = MULTIMODAL_FEATURE_NAMES

FEATURE_DESCRIPTIONS = {
    # Trend
    "recency_ratio": "Rasio recency terhadap baseline personal (recency_days / avg_ipt)",
    "frequency_trend_smoothed": "Slope tren frekuensi transaksi (smoothed, de-noised)",
    "spend_trend_smoothed": "Slope tren belanja (smoothed, de-noised)",
    "msg_trend_smoothed": "Slope tren komunikasi (smoothed, de-noised)",
    "sentiment_trend": "Perubahan sentimen (30d - prior_30d)",
    # Context
    "recency_days": "Hari sejak transaksi terakhir",
    "tx_count_90d": "Jumlah transaksi dalam 90 hari",
    "spend_90d": "Total belanja dalam 90 hari",
    "avg_tx_value": "Rata-rata nilai transaksi (spend_90d / tx_count_90d)",
    "tenure_days": "Lama menjadi customer (hari)",
    # Magnitude
    "activity_mean": "Rata-rata tx count per window (3 windows × 30d)",
    "recent_activity_avg": "Tx count di window terkini (30d terakhir)",
    # Volatility
    "activity_std": "Standar deviasi tx count antar window",
    "activity_cv": "Koefisien variasi aktivitas (std/mean, capped, zero-safe)",
    "spend_volatility_cv": "Koefisien variasi belanja antar window",
    # Interaction
    "trend_magnitude_interaction": "frequency_trend_smoothed × activity_mean",
    # NLP
    "avg_sentiment_score": "Rata-rata skor sentimen 30 hari",
    "complaint_ratio": "Rasio pesan komplain 30 hari (0-1)",
    "msg_volatility": "Volatilitas pola pesan harian (std dev)",
    "response_delay_mean": "Rata-rata waktu respons admin (detik)",
    "has_communication_90d": "Indikator pesan inbound trusted tersedia dalam 90 hari",
    # v3.1: Channel mix
    "homecare_tx_ratio_90d": "Rasio transaksi homecare dalam 90 hari (0-1)",
    "last_tx_is_homecare": "Flag: transaksi terakhir bertipe homecare (0 atau 1)",
    # v3.1: Transaction quality
    "zero_amount_tx_count_90d": "Jumlah transaksi selesai dengan nominal Rp 0 dalam 90 hari",
    # v3.1: Lifetime value
    "lifetime_tx_count": "Total transaksi selesai sepanjang masa sampai tanggal observasi",
}


def _compute_file_hash(filepath: str) -> str:
    """Compute short SHA256 hash for artifact identity."""
    if not filepath or not os.path.exists(filepath):
        return None
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def get_default_training_cutoff(churn_window_days: int = DEFAULT_CHURN_WINDOW_DAYS) -> date:
    """
    Choose the latest cutoff with a complete future outcome window.

    Training labels look forward from cutoff_date, so the cutoff must be at
    least churn_window_days before the latest event in the dataset.
    """
    latest_observed_date = FeatureService.get_default_as_of_date()
    return latest_observed_date - timedelta(days=churn_window_days)


def get_observation_dates(
    cutoff_date: date,
    observation_window_days: int = DEFAULT_OBSERVATION_WINDOW_DAYS,
) -> List[date]:
    """
    Build monthly observation dates with enough historical context.

    The cutoff_date is the latest allowed observation date. It is usually
    max(dataset_date) - prediction_window so labels have complete future data.
    """
    min_tx = db.session.query(func.min(Transaction.tx_date)).filter(
        Transaction.status == "completed"
    ).scalar()

    if not min_tx:
        return []

    earliest = min_tx.date() + timedelta(days=observation_window_days)
    if earliest > cutoff_date:
        return [cutoff_date]

    monthly = pd.date_range(start=earliest, end=cutoff_date, freq="MS")
    dates = [ts.date() for ts in monthly]

    # Keep the exact latest complete cutoff in the training set even when it is
    # not a month start. This preserves production recency while retaining the
    # notebook's multi-observation-date design.
    if cutoff_date not in dates:
        dates.append(cutoff_date)

    return sorted(set(dates))


def prepare_dataset(
    cutoff_date: date,
    churn_window_days: int = DEFAULT_CHURN_WINDOW_DAYS,
    observation_window_days: int = DEFAULT_OBSERVATION_WINDOW_DAYS,
) -> pd.DataFrame:
    """
    Prepare training dataset using multiple temporal observation dates.
    """
    observation_dates = get_observation_dates(cutoff_date, observation_window_days)
    logger.info(
        "Preparing dataset with %s observation dates through cutoff %s",
        len(observation_dates),
        cutoff_date,
    )

    feature_service = FeatureService()
    data = []

    for obs_date in observation_dates:
        feature_as_of_date = obs_date - timedelta(days=1)
        window_end = obs_date + timedelta(days=churn_window_days)
        customers = Customer.query.filter(
            Customer.is_active.is_(True),
            Customer.is_provisional.is_(False),
            Customer.consent_given.is_(True),
            Customer.created_at < datetime.combine(obs_date, datetime.min.time()),
            Customer.customer_id.in_(
                db.session.query(Transaction.customer_id).filter(
                    Transaction.status == "completed",
                    Transaction.tx_date < datetime.combine(obs_date, datetime.min.time()),
                )
            ),
        ).all()

        obs_rows = 0
        obs_positive = 0
        for index, customer in enumerate(customers):
            cid = str(customer.customer_id)
            try:
                feature_service.populate_all_features(
                    cid,
                    feature_as_of_date,
                    commit=False,
                )
                features = feature_service.get_ml_feature_dict(cid, feature_as_of_date)
            except Exception as exc:
                logger.warning("Skipping customer %s at %s: %s", cid, obs_date, exc)
                db.session.rollback()
                continue

            if not features or any(name not in features for name in FEATURE_NAMES):
                continue

            has_transaction = Transaction.query.filter(
                Transaction.customer_id == cid,
                Transaction.status == "completed",
                Transaction.tx_date >= datetime.combine(obs_date, datetime.min.time()),
                Transaction.tx_date < datetime.combine(window_end, datetime.min.time()),
            ).first() is not None

            churned = 0 if has_transaction else 1
            row = {
                "customer_id": cid,
                "observation_date": obs_date,
                "feature_as_of_date": feature_as_of_date,
                "churned": churned,
                "has_text_signal": int(
                    float(features.get("has_communication_90d") or 0.0) >= 0.5
                ),
            }
            row.update({name: float(features.get(name) or 0.0) for name in FEATURE_NAMES})
            data.append(row)
            obs_rows += 1
            obs_positive += churned

            if (index + 1) % 100 == 0:
                db.session.commit()

        db.session.commit()

        logger.info(
            "Observation %s: %s samples, %s risk-positive labels",
            obs_date,
            obs_rows,
            obs_positive,
        )
    
    df = pd.DataFrame(data)
    if not df.empty:
        logger.info(
            "Dataset: %s samples, %s risk-positive labels",
            len(df),
            int(df["churned"].sum()),
        )
    else:
        logger.warning("No training rows could be prepared")
    
    return df


def purged_temporal_split(
    df: pd.DataFrame,
    test_size: float = 0.2,
    prediction_horizon_days: int = DEFAULT_CHURN_WINDOW_DAYS,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, date]:
    """
    Split complete observation dates and purge rows with unavailable labels.

    Test contains the latest fraction of unique observation dates. A training
    row is retained only when its full future label window ends no later than
    the first test observation date.
    """
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1")
    if prediction_horizon_days < 1:
        raise ValueError("prediction_horizon_days must be at least 1")
    if "observation_date" not in df.columns:
        raise ValueError("Dataset missing observation_date")

    ordered = df.copy()
    ordered["observation_date"] = pd.to_datetime(
        ordered["observation_date"]
    ).dt.normalize()
    ordered = ordered.sort_values(
        ["observation_date", "customer_id"]
    ).reset_index(drop=True)

    unique_dates = pd.DatetimeIndex(
        ordered["observation_date"].drop_duplicates().sort_values()
    )
    if len(unique_dates) < 2:
        raise ValueError("Purged temporal split requires at least 2 observation dates")

    test_date_count = max(1, int(np.ceil(len(unique_dates) * test_size)))
    test_start_idx = len(unique_dates) - test_date_count
    if test_start_idx < 1:
        raise ValueError("Not enough observation dates for a non-empty training period")

    test_start = unique_dates[test_start_idx]
    label_window_end = ordered["observation_date"] + pd.to_timedelta(
        prediction_horizon_days,
        unit="D",
    )
    train_mask = label_window_end <= test_start
    test_mask = ordered["observation_date"] >= test_start
    purge_mask = ~(train_mask | test_mask)

    train_df = ordered.loc[train_mask].reset_index(drop=True)
    test_df = ordered.loc[test_mask].reset_index(drop=True)
    purged_df = ordered.loc[purge_mask].reset_index(drop=True)

    if train_df.empty or test_df.empty:
        raise ValueError(
            "Purged temporal split produced an empty train or test set; "
            "add observation dates or reduce the prediction horizon"
        )

    return train_df, test_df, purged_df, test_start.date()


def train_model(
    df: pd.DataFrame,
    test_size: float = 0.2,
    feature_names: Optional[List[str]] = None,
    model_label: str = "multimodal",
    prediction_horizon_days: int = DEFAULT_CHURN_WINDOW_DAYS,
    neutralized_features: Optional[List[str]] = None,
) -> Tuple[xgb.XGBClassifier, SimpleImputer, Dict[str, Any], np.ndarray]:
    """Train XGBoost model for a specific feature set."""
    if len(df) < 10:
        raise ValueError("Not enough training data")

    feature_names = feature_names or MULTIMODAL_FEATURE_NAMES
    missing_features = [name for name in feature_names if name not in df.columns]
    if missing_features:
        raise ValueError(f"Training dataset missing features for {model_label}: {missing_features}")

    train_df, test_df, purged_df, split_observation_date = purged_temporal_split(
        df,
        test_size=test_size,
        prediction_horizon_days=prediction_horizon_days,
    )

    X_train = train_df[feature_names].copy()
    X_test = test_df[feature_names].copy()
    neutralized_features = (
        NEUTRALIZED_MODEL_FEATURES
        if neutralized_features is None
        else neutralized_features
    )
    for feature in neutralized_features:
        if feature in X_train.columns:
            X_train[feature] = 0.0
            X_test[feature] = 0.0
    y_train = train_df["churned"].astype(int).copy()
    y_test = test_df["churned"].astype(int).copy()

    imputer = SimpleImputer(strategy="median")
    X_train = pd.DataFrame(imputer.fit_transform(X_train), columns=feature_names)
    X_test = pd.DataFrame(imputer.transform(X_test), columns=feature_names)

    original_train_size = len(X_train)
    original_positive = int(y_train.sum())
    original_negative = int(len(y_train) - original_positive)
    positive_ratio = original_positive / len(y_train) if len(y_train) else 0
    smote_applied = False

    if original_positive >= 10 and positive_ratio < 0.20:
        try:
            from imblearn.over_sampling import SMOTE

            k_neighbors = min(5, original_positive - 1)
            smote = SMOTE(random_state=42, k_neighbors=k_neighbors)
            X_train_resampled, y_train_resampled = smote.fit_resample(X_train, y_train)
            X_train = pd.DataFrame(X_train_resampled, columns=feature_names)
            y_train = pd.Series(y_train_resampled)
            smote_applied = True
            logger.info("Applied SMOTE: train samples %s -> %s", original_train_size, len(X_train))
        except ImportError:
            logger.warning("imbalanced-learn is not installed; continuing without SMOTE")

    pos_after = int(y_train.sum())
    neg_after = int(len(y_train) - pos_after)
    base_scale_pos_weight = neg_after / max(pos_after, 1)
    scale_pos_weight = base_scale_pos_weight * SCALE_POS_WEIGHT_MULTIPLIER

    logger.info(
        "Purged time-based split (%s): train=%s, purged=%s, test=%s, "
        "split_observation_date=%s, horizon_days=%s",
        model_label,
        len(X_train),
        len(purged_df),
        len(X_test),
        split_observation_date,
        prediction_horizon_days,
    )
    
    model = xgb.XGBClassifier(
        **XGB_PRODUCTION_PARAMS,
        objective='binary:logistic',
        eval_metric='logloss',
        scale_pos_weight=scale_pos_weight,
        random_state=42
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    # Evaluate at the production operating threshold.
    y_prob = model.predict_proba(X_test)[:, 1]
    operating_threshold = get_operating_threshold()
    y_pred = (y_prob >= operating_threshold).astype(int)
    threshold_sensitivity = []
    for threshold in get_threshold_grid(operating_threshold):
        y_threshold = (y_prob >= threshold).astype(int)
        threshold_sensitivity.append({
            "threshold": threshold,
            "precision": round(precision_score(y_test, y_threshold, zero_division=0), 4),
            "recall": round(recall_score(y_test, y_threshold, zero_division=0), 4),
            "f1_score": round(f1_score(y_test, y_threshold, zero_division=0), 4),
            "high_risk_customers": int(y_threshold.sum()),
        })
    
    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_prob), 4) if len(np.unique(y_test)) > 1 else 0,
        "pr_auc": round(average_precision_score(y_test, y_prob), 4) if len(np.unique(y_test)) > 1 else 0,
        "train_size": len(X_train),
        "test_size": len(X_test),
        "original_train_size": original_train_size,
        "original_positive_labels": original_positive,
        "original_negative_labels": original_negative,
        "test_positive_labels": int(y_test.sum()),
        "test_negative_labels": int(len(y_test) - y_test.sum()),
        "classification_threshold": operating_threshold,
        "split_strategy": "purged_time_based",
        "split_observation_date": split_observation_date.isoformat(),
        "prediction_horizon_days": prediction_horizon_days,
        "purged_size": len(purged_df),
        "purged_observation_dates": sorted(
            {d.date().isoformat() for d in purged_df["observation_date"]}
        ),
        "train_observation_dates": sorted(
            {d.date().isoformat() for d in train_df["observation_date"]}
        ),
        "test_observation_dates": sorted(
            {d.date().isoformat() for d in test_df["observation_date"]}
        ),
        "smote_applied": smote_applied,
        "scale_pos_weight": round(scale_pos_weight, 4),
        "base_scale_pos_weight": round(base_scale_pos_weight, 4),
        "scale_pos_weight_multiplier": SCALE_POS_WEIGHT_MULTIPLIER,
        "xgb_params": XGB_PRODUCTION_PARAMS,
        "observation_dates": sorted(
            {
                pd.Timestamp(d).date().isoformat()
                for d in df["observation_date"]
            }
        ),
        "threshold_sensitivity": threshold_sensitivity,
        "neutralized_model_features": neutralized_features,
        "text_coverage_train": round(
            float(train_df["has_text_signal"].mean())
            if "has_text_signal" in train_df
            else 0.0,
            4,
        ),
        "text_coverage_test": round(
            float(test_df["has_text_signal"].mean())
            if "has_text_signal" in test_df
            else 0.0,
            4,
        ),
        "model_type": model_label,
        "feature_count": len(feature_names),
        "feature_names": feature_names,
    }
    
    logger.info("%s metrics: %s", model_label, metrics)
    return model, imputer, metrics, X_train.values


def _new_xgb_classifier(y: pd.Series) -> xgb.XGBClassifier:
    """Build the transaction base learner with fold-local class weighting."""
    positives = int(pd.Series(y).sum())
    negatives = int(len(y) - positives)
    if positives == 0 or negatives == 0:
        raise ValueError("XGBoost training requires both risk classes")
    return xgb.XGBClassifier(
        **XGB_PRODUCTION_PARAMS,
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=(negatives / positives) * SCALE_POS_WEIGHT_MULTIPLIER,
        random_state=42,
    )


def _neutralize_frame(
    frame: pd.DataFrame,
    neutralized_features: List[str],
) -> pd.DataFrame:
    result = frame.copy()
    for feature in neutralized_features:
        if feature in result.columns:
            result[feature] = 0.0
    return result


def build_group_oof_base_scores(
    df: pd.DataFrame,
    feature_names: List[str],
    neutralized_features: List[str],
    n_splits: int = 5,
) -> np.ndarray:
    """Generate customer-held-out base scores for leakage-safe stacking."""
    groups = df["customer_id"].astype(str)
    unique_groups = groups.nunique()
    if unique_groups < 2:
        raise ValueError("Grouped OOF scoring requires at least 2 customers")

    splitter = GroupKFold(n_splits=min(n_splits, unique_groups))
    scores = np.full(len(df), np.nan, dtype=float)
    X = df[feature_names].copy()
    y = df["churned"].astype(int)

    for train_idx, valid_idx in splitter.split(X, y, groups):
        X_train = _neutralize_frame(
            X.iloc[train_idx],
            neutralized_features,
        )
        X_valid = _neutralize_frame(
            X.iloc[valid_idx],
            neutralized_features,
        )
        imputer = SimpleImputer(strategy="median")
        X_train_arr = imputer.fit_transform(X_train)
        X_valid_arr = imputer.transform(X_valid)
        fold_model = _new_xgb_classifier(y.iloc[train_idx])
        fold_model.fit(X_train_arr, y.iloc[train_idx], verbose=False)
        scores[valid_idx] = fold_model.predict_proba(X_valid_arr)[:, 1]

    if np.isnan(scores).any():
        raise RuntimeError("Grouped OOF scoring did not cover every training row")
    return scores


def _meta_matrix(
    frame: pd.DataFrame,
    base_scores: np.ndarray,
) -> np.ndarray:
    return np.column_stack(
        [
            np.asarray(base_scores, dtype=float),
            frame["complaint_ratio"].astype(float).to_numpy(),
            frame["msg_trend_smoothed"].astype(float).to_numpy(),
            np.log1p(
                np.maximum(
                    frame["response_delay_mean"].astype(float).to_numpy(),
                    0.0,
                )
            ),
        ]
    )


def _binary_metrics(
    y_true: pd.Series,
    probabilities: np.ndarray,
    threshold: Optional[float] = None,
) -> Dict[str, Any]:
    y_array = np.asarray(y_true, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    classification_threshold = get_operating_threshold() if threshold is None else threshold
    predicted = (probabilities >= classification_threshold).astype(int)
    both_classes = len(np.unique(y_array)) > 1
    return {
        "accuracy": round(accuracy_score(y_array, predicted), 4),
        "precision": round(precision_score(y_array, predicted, zero_division=0), 4),
        "recall": round(recall_score(y_array, predicted, zero_division=0), 4),
        "f1": round(f1_score(y_array, predicted, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_array, probabilities), 4)
        if both_classes else 0.0,
        "pr_auc": round(average_precision_score(y_array, probabilities), 4)
        if both_classes else 0.0,
        "classification_threshold": classification_threshold,
    }


def _new_logistic_adjuster() -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "logistic",
                LogisticRegression(
                    C=0.25,
                    class_weight="balanced",
                    max_iter=2000,
                    solver="liblinear",
                    random_state=42,
                ),
            ),
        ]
    )


def train_gated_adjuster(
    df: pd.DataFrame,
    base_oof_scores: np.ndarray,
    n_splits: int = 5,
) -> Tuple[Pipeline, Dict[str, Any], bool]:
    """Train and group-validate the regularized communication adjustment."""
    eligible_mask = df["has_text_signal"].astype(int) == 1
    eligible = df.loc[eligible_mask].reset_index(drop=True)
    eligible_base_scores = np.asarray(base_oof_scores)[eligible_mask.to_numpy()]

    unique_customers = eligible["customer_id"].astype(str).nunique()
    positives = int(eligible["churned"].sum())
    negatives = int(len(eligible) - positives)
    if unique_customers < 10 or min(positives, negatives) < 5:
        raise ValueError(
            "Insufficient labeled multimodal cohort: "
            f"customers={unique_customers}, positives={positives}, negatives={negatives}"
        )

    X_meta = _meta_matrix(eligible, eligible_base_scores)
    y_meta = eligible["churned"].astype(int)
    groups = eligible["customer_id"].astype(str)
    folds = min(n_splits, unique_customers, positives, negatives)
    splitter = StratifiedGroupKFold(
        n_splits=max(2, folds),
        shuffle=True,
        random_state=42,
    )
    adjusted_oof = np.full(len(eligible), np.nan, dtype=float)

    for train_idx, valid_idx in splitter.split(X_meta, y_meta, groups):
        fold_adjuster = _new_logistic_adjuster()
        fold_adjuster.fit(X_meta[train_idx], y_meta.iloc[train_idx])
        adjusted_oof[valid_idx] = fold_adjuster.predict_proba(
            X_meta[valid_idx]
        )[:, 1]

    if np.isnan(adjusted_oof).any():
        raise RuntimeError("Grouped logistic validation did not cover every row")

    base_metrics = _binary_metrics(y_meta, eligible_base_scores)
    adjusted_metrics = _binary_metrics(y_meta, adjusted_oof)
    improvement = compute_incremental_improvement(
        base_metrics,
        adjusted_metrics,
    )

    # A small tolerance avoids disabling the gated path because of sampling
    # noise, while still preventing a clearly inferior adjustment from being
    # promoted.
    adjustment_enabled = (
        adjusted_metrics["roc_auc"] >= base_metrics["roc_auc"] - 0.02
        and adjusted_metrics["pr_auc"] >= base_metrics["pr_auc"] - 0.02
    )

    adjuster = _new_logistic_adjuster()
    adjuster.fit(X_meta, y_meta)
    metrics = {
        "validation_strategy": "stratified_group_kfold_by_customer",
        "folds": max(2, folds),
        "rows": len(eligible),
        "unique_customers": unique_customers,
        "positive_labels": positives,
        "negative_labels": negatives,
        "meta_feature_names": list(GatedRiskModel.META_FEATURE_NAMES),
        "base_on_multimodal_cohort": base_metrics,
        "gated_logistic": adjusted_metrics,
        "improvement": improvement,
        "adjustment_enabled": adjustment_enabled,
    }
    logger.info("Gated logistic metrics: %s", metrics)
    return adjuster, metrics, adjustment_enabled


def fit_production_base_model(
    df: pd.DataFrame,
    feature_names: List[str],
    neutralized_features: List[str],
) -> Tuple[xgb.XGBClassifier, SimpleImputer]:
    """Refit the transaction base on every complete labeled observation."""
    X = _neutralize_frame(df[feature_names], neutralized_features)
    y = df["churned"].astype(int)
    imputer = SimpleImputer(strategy="median")
    X_arr = imputer.fit_transform(X)
    model = _new_xgb_classifier(y)
    model.fit(X_arr, y, verbose=False)
    return model, imputer


def _coerce_numeric_array(values) -> np.ndarray:
    """Convert feature matrix to a pure float array for XGBoost/SHAP."""
    return coerce_numeric_array(values)


def create_shap_explainer(
    model: xgb.XGBClassifier,
    X_sample: np.ndarray,
    neutralized_features: Optional[List[str]] = None,
):
    """Create a SHAP explainer bound to the trained model.

    TreeExplainer is preferred. Some SHAP/XGBoost combinations fail while
    parsing the booster dump (for example split values like "[5E-1]"), so we
    fall back to a model-agnostic SHAP explainer instead of dropping
    explanations entirely.
    """
    try:
        import shap
        logger.info("Creating SHAP explainer...")
        X_sample = _coerce_numeric_array(X_sample)

        try:
            explainer = shap.TreeExplainer(model)
            _ = explainer.shap_values(X_sample[:5])
            logger.info("Created SHAP TreeExplainer")
            return explainer
        except Exception as tree_exc:
            logger.warning(f"TreeExplainer failed, using model-agnostic SHAP: {tree_exc}")

        background_size = min(50, len(X_sample))
        test_size = min(2, len(X_sample))
        if background_size == 0 or test_size == 0:
            raise ValueError("No samples available to initialize SHAP explainer")

        background = X_sample[:background_size]
        masker = shap.maskers.Independent(background, max_samples=background_size)
        explainer = shap.Explainer(
            RiskProbabilityModel(
                model,
                [
                    FEATURE_NAMES.index(name)
                    for name in (
                        NEUTRALIZED_MODEL_FEATURES
                        if neutralized_features is None
                        else neutralized_features
                    )
                    if name in FEATURE_NAMES
                ],
            ),
            masker,
            algorithm="permutation",
        )
        _ = explainer(
            X_sample[:test_size],
            max_evals=(2 * X_sample.shape[1]) + 1,
            silent=True,
        )
        logger.info("Created model-agnostic SHAP explainer")
        return explainer
    except Exception as e:
        logger.error(f"SHAP failed: {e}")
        return None


def save_artifacts(
    model,
    imputer,
    metrics,
    shap_explainer,
    version,
    output_dir="models",
    neutralized_features: Optional[List[str]] = None,
):
    """Save production multimodal model artifacts."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    
    # Production model: multimodal only.
    model_path = os.path.join(output_dir, "multimodal_model.pkl")
    joblib.dump(model, model_path)
    paths["model"] = model_path

    # Imputer/scaler artifact. Filename kept as scaler.pkl for compatibility
    # with the existing app convention and notebook artifact contract.
    scaler_path = os.path.join(output_dir, "scaler.pkl")
    joblib.dump(imputer, scaler_path)
    paths["scaler"] = scaler_path
    
    # Feature metadata
    feature_meta = {
        "feature_names": MULTIMODAL_FEATURE_NAMES,
        "feature_descriptions": FEATURE_DESCRIPTIONS,
        "expected_shape": len(MULTIMODAL_FEATURE_NAMES),
        "model_type": "gated_transaction_xgb_logistic",
        "neutralized_model_features": (
            NEUTRALIZED_MODEL_FEATURES
            if neutralized_features is None
            else neutralized_features
        ),
        "version": version,
        "trained_at": datetime.utcnow().isoformat()
    }
    
    meta_path = os.path.join(output_dir, "features.json")
    with open(meta_path, 'w') as f:
        json.dump(feature_meta, f, indent=2)
    paths["features"] = meta_path
    
    # SHAP
    shap_path = os.path.join(output_dir, "shap_explainer.pkl")
    shap_available = shap_explainer is not None
    if shap_explainer:
        joblib.dump(shap_explainer, shap_path)
        paths["shap"] = shap_path
    elif os.path.exists(shap_path):
        os.remove(shap_path)

    metrics["shap_available"] = shap_available

    model_hash = _compute_file_hash(model_path)
    scaler_hash = _compute_file_hash(scaler_path)
    shap_hash = _compute_file_hash(shap_path) if os.path.exists(shap_path) else None
    model_metadata = {
        "model_hash": model_hash,
        "model_version": version,
        "feature_schema_version": FeatureService.FEATURE_SCHEMA_VERSION,
        "feature_schema_hash": FeatureService.get_feature_schema_hash(),
        "expected_feature_count": len(MULTIMODAL_FEATURE_NAMES),
        "metrics": metrics,
        "shap_available": shap_available,
        "explanation_status": "available" if shap_available else "unavailable",
        "artifact_paths": {
            "model": model_path,
            "features": meta_path,
            "scaler": scaler_path,
            "shap": shap_path if os.path.exists(shap_path) else None,
        },
        "artifact_hashes": {
            "model": model_hash,
            "features": _compute_file_hash(meta_path),
            "scaler": scaler_hash,
            "shap": shap_hash,
        },
        "trained_at": datetime.utcnow().isoformat(),
    }

    metadata_path = os.path.join(output_dir, "model_metadata.pkl")
    joblib.dump(model_metadata, metadata_path)
    paths["metadata"] = metadata_path
    
    return paths


def save_baseline_artifacts(
    model,
    imputer,
    metrics,
    version,
    output_dir="models",
    neutralized_features: Optional[List[str]] = None,
):
    """Save research-only baseline artifacts."""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}

    model_path = os.path.join(output_dir, "baseline_model.pkl")
    joblib.dump(model, model_path)
    paths["model"] = model_path

    scaler_path = os.path.join(output_dir, "baseline_scaler.pkl")
    joblib.dump(imputer, scaler_path)
    paths["scaler"] = scaler_path

    feature_meta = {
        "feature_names": BASELINE_FEATURE_NAMES,
        "feature_descriptions": {
            name: FEATURE_DESCRIPTIONS.get(name, name)
            for name in BASELINE_FEATURE_NAMES
        },
        "expected_shape": len(BASELINE_FEATURE_NAMES),
        "model_type": "transaction_only_baseline",
        "neutralized_model_features": [
            name for name in (
                NEUTRALIZED_MODEL_FEATURES
                if neutralized_features is None
                else neutralized_features
            )
            if name in BASELINE_FEATURE_NAMES
        ],
        "version": version,
        "trained_at": datetime.utcnow().isoformat(),
        "research_only": True,
    }

    meta_path = os.path.join(output_dir, "baseline_features.json")
    with open(meta_path, "w") as f:
        json.dump(feature_meta, f, indent=2)
    paths["features"] = meta_path

    baseline_metadata = {
        "model_hash": _compute_file_hash(model_path),
        "model_version": version,
        "feature_schema_version": FeatureService.FEATURE_SCHEMA_VERSION,
        "feature_schema_hash": hashlib.sha256(
            json.dumps(feature_meta, sort_keys=True).encode()
        ).hexdigest()[:16],
        "expected_feature_count": len(BASELINE_FEATURE_NAMES),
        "metrics": metrics,
        "artifact_paths": {
            "model": model_path,
            "features": meta_path,
            "scaler": scaler_path,
        },
        "artifact_hashes": {
            "model": _compute_file_hash(model_path),
            "features": _compute_file_hash(meta_path),
            "scaler": _compute_file_hash(scaler_path),
        },
        "trained_at": datetime.utcnow().isoformat(),
        "research_only": True,
    }
    metadata_path = os.path.join(output_dir, "baseline_model_metadata.pkl")
    joblib.dump(baseline_metadata, metadata_path)
    paths["metadata"] = metadata_path

    return paths


def compute_incremental_improvement(
    baseline_metrics: Dict[str, Any],
    multimodal_metrics: Dict[str, Any],
) -> Dict[str, float]:
    """Compute multimodal minus baseline gains for thesis validation."""
    keys = ["roc_auc", "pr_auc", "precision", "recall", "f1"]
    return {
        key: round(float(multimodal_metrics.get(key, 0) or 0) - float(baseline_metrics.get(key, 0) or 0), 4)
        for key in keys
    }


def select_neutralized_features(
    df: pd.DataFrame,
    prediction_horizon_days: int,
) -> Tuple[List[str], float]:
    """Neutralize communication inputs when temporal training coverage is weak."""
    train_df, _, _, _ = purged_temporal_split(
        df,
        prediction_horizon_days=prediction_horizon_days,
    )
    coverage = (
        float(train_df["has_text_signal"].mean())
        if "has_text_signal" in train_df
        else 0.0
    )
    neutralized = list(BASE_NEUTRALIZED_MODEL_FEATURES)
    if coverage < MIN_TEXT_TRAINING_COVERAGE:
        neutralized.extend(COMMUNICATION_FEATURES)
    return list(dict.fromkeys(neutralized)), coverage


def validate_candidate_improvement(improvement: Dict[str, float]) -> None:
    """Reject a production candidate that materially underperforms baseline."""
    tolerance = 0.002
    if (
        float(improvement.get("roc_auc", 0.0)) < -tolerance
        or float(improvement.get("pr_auc", 0.0)) < -tolerance
    ):
        raise RuntimeError(
            "Multimodal candidate rejected: validation ROC-AUC or PR-AUC "
            "is worse than the transaction baseline."
        )


def promote_staged_artifacts(staging_dir: str, output_dir: str) -> None:
    """Promote one complete artifact set with rollback on filesystem failure."""
    artifact_names = [
        "multimodal_model.pkl",
        "scaler.pkl",
        "features.json",
        "shap_explainer.pkl",
        "model_metadata.pkl",
        "baseline_model.pkl",
        "baseline_scaler.pkl",
        "baseline_features.json",
        "baseline_model_metadata.pkl",
    ]
    os.makedirs(output_dir, exist_ok=True)
    backup_dir = os.path.join(output_dir, ".artifact-backup")
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    os.makedirs(backup_dir)

    # Metadata should reference stable production paths, not staging paths.
    for metadata_name in ("model_metadata.pkl", "baseline_model_metadata.pkl"):
        metadata_path = os.path.join(staging_dir, metadata_name)
        if not os.path.exists(metadata_path):
            continue
        metadata = joblib.load(metadata_path)
        metadata["artifact_paths"] = {
            key: (
                os.path.join(output_dir, os.path.basename(value))
                if value
                else None
            )
            for key, value in (metadata.get("artifact_paths") or {}).items()
        }
        joblib.dump(metadata, metadata_path)

    moved_new = []
    backed_up = []
    try:
        for name in artifact_names:
            target = os.path.join(output_dir, name)
            if os.path.exists(target):
                os.replace(target, os.path.join(backup_dir, name))
                backed_up.append(name)

        for name in artifact_names:
            candidate = os.path.join(staging_dir, name)
            if os.path.exists(candidate):
                os.replace(candidate, os.path.join(output_dir, name))
                moved_new.append(name)
    except Exception:
        for name in moved_new:
            target = os.path.join(output_dir, name)
            if os.path.exists(target):
                os.remove(target)
        for name in backed_up:
            backup = os.path.join(backup_dir, name)
            if os.path.exists(backup):
                os.replace(backup, os.path.join(output_dir, name))
        raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    shutil.rmtree(backup_dir, ignore_errors=True)


def build_research_metrics(
    baseline_metrics: Dict[str, Any],
    multimodal_metrics: Dict[str, Any],
    improvement: Dict[str, float],
    baseline_paths: Dict[str, str],
    multimodal_paths: Dict[str, str],
    version: str,
) -> Dict[str, Any]:
    """Store comparison data while preserving legacy top-level metrics."""
    trained_at = datetime.utcnow().isoformat()
    baseline_metadata = {
        "feature_count": len(BASELINE_FEATURE_NAMES),
        "training_samples": baseline_metrics.get("train_size"),
        "training_date": trained_at,
        "model_version": version,
        "model_path": baseline_paths.get("model"),
        "model_hash": _compute_file_hash(baseline_paths.get("model")),
        "research_only": True,
    }
    multimodal_metadata = {
        "feature_count": len(MULTIMODAL_FEATURE_NAMES),
        "training_samples": (
            multimodal_metrics.get("production_refit_size")
            or multimodal_metrics.get("train_size")
        ),
        "training_date": trained_at,
        "model_version": version,
        "model_path": multimodal_paths.get("model"),
        "model_hash": _compute_file_hash(multimodal_paths.get("model")),
        "production_model": True,
    }

    return {
        **multimodal_metrics,
        "baseline": baseline_metrics,
        "multimodal": multimodal_metrics,
        "improvement": improvement,
        "model_metadata": {
            "baseline": baseline_metadata,
            "multimodal": multimodal_metadata,
        },
        "comparison_interpretation": build_comparison_interpretation(improvement),
    }


def build_comparison_interpretation(improvement: Dict[str, float]) -> str:
    roc_gain = improvement.get("roc_auc", 0) or 0
    f1_gain = improvement.get("f1", 0) or 0
    direction = "improves" if roc_gain >= 0 and f1_gain >= 0 else "changes"
    value_note = (
        "customer interaction signals contribute additional predictive value beyond transactional behavior."
        if roc_gain > 0 or f1_gain > 0
        else "customer interaction signals did not improve these validation metrics in the current split."
    )
    return (
        f"Multimodal model {direction} ROC-AUC by {roc_gain:.3f} and "
        f"F1-Score by {f1_gain:.3f} compared to the transaction-only baseline. "
        f"This indicates that {value_note}"
    )


def register_model_version(version, model_path, metrics):
    """Register in model_versions table"""
    existing = ModelVersion.query.filter_by(model_version=version).first()
    if existing:
        existing.model_path = model_path
        existing.metrics = metrics
        existing.trained_at = datetime.utcnow()
        db.session.commit()
        return existing
    
    mv = ModelVersion(
        model_version=version,
        model_path=model_path,
        trained_at=datetime.utcnow(),
        metrics=metrics,
        deployed=False
    )
    db.session.add(mv)
    db.session.commit()
    return mv


def register_active_multimodal_model(version, model_path, paths, metrics):
    """Register only the multimodal artifact as active production model."""
    try:
        from app.models.ml_registry import MLModelRegistry

        model_hash = _compute_file_hash(model_path)
        feature_hash = FeatureService.get_feature_schema_hash()
        shap_hash = _compute_file_hash(paths.get("shap")) if paths.get("shap") else None
        MLModelRegistry.query.filter_by(is_active=True).update({"is_active": False})

        existing = MLModelRegistry.query.filter_by(model_hash=model_hash).first()
        if existing:
            registry = existing
            registry.is_active = True
            registry.model_version = version
            registry.model_name = "gated_transaction_xgb_logistic"
            registry.feature_schema_hash = feature_hash
            registry.feature_names = MULTIMODAL_FEATURE_NAMES
            registry.expected_feature_count = len(MULTIMODAL_FEATURE_NAMES)
            registry.training_data_count = (
                metrics.get("production_refit_size")
                or metrics.get("train_size")
            )
            registry.training_date = datetime.utcnow()
            registry.shap_explainer_hash = shap_hash
            registry.notes = (
                "Production gated model: transaction XGBoost with regularized "
                "logistic communication adjustment."
            )
        else:
            registry = MLModelRegistry(
                model_name="gated_transaction_xgb_logistic",
                model_version=version,
                model_hash=model_hash,
                feature_schema_hash=feature_hash,
                feature_names=MULTIMODAL_FEATURE_NAMES,
                expected_feature_count=len(MULTIMODAL_FEATURE_NAMES),
                training_data_count=(
                    metrics.get("production_refit_size")
                    or metrics.get("train_size")
                ),
                training_date=datetime.utcnow(),
                shap_explainer_hash=shap_hash,
                is_active=True,
                notes=(
                    "Production gated model: transaction XGBoost with regularized "
                    "logistic communication adjustment."
                ),
            )
            db.session.add(registry)

        db.session.commit()
        return registry
    except Exception as exc:
        db.session.rollback()
        raise RuntimeError(f"Could not update ML model registry: {exc}") from exc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff-date", type=str, default=None)
    parser.add_argument("--churn-window", type=int, default=DEFAULT_CHURN_WINDOW_DAYS)
    parser.add_argument("--observation-window", type=int, default=DEFAULT_OBSERVATION_WINDOW_DAYS)
    parser.add_argument("--version", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default="models")
    
    args = parser.parse_args()
    version = args.version or datetime.now().strftime("v%Y%m%d_%H%M%S")
    
    app = create_app()
    
    with app.app_context():
        cutoff_date = (
            date.fromisoformat(args.cutoff_date)
            if args.cutoff_date
            else get_default_training_cutoff(args.churn_window)
        )
        logger.info(
            "Training with cutoff: %s, observation_window: %s days, churn_window: %s days, version: %s",
            cutoff_date,
            args.observation_window,
            args.churn_window,
            version,
        )
        df = prepare_dataset(cutoff_date, args.churn_window, args.observation_window)
        
        if len(df) < 10:
            logger.error("Insufficient data")
            sys.exit(1)

        text_training_coverage = float(df["has_text_signal"].mean())
        base_neutralized_features = list(dict.fromkeys(
            BASE_NEUTRALIZED_MODEL_FEATURES + COMMUNICATION_FEATURES
        ))
        logger.info(
            "Temporal multimodal coverage: %.2f%%; XGBoost-neutralized features: %s",
            text_training_coverage * 100,
            base_neutralized_features,
        )
        
        baseline_model, baseline_imputer, baseline_metrics, _ = train_model(
            df,
            feature_names=BASELINE_FEATURE_NAMES,
            model_label="baseline",
            prediction_horizon_days=args.churn_window,
            neutralized_features=BASE_NEUTRALIZED_MODEL_FEATURES,
        )
        _, _, transaction_metrics, _ = train_model(
            df,
            feature_names=MULTIMODAL_FEATURE_NAMES,
            model_label="transaction_base",
            prediction_horizon_days=args.churn_window,
            neutralized_features=base_neutralized_features,
        )

        base_oof_scores = build_group_oof_base_scores(
            df,
            MULTIMODAL_FEATURE_NAMES,
            base_neutralized_features,
        )
        adjuster, adjuster_metrics, adjustment_enabled = train_gated_adjuster(
            df,
            base_oof_scores,
        )
        production_base, production_imputer = fit_production_base_model(
            df,
            MULTIMODAL_FEATURE_NAMES,
            base_neutralized_features,
        )
        multimodal_model = GatedRiskModel(
            base_model=production_base,
            adjuster=adjuster,
            feature_names=MULTIMODAL_FEATURE_NAMES,
            base_neutralized_features=base_neutralized_features,
            adjustment_enabled=adjustment_enabled,
        )
        multimodal_metrics = {
            **transaction_metrics,
            "model_type": "gated_transaction_xgb_logistic",
            "gated_adjuster": adjuster_metrics,
            "production_refit_size": len(df),
            "adjustment_enabled": adjustment_enabled,
        }
        improvement = adjuster_metrics["improvement"]

        shap_source = df[MULTIMODAL_FEATURE_NAMES].sample(
            n=min(500, len(df)),
            random_state=42,
        )
        shap_sample = production_imputer.transform(shap_source)

        shap_enabled = os.getenv("ENABLE_SHAP", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        shap_explainer = (
            create_shap_explainer(
                multimodal_model,
                shap_sample,
                neutralized_features=[],
            )
            if shap_enabled
            else None
        )
        if shap_enabled and shap_explainer is None:
            raise RuntimeError(
                "SHAP explainer generation failed. Existing production artifacts "
                "were preserved; inspect the training log before retrying."
            )

        staging_dir = os.path.join(args.output_dir, f".training-{version}")
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)
        os.makedirs(staging_dir, exist_ok=True)
        baseline_paths = save_baseline_artifacts(
            baseline_model,
            baseline_imputer,
            baseline_metrics,
            version,
            staging_dir,
            neutralized_features=BASE_NEUTRALIZED_MODEL_FEATURES,
        )
        multimodal_paths = save_artifacts(
            multimodal_model,
            production_imputer,
            multimodal_metrics,
            shap_explainer,
            version,
            staging_dir,
            neutralized_features=[],
        )
        promote_staged_artifacts(staging_dir, args.output_dir)
        baseline_paths = {
            key: os.path.join(args.output_dir, os.path.basename(path))
            for key, path in baseline_paths.items()
        }
        multimodal_paths = {
            key: os.path.join(args.output_dir, os.path.basename(path))
            for key, path in multimodal_paths.items()
        }
        metrics = build_research_metrics(
            baseline_metrics,
            multimodal_metrics,
            improvement,
            baseline_paths,
            multimodal_paths,
            version,
        )
        metrics["text_training_coverage"] = round(text_training_coverage, 4)
        metrics["base_neutralized_model_features"] = base_neutralized_features
        metrics["gated_adjuster"] = adjuster_metrics
        register_model_version(version, multimodal_paths["model"], metrics)
        register_active_multimodal_model(version, multimodal_paths["model"], multimodal_paths, multimodal_metrics)
        
        logger.info(f"Training complete! Version: {version}")


if __name__ == "__main__":
    main()
