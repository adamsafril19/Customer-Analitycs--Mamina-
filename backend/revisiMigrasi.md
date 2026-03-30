INSTRUKSI: Revisi migrasi & service → embedding + semantic layer (ML-grade)
Tujuan singkat

Pertahankan semantic outputs (topic_id, sentiment_label, complaint_type) — jangan hapus makna bisnis.

Tambahkan representation (embedding) untuk dipakai di ML.

Sediakan message-level dan customer-level features yang dapat ditangani XGBoost (embed + scalar behavioral).

SHAP dipakai untuk tactical explainability (per-customer), sedangkan topic-lift dipakai untuk strategic insights (population-level).

PRIORITAS (urutan pekerjaan)

DB: tambahkan tabel yang hilang / ubah kolom embedding jadi vector (pgvector), restore topic/sentiment columns.

ETL: rewrite untuk menulis feedback_features (message-level) with embedding + semantic labels.

Topic modeling: run BERTopic (or cluster) offline to produce topics table and topic assignments.

Feature aggregation: populate customer_text_features & enrich customer_features (join transactions).

ML pipeline: train model on new features; save artifacts + register model_versions.

Explainer: compute SHAP; cache shap_cache; add "nearest messages" mapping for top reasons.

API: expose endpoints for churn, topics, customer360, explain.

Tests & acceptance criteria.

A. DATABASE MIGRATION (Alembic) — concrete steps

Goal: keep business signals (topic, sentiment), add embeddings and topic mapping table, and add utility tables (model_versions, shap_cache).

1 — Ensure pgvector extension

Alembic upgrade step (if not yet):

op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

2 — Create topics table
CREATE TABLE topics (
  topic_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT,
  top_keywords TEXT[],
  model_version VARCHAR,
  created_at TIMESTAMP DEFAULT now()
);


Alembic example:

op.create_table(
  'topics',
  sa.Column('topic_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
  sa.Column('name', sa.Text(), nullable=True),
  sa.Column('top_keywords', postgresql.ARRAY(sa.Text), nullable=True),
  sa.Column('model_version', sa.String(50), nullable=True),
  sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
)

3 — Modify feedback_features (message-level)

Keep + add these columns (if not present):

embedding ⇒ use vector(384) or vector(768) (choose model dim). Implementation: add new column embedding_vec vector(<dim>), compute & copy later, then drop old array. Example Alembic flow:

op.add_column('feedback_features', sa.Column('embedding_vec', sa.Text(), nullable=True))
# Agent: replace sa.Text() with raw SQL to create vector column:
op.execute('ALTER TABLE feedback_features ADD COLUMN embedding_vec vector(384);')


sentiment_score FLOAT, sentiment_label VARCHAR, topic_id UUID REFERENCES topics(topic_id), topic_confidence FLOAT, complaint_type VARCHAR, keywords JSONB

keep response_time_secs, processed_at

Important: do not delete topic_labels or sentiment_label — we will populate them via ML (not TextBlob). We will keep both representation and semantic labels.

4 — Create customer_text_features (already created; ensure fields)

Ensure it contains:

avg_embedding vector(<dim>) (optional — see note below)

embedding_count_30d INT

last_n_embedding JSONB or store last N embedding ids (for nearest-message drilldown)

scalar features: msg_count_7d, msg_count_30d, complaint_rate_30d, avg_msg_length_30d, response_delay_mean, msg_volatility

maintain UNIQUE(customer_id, as_of_date)

5 — Add model_versions and shap_cache

model_versions:

CREATE TABLE model_versions (
  model_version VARCHAR PRIMARY KEY,
  model_path TEXT,
  trained_at TIMESTAMP,
  metrics JSONB,
  deployed BOOLEAN DEFAULT FALSE,
  notes TEXT,
  created_at TIMESTAMP DEFAULT now()
);


shap_cache:

CREATE TABLE shap_cache (
  pred_id UUID PRIMARY KEY,
  shap_top JSONB,
  nearest_messages JSONB,
  computed_at TIMESTAMP DEFAULT now(),
  explainer_version VARCHAR
);

6 — Migration notes for agent

If feedback_clean was dropped: restore semantic columns in feedback_features (sentiment_label, topic_id, keywords) — the migration must not leave you without topic/sentiment.

Convert embedding array → pgvector by creating embedding_vec column, writing values by batch job (compute from model) and then drop old array column.

Use ON CONFLICT (msg_id) DO UPDATE for idempotent ETL.

B. ETL (rewrite) — message-level pipeline (feedback_features)
Goal

Each raw message → normalized text → features (embedding + semantic labels + signal scalars) → upsert to feedback_features.

High level flow (code outline)

Read raw messages from feedback_raw (only new/unprocessed).

text_clean = normalize_text(text) (lowercase, slang map, remove PII).

embedding = encoder.encode(text_clean) — prefer sentence-transformers MiniLM or Indo-specific SBERT (choose dim 384 or 768).

sentiment_label, sentiment_score = sentiment_classifier.predict(text_clean) — classifier trained on Indonesian data or off-the-shelf Indonesian sentiment model.

topic_id, topic_confidence = topic_assigner.assign(text_clean, embedding) — use BERTopic or nearest topic cluster.

complaint_type = complaint_classifier.predict(text_clean) (optional).

Extract scalar signals: msg_length, num_exclamations, num_questions, has_refund_request (via classifier or regex), language_confidence.

Upsert into feedback_features:

INSERT INTO feedback_features (feature_id, msg_id, customer_id, embedding_vec, sentiment_score, sentiment_label, topic_id, topic_confidence, complaint_type, msg_length, num_exclamations, num_questions, has_complaint, processed_at)
VALUES (...)
ON CONFLICT (msg_id) DO UPDATE SET ...

Implementation notes

Use batch processing (e.g., process 500–2000 messages per worker call).

Compute embeddings offline in workers (Celery) and cache them to avoid recomputing same message.

Use sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 as pragmatic default. If later upgrade to Indo-specific, keep dim consistent or create new column/version.

Example snippet (embedding compute)
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
embs = model.encode(list_of_texts, show_progress_bar=True)
# store each embedding as pgvector via psycopg2 binary saver or SQL.

C. TOPIC MODELING & semantic labels (offline process)
Use BERTopic or HDBSCAN + c-TF-IDF pattern

Build document embeddings (MiniLM).

Run UMAP (optional) → HDBSCAN → create clusters.

Produce topic_id and top keywords per topic.

Insert topics into topics table with top_keywords.

Assign topic_id per message (as in ETL).

Why: topic clusters give stable interpretable labels (you can name clusters manually: topic_name), enabling population-level topic × churn analysis.

D. FEATURE AGGREGATION (customer_text_features & customer_features)
Customer-level signals for ML:

Numeric RFM features from transactions (r_score, f_score, m_score, tenure_days).

Scalar text features aggregated:

msg_count_7d, msg_count_30d

complaint_rate_30d = (msg with complaint)/msg_count_30d

avg_msg_length_30d

response_delay_mean

msg_volatility (std dev daily msg counts)

Embedding aggregations (optional, use cautiously):

avg_embedding_30d (mean pooling) — document caution: include as feature but also include topic distribution and scalar features to avoid overreliance on averaged embedding.

last_embedding (embedding of last message)

top_topic_counts (array or JSON): counts of top-3 topics in window

Implementation

Create an ETL job recalculate_customer_text_features(as_of_date) that:

aggregates SQL counts and joins to build scalar features (use SQL aggregations; avoid loading all rows).

for embeddings: fetch embeddings for last N messages per customer, compute mean in Python and upsert customer_text_features. Batch commit.

Use ON CONFLICT (customer_id, as_of_date) DO UPDATE.

E. ML TRAINING PIPELINE (notebook → script)
Training artifacts to produce

churn_model.pkl (XGBoost / LightGBM)

feature_order.json

model_versions metadata entry

explainer saved (if using TreeExplainer, keep model and background dataset for SHAP)

Training steps (recommended)

Prepare dataset with time-based split: choose cutoff date T, extract features as of T, label = did customer repeat in next 180 days? (as defined). Avoid leakage.

Use embeddings + scalar features (RFM + text scalars + optional aggregated embedding) as X.

Train baseline (XGBoost), tune hyperparams, measure Precision/Recall/F1 (focus recall), save model.

Save feature_order.json with feature names and scaling metadata.

Register model in model_versions.

F. EXPLAINER SERVICE (update)
Goals

Compute SHAP for a prediction.

Provide top reasons (current ExplainerService OK).

Add nearest-message drilldown: for each top feature (if it's an embedding-derived feature or topic_count), return example messages that contributed (via nearest-neighbor in embedding space).

Implementation notes

Keep heavy SHAP compute as Celery job; store results in shap_cache.

For top shap feature that is topic_count_X or last_embedding:

if feature is topic_count → return latest messages with that topic.

if feature is embedding dimension or agg-embedding → use cosine similarity between last_embedding and feedback_features.embedding_vec to find top-N messages; return their text snippets (mask PII).

Return nearest_messages in shap_cache as JSON.

G. API changes (Flask) — endpoints & behaviors

Add/modify endpoints:

GET /api/health

GET /api/dashboard/summary → include strategic view: top topics with lift (topic-churn stats).

GET /api/churn/high-risk?limit=50 → returns customers with churn_score, risk_label, top_reasons (from shap_cache or compute light-weight).

GET /api/customers/{id}/360 → return profile, transactions, customer_text_features, last messages, top_reasons, nearest_messages.

POST /api/admin/trigger-etl → enqueue ETL batch (compute embeddings + topics + aggregates).

POST /api/admin/compute-shap/{pred_id} → enqueue SHAP compute job and return job id; once done, read shap_cache.

GET /api/topics → return topics table with top_keywords and lift metrics.

Behavioral rules

Inference endpoint should not compute SHAP on-the-fly if heavy; return shap_status: queued and allow async retrieval.

All endpoints should return model_version.

H. Background Jobs (Celery)
Tasks to implement

compute_embeddings(batch_of_msg_ids) — compute and upsert embedding_vec.

assign_topics(batch_of_msg_ids) — assign topic_id via topic_assigner.

recalculate_customer_text_features(date, batch_size=500) — aggregate and upsert.

train_model_task() — optional to run scheduled retraining.

compute_shap_task(pred_id) — compute SHAP and nearest messages; upsert shap_cache.

Run pattern:

ETL job enqueues embedding+topic tasks → once done mark processed → enqueue aggregation job.

I. Tests & QA
Unit tests

ETL: normalize_text, extract_signals, embedding interface (mock).

FeatureService: given sample messages & transactions, calculate_customer_features returns expected scalars.

ExplainerService: get_top_reasons returns fallback when SHAP missing.

Integration tests

Run small synthetic dataset (200 customers, sample messages) → run complete ETL → ensure customer_text_features populated → train model on sample dataset → run inference → ensure churn_predictions inserted.

Acceptance Criteria (explicit)

feedback_features contains embedding_vec populated for processed messages (>= 95% of processed messages).

topics table populated with named topics (>= 5 topics) and topic_id assigned to messages.

customer_text_features exists for each customer snapshot date with scalar features non-null.

Trained model saved and model_versions updated.

GET /api/customers/{id}/360 returns churn_score, top_reasons and nearest_messages.

compute_shap_task writes shap_cache with top_reasons and nearest_messages.

All changes have unit tests + integration test passing.

J. Implementation snippets (copy/paste)
Alembic: add vector column (safest method)
# add new vector column
op.execute("ALTER TABLE feedback_features ADD COLUMN embedding_vec vector(384)")

# later, agent will run an offline job to compute embeddings and update embedding_vec
# after verify, drop old embedding array column:
op.drop_column('feedback_features', 'embedding')

Upsert feedback_features (psycopg2 execute_values)
INSERT INTO feedback_features (feature_id, msg_id, customer_id, embedding_vec, sentiment_score, sentiment_label, topic_id, topic_confidence, complaint_type, msg_length, num_exclamations, num_questions, has_complaint, processed_at)
VALUES %s
ON CONFLICT (msg_id) DO UPDATE SET
  embedding_vec = EXCLUDED.embedding_vec,
  sentiment_score = EXCLUDED.sentiment_score,
  sentiment_label = EXCLUDED.sentiment_label,
  topic_id = EXCLUDED.topic_id,
  topic_confidence = EXCLUDED.topic_confidence,
  complaint_type = EXCLUDED.complaint_type,
  msg_length = EXCLUDED.msg_length,
  num_exclamations = EXCLUDED.num_exclamations,
  num_questions = EXCLUDED.num_questions,
  has_complaint = EXCLUDED.has_complaint,
  processed_at = EXCLUDED.processed_at

Compute embedding with sentence-transformers
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
embeddings = model.encode(texts, show_progress_bar=True)
# store each embedding into embedding_vec column via psycopg2 with vector adapter OR use SQL: INSERT ... embedding_vec => use binary format

Nearest messages (cosine similarity in SQL using pgvector)
SELECT msg_id, customer_id, text, embedding_vec <#> query_embedding AS distance
FROM feedback_features
WHERE embedding_vec IS NOT NULL
ORDER BY query_embedding <-> embedding_vec
LIMIT 5;


(uses pgvector <-> operator for cosine/inner product as configured)

K. Deliverables expected from agent (per milestone)
Milestone 1 — DB + ETL baseline

Alembic migration scripts (including vector column addition)

ETL worker that processes messages, computes embedding, semantic labels, stores in feedback_features

Topic modeling script to populate topics

Milestone 2 — Aggregation & Features

recalculate_customer_text_features job

integration test that populates customer_text_features for sample dataset

Milestone 3 — Model & Explainer

Training script producing model artifact + model_versions entry

Explainer Celery task creating shap_cache with nearest_messages

API endpoints for /predict and /customers/{id}/360

Milestone 4 — Tests & README

Unit & integration tests, README with run instructions (docker-compose up, envvars, celery commands)

L. Commands / env / libs to use

Python libs: sentence-transformers, bertopic, hdbscan, umap-learn, psycopg2-binary, sqlalchemy, alembic, celery, redis, xgboost, shap

Alembic: alembic revision --autogenerate -m "add embedding_vec", alembic upgrade head

Celery worker: celery -A app.celery worker --loglevel=info

Run ETL: python -m scripts.etl_runner --process-unprocessed --batch 500

M. Notes / Rationale (for agent & code reviewer)

Do not remove topic / sentiment columns without restoring them via ML-based assignment. They are essential for strategic analysis.

Store embeddings to accelerate similarity and clustering, but do not treat embeddings as final business signals alone — always derive human-interpretable labels (topic_name, complaint_type) from embeddings.

Keep versioning: every NLP model (encoder, topic model, sentiment classifier) must be recorded (model_versions) and stored in DB columns nlp_version where relevant.

Jika agent selesai satu milestone, minta mereka push branch + CI lalu kirim PR ke kamu.
Kalau mau, aku bisa selanjutnya generate tugas kode sample (ETL worker, topic assigner, alembic snippet, or Celery task) untuk diberikan langsung ke agent. Mau aku buatkan salah satu file masukannya sekarang? (pilih: ETL worker / topic assigner / aggregate job / shap task)