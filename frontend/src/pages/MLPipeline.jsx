import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertCircle,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Database,
  FileSpreadsheet,
  Loader2,
  Lightbulb,
  MessageSquare,
  Play,
  RefreshCw,
  Tags,
} from "lucide-react";
import Button from "../components/common/Button";
import Card from "../components/common/Card";
import EmptyState from "../components/common/EmptyState";
import {
  useGenerateFeatures,
  useGenerateRecommendations,
  usePipelineStatus,
  useProcessNLP,
  useRetrainModel,
  useRunScoring,
  useTopicEvaluation,
  useTrainTopicModel,
} from "../hooks/usePipeline";
import { usePipelineTasks } from "../hooks/usePipelineTasks";
import { useLeadInsights } from "../hooks/useCustomers";

const statusStyles = {
  pending: "bg-stone-100 text-stone-600",
  processing: "bg-blue-50 text-blue-700",
  completed: "bg-emerald-50 text-emerald-700",
  failed: "bg-rose-50 text-rose-700",
  partial: "bg-amber-50 text-amber-700",
};

function formatNumber(value) {
  return Number(value || 0).toLocaleString("id-ID");
}

function normalizeTaskStatus(task) {
  if (!task) return null;
  if (["PENDING", "STARTED", "PROGRESS"].includes(task.status)) return "processing";
  if (task.status === "SUCCESS") return "completed";
  if (["FAILURE", "REVOKED"].includes(task.status)) return "failed";
  return "pending";
}

export default function MLPipeline() {
  const { data, isLoading, error } = usePipelineStatus();
  const [isFeatureModalOpen, setIsFeatureModalOpen] = useState(false);

  // Task IDs dipersist ke localStorage agar tidak hilang saat pindah halaman.
  const { setTask, taskQueries } = usePipelineTasks();

  const nlp = useProcessNLP();
  const topicModel = useTrainTopicModel();
  const features = useGenerateFeatures();
  const scoring = useRunScoring();
  const recommendations = useGenerateRecommendations();
  const retrain = useRetrainModel();
  const topicEval = useTopicEvaluation();
  const leadInsights = useLeadInsights(10);

  const runStep = (key, mutation) => {
    mutation.mutate(undefined, {
      onSuccess: (res) => {
        if (res.task_id) setTask(key, res.task_id);
      },
    });
  };

  if (isLoading) {
    return <div className="p-8 text-stone-500">Memuat status pipeline...</div>;
  }

  if (error && !data) {
    return (
      <div className="rounded-lg border border-rose-200 bg-rose-50 p-6 text-rose-700">
        Gagal memuat status ML Pipeline.
      </div>
    );
  }

  const importData = data?.import_linking || {};
  const nlpData = data?.nlp || {};
  const topicModelData = data?.topic_model || {};
  const featureData = data?.features || {};
  const scoringData = data?.scoring || {};
  const modelData = data?.model || {};
  const recommendationData = data?.recommendations || {};
  const leadData = leadInsights.data || {};
  const nlpResult = taskQueries.nlp.data?.result;
  const nlpProcessed = nlpResult?.processed ?? nlpData.processed_messages;
  const nlpFailed = nlpResult?.failed ?? nlpData.failed_messages ?? 0;
  const scoringResult = taskQueries.scoring.data?.result;
  const scoringProcessed = scoringResult?.processed ?? scoringData.processed ?? 0;
  const scoringFailed = scoringResult?.failed ?? scoringData.failed ?? 0;
  const taskFeatureSamples = taskQueries.features.data?.result?.sample_rows;
  const featureSamples = taskFeatureSamples?.length
    ? taskFeatureSamples
    : (featureData.sample_rows || []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-primary-900">ML Pipeline</h1>
        <p className="mt-1 text-sm text-stone-500">
          Orchestration manual untuk Behavioral Risk Scoring setelah import dan linking data.
        </p>
      </div>

      <StepCard
        number="1"
        title="Data Import & Linking"
        icon={<Database className="h-5 w-5" />}
        status={importData.whatsapp_messages ? "completed" : "pending"}
      >
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Metric label="Customer" value={formatNumber(importData.customers)} />
          <Metric label="Transaksi" value={formatNumber(importData.transactions)} />
          <Metric label="WhatsApp" value={formatNumber(importData.whatsapp_messages)} />
          <Metric label="Linked" value={formatNumber(importData.linked_messages)} />
          <Metric label="Unlinked" value={formatNumber(importData.unlinked_messages)} />
          <Metric label="Customer Aktif" value={formatNumber(importData.active_customers)} />
        </div>
        <Link to="/import" className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-pink-600 hover:text-pink-700">
          <FileSpreadsheet className="h-4 w-4" />
          Buka Import Data
        </Link>
      </StepCard>

      <StepCard
        number="1B"
        title="Lead Insights (Terpisah dari Churn)"
        icon={<MessageSquare className="h-5 w-5" />}
        status={leadData.summary?.total_leads ? "completed" : "pending"}
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <Metric label="Lead Provisional" value={formatNumber(leadData.summary?.total_leads)} />
          <Metric label="Pesan Lead" value={formatNumber(leadData.summary?.total_messages)} />
          <Metric label="Aktif 30 Hari" value={formatNumber(leadData.summary?.active_leads_30d)} />
        </div>
        <p className="mt-3 text-sm text-stone-500">
          Lead tidak masuk churn scoring. NLP isi pesan ditahan sampai identity dan consent tervalidasi.
        </p>
      </StepCard>

      <StepCard
        number="2"
        title="Train Topic Model"
        icon={<Tags className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.topicModel.data) || topicModelData.status}
        progress={taskQueries.topicModel.data?.progress}
        action={
          <Button
            size="sm"
            loading={topicModel.isPending || normalizeTaskStatus(taskQueries.topicModel.data) === "processing"}
            icon={<Play className="h-4 w-4" />}
            onClick={() => runStep("topicModel", topicModel)}
          >
            Train Topic Model
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Model Tersedia" value={topicModelData.model_exists ? "Ya" : "Belum"} />
          <Metric label="Jumlah Topic" value={formatNumber(topicModelData.topic_count)} />
          <Metric label="Model Version" value={taskQueries.topicModel.data?.result?.model_version || topicModelData.model_version || "-"} />
          <Metric label="Strict NLP" value={topicModelData.strict_required ? "Aktif" : "Nonaktif"} />
        </div>
        <p className="mt-3 text-sm text-stone-500">
          Path aktif: {topicModelData.configured_path || "/app/models/topic_model"}
        </p>
        <ErrorSummary task={taskQueries.topicModel.data} />

        {/* ── Clustering Evaluation Panel ───────────────────────────── */}
        <TopicEvaluationPanel eval={topicEval} />
      </StepCard>

      <StepCard
        number="3"
        title="Process NLP"
        icon={<MessageSquare className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.nlp.data) || nlpData.status}
        progress={taskQueries.nlp.data?.progress}
        action={
          <Button
            size="sm"
            loading={nlp.isPending || normalizeTaskStatus(taskQueries.nlp.data) === "processing"}
            disabled={topicModelData.strict_required && !topicModelData.model_exists}
            icon={<Play className="h-4 w-4" />}
            onClick={() => runStep("nlp", nlp)}
          >
            Run NLP Processing
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <Metric label="Pesan Diproses" value={formatNumber(nlpProcessed)} />
          <Metric label="Sukses" value={formatNumber(nlpProcessed)} />
          <Metric label="Gagal" value={formatNumber(nlpFailed)} />
        </div>
        <PreviewList title="Distribusi Sentimen" items={nlpData.sentiment_distribution} />
        <PreviewChips title="Dominant Keywords" items={(taskQueries.nlp.data?.result?.dominant_keywords || nlpData.dominant_keywords || []).map((x) => `${x.keyword} (${x.count})`)} />
        {topicModelData.strict_required && !topicModelData.model_exists && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Topic model belum tersedia. Jalankan Train Topic Model sebelum NLP Processing.
          </div>
        )}
        <ErrorSummary task={taskQueries.nlp.data} />
      </StepCard>

      <StepCard
        number="4"
        title="Generate Features"
        icon={<BarChart3 className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.features.data) || featureData.status}
        progress={taskQueries.features.data?.progress}
        action={
          <Button
            size="sm"
            loading={features.isPending || normalizeTaskStatus(taskQueries.features.data) === "processing"}
            icon={<Play className="h-4 w-4" />}
            onClick={() => runStep("features", features)}
          >
            Generate Behavioral Features
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <Metric label="Feature Vector" value={formatNumber(taskQueries.features.data?.result?.processed ?? featureData.feature_vectors)} />
          <Metric label="Total Snapshot" value={formatNumber(featureData.feature_snapshots_total)} />
          <Metric label="Missing Feature" value={formatNumber(taskQueries.features.data?.result?.missing_features)} />
          <Metric label="Latest As Of" value={taskQueries.features.data?.result?.as_of_date || featureData.latest_as_of_date || "-"} />
          <Metric label="Schema Version" value={taskQueries.features.data?.result?.schema_version || featureData.schema_version || "-"} />
          <Metric label="Jumlah Fitur" value={formatNumber(featureData.expected_features)} />
        </div>
        <FeatureSample rows={featureSamples} />
        {featureSamples.length > 0 && (
          <div className="mt-3 flex justify-end">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setIsFeatureModalOpen(true)}
            >
              Lihat Seluruh 25 Fitur (Pop-up)
            </Button>
          </div>
        )}
        <ErrorSummary task={taskQueries.features.data} />
      </StepCard>

      <StepCard
        number="5"
        title="Run Risk Scoring"
        icon={<AlertTriangle className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.scoring.data) || scoringData.status}
        progress={taskQueries.scoring.data?.progress}
        action={
          <Button
            size="sm"
            loading={scoring.isPending || normalizeTaskStatus(taskQueries.scoring.data) === "processing"}
            icon={<Play className="h-4 w-4" />}
            onClick={() => runStep("scoring", scoring)}
          >
            Generate Risk Scores
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Berhasil" value={formatNumber(scoringProcessed)} />
          <Metric label="Gagal" value={formatNumber(scoringFailed)} />
          <Metric label="Low Risk" value={formatNumber(scoringData.risk_distribution?.low)} />
          <Metric label="High Risk" value={formatNumber(scoringData.risk_distribution?.high)} />
        </div>
        <p className="mt-3 text-sm text-stone-500">
          Terakhir diproses: {taskQueries.scoring.data?.result?.last_processed_at || scoringData.last_processed_at || "-"}
        </p>
        <ErrorSummary task={taskQueries.scoring.data} />
      </StepCard>

      <StepCard
        number="6"
        title="Generate Action Recommendations"
        icon={<Lightbulb className="h-5 w-5" />}
        status={
          normalizeTaskStatus(taskQueries.recommendations.data)
          || recommendationData.status
        }
        progress={taskQueries.recommendations.data?.progress}
        action={
          <Button
            size="sm"
            loading={
              recommendations.isPending
              || normalizeTaskStatus(taskQueries.recommendations.data) === "processing"
            }
            icon={<Play className="h-4 w-4" />}
            onClick={() => runStep("recommendations", recommendations)}
          >
            Generate Recommendations
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Total" value={formatNumber(recommendationData.total)} />
          <Metric label="Dengan Customer Voice" value={formatNumber(recommendationData.with_customer_voice)} />
          <Metric label="Fallback Transaksi" value={formatNumber(recommendationData.without_customer_voice)} />
          <Metric label="Policy" value={recommendationData.policy_version || "-"} />
        </div>
        <p className="mt-3 text-sm text-stone-500">
          Customer voice menentukan konteks tindakan, bukan mengubah risk score.
        </p>
        <ErrorSummary task={taskQueries.recommendations.data} />
      </StepCard>

      <StepCard
        number="7"
        title="Retrain Model"
        icon={<RefreshCw className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.retrain.data) || (modelData.model_version ? "completed" : "pending")}
        progress={taskQueries.retrain.data?.progress}
        action={
          <Button
            size="sm"
            variant="outline"
            loading={retrain.isPending || normalizeTaskStatus(taskQueries.retrain.data) === "processing"}
            icon={<RefreshCw className="h-4 w-4" />}
            onClick={() => runStep("retrain", retrain)}
          >
            Retrain Model
          </Button>
        }
      >
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          Admin/research mode. Gunakan hanya saat feature schema berubah atau data historis bertambah signifikan.
        </div>
        <div className="grid gap-3 sm:grid-cols-5">
          <Metric label="Model Version" value={taskQueries.retrain.data?.result?.model_version || modelData.model_version || "-"} />
          <Metric label="Feature Schema" value={modelData.feature_schema_version || "-"} />
          <Metric label="Training Date" value={modelData.training_date || "-"} />
          <Metric label="Training Samples" value={modelData.training_samples ?? "-"} />
          <Metric
            label="SHAP"
            value={
              taskQueries.retrain.data?.result?.shap_available || modelData.shap_available
                ? `Tersedia (${modelData.shap_cache_count || 0} cache)`
                : "Belum tersedia"
            }
          />
        </div>
        <p className="mt-3 text-xs text-stone-500">
          Setelah retrain berhasil dan SHAP tersedia, jalankan Run Risk Scoring
          untuk membuat alasan risiko per customer.
        </p>
        <ErrorSummary task={taskQueries.retrain.data} />
      </StepCard>
      <FeaturePreviewModal
        isOpen={isFeatureModalOpen}
        onClose={() => setIsFeatureModalOpen(false)}
        rows={featureSamples}
      />
    </div>
  );
}

function StepCard({ number, title, icon, status = "pending", progress, action, children }) {
  const effectiveStatus = status || "pending";
  const numericProgress = Number.isFinite(Number(progress))
    ? Math.min(100, Math.max(0, Number(progress)))
    : 0;
  return (
    <Card className="hover:shadow-md">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-pink-50 text-pink-600">{number}</div>
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-primary-900">
              {icon}
              {title}
            </h2>
            <StatusBadge status={effectiveStatus} progress={progress} />
          </div>
        </div>
        {action}
      </div>
      {effectiveStatus === "processing" && (
        <div className="mb-4">
          <div className="h-2 overflow-hidden rounded-full bg-stone-100">
            <div
              className="h-full rounded-full bg-pink-500 transition-all duration-500"
              style={{ width: `${numericProgress}%` }}
            />
          </div>
        </div>
      )}
      {children}
    </Card>
  );
}

function StatusBadge({ status, progress }) {
  const icon = status === "processing" ? <Loader2 className="h-3 w-3 animate-spin" /> : status === "completed" ? <CheckCircle2 className="h-3 w-3" /> : <Clock className="h-3 w-3" />;
  
  let label = "Pending";
  if (status === "processing") {
    label = progress !== undefined && progress > 0 ? `Processing ${progress}%` : "Processing";
  } else if (status === "completed") {
    label = "Completed";
  } else if (status === "failed") {
    label = "Failed";
  } else if (status === "partial") {
    label = "Partial";
  }

  return (
    <span className={`mt-1 inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${statusStyles[status] || statusStyles.pending}`}>
      {icon}
      {label}
    </span>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg bg-primary-50 px-3 py-2">
      <p className="text-xs font-medium text-stone-500">{label}</p>
      <p className="text-lg font-bold text-primary-900">{value}</p>
    </div>
  );
}

function PreviewList({ title, items }) {
  if (!items || Object.keys(items).length === 0) return null;
  return (
    <div className="mt-4">
      <p className="text-sm font-semibold text-primary-900">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {Object.entries(items).map(([key, value]) => (
          <span key={key} className="rounded-full bg-stone-100 px-3 py-1 text-xs text-stone-700">
            {key}: {value}
          </span>
        ))}
      </div>
    </div>
  );
}

function PreviewChips({ title, items }) {
  if (!items?.length) return null;
  return (
    <div className="mt-4">
      <p className="text-sm font-semibold text-primary-900">{title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {items.slice(0, 10).map((item) => (
          <span key={item} className="rounded-full bg-purple-50 px-3 py-1 text-xs text-purple-700">{item}</span>
        ))}
      </div>
    </div>
  );
}

function FeatureSample({ rows }) {
  if (!rows?.length) return <EmptyState title="Sample feature belum tersedia" description="Jalankan Generate Behavioral Features untuk melihat preview." />;
  return (
    <div className="mt-4 overflow-x-auto rounded-lg border border-primary-100">
      <table className="min-w-full text-sm">
        <thead className="bg-primary-50 text-left text-xs uppercase text-stone-500">
          <tr>
            <th className="px-3 py-2">Customer</th>
            <th className="px-3 py-2">Recency Days</th>
            <th className="px-3 py-2">Tx 90d</th>
            <th className="px-3 py-2">Spend 90d</th>
            <th className="px-3 py-2">Sentimen</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-primary-100">
          {rows.map((row) => (
            <tr key={row.customer_id}>
              <td className="px-3 py-2 font-medium text-primary-900">{row.customer_name}</td>
              <td className="px-3 py-2">{row.recency_days}</td>
              <td className="px-3 py-2">{row.tx_count_90d}</td>
              <td className="px-3 py-2">{formatNumber(row.spend_90d)}</td>
              <td className="px-3 py-2">{row.avg_sentiment_score ?? "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ErrorSummary({ task }) {
  const errors = task?.result?.error_summary || (task?.error ? [task.error] : []);
  if (!errors?.length) return null;
  return (
    <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
      {errors.slice(0, 5).map((item, idx) => <p key={idx}>{item}</p>)}
    </div>
  );
}

// ── Helper: format a 0-1 float as percentage string ─────────────────────────
function fmtPct(val) {
  if (val === null || val === undefined) return "-";
  return `${(Number(val) * 100).toFixed(1)}%`;
}

// ── Helper: format a decimal metric value ────────────────────────────────────
function fmtDecimal(val, digits = 4) {
  if (val === null || val === undefined) return "-";
  return Number(val).toFixed(digits);
}

// ── Helper: determine traffic-light color class based on threshold ────────────
function metricColor(value, { warnBelow, warnAbove } = {}) {
  if (value === null || value === undefined) return "text-stone-400";
  if (warnAbove !== undefined && value > warnAbove) return "text-rose-600";
  if (warnBelow !== undefined && value < warnBelow) return "text-amber-600";
  return "text-emerald-600";
}

// ── Main evaluation panel ─────────────────────────────────────────────────────
function TopicEvaluationPanel({ eval: evalQuery }) {
  if (evalQuery.isLoading) {
    return (
      <div className="mt-4 flex items-center gap-2 text-xs text-stone-400">
        <div className="h-3 w-3 animate-spin rounded-full border border-pink-400 border-t-transparent" />
        Memuat evaluasi clustering...
      </div>
    );
  }

  const d = evalQuery.data;

  // Not yet evaluated
  if (!d || d.available === false) {
    return (
      <div className="mt-4 rounded-lg border border-stone-200 bg-stone-50 p-3 text-xs text-stone-500">
        Belum ada data evaluasi clustering. Jalankan <strong>Train Topic Model</strong> untuk menghasilkan metrik.
      </div>
    );
  }

  // Evaluation was run but encountered an error
  if (d.evaluation_error) {
    return (
      <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-700">
        <span className="font-semibold">Evaluasi Error:</span> {d.evaluation_error}
      </div>
    );
  }

  const warnings = d.evaluation_warnings || [];
  const outlierColor   = metricColor(d.outlier_rate,   { warnAbove: 0.40 });
  const diversityColor = metricColor(d.topic_diversity, { warnBelow: 0.50 });
  const silhouetteColor = metricColor(d.silhouette_score, { warnBelow: 0.10 });

  return (
    <div className="mt-5 space-y-4">
      {/* Section header */}
      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-stone-200" />
        <span className="text-xs font-bold uppercase tracking-wider text-stone-400">
          Clustering Evaluation
        </span>
        <div className="h-px flex-1 bg-stone-200" />
      </div>

      {/* Metric cards row */}
      <div className="grid gap-3 sm:grid-cols-3">
        {/* Outlier Rate */}
        <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-stone-500">Outlier Rate</p>
          <p className={`mt-1 text-2xl font-bold ${outlierColor}`}>
            {fmtPct(d.outlier_rate)}
          </p>
          <p className="mt-1 text-xs text-stone-400">
            {d.n_outliers ?? "-"} dari {d.n_docs ?? "-"} dokumen
          </p>
          <p className="mt-2 text-[10px] text-stone-400">
            Threshold: &lt; 40% ✓ — dokumen tanpa klaster (topic -1)
          </p>
        </div>

        {/* Topic Diversity */}
        <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-stone-500">Topic Diversity</p>
          <p className={`mt-1 text-2xl font-bold ${diversityColor}`}>
            {fmtDecimal(d.topic_diversity, 3)}
          </p>
          <p className="mt-1 text-xs text-stone-400">
            {d.n_topics_found ?? "-"} topik ditemukan
          </p>
          <p className="mt-2 text-[10px] text-stone-400">
            Threshold: &gt; 0.50 ✓ — keunikan kata kunci antar topik
          </p>
        </div>

        {/* Silhouette Score */}
        <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-stone-500">Silhouette Score</p>
          <p className={`mt-1 text-2xl font-bold ${silhouetteColor}`}>
            {fmtDecimal(d.silhouette_score, 4)}
          </p>
          <p className="mt-1 text-xs text-stone-400">
            {d.silhouette_sampled
              ? `Sampling n=${(d.silhouette_n ?? 0).toLocaleString("id-ID")}`
              : d.silhouette_n
              ? `n=${(d.silhouette_n).toLocaleString("id-ID")}`
              : "—"}
          </p>
          <p className="mt-2 text-[10px] text-stone-400">
            Threshold: &gt; 0.10 ✓ — kerapatan klaster di embedding space
          </p>
        </div>
      </div>

      {/* Model version info */}
      <p className="text-xs text-stone-400">
        Model: <span className="font-mono text-stone-600">{d.model_version || "-"}</span>
        {d.trained_at && (
          <> &nbsp;·&nbsp; Dilatih: {new Date(d.trained_at).toLocaleString("id-ID")}</>
        )}
      </p>

      {/* Quality warnings */}
      {warnings.length > 0 && (
        <div className="space-y-2">
          {warnings.map((w, i) => (
            <div
              key={i}
              className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800"
            >
              <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
              <span>{w}</span>
            </div>
          ))}
        </div>
      )}

      {/* All-clear */}
      {warnings.length === 0 && d.available && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          Semua metrik kualitas clustering dalam batas normal.
        </div>
      )}
    </div>
  );
}

// ── Feature labels mappings for human-friendly table headers ──────────────────
const FEATURE_LABELS = {
  recency_ratio: "Rasio Keterlambatan Kunjungan",
  frequency_trend_smoothed: "Tren Frekuensi Kunjungan",
  spend_trend_smoothed: "Tren Nilai Transaksi",
  msg_trend_smoothed: "Tren Komunikasi WhatsApp",
  sentiment_trend: "Tren Sentimen",
  recency_days: "Hari Sejak Transaksi Terakhir",
  tx_count_90d: "Jumlah Transaksi 90 Hari",
  spend_90d: "Total Belanja 90 Hari",
  avg_tx_value: "Rata-rata Nilai Transaksi",
  tenure_days: "Lama Menjadi Customer",
  activity_mean: "Rata-rata Aktivitas",
  recent_activity_avg: "Aktivitas Terkini",
  activity_std: "Variasi Aktivitas",
  activity_cv: "Stabilitas Aktivitas",
  spend_volatility_cv: "Stabilitas Nilai Belanja",
  trend_magnitude_interaction: "Interaksi Tren dan Aktivitas",
  avg_sentiment_score: "Rata-rata Sentimen",
  complaint_ratio: "Rasio Komplain",
  msg_volatility: "Volatilitas Pesan",
  response_delay_mean: "Rata-rata Waktu Respons",
  homecare_tx_ratio_90d: "Rasio Transaksi Homecare",
  last_tx_is_homecare: "Transaksi Terakhir Homecare",
  zero_amount_tx_count_90d: "Transaksi Nol Rupiah 90 Hari",
  lifetime_tx_count: "Total Transaksi Seumur Hidup",
};

// ── Complete 20-Feature Popup Modal Component ──────────────────────────────────
function FeaturePreviewModal({ isOpen, onClose, rows }) {
  if (!isOpen) return null;

  const featureKeys = Object.keys(FEATURE_LABELS);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-stone-900/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      {/* Modal Content */}
      <div className="relative flex max-h-[85vh] w-full max-w-6xl flex-col rounded-2xl bg-white shadow-2xl border border-stone-200 overflow-hidden animate-in fade-in zoom-in duration-200">

        {/* Header */}
        <div className="flex items-center justify-between border-b border-stone-100 bg-stone-50/70 px-6 py-4">
          <div>
            <h3 className="text-lg font-bold text-primary-900 flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-pink-600" />
              Preview Fitur Lengkap (ML Dataset Sample)
            </h3>
            <p className="mt-0.5 text-xs text-stone-500">
              Menampilkan nilai dari seluruh 24 fitur masukan model untuk sampel customer aktif.
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-700 transition"
          >
            <span className="text-xl font-bold">&times;</span>
          </button>
        </div>

        {/* Scrollable Table Area */}
        <div className="flex-1 overflow-auto p-6">
          {!rows?.length ? (
            <EmptyState
              title="Sample fitur belum tersedia"
              description="Jalankan Generate Behavioral Features untuk mengekstraksi data."
            />
          ) : (
            <div className="overflow-x-auto rounded-xl border border-stone-200">
              <table className="min-w-full text-sm border-collapse">
                <thead className="sticky top-0 bg-stone-50 text-left text-xs uppercase text-stone-500 shadow-sm border-b border-stone-200">
                  <tr>
                    <th className="sticky left-0 bg-stone-50 px-4 py-3 font-bold border-r border-stone-200 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)] z-10">
                      Customer
                    </th>
                    {featureKeys.map((key) => (
                      <th key={key} className="px-4 py-3 font-semibold min-w-[200px] border-r border-stone-100 last:border-r-0">
                        <div className="font-bold text-stone-700 leading-tight">
                          {FEATURE_LABELS[key] || key}
                        </div>
                        <div className="mt-0.5 text-[9px] font-mono text-stone-400 lowercase font-normal">
                          {key}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100 bg-white">
                  {rows.map((row, idx) => (
                    <tr key={row.customer_id || idx} className="hover:bg-primary-50/30 transition-colors">
                      <td className="sticky left-0 bg-white group-hover:bg-primary-50 px-4 py-3 font-semibold text-primary-900 border-r border-stone-200 shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)] z-10">
                        {row.customer_name}
                      </td>
                      {featureKeys.map((key) => {
                        const val = row[key];
                        let renderedVal = val ?? "-";
                        if (typeof val === "number") {
                          if (key.includes("spend") || key.includes("value")) {
                            renderedVal = formatNumber(val);
                          } else if (val % 1 !== 0) {
                            renderedVal = val.toFixed(4);
                          } else {
                            renderedVal = val;
                          }
                        }
                        return (
                          <td key={key} className="px-4 py-3 border-r border-stone-100 last:border-r-0 font-mono text-xs text-stone-600">
                            {renderedVal}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-stone-100 bg-stone-50/50 px-6 py-4">
          <span className="text-xs text-stone-400">
            * 20 fitur ini murni fitur masukan (independen) untuk model prediksi, tidak termasuk target label.
          </span>
          <Button size="sm" onClick={onClose}>
            Tutup Preview
          </Button>
        </div>
      </div>
    </div>
  );
}
