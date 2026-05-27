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
import sys
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    precision_score, recall_score, f1_score, 
    accuracy_score, roc_auc_score, average_precision_score
)
from sqlalchemy import func
import xgboost as xgb

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.models.topic import ModelVersion
from app.services.feature_service import FeatureService
from app.services.shap_wrapper import RiskProbabilityModel, coerce_numeric_array

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_CHURN_WINDOW_DAYS = 90
DEFAULT_OBSERVATION_WINDOW_DAYS = 90
NEUTRALIZED_MODEL_FEATURES = ["tenure_days"]

# Feature configuration (20 features: v3.0.0 schema)
# Must match FeatureService.FEATURE_SCHEMA exactly
FEATURE_NAMES = [
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
]

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
        for customer in customers:
            cid = str(customer.customer_id)
            try:
                feature_service.populate_all_features(cid, feature_as_of_date)
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
            }
            row.update({name: float(features.get(name) or 0.0) for name in FEATURE_NAMES})
            data.append(row)
            obs_rows += 1
            obs_positive += churned

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


def train_model(df: pd.DataFrame, test_size: float = 0.2) -> Tuple[xgb.XGBClassifier, SimpleImputer, Dict[str, Any], np.ndarray]:
    """Train XGBoost model"""
    if len(df) < 10:
        raise ValueError("Not enough training data")

    df = df.sort_values(["observation_date", "customer_id"]).reset_index(drop=True)
    X = df[FEATURE_NAMES].copy()
    for feature in NEUTRALIZED_MODEL_FEATURES:
        if feature in X.columns:
            X[feature] = 0.0
    y = df["churned"].astype(int).copy()
    observation_dates = pd.to_datetime(df["observation_date"]).reset_index(drop=True)

    cutoff_idx = int(len(df) * (1 - test_size))
    cutoff_idx = min(max(cutoff_idx, 1), len(df) - 1)
    split_observation_date = observation_dates.iloc[cutoff_idx].date()

    X_train = X.iloc[:cutoff_idx].copy()
    X_test = X.iloc[cutoff_idx:].copy()
    y_train = y.iloc[:cutoff_idx].copy()
    y_test = y.iloc[cutoff_idx:].copy()

    imputer = SimpleImputer(strategy="median")
    X_train = pd.DataFrame(imputer.fit_transform(X_train), columns=FEATURE_NAMES)
    X_test = pd.DataFrame(imputer.transform(X_test), columns=FEATURE_NAMES)

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
            X_train = pd.DataFrame(X_train_resampled, columns=FEATURE_NAMES)
            y_train = pd.Series(y_train_resampled)
            smote_applied = True
            logger.info("Applied SMOTE: train samples %s -> %s", original_train_size, len(X_train))
        except ImportError:
            logger.warning("imbalanced-learn is not installed; continuing without SMOTE")

    pos_after = int(y_train.sum())
    neg_after = int(len(y_train) - pos_after)
    scale_pos_weight = neg_after / max(pos_after, 1)

    logger.info(
        "Time-based split: train=%s, test=%s, split_observation_date=%s",
        len(X_train),
        len(X_test),
        split_observation_date,
    )
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        objective='binary:logistic',
        eval_metric='logloss',
        scale_pos_weight=scale_pos_weight,
        use_label_encoder=False,
        random_state=42
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    # Evaluate
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    threshold_sensitivity = []
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
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
        "split_strategy": "time_based",
        "split_observation_date": split_observation_date.isoformat(),
        "smote_applied": smote_applied,
        "scale_pos_weight": round(scale_pos_weight, 4),
        "observation_dates": sorted({d.isoformat() for d in df["observation_date"]}),
        "threshold_sensitivity": threshold_sensitivity,
        "neutralized_model_features": NEUTRALIZED_MODEL_FEATURES,
    }
    
    logger.info(f"Metrics: {metrics}")
    return model, imputer, metrics, X_train.values


def _coerce_numeric_array(values) -> np.ndarray:
    """Convert feature matrix to a pure float array for XGBoost/SHAP."""
    return coerce_numeric_array(values)


def create_shap_explainer(model: xgb.XGBClassifier, X_sample: np.ndarray):
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
                [FEATURE_NAMES.index(name) for name in NEUTRALIZED_MODEL_FEATURES if name in FEATURE_NAMES],
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


def save_artifacts(model, imputer, metrics, shap_explainer, version, output_dir="models"):
    """Save model artifacts"""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    
    # Model
    model_path = os.path.join(output_dir, "churn_model.pkl")
    joblib.dump(model, model_path)
    paths["model"] = model_path

    # Imputer/scaler artifact. Filename kept as scaler.pkl for compatibility
    # with the existing app convention and notebook artifact contract.
    scaler_path = os.path.join(output_dir, "scaler.pkl")
    joblib.dump(imputer, scaler_path)
    paths["scaler"] = scaler_path
    
    # Feature metadata
    feature_meta = {
        "feature_names": FEATURE_NAMES,
        "feature_descriptions": FEATURE_DESCRIPTIONS,
        "expected_shape": len(FEATURE_NAMES),
        "model_type": "ontology_refactored",
        "neutralized_model_features": NEUTRALIZED_MODEL_FEATURES,
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
        "expected_feature_count": len(FEATURE_NAMES),
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
        
        model, imputer, metrics, shap_sample = train_model(df)
        shap_explainer = create_shap_explainer(model, shap_sample)
        paths = save_artifacts(model, imputer, metrics, shap_explainer, version, args.output_dir)
        register_model_version(version, paths["model"], metrics)
        
        logger.info(f"Training complete! Version: {version}")


if __name__ == "__main__":
    main()
