# 🔍 Audit Notebook: `01_churn_model_training.ipynb`

Berikut hasil review kode dan logika notebook training model churn. Saya membagi temuan menjadi:
- 🔴 **CRITICAL** — Bug yang akan menyebabkan error atau hasil salah
- 🟡 **WARNING** — Potensi masalah logika atau best-practice
- 🟢 **OK** — Bagian yang sudah benar (untuk konfirmasi)

---

## 🔴 CRITICAL Issues

### 1. Cell 14: Tidak Ada Kode Save Model!

[Cell 14](file:///d:/coolyeah/Skripsi/Customer%20Analitycs%20%28Mamina%29/notebooks/01_churn_model_training.ipynb) seharusnya berjudul "Save Model & Artifacts", tetapi isinya **hanya duplikat dari Cell 12** (Feature Importance plot). Tidak ada kode untuk menyimpan:
- `churn_model.pkl` (model XGBoost)
- `scaler.pkl` (imputer/scaler)
- `shap_explainer.pkl` (SHAP explainer)
- `features.json` (metadata fitur)
- `model_metadata.pkl` (metadata model)

```diff
- # Cell 14 saat ini hanya plot feature importance (duplikat Cell 12)

+ # Seharusnya berisi:
+ import os
+ MODEL_DIR = "../backend/models"
+ os.makedirs(MODEL_DIR, exist_ok=True)
+
+ # Save model
+ joblib.dump(xgb_model, os.path.join(MODEL_DIR, "churn_model.pkl"))
+
+ # Save imputer (CRITICAL: frontend/pipeline membutuhkan ini)
+ joblib.dump(imputer, os.path.join(MODEL_DIR, "scaler.pkl"))
+
+ # Save SHAP explainer
+ joblib.dump(explainer, os.path.join(MODEL_DIR, "shap_explainer.pkl"))
+
+ # Save feature metadata
+ features_meta = {
+     "feature_names": FEATURE_NAMES,
+     "feature_schema": FEATURE_SCHEMA,
+     "schema_version": FEATURE_SCHEMA_VERSION,
+     "schema_hash": get_feature_schema_hash(),
+     "expected_count": EXPECTED_FEATURE_COUNT,
+     "training_date": datetime.now().isoformat(),
+     "train_samples": len(X_train),
+     "test_samples": len(X_test),
+     "smote_applied": SMOTE_APPLIED,
+ }
+ with open(os.path.join(MODEL_DIR, "features.json"), "w") as f:
+     json.dump(features_meta, f, indent=2)
+
+ # Save model metadata (for MLModelRegistry)
+ model_hash = hashlib.sha256(
+     open(os.path.join(MODEL_DIR, "churn_model.pkl"), "rb").read()
+ ).hexdigest()[:16]
+ model_metadata = {
+     "model_hash": model_hash,
+     "model_version": FEATURE_SCHEMA_VERSION,
+     "feature_schema_hash": get_feature_schema_hash(),
+     "expected_feature_count": EXPECTED_FEATURE_COUNT,
+     "metrics": {
+         "accuracy": accuracy_score(y_test, y_pred),
+         "precision": precision_score(y_test, y_pred, zero_division=0),
+         "recall": recall_score(y_test, y_pred, zero_division=0),
+         "f1": f1_score(y_test, y_pred, zero_division=0),
+         "roc_auc": roc_auc_score(y_test, y_pred_proba) if len(np.unique(y_test)) > 1 else None,
+         "train_size": len(X_train),
+         "test_size": len(X_test),
+     }
+ }
+ joblib.dump(model_metadata, os.path.join(MODEL_DIR, "model_metadata.pkl"))
```

> [!CAUTION]
> Tanpa kode save ini, notebook **tidak menghasilkan artefak apapun**. Semua training sia-sia karena model tidak tersimpan ke disk. Ini juga menjelaskan error `code expected at most 16 arguments, got 18` di Docker — file `.pkl` lama tidak kompatibel karena belum pernah di-overwrite oleh notebook ini.

---

### 2. Cell 7: SQL Injection via f-string pada `trusted_statuses_sql`

```python
trusted_statuses_sql = str(TRUSTED_LINK_STATUSES)
# Menghasilkan: "('verified', 'probable')"

query = text(f"""
    ...
    AND fl.link_status IN {trusted_statuses_sql}
    ...
""")
```

Ini **bukan parameterized query**. Meskipun nilainya hardcoded dan tidak berbahaya, ini adalah anti-pattern yang bisa menyebabkan:
1. **SQL syntax error** jika tuple hanya 1 elemen (Python menghasilkan `('verified',)` yang valid di SQL, tapi membingungkan)
2. **Kebiasaan buruk** yang tidak bisa lolos review skripsi

**Fix:**
```python
# Gunakan parameterized IN clause
# SQLAlchemy mendukung: WHERE fl.link_status = ANY(:statuses)
# Atau gunakan hardcoded string yang aman:
trusted_in_clause = "('verified', 'probable')"
```

---

### 3. Cell 10: Double-Counting `scale_pos_weight` Setelah SMOTE

```python
# Cell 9.5: SMOTE sudah menyeimbangkan data
X_train, y_train = smote.fit_resample(X_train, y_train)

# Cell 10: scale_pos_weight dihitung SETELAH SMOTE
scale_pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)
```

Jika SMOTE telah di-apply, `y_train` sudah seimbang (50:50), sehingga `scale_pos_weight ≈ 1.0`. Ini berarti parameter ini **tidak melakukan apa-apa**. 

**Masalahnya:** Jika SMOTE TIDAK di-apply (karena data sudah cukup seimbang, misal 30:70), maka `scale_pos_weight` tetap dihitung dari data asli — ini benar. Tapi secara logika, kode ini **membingungkan**.

**Fix:**
```python
# Hitung scale_pos_weight SEBELUM SMOTE, dari data original
scale_pos_weight = (y_train_original == 0).sum() / max((y_train_original == 1).sum(), 1)

# Jika SMOTE sudah diterapkan, override ke 1.0
if SMOTE_APPLIED:
    scale_pos_weight = 1.0
```

---

## 🟡 WARNING Issues

### 4. Cell 7: `msg_volatility` Dihitung Berbeda dari Backend

**Notebook:**
```python
# msg_volatility = STDDEV dari daily_count per message_date
# Ini menghitung std dari hari-hari YANG ADA data saja
SELECT STDDEV(daily_count) FROM daily_counts
```

**Backend (`feature_service.py` baris 280-290):**
```python
# msg_volatility = std dari SEMUA hari dalam range (termasuk hari 0 pesan)
counts = []
current = thirty_days_ago
while current <= as_of_date:
    counts.append(daily_counts.get(current, 0))
    current += timedelta(days=1)
signals.msg_volatility = float(np.std(counts))
```

**Perbedaan:** Backend menghitung std dari 30 hari penuh (termasuk hari tanpa pesan = 0), sedangkan notebook hanya dari hari yang ada pesan. Ini menyebabkan **training-serving skew** — model dilatih dengan distribusi fitur yang berbeda dari yang dipakai saat inferensi.

**Fix Notebook:**
```python
# Ganti query menjadi: generate series 30 hari, isi 0 untuk hari kosong
# Atau hitung secara manual di Python setelah mendapat daily_counts
```

---

### 5. Cell 7: `complaint_ratio` Window Terlalu Sempit

Notebook menghitung `complaint_ratio` hanya dari **30 hari terakhir** (`WINDOW_SIZE_DAYS = 30`):
```python
AND fr.timestamp >= CAST(:obs_date AS date) - :window_days   -- 30 hari
AND fr.timestamp < CAST(:obs_date AS date)
```

Backend (`feature_service.py` baris 254-262) juga menggunakan 30 hari. **Ini konsisten** ✅, tapi perlu diperhatikan bahwa:
- Jika customer hanya punya 2-3 pesan dalam 30 hari, `complaint_ratio` sangat noisy (0% atau 33% atau 100%)
- Pertimbangkan smoothing atau minimum sample threshold

---

### 6. Cell 6: `tx_date < :obs_date` vs `tx_date <= :obs_date`

```sql
-- Feature window
LEFT JOIN transactions t ON cp.customer_id = t.customer_id
    AND t.status = 'completed' AND t.tx_date < :obs_date  -- STRICT less than

-- Label window
AND t.tx_date >= :obs_date   -- Inclusive
```

**Ini berarti:** Transaksi yang terjadi **tepat pada obs_date** tidak masuk ke feature window, tapi **masuk** ke label window (dianggap sebagai "future" activity). Secara logika temporal ini konsisten, tapi perlu didokumentasikan karena bisa membingungkan reviewer skripsi.

---

### 7. Cell 10: `use_label_encoder=False` Deprecated

```python
xgb_model = xgb.XGBClassifier(
    ...
    use_label_encoder=False,  # Deprecated sejak XGBoost 1.6
    ...
)
```

Pada versi XGBoost terbaru (2.0+), parameter ini sudah dihapus dan akan menyebabkan **warning** (bukan error). Hapus saja baris ini.

---

### 8. Cell 6: Potential Data Leakage pada `tenure_days`

```sql
-- Tenure dihitung dari customers.created_at
tenure AS (
    SELECT customer_id,
           EXTRACT(DAY FROM (CAST(:obs_date AS timestamp) - created_at))::int as tenure_days
    FROM customers
    WHERE is_provisional = FALSE
)
```

Filter `is_provisional = FALSE` mungkin menyebabkan masalah:
- Jika customer awalnya provisional, lalu di-confirm setelah obs_date, maka pada saat obs_date seharusnya customer ini masih provisional — tapi query ini mungkin tetap meng-include-nya karena filter dievaluasi pada **saat query dijalankan** (sekarang), bukan pada obs_date.
- Ini adalah **minor temporal leakage** yang sulit dihindari tanpa versi/audit trail pada kolom `is_provisional`.

---

## 🟢 Yang Sudah Benar

| Aspek | Status | Keterangan |
|-------|--------|------------|
| Feature schema | ✅ | 20 fitur, urutan sama dengan `FeatureService.FEATURE_SCHEMA` |
| Schema version | ✅ | `v3.0.0` cocok |
| Temporal separation | ✅ | Feature dari masa lalu, label dari masa depan, window tidak overlap |
| Time-based split | ✅ | Bukan random split, cutoff berbasis waktu |
| Imputation setelah split | ✅ | `fit_transform` pada train, `transform` pada test |
| Smoothing functions | ✅ | SMA dan EMA identik dengan backend |
| `compute_trend_slope` | ✅ | Linear regression identik dengan backend |
| `compute_cv` | ✅ | Zero-safe, capped, identik dengan backend |
| `safe_ratio` | ✅ | Identik dengan `FeatureService._safe_ratio` |
| Ablation tests | ✅ | Bagus untuk validasi model |
| SHAP explainer | ✅ | Handles both list and array output |

---

## 📋 Rangkuman Prioritas Perbaikan

| # | Severity | Issue | Cell |
|---|----------|-------|------|
| 1 | 🔴 CRITICAL | Cell 14 tidak menyimpan model/artefak (duplikat Cell 12) | 14 |
| 2 | 🔴 CRITICAL | SQL f-string injection pada `trusted_statuses_sql` | 7 |
| 3 | 🔴 CRITICAL | `scale_pos_weight` dihitung setelah SMOTE (double-counting) | 10 |
| 4 | 🟡 WARNING | `msg_volatility` dihitung berbeda dari backend (training-serving skew) | 7 |
| 5 | 🟡 WARNING | `use_label_encoder=False` deprecated | 10 |
| 6 | 🟡 WARNING | Minor temporal leakage pada `is_provisional` filter | 6 |

> [!IMPORTANT]
> **Issue #1 adalah yang paling kritis.** Tanpa kode save, notebook ini tidak menghasilkan file model yang bisa dipakai oleh Docker backend. Ini juga menjelaskan mengapa error `code expected at most 16 arguments, got 18` muncul di Docker — file `.pkl` yang ada sekarang kemungkinan berasal dari versi Python/XGBoost yang berbeda dan belum pernah di-update oleh notebook ini.

---

Apakah Anda ingin saya langsung perbaiki semua issue di atas?
