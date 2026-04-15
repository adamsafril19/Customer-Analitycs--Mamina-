# 🎯 Behavioral Risk Scoring Model Training — v3.0.0
## Mamina Baby Spa

Notebook ini menggunakan **Temporal Proxy Label** yang valid + **Enhanced Feature Engineering**:
- Fitur dihitung dari window **[obs_date - 90, obs_date]** (masa lalu)
- Label ditentukan dari window **[obs_date, obs_date + 90]** (masa depan)
- Train-test split berbasis **waktu** (bukan random)
- Imputation dilakukan **setelah** split
- **NEW v3**: Smoothed trends, magnitude features, volatility features, interaction features
- Ablation tests untuk validasi model

---

## Cell 1: Setup & Import Libraries

```python
!pip install psycopg2-binary sqlalchemy pandas numpy scikit-learn xgboost shap matplotlib seaborn joblib imbalanced-learn
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

from sqlalchemy import create_engine, text
from sklearn.model_selection import StratifiedKFold
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
    roc_curve, precision_recall_curve
)
import xgboost as xgb
import shap
import joblib

print("✅ Libraries imported successfully!")
```

---

## Cell 3: Feature Schema v3.0.0 (CRITICAL!) + Configuration

```python
# ============================================================
# FEATURE SCHEMA v3 — Must match FeatureService.FEATURE_SCHEMA
# ============================================================

FEATURE_SCHEMA_VERSION = "v3.0.0"

# === CONFIGURABLE PARAMETERS (same as FeatureConfig in backend) ===
SMOOTHING_METHOD = "sma"       # "sma" or "ema"
SMOOTHING_WINDOW = 3           # Window size for smoothing
EMA_ALPHA = None               # If None, computed as 2/(window+1)
ACTIVITY_WINDOWS = 3           # Number of 30d windows
WINDOW_SIZE_DAYS = 30          # Size of each window
MIN_ACTIVITY_THRESHOLD = 0.01  # Floor for CV denominator
CV_CAP = 10.0                  # Cap for coefficient of variation
RATIO_CAP = 10.0               # Cap for safe ratio
RATIO_DEFAULT = 1.0            # Default when both num & denom are zero

FEATURE_SCHEMA = [
    # === TREND (smoothed, de-noised) ===
    ("recency_ratio", "numeric"),
    ("frequency_trend_smoothed", "numeric"),
    ("spend_trend_smoothed", "numeric"),
    ("msg_trend_smoothed", "numeric"),
    ("sentiment_trend", "numeric"),
    # === ABSOLUTE CONTEXT ===
    ("recency_days", "numeric"),
    ("tx_count_90d", "numeric"),
    ("spend_90d", "numeric"),
    ("avg_tx_value", "numeric"),
    ("tenure_days", "numeric"),
    # === MAGNITUDE ===
    ("activity_mean", "numeric"),
    ("recent_activity_avg", "numeric"),
    # === VOLATILITY ===
    ("activity_std", "numeric"),
    ("activity_cv", "numeric"),
    ("spend_volatility_cv", "numeric"),
    # === INTERACTION ===
    ("trend_magnitude_interaction", "numeric"),
    # === NLP / COMMUNICATION ===
    ("avg_sentiment_score", "numeric"),
    ("complaint_ratio", "numeric"),
    ("msg_volatility", "numeric"),
    ("response_delay_mean", "numeric"),
]

FEATURE_NAMES = [name for name, _ in FEATURE_SCHEMA]
EXPECTED_FEATURE_COUNT = len(FEATURE_SCHEMA)

def get_feature_schema_hash():
    schema_str = json.dumps(FEATURE_SCHEMA, sort_keys=True)
    return hashlib.sha256(schema_str.encode()).hexdigest()[:16]

def safe_ratio(current, prior, default=RATIO_DEFAULT, cap=RATIO_CAP):
    """Safe division for trend features."""
    if prior == 0:
        return default if current == 0 else cap
    return min(cap, current / prior)

# === SMOOTHING FUNCTIONS ===
def apply_sma(series, window=SMOOTHING_WINDOW):
    """Simple Moving Average."""
    result = []
    for i in range(len(series)):
        start = max(0, i - window + 1)
        result.append(float(np.mean(series[start:i + 1])))
    return result

def apply_ema(series, alpha=None):
    """Exponential Moving Average."""
    if alpha is None:
        alpha = 2.0 / (SMOOTHING_WINDOW + 1)
    if not series:
        return []
    result = [series[0]]
    for i in range(1, len(series)):
        ema_val = alpha * series[i] + (1 - alpha) * result[i - 1]
        result.append(ema_val)
    return result

def apply_smoothing(series):
    """Apply configured smoothing method."""
    if len(series) <= 1:
        return series[:]
    if SMOOTHING_METHOD == "ema":
        return apply_ema(series, EMA_ALPHA)
    return apply_sma(series, SMOOTHING_WINDOW)

def compute_trend_slope(smoothed_series):
    """Linear regression slope on smoothed series."""
    n = len(smoothed_series)
    if n < 2:
        return 0.0
    t = np.arange(n, dtype=float)
    y = np.array(smoothed_series, dtype=float)
    t_mean, y_mean = t.mean(), y.mean()
    num = np.sum((t - t_mean) * (y - y_mean))
    denom = np.sum((t - t_mean) ** 2)
    return float(num / denom) if denom != 0 else 0.0

def compute_cv(values, min_thresh=MIN_ACTIVITY_THRESHOLD, cap=CV_CAP):
    """Coefficient of Variation with zero-safe handling."""
    if len(values) < 2:
        return 0.0
    mean_val = float(np.mean(values))
    if mean_val < min_thresh:
        return 0.0
    return min(cap, float(np.std(values, ddof=0)) / mean_val)

print(f"📋 Feature Schema Version: {FEATURE_SCHEMA_VERSION}")
print(f"📊 Expected Features: {EXPECTED_FEATURE_COUNT}")
print(f"🔐 Schema Hash: {get_feature_schema_hash()}")
print(f"🔧 Smoothing: {SMOOTHING_METHOD} (window={SMOOTHING_WINDOW})")
print(f"\n🏷️ Features:")
for i, name in enumerate(FEATURE_NAMES):
    print(f"  {i+1}. {name}")
```

---

## Cell 4: Database Connection

```python
DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5433,
    'database': 'maminaChurn_db',
    'user': 'postgres',
    'password': 'adamsafril234'  # Ganti dengan password Anda
}

DATABASE_URL = f"postgresql+psycopg2://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✅ Database connected successfully!")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
```

---

## Cell 5: Generate Observation Dates & Proxy Labels (CRITICAL!)

```python
# ============================================================
# TEMPORAL PROXY LABEL GENERATION
#
# KEY PRINCIPLE:
#   Features = computed from data BEFORE observation_date
#   Label = determined by behavior AFTER observation_date
#
# Definition:
#   is_disengaged = TRUE if NO transaction in 90 days AFTER observation_date
#
# This is NOT circular because:
#   - Features use data from [obs_date - 90, obs_date]
#   - Label uses data from [obs_date, obs_date + 90]
#   - These windows DO NOT OVERLAP
# ============================================================

# Step 1: Determine valid observation date range
date_range_query = """
SELECT 
    MIN(tx_date)::date + 90 as earliest_obs_date,
    MAX(tx_date)::date - 90 as latest_obs_date,
    COUNT(DISTINCT customer_id) as total_customers
FROM transactions
WHERE status = 'completed'
"""
date_info = pd.read_sql(date_range_query, engine)
print(f"📅 Earliest observation date: {date_info['earliest_obs_date'].iloc[0]}")
print(f"📅 Latest observation date: {date_info['latest_obs_date'].iloc[0]}")
print(f"👥 Total customers with transactions: {date_info['total_customers'].iloc[0]}")

# Step 2: Create observation dates (monthly intervals)
earliest = pd.to_datetime(date_info['earliest_obs_date'].iloc[0])
latest = pd.to_datetime(date_info['latest_obs_date'].iloc[0])
observation_dates = pd.date_range(start=earliest, end=latest, freq='MS')
print(f"\n📆 Generated {len(observation_dates)} observation dates")
for d in observation_dates:
    print(f"  - {d.date()}")
```

---

## Cell 6: Build Training Dataset with Temporal Separation

```python
# ============================================================
# BUILD TRAINING DATA
# For each (customer, observation_date):
#   1. Compute features from [obs_date - 90, obs_date]
#   2. Compute label from [obs_date, obs_date + 90]
#
# v3 CHANGE: Also pull per-window data for smoothing
# ============================================================

training_rows = []

for obs_date in observation_dates:
    obs_date_str = obs_date.strftime('%Y-%m-%d')
    
    query = text("""
    WITH customer_pool AS (
        -- Customers who had at least 1 transaction BEFORE obs_date
        SELECT DISTINCT customer_id
        FROM transactions
        WHERE status = 'completed'
          AND tx_date < :obs_date
    ),
    -- === FEATURE WINDOW: [obs_date - 90, obs_date] ===
    tx_features AS (
        SELECT
            cp.customer_id,
            -- Recency
            EXTRACT(DAY FROM (:obs_date::timestamp - MAX(t.tx_date)))::int as recency_days,
            -- Frequency & Monetary (per window for smoothing)
            COUNT(CASE WHEN t.tx_date >= :obs_date::date - 30 THEN t.tx_id END) as tx_count_w3,
            COUNT(CASE WHEN t.tx_date >= :obs_date::date - 60
                        AND t.tx_date < :obs_date::date - 30 THEN t.tx_id END) as tx_count_w2,
            COUNT(CASE WHEN t.tx_date >= :obs_date::date - 90
                        AND t.tx_date < :obs_date::date - 60 THEN t.tx_id END) as tx_count_w1,
            -- Total 90d
            COUNT(CASE WHEN t.tx_date >= :obs_date::date - 90 THEN t.tx_id END) as tx_count_90d,
            -- Spend per window
            COALESCE(SUM(CASE WHEN t.tx_date >= :obs_date::date - 30 THEN t.amount END), 0) as spend_w3,
            COALESCE(SUM(CASE WHEN t.tx_date >= :obs_date::date - 60
                              AND t.tx_date < :obs_date::date - 30 THEN t.amount END), 0) as spend_w2,
            COALESCE(SUM(CASE WHEN t.tx_date >= :obs_date::date - 90
                              AND t.tx_date < :obs_date::date - 60 THEN t.amount END), 0) as spend_w1,
            -- Total spend 90d
            COALESCE(SUM(CASE WHEN t.tx_date >= :obs_date::date - 90 THEN t.amount END), 0) as spend_90d,
            -- Avg transaction value
            COALESCE(AVG(CASE WHEN t.tx_date >= :obs_date::date - 90 THEN t.amount END), 0) as avg_tx_value
        FROM customer_pool cp
        LEFT JOIN transactions t ON cp.customer_id = t.customer_id
            AND t.status = 'completed' AND t.tx_date < :obs_date
        GROUP BY cp.customer_id
    ),
    -- Tenure
    tenure AS (
        SELECT customer_id,
               EXTRACT(DAY FROM (:obs_date::timestamp - created_at))::int as tenure_days
        FROM customers
        WHERE is_provisional = FALSE
    ),
    -- === LABEL WINDOW: [obs_date, obs_date + 90] ===
    label AS (
        SELECT
            cp.customer_id,
            CASE WHEN COUNT(t.tx_id) = 0 THEN 1 ELSE 0 END as is_disengaged
        FROM customer_pool cp
        LEFT JOIN transactions t ON cp.customer_id = t.customer_id
            AND t.status = 'completed'
            AND t.tx_date >= :obs_date
            AND t.tx_date < :obs_date::date + 90
        GROUP BY cp.customer_id
    )
    SELECT
        tf.customer_id,
        :obs_date::date as observation_date,
        -- Raw features
        tf.recency_days,
        tf.tx_count_w1, tf.tx_count_w2, tf.tx_count_w3,
        tf.tx_count_90d,
        tf.spend_w1, tf.spend_w2, tf.spend_w3,
        tf.spend_90d,
        tf.avg_tx_value,
        tn.tenure_days,
        -- Label (from FUTURE window)
        lb.is_disengaged
    FROM tx_features tf
    JOIN tenure tn ON tf.customer_id = tn.customer_id
    JOIN label lb ON tf.customer_id = lb.customer_id
    WHERE tf.recency_days IS NOT NULL
      AND tn.tenure_days > 0
    """)
    
    df_obs = pd.read_sql(query, engine, params={"obs_date": obs_date_str})
    df_obs['observation_date'] = obs_date.date()
    training_rows.append(df_obs)
    print(f"  📅 {obs_date.date()}: {len(df_obs)} samples, "
          f"disengaged={df_obs['is_disengaged'].sum()}")

df_raw = pd.concat(training_rows, ignore_index=True)
print(f"\n✅ Total raw training samples: {len(df_raw)}")
print(f"📊 Disengagement rate: {df_raw['is_disengaged'].mean()*100:.1f}%")
```

---

## Cell 7: Compute Derived Features (v3 — Smoothed + Magnitude + Volatility)

```python
# ============================================================
# COMPUTE v3 FEATURES
# 3 Dimensions: Trend (smoothed) + Magnitude + Volatility
# Plus: Interaction feature and NLP signals
# ============================================================

# --- Avg Interpurchase Days (per customer, all tx before obs) ---
def compute_avg_interpurchase(customer_id, obs_date):
    """Average gap between consecutive transactions."""
    query = text("""
        SELECT tx_date FROM transactions
        WHERE customer_id = :cid AND status = 'completed'
          AND tx_date < :obs_date
        ORDER BY tx_date
    """)
    dates = pd.read_sql(query, engine, params={"cid": str(customer_id), "obs_date": str(obs_date)})
    if len(dates) < 2:
        return 0.0
    gaps = dates['tx_date'].diff().dropna().dt.days
    return float(gaps.mean()) if len(gaps) > 0 else 0.0

print("⏳ Computing avg interpurchase days...")
df_raw['avg_ipt'] = df_raw.apply(
    lambda r: compute_avg_interpurchase(r['customer_id'], r['observation_date']), axis=1
)

# --- recency_ratio ---
df_raw['recency_ratio'] = df_raw.apply(
    lambda r: safe_ratio(r['recency_days'], r['avg_ipt']), axis=1)

# --- Windowed series for smoothing ---
# tx_count series: [w1 (oldest), w2, w3 (newest)]
print("⏳ Computing smoothed trends, magnitude, volatility...")

def compute_smoothed_features(row):
    """Compute all v3 derived features from windowed data."""
    # Transaction series (oldest → newest)
    tx_series = [float(row['tx_count_w1']), float(row['tx_count_w2']), float(row['tx_count_w3'])]
    spend_series = [float(row['spend_w1']), float(row['spend_w2']), float(row['spend_w3'])]
    
    # Smoothing
    tx_smoothed = apply_smoothing(tx_series)
    spend_smoothed = apply_smoothing(spend_series)
    
    # Trend slope (linear regression on smoothed)
    freq_trend = compute_trend_slope(tx_smoothed)
    spend_trend = compute_trend_slope(spend_smoothed)
    
    # Magnitude
    activity_mean = float(np.mean(tx_series))
    recent_activity_avg = float(tx_series[-1])  # Most recent window
    
    # Volatility
    activity_std = float(np.std(tx_series, ddof=0))
    activity_cv = compute_cv(tx_series)
    spend_cv = compute_cv(spend_series)
    
    # Interaction
    trend_mag = freq_trend * activity_mean
    
    return pd.Series({
        'frequency_trend_smoothed': freq_trend,
        'spend_trend_smoothed': spend_trend,
        'activity_mean': activity_mean,
        'recent_activity_avg': recent_activity_avg,
        'activity_std': activity_std,
        'activity_cv': activity_cv,
        'spend_volatility_cv': spend_cv,
        'trend_magnitude_interaction': trend_mag,
    })

derived = df_raw.apply(compute_smoothed_features, axis=1)
for col in derived.columns:
    df_raw[col] = derived[col]

# --- Message Features (with windowed smoothing) ---
def compute_msg_features(customer_id, obs_date):
    """Message counts per window and complaint ratio from verified feedback."""
    results = {}
    for window_idx, suffix in enumerate(['w1', 'w2', 'w3']):
        offset_end = (2 - window_idx) * 30
        offset_start = offset_end + 30
        
        query = text("""
            SELECT COUNT(*) as cnt
            FROM feedback_features ff
            JOIN feedback_linked fl ON ff.link_id = fl.link_id
            WHERE fl.customer_id = :cid
              AND fl.link_status = 'verified'
              AND ff.processed_at >= :obs_date::date - :start
              AND ff.processed_at < :obs_date::date - :end_off
        """)
        try:
            r = pd.read_sql(query, engine, params={
                "cid": str(customer_id), "obs_date": str(obs_date),
                "start": offset_start, "end_off": offset_end
            })
            results[f'msg_{suffix}'] = int(r.iloc[0]['cnt']) if len(r) > 0 else 0
        except:
            results[f'msg_{suffix}'] = 0
    
    # Complaint ratio and other NLP signals (most recent 30d)
    query2 = text("""
        SELECT
            COALESCE(AVG(CASE WHEN ff.has_complaint THEN 1.0 ELSE 0.0 END), 0) as complaint_ratio,
            COALESCE(STDDEV(daily_count), 0) as msg_volatility,
            COALESCE(AVG(ff.response_time_secs), 0) as response_delay_mean
        FROM feedback_features ff
        JOIN feedback_linked fl ON ff.link_id = fl.link_id
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::float as daily_count
            FROM feedback_features ff2
            JOIN feedback_linked fl2 ON ff2.link_id = fl2.link_id
            WHERE fl2.customer_id = :cid
              AND fl2.link_status = 'verified'
              AND ff2.processed_at >= :obs_date::date - 30
              AND ff2.processed_at < :obs_date::date
            GROUP BY ff2.processed_at::date
        ) daily ON true
        WHERE fl.customer_id = :cid
          AND fl.link_status = 'verified'
          AND ff.processed_at >= :obs_date::date - 30
          AND ff.processed_at < :obs_date::date
    """)
    try:
        r2 = pd.read_sql(query2, engine, params={
            "cid": str(customer_id), "obs_date": str(obs_date)
        })
        if len(r2) > 0:
            results['complaint_ratio'] = float(r2.iloc[0].get('complaint_ratio', 0) or 0)
            results['msg_volatility'] = float(r2.iloc[0].get('msg_volatility', 0) or 0)
            results['response_delay_mean'] = float(r2.iloc[0].get('response_delay_mean', 0) or 0)
        else:
            results['complaint_ratio'] = 0.0
            results['msg_volatility'] = 0.0
            results['response_delay_mean'] = 0.0
    except:
        results['complaint_ratio'] = 0.0
        results['msg_volatility'] = 0.0
        results['response_delay_mean'] = 0.0
    
    return results

print("⏳ Computing message features...")
msg_features = df_raw.apply(
    lambda r: compute_msg_features(r['customer_id'], r['observation_date']), axis=1
)
msg_df = pd.DataFrame(msg_features.tolist())

# Compute msg_trend_smoothed from windowed message series
def compute_msg_trend_from_row(row):
    msg_series = [float(row.get('msg_w1', 0)), float(row.get('msg_w2', 0)), float(row.get('msg_w3', 0))]
    smoothed = apply_smoothing(msg_series)
    return compute_trend_slope(smoothed)

df_raw['msg_trend_smoothed'] = msg_df.apply(compute_msg_trend_from_row, axis=1)
df_raw['complaint_ratio'] = msg_df['complaint_ratio']
df_raw['msg_volatility'] = msg_df['msg_volatility']
df_raw['response_delay_mean'] = msg_df['response_delay_mean']

# --- Sentiment Features ---
def compute_sentiment(customer_id, obs_date):
    """Get sentiment from pre-computed semantics table."""
    query = text("""
        SELECT avg_sentiment_score FROM customer_text_semantics
        WHERE customer_id = :cid AND as_of_date <= :obs_date
        ORDER BY as_of_date DESC LIMIT 1
    """)
    try:
        result = pd.read_sql(query, engine, params={
            "cid": str(customer_id), "obs_date": str(obs_date)
        })
        if len(result) > 0 and result.iloc[0]['avg_sentiment_score'] is not None:
            current = float(result.iloc[0]['avg_sentiment_score'])
            # Prior period
            prior_q = text("""
                SELECT avg_sentiment_score FROM customer_text_semantics
                WHERE customer_id = :cid AND as_of_date <= :prior_date
                ORDER BY as_of_date DESC LIMIT 1
            """)
            prior_date = str(pd.to_datetime(obs_date) - timedelta(days=30))[:10]
            prior_r = pd.read_sql(prior_q, engine, params={
                "cid": str(customer_id), "prior_date": prior_date
            })
            prior = float(prior_r.iloc[0]['avg_sentiment_score']) if len(prior_r) > 0 and prior_r.iloc[0]['avg_sentiment_score'] is not None else 0.0
            return current, current - prior
    except:
        pass
    return 0.0, 0.0

print("⏳ Computing sentiment features...")
sentiment_results = df_raw.apply(
    lambda r: compute_sentiment(r['customer_id'], r['observation_date']), axis=1
)
df_raw['avg_sentiment_score'] = sentiment_results.apply(lambda x: x[0])
df_raw['sentiment_trend'] = sentiment_results.apply(lambda x: x[1])

print(f"\n✅ All v3 features computed!")
print(f"📊 Feature columns available: {len(df_raw.columns)}")
```

---

## Cell 8: Assemble Feature Matrix (Schema-Ordered)

```python
# ============================================================
# ASSEMBLE X AND y IN SCHEMA ORDER
# ============================================================

X = pd.DataFrame({name: df_raw[name] for name in FEATURE_NAMES})
y = df_raw['is_disengaged'].copy()
obs_dates = df_raw['observation_date'].copy()

assert list(X.columns) == FEATURE_NAMES, "Feature order mismatch!"
assert X.shape[1] == EXPECTED_FEATURE_COUNT, f"Expected {EXPECTED_FEATURE_COUNT}, got {X.shape[1]}"

print(f"📊 Feature Matrix: {X.shape}")
print(f"🎯 Target: {y.shape}")
print(f"✅ Feature order matches FEATURE_SCHEMA: True")
print(f"\n📊 Disengagement rate: {y.mean()*100:.1f}%")
print(f"\n❓ Missing values:\n{X.isnull().sum()}")
```

---

## Cell 8.5: 📊 Feature Validation (Pre-Modeling EDA)

```python
# ============================================================
# FEATURE VALIDATION — Distribution & Discriminative Power
# ============================================================

print("=" * 60)
print("📊 FEATURE VALIDATION (Pre-Modeling)")
print("=" * 60)

# 1. Distribution plots
fig, axes = plt.subplots(5, 4, figsize=(20, 20))
axes = axes.ravel()
for i, name in enumerate(FEATURE_NAMES):
    ax = axes[i]
    X[name].hist(bins=30, ax=ax, alpha=0.7, color='steelblue')
    ax.set_title(name, fontsize=10)
    ax.set_xlabel('')
plt.suptitle('Feature Distributions (v3)', fontsize=14, y=1.02)
plt.tight_layout()
plt.show()

# 2. Compare high-risk vs low-risk
print("\n📊 Feature comparison: Disengaged vs Active")
comparison = pd.DataFrame({
    'Active_mean': X[y == 0].mean(),
    'Disengaged_mean': X[y == 1].mean(),
    'Active_std': X[y == 0].std(),
    'Disengaged_std': X[y == 1].std(),
})
comparison['diff_pct'] = ((comparison['Disengaged_mean'] - comparison['Active_mean'])
                          / comparison['Active_mean'].replace(0, np.nan) * 100)
print(comparison.round(3).to_string())

# 3. Correlation matrix
print("\n📊 Feature Correlation Matrix")
corr = X.corr()
plt.figure(figsize=(14, 12))
mask = np.triu(np.ones_like(corr, dtype=bool))
sns.heatmap(corr, mask=mask, annot=True, fmt='.2f', cmap='RdBu_r',
            center=0, vmin=-1, vmax=1, square=True, linewidths=0.5)
plt.title('Feature Correlation Matrix (v3)')
plt.tight_layout()
plt.show()

# 4. Redundancy detection
print("\n⚠️ Highly Correlated Pairs (|corr| > 0.90):")
high_corr = []
for i in range(len(corr.columns)):
    for j in range(i+1, len(corr.columns)):
        if abs(corr.iloc[i, j]) > 0.90:
            high_corr.append((corr.columns[i], corr.columns[j], corr.iloc[i, j]))
            print(f"  {corr.columns[i]} ↔ {corr.columns[j]}: {corr.iloc[i, j]:.3f}")
if not high_corr:
    print("  ✅ No highly correlated pairs found")

# 5. Edge case report
print(f"\n📊 Edge Case Report:")
print(f"  Zero activity_mean: {(X['activity_mean'] == 0).sum()} samples")
print(f"  Zero recent_activity: {(X['recent_activity_avg'] == 0).sum()} samples")
print(f"  Zero activity_cv: {(X['activity_cv'] == 0).sum()} samples")
print(f"  Capped activity_cv (={CV_CAP}): {(X['activity_cv'] >= CV_CAP).sum()} samples")
```

---

## Cell 9: TIME-BASED Train-Test Split (CRITICAL!)

```python
# ============================================================
# TIME-BASED SPLIT (NOT random!)
# ============================================================

sort_idx = obs_dates.argsort()
X = X.iloc[sort_idx].reset_index(drop=True)
y = y.iloc[sort_idx].reset_index(drop=True)
obs_dates_sorted = obs_dates.iloc[sort_idx].reset_index(drop=True)

cutoff_idx = int(len(X) * 0.8)
cutoff_date = obs_dates_sorted.iloc[cutoff_idx]

X_train = X.iloc[:cutoff_idx].copy()
X_test = X.iloc[cutoff_idx:].copy()
y_train = y.iloc[:cutoff_idx].copy()
y_test = y.iloc[cutoff_idx:].copy()

print(f"📅 Time-based split cutoff: {cutoff_date}")
print(f"📚 Training set: {X_train.shape[0]} samples (before {cutoff_date})")
print(f"🧪 Test set: {X_test.shape[0]} samples (from {cutoff_date} onward)")
print(f"\n📈 Training disengagement rate: {y_train.mean()*100:.1f}%")
print(f"📉 Test disengagement rate: {y_test.mean()*100:.1f}%")

# ============================================================
# IMPUTATION — AFTER SPLIT, FIT ON TRAINING ONLY
# ============================================================
from sklearn.impute import SimpleImputer

imputer = SimpleImputer(strategy='median')
X_train_cols = X_train.columns
X_train = pd.DataFrame(imputer.fit_transform(X_train), columns=X_train_cols)
X_test = pd.DataFrame(imputer.transform(X_test), columns=X_train_cols)

print(f"\n✅ Imputation done (fit on training only)")
print(f"❓ Remaining NaN in train: {X_train.isnull().sum().sum()}")
print(f"❓ Remaining NaN in test: {X_test.isnull().sum().sum()}")
```

---

## Cell 9.5: Handle Imbalanced Data (SMOTE)

```python
from imblearn.over_sampling import SMOTE

churn_count = (y_train == 1).sum()
non_churn_count = (y_train == 0).sum()
churn_ratio = churn_count / len(y_train)

print("📊 Imbalance Analysis:")
print(f"   Non-disengaged (0): {non_churn_count} ({non_churn_count/len(y_train):.1%})")
print(f"   Disengaged (1): {churn_count} ({churn_ratio:.1%})")

X_train_original = X_train.copy()
y_train_original = y_train.copy()
USE_SMOTE = False

if churn_count < 10:
    print("\n⚠️ Too few positive samples for SMOTE (<10)")
elif churn_ratio < 0.20:
    print("\n✅ Applying SMOTE...")
    k = min(5, churn_count - 1)
    smote = SMOTE(random_state=42, k_neighbors=k)
    X_train, y_train = smote.fit_resample(X_train, y_train)
    USE_SMOTE = True
    print(f"   After SMOTE: {len(y_train)} samples")
else:
    print("\n✅ Data balanced enough, no SMOTE needed")

SMOTE_APPLIED = USE_SMOTE
```

---

## Cell 10: Train XGBoost Model

```python
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

y_pred = xgb_model.predict(X_test)
y_pred_proba = xgb_model.predict_proba(X_test)[:, 1]
print("✅ Model trained!")
```

---

## Cell 11: Model Evaluation

```python
print("📊 Model Performance:\n")
print(f"Accuracy:  {accuracy_score(y_test, y_pred):.4f}")
print(f"Precision: {precision_score(y_test, y_pred, zero_division=0):.4f}")
print(f"Recall:    {recall_score(y_test, y_pred, zero_division=0):.4f}")
print(f"F1 Score:  {f1_score(y_test, y_pred, zero_division=0):.4f}")

if len(np.unique(y_test)) > 1:
    print(f"ROC-AUC:   {roc_auc_score(y_test, y_pred_proba):.4f}")

print("\n📋 Classification Report:")
print(classification_report(y_test, y_pred,
    target_names=['Active', 'Disengaged'], zero_division=0))

plt.figure(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Active', 'Disengaged'],
            yticklabels=['Active', 'Disengaged'])
plt.title('Confusion Matrix')
plt.ylabel('Actual')
plt.xlabel('Predicted')
plt.show()
```

---

## Cell 12: Feature Importance

```python
importance_df = pd.DataFrame({
    'feature': FEATURE_NAMES,
    'importance': xgb_model.feature_importances_
}).sort_values('importance', ascending=False)

plt.figure(figsize=(10, 10))
sns.barplot(data=importance_df, x='importance', y='feature', palette='viridis')
plt.title('Feature Importance (XGBoost v3)')
plt.xlabel('Importance Score')
plt.tight_layout()
plt.show()

print("🏆 Top 5 Features:")
for _, row in importance_df.head(5).iterrows():
    print(f"  {row['feature']}: {row['importance']:.4f}")
```

---

## Cell 12.5: 🧪 ABLATION TESTS (Model Validation)

```python
# ============================================================
# ABLATION TESTS — Verify model is NOT a rule approximator
# ============================================================

print("=" * 60)
print("🧪 ABLATION TESTS")
print("=" * 60)

# --- Test 1: Drop recency_ratio, check AUC drop ---
print("\n📊 Test 1: Model WITHOUT recency_ratio")
drop_cols_1 = ['recency_ratio', 'recency_days']
X_train_no_rec = X_train.drop(columns=drop_cols_1, errors='ignore')
X_test_no_rec = X_test.drop(columns=drop_cols_1, errors='ignore')

model_no_rec = xgb.XGBClassifier(
    n_estimators=100, max_depth=4, learning_rate=0.1,
    scale_pos_weight=scale_pos_weight, random_state=42,
    use_label_encoder=False, eval_metric='logloss'
)
model_no_rec.fit(X_train_no_rec, y_train, verbose=False)
pred_no_rec = model_no_rec.predict_proba(X_test_no_rec)[:, 1]

if len(np.unique(y_test)) > 1:
    auc_full = roc_auc_score(y_test, y_pred_proba)
    auc_no_rec = roc_auc_score(y_test, pred_no_rec)
    auc_drop = (auc_full - auc_no_rec) / auc_full * 100
    print(f"   Full model AUC: {auc_full:.4f}")
    print(f"   Without recency AUC: {auc_no_rec:.4f}")
    print(f"   AUC drop: {auc_drop:.1f}%")
    if auc_drop > 20:
        print(f"   ⚠️ WARNING: Model too dependent on recency ({auc_drop:.0f}% drop)")
    else:
        print(f"   ✅ Model survives without recency (only {auc_drop:.0f}% drop)")

# --- Test 2: Feature concentration (Gini) ---
print("\n📊 Test 2: Feature Importance Concentration")
importances = xgb_model.feature_importances_
normalized = importances / importances.sum()
gini = 1 - sum(n**2 for n in normalized)
print(f"   Gini index: {gini:.3f} (0=single feature dominant, 1=perfectly spread)")
if gini < 0.3:
    print(f"   ⚠️ WARNING: Features too concentrated (Gini={gini:.2f})")
else:
    print(f"   ✅ Feature importance well distributed")

# --- Test 3: NLP feature contribution ---
print("\n📊 Test 3: NLP Feature Contribution")
nlp_features = ['avg_sentiment_score', 'sentiment_trend', 'complaint_ratio']
nlp_importance = sum(importance_df[importance_df['feature'].isin(nlp_features)]['importance'])
total_importance = importance_df['importance'].sum()
nlp_pct = nlp_importance / total_importance * 100 if total_importance > 0 else 0
print(f"   NLP features: {nlp_features}")
print(f"   NLP contribution: {nlp_pct:.1f}%")
if nlp_pct < 5:
    print(f"   ⚠️ NLP features contribute <5% — consider if they add value")
else:
    print(f"   ✅ NLP features contribute {nlp_pct:.1f}%")

# --- Test 4: NEW v3 feature contribution ---
print("\n📊 Test 4: v3 New Feature Contribution")
v3_features = ['activity_mean', 'recent_activity_avg', 'activity_std', 
                'activity_cv', 'spend_volatility_cv', 'trend_magnitude_interaction',
                'frequency_trend_smoothed', 'spend_trend_smoothed', 'msg_trend_smoothed']
v3_importance = sum(importance_df[importance_df['feature'].isin(v3_features)]['importance'])
v3_pct = v3_importance / total_importance * 100 if total_importance > 0 else 0
print(f"   v3 new features: {len(v3_features)}")
print(f"   v3 contribution: {v3_pct:.1f}%")
if v3_pct < 10:
    print(f"   ⚠️ New v3 features contribute <10% — verify they add value")
else:
    print(f"   ✅ New v3 features contribute {v3_pct:.1f}%")

print("\n" + "=" * 60)
```

---

## Cell 13: SHAP Explainer

```python
print("🔍 Creating SHAP explainer...")
explainer = shap.TreeExplainer(xgb_model)
shap_values_raw = explainer.shap_values(X_test)

if isinstance(shap_values_raw, list):
    shap_values = shap_values_raw[1] if len(shap_values_raw) > 1 else shap_values_raw[0]
else:
    shap_values = shap_values_raw

assert shap_values.shape[1] == EXPECTED_FEATURE_COUNT, "SHAP feature count mismatch!"

plt.figure(figsize=(12, 10))
shap.summary_plot(shap_values, X_test, feature_names=FEATURE_NAMES, show=False)
plt.title('SHAP Feature Impact (v3 Risk Scoring)')
plt.tight_layout()
plt.show()
```

---

## Cell 14: Save Model & Artifacts

```python
import os, pickle

MODEL_VERSION = "v3.0.0"
SAVE_DIR = "../backend/ml_models"
os.makedirs(SAVE_DIR, exist_ok=True)

model_bytes = pickle.dumps(xgb_model)
model_hash = hashlib.sha256(model_bytes).hexdigest()[:16]
shap_bytes = pickle.dumps(explainer)
shap_hash = hashlib.sha256(shap_bytes).hexdigest()[:16]

feature_metadata = {
    "feature_names": FEATURE_NAMES,
    "expected_shape": EXPECTED_FEATURE_COUNT,
    "feature_schema": FEATURE_SCHEMA,
    "feature_schema_hash": get_feature_schema_hash(),
    "schema_version": FEATURE_SCHEMA_VERSION,
    "feature_config": {
        "smoothing_method": SMOOTHING_METHOD,
        "smoothing_window": SMOOTHING_WINDOW,
        "ema_alpha": EMA_ALPHA,
        "activity_windows": ACTIVITY_WINDOWS,
        "window_size_days": WINDOW_SIZE_DAYS,
        "min_activity_threshold": MIN_ACTIVITY_THRESHOLD,
        "cv_cap": CV_CAP,
    },
    "feature_descriptions": {
        "recency_ratio": "Rasio recency terhadap baseline personal",
        "frequency_trend_smoothed": "Slope tren frekuensi (smoothed, de-noised)",
        "spend_trend_smoothed": "Slope tren belanja (smoothed, de-noised)",
        "msg_trend_smoothed": "Slope tren komunikasi (smoothed, de-noised)",
        "sentiment_trend": "Perubahan sentimen (30d vs prior 30d)",
        "recency_days": "Hari sejak transaksi terakhir",
        "tx_count_90d": "Jumlah transaksi 90 hari",
        "spend_90d": "Total belanja 90 hari",
        "avg_tx_value": "Rata-rata nilai transaksi",
        "tenure_days": "Lama menjadi customer (hari)",
        "activity_mean": "Rata-rata tx per window (3 × 30d)",
        "recent_activity_avg": "Tx count di window terkini",
        "activity_std": "Std deviasi aktivitas antar window",
        "activity_cv": "Koefisien variasi aktivitas (std/mean)",
        "spend_volatility_cv": "Koefisien variasi belanja antar window",
        "trend_magnitude_interaction": "Interaksi tren × tingkat aktivitas",
        "avg_sentiment_score": "Rata-rata skor sentimen 30 hari",
        "complaint_ratio": "Rasio pesan komplain 30 hari",
        "msg_volatility": "Volatilitas pola pesan",
        "response_delay_mean": "Rata-rata waktu respons admin",
    }
}

# Save artifacts
joblib.dump(xgb_model, f"{SAVE_DIR}/churn_model.joblib")
joblib.dump(explainer, f"{SAVE_DIR}/shap_explainer.joblib")
joblib.dump(imputer, f"{SAVE_DIR}/imputer.joblib")

with open(f"{SAVE_DIR}/feature_metadata.json", 'w') as f:
    json.dump(feature_metadata, f, indent=2)

print("✅ Model artifacts saved:")
print(f"  📦 Model: {SAVE_DIR}/churn_model.joblib")
print(f"  🔍 SHAP: {SAVE_DIR}/shap_explainer.joblib")
print(f"  📋 Metadata: {SAVE_DIR}/feature_metadata.json")
print(f"  🔧 Imputer: {SAVE_DIR}/imputer.joblib")
print(f"\n🔐 Model hash: {model_hash}")
print(f"🔐 Schema hash: {get_feature_schema_hash()}")
```

---

## Summary

Dengan training guide v3 ini:
1. ✅ **Label temporal** — fitur dari masa lalu, label dari masa depan
2. ✅ **Smoothed trends** — frequency_trend_smoothed, spend_trend_smoothed, msg_trend_smoothed
3. ✅ **Magnitude features** — activity_mean, recent_activity_avg
4. ✅ **Volatility features** — activity_std, activity_cv, spend_volatility_cv
5. ✅ **Interaction feature** — trend_magnitude_interaction
6. ✅ **Sentiment features** — avg_sentiment_score, sentiment_trend
7. ✅ **Time-based split** — train pada data awal, test pada data akhir
8. ✅ **Imputation setelah split** — fit pada training saja
9. ✅ **Pre-modeling EDA** — distribusi, korelasi, redundancy check
10. ✅ **Ablation tests** — validasi model bukan rule approximator
11. ✅ **20 features** sesuai FEATURE_SCHEMA v3.0.0
