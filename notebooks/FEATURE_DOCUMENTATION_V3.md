# 📋 Feature Documentation — v3.0.0
## Behavioral Risk Scoring — Mamina Baby Spa

> **Schema Version**: v3.0.0  
> **Total Features**: 20  
> **Dimensi Behavioral**: Trend, Magnitude, Volatility, Interaction, Context, NLP  
> **Smoothing**: SMA (default) / EMA (configurable)

---

## Design Principles

Setiap feature merepresentasikan minimal satu dari 3 dimensi perilaku:

1. **Trend** — Arah perubahan aktivitas (meningkat/menurun)
2. **Magnitude** — Tingkat aktivitas absolut (aktif/pasif)
3. **Volatility** — Stabilitas/konsistensi aktivitas

Ditambah:
- **Interaction** — Kombinasi Trend × Magnitude untuk menangkap bahwa penurunan pada customer aktif lebih signifikan
- **Context** — Informasi absolut yang menjadi baseline
- **NLP** — Signal dari pola komunikasi

---

## Configurable Parameters

| Parameter | Default | Deskripsi |
|---|---|---|
| `smoothing_method` | `"sma"` | Metode smoothing: `"sma"` atau `"ema"` |
| `smoothing_window` | `3` | Window size untuk SMA / span untuk EMA |
| `ema_alpha` | `None` (auto) | Alpha EMA. Jika None, dihitung sebagai `2/(window+1)` |
| `activity_windows` | `3` | Jumlah window historis (×30d) |
| `window_size_days` | `30` | Ukuran setiap window dalam hari |
| `min_activity_threshold` | `0.01` | Floor untuk denominator CV |
| `cv_cap` | `10.0` | Cap untuk coefficient of variation |
| `ratio_cap` | `10.0` | Cap untuk safe ratio |
| `ratio_default` | `1.0` | Default ketika numerator & denominator = 0 |

---

## Feature Catalog

### 1. TREND FEATURES (Smoothed)

---

#### 1.1 `recency_ratio`
- **Definisi**: `recency_days / avg_interpurchase_days`
- **Tipe**: Numeric (ratio)
- **Behavioral Meaning**: Mengukur seberapa "terlambat" customer dibanding pola pribadinya. Nilai > 1 berarti sudah lebih lama dari biasanya tidak bertransaksi.
- **Alasan**: Recency absolut tidak adil — customer yang biasa datang 2 minggu sekali berbeda dengan yang datang 2 bulan sekali. Ratio menormalisasi terhadap baseline personal.
- **Edge Cases**:
  - `avg_ipt = 0` (customer baru, <2 transaksi) → return `ratio_default` (1.0) jika recency juga 0, atau `ratio_cap` (10.0) jika ada recency
  - Capped at `ratio_cap` untuk mencegah extreme values

---

#### 1.2 `frequency_trend_smoothed`
- **Definisi**: `slope(SMA([tx_count_w1, tx_count_w2, tx_count_w3]))`
  - Linear regression slope pada smoothed tx count series
  - Series: 3 windows × 30 hari (oldest → newest)
- **Tipe**: Numeric (slope)
- **Behavioral Meaning**: Arah perubahan frekuensi transaksi yang sudah di-denoise. Positif = meningkat, negatif = menurun, ~0 = stabil.
- **Alasan**: Raw ratio (`tx_30d / tx_prior_30d`) terlalu sensitif — 1 transaksi bisa mengubah ratio dari 0 ke infinity. Smoothing + slope lebih stabil.
- **Edge Cases**:
  - Series semua 0 → slope = 0 (customer memang tidak aktif)
  - Series length < 2 → return 0.0

---

#### 1.3 `spend_trend_smoothed`
- **Definisi**: `slope(SMA([spend_w1, spend_w2, spend_w3]))`
- **Tipe**: Numeric (slope)
- **Behavioral Meaning**: Arah perubahan nominal belanja (smoothed). Menangkap apakah customer mulai berbelanja lebih sedikit.
- **Alasan**: Sama seperti frequency_trend — raw ratio terlalu noisy. Slope pada smoothed series lebih robust.
- **Edge Cases**: Sama seperti frequency_trend_smoothed

---

#### 1.4 `msg_trend_smoothed`
- **Definisi**: `slope(SMA([msg_count_w1, msg_count_w2, msg_count_w3]))`
- **Tipe**: Numeric (slope)
- **Behavioral Meaning**: Arah perubahan intensitas komunikasi. Customer yang mulai berhenti berkomunikasi mungkin losing engagement.
- **Alasan**: Komunikasi adalah early signal disengagement sebelum transaksi berhenti.
- **Edge Cases**: Customer tanpa feedback verified → semua 0 → slope = 0.0

---

#### 1.5 `sentiment_trend`
- **Definisi**: `avg_sentiment_30d - avg_sentiment_prior_30d`
- **Tipe**: Numeric (delta)
- **Behavioral Meaning**: Perubahan sentimen customer. Negatif = sentimen memburuk. Positif = membaik.
- **Alasan**: Tidak di-smooth karena sudah dirata-rata per periode (30d mean). Smoothing tambahan akan over-smooth.
- **Edge Cases**: Tidak ada data sentimen → default 0.0 (netral, no change)

---

### 2. ABSOLUTE CONTEXT FEATURES

---

#### 2.1 `recency_days`
- **Definisi**: `(as_of_date - tanggal_transaksi_terakhir).days`
- **Tipe**: Integer (hari)
- **Behavioral Meaning**: Berapa hari sejak transaksi terakhir. Semakin tinggi = semakin lama tidak aktif.
- **Alasan**: Konteks absolut yang diperlukan bersama `recency_ratio` untuk interpretasi lengkap.
- **Edge Cases**: Tidak ada transaksi → 999

---

#### 2.2 `tx_count_90d`
- **Definisi**: `count(transaksi completed dalam 90 hari terakhir)`
- **Tipe**: Integer
- **Behavioral Meaning**: Volume transaksi dalam periode observasi. Representasi level engagement.
- **Alasan**: Memberikan konteks absolut untuk trend features.
- **Note on `activity_total`**: TIDAK menambahkan `activity_total` (sum dari 3 windows) karena semantik identik dengan `tx_count_90d` (3×30d = 90d). Menambahkannya adalah redundansi tanpa informasi baru.

---

#### 2.3 `spend_90d`
- **Definisi**: `sum(amount dari transaksi completed dalam 90 hari)`
- **Tipe**: Float (nominal)
- **Behavioral Meaning**: Total pengeluaran customer. Proxy untuk nilai ekonomis customer.

---

#### 2.4 `avg_tx_value`
- **Definisi**: `spend_90d / tx_count_90d` (0 jika tidak ada transaksi)
- **Tipe**: Float (nominal)
- **Behavioral Meaning**: Rata-rata nilai per transaksi. Customer high-value vs casual.

---

#### 2.5 `tenure_days`
- **Definisi**: `(as_of_date - customer.created_at).days`
- **Tipe**: Integer (hari)
- **Behavioral Meaning**: Lama menjadi customer. Customer baru memiliki risiko berbeda dari customer lama.

---

### 3. MAGNITUDE FEATURES (Activity Level)

---

#### 3.1 `activity_mean`
- **Definisi**: `mean([tx_count_w1, tx_count_w2, tx_count_w3])`
- **Tipe**: Float
- **Behavioral Meaning**: Tingkat aktivitas rata-rata customer. Membedakan customer aktif (mean tinggi) vs pasif (mean rendah).
- **Alasan**: Model memerlukan informasi magnitude agar penurunan trend pada customer aktif (mean=10, slope=-3) diperlakukan berbeda dari customer pasif (mean=0.5, slope=-0.5).
- **Relasi dengan `tx_count_90d`**: `activity_mean ≈ tx_count_90d / 3` — berkorelasi tapi bukan identik karena pembagian window bisa sedikit berbeda dari 90d continuous. Di-keep karena `activity_mean` diperlukan untuk `activity_cv` dan `trend_magnitude_interaction`.

---

#### 3.2 `recent_activity_avg`
- **Definisi**: `tx_count di window paling baru (30 hari terakhir)`  
  Sama dengan `tx_count_w3` (window terkini)
- **Tipe**: Float
- **Behavioral Meaning**: Aktivitas terkini. Customer yang masih aktif baru-baru ini memiliki risiko berbeda dari yang sudah lama dormant.
- **Alasan**: `activity_mean` merata-rata 3 periode sehingga bisa menyembunyikan fakta bahwa customer sudah berhenti di periode terakhir.

---

### 4. VOLATILITY FEATURES (Stability)

---

#### 4.1 `activity_std`
- **Definisi**: `std([tx_count_w1, tx_count_w2, tx_count_w3], ddof=0)`
  - Population standard deviation (bukan sample) karena N kecil (3)
- **Tipe**: Float (≥ 0)
- **Behavioral Meaning**: Seberapa stabil pola transaksi customer antar periode.
  - Rendah (< 0.5) = konsisten
  - Tinggi (> 2) = sangat fluktuatif
- **Alasan**: Customer dengan aktivitas berfluktuasi (misal: 5, 0, 3) lebih sulit diprediksi dan bisa menunjukkan perilaku tidak committed.

---

#### 4.2 `activity_cv`
- **Definisi**: `activity_std / activity_mean` (capped at `cv_cap`)
- **Tipe**: Float (0 ≤ cv ≤ cv_cap)
- **Behavioral Meaning**: Volatilitas relatif terhadap tingkat aktivitas.
  - `activity_std = 2` pada customer dengan `mean = 10` → CV = 0.2 (rendah, normal variasi)
  - `activity_std = 2` pada customer dengan `mean = 2` → CV = 1.0 (tinggi, sangat volatile)
- **Alasan**: CV menormalisasi volatilitas sehingga bisa dibandingkan antar customer dengan level aktivitas berbeda.
- **Edge Cases**:
  - `activity_mean < min_activity_threshold` → CV = 0.0 (bukan volatile, tapi dormant)
  - CV capped at `cv_cap` (10.0) untuk mencegah extreme values

---

#### 4.3 `spend_volatility_cv`
- **Definisi**: `std(spend per window) / mean(spend per window)` (capped)
- **Tipe**: Float (0 ≤ cv ≤ cv_cap)
- **Behavioral Meaning**: Stabilitas pola belanja nominal. Customer bisa stabil dalam frekuensi tapi volatile dalam nominal (atau sebaliknya).
- **Alasan**: Pelengkap `activity_cv`. Contoh: customer yang konsisten datang 2x/bulan tapi belanja kadang Rp50k kadang Rp500k menunjukkan pola berbeda dari yang konsisten Rp100k-150k.
- **Edge Cases**: Sama seperti `activity_cv`

---

### 5. INTERACTION FEATURE

---

#### 5.1 `trend_magnitude_interaction`
- **Definisi**: `frequency_trend_smoothed × activity_mean`
- **Tipe**: Float
- **Behavioral Meaning**: Menangkap bahwa **penurunan pada customer aktif lebih signifikan** dibanding customer pasif.
  - Customer aktif (mean=10) dengan trend menurun (slope=-2) → interaction = -20 (**ALERT**)
  - Customer pasif (mean=0.5) dengan trend menurun (slope=-0.5) → interaction = -0.25 (rendah)
- **Alasan**: Tanpa interaction, model memerlukan non-linear split yang kompleks untuk menangkap ini. Interaction feature menyederhanakan decision boundary.

---

### 6. NLP / COMMUNICATION FEATURES

---

#### 6.1 `avg_sentiment_score`
- **Definisi**: Rata-rata skor sentimen dari pesan customer dalam 30 hari terakhir
- **Source**: Pre-computed dari `customer_text_semantics` atau live SentimentService
- **Tipe**: Float (-1 sampai +1)
- **Behavioral Meaning**: Sentimen rata-rata. Negatif = ketidakpuasan, positif = satisfied.

---

#### 6.2 `complaint_ratio`
- **Definisi**: `jumlah pesan komplain / total pesan dalam 30 hari` (0-1)
- **Tipe**: Float (ratio)
- **Behavioral Meaning**: Proporsi pesan yang berisi komplain. Tinggi = customer tidak puas.
- **Edge Cases**: Tidak ada pesan → 0.0

---

#### 6.3 `msg_volatility`
- **Definisi**: Standard deviation dari daily message count dalam 30 hari terakhir
- **Tipe**: Float (≥ 0)
- **Behavioral Meaning**: Seberapa berfluktuasi pola komunikasi harian customer.

---

#### 6.4 `response_delay_mean`
- **Definisi**: Rata-rata waktu respons admin terhadap pesan customer (dalam detik)
- **Tipe**: Float (detik)
- **Behavioral Meaning**: Kualitas layanan yang diterima customer. Response lambat bisa berkontribusi pada disengagement.

---

## Anti-Patterns yang Dihindari

| ❌ Anti-Pattern | ✅ Solusi pada v3 |
|---|---|
| Raw trend tanpa smoothing | Semua trend menggunakan SMA/EMA sebelum slope |
| Trend tanpa konteks magnitude | `trend_magnitude_interaction` menambah konteks |
| Tidak handle user pasif | `activity_cv = 0` untuk user dormant, bukan infinite |
| Feature tanpa tujuan jelas | Setiap feature didokumentasikan dengan behavioral meaning |
| `activity_total` redundan | TIDAK ditambahkan — identik dengan `tx_count_90d` |
| Hard-coded parameters | `FeatureConfig` dataclass, configurable via config |

---

## Smoothing Methods

### Simple Moving Average (SMA) — Default
```
SMA_t = mean(series[max(0, t-w+1) : t+1])
```
- **Kelebihan**: Interpretable, stabil, tidak ada hyperparameter selain window
- **Kekurangan**: Memberikan bobot sama ke semua observasi dalam window

### Exponential Moving Average (EMA) — Optional
```
EMA_t = α × x_t + (1 - α) × EMA_{t-1}
EMA_0 = x_0
α = 2 / (window + 1)  # default jika tidak di-set manual
```
- **Kelebihan**: Lebih responsif terhadap perubahan terbaru
- **Kekurangan**: Bisa lebih sensitif terhadap noise

**Rekomendasi**: Gunakan SMA (default) untuk production. EMA bisa digunakan untuk eksperimen via `FeatureConfig(smoothing_method='ema')`.
