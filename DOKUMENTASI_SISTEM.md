# 📘 Dokumentasi Sistem Prediksi Customer Churn - Mamina Baby Spa

## 📋 Daftar Isi

1. [Gambaran Umum Sistem](#1-gambaran-umum-sistem)
2. [Arsitektur Sistem](#2-arsitektur-sistem)
3. [Diagram Alur Data](#3-diagram-alur-data)
4. [Komponen Utama](#4-komponen-utama)
5. [Alur Data Detail](#5-alur-data-detail)
6. [Struktur Database](#6-struktur-database)
7. [API Endpoints](#7-api-endpoints)
8. [Alur Proses Bisnis](#8-alur-proses-bisnis)

---

## 1. Gambaran Umum Sistem

Sistem ini adalah aplikasi **Customer Churn Prediction** untuk **Mamina Baby Spa & Pijat Laktasi**. Sistem menggunakan Machine Learning untuk memprediksi kemungkinan customer berhenti menggunakan layanan (churn).

### Fitur Utama:

- ✅ Prediksi risiko churn customer menggunakan XGBoost
- ✅ Explainability dengan SHAP values
- ✅ ETL data dari WhatsApp chat logs
- ✅ Dashboard real-time untuk monitoring

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
            FEATURE["Feature Service"]
            ETL["ETL Service"]
            LINK["Linking Service"]
            EXPLAINER["Explainer Service"]
            SEMANTIC["Semantic Service"]
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
        MODEL["churn_model.pkl"]
        SCALER["scaler.pkl"]
        SHAP["shap_explainer.pkl"]
    end

    FE --> NGINX
    NGINX --> FLASK
    FLASK --> SERVICES
    FLASK --> PG
    FLASK --> REDIS
    REDIS --> CELERY
    CELERY --> PG
    ML --> MODEL
    ML --> SCALER
    EXPLAINER --> SHAP
```

### 2.2 Tech Stack

| Layer           | Teknologi                    |
| --------------- | ---------------------------- |
| Frontend        | React 18, Tailwind CSS, Vite |
| Backend         | Flask, SQLAlchemy, Flasgger  |
| Database        | PostgreSQL + pgvector        |
| Cache/Queue     | Redis                        |
| Background Jobs | Celery                       |
| ML              | XGBoost, SHAP, scikit-learn  |
| Auth            | JWT (Flask-JWT-Extended)     |

---

## 3. Diagram Alur Data

### 3.1 Alur Data Utama (End-to-End)

```mermaid
flowchart TD
    %% Styling
    classDef inputStyle fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#01579b
    classDef etlStyle fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#e65100
    classDef featureStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#2e7d32
    classDef mlStyle fill:#fce4ec,stroke:#c2185b,stroke-width:2px,color:#c2185b
    classDef outputStyle fill:#ede7f6,stroke:#512da8,stroke-width:2px,color:#512da8
    classDef dashStyle fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#1565c0

    %% INPUT DATA
    subgraph INPUT["📥 INPUT DATA"]
        direction TB
        WA["📱 WhatsApp<br/>Chat Logs"]
        TX["💳 Data Transaksi<br/>POS/Manual"]
        CUST["👤 Data Customer<br/>Profile"]
    end

    %% ETL LAYER
    subgraph ETL["🔄 ETL & IDENTITY RESOLUTION"]
        direction TB
        PARSE["📝 Parse WhatsApp Format"]
        RAW["📦 FeedbackRaw<br/>phone_number"]
        LINKING["🔗 Identity Resolution<br/>LinkingService"]
        LINKED["✅ FeedbackLinked<br/>customer_id"]

        PARSE --> RAW
        RAW --> LINKING
        LINKING --> LINKED
    end

    %% FEATURE ENGINEERING
    subgraph FEATURE["📊 FEATURE ENGINEERING"]
        direction TB
        NUMERIC["🔢 Numeric Features<br/>RFM, Transaction Stats"]
        TEXT["💬 Text Signals<br/>Complaint Rate, Msg Count"]
        SEMANTIC["🧠 Text Semantics<br/>Sentiment, Topic"]
    end

    %% ML INFERENCE
    subgraph ML["🤖 ML INFERENCE"]
        direction TB
        VECTOR["📋 Build Feature Vector<br/>13 Features"]
        PREDICT["⚡ XGBoost Prediction"]
        SHAPEX["🔍 SHAP Explanation"]

        VECTOR --> PREDICT
        PREDICT --> SHAPEX
    end

    %% OUTPUT
    subgraph OUTPUT["📤 PREDICTION OUTPUT"]
        direction LR
        SCORE["🎯 Churn Score<br/>0.0 - 1.0"]
        LABEL["🏷️ Risk Label<br/>Low / Medium / High"]
        REASONS["📖 Top Reasons<br/>SHAP-based"]
    end

    %% DASHBOARD
    subgraph DASHBOARD["📱 DASHBOARD DISPLAY"]
        direction LR
        DISPLAY["📋 Customer List<br/>with Risk Level"]
        TREND["📈 Trend<br/>Visualization"]
    end

    %% Connections - Input to ETL
    WA --> PARSE
    TX --> CUST
    CUST --> LINKING

    %% Connections - ETL to Features
    LINKED --> NUMERIC
    LINKED --> TEXT
    LINKED --> SEMANTIC
    TX --> NUMERIC

    %% Connections - Features to ML
    NUMERIC --> VECTOR
    TEXT --> VECTOR

    %% Connections - ML to Output
    SHAPEX --> SCORE
    SHAPEX --> LABEL
    SHAPEX --> REASONS

    %% Connections - Output to Dashboard
    SCORE --> DISPLAY
    LABEL --> DISPLAY
    REASONS --> DISPLAY
    SCORE --> TREND

    %% Apply styles
    class WA,TX,CUST inputStyle
    class PARSE,RAW,LINKING,LINKED etlStyle
    class NUMERIC,TEXT,SEMANTIC featureStyle
    class VECTOR,PREDICT,SHAPEX mlStyle
    class SCORE,LABEL,REASONS outputStyle
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

### 3.3 Alur Prediksi Churn

```mermaid
sequenceDiagram
    participant User
    participant API as Flask API
    participant FS as Feature Service
    participant ML as ML Service
    participant EX as Explainer Service
    participant DB as PostgreSQL

    User->>API: POST /predict/customer/{id}
    API->>DB: Validate Customer exists

    API->>FS: populate_numeric_features()
    FS->>DB: Query Transactions (30d, 90d)
    FS->>DB: Query FeedbackLinked
    FS->>DB: Save CustomerNumericFeatures

    API->>FS: populate_text_signals()
    FS->>DB: Query Message Stats
    FS->>DB: Save CustomerTextSignals

    API->>FS: get_ml_feature_vector()
    FS-->>API: [13 features array]

    API->>ML: predict(feature_vector)
    ML->>ML: Scale features
    ML->>ML: XGBoost.predict_proba()
    ML-->>API: (churn_score, churn_label)

    API->>DB: Save ChurnPrediction

    API->>EX: calculate_shap_values()
    EX->>EX: SHAP TreeExplainer
    EX-->>API: SHAP values array

    API->>DB: Save ShapCache
    API-->>User: Prediction Response
```

### 3.4 Alur Feature Engineering

```mermaid
flowchart LR
    subgraph RAW_DATA["Raw Data"]
        TX[("transactions")]
        MSG[("feedback_linked")]
    end

    subgraph NUMERIC["Numeric Features (13)"]
        R["recency_days"]
        TC30["tx_count_30d"]
        TC90["tx_count_90d"]
        S30["spend_30d"]
        S90["spend_90d"]
        AVG["avg_tx_value"]
        TEN["tenure_days"]
        MC7["msg_count_7d"]
        MC30["msg_count_30d"]
        VOL["msg_volatility"]
        LEN["avg_msg_length_30d"]
        COMP["complaint_rate_30d"]
        DELAY["response_delay_mean"]
    end

    subgraph ML_VECTOR["ML Feature Vector"]
        VEC["13-element array<br/>(ordered)"]
    end

    TX --> R
    TX --> TC30
    TX --> TC90
    TX --> S30
    TX --> S90
    TX --> AVG
    TX --> TEN

    MSG --> MC7
    MSG --> MC30
    MSG --> VOL
    MSG --> LEN
    MSG --> COMP
    MSG --> DELAY

    R --> VEC
    TC30 --> VEC
    TC90 --> VEC
    S30 --> VEC
    S90 --> VEC
    AVG --> VEC
    TEN --> VEC
    MC7 --> VEC
    MC30 --> VEC
    VOL --> VEC
    LEN --> VEC
    COMP --> VEC
    DELAY --> VEC
```

---

## 4. Komponen Utama

### 4.1 Backend Services

```mermaid
classDiagram
    class MLService {
        -model: XGBoostClassifier
        -scaler: StandardScaler
        -shap_explainer: TreeExplainer
        +predict(features) tuple
        +is_model_loaded() bool
        +get_model_version() str
    }

    class FeatureService {
        +FEATURE_SCHEMA: list
        +populate_numeric_features()
        +populate_text_signals()
        +get_ml_feature_vector() list
        +get_feature_schema_hash() str
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
        +find_nearest_messages() list
    }

    class SemanticService {
        +populate_text_semantics()
        -sentiment_service: SentimentService
        -topic_service: TopicService
    }

    MLService --> FeatureService : uses features
    ExplainerService --> MLService : uses model
    FeatureService --> LinkingService : uses linked data
    ETLService --> LinkingService : triggers
    SemanticService --> LinkingService : uses linked data
```

### 4.2 Database Models

```mermaid
erDiagram
    CUSTOMERS ||--o{ TRANSACTIONS : has
    CUSTOMERS ||--o{ FEEDBACK_RAW : has
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
    }

    TRANSACTIONS {
        uuid tx_id PK
        uuid customer_id FK
        float amount
        string service_type
        datetime tx_date
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
    }

    CHURN_PREDICTIONS {
        uuid pred_id PK
        uuid customer_id FK
        float churn_score
        string churn_label
        string model_version
        date as_of_date
        json features_used
    }
```

---

## 5. Alur Data Detail

### 5.1 Data Flow Layers

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
        I1["feedback_linked<br/>(customer_id mapped)"]
    end

    subgraph L4["Layer 4: Feature Tables"]
        direction LR
        F1["customer_numeric_features"]
        F2["customer_text_signals"]
        F3["customer_text_semantics<br/>(dashboard only)"]
    end

    subgraph L5["Layer 5: ML Output"]
        direction LR
        M1["churn_predictions"]
        M2["shap_cache"]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
```

### 5.2 Identity Resolution Flow

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

### 5.3 ML Pipeline Flow

```mermaid
flowchart LR
    subgraph TRAINING["🎓 Training (Jupyter Notebook)"]
        T1["Load Historical Data"]
        T2["Feature Engineering"]
        T3["Train XGBoost"]
        T4["Cross Validation"]
        T5["Export Artifacts"]
    end

    subgraph ARTIFACTS["📦 Model Artifacts"]
        A1["churn_model.pkl"]
        A2["scaler.pkl"]
        A3["features.json"]
        A4["shap_explainer.pkl"]
    end

    subgraph INFERENCE["⚡ Inference (Flask)"]
        I1["Load Model<br/>(Startup)"]
        I2["Build Features"]
        I3["Scale Features"]
        I4["Predict"]
        I5["Explain"]
    end

    T5 --> A1
    T5 --> A2
    T5 --> A3
    T5 --> A4

    A1 --> I1
    A2 --> I1
    A3 --> I1
    A4 --> I1

    I1 --> I2
    I2 --> I3
    I3 --> I4
    I4 --> I5
```

---

## 6. Struktur Database

### 6.1 Schema Overview

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

### 6.2 Tabel Utama

| Tabel                       | Deskripsi                            | Layer     |
| --------------------------- | ------------------------------------ | --------- |
| `customers`                 | Data profil customer                 | Core      |
| `transactions`              | Riwayat transaksi                    | Core      |
| `feedback_raw`              | Pesan WhatsApp mentah                | Staging   |
| `feedback_linked`           | Pesan yang sudah di-link ke customer | Identity  |
| `customer_numeric_features` | Fitur numerik untuk ML               | Feature   |
| `customer_text_signals`     | Sinyal teks (stats)                  | Feature   |
| `customer_text_semantics`   | Semantik teks (dashboard only)       | Display   |
| `churn_predictions`         | Hasil prediksi                       | ML Output |
| `shap_cache`                | Cache SHAP values                    | ML Output |

---

## 7. API Endpoints

### 7.1 Endpoint Overview

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
```

### 7.2 Endpoint Details

| Method | Endpoint                     | Deskripsi              |
| ------ | ---------------------------- | ---------------------- |
| POST   | `/api/auth/login`            | Login user             |
| GET    | `/api/customers`             | List semua customer    |
| GET    | `/api/customers/{id}`        | Detail customer        |
| POST   | `/api/predict/customer/{id}` | Prediksi satu customer |
| POST   | `/api/predict/batch`         | Prediksi batch         |
| GET    | `/api/predictions`           | List prediksi          |
| GET    | `/api/dashboard/stats`       | Statistik dashboard    |
| GET    | `/api/dashboard/trend`       | Trend churn            |

---

## 8. Alur Proses Bisnis

### 8.1 Workflow Pengguna

```mermaid
flowchart TD
    START(["Admin Login"])

    UPLOAD["Upload WhatsApp<br/>Export"]

    ETL_PROCESS["Sistem proses ETL<br/>& Feature Extraction"]

    PREDICT["Jalankan Batch<br/>Prediction"]

    VIEW_DASH["Lihat Dashboard<br/>Overview"]

    CHECK_RISK{"Ada High Risk<br/>Customer?"}

    VIEW_DETAIL["Lihat Detail<br/>Customer"]

    UNDERSTAND["Pahami alasan<br/>(SHAP Explanation)"]

    END(["Selesai"])

    START --> VIEW_DASH
    UPLOAD --> ETL_PROCESS
    ETL_PROCESS --> PREDICT
    PREDICT --> VIEW_DASH
    VIEW_DASH --> CHECK_RISK
    CHECK_RISK -->|Ya| VIEW_DETAIL
    CHECK_RISK -->|Tidak| END
    VIEW_DETAIL --> UNDERSTAND
    UNDERSTAND --> END
```

---

## 📝 Catatan Penting

### Separation of Concerns

1. **Training** dilakukan di **Jupyter Notebook** (terpisah)
2. **Inference** dilakukan di **Flask Backend**
3. **Dashboard** adalah **React Frontend**

### Data Privacy

- Phone number di-hash sebelum disimpan
- Customer data bisa di-mask untuk display
- Consent tracking tersedia

### Model Versioning

- Model artifacts memiliki hash untuk tracking
- Registry mencatat model aktif
- Feature schema di-validate saat load

---

_Dokumentasi ini dibuat pada: Januari 2026_
_Versi: 1.0_
