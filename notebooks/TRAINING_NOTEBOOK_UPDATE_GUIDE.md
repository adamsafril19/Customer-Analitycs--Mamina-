# 🎯 Customer Churn Model Training - Truth-Aware Version
## Mamina Baby Spa

Notebook ini diupdate untuk menggunakan **Truth Architecture** yang baru:
- Filter hanya data dengan `link_status='verified'`
- Menggunakan 13 features dari `FEATURE_SCHEMA`
- Registrasi model ke `MLModelRegistry`
- Schema hash binding untuk reproducibility

---

## Cell 1: Setup & Import Libraries

```python
# Install dependencies jika belum ada
!pip install psycopg2-binary sqlalchemy pandas numpy scikit-learn xgboost shap matplotlib seaborn joblib
```

---

## Cell 2: Import Libraries

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import warnings
import hashlib
import json
import uuid
warnings.filterwarnings('ignore')

# Database
from sqlalchemy import create_engine, text

# ML Libraries
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    roc_curve, precision_recall_curve
)
import xgboost as xgb

# Explainability
import shap

# Model Persistence
import joblib

print("✅ Libraries imported successfully!")
print(f"XGBoost version: {xgb.__version__}")
print(f"SHAP version: {shap.__version__}")
```

---

## Cell 3: Feature Schema Definition (CRITICAL!)

```python
# ============================================================
# FEATURE SCHEMA - Must match FeatureService.FEATURE_SCHEMA
# ============================================================

FEATURE_SCHEMA_VERSION = "v1.0.0"

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

FEATURE_NAMES = [name for name, _ in FEATURE_SCHEMA]
EXPECTED_FEATURE_COUNT = len(FEATURE_SCHEMA)

def get_feature_schema_hash():
    """Generate hash of feature schema for validation"""
    schema_str = json.dumps(FEATURE_SCHEMA, sort_keys=True)
    return hashlib.sha256(schema_str.encode()).hexdigest()[:16]

print(f"📋 Feature Schema Version: {FEATURE_SCHEMA_VERSION}")
print(f"📊 Expected Features: {EXPECTED_FEATURE_COUNT}")
print(f"🔐 Schema Hash: {get_feature_schema_hash()}")
print(f"\n🏷️ Feature Names:")
for i, name in enumerate(FEATURE_NAMES):
    print(f"  {i+1}. {name}")
```

---

## Cell 4: Database Connection

```python
# Konfigurasi Database - sesuaikan dengan .env backend
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5433,
    'database': 'maminaChurn_db',
    'user': 'postgres',
    'password': 'adamsafril234'  # Ganti dengan password Anda
}

DATABASE_URL = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"

engine = create_engine(DATABASE_URL)

# Test connection
try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✅ Database connected successfully!")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
```

---

## Cell 5: Load Training Data - VERIFIED ONLY (CRITICAL!)

```python
# ============================================================
# TRUTH-AWARE DATA LOADING
# Only load data from VERIFIED feedback
# ============================================================

query_training_data = """
WITH verified_customers AS (
    -- Only customers with at least one verified feedback
    SELECT DISTINCT fl.customer_id
    FROM feedback_linked fl
    WHERE fl.link_status = 'verified'
),
latest_features AS (
    -- Get only the LATEST snapshot per customer to avoid time leakage
    SELECT 
        c.customer_id,
        nf.as_of_date,
        -- Numeric features from customer_numeric_features
        COALESCE(nf.recency_days, 999) as recency_days,
        COALESCE(nf.tx_count_30d, 0) as tx_count_30d,
        COALESCE(nf.tx_count_90d, 0) as tx_count_90d,
        COALESCE(nf.spend_30d, 0) as spend_30d,
        COALESCE(nf.spend_90d, 0) as spend_90d,
        COALESCE(nf.avg_tx_value, 0) as avg_tx_value,
        COALESCE(nf.tenure_days, 0) as tenure_days,
        -- Text signals from customer_text_signals
        COALESCE(ts.msg_count_7d, 0) as msg_count_7d,
        COALESCE(ts.msg_count_30d, 0) as msg_count_30d,
        COALESCE(ts.msg_volatility, 0) as msg_volatility,
        COALESCE(ts.avg_msg_length_30d, 0) as avg_msg_length_30d,
        COALESCE(ts.complaint_rate_30d, 0) as complaint_rate_30d,
        COALESCE(ts.response_delay_mean, 0) as response_delay_mean,
        -- Churn label (if exists)
        COALESCE(cl.is_churn, FALSE) as is_churn,
        -- Row number to get latest only
        ROW_NUMBER() OVER (
            PARTITION BY c.customer_id 
            ORDER BY nf.as_of_date DESC
        ) as rn
    FROM verified_customers vc
    JOIN customers c ON c.customer_id = vc.customer_id
    LEFT JOIN customer_numeric_features nf ON c.customer_id = nf.customer_id
    LEFT JOIN customer_text_signals ts ON c.customer_id = ts.customer_id 
        AND nf.as_of_date = ts.as_of_date
    LEFT JOIN churn_labels cl ON c.customer_id = cl.customer_id
    WHERE c.is_provisional = FALSE  -- Exclude provisional customers
)
SELECT * FROM latest_features
WHERE rn = 1  -- Only latest snapshot per customer
  AND recency_days IS NOT NULL
ORDER BY customer_id
"""

df = pd.read_sql(query_training_data, engine)

# Count verified feedback for each customer
verified_count_query = """
SELECT customer_id, COUNT(*) as verified_feedback_count
FROM feedback_linked
WHERE link_status = 'verified'
GROUP BY customer_id
"""
df_verified = pd.read_sql(verified_count_query, engine)
df = df.merge(df_verified, on='customer_id', how='left')

print(f"✅ Loaded {len(df)} customers with VERIFIED identity (latest snapshot only)")
print(f"📊 Churn distribution:")
print(df['is_churn'].value_counts())
print(f"\n🔗 Verified feedback per customer:")
print(df['verified_feedback_count'].describe())
df.head()
```

---

## Cell 6: Validate Feature Schema

```python
# ============================================================
# VALIDATE FEATURE COUNT MATCHES SCHEMA
# ============================================================

actual_features = [col for col in df.columns if col in FEATURE_NAMES]
missing_features = [name for name in FEATURE_NAMES if name not in df.columns]

print(f"📋 Expected features: {EXPECTED_FEATURE_COUNT}")
print(f"✅ Found features: {len(actual_features)}")

if missing_features:
    print(f"❌ MISSING FEATURES: {missing_features}")
    raise ValueError(f"Feature schema mismatch! Missing: {missing_features}")
else:
    print("✅ All features present!")

# Verify order
for i, name in enumerate(FEATURE_NAMES):
    print(f"  {i+1}. {name}: ✓")
```

---

## Cell 7: Define Churn Label (if not from DB)

```python
# ============================================================
# DEFINE CHURN LABEL
# Option 1: Use is_churn from database (if available)
# Option 2: Create synthetic label based on business rules
# 
# IMPORTANT: If using synthetic labels, this is NOT predictive ML
# It is "behavioral risk scoring" (rule compression)
# ============================================================

# Track label source for governance
LABEL_SOURCE = None

# Check if we have churn labels
if df['is_churn'].sum() > 0:
    print("✅ Using churn labels from database")
    df['churn'] = df['is_churn'].astype(int)
    LABEL_SOURCE = "database_ground_truth"
else:
    print("⚠️ No churn labels found - creating synthetic labels")
    print("⚠️ WARNING: Model will learn YOUR RULES, not predict real churn!")
    
    def define_churn(row):
        """
        Define churn based on behavioral signals:
        - High recency (long time since last transaction)
        - Low transaction activity
        - High complaint rate
        
        This is RULE COMPRESSION, not true supervised learning!
        """
        churn_score = 0
        
        # Risk factors
        if row['recency_days'] > 60:
            churn_score += 2
        if row['tx_count_30d'] == 0:
            churn_score += 2
        if row['complaint_rate_30d'] > 0.3:
            churn_score += 1
        if row['msg_volatility'] > 2.0:
            churn_score += 1
            
        # Protective factors
        if row['tx_count_90d'] > 3:
            churn_score -= 1
        if row['spend_90d'] > 500000:
            churn_score -= 1
            
        return 1 if churn_score >= 2 else 0
    
    df['churn'] = df.apply(define_churn, axis=1)
    LABEL_SOURCE = "synthetic_rule_v1"

print(f"\n📊 Churn Distribution:")
print(df['churn'].value_counts())
print(f"Churn Rate: {df['churn'].mean()*100:.2f}%")
print(f"\n🏷️ Label Source: {LABEL_SOURCE}")
if LABEL_SOURCE == "synthetic_rule_v1":
    print("⚠️ Model is a BEHAVIORAL RISK SCORER, not churn predictor!")
```

---

## Cell 8: Prepare Features

```python
# ============================================================
# PREPARE FEATURE MATRIX
# Order MUST match FEATURE_SCHEMA
# ============================================================

X = df[FEATURE_NAMES].copy()
y = df['churn'].copy()

# Store customer IDs for provenance
customer_ids = df['customer_id'].tolist()

print(f"📊 Feature Matrix: {X.shape}")
print(f"🎯 Target: {y.shape}")
print(f"✅ Feature order matches FEATURE_SCHEMA: {list(X.columns) == FEATURE_NAMES}")

# Handle missing values
print(f"\n❓ Missing values:")
print(X.isnull().sum())

for col in X.columns:
    if X[col].isnull().sum() > 0:
        X[col].fillna(X[col].median(), inplace=True)
```

---

## Cell 9: Train-Test Split

```python
# ============================================================
# TRAIN-TEST SPLIT
# ============================================================

if len(X) < 20:
    print("⚠️ Dataset kecil - menggunakan split tanpa stratify")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=0.3,
        random_state=42
    )
else:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, 
        test_size=0.2, 
        random_state=42,
        stratify=y
    )

print(f"📚 Training set: {X_train.shape[0]} samples")
print(f"🧪 Test set: {X_test.shape[0]} samples")
print(f"\n📈 Training churn rate: {y_train.mean()*100:.2f}%")
print(f"📉 Test churn rate: {y_test.mean()*100:.2f}%")
```

---

## Cell 9.5: Handle Imbalanced Data (SMOTE)

```python
# ============================================================
# ADAPTIVE IMBALANCE HANDLING
# SMOTE (Synthetic Minority Over-sampling Technique)
# ============================================================
from imblearn.over_sampling import SMOTE

churn_count = (y_train == 1).sum()
non_churn_count = (y_train == 0).sum()
churn_ratio = churn_count / len(y_train)

print("📊 Imbalance Analysis:")
print(f"   Total training samples: {len(y_train)}")
print(f"   Non-churn (0): {non_churn_count} ({non_churn_count/len(y_train):.1%})")
print(f"   Churn (1): {churn_count} ({churn_ratio:.1%})")
print(f"   Imbalance ratio: {non_churn_count/max(churn_count,1):.1f}:1")

# Store original for comparison
X_train_original = X_train.copy()
y_train_original = y_train.copy()

# Decision logic based on dataset analysis
USE_SMOTE = False

if churn_count < 10:
    print("\n⚠️ Too few churn samples for SMOTE (<10)")
    print("   Using scale_pos_weight only in XGBoost")
    
elif churn_ratio < 0.20:  # < 20% minority = imbalanced
    print("\n✅ Applying SMOTE (churn < 20%)...")
    
    # k_neighbors must be < minority samples
    k = min(5, churn_count - 1)
    print(f"   k_neighbors = {k}")
    
    smote = SMOTE(random_state=42, k_neighbors=k)
    X_train, y_train = smote.fit_resample(X_train, y_train)
    USE_SMOTE = True
    
    print(f"\n📊 After SMOTE:")
    print(f"   Total samples: {len(y_train)}")
    print(f"   Non-churn (0): {(y_train == 0).sum()}")
    print(f"   Churn (1): {(y_train == 1).sum()}")
    print(f"   Synthetic samples added: {len(y_train) - len(y_train_original)}")
    
else:
    print("\n✅ Data relatively balanced (churn >= 20%)")
    print("   No SMOTE needed")

# Track for provenance
SMOTE_APPLIED = USE_SMOTE
print(f"\n🏷️ SMOTE Applied: {SMOTE_APPLIED}")
```

> **Note:** SMOTE hanya diaplikasikan ke **training set**, TIDAK ke test set.
> Perlu install: `pip install imbalanced-learn`

---

## Cell 10: Train XGBoost Model

```python
# ============================================================
# TRAIN XGBOOST MODEL
# ============================================================

# Calculate class weights for imbalanced data
scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

xgb_model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=4,
    learning_rate=0.1,
    scale_pos_weight=scale_pos_weight,
    random_state=42,
    use_label_encoder=False,
    eval_metric='logloss'
)

print("🚀 Training XGBoost model...")
xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

# Predictions
y_pred = xgb_model.predict(X_test)
y_pred_proba = xgb_model.predict_proba(X_test)[:, 1]

print("✅ Model trained successfully!")
```

---

## Cell 11: Model Evaluation

```python
# ============================================================
# MODEL EVALUATION
# ============================================================

print("📊 Model Performance:\n")
print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
print(f"Recall:    {recall_score(y_test, y_pred, zero_division=0):.4f}")
print(f"F1 Score:  {f1_score(y_test, y_pred, zero_division=0):.4f}")

if len(np.unique(y_test)) > 1:
    print(f"ROC-AUC:   {roc_auc_score(y_test, y_pred_proba):.4f}")

print("\n📋 Classification Report:")
print(classification_report(y_test, y_pred, target_names=['Active', 'Churned'], zero_division=0))

# Confusion Matrix
plt.figure(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
            xticklabels=['Active', 'Churned'],
            yticklabels=['Active', 'Churned'])
plt.title('Confusion Matrix')
plt.ylabel('Actual')
plt.xlabel('Predicted')
plt.show()
```

---

## Cell 12: Feature Importance

```python
# ============================================================
# FEATURE IMPORTANCE
# ============================================================

importance_df = pd.DataFrame({
    'feature': FEATURE_NAMES,
    'importance': xgb_model.feature_importances_
}).sort_values('importance', ascending=False)

plt.figure(figsize=(10, 8))
sns.barplot(data=importance_df, x='importance', y='feature', palette='viridis')
plt.title('Feature Importance (XGBoost)')
plt.xlabel('Importance Score')
plt.tight_layout()
plt.show()

print("🏆 Top 5 Most Important Features:")
for i, row in importance_df.head(5).iterrows():
    print(f"  {row['feature']}: {row['importance']:.4f}")
```

---

## Cell 13: SHAP Explainer

```python
# ============================================================
# SHAP EXPLAINABILITY
# ============================================================

print("🔍 Creating SHAP explainer...")
explainer = shap.TreeExplainer(xgb_model)
shap_values_raw = explainer.shap_values(X_test)

# CRITICAL: Handle different SHAP output formats
# XGBoost binary classifier can return list[2] or array depending on version
if isinstance(shap_values_raw, list):
    print(f"📦 SHAP returned list of length {len(shap_values_raw)}")
    # For binary classification, use positive class (index 1)
    shap_values = shap_values_raw[1] if len(shap_values_raw) > 1 else shap_values_raw[0]
else:
    print(f"📦 SHAP returned array of shape {shap_values_raw.shape}")
    shap_values = shap_values_raw

print(f"✅ SHAP values shape: {shap_values.shape}")
print(f"✅ Expected shape: ({len(X_test)}, {EXPECTED_FEATURE_COUNT})")

# Validate shape matches
assert shap_values.shape[1] == EXPECTED_FEATURE_COUNT, "SHAP feature count mismatch!"

# Summary plot
plt.figure(figsize=(12, 8))
shap.summary_plot(shap_values, X_test, feature_names=FEATURE_NAMES, show=False)
plt.title('SHAP Feature Impact')
plt.tight_layout()
plt.show()

print("✅ SHAP explainer created successfully!")
```

---

## Cell 14: Save Model & Artifacts (CRITICAL!)

```python
# ============================================================
# SAVE MODEL WITH PROVENANCE
# ============================================================
import os

MODEL_VERSION = "v1.0.0"
SAVE_DIR = "../backend/ml_models"
os.makedirs(SAVE_DIR, exist_ok=True)

# Generate model hash
model_bytes = pickle.dumps(xgb_model)
model_hash = hashlib.sha256(model_bytes).hexdigest()[:16]

# Generate SHAP hash
shap_bytes = pickle.dumps(explainer)
shap_hash = hashlib.sha256(shap_bytes).hexdigest()[:16]

# Feature metadata
feature_metadata = {
    "feature_names": FEATURE_NAMES,
    "expected_shape": EXPECTED_FEATURE_COUNT,
    "feature_schema": FEATURE_SCHEMA,
    "feature_schema_hash": get_feature_schema_hash(),
    "feature_descriptions": {
        "recency_days": "Days since last transaction",
        "tx_count_30d": "Transaction count in last 30 days",
        "tx_count_90d": "Transaction count in last 90 days",
        "spend_30d": "Total spending in last 30 days",
        "spend_90d": "Total spending in last 90 days",
        "avg_tx_value": "Average transaction value",
        "tenure_days": "Customer tenure in days",
        "msg_count_7d": "Message count in last 7 days",
        "msg_count_30d": "Message count in last 30 days",
        "msg_volatility": "Std dev of daily message count",
        "avg_msg_length_30d": "Average message length",
        "complaint_rate_30d": "Complaint rate in last 30 days",
        "response_delay_mean": "Mean response time in seconds"
    }
}

# Save artifacts
joblib.dump(xgb_model, f"{SAVE_DIR}/churn_model.joblib")
joblib.dump(explainer, f"{SAVE_DIR}/shap_explainer.joblib")
joblib.dump(feature_metadata, f"{SAVE_DIR}/feature_metadata.joblib")

print("✅ Model artifacts saved:")
print(f"  📦 Model: {SAVE_DIR}/churn_model.joblib")
print(f"  🔍 SHAP: {SAVE_DIR}/shap_explainer.joblib")
print(f"  📋 Metadata: {SAVE_DIR}/feature_metadata.joblib")
print(f"\n🔐 Hashes:")
print(f"  Model: {model_hash}")
print(f"  SHAP: {shap_hash}")
print(f"  Schema: {get_feature_schema_hash()}")
```

---

## Cell 15: Register to MLModelRegistry

```python
# ============================================================
# REGISTER MODEL TO DATABASE
# ============================================================

registry_entry = {
    "model_name": "churn_xgboost",
    "model_version": MODEL_VERSION,
    "model_hash": model_hash,
    "feature_schema_hash": get_feature_schema_hash(),
    "feature_names": FEATURE_NAMES,
    "expected_feature_count": EXPECTED_FEATURE_COUNT,
    "shap_explainer_hash": shap_hash,
    "training_data_count": len(y_train_original),  # Original count before SMOTE
    "training_data_count_after_smote": len(y_train) if SMOTE_APPLIED else None,
    "smote_applied": SMOTE_APPLIED,
    "trained_on_link_status": "verified",
    "label_source": LABEL_SOURCE,  # CRITICAL: Track synthetic vs ground truth
    "training_date": datetime.utcnow().isoformat(),
    "is_active": True,
    "notes": f"Truth-aware training. Label: {LABEL_SOURCE}. SMOTE: {SMOTE_APPLIED}"
}

# Insert to database
insert_query = text("""
    INSERT INTO ml_model_registry (
        model_name, model_version, model_hash, feature_schema_hash,
        feature_names, expected_feature_count, shap_explainer_hash,
        training_data_count, trained_on_link_status, training_date,
        is_active, notes
    ) VALUES (
        :model_name, :model_version, :model_hash, :feature_schema_hash,
        :feature_names, :expected_feature_count, :shap_explainer_hash,
        :training_data_count, :trained_on_link_status, :training_date,
        :is_active, :notes
    )
    ON CONFLICT (model_hash) DO UPDATE SET
        is_active = EXCLUDED.is_active,
        notes = EXCLUDED.notes
""")

try:
    with engine.connect() as conn:
        conn.execute(insert_query, {
            **registry_entry,
            "feature_names": json.dumps(FEATURE_NAMES)
        })
        conn.commit()
    print("✅ Model registered to MLModelRegistry!")
except Exception as e:
    print(f"⚠️ Registry insert failed (may already exist): {e}")

print(f"\n📋 Registry Entry:")
for k, v in registry_entry.items():
    print(f"  {k}: {v}")
```

---

## Summary

Dengan notebook ini, model yang ditraining akan:
1. ✅ Hanya menggunakan data dari **verified feedback**
2. ✅ Menggunakan **13 features** sesuai `FEATURE_SCHEMA`
3. ✅ Menyimpan **schema hash** untuk validasi
4. ✅ Terdaftar di **MLModelRegistry** untuk governance
5. ✅ Memiliki **SHAP explainer** yang terikat dengan model
