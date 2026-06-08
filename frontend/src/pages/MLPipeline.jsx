import { useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  Database,
  FileSpreadsheet,
  Loader2,
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
  usePipelineStatus,
  usePipelineTask,
  useProcessNLP,
  useRetrainModel,
  useRunScoring,
  useTrainTopicModel,
} from "../hooks/usePipeline";

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
  const [tasks, setTasks] = useState({});

  const nlp = useProcessNLP();
  const topicModel = useTrainTopicModel();
  const features = useGenerateFeatures();
  const scoring = useRunScoring();
  const retrain = useRetrainModel();

  const taskQueries = {
    nlp: usePipelineTask(tasks.nlp),
    topicModel: usePipelineTask(tasks.topicModel),
    features: usePipelineTask(tasks.features),
    scoring: usePipelineTask(tasks.scoring),
    retrain: usePipelineTask(tasks.retrain),
  };

  const runStep = (key, mutation) => {
    mutation.mutate(undefined, {
      onSuccess: (res) => {
        if (res.task_id) setTasks((prev) => ({ ...prev, [key]: res.task_id }));
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
  const nlpResult = taskQueries.nlp.data?.result;
  const nlpProcessed = nlpResult?.processed ?? nlpData.processed_messages;
  const nlpFailed = nlpResult?.failed ?? nlpData.failed_messages ?? 0;
  const scoringResult = taskQueries.scoring.data?.result;
  const scoringProcessed = scoringResult?.processed ?? scoringData.processed ?? 0;
  const scoringFailed = scoringResult?.failed ?? scoringData.failed ?? 0;

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
        number="2"
        title="Train Topic Model"
        icon={<Tags className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.topicModel.data) || topicModelData.status}
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
      </StepCard>

      <StepCard
        number="3"
        title="Process NLP"
        icon={<MessageSquare className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.nlp.data) || nlpData.status}
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
        <FeatureSample rows={taskQueries.features.data?.result?.sample_rows || []} />
        <ErrorSummary task={taskQueries.features.data} />
      </StepCard>

      <StepCard
        number="5"
        title="Run Risk Scoring"
        icon={<AlertTriangle className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.scoring.data) || scoringData.status}
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
        title="Retrain Model"
        icon={<RefreshCw className="h-5 w-5" />}
        status={normalizeTaskStatus(taskQueries.retrain.data) || (modelData.model_version ? "completed" : "pending")}
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
        <div className="grid gap-3 sm:grid-cols-4">
          <Metric label="Model Version" value={taskQueries.retrain.data?.result?.model_version || modelData.model_version || "-"} />
          <Metric label="Feature Schema" value={modelData.feature_schema_version || "-"} />
          <Metric label="Training Date" value={modelData.training_date || "-"} />
          <Metric label="Training Samples" value={modelData.training_samples ?? "-"} />
        </div>
        <ErrorSummary task={taskQueries.retrain.data} />
      </StepCard>
    </div>
  );
}

function StepCard({ number, title, icon, status = "pending", action, children }) {
  const effectiveStatus = status || "pending";
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
            <StatusBadge status={effectiveStatus} />
          </div>
        </div>
        {action}
      </div>
      {children}
    </Card>
  );
}

function StatusBadge({ status }) {
  const icon = status === "processing" ? <Loader2 className="h-3 w-3 animate-spin" /> : status === "completed" ? <CheckCircle2 className="h-3 w-3" /> : <Clock className="h-3 w-3" />;
  return (
    <span className={`mt-1 inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-semibold ${statusStyles[status] || statusStyles.pending}`}>
      {icon}
      {status === "processing" ? "Processing" : status === "completed" ? "Completed" : status === "failed" ? "Failed" : status === "partial" ? "Partial" : "Pending"}
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
