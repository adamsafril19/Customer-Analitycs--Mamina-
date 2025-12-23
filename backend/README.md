# Sistem Prediksi Customer Churn - Mamina Baby Spa

Backend API untuk sistem prediksi churn pelanggan multimodal menggunakan Flask, PostgreSQL, dan Machine Learning.

## 📋 Daftar Isi

- [Arsitektur Sistem](#arsitektur-sistem)
- [Batasan Flask Backend](#batasan-flask-backend)
- [Alur Data](#alur-data)
- [Struktur Proyek](#struktur-proyek)
- [Instalasi & Konfigurasi](#instalasi--konfigurasi)
- [Menjalankan dengan Docker](#menjalankan-dengan-docker)
- [Menjalankan Lokal](#menjalankan-lokal)
- [API Documentation](#api-documentation)
- [Mengganti Model ML](#mengganti-model-ml)
- [Testing](#testing)

---

## 🏗️ Arsitektur Sistem

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                         │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     NGINX (Reverse Proxy)                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FLASK API (Inference Only)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Routes    │  │  Services   │  │   ML Service (Singleton) │  │
│  │  /predict   │──│  Feature    │──│  - Load model at startup │  │
│  │  /customers │  │  Explainer  │  │  - Inference < 500ms     │  │
│  │  /actions   │  │  ETL        │  │  - SHAP explanations     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
        │                                       │
        ▼                                       ▼
┌───────────────┐                    ┌─────────────────────┐
│  PostgreSQL   │                    │  Redis (Message Q)  │
│  - Customers  │                    │  - Task Queue       │
│  - Features   │                    │  - Rate Limiting    │
│  - Predictions│                    │  - Caching          │
└───────────────┘                    └─────────────────────┘
                                              │
                                              ▼
                                    ┌─────────────────────┐
                                    │   Celery Workers    │
                                    │  - ETL Tasks        │
                                    │  - Batch Prediction │
                                    │  - SHAP Calculation │
                                    └─────────────────────┘
```

## ⚠️ Batasan Flask Backend

Backend ini **HANYA untuk inference**, bukan untuk training model ML.

### ✅ Yang Dilakukan Flask:

- Load model ML yang sudah di-train (pickle files)
- Prediksi churn untuk customer baru/existing
- Perhitungan SHAP values untuk explainability
- ETL data dari WhatsApp logs
- Ekstraksi fitur RFM, Sentiment, Engagement
- Menyimpan hasil prediksi ke database

### ❌ Yang TIDAK Dilakukan Flask:

- Training model ML (gunakan Jupyter Notebook terpisah)
- Hyperparameter tuning
- Cross-validation atau model evaluation
- Feature selection/engineering untuk training

### Alasan:

1. **Separation of Concerns**: Training adalah proses offline yang membutuhkan resource besar
2. **Performance**: Flask harus responsif untuk serving (< 500ms per prediction)
3. **Reproducibility**: Model training harus terdokumentasi di notebook terpisah

---

## 🔄 Alur Data

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ALUR DATA LENGKAP                             │
└─────────────────────────────────────────────────────────────────────────┘

1. INPUT DATA
   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
   │  WhatsApp    │    │  Transaksi   │    │  Customer    │
   │  Chat Logs   │    │  (POS/Manual)│    │  Profile     │
   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
          │                   │                   │
          ▼                   ▼                   ▼
2. ETL & PREPROCESSING
   ┌──────────────────────────────────────────────────────┐
   │  ETL Service                                         │
   │  - Parse WhatsApp format                             │
   │  - Extract timestamp, sender, message                │
   │  - Sentiment analysis per message                    │
   │  - Store to feedback_raw & feedback_clean           │
   └──────────────────────────────────────────────────────┘
          │
          ▼
3. FEATURE EXTRACTION
   ┌──────────────────────────────────────────────────────┐
   │  Feature Service                                      │
   │  ┌────────────┐  ┌────────────┐  ┌────────────────┐  │
   │  │    RFM     │  │ Sentiment  │  │   Engagement   │  │
   │  │ - Recency  │  │ - avg_30d  │  │ - response_sec │  │
   │  │ - Frequency│  │ - neg_count│  │ - intensity_7d │  │
   │  │ - Monetary │  │            │  │                │  │
   │  └────────────┘  └────────────┘  └────────────────┘  │
   │                                                       │
   │  Output: customer_features table                      │
   └──────────────────────────────────────────────────────┘
          │
          ▼
4. PREDICTION (ML Inference)
   ┌──────────────────────────────────────────────────────┐
   │  ML Service (Singleton)                               │
   │  - Load pre-trained XGBoost model                     │
   │  - Build feature vector in correct order              │
   │  - Predict probability (0.0 - 1.0)                   │
   │  - Classify: LOW / MEDIUM / HIGH risk                │
   └──────────────────────────────────────────────────────┘
          │
          ▼
5. EXPLAINABILITY
   ┌──────────────────────────────────────────────────────┐
   │  Explainer Service                                    │
   │  - Calculate SHAP values                              │
   │  - Extract top 3 reasons for prediction              │
   │  - Format human-readable explanations                │
   └──────────────────────────────────────────────────────┘
          │
          ▼
6. ACTIONS & RECOMMENDATIONS
   ┌──────────────────────────────────────────────────────┐
   │  Action Recommendation                                │
   │  - HIGH: Immediate phone call + discount offer       │
   │  - MEDIUM: Personalized WhatsApp message             │
   │  - LOW: Regular newsletter + loyalty program         │
   └──────────────────────────────────────────────────────┘
          │
          ▼
7. OUTPUT
   ┌──────────────────────────────────────────────────────┐
   │  Dashboard Display                                    │
   │  - Customer list with churn risk                     │
   │  - Trend visualization                               │
   │  - Action queue for marketing team                   │
   └──────────────────────────────────────────────────────┘
```

---

## 📁 Struktur Proyek

```
backend/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration classes
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # User & authentication
│   │   ├── customer.py      # Customer profiles
│   │   ├── transaction.py   # Transaction records
│   │   ├── feedback.py      # WhatsApp feedback
│   │   ├── feature.py       # Extracted features
│   │   ├── prediction.py    # Churn predictions
│   │   └── action.py        # Recommended actions
│   ├── services/            # Business logic
│   │   ├── ml_service.py    # ML model loading & inference
│   │   ├── explainer_service.py  # SHAP explanations
│   │   ├── feature_service.py    # Feature extraction
│   │   └── etl_service.py   # WhatsApp ETL
│   ├── routes/              # API endpoints
│   │   ├── health.py        # Health checks
│   │   ├── auth.py          # Authentication
│   │   ├── predictions.py   # Churn predictions
│   │   ├── customers.py     # Customer management
│   │   ├── actions.py       # Action recommendations
│   │   └── admin.py         # Admin operations
│   ├── tasks/               # Celery background tasks
│   │   ├── etl_tasks.py     # ETL processing
│   │   └── prediction_tasks.py  # Batch predictions
│   ├── schemas/             # Marshmallow schemas
│   └── utils/               # Helpers
├── migrations/              # Alembic migrations
├── tests/                   # pytest tests
├── models/                  # ML model files (.pkl)
├── scripts/                 # Utility scripts
├── docker/                  # Docker configuration
├── requirements.txt
├── run.py                   # Entry point
└── .env.example
```

---

## 🚀 Instalasi & Konfigurasi

### Prerequisites

- Python 3.10+
- PostgreSQL 13+
- Redis 6+
- Docker & Docker Compose (untuk deployment)

### 1. Clone & Setup Virtual Environment

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

### 2. Konfigurasi Environment

```bash
copy .env.example .env
```

Edit `.env`:

```env
FLASK_ENV=development
SECRET_KEY=your-super-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production

DATABASE_URL=postgresql://user:password@localhost:5432/mamina_churn

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

MODEL_PATH=models/churn_model.pkl
MODEL_VERSION=v1.0.0
```

### 3. Database Migration

```bash
# Initialize migrations (first time only)
flask db init

# Generate migration
flask db migrate -m "Initial migration"

# Apply migration
flask db upgrade
```

### 4. Seed Data (Optional)

```bash
python scripts/seed_data.py
```

---

## 🐳 Menjalankan dengan Docker

### Quick Start

```bash
cd docker

# Build & start all services
docker-compose up -d --build

# Check logs
docker-compose logs -f api

# Stop all services
docker-compose down
```

### Services

| Service       | Port | Description      |
| ------------- | ---- | ---------------- |
| api           | 5000 | Flask API        |
| celery-worker | -    | Background tasks |
| celery-beat   | -    | Scheduled tasks  |
| db            | 5432 | PostgreSQL       |
| redis         | 6379 | Redis            |

### Production Deployment

```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Scale workers
docker-compose up -d --scale celery-worker=3
```

---

## 💻 Menjalankan Lokal (Development)

### Terminal 1: Flask API

```bash
cd backend
venv\Scripts\activate
flask run --debug
```

### Terminal 2: Celery Worker

```bash
cd backend
venv\Scripts\activate
celery -A app.tasks worker --loglevel=info --pool=solo
```

### Terminal 3: Celery Beat (Scheduler)

```bash
cd backend
venv\Scripts\activate
celery -A app.tasks beat --loglevel=info
```

---

## 📚 API Documentation

### Base URL

- Development: `http://localhost:5000`
- Production: `https://api.mamina.com`

### Swagger UI

Access interactive documentation at: `http://localhost:5000/apidocs`

### Authentication

All protected endpoints require JWT token:

```
Authorization: Bearer <token>
```

### Main Endpoints

#### Health Check

```
GET /api/v1/health
GET /api/v1/health/ready
```

#### Authentication

```
POST /api/v1/auth/login
POST /api/v1/auth/refresh
```

#### Predictions

```
GET  /api/v1/predictions                    # List predictions
GET  /api/v1/predictions/{id}               # Get prediction detail
POST /api/v1/predictions/single             # Single prediction
POST /api/v1/predictions/batch              # Batch prediction (async)
GET  /api/v1/predictions/{id}/explanation   # SHAP explanation
```

#### Customers

```
GET  /api/v1/customers                      # List customers
GET  /api/v1/customers/{id}                 # Get customer detail
GET  /api/v1/customers/{id}/features        # Get customer features
GET  /api/v1/customers/{id}/predictions     # Get prediction history
```

#### Actions

```
GET   /api/v1/actions                       # List actions
POST  /api/v1/actions                       # Create action
PATCH /api/v1/actions/{id}/complete         # Mark as completed
```

#### Admin

```
POST /api/v1/admin/etl/trigger              # Trigger ETL
POST /api/v1/admin/features/recalculate     # Recalculate features
POST /api/v1/admin/predictions/batch        # Trigger batch prediction
GET  /api/v1/admin/model/info               # Model info
```

---

## 🔄 Mengganti Model ML

### 1. Train Model Baru (di Jupyter Notebook)

```python
import joblib
import shap
from xgboost import XGBClassifier

# Load data & train
model = XGBClassifier(
    n_estimators=100,
    max_depth=5,
    learning_rate=0.1
)
model.fit(X_train, y_train)

# Save model
joblib.dump(model, 'models/churn_model.pkl')

# Create SHAP explainer
explainer = shap.TreeExplainer(model)
joblib.dump(explainer, 'models/shap_explainer.pkl')
```

### 2. Update Feature Metadata (jika berubah)

Edit `models/features.json`:

```json
{
  "version": "v2.0.0",
  "features": [
    { "name": "r_score", "type": "numeric", "position": 0 },
    { "name": "f_score", "type": "numeric", "position": 1 }
    // ... tambah/ubah sesuai model baru
  ]
}
```

### 3. Update Environment Variable

```env
MODEL_VERSION=v2.0.0
MODEL_PATH=models/churn_model_v2.pkl
```

### 4. Restart Service

```bash
docker-compose restart api celery-worker
```

### 5. Verify

```bash
curl http://localhost:5000/api/v1/admin/model/info
```

---

## 🧪 Testing

### Run All Tests

```bash
pytest
```

### Run with Coverage

```bash
pytest --cov=app --cov-report=html
```

### Run Specific Test

```bash
pytest tests/test_ml_service.py -v
pytest tests/test_api.py::TestPredictions -v
```

### Test Categories

- `tests/test_api.py` - API endpoint tests
- `tests/test_ml_service.py` - ML service tests
- `tests/test_features.py` - Feature extraction tests

---

## 📊 Database Schema

### Tables

| Table             | Description                       |
| ----------------- | --------------------------------- |
| users             | Admin users for dashboard         |
| customers         | Customer profiles                 |
| transactions      | Transaction records               |
| feedback_raw      | Raw WhatsApp messages             |
| feedback_clean    | Processed feedback with sentiment |
| customer_features | Extracted ML features             |
| churn_predictions | Prediction results with SHAP      |
| actions           | Recommended retention actions     |

### Key Relationships

```
customers (1) ──── (N) transactions
customers (1) ──── (N) feedback_clean
customers (1) ──── (1) customer_features
customers (1) ──── (N) churn_predictions
churn_predictions (1) ──── (N) actions
```

---

## 🔒 Security

- All passwords hashed with bcrypt
- JWT tokens with 1 hour expiry
- CORS configured for frontend domain
- Rate limiting on API endpoints
- Input validation with Marshmallow
- SQL injection prevention via SQLAlchemy ORM

---

## 📝 License

MIT License - Skripsi Project for Mamina Baby Spa

---

## 👤 Author

Customer Churn Prediction System - Thesis Project
