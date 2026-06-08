import {
  AlertCircle,
  CheckCircle2,
  Info,
  TrendingUp,
  GitBranch,
  Calendar,
  Users,
  ShieldCheck,
  Zap,
  Award,
  Layers,
  HelpCircle,
  ArrowRightLeft,
  Sparkles,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Cell,
} from "recharts";
import Card from "../components/common/Card";
import EmptyState from "../components/common/EmptyState";
import {
  useFeatureImportance,
  useModelEvaluation,
  useRiskDistribution,
  useThresholdSensitivity,
} from "../hooks/usePipeline";

const metricDescriptions = {
  roc_auc: "Mengukur keandalan pemisahan segmen model dalam membedakan pelanggan berisiko tinggi dan rendah secara konsisten.",
  pr_auc: "Metrik paling stabil & tepercaya untuk mengevaluasi data perilaku tidak seimbang (minoritas berisiko disengagement).",
  precision: "Akurasi penargetan: Dari seluruh pelanggan yang ditandai berisiko tinggi, persentase yang benar-benar mengalami penurunan aktivitas.",
  recall: "Sensitivitas tangkapan: Rasio total pelanggan berisiko tinggi yang berhasil diidentifikasi awal oleh sistem.",
  f1_score: "Rata-rata harmonis yang menyeimbangkan presisi penargetan dan sensitivitas tangkapan secara optimal.",
};

const metricLabels = {
  roc_auc: "ROC-AUC",
  pr_auc: "PR-AUC",
  precision: "Precision",
  recall: "Recall",
  f1_score: "F1-Score",
};

function formatMetric(value) {
  return value === null || value === undefined ? "-" : Number(value).toFixed(3);
}

function formatGain(value) {
  if (value === null || value === undefined) return "-";
  const numberValue = Number(value);
  const sign = numberValue > 0 ? "+" : "";
  return `${sign}${numberValue.toFixed(3)}`;
}

export default function ModelEvaluation() {
  const evaluation = useModelEvaluation();
  const importance = useFeatureImportance();
  const threshold = useThresholdSensitivity();
  const distribution = useRiskDistribution();

  if (evaluation.isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-stone-500 gap-3">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-pink-500 border-t-transparent" />
        <span className="font-semibold text-sm">Memuat metrik evaluasi model...</span>
      </div>
    );
  }

  if (evaluation.error) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700 flex items-start gap-4">
        <AlertCircle className="h-6 w-6 text-red-600 shrink-0 mt-0.5" />
        <div>
          <h3 className="font-bold text-base">Gagal Memuat Evaluasi Model</h3>
          <p className="text-sm mt-1 text-red-600/90">Terjadi kesalahan saat mengambil metrik model dari server. Pastikan server backend Anda berjalan dengan benar.</p>
        </div>
      </div>
    );
  }

  const data = evaluation.data || {};
  const overview = data.overview || {};
  const summary = data.business_summary;
  const metrics = data.technical_metrics;
  const comparisonRows = data.baseline_comparison?.rows || [];
  const modelMetadata = data.model_metadata || {};
  const thresholdRows = threshold.data?.rows || [];
  const importanceRows = importance.data?.features || [];
  const riskCounts = distribution.data?.distribution || {};
  
  const riskChart = [
    { name: "Low Risk", value: riskCounts.low || 0, color: "#10b981" },
    { name: "Medium Risk", value: riskCounts.medium || 0, color: "#f59e0b" },
    { name: "High Risk", value: riskCounts.high || 0, color: "#ef4444" },
  ];

  return (
    <div className="space-y-8 pb-12">
      {/* HEADER BANNER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-pink-600 text-xs font-bold uppercase tracking-wider">
            <ShieldCheck className="h-4 w-4" />
            Decision Support System (DSS) Validation
          </div>
          <h1 className="text-2xl font-bold text-primary-900 mt-1">Model Evaluation & Metrics</h1>
          <p className="mt-1 text-sm text-stone-500">
            Halaman pembuktian akademis dan audit performa model kecerdasan buatan (ML) untuk mengestimasi disengagement risk.
          </p>
        </div>
      </div>

      {/* SECTION 1: MODEL OVERVIEW */}
      <div className="bg-white rounded-2xl border border-primary-100 shadow-sm overflow-hidden">
        <div className="border-b border-primary-50 bg-stone-50/55 p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary-100 text-primary-700">
              <Layers className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-primary-900">Model Meta-Overview</h2>
              <p className="text-xs text-stone-500 mt-0.5">Spesifikasi teknis, versi, dan volume data latih model aktif.</p>
            </div>
          </div>
        </div>
        <div className="p-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
            <MetricCard 
              label="Model Version" 
              value={overview.model_version || "-"} 
              icon={<GitBranch className="h-4 w-4 text-purple-500" />}
              bgColor="bg-purple-50"
            />
            <MetricCard 
              label="Feature Schema" 
              value={overview.feature_schema_version || "-"} 
              icon={<Award className="h-4 w-4 text-pink-500" />}
              bgColor="bg-pink-50"
            />
            <MetricCard 
              label="Training Date" 
              value={overview.training_date || "-"} 
              icon={<Calendar className="h-4 w-4 text-blue-500" />}
              bgColor="bg-blue-50"
            />
            <MetricCard 
              label="Training Samples" 
              value={overview.training_samples?.toLocaleString("id-ID") ?? "-"} 
              icon={<Users className="h-4 w-4 text-emerald-500" />}
              bgColor="bg-emerald-50"
            />
            <MetricCard 
              label="Test Samples" 
              value={overview.test_samples?.toLocaleString("id-ID") ?? "-"} 
              icon={<ArrowRightLeft className="h-4 w-4 text-amber-500" />}
              bgColor="bg-amber-50"
            />
            <MetricCard 
              label="Operational Status" 
              value={overview.is_active ? "Aktif (Produksi)" : "Tidak aktif"} 
              icon={<Zap className="h-4 w-4 text-indigo-500" />}
              bgColor={overview.is_active ? "bg-emerald-50/70 text-emerald-800" : "bg-stone-100 text-stone-700"}
              valueClassName={overview.is_active ? "text-emerald-700 font-extrabold" : ""}
            />
          </div>
        </div>
      </div>

      {/* SECTION 2: BUSINESS-FRIENDLY SUMMARY */}
      <div className="bg-white rounded-2xl border border-primary-100 shadow-sm overflow-hidden">
        <div className="border-b border-primary-50 bg-stone-50/55 p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-pink-100 text-pink-700">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-primary-900">Business-Friendly Summary</h2>
              <p className="text-xs text-stone-500 mt-0.5">Penjelasan berbasis narasi bisnis Mamina Baby Spa untuk keperluan non-teknis.</p>
            </div>
          </div>
        </div>
        <div className="p-6">
          {summary ? (
            <div className="grid gap-6 md:grid-cols-3">
              <SummaryItem
                icon={summary.performance_status === "Baik" ? <CheckCircle2 className="h-6 w-6 text-emerald-600" /> : <AlertCircle className="h-6 w-6 text-rose-600" />}
                label="Status Performa Model"
                value={summary.performance_status}
                bgColor={summary.performance_status === "Baik" ? "from-emerald-50 to-teal-50/30 border-emerald-100" : "from-rose-50 to-orange-50/30 border-rose-100"}
              />
              <SummaryItem 
                icon={<TrendingUp className="h-6 w-6 text-purple-600" />} 
                label="Kemampuan Deteksi Pelanggan Berisiko" 
                value={summary.risk_detection} 
                bgColor="from-purple-50 to-pink-50/30 border-purple-100"
              />
              <SummaryItem 
                icon={<Info className="h-6 w-6 text-blue-600" />} 
                label="Catatan Pemakaian & Rekomendasi" 
                value={summary.usage_note} 
                bgColor="from-blue-50 to-indigo-50/30 border-blue-100"
              />
            </div>
          ) : (
            <EmptyState 
              icon="-" 
              title="Ringkasan bisnis belum tersedia" 
              description={data.empty_message || "Jalankan proses pelatihan ulang model (Retrain Model) terlebih dahulu untuk memunculkan ringkasan bisnis."} 
            />
          )}
        </div>
      </div>

      {/* SECTION 3: BASELINE VS MULTIMODAL COMPARISON */}
      <div className="bg-white rounded-2xl border border-primary-100 shadow-sm overflow-hidden">
        <div className="border-b border-primary-50 bg-stone-50/55 p-6">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-indigo-100 text-indigo-700">
              <ArrowRightLeft className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-primary-900">Baseline vs Multimodal Comparison</h2>
              <p className="text-xs text-stone-500 mt-0.5">Validasi H2: dampak penambahan sinyal interaksi WhatsApp/NLP terhadap baseline transaksi.</p>
            </div>
          </div>
        </div>
        <div className="p-6 space-y-6">
          {comparisonRows.length ? (
            <>
              <div className="overflow-hidden rounded-xl border border-stone-200">
                <div className="overflow-x-auto">
                  <table className="min-w-full text-sm divide-y divide-stone-200">
                    <thead className="bg-stone-50 text-left text-xs font-bold uppercase tracking-wider text-stone-600">
                      <tr>
                        <th className="px-6 py-4">Metric</th>
                        <th className="px-6 py-4">Baseline</th>
                        <th className="px-6 py-4">Multimodal</th>
                        <th className="px-6 py-4">Improvement</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-stone-100 bg-white">
                      {comparisonRows.map((row) => (
                        <tr key={row.metric} className="hover:bg-primary-50/30 transition-all">
                          <td className="px-6 py-4 font-semibold text-stone-800">{row.label}</td>
                          <td className="px-6 py-4 font-mono text-stone-700">{formatMetric(row.baseline)}</td>
                          <td className="px-6 py-4 font-mono font-bold text-primary-900">{formatMetric(row.multimodal)}</td>
                          <td className={`px-6 py-4 font-mono font-bold ${Number(row.improvement || 0) >= 0 ? "text-emerald-700" : "text-rose-700"}`}>
                            {formatGain(row.improvement)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="rounded-xl border border-indigo-100 bg-indigo-50/60 p-5">
                <div className="flex items-start gap-3">
                  <Info className="h-5 w-5 text-indigo-700 shrink-0 mt-0.5" />
                  <p className="text-sm font-medium leading-relaxed text-indigo-950">
                    {data.comparison_interpretation}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <ModelMetadataPanel title="Baseline" metadata={modelMetadata.baseline} />
                <ModelMetadataPanel title="Multimodal" metadata={modelMetadata.multimodal} />
              </div>
            </>
          ) : (
            <EmptyState 
              icon="-" 
              title="Perbandingan baseline belum tersedia" 
              description="Jalankan Retrain Model untuk melatih baseline transaksi dan model multimodal secara bersamaan." 
            />
          )}
        </div>
      </div>

      {/* SECTION 3: TECHNICAL METRICS WITH GAUGES */}
      <div className="bg-white rounded-2xl border border-primary-100 shadow-sm overflow-hidden">
        <div className="border-b border-primary-50 bg-stone-50/55 p-6">
          <h2 className="text-lg font-bold text-primary-900">Key AI Performance Metrics</h2>
          <p className="text-xs text-stone-500 mt-0.5">Penilaian akurasi matematis model berdasarkan hasil validasi test set.</p>
        </div>
        <div className="p-6">
          {metrics ? (
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-5">
              {Object.keys(metricLabels).map((key) => {
                const rawVal = metrics[key];
                const percentage = rawVal !== null && rawVal !== undefined ? Math.min(Number(rawVal) * 100, 100) : 0;
                
                return (
                  <div key={key} className="relative group overflow-hidden rounded-2xl border border-stone-200 bg-white p-5 transition-all hover:-translate-y-1 hover:shadow-md hover:border-pink-300">
                    <div className="absolute top-0 right-0 h-16 w-16 -mr-4 -mt-4 rounded-full bg-pink-50/30 transition-transform group-hover:scale-125" />
                    
                    <span className="text-xs font-bold text-stone-400 tracking-wide uppercase">{metricLabels[key]}</span>
                    
                    <div className="mt-3 flex items-baseline gap-1">
                      <span className="text-3xl font-extrabold text-primary-900 tracking-tight">
                        {formatMetric(rawVal)}
                      </span>
                    </div>

                    {/* Progress Bar Visualizer */}
                    <div className="mt-4 space-y-1.5">
                      <div className="flex justify-between text-[10px] text-stone-500 font-semibold">
                        <span>Akurasi Nilai</span>
                        <span>{percentage.toFixed(1)}%</span>
                      </div>
                      <div className="h-2 w-full rounded-full bg-stone-100 overflow-hidden">
                        <div 
                          className="h-full rounded-full bg-gradient-to-r from-pink-500 to-purple-600 transition-all duration-1000" 
                          style={{ width: `${percentage}%` }}
                        />
                      </div>
                    </div>

                    <p className="mt-4 text-[11px] leading-relaxed text-stone-500">
                      {metricDescriptions[key]}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState 
              icon="-" 
              title="Metrik teknis belum tersedia" 
              description={data.empty_message || "Lakukan pelatihan model terlebih dahulu di modul ML Pipeline."} 
            />
          )}
        </div>
      </div>

      {/* SECTION 4: THRESHOLD SENSITIVITY DESIGNED */}
      <div className="bg-white rounded-2xl border border-primary-100 shadow-sm overflow-hidden">
        <div className="border-b border-primary-50 bg-stone-50/55 p-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-2">
            <div>
              <h2 className="text-lg font-bold text-primary-900">Operational Threshold Sensitivity</h2>
              <p className="text-xs text-stone-500 mt-0.5">Dampak pemilihan batas risiko (threshold) terhadap akurasi presisi sasaran dan sensitivitas tangkapan.</p>
            </div>
            <div className="flex items-center gap-1.5 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-3 py-1 self-start md:self-auto">
              <HelpCircle className="h-4 w-4 text-amber-600 shrink-0" />
              <span>F1-Score tinggi dianjurkan untuk operasional seimbang.</span>
            </div>
          </div>
        </div>
        <div className="p-6">
          {thresholdRows.length ? (
            <div className="overflow-hidden rounded-xl border border-stone-200">
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm divide-y divide-stone-200">
                  <thead className="bg-stone-50 text-left text-xs font-bold uppercase tracking-wider text-stone-600">
                    <tr>
                      <th className="px-6 py-4">Batas Skor (Threshold)</th>
                      <th className="px-6 py-4">Precision (Kebenaran Sasaran)</th>
                      <th className="px-6 py-4">Recall (Tangkapan Risiko)</th>
                      <th className="px-6 py-4 bg-pink-50/40 text-pink-900 font-extrabold border-x border-pink-100">F1-Score (Titik Optimal)</th>
                      <th className="px-6 py-4">Volume Pelanggan (High Risk)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 bg-white">
                    {thresholdRows.map((row) => {
                      const isF1Optimal = row.f1_score > 0.75 || row.f1 > 0.75;
                      return (
                        <tr 
                          key={row.threshold} 
                          className="hover:bg-primary-50/30 transition-all"
                        >
                          <td className="px-6 py-4 font-semibold text-stone-800">
                            <span className="inline-flex items-center justify-center rounded-lg bg-stone-100 px-2 py-1 text-xs text-stone-700 border border-stone-200 font-mono">
                              {(row.threshold * 100).toFixed(0)}% ({row.threshold.toFixed(2)})
                            </span>
                          </td>
                          <td className="px-6 py-4 text-stone-600 font-medium">
                            {formatMetric(row.precision)}
                          </td>
                          <td className="px-6 py-4 text-stone-600 font-medium">
                            {formatMetric(row.recall)}
                          </td>
                          <td className="px-6 py-4 bg-pink-50/20 font-extrabold text-pink-700 border-x border-pink-100/60">
                            <div className="flex items-center gap-2">
                              <span>{formatMetric(row.f1_score || row.f1)}</span>
                              {isF1Optimal && (
                                <span className="inline-flex h-2 w-2 rounded-full bg-pink-500 animate-ping" />
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-stone-700 font-semibold">
                            {row.high_risk_customers ?? row.customer_count ?? "-"} <span className="text-xs font-normal text-stone-400 ml-1">pelanggan</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <EmptyState 
              icon="-" 
              title="Threshold sensitivity belum tersedia" 
              description={threshold.data?.empty_message || "Lakukan retrain model untuk memetakan sensitivitas threshold ini."} 
            />
          )}
        </div>
      </div>

      {/* SECTION 5: FEATURE IMPORTANCE & RISK DISTRIBUTION SIDE-BY-SIDE */}
      <div className="grid gap-6 xl:grid-cols-2">
        {/* FEATURE IMPORTANCE */}
        <div className="bg-white rounded-2xl border border-primary-100 shadow-sm overflow-hidden">
          <div className="border-b border-primary-50 bg-stone-50/55 p-6">
            <h2 className="text-lg font-bold text-primary-900">Feature Importance (SHAP Weights)</h2>
            <p className="text-xs text-stone-500 mt-0.5">Faktor-faktor perilaku dominan yang paling berkontribusi pada estimasi disengagement risk.</p>
          </div>
          <div className="p-6">
            {importance.isLoading ? (
              <div className="flex items-center justify-center py-12 gap-2 text-stone-500 text-sm">
                <div className="h-4 w-4 animate-spin rounded-full border-2 border-pink-500 border-t-transparent" />
                <span>Memuat feature importance...</span>
              </div>
            ) : importanceRows.length ? (
              <div className="space-y-5">
                {importanceRows.slice(0, 8).map((row) => (
                  <div key={row.feature} className="group">
                    <div className="mb-1.5 flex items-center justify-between text-sm">
                      <span className="font-semibold text-primary-900 group-hover:text-pink-600 transition-colors">
                        {row.label}
                      </span>
                      <span className="font-mono text-xs font-bold text-stone-500 bg-stone-100 px-1.5 py-0.5 rounded border border-stone-200/50">
                        {Number(row.importance).toFixed(3)}
                      </span>
                    </div>
                    
                    {/* Gradient Progress Bar */}
                    <div className="h-2.5 w-full rounded-full bg-stone-100 overflow-hidden">
                      <div 
                        className="h-full rounded-full bg-gradient-to-r from-pink-400 to-purple-600 transition-all duration-1000 group-hover:opacity-95" 
                        style={{ width: `${Math.min(Number(row.importance || 0) * 100, 100)}%` }}
                      />
                    </div>
                    
                    <p className="mt-1 text-[10px] text-stone-400 font-mono tracking-tight">{row.feature}</p>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState 
                icon="-" 
                title="Feature importance belum tersedia" 
                description={importance.data?.empty_message || "Feature importance akan tampil setelah model AI dilatih."} 
              />
            )}
          </div>
        </div>

        {/* RISK DISTRIBUTION */}
        <div className="bg-white rounded-2xl border border-primary-100 shadow-sm overflow-hidden">
          <div className="border-b border-primary-50 bg-stone-50/55 p-6">
            <h2 className="text-lg font-bold text-primary-900">Current Risk Segments Distribution</h2>
            <p className="text-xs text-stone-500 mt-0.5">Proporsi pembagian level risiko pelanggan Mamina Baby Spa saat ini.</p>
          </div>
          <div className="p-6">
            {riskChart.some((item) => item.value > 0) ? (
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={riskChart} margin={{ top: 20, right: 10, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1e7ea" vertical={false} />
                    <XAxis 
                      dataKey="name" 
                      tick={{ fill: '#78716c', fontSize: 12, fontWeight: 600 }}
                      tickLine={false}
                      axisLine={{ stroke: '#e7e5e4' }}
                    />
                    <YAxis 
                      allowDecimals={false} 
                      tick={{ fill: '#78716c', fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: '#e7e5e4' }}
                    />
                    <Tooltip 
                      contentStyle={{ backgroundColor: "#fff", borderRadius: "12px", border: "1px solid #e7e5e4", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                      formatter={(value, name) => [`${value} Pelanggan`, "Jumlah"]}
                    />
                    <Bar 
                      dataKey="value" 
                      radius={[8, 8, 0, 0]}
                      barSize={48}
                    >
                      {riskChart.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-80 flex flex-col items-center justify-center">
                <EmptyState 
                  icon="-" 
                  title="Distribusi risiko belum tersedia" 
                  description="Jalankan Generate Risk Scores dari ML Pipeline terlebih dahulu untuk menghitung sebaran data." 
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ label, value, icon, bgColor, valueClassName = "" }) {
  return (
    <div className={`rounded-xl border border-primary-100/50 p-4 transition-all hover:shadow-sm ${bgColor} flex flex-col justify-between`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold text-stone-500 uppercase tracking-wider">{label}</span>
        <div className="p-1 rounded-md bg-white/70 shadow-sm border border-stone-200/20">{icon}</div>
      </div>
      <p className={`break-words text-lg font-bold text-stone-800 ${valueClassName}`}>{value}</p>
    </div>
  );
}

function SummaryItem({ icon, label, value, bgColor }) {
  return (
    <div className={`rounded-2xl border p-5 bg-gradient-to-br ${bgColor} transition-all hover:shadow-sm flex items-start gap-4`}>
      <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm border border-stone-200/10">
        {icon}
      </div>
      <div>
        <span className="text-[10px] font-bold text-stone-500 uppercase tracking-widest">{label}</span>
        <p className="mt-1 text-sm font-medium leading-relaxed text-stone-800">{value}</p>
      </div>
    </div>
  );
}

function ModelMetadataPanel({ title, metadata }) {
  const rows = [
    ["Feature Count", metadata?.feature_count],
    ["Training Samples", metadata?.training_samples?.toLocaleString("id-ID")],
    ["Training Date", metadata?.training_date],
    ["Model Version", metadata?.model_version],
  ];

  return (
    <div className="rounded-xl border border-stone-200 bg-white p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="text-sm font-extrabold text-primary-900">{title}</h3>
        <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider ${
          metadata?.production_model ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-stone-100 text-stone-600 border border-stone-200"
        }`}>
          {metadata?.production_model ? "Production" : "Research Only"}
        </span>
      </div>
      <dl className="space-y-3">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-start justify-between gap-4 text-sm">
            <dt className="text-stone-500">{label}</dt>
            <dd className="max-w-[65%] break-words text-right font-semibold text-stone-800">{value ?? "-"}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
