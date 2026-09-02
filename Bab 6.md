# BAB VI. HASIL DAN PEMBAHASAN

## 6.1 Pendahuluan Hasil dan Pembahasan

Bab ini menyajikan hasil penelitian yang dicapai setelah implementasi dan pengujian pada Bab V, kemudian membahas makna dari hasil tersebut secara kritis. Hasil yang dibahas mencakup kinerja model behavioral risk scoring, dampak hyperparameter tuning dan threshold tuning, keputusan tidak digunakannya gated logistic adjustment, peran NLP dalam sistem, serta kemampuan Recommendation Policy v2 sebagai pendukung keputusan. Pembahasan diorganisasikan berdasarkan tiga dimensi utama: (1) kesesuaian hasil model dengan tolok ukur ilmiah dari penelitian terdahulu, (2) analisis kesenjangan antara rancangan teoritis dan capaian implementasi aktual, serta (3) penilaian menyeluruh terhadap kemampuan sistem sebagai decision support tool. Prinsip utama yang dipegang dalam bab ini adalah integritas analitik: hasil yang lebih rendah dari ekspektasi awal maupun dari penelitian sejenis tidak tersembunyi, melainkan diurai secara mendalam untuk mengidentifikasi akar penyebabnya.

---

## 6.2 Hasil dan Pembahasan Kinerja Model Behavioral Risk Scoring

### 6.2.1 Evaluasi Baseline dan Model Aktif

Evaluasi kinerja model diawali dari baseline XGBoost sebagai titik kontrol. Baseline diperlukan untuk menilai apakah proses hyperparameter tuning dan threshold tuning benar-benar memberikan kontribusi terhadap model akhir, bukan hanya menghasilkan konfigurasi baru tanpa peningkatan yang terukur. Pada test split temporal, baseline XGBoost memperoleh ROC-AUC 0,8380 dan PR-AUC 0,9273. Nilai ini menunjukkan bahwa model berbasis transaksi sudah memiliki kemampuan diskriminasi yang kuat sebelum tuning dilakukan.

Setelah baseline ditetapkan, kandidat hasil tuning dievaluasi dengan guardrail konservatif. Model aktif yang dipilih adalah `gated_transaction_xgb_logistic v20260707_211306`, dengan komponen prediktif utama berupa XGBoost transaksi karena gated logistic adjustment tidak dipromosikan ke produksi. Ringkasan performa model aktif disajikan pada Tabel 6.1, sedangkan perbandingan rinci antara baseline dan kandidat tuned dibahas pada Subbab 6.2.2.

**Tabel 6.1 Ringkasan Metrik Evaluasi Model Aktif**

| Metrik | Nilai | Interpretasi |
|---|---:|---|
| ROC-AUC | 0,8426 | Kemampuan model aktif membedakan pelanggan berisiko dari yang tidak berisiko. |
| PR-AUC | 0,9286 | Performa model aktif pada kondisi distribusi kelas yang tidak seimbang. |
| Precision @0,39 | 0,8366 | Dari seluruh prediksi positif pada threshold operasional 0,39, 83,66% adalah benar. |
| Recall @0,39 | 0,9235 | Model aktif berhasil mendeteksi 92,35% dari seluruh kasus berisiko nyata. |
| F1-Score @0,39 | 0,8779 | Keseimbangan antara precision dan recall model aktif pada threshold 0,39. |

Berdasarkan hasil tersebut, model aktif memiliki performa yang cukup kuat untuk digunakan sebagai komponen pendukung keputusan operasional. Namun, angka pada Tabel 6.1 belum cukup untuk membuktikan kontribusi tuning karena tabel tersebut hanya menampilkan kondisi akhir model. Oleh karena itu, baseline tetap dibahas sebagai pembanding metodologis pada Subbab 6.2.2, sehingga pemilihan model aktif dapat ditelusuri sebagai hasil seleksi bertahap dari baseline.

![Visualisasi ROC Curve dan Precision-Recall Curve](images/gambar-6-1-roc-pr-curve.png)

**Gambar 6.1 Visualisasi ROC Curve dan Precision-Recall Curve Model Aktif/Tuned**

Selain metrik performa agregat, pengujian ketepatan model aktif juga dievaluasi menggunakan *Confusion Matrix* untuk melihat sebaran prediksi benar dan salah secara absolut pada data uji.

![Confusion Matrix Model Aktif](images/gambar-6-2-confusion-matrix.png)

**Gambar 6.2 Confusion Matrix Model Aktif pada Threshold 0,39**

**Tabel 6.2 *Confusion Matrix* Model Aktif**

| Aktual \ Prediksi | Prediksi Berisiko (Positif) | Prediksi Aman (Negatif) |
|---|---|---|
| **Aktual Berisiko (Positif)** | *True Positive* (TP) = 8.328 | *False Negative* (FN) = 690 |
| **Aktual Aman (Negatif)** | *False Positive* (FP) = 1.626 | *True Negative* (TN) = 1.737 |

Confusion matrix tersebut dihitung pada test split temporal model aktif dengan threshold evaluasi operasional 0,39. Pada test split ini terdapat 12.381 baris uji, terdiri atas 9.018 label positif dan 3.363 label negatif. Model menghasilkan 9.954 prediksi positif; sekitar 8.328 di antaranya benar positif dan 1.626 merupakan false positive. Perbedaan satuan desimal pada confusion matrix disebabkan oleh pembulatan nilai precision dan recall yang disimpan pada metadata model.

Nilai ROC-AUC sebesar 0,8426 berada dalam kategori "sangat baik" berdasarkan skala umum yang digunakan dalam literatur analitik prediktif (Imani et al., 2025), di mana ROC-AUC > 0,80 mengindikasikan model yang cukup reliabel untuk mendukung keputusan operasional. Yang lebih penting untuk dicermati adalah nilai PR-AUC sebesar 0,9286. Metrik ini relevan untuk mengevaluasi kemampuan model mempertahankan precision dan recall pada kelas positif, terutama ketika distribusi kelas tidak seimbang antarperiode observasi. Nilai PR-AUC mendekati 1,0 mengindikasikan bahwa model mampu memetakan pelanggan berisiko dengan kualitas precision-recall yang kuat.

Nilai Recall sebesar 0,9235 memiliki arti yang strategis dari perspektif bisnis: pada threshold operasional 0,39, model melewatkan sekitar 690 dari 9.018 kasus positif pada test split temporal, atau sekitar 7,65% pelanggan yang sesungguhnya berisiko. Dalam konteks retensi pelanggan, *false negative* memiliki biaya bisnis yang jauh lebih mahal dibandingkan *false positive*. Oleh karena itu, penurunan precision dibanding threshold 0,5 diterima karena recall dan F1-score meningkat secara bersamaan.

### 6.2.2 Pembahasan Dampak Hyperparameter dan Threshold Tuning

Hasil pengujian pada Bab V menunjukkan bahwa hyperparameter tuning memberikan peningkatan yang konservatif, bukan lompatan performa yang besar. Pada test split utama, baseline XGBoost memperoleh ROC-AUC 0,8380 dan PR-AUC 0,9273, sedangkan kandidat tuned memperoleh ROC-AUC 0,8426 dan PR-AUC 0,9286. Peningkatan ROC-AUC sebesar 0,0046 dan PR-AUC sebesar 0,0013 menunjukkan bahwa tuning memperbaiki kemampuan ranking probabilitas model, tetapi perbaikannya tetap terbatas karena sinyal utama masih berasal dari pola transaksi yang sama. Oleh karena itu, hasil tuning tidak ditafsirkan sebagai perubahan arsitektur yang radikal, melainkan sebagai penyempurnaan konfigurasi dari baseline yang sudah kuat.

**Tabel 6.3 Perbandingan Baseline dan Kandidat Tuned pada Test Split**

| Model | ROC-AUC | PR-AUC | Precision @0,39 | Recall @0,39 | F1 @0,39 | Prediksi Positif |
|---|---:|---:|---:|---:|---:|---:|
| Baseline XGBoost | 0,8380 | 0,9273 | 0,8512 | 0,8892 | 0,8698 | 9.421 |
| Kandidat Tuned | 0,8426 | 0,9286 | 0,8366 | 0,9235 | 0,8779 | 9.954 |
| Perubahan | +0,0046 | +0,0013 | -0,0146 | +0,0343 | +0,0081 | +533 |

Dampak yang lebih besar terlihat pada threshold operasional. Penggunaan threshold 0,39 meningkatkan recall dan F1-score dibanding threshold 0,50, dengan konsekuensi precision menurun. Secara teknis, threshold yang lebih rendah tidak membuat model "lebih pintar" dalam membedakan kelas karena ROC-AUC dan PR-AUC tidak berubah oleh threshold. Threshold hanya mengubah titik keputusan: semakin rendah threshold, semakin banyak customer diklasifikasikan berisiko. Pada sistem retensi pelanggan, trade-off ini dapat diterima karena tujuan utama sistem adalah mengurangi *false negative*, yaitu pelanggan berisiko yang tidak masuk prioritas tindak lanjut.

**Tabel 6.4 Hasil Threshold Sensitivity Baseline Model**

| Threshold | Precision | Recall | F1-Score | Prediksi Positif |
|---:|---:|---:|---:|---:|
| 0,30 | 0,8281 | 0,9312 | 0,8767 | 10.141 |
| 0,39 | 0,8512 | 0,8892 | 0,8698 | 9.421 |
| 0,40 | 0,8534 | 0,8829 | 0,8679 | 9.330 |
| 0,50 | 0,8763 | 0,8106 | 0,8422 | 8.342 |
| 0,60 | 0,8975 | 0,7292 | 0,8046 | 7.327 |
| 0,70 | 0,9191 | 0,6346 | 0,7508 | 6.227 |

Dengan demikian, kontribusi tuning pada penelitian ini bersifat operasional dan metodologis. Secara operasional, threshold 0,39 membuat sistem lebih sensitif terhadap potensi risiko pelanggan. Secara metodologis, penggunaan validation guardrail mencegah pemilihan konfigurasi yang hanya bagus pada satu metrik tetapi menurunkan metrik penting lain seperti PR-AUC, recall, atau F1-score. Hasil ini mendukung posisi bahwa tuning tidak cukup dinilai dari satu angka ROC-AUC, melainkan harus dikaitkan dengan tujuan keputusan bisnis yang dibantu oleh sistem.

![Pembahasan Trade-off Threshold Operasional](images/gambar-6-3-threshold-tradeoff.png)

**Gambar 6.3 Pembahasan Trade-off Threshold Operasional terhadap Precision, Recall, dan F1-Score**

### 6.2.3 Perbandingan dengan Penelitian Terdahulu

Untuk mengontekstualisasikan hasil di atas secara ilmiah, perlu dilakukan perbandingan sistematis dengan penelitian terkait yang menggunakan arsitektur dan domain serupa.

**Tabel 6.5 Perbandingan Kinerja Model dengan Penelitian Terdahulu**

| Penelitian | Algoritma Utama | Domain | ROC-AUC | F1-Score | Keterangan |
|---|---|---|---|---|---|
| Ardhani & Tania (2025) | XGBoost + SMOTE | Ritel / Layanan | ~0,87–0,91 | ~0,85–0,89 | Data bersih, label eksplisit |
| Imani et al. (2025) – Review | Ensemble Learning | Multi-domain | Rata-rata 0,82–0,90 | Rata-rata 0,78–0,86 | Review 50+ studi |
| Bhatnagar & Srivastava (2025) | XGBoost / LightGBM | Telekomunikasi | 0,89–0,93 | 0,83–0,88 | Data kontraktual, label pasti |
| Tan (2025) | XGBoost + SMOTE | Perbankan | 0,84–0,88 | 0,80–0,85 | Data tabular murni |
| **Penelitian ini** | **XGBoost (Gated)** | **Baby Spa Non-Kontraktual** | **0,8426** | **0,8779** | **Data operasional, temporal proxy label** |

![Perbandingan Kinerja Model dengan Penelitian Terdahulu](images/gambar-6-4-perbandingan-penelitian.png)

**Gambar 6.4 Visualisasi Perbandingan Kinerja Model dengan Penelitian Terdahulu**

Secara umum, hasil penelitian ini berada dalam rentang bawah-menengah dari distribusi kinerja yang dilaporkan penelitian terdahulu pada domain yang memiliki label churn eksplisit. Namun, perbandingan ini harus disertai catatan metodologis yang krusial:

Pertama, sebagian besar penelitian pembanding menggunakan dataset berupa **label churn eksplisit** (kontrak yang diputus, akun yang ditutup secara formal). Pada penelitian ini, label target adalah **temporal proxy label**—label yang didefinisikan secara operasional berdasarkan ketidakaktifan dalam *prediction window* 90 hari setelah *observation date*. Jenis label ini secara inheren lebih noisy dan kurang deterministik dibandingkan label eksplisit, sehingga sedikit penurunan metrik dari nilai tertinggi di literatur adalah hal yang dapat dijelaskan secara rasional.

Kedua, penelitian ini beroperasi pada domain **bisnis non-kontraktual skala kecil** (Baby Spa dan Pijat Laktasi) dengan hanya 2.423 customer eligible untuk scoring. Dataset dalam literatur pembanding umumnya berskala puluhan hingga ratusan ribu pelanggan, yang secara statistik memberikan lebih banyak sinyal bagi model untuk mempelajari pola yang kuat. Ukuran data yang lebih kecil cenderung menghasilkan lebih banyak varian pada estimasi metrik.

Ketiga, arsitektur yang dipilih secara sengaja menempatkan XGBoost sebagai model berbasis transaksi (*unimodal*) tanpa fusi paksa fitur NLP, karena data komunikasi yang tersedia belum mencukupi untuk mendukung integrasi multimodal yang stabil. Memaksakan fusi multimodal pada kondisi seperti ini, sebagaimana ditunjukkan oleh Zou et al. (2026), justru akan menurunkan kualitas prediksi akibat *semantic shift*. Dengan demikian, hasil ROC-AUC 0,8426 yang dicapai melalui model aktif berbasis XGBoost transaksi dapat diinterpretasikan sebagai bukti bahwa basis transaksional sistem memiliki fondasi yang kuat dan tidak bergantung pada sinyal NLP yang belum matang.

### 6.2.4 Analisis Keputusan Fail-Closed pada Gated Logistic Adjustment

Salah satu temuan paling penting dalam penelitian ini adalah bahwa **komponen gated logistic adjustment tidak dipakai pada sistem saat ini** (`adjustment_enabled=false`) karena mekanisme *fail-closed*. Hal ini terjadi setelah validasi komparatif pada 279 panel rows dari 47 customer yang memiliki histori komunikasi pada kohort training:

**Tabel 6.6 Perbandingan Kinerja pada Kohort Komunikasi**

| Model | ROC-AUC | PR-AUC | Keputusan |
|---|---|---|---|
| Base XGBoost (transaksi saja) | 0,8433 | 0,4935 | Dipilih sebagai model produksi |
| Gated Logistic Adjustment | 0,8160 | 0,4656 | Ditolak, tidak dipromosikan |
| Penurunan (delta) | -0,0273 | -0,0279 | Batas toleransi terlampaui |

Penurunan ROC-AUC sebesar 0,0273 dan PR-AUC sebesar 0,0279 pada kohort komunikasi menyebabkan kandidat model gated tidak dipromosikan ke produksi. Keputusan ini sejalan dengan prinsip *conservative unimodal fallback* yang divalidasi oleh Zou et al. (2026): ketika modalitas sekunder (teks percakapan) tidak memiliki cukup data untuk menghasilkan sinyal yang reliabel, mempertahankan modalitas primer (transaksi) sebagai satu-satunya dasar keputusan adalah mekanisme keamanan yang secara ilmiah terbukti lebih aman. Hasil ini tidak menunjukkan bahwa pendekatan gated secara umum lebih buruk daripada model transaksi, melainkan bahwa pada cakupan data komunikasi penelitian ini, sinyal WhatsApp belum cukup stabil untuk meningkatkan performa dibanding base model.

Penyebab utama kegagalan komponen adjustment ini dapat ditelusuri pada dua faktor: (1) **sparsitas data komunikasi**—hanya 109 dari 2.423 customer (4,5%) yang memiliki pesan *trusted*, dan hanya 47 customer (1,9%) yang muncul pada kohort training dengan data komunikasi—sehingga logistic adjuster tidak mendapat sinyal yang cukup untuk membangun bobot yang general; (2) **heterogenitas konteks percakapan**—data WhatsApp Mamina bercampur antara reservasi, konsultasi laktasi, dan keluhan operasional, sehingga sinyal yang secara teoritis diharapkan berkaitan dengan penurunan aktivitas belum cukup terisolasi secara statistik.

Penelitian ini **tidak menyembunyikan kegagalan parsial** komponen gated adjustment ini. Sebaliknya, penelitian ini berargumen bahwa arsitektur yang mampu mendeteksi dan mencegah degradasi model secara otomatis (*fail-closed mechanism*) adalah kontribusi desain sistem yang memiliki nilai ilmiah tersendiri, sebagaimana diperkuat oleh Han et al. (2022) mengenai pentingnya *sparse gating* tingkat sampel.

### 6.2.5 Hasil Explainability Model

Hasil explainability model disajikan melalui feature importance global dan SHAP. Feature importance XGBoost digunakan untuk melihat fitur yang paling sering berkontribusi dalam struktur tree secara agregat, sedangkan SHAP digunakan untuk menjelaskan kontribusi fitur terhadap prediksi customer tertentu.

![Feature Importance XGBoost](images/gambar-6-5-feature-importance.png)

**Gambar 6.5 Visualisasi Feature Importance Model XGBoost**

Pada risk scoring terbaru, SHAP cache berhasil dibuat untuk seluruh 2.423 prediction model aktif. Setiap cache menyimpan nilai kontribusi, lima alasan teratas, model version, feature schema hash, explanation type, dan temporal anchor. Hasil ini menunjukkan bahwa sistem tidak hanya menghasilkan skor risiko, tetapi juga menyediakan penjelasan yang dapat ditelusuri pada level customer.

![SHAP Summary Plot](images/gambar-6-6-shap-summary.png)

**Gambar 6.6 Visualisasi SHAP Summary Plot Model Aktif**

---

## 6.3 Hasil dan Pembahasan Peran NLP dalam Sistem

### 6.3.1 Reorientasi Peran NLP: Dari Prediktor ke Customer Voice Provider

Meskipun komponen NLP tidak berkontribusi pada *risk score* model produksi saat ini, penelitian ini berhasil menunjukkan bahwa NLP dapat memainkan peran yang sama pentingnya dalam ekosistem analitik prediktif, yaitu sebagai **penyedia konteks operasional (Customer Voice Provider)** untuk sistem rekomendasi.

Dari 109 customer yang memiliki agregat semantik, 100 di antaranya memiliki *customer voice* yang relevan terhadap *prediction window* terbaru. Konteks ini dipetakan menjadi:
- **42 intent reservasi**: Menunjukkan pelanggan yang masih berniat bertransaksi namun belum terealisasi.
- **31 indikasi friksi operasional**: Memberikan sinyal konteks yang perlu ditinjau sebelum diperlakukan sebagai keluhan layanan.
- **25 kebutuhan layanan**: Membuka peluang upselling atau cross-selling yang kontekstual.

Informasi ini, meskipun tidak mengubah *risk score*, secara langsung memperkaya kualitas **Recommendation Policy v2**. Sistem menghasilkan 2.423 rekomendasi, di mana 100 (4,1%) dipersonalisasi menggunakan *customer voice* dan 2.323 (95,9%) menggunakan *fallback* berbasis kondisi transaksi. Distribusi ini mencerminkan keterbatasan data aktual, bukan keterbatasan arsitektur sistem.

### 6.3.2 Keterbatasan Klasifikasi Sentimen pada Teks Informal

Salah satu tantangan teknis yang dihadapi adalah bahwa **complaint_ratio** perlu dihitung melalui aturan deterministik kontekstual, bukan dari klasifikasi IndoBERTweet maupun pencocokan keyword sederhana. IndoBERTweet tetap berguna untuk membaca polaritas pesan pada level per pesan, misalnya membedakan pesan bernada negatif, netral, atau positif. Namun, polaritas negatif tidak selalu identik dengan komplain layanan. Pada domain Mamina, konsultasi laktasi atau diskusi *caregiving* dapat bernada negatif karena membahas kondisi bayi atau ibu, bukan karena pelanggan tidak puas terhadap layanan. Selain itu, pencocokan keyword sederhana juga rentan salah karena kata seperti "keluhan" sering muncul sebagai field pada form reservasi, bukan sebagai komplain terhadap Mamina.

Temuan ini mengonfirmasi argumen Hase et al. (2023) dan Indriani et al. (2024) bahwa model NLP berbasis supervised learning, meskipun unggul dalam tes benchmark, memerlukan adaptasi kontekstual yang cermat ketika dihadapkan pada domain sangat spesifik. Kombinasi antara klasifikasi sentimen (IndoBERTweet untuk *polarity*) dan ekstraksi deterministik kontekstual untuk *complaint intent* adalah solusi hibrida yang lebih robust daripada mengandalkan satu pendekatan saja.

---

## 6.4 Hasil dan Pembahasan Recommendation Policy v2 dan Decision Support

### 6.4.1 Kinerja dan Cakupan Rekomendasi

Recommendation Policy v2 berhasil menghasilkan rekomendasi terstruktur untuk seluruh 2.423 pelanggan yang di-*score*. Setiap rekomendasi mencakup: tujuan tindakan (*objective*), waktu optimal (*timing*), saluran komunikasi (*channel*), contoh pembuka pesan, kode alasan (*reason codes*), dan sumber data rekomendasi (*provenance*).

Variasi rekomendasi yang dihasilkan adalah 13 judul rekomendasi dan 12 variasi contoh pembuka. Keterbatasan variasi ini secara langsung berkaitan dengan dominasi kondisi *dormant* pada distribusi sinyal transaksi (1.539 dari 2.423 = 63,5%).

**Tabel 6.7 Distribusi Kondisi Transaksi pada Recommendation Policy v2**

| Kondisi Transaksi | Jumlah | Persentase |
|---|---|---|
| Dormant | 1.539 | 63,5% |
| New Customer | 266 | 11,0% |
| Frequency Decline | 182 | 7,5% |
| Overdue | 179 | 7,4% |
| Routine | 94 | 3,9% |
| Homecare | 84 | 3,5% |
| Loyal | 42 | 1,7% |
| Transaction Quality | 23 | 0,9% |
| Spend Decline | 14 | 0,6% |

Dominasi kondisi *dormant* mengindikasikan bahwa **mayoritas pelanggan Mamina saat ini berada dalam status inaktif jangka panjang**, sebuah temuan bisnis yang penting dan berdiri sendiri sebagai wawasan operasional di luar konteks model ML. Hal ini menegaskan argumentasi awal penelitian bahwa bisnis non-kontraktual rentan terhadap *silent attrition* yang tidak terdeteksi melalui metrik konvensional.

### 6.4.2 Validasi Konseptual: Pemisahan SHAP dan Recommendation

Keputusan desain yang paling kritis dari penelitian ini adalah **pemisahan fungsi epistemik** antara SHAP dan Recommendation Policy. SHAP digunakan untuk menjelaskan *output model ML* (mengapa *risk score* seorang pelanggan tinggi), sedangkan Recommendation Policy dibangun dari kondisi transaksi dan *customer voice* (mengapa dan bagaimana admin harus merespons).

Pemisahan ini sengaja dibuat untuk menghindari dua risiko: (1) *over-reliance* pada model—admin yang hanya mengandalkan SHAP tanpa konteks percakapan akan kehilangan nuansa yang tidak dapat dikuantifikasi; dan (2) *under-reliance* pada model—mengabaikan *risk score* karena merasa rekomendasi sudah "cukup". Dengan memisahkan dua lapisan ini, sistem mendorong pengambilan keputusan yang komprehensif dan berbasis manusia (*human-in-the-loop*).

---

## 6.5 Hasil dan Pembahasan Arsitektur Sistem dan Keputusan Teknis

### 6.5.1 Validasi Arsitektur Gated terhadap Literatur

Penelitian ini mengimplementasikan arsitektur *gated logistic adjustment* yang secara konseptual sejajar dengan kerangka *Ensemble with Conditional Feature Fusion* (ECFF) oleh Kunhoth et al. (2024-2026). Justifikasi akademis tersebut kini dapat diverifikasi empiris: mekanisme *gating* pada penelitian ini benar-benar bekerja sebagaimana dirancang—ia mengevaluasi kesiapan modalitas sekunder, dan ketika sinyal NLP tidak mencukupi, ia menutup jalur fusi secara otomatis.

Dari perspektif *sparse gating* tingkat sampel (Han et al., 2022), validasi gated adjustment menunjukkan bahwa hanya 47 customer pada kohort training/validasi yang memiliki histori komunikasi memadai untuk menguji penyesuaian logistic regression. Pada data operasional terbaru, 2.423 pelanggan tetap di-*score* oleh base XGBoost transaksi, sedangkan logistic adjustment tidak diterapkan karena `adjustment_enabled=false`. Hal ini menunjukkan bahwa sistem mampu menahan jalur fusi ketika modalitas komunikasi belum cukup kuat, sehingga populasi dengan sinyal komunikasi terbatas lebih aman ditangani menggunakan model transaksional murni.

### 6.5.2 Evaluasi Mekanisme Identity Resolution dan PPRL

Sistem berhasil melakukan *identity resolution* antara log WhatsApp dan database transaksi menggunakan *hashing* SHA-256 deterministik. Dari 25.346 pesan yang diimpor, 11.993 pesan berhasil dihubungkan ke 109 customer terdaftar dengan tingkat kepercayaan (*confidence*) lebih dari atau sama dengan 0,7. Sebanyak 358 profil teridentifikasi sebagai *provisional lead*—nomor yang menghubungi layanan namun tidak memiliki rekam transaksi yang dapat diverifikasi.

Nilai penting dari mekanisme ini tidak hanya pada angka keberhasilannya, tetapi pada **prinsip arsitekturalnya**: seluruh proses pencocokan dilakukan menggunakan *phone_hash* (bukan nomor telepon asli), memastikan bahwa model ML tidak pernah menyentuh PII secara langsung. Hal ini merupakan implementasi nyata dari prinsip *privacy-by-design* yang diadvokasi oleh ENISA (2026) dan kerangka PPRL.

---

## 6.6 Implikasi dan Kontribusi Penelitian

### 6.6.1 Implikasi Teoritis

Penelitian ini memberikan beberapa kontribusi konseptual bagi literatur:

1. **Validasi empiris mekanisme fail-closed pada domain non-kontraktual skala kecil.** Penelitian ini mendokumentasikan hasil pengujian penyesuaian sinyal komunikasi ketika cakupan datanya tidak mencukupi. Mekanisme validasi menonaktifkan penyesuaian tersebut dan mempertahankan model transaksi sebagai model produksi, sehingga tidak ada klaim bahwa skor aktif dihasilkan melalui fusi multimodal.

2. **Demonstrasi peran ganda NLP pada sistem prediktif.** NLP tidak harus berfungsi sebagai fitur prediktif langsung untuk memberikan nilai dalam sistem intelijen pelanggan. Pemanfaatannya sebagai *customer voice provider* pada lapisan rekomendasi adalah model arsitektur yang dapat diadopsi pada konteks serupa.

3. **Kontribusi pada metodologi temporal proxy label pada bisnis non-kontraktual.** Penelitian ini mendokumentasikan secara rinci prosedur pembangunan dataset *panel-based* dengan *rolling observation window* dan *temporal cutoff* untuk mencegah *data leakage*, yang dapat dijadikan referensi untuk penelitian serupa di bisnis jasa non-kontraktual di Indonesia.

### 6.6.2 Implikasi Praktis

1. **Sistem mampu mengidentifikasi segmen pelanggan yang perlu perhatian segera.** Distribusi prediksi menunjukkan 1.265 pelanggan (52,2%) berada pada kategori *high risk*. Tanpa sistem seperti ini, identifikasi tersebut hanya dapat dilakukan melalui inspeksi manual.

2. **Rekomendasi berbasis kondisi transaksi sudah langsung operasional.** Meskipun *customer voice* baru tercakup untuk 100 dari 2.423 pelanggan, rekomendasi berbasis transaksi sudah mencakup 100% pelanggan *scored* dengan saran yang kontekstual dan dapat ditelusuri.

3. **Sistem memiliki kapasitas untuk berkembang seiring bertambahnya data.** Ketika cakupan data komunikasi meningkat, komponen gated adjustment dapat diaktifkan kembali tanpa perlu mengubah arsitektur sistem. Sistem ini bersifat *data-adaptive*, bukan *data-rigid*.

---

## 6.7 Keterbatasan dan Rekomendasi Penelitian Lanjutan

### 6.7.1 Keterbatasan yang Teridentifikasi

1. **Keterbatasan validasi eksternal.** Evaluasi dilakukan sepenuhnya pada satu bisnis Baby Spa dan Pijat Laktasi. Validitas model dan kebijakan rekomendasi pada domain bisnis lain atau periode waktu yang berbeda memerlukan pengujian eksternal yang belum dilakukan dalam cakupan penelitian ini.

2. **Keterbatasan uji pengguna (user testing) terstruktur.** Meskipun sistem telah diimplementasikan dan antarmuka telah diuji secara fungsional (black-box testing), penelitian ini belum mencakup pengujian kegunaan (*usability testing*) terstruktur dengan responden dari manajemen Mamina menggunakan instrumen seperti System Usability Scale (SUS) atau User Experience Questionnaire (UEQ).

3. **Keterbatasan evaluasi outcome rekomendasi.** Recommendation Policy v2 belum dievaluasi berdasarkan hasil nyata (*outcome*): apakah pelanggan yang menerima intervensi berbasis rekomendasi sistem menunjukkan perbaikan aktivitas pada periode berikutnya? Evaluasi ini memerlukan deployment longitudinal yang melampaui cakupan penelitian ini.

4. **Keterbatasan label target.** Penggunaan *temporal proxy label* berbasis ketidakaktifan, meskipun merupakan pendekatan yang lazim untuk bisnis non-kontraktual, tetap mengandung ketidakpastian. Seorang pelanggan yang tidak melakukan transaksi dalam 90 hari belum tentu telah berpindah ke kompetitor.

### 6.7.2 Rekomendasi untuk Penelitian Lanjutan

1. **Perluasan cakupan data komunikasi.** Menerapkan mekanisme *consent* aktif dan normalisasi nomor telepon yang lebih agresif akan meningkatkan *text coverage* dari 4,5% saat ini dan membuka jalan untuk mengaktifkan *gated logistic adjustment* di masa depan.

2. **Uji coba active learning untuk complaint labeling.** Pembuatan dataset berlabel secara manual pada sampel percakapan, kemudian digunakan untuk melatih *complaint intent classifier* khusus domain Mamina, dapat meningkatkan presisi deteksi keluhan secara signifikan.

3. **Evaluasi longitudinal Recommendation Policy.** Penelitian lanjutan dapat merancang desain evaluasi terkontrol (*A/B testing* atau *quasi-experimental*) untuk mengukur apakah intervensi berbasis Recommendation Policy v2 secara nyata menurunkan tingkat *behavioral disengagement* pelanggan.

4. **Penerapan usability testing terstruktur.** Melibatkan pengguna akhir (admin, manajer) dalam sesi pengujian terstruktur menggunakan instrumen SUS atau TAM (*Technology Acceptance Model*) akan memberikan validasi holistik terhadap efektivitas sistem sebagai alat bantu keputusan.

5. **Eksplorasi label proksi alternatif.** Mendefinisikan label target menggunakan kombinasi ketidakaktifan transaksi dan penurunan sentimen komunikasi dapat menghasilkan *proxy label* yang lebih selaras dengan kondisi aktual pelanggan yang berisiko.

---

## 6.8 Ringkasan Hasil dan Pembahasan

Secara keseluruhan, penelitian ini berhasil membangun dan memvalidasi sistem intelijen pelanggan berbasis *behavioral risk scoring* yang fungsional, transparan, dan dapat ditelusuri (*auditable*). Kontribusi utamanya bukan pada pencapaian nilai metrik yang melampaui semua penelitian terdahulu, melainkan pada:

1. **Demonstrasi arsitektur yang jujur terhadap keterbatasan datanya sendiri.** Sistem ini tahu kapan harus berhenti (*fail-closed*) dan tahu kapan datanya tidak mencukupi untuk membuat klaim yang lebih kuat.
2. **Pemisahan peran yang tepat antara ML, SHAP, dan Recommendation Policy**, sehingga sistem mendorong pengambilan keputusan manusia yang berbasis bukti (*evidence-based*), bukan otomatisasi keputusan secara buta.
3. **Penerapan prinsip-prinsip privasi data (PPRL, hashing SHA-256)** yang menjamin sistem ini siap digunakan pada lingkungan yang membutuhkan kepatuhan terhadap regulasi perlindungan data.
4. **Fondasi arsitektur yang bersifat data-adaptive**: ketika data komunikasi tumbuh di masa mendatang, gated adjustment dapat diaktifkan tanpa perubahan arsitektur sistem.

Dengan demikian, meskipun terdapat keterbatasan pada sisi cakupan data NLP dan validasi outcome rekomendasi, penelitian ini memberikan kontribusi yang valid dan relevan bagi literatur analitik prediktif pada domain bisnis jasa non-kontraktual skala kecil menengah di Indonesia.
