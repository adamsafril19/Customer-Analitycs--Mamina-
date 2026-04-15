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
import json
import logging
import os
import sys
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    precision_score, recall_score, f1_score, 
    accuracy_score, roc_auc_score
)
import xgboost as xgb

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.customer import Customer
from app.models.numeric_features import CustomerNumericFeatures
from app.models.text_signals import CustomerTextSignals
from app.models.transaction import Transaction
from app.models.topic import ModelVersion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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


def prepare_dataset(cutoff_date: date, churn_window_days: int = 180) -> pd.DataFrame:
    """
    Prepare training dataset using correct ontology
    
    Joins: numeric_features + text_signals (NOT semantics)
    """
    logger.info(f"Preparing dataset with cutoff date: {cutoff_date}")
    
    # Get numeric features
    numeric_features = CustomerNumericFeatures.query.filter(
        CustomerNumericFeatures.as_of_date <= cutoff_date
    ).all()
    
    if not numeric_features:
        logger.warning("No numeric features found")
        return pd.DataFrame()
    
    # Group by customer, take latest
    customer_numeric = {}
    for f in numeric_features:
        cid = str(f.customer_id)
        if cid not in customer_numeric or f.as_of_date > customer_numeric[cid].as_of_date:
            customer_numeric[cid] = f
    
    # Get text signals
    text_signals = CustomerTextSignals.query.filter(
        CustomerTextSignals.as_of_date <= cutoff_date
    ).all()
    
    customer_signals = {}
    for s in text_signals:
        cid = str(s.customer_id)
        if cid not in customer_signals or s.as_of_date > customer_signals[cid].as_of_date:
            customer_signals[cid] = s
    
    # Build dataset
    window_end = cutoff_date + timedelta(days=churn_window_days)
    data = []
    
    for cid, numeric in customer_numeric.items():
        signals = customer_signals.get(cid)
        
        # Check for churn (no transaction in window)
        has_transaction = Transaction.query.filter(
            Transaction.customer_id == cid,
            Transaction.status == "completed",
            Transaction.tx_date > datetime.combine(cutoff_date, datetime.min.time()),
            Transaction.tx_date <= datetime.combine(window_end, datetime.max.time())
        ).first() is not None
        
        churned = 0 if has_transaction else 1
        
        row = {
            "customer_id": cid,
            # Numeric features
            "r_score": numeric.r_score or 0,
            "f_score": numeric.f_score or 0,
            "m_score": numeric.m_score or 0,
            "tenure_days": numeric.tenure_days or 0,
            # Text signals
            "msg_count_7d": signals.msg_count_7d if signals else 0,
            "msg_count_30d": signals.msg_count_30d if signals else 0,
            "msg_volatility": signals.msg_volatility if signals else 0,
            "avg_msg_length_30d": signals.avg_msg_length_30d if signals else 0,
            "complaint_rate_30d": signals.complaint_rate_30d if signals else 0,
            "response_delay_mean": signals.response_delay_mean if signals else 0,
            # Label
            "churned": churned
        }
        data.append(row)
    
    df = pd.DataFrame(data)
    logger.info(f"Dataset: {len(df)} samples, {df['churned'].sum()} churned")
    
    return df


def train_model(df: pd.DataFrame, test_size: float = 0.2) -> Tuple[xgb.XGBClassifier, Dict[str, Any]]:
    """Train XGBoost model"""
    if len(df) < 10:
        raise ValueError("Not enough training data")
    
    X = df[FEATURE_NAMES].values
    y = df["churned"].values
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42,
        stratify=y if len(np.unique(y)) > 1 else None
    )
    
    logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        objective='binary:logistic',
        eval_metric='auc',
        use_label_encoder=False,
        random_state=42
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    
    # Evaluate
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    
    metrics = {
        "accuracy": round(accuracy_score(y_test, y_pred), 4),
        "precision": round(precision_score(y_test, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_test, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_test, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_test, y_prob), 4) if len(np.unique(y_test)) > 1 else 0,
        "train_size": len(X_train),
        "test_size": len(X_test)
    }
    
    logger.info(f"Metrics: {metrics}")
    return model, metrics


def create_shap_explainer(model: xgb.XGBClassifier, X_sample: np.ndarray):
    """Create SHAP TreeExplainer"""
    try:
        import shap
        logger.info("Creating SHAP explainer...")
        explainer = shap.TreeExplainer(model)
        _ = explainer.shap_values(X_sample[:5])
        return explainer
    except Exception as e:
        logger.error(f"SHAP failed: {e}")
        return None


def save_artifacts(model, metrics, shap_explainer, version, output_dir="models"):
    """Save model artifacts"""
    os.makedirs(output_dir, exist_ok=True)
    paths = {}
    
    # Model
    model_path = os.path.join(output_dir, "churn_model.pkl")
    joblib.dump(model, model_path)
    paths["model"] = model_path
    
    # Feature metadata
    feature_meta = {
        "feature_names": FEATURE_NAMES,
        "feature_descriptions": FEATURE_DESCRIPTIONS,
        "expected_shape": len(FEATURE_NAMES),
        "model_type": "ontology_refactored",
        "version": version,
        "trained_at": datetime.utcnow().isoformat()
    }
    
    meta_path = os.path.join(output_dir, "features.json")
    with open(meta_path, 'w') as f:
        json.dump(feature_meta, f, indent=2)
    paths["features"] = meta_path
    
    # SHAP
    if shap_explainer:
        shap_path = os.path.join(output_dir, "shap_explainer.pkl")
        joblib.dump(shap_explainer, shap_path)
        paths["shap"] = shap_path
    
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
    parser.add_argument("--cutoff-date", type=str, 
                        default=(date.today() - timedelta(days=180)).isoformat())
    parser.add_argument("--churn-window", type=int, default=180)
    parser.add_argument("--version", type=str, default=None)
    parser.add_argument("--output-dir", type=str, default="models")
    
    args = parser.parse_args()
    cutoff_date = date.fromisoformat(args.cutoff_date)
    version = args.version or datetime.now().strftime("v%Y%m%d_%H%M%S")
    
    logger.info(f"Training with cutoff: {cutoff_date}, version: {version}")
    
    app = create_app()
    
    with app.app_context():
        df = prepare_dataset(cutoff_date, args.churn_window)
        
        if len(df) < 10:
            logger.error("Insufficient data")
            sys.exit(1)
        
        model, metrics = train_model(df)
        X = df[FEATURE_NAMES].values
        shap_explainer = create_shap_explainer(model, X)
        paths = save_artifacts(model, metrics, shap_explainer, version, args.output_dir)
        register_model_version(version, paths["model"], metrics)
        
        logger.info(f"Training complete! Version: {version}")


if __name__ == "__main__":
    main()
