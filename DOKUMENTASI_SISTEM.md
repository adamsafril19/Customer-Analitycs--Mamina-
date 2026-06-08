# 📘 Dokumentasi Sistem Prediksi Customer Churn - Mamina Baby Spa

## 📋 Daftar Isi

1. [Gambaran Umum Sistem](#1-gambaran-umum-sistem)
2. [Arsitektur Sistem](#2-arsitektur-sistem)
3. [Diagram Alur Data](#3-diagram-alur-data)
4. [Komponen Utama](#4-komponen-utama)
5. [Feature Engineering v3](#5-feature-engineering-v3)
6. [Alur Data Detail](#6-alur-data-detail)
7. [Struktur Database](#7-struktur-database)
8. [API Endpoints](#8-api-endpoints)
9. [Alur Proses Bisnis](#9-alur-proses-bisnis)

---

## 1. Gambaran Umum Sistem

Sistem ini adalah aplikasi **Behavioral Risk Scoring** untuk **Mamina Baby Spa & Pijat Laktasi**. Sistem menggunakan Machine Learning untuk memprediksi risiko disengagement customer berdasarkan **3 dimensi perilaku**: trend, magnitude, dan volatility.

### Fitur Utama:

- ✅ Prediksi risiko disengagement menggunakan XGBoost (20 features, v3.0.0)
- ✅ Smoothed trend features (SMA/EMA) untuk mengurangi noise
- ✅ Magnitude & volatility features untuk konteks aktivitas
- ✅ Interaction feature (trend × magnitude) untuk menangkap penurunan pada user aktif
- ✅ Explainability dengan SHAP values
- ✅ Temporal proxy labels (fitur dari masa lalu, label dari masa depan)
- ✅ ETL data dari WhatsApp chat logs
- ✅ Dashboard real-time untuk monitoring
- ✅ Configurable feature parameters via `FeatureConfig`

### Design Principles (Feature Engineering):

| Dimensi | Deskripsi | Contoh Feature |
|---|---|---|
| **Trend** | Arah perubahan aktivitas (smoothed) | `frequency_trend_smoothed`, `spend_trend_smoothed` |
| **Magnitude** | Tingkat aktivitas absolut & relatif | `activity_mean`, `recent_activity_avg` |
| **Volatility** | Stabilitas/konsistensi aktivitas | `activity_cv`, `spend_volatility_cv` |
| **Interaction** | Kombinasi trend × magnitude | `trend_magnitude_interaction` |

---

## 2. Arsitektur Sistem

### 2.1 Arsitektur High-Level

```mermaid
flowchart TB
    subgraph CLIENT["🖥️ CLIENT LAYER"]
        FE["React Frontend<br/>(Dashboard)"]
    end

    subgraph PROXY["🔀 PROXY LAYER"]
        NGINX["NGINX<br/>Reverse Proxy"]
    end

    subgraph API["⚙️ API LAYER"]
        FLASK["Flask API<br/>(Inference Only)"]

        subgraph SERVICES["Services"]
            ML["ML Service"]
            FEATURE["Feature Service v3"]
            FCONFIG["Feature Config"]
            ETL["ETL Service"]
            LINK["Linking Service"]
            EXPLAINER["Explainer Service"]
            SEMANTIC["Semantic Service"]
            SENTIMENT["Sentiment Service"]
            TOPIC["Topic Service"]
            EMBED["Embedding Service"]
            MSGFEAT["Message Feature Service"]
        end
    end

    subgraph DATA["💾 DATA LAYER"]
        PG[("PostgreSQL<br/>+ pgvector")]
        REDIS[("Redis<br/>Cache & Queue")]
    end

    subgraph WORKER["👷 WORKER LAYER"]
        CELERY["Celery Workers"]
    end

    subgraph ML_ARTIFACTS["🤖 ML ARTIFACTS"]
        MODEL["churn_model.joblib"]
        IMPUTER["imputer.joblib"]
        FEATURES_JSON["feature_metadata.json"]
        SHAP["shap_explainer.joblib"]
    end

    FE --> NGINX
    NGINX --> FLASK
    FLASK --> SERVICES
    FLASK --> PG
    FLASK --> REDIS
    REDIS --> CELERY
    CELERY --> PG
    FCONFIG -->|inject| FEATURE
    FEATURE -->|20 features| ML
    ML --> MODEL
    ML --> IMPUTER
    ML --> FEATURES_JSON
    EXPLAINER --> SHAP
```

### 2.2 Tech Stack

| Layer           | Teknologi                              |
| --------------- | -------------------------------------- |
| Frontend        | React 18, Tailwind CSS, Vite           |
| Backend         | Flask, SQLAlchemy, Flasgger            |
| Database        | PostgreSQL + pgvector                  |
| Cache/Queue     | Redis                                  |
| Background Jobs | Celery                                 |
| ML              | XGBoost, SHAP, scikit-learn            |
| NLP             | IndoBERTweet (sentiment), MiniLM (embeddings) |
| Auth            | JWT (Flask-JWT-Extended)               |

---

## 3. Diagram Alur Data

### 3.1 Alur Data Utama (End-to-End)

```mermaid
flowchart TD
    classDef inputStyle fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#01579b
    classDef etlStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#e65100
    classDef featureStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#2e7d32
    classDef mlStyle fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#c2185b
    classDef outputStyle fill:#ede7f6,stroke:#512da8,stroke-width:2px,color:#512da8
    classDef dashStyle fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#1565c0

    subgraph INPUT["📥 INPUT DATA"]
        direction TB
        WA["📱 WhatsApp<br/>Chat Logs"]
        TX["💳 Data Transaksi<br/>POS/Manual"]
        CUST["👤 Data Customer<br/>Profile"]
    end

    subgraph ETL["🔄 ETL & IDENTITY RESOLUTION"]
        direction TB
        PARSE["📝 Parse WhatsApp Format"]
        RAW["📦 FeedbackRaw<br/>phone_number"]
        LINKING["🔗 Identity Resolution<br/>LinkingService"]
        LINKED["✅ FeedbackLinked<br/>customer_id + link_status"]

        PARSE --> RAW
        RAW --> LINKING
        LINKING --> LINKED
    end

    subgraph FEATURE["📊 FEATURE ENGINEERING v3"]
        direction TB
        CONFIG["⚙️ FeatureConfig<br/>SMA/EMA, windows, caps"]
        WINDOWED["📈 Windowed Series<br/>3×30d tx/spend/msg"]
        SMOOTH["🔧 Smoothing<br/>SMA or EMA"]
        NUMERIC["🔢 Trend + Context<br/>slope, recency, tx_count"]
        MAGNITUDE["📊 Magnitude<br/>activity_mean, recent"]
        VOLATILITY["📉 Volatility<br/>std, CV"]
        INTERACT["🔗 Interaction<br/>trend × magnitude"]
        TEXT["💬 NLP Signals<br/>sentiment, complaints"]

        CONFIG --> WINDOWED
        WINDOWED --> SMOOTH
        SMOOTH --> NUMERIC
        WINDOWED --> MAGNITUDE
        WINDOWED --> VOLATILITY
        NUMERIC --> INTERACT
        MAGNITUDE --> INTERACT
    end

    subgraph ML["🤖 ML INFERENCE"]
        direction TB
        VERIFY["🔐 Identity Enforcement<br/>verified feedback only"]
        VECTOR["📋 Build Feature Vector<br/>20 Features (schema-ordered)"]
        VALIDATE["✅ Schema Validation<br/>hash + count check"]
        PREDICT["⚡ XGBoost Prediction"]
        SHAPEX["🔍 SHAP Explanation"]

        VERIFY --> VECTOR
        VECTOR --> VALIDATE
        VALIDATE --> PREDICT
        PREDICT --> SHAPEX
    end

    subgraph OUTPUT["📤 PREDICTION OUTPUT"]
        direction LR
        SCORE["🎯 Risk Score<br/>0.0 - 1.0"]
        LABEL["🏷️ Risk Label<br/>Low / Medium / High"]
        REASONS["📖 Top Reasons<br/>SHAP-based"]
        PROVENANCE["🔐 Provenance<br/>model_hash, schema_hash"]
    end

    subgraph DASHBOARD["📱 DASHBOARD DISPLAY"]
        direction LR
        DISPLAY["📋 Customer List<br/>with Risk Level"]
        TREND["📈 Trend<br/>Visualization"]
    end

    WA --> PARSE
    TX --> CUST
    CUST --> LINKING

    LINKED --> NUMERIC
    LINKED --> TEXT
    TX --> WINDOWED

    NUMERIC --> VECTOR
    MAGNITUDE --> VECTOR
    VOLATILITY --> VECTOR
    INTERACT --> VECTOR
    TEXT --> VECTOR

    SHAPEX --> SCORE
    SHAPEX --> LABEL
    SHAPEX --> REASONS
    SHAPEX --> PROVENANCE

    SCORE --> DISPLAY
    LABEL --> DISPLAY
    REASONS --> DISPLAY
    SCORE --> TREND

    class WA,TX,CUST inputStyle
    class PARSE,RAW,LINKING,LINKED etlStyle
    class CONFIG,WINDOWED,SMOOTH,NUMERIC,MAGNITUDE,VOLATILITY,INTERACT,TEXT featureStyle
    class VERIFY,VECTOR,VALIDATE,PREDICT,SHAPEX mlStyle
    class SCORE,LABEL,REASONS,PROVENANCE outputStyle
    class DISPLAY,TREND dashStyle
```

### 3.2 Alur ETL WhatsApp

```mermaid
sequenceDiagram
    participant Admin
    participant API as Flask API
    participant ETL as ETL Service
    participant LS as Linking Service
    participant DB as PostgreSQL

    Admin->>API: Upload WhatsApp Export (.txt)
    API->>ETL: process_whatsapp_export()

    loop For Each Message
        ETL->>ETL: Parse [DD/MM/YY, HH:MM:SS] Sender: Message
        ETL->>ETL: Hash phone number
        ETL->>DB: Insert FeedbackRaw (phone_number)
    end

    ETL->>API: Return stats (new/duplicate)
    API->>LS: link_unlinked_messages()

    loop For Each Unlinked Message
        LS->>DB: Find Customer by phone_hash
        alt Customer Found
            LS->>DB: Create FeedbackLinked (confidence=1.0)
        else Customer Not Found
            LS->>DB: Create Provisional Customer
            LS->>DB: Create FeedbackLinked (confidence=0.6)
        end
    end

    LS->>API: Return linking stats
    API->>Admin: Success Response
```

### 3.3 Alur Prediksi (v3 — Trust Boundary)

```mermaid
sequenceDiagram
    participant User
    participant API as Flask API
    participant ML as ML Service
    participant FS as Feature Service v3
    participant FC as FeatureConfig
    participant EX as Explainer Service
    participant DB as PostgreSQL

    User->>API: POST /predict/customer/{id}
    API->>ML: predict_for_customer(id)

    Note over ML: SINGLE TRUST BOUNDARY

    ML->>FS: build_verified_features(id)
    FS->>FC: Load config (smoothing, windows, caps)
    FS->>DB: Check verified feedback count > 0
    FS->>DB: Query transactions (3 windows × 30d)
    FS->>FS: Compute windowed series
    FS->>FS: Apply smoothing (SMA/EMA)
    FS->>FS: Compute trend slopes
    FS->>FS: Compute magnitude features
    FS->>FS: Compute volatility features
    FS->>FS: Compute interaction feature
    FS->>DB: Query NLP signals (verified only)
    FS-->>ML: {features: [20 values], schema_hash, ...}

    ML->>ML: Validate schema hash (cross-service)
    ML->>ML: Validate feature count == 20
    ML->>ML: XGBoost.predict_proba()
    ML-->>API: {score, label, provenance}

    API->>DB: Save ChurnPrediction
    API->>EX: compute_and_cache_shap() (async/Celery)
    EX->>EX: SHAP TreeExplainer
    EX->>DB: Save ShapCache

    API-->>User: Prediction Response + Provenance
```

### 3.4 Alur Feature Engineering v3

```mermaid
flowchart LR
    subgraph RAW_DATA["Raw Data Sources"]
        TX[("transactions")]
        MSG[("feedback_linked<br/>(verified only)")]
        SEM[("customer_text_semantics")]
    end

    subgraph CONFIG["⚙️ Configuration"]
        FC["FeatureConfig<br/>smoothing_method: sma/ema<br/>smoothing_window: 3<br/>activity_windows: 3<br/>window_size_days: 30<br/>cv_cap: 10.0"]
    end

    subgraph WINDOWED["Windowed Series (3×30d)"]
        W1["Window 1 (oldest)"]
        W2["Window 2"]
        W3["Window 3 (newest)"]
    end

    subgraph SMOOTHING["Smoothing Engine"]
        SMA["SMA (default)"]
        EMA["EMA (optional)"]
    end

    subgraph FEATURES["20 Feature Vector (ordered)"]
        direction TB
        subgraph TREND["Trend (5)"]
            F1["recency_ratio"]
            F2["frequency_trend_smoothed"]
            F3["spend_trend_smoothed"]
            F4["msg_trend_smoothed"]
            F5["sentiment_trend"]
        end
        subgraph CONTEXT["Context (5)"]
            F6["recency_days"]
            F7["tx_count_90d"]
            F8["spend_90d"]
            F9["avg_tx_value"]
            F10["tenure_days"]
        end
        subgraph MAGNITUDE["Magnitude (2)"]
            F11["activity_mean"]
            F12["recent_activity_avg"]
        end
        subgraph VOLATILITY["Volatility (3)"]
            F13["activity_std"]
            F14["activity_cv"]
            F15["spend_volatility_cv"]
        end
        subgraph INTERACTION["Interaction (1)"]
            F16["trend_magnitude_interaction"]
        end
        subgraph NLP["NLP (4)"]
            F17["avg_sentiment_score"]
            F18["complaint_ratio"]
            F19["msg_volatility"]
            F20["response_delay_mean"]
        end
    end

    TX --> WINDOWED
    FC --> WINDOWED
    WINDOWED --> SMOOTHING
    SMOOTHING --> TREND
    WINDOWED --> MAGNITUDE
    WINDOWED --> VOLATILITY
    TREND --> INTERACTION
    MAGNITUDE --> INTERACTION
    MSG --> NLP
    SEM --> TREND
    TX --> CONTEXT
```

---

## 4. Komponen Utama

### 4.1 Backend Services

```mermaid
classDiagram
    class FeatureConfig {
        <<dataclass, frozen>>
        +smoothing_method: str = "sma"
        +smoothing_window: int = 3
        +ema_alpha: float = None
        +activity_windows: int = 3
        +window_size_days: int = 30
        +min_activity_threshold: float = 0.01
        +cv_cap: float = 10.0
        +ratio_cap: float = 10.0
        +from_dict(d) FeatureConfig
        +get_ema_alpha() float
        +to_dict() dict
    }

    class FeatureService {
        <<v3.0.0>>
        +FEATURE_SCHEMA: list (20 features)
        +config: FeatureConfig
        +populate_numeric_features()
        +populate_text_signals()
        +get_ml_feature_vector() list
        +build_verified_features() dict
        +get_feature_schema_hash() str
        -_apply_smoothing() list
        -_apply_sma() list
        -_apply_ema() list
        -_compute_windowed_series() list
        -_compute_trend_slope() float
        -_compute_magnitude_features() dict
        -_compute_volatility_features() dict
    }

    class MLService {
        <<singleton>>
        -model: XGBoostClassifier
        -feature_metadata: dict
        -shap_explainer: TreeExplainer
        -model_hash: str
        -feature_schema_hash: str
        +predict_for_customer(id) dict
        +load_all_models()
        +get_model_identity() dict
        -_predict_raw(features) tuple
        -_validate_against_registry() bool
    }

    class ETLService {
        +WA_PATTERN: regex
        +process_whatsapp_export() dict
        -_parse_messages() list
        -_store_raw_message() str
    }

    class LinkingService {
        +link_unlinked_messages() dict
        +link_message() tuple
    }

    class ExplainerService {
        +calculate_shap_values() ndarray
        +get_top_reasons() list
        +get_nearest_messages() list
        +compute_and_cache_shap() ShapCache
    }

    class SemanticService {
        +populate_text_semantics()
        -sentiment_service: SentimentService
        -topic_service: TopicService
    }

    class SentimentService {
        +predict(text) tuple
        +is_model_loaded() bool
        +load_model()
    }

    class EmbeddingService {
        +get_embedding(text) list
        +compute_similarity() float
    }

    FeatureConfig --> FeatureService : configures
    MLService --> FeatureService : builds features via
    ExplainerService --> MLService : uses model
    FeatureService --> LinkingService : uses verified links
    ETLService --> LinkingService : triggers
    SemanticService --> SentimentService : uses
    SemanticService --> LinkingService : uses linked data
```

### 4.2 File Struktur Services

| File | Service | Deskripsi |
|---|---|---|
| `feature_config.py` | `FeatureConfig` | Structured config (frozen dataclass) untuk parameter feature engineering |
| `feature_service.py` | `FeatureService` | **Core**: Feature engineering v3 — smoothing, trend, magnitude, volatility |
| `ml_service.py` | `MLService` | Model loading, inference, provenance tracking (singleton) |
| `explainer_service.py` | `ExplainerService` | SHAP explanation + nearest message drilldown |
| `etl_service.py` | `ETLService` | WhatsApp chat log parsing & ingestion |
| `linking_service.py` | `LinkingService` | Identity resolution (phone → customer) |
| `semantic_service.py` | `SemanticService` | Orchestrator untuk sentiment & topic analysis |
| `sentiment_service.py` | `SentimentService` | IndoBERTweet sentiment analysis |
| `topic_service.py` | `TopicService` | Topic modeling |
| `embedding_service.py` | `EmbeddingService` | MiniLM text embeddings |
| `message_feature_service.py` | `MessageFeatureService` | Per-message feature extraction |

### 4.3 Scripts

| File | Deskripsi |
|---|---|
| `scripts/train_model.py` | Training script (v3 schema, 20 features) |
| `scripts/validate_features.py` | Feature validation / EDA utility |
| `scripts/seed_data.py` | Database seeding |
| `scripts/check_db.py` | Database health check |
| `scripts/verify_tables.py` | Table verification |

### 4.4 Notebooks & Dokumentasi

| File | Deskripsi |
|---|---|
| `notebooks/01_churn_model_training.ipynb` | Jupyter notebook untuk training model |
| `notebooks/TRAINING_NOTEBOOK_UPDATE_GUIDE.md` | Panduan cell-by-cell untuk training v3 |
| `notebooks/FEATURE_DOCUMENTATION_V3.md` | Dokumentasi lengkap per-feature (definisi, meaning, edge cases) |

### 4.5 Database Models

```mermaid
erDiagram
    CUSTOMERS ||--o{ TRANSACTIONS : has
    CUSTOMERS ||--o{ FEEDBACK_LINKED : has
    CUSTOMERS ||--o{ CHURN_PREDICTIONS : has
    CUSTOMERS ||--o{ CUSTOMER_NUMERIC_FEATURES : has
    CUSTOMERS ||--o{ CUSTOMER_TEXT_SIGNALS : has
    CUSTOMERS ||--o{ CUSTOMER_TEXT_SEMANTICS : has

    FEEDBACK_RAW ||--o| FEEDBACK_LINKED : links_to
    FEEDBACK_LINKED ||--o| FEEDBACK_FEATURES : has

    CHURN_PREDICTIONS ||--o| SHAP_CACHE : has

    CUSTOMERS {
        uuid customer_id PK
        string external_id
        string name
        string phone_hash
        string city
        boolean consent_given
        boolean is_active
        boolean is_provisional
        datetime created_at
        datetime last_seen_at
    }

    TRANSACTIONS {
        uuid tx_id PK
        uuid customer_id FK
        float amount
        string service_type
        string status
        datetime tx_date
        datetime created_at
    }

    FEEDBACK_RAW {
        uuid msg_id PK
        string phone_number
        string direction
        text text
        datetime timestamp
    }

    FEEDBACK_LINKED {
        uuid link_id PK
        uuid msg_id FK
        uuid customer_id FK
        float match_confidence
        string match_method
        string link_status
        datetime linked_at
    }

    FEEDBACK_FEATURES {
        uuid feature_id PK
        uuid link_id FK
        uuid msg_id FK
        uuid customer_id FK
        integer msg_length
        integer num_exclamations
        integer num_questions
        boolean has_complaint
        boolean has_refund_request
        float language_confidence
        integer response_time_secs
        vector embedding
        string embedding_model_version
        datetime processed_at
    }

    CUSTOMER_NUMERIC_FEATURES {
        uuid feature_id PK
        uuid customer_id FK
        date as_of_date
        integer recency_days
        integer tx_count_30d
        integer tx_count_90d
        float spend_30d
        float spend_90d
        float avg_tx_value
        integer tenure_days
        float r_score
        float f_score
        float m_score
    }

    CUSTOMER_TEXT_SIGNALS {
        uuid id PK
        uuid customer_id FK
        date as_of_date
        integer msg_count_7d
        integer msg_count_30d
        float msg_volatility
        float avg_msg_length_30d
        float complaint_rate_30d
        float response_delay_mean
        vector avg_embedding
        integer embedding_count_30d
        datetime created_at
    }

    CUSTOMER_TEXT_SEMANTICS {
        uuid id PK
        uuid customer_id FK
        date as_of_date
        jsonb top_topic_counts
        float avg_topic_similarity
        string topic_model_version
        jsonb sentiment_dist
        float avg_sentiment_score
        string sentiment_model_version
        jsonb top_keywords
        jsonb top_complaint_types
        jsonb last_n_msg_ids
        datetime created_at
    }

    CHURN_PREDICTIONS {
        uuid pred_id PK
        uuid customer_id FK
        float churn_score
        string churn_label
        string model_version
        date as_of_date
        datetime created_at
        json features_used
        datetime feature_as_of
        string feature_schema_hash
        string model_hash
    }

    ML_MODEL_REGISTRY {
        uuid id PK
        string model_version
        string model_path
        string model_hash
        string feature_schema_hash
        string shap_explainer_hash
        boolean is_active
        json metrics
        datetime trained_at
    }
```

---

## 5. Feature Engineering v3

### 5.1 Feature Schema v3.0.0 (20 Features)

| # | Feature | Kategori | Formula | Behavioral Meaning |
|---|---|---|---|---|
| 1 | `recency_ratio` | Trend | recency_days / avg_ipt | Seberapa "telat" vs baseline personal |
| 2 | `frequency_trend_smoothed` | Trend | slope(SMA/EMA(tx_count per window)) | Arah perubahan frekuensi (de-noised) |
| 3 | `spend_trend_smoothed` | Trend | slope(SMA/EMA(spend per window)) | Arah perubahan belanja (de-noised) |
| 4 | `msg_trend_smoothed` | Trend | slope(SMA/EMA(msg_count per window)) | Arah perubahan komunikasi (de-noised) |
| 5 | `sentiment_trend` | Trend | sentiment_30d - sentiment_prior_30d | Perubahan sentimen |
| 6 | `recency_days` | Context | days since last tx | Absolute recency |
| 7 | `tx_count_90d` | Context | count(tx in 90d) | Absolute frekuensi |
| 8 | `spend_90d` | Context | sum(amount in 90d) | Absolute monetary |
| 9 | `avg_tx_value` | Context | spend_90d / tx_count_90d | Rata-rata belanja |
| 10 | `tenure_days` | Context | days since customer created | Lama jadi customer |
| 11 | `activity_mean` | Magnitude | mean(tx_count per window) | Tingkat aktivitas rata-rata |
| 12 | `recent_activity_avg` | Magnitude | tx_count di window terkini | Aktivitas terkini |
| 13 | `activity_std` | Volatility | std(tx_count per window) | Stabilitas frekuensi |
| 14 | `activity_cv` | Volatility | std/mean (capped, zero-safe) | Volatilitas relatif |
| 15 | `spend_volatility_cv` | Volatility | std(spend)/mean(spend) (capped) | Stabilitas belanja |
| 16 | `trend_magnitude_interaction` | Interaction | freq_trend_smoothed × activity_mean | Penurunan user aktif > user pasif |
| 17 | `avg_sentiment_score` | NLP | mean sentiment 30d | Sentimen rata-rata |
| 18 | `complaint_ratio` | NLP | complaint/total messages 30d | Rasio komplain |
| 19 | `msg_volatility` | NLP | std daily message count | Volatilitas pesan |
| 20 | `response_delay_mean` | NLP | mean admin response time | Waktu respon admin |

### 5.2 Smoothing

```mermaid
flowchart LR
    RAW["Raw Series<br/>[w1, w2, w3]<br/>oldest → newest"] --> METHOD{Smoothing Method}
    METHOD -->|SMA| SMA["Simple Moving Average<br/>SMA_t = mean(series[t-w+1:t+1])"]
    METHOD -->|EMA| EMA["Exponential Moving Average<br/>EMA_t = α·x_t + (1-α)·EMA_{t-1}"]
    SMA --> SLOPE["Linear Regression Slope<br/>slope = cov(t,y) / var(t)"]
    EMA --> SLOPE
    SLOPE --> FEATURE["trend_smoothed feature"]
```

- **SMA** (default): Stabil, interpretable, bobot sama ke semua observasi
- **EMA** (optional): Lebih responsif terhadap perubahan terbaru

### 5.3 Configurable Parameters

| Parameter | Default | Deskripsi |
|---|---|---|
| `smoothing_method` | `"sma"` | Metode smoothing: `"sma"` atau `"ema"` |
| `smoothing_window` | `3` | Window size untuk SMA / span untuk EMA |
| `ema_alpha` | `None` (auto) | Alpha EMA. Jika None, dihitung = `2/(window+1)` |
| `activity_windows` | `3` | Jumlah window historis (×30d) |
| `window_size_days` | `30` | Ukuran setiap window (hari) |
| `min_activity_threshold` | `0.01` | Floor untuk denominator CV |
| `cv_cap` | `10.0` | Cap untuk coefficient of variation |
| `ratio_cap` | `10.0` | Cap untuk safe ratio |

**Penggunaan:**
```python
# Default (production)
svc = FeatureService()

# Eksperimen
svc = FeatureService(config=FeatureConfig(smoothing_method='ema', smoothing_window=5))

# Dari Flask config
config = FeatureConfig.from_dict(app.config.get('FEATURE_CONFIG', {}))
svc = FeatureService(config=config)
```

### 5.4 Edge Case Handling

| Situasi | Penanganan |
|---|---|
| Customer tanpa transaksi | `recency_days = 999`, series = [0,0,0], trend = 0 |
| Customer dengan 1 transaksi | `avg_ipt = 0` → `recency_ratio` = cap (10.0) |
| `activity_mean` ≈ 0 (dormant) | `activity_cv = 0.0` (bukan infinite — dormant ≠ volatile) |
| Division by zero pada CV | Jika mean < `min_activity_threshold` → CV = 0.0 |
| Tidak ada verified feedback | `PermissionError` — ML requires verified identity |
| Smoothed series length < 2 | slope = 0.0 |

### 5.5 Catatan tentang `activity_total`

`activity_total` (sum dari 3 windows × 30d) **TIDAK ditambahkan** karena secara semantik identik dengan `tx_count_90d` (3×30d = 90d). Menambahkannya akan redundan tanpa informasi baru.

---

## 6. Alur Data Detail

### 6.1 Data Flow Layers

```mermaid
flowchart TB
    subgraph L1["Layer 1: Raw Data"]
        direction LR
        R1["WhatsApp Export"]
        R2["Transaction CSV"]
        R3["Customer Import"]
    end

    subgraph L2["Layer 2: Staging"]
        direction LR
        S1["feedback_raw<br/>(no identity)"]
        S2["transactions"]
        S3["customers"]
    end

    subgraph L3["Layer 3: Identity Resolution"]
        direction LR
        I1["feedback_linked<br/>(customer_id + link_status)"]
    end

    subgraph L4["Layer 4: Feature Tables"]
        direction LR
        F1["customer_numeric_features"]
        F2["customer_text_signals"]
        F3["customer_text_semantics<br/>(dashboard + sentiment)"]
        F4["feedback_features<br/>(per-message signals)"]
    end

    subgraph L5["Layer 5: ML Output"]
        direction LR
        M1["churn_predictions<br/>(+ provenance)"]
        M2["shap_cache"]
        M3["ml_model_registry"]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
```

### 6.2 Identity Resolution Flow

```mermaid
flowchart TD
    START["FeedbackRaw<br/>(phone_number only)"]

    CHECK{"Customer with<br/>matching phone_hash?"}

    subgraph FOUND["Customer Found"]
        PROV{"Is Provisional?"}
        REAL["Real Customer<br/>confidence=1.0<br/>status=probable"]
        GHOST["Provisional Customer<br/>confidence=0.6<br/>status=provisional"]
    end

    subgraph NOT_FOUND["Customer Not Found"]
        CREATE["Create Provisional<br/>Customer"]
        NEW["New Link<br/>confidence=0.6<br/>status=provisional"]
    end

    RESULT["FeedbackLinked<br/>(customer_id assigned)"]

    START --> CHECK
    CHECK -->|Yes| PROV
    CHECK -->|No| CREATE
    PROV -->|No| REAL
    PROV -->|Yes| GHOST
    CREATE --> NEW
    REAL --> RESULT
    GHOST --> RESULT
    NEW --> RESULT
```

### 6.3 ML Pipeline Flow

```mermaid
flowchart LR
    subgraph TRAINING["🎓 Training (Jupyter Notebook)"]
        T1["Generate Temporal<br/>Proxy Labels"]
        T2["Windowed Feature<br/>Engineering (3×30d)"]
        T3["Smoothing +<br/>Trend/Mag/Vol"]
        T4["Time-Based Split<br/>(NOT random)"]
        T5["Train XGBoost +<br/>Ablation Tests"]
        T6["Export Artifacts"]
    end

    subgraph ARTIFACTS["📦 Model Artifacts"]
        A1["churn_model.joblib"]
        A2["imputer.joblib"]
        A3["feature_metadata.json<br/>(schema, config, descriptions)"]
        A4["shap_explainer.joblib"]
    end

    subgraph INFERENCE["⚡ Inference (Flask)"]
        I1["Load Model<br/>+ Validate Registry"]
        I2["Build Verified<br/>Features (20)"]
        I3["Schema Hash<br/>Validation"]
        I4["Predict +<br/>Provenance"]
        I5["SHAP Explain<br/>(async)"]
    end

    T6 --> A1
    T6 --> A2
    T6 --> A3
    T6 --> A4

    A1 --> I1
    A2 --> I1
    A3 --> I1
    A4 --> I1

    I1 --> I2
    I2 --> I3
    I3 --> I4
    I4 --> I5
```

### 6.4 Training: Temporal Proxy Label

```mermaid
flowchart LR
    subgraph PAST["⬅️ Feature Window<br/>[obs_date - 90, obs_date]"]
        FW["Fitur dihitung<br/>dari data MASA LALU"]
    end

    OBS["📅 observation_date"]

    subgraph FUTURE["➡️ Label Window<br/>[obs_date, obs_date + 90]"]
        LW["Label ditentukan<br/>dari data MASA DEPAN"]
    end

    PAST --> OBS
    OBS --> FUTURE
```

**Key Principle**: Fitur dan label menggunakan window yang **TIDAK overlap**, mencegah data leakage.

---

## 7. Struktur Database

### 7.1 Schema Overview

```mermaid
graph TB
    subgraph CORE["Core Entities"]
        C[customers]
        T[transactions]
        U[users]
    end

    subgraph FEEDBACK["Feedback Pipeline"]
        FR[feedback_raw]
        FL[feedback_linked]
        FF[feedback_features]
    end

    subgraph FEATURES["Feature Store"]
        NF[customer_numeric_features]
        TS[customer_text_signals]
        SE[customer_text_semantics]
    end

    subgraph ML_OUTPUT["ML Output"]
        CP[churn_predictions]
        SC[shap_cache]
        MR[ml_model_registry]
    end

    C --> T
    C --> FR
    FR --> FL
    FL --> FF
    C --> NF
    C --> TS
    C --> SE
    C --> CP
    CP --> SC
```

### 7.2 Tabel Utama

| Tabel | Deskripsi | Layer |
|---|---|---|
| `customers` | Data profil customer | Core |
| `transactions` | Riwayat transaksi (amount, status, tx_date) | Core |
| `users` | Admin/user akun untuk login | Core |
| `feedback_raw` | Pesan WhatsApp mentah (phone_number) | Staging |
| `feedback_linked` | Pesan yang sudah di-link ke customer (link_status) | Identity |
| `feedback_features` | Per-message ML features (complaint, sentiment, embedding) | Feature |
| `customer_numeric_features` | Base transaction signals (recency, tx_count, spend, RFM) | Feature |
| `customer_text_signals` | Text behavior signals (msg count, volatility, complaint rate) | Feature |
| `customer_text_semantics` | Semantic features (sentiment score, topic) — untuk dashboard | Display |
| `churn_predictions` | Hasil prediksi + provenance (model_hash, schema_hash) | ML Output |
| `shap_cache` | Cache SHAP values + nearest messages | ML Output |
| `ml_model_registry` | Registry model aktif (hash, metrics, version) | ML Output |

---

## 8. API Endpoints

### 8.1 Endpoint Overview

```mermaid
flowchart LR
    subgraph AUTH["🔐 Auth"]
        A1["/api/auth/login"]
        A2["/api/auth/register"]
    end

    subgraph CUSTOMERS["👥 Customers"]
        C1["/api/customers"]
        C2["/api/customers/{id}"]
        C3["/api/customers/{id}/features"]
    end

    subgraph PREDICTIONS["🎯 Predictions"]
        P1["/api/predict/customer/{id}"]
        P2["/api/predict/batch"]
        P3["/api/predictions"]
    end

    subgraph DASHBOARD["📊 Dashboard"]
        D1["/api/dashboard/stats"]
        D2["/api/dashboard/trend"]
        D3["/api/dashboard/drivers"]
    end

    subgraph ADMIN["🔧 Admin"]
        AD1["/api/admin/etl/upload"]
        AD2["/api/admin/features/refresh"]
        AD3["/api/admin/model/status"]
    end

    subgraph HEALTH["💚 Health"]
        H1["/api/health"]
    end
```

### 8.2 Endpoint Details

| Method | Endpoint | Deskripsi |
|---|---|---|
| POST | `/api/auth/login` | Login user |
| POST | `/api/auth/register` | Register admin user |
| GET | `/api/customers` | List semua customer (paginated) |
| GET | `/api/customers/{id}` | Detail customer |
| GET | `/api/customers/{id}/features` | Feature vector customer |
| POST | `/api/predict/customer/{id}` | Prediksi satu customer (trust boundary) |
| POST | `/api/predict/batch` | Prediksi batch |
| GET | `/api/predictions` | List prediksi (paginated) |
| GET | `/api/dashboard/stats` | Statistik dashboard |
| GET | `/api/dashboard/trend` | Trend churn over time |
| GET | `/api/dashboard/drivers` | Top churn drivers |
| POST | `/api/admin/etl/upload` | Upload WhatsApp export |
| POST | `/api/admin/features/refresh` | Refresh features untuk customer |
| GET | `/api/admin/model/status` | Model status & identity |
| GET | `/api/health` | Health check |

---

## 9. Alur Proses Bisnis

### 9.1 Workflow Pengguna

```mermaid
flowchart TD
    START(["Admin Login"])

    UPLOAD["Upload WhatsApp<br/>Export"]

    ETL_PROCESS["Sistem proses ETL<br/>& Identity Resolution"]

    PREDICT["Jalankan Batch<br/>Prediction"]

    VIEW_DASH["Lihat Dashboard<br/>Overview"]

    CHECK_RISK{"Ada High Risk<br/>Customer?"}

    VIEW_DETAIL["Lihat Detail<br/>Customer"]

    UNDERSTAND["Pahami alasan<br/>(SHAP Explanation +<br/>Nearest Messages)"]

    ACTION["Ambil Tindakan<br/>(Follow-up, Promo, dll.)"]

    END(["Selesai"])

    START --> VIEW_DASH
    UPLOAD --> ETL_PROCESS
    ETL_PROCESS --> PREDICT
    PREDICT --> VIEW_DASH
    VIEW_DASH --> CHECK_RISK
    CHECK_RISK -->|Ya| VIEW_DETAIL
    CHECK_RISK -->|Tidak| END
    VIEW_DETAIL --> UNDERSTAND
    UNDERSTAND --> ACTION
    ACTION --> END
```

---

## 📝 Catatan Penting

### Separation of Concerns

1. **Training** dilakukan di **Jupyter Notebook** (terpisah, temporal proxy labels)
2. **Inference** dilakukan di **Flask Backend** (single trust boundary via `predict_for_customer`)
3. **Dashboard** adalah **React Frontend**
4. **Feature config** terstruktur via `FeatureConfig` dataclass (bukan .env)

### Data Privacy

- Phone number di-hash sebelum disimpan
- Customer data bisa di-mask untuk display
- Consent tracking tersedia

### Model Versioning & Provenance

- Model artifacts memiliki hash untuk tracking
- Registry mencatat model aktif (`ml_model_registry`)
- Feature schema di-validate saat load (cross-service hash check)
- Setiap prediksi menyimpan **provenance**: model_hash, schema_hash, features_used, predicted_at
- SHAP explanations terikat ke model version tertentu

### Trust Boundary

- ML inference hanya melalui `MLService.predict_for_customer()`
- Features dibangun internally oleh `FeatureService.build_verified_features()` (pure, no side effects)
- Hanya data dari **verified** feedback links yang digunakan untuk ML
- External feature injection **dilarang** (method deprecated)

### Feature Engineering Principles

- Semua trend features menggunakan **smoothing** (SMA/EMA) untuk mengurangi noise
- **Interaction feature** menangkap bahwa penurunan pada user aktif lebih signifikan
- **CV (Coefficient of Variation)** menormalisasi volatilitas terhadap activity level
- User dormant (activity ≈ 0) → CV = 0, bukan infinite (dormant ≠ volatile)

---

_Dokumentasi ini terakhir diperbarui: April 2026_
_Versi Sistem: v3.0.0_
_Feature Schema: 20 features (Trend + Context + Magnitude + Volatility + Interaction + NLP)_
