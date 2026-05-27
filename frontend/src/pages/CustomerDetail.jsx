import { useState, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Phone,
  Mail,
  MapPin,
  Calendar,
  DollarSign,
  MessageSquare,
  Clock,
  Plus,
  History,
  TrendingDown,
  Activity,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Hash,
  Sparkles,
  Lightbulb,
  Smile,
  Meh,
  Frown,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useCustomer360, useCustomerTimeline, useCustomerRiskHistory } from "../hooks/useCustomers";
import { useCustomerActions } from "../hooks/useActions";
import ChurnScoreBadge from "../components/customer/ChurnScoreBadge";
import RiskLevelBadge from "../components/customer/RiskLevelBadge";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import { DetailSkeleton } from "../components/common/Skeleton";
import CreateActionModal from "../components/actions/CreateActionModal";
import ActionHistoryModal from "../components/actions/ActionHistoryModal";
import {
  formatDate,
  formatRelativeTime,
  formatCurrency,
  getInitials,
  maskPhone,
  getRiskLevel,
  getRiskColors,
  FEATURE_LABELS,
  EXPLAINABILITY_MAP,
  getDynamicActionSuggestions,
  getSentimentColor,
} from "../lib/utils";

function SentimentIcon({ value }) {
  if (value >= 0.3) {
    return <Smile className="h-5 w-5 text-emerald-600 mx-auto mb-1.5" />;
  }
  if (value >= -0.3) {
    return <Meh className="h-5 w-5 text-yellow-600 mx-auto mb-1.5" />;
  }
  return <Frown className="h-5 w-5 text-red-600 mx-auto mb-1.5" />;
}

function CustomerDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("transactions");
  const [showCreateAction, setShowCreateAction] = useState(false);
  const [showActionHistory, setShowActionHistory] = useState(false);
  const [showAllFeatures, setShowAllFeatures] = useState(false);
  const [activeChartTab, setActiveChartTab] = useState("risk");
  const [activeSection, setActiveSection] = useState("overview");

  const { data, isLoading, error } = useCustomer360(id);
  const { data: timeline, isLoading: timelineLoading } = useCustomerTimeline(
    id,
    activeTab
  );
  const { data: actions } = useCustomerActions(id);
  const { data: riskHistory } = useCustomerRiskHistory(id);

  // Reconstructed activity timeline progression
  const activityTimelineData = useMemo(() => {
    const dailyMap = {};
    
    // Extract transaction items and message items from timeline
    const items = timeline?.items || timeline?.data || [];
    items.forEach((item) => {
      if (!item.date) return;
      const dateStr = item.date.slice(0, 10);
      if (!dailyMap[dateStr]) {
        dailyMap[dateStr] = { date: dateStr, transactions: 0, messages: 0, spend: 0 };
      }
      if (item.type === "transaction") {
        dailyMap[dateStr].transactions += 1;
        dailyMap[dateStr].spend += item.amount || 0;
      } else if (item.type === "feedback") {
        dailyMap[dateStr].messages += 1;
      }
    });

    return Object.values(dailyMap).sort((a, b) => a.date.localeCompare(b.date));
  }, [timeline]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-stone-600 hover:text-primary-900"
        >
          <ArrowLeft className="h-5 w-5" />
          <span>Kembali</span>
        </button>
        <DetailSkeleton />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Gagal memuat data customer</p>
        <Button className="mt-4" onClick={() => navigate(-1)}>
          Kembali
        </Button>
      </div>
    );
  }

  const {
    customer,
    latest_prediction,
    quick_stats,
    transaction_summary,
    sentiment_summary,
    numeric_features,
    text_signals,
    text_semantics,
    last_messages,
    historical_messages,
  } = data;

  const fallbackStats = {
    total_transactions: transaction_summary?.total_transactions || 0,
    total_spent: transaction_summary?.total_spent || 0,
    last_visit:
      transaction_summary?.last_transaction_date ||
      customer.last_seen_at ||
      customer.created_at,
    message_count: sentiment_summary?.neg_msg_count_30 || 0,
    avg_sentiment_30: sentiment_summary?.avg_sentiment_30 || 0,
  };
  const stats = {
    ...fallbackStats,
    ...(quick_stats || {}),
    last_visit:
      quick_stats?.last_visit ||
      fallbackStats.last_visit,
    total_spent:
      quick_stats?.total_spent ?? fallbackStats.total_spent,
    total_transactions:
      quick_stats?.total_transactions ?? fallbackStats.total_transactions,
    message_count:
      quick_stats?.message_count ?? fallbackStats.message_count,
  };

  const riskLevel =
    latest_prediction?.risk_label || getRiskLevel(latest_prediction?.risk_score || 0);
  const riskColors = getRiskColors(riskLevel);
  const suggestions = getDynamicActionSuggestions(latest_prediction?.top_reasons);

  // Process top reasons
  const topReasons = (latest_prediction?.top_reasons || [])
    .slice(0, 5)
    .map((reason) => {
      const mapping = EXPLAINABILITY_MAP[reason.feature] || {
        icon: "📊",
        title: reason.feature,
        getDetail: () => reason.description,
      };

      let detail = "";
      let impactLevel = "low";

      try {
        const absImpact = Math.abs(reason.impact || 0);
        impactLevel =
          absImpact > 0.2 ? "high" : absImpact > 0.1 ? "medium" : "low";

        if (mapping.getDetail) {
          detail = mapping.getDetail(reason.value, reason.impact);
        } else {
          const impactLabel =
            impactLevel === "high"
              ? "Tinggi"
              : impactLevel === "medium"
              ? "Sedang"
              : "Rendah";
          detail = `Impact: ${impactLabel} | ${reason.description}`;
        }
      } catch {
        detail = reason.description || "Faktor yang mempengaruhi risiko";
      }

      return {
        title: mapping.title || FEATURE_LABELS[reason.feature] || reason.feature,
        detail,
        impactLevel,
      };
    });

  // Risk history chart data
  const riskHistoryData = (riskHistory?.history || []).map((h) => ({
    date: h.as_of_date ? h.as_of_date.slice(0, 10) : "",
    risk_score: h.risk_score,
  }));

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-stone-600 hover:text-primary-900 transition"
      >
        <ArrowLeft className="h-5 w-5" />
        <span>Kembali</span>
      </button>

      {/* SECTION A: Customer Profile Header */}
      <div className="overflow-hidden rounded-xl bg-white shadow-md border border-primary-100">
        <div className="h-2 bg-primary-600" />
        <div className="p-5 lg:p-6">
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1fr_280px]">
            <div className="min-w-0">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                <div className="h-20 w-20 rounded-2xl bg-primary-50 border border-primary-200 flex items-center justify-center shrink-0 shadow-sm">
                  <span className="text-primary-700 font-bold text-2xl">
                    {getInitials(customer.name)}
                  </span>
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0">
                      <h1 className="text-2xl font-bold text-primary-900 leading-tight break-words">
                        {customer.name}
                      </h1>
                      <p className="text-sm text-stone-500 mt-1">
                        Customer profile dan sinyal risiko terbaru
                      </p>
                    </div>
                    <RiskLevelBadge
                      score={latest_prediction?.risk_score || 0}
                      level={latest_prediction?.risk_label}
                      size="lg"
                    />
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {customer.phone_display && (
                      <span className="inline-flex items-center gap-1.5 rounded-full border border-primary-100 bg-primary-50 px-3 py-1.5 text-xs font-medium text-stone-700">
                        <Phone className="h-3.5 w-3.5 text-primary-500" />
                        {maskPhone(customer.phone_display)}
                      </span>
                    )}
                    {customer.email && (
                      <span className="inline-flex min-w-0 items-center gap-1.5 rounded-full border border-primary-100 bg-primary-50 px-3 py-1.5 text-xs font-medium text-stone-700">
                        <Mail className="h-3.5 w-3.5 text-primary-500 shrink-0" />
                        <span className="truncate max-w-[220px]">{customer.email}</span>
                      </span>
                    )}
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-primary-100 bg-primary-50 px-3 py-1.5 text-xs font-medium text-stone-700">
                      <MapPin className="h-3.5 w-3.5 text-primary-500" />
                      {customer.city || "Kota belum tersedia"}
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full border border-primary-100 bg-primary-50 px-3 py-1.5 text-xs font-medium text-stone-700">
                      <Calendar className="h-3.5 w-3.5 text-primary-500" />
                      Member sejak {formatDate(customer.created_at)}
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-lg border border-primary-100 bg-primary-50 p-4">
                  <div className="flex items-start gap-3">
                    <DollarSign className="h-5 w-5 text-emerald-600 mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-stone-500">Total Spent</p>
                      <p className="text-base font-bold text-primary-900 truncate">
                        {formatCurrency(stats.total_spent || 0)}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border border-primary-100 bg-primary-50 p-4">
                  <div className="flex items-start gap-3">
                    <Clock className="h-5 w-5 text-primary-600 mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-stone-500">Kunjungan Terakhir</p>
                      <p className="text-base font-bold text-primary-900 truncate">
                        {formatRelativeTime(stats.last_visit)}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border border-primary-100 bg-primary-50 p-4">
                  <div className="flex items-start gap-3">
                    <MessageSquare className="h-5 w-5 text-purple-600 mt-0.5 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-stone-500">Pesan 30 Hari</p>
                      <p className="text-base font-bold text-primary-900">
                        {stats.message_count || 0}
                      </p>
                    </div>
                  </div>
                </div>
                <div className="rounded-lg border border-primary-100 bg-primary-50 p-4">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 shrink-0">
                      <SentimentIcon value={stats.avg_sentiment_30 || 0} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-stone-500">Sentimen 30 Hari</p>
                      <p
                        className={`text-base font-bold ${getSentimentColor(
                          stats.avg_sentiment_30 || 0
                        )}`}
                      >
                        {((stats.avg_sentiment_30 || 0) * 100).toFixed(0)}%
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className={`rounded-xl border p-5 ${riskColors.bg} ${riskColors.border}`}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase text-stone-500">
                    Risk Score
                  </p>
                  <div className="mt-3">
                    <ChurnScoreBadge
                      score={latest_prediction?.risk_score || 0}
                      size="lg"
                    />
                  </div>
                </div>
                <Activity className="h-5 w-5 text-primary-500" />
              </div>

              <div className="mt-5 space-y-3 rounded-lg bg-white/70 p-3 border border-white/80">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs text-stone-500">Level</span>
                  <RiskLevelBadge
                    score={latest_prediction?.risk_score || 0}
                    level={latest_prediction?.risk_label}
                  />
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs text-stone-500">Model</span>
                  <span className="text-xs font-semibold text-stone-700 truncate max-w-[130px]">
                    {latest_prediction?.model_version || "-"}
                  </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-xs text-stone-500">Prediksi</span>
                  <span className="text-xs font-semibold text-stone-700">
                    {formatDate(latest_prediction?.as_of_date)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-primary-100 p-1 flex flex-wrap gap-1">
        {[
          { key: "overview", label: "Overview & Action" },
          { key: "signals", label: "Sinyal Risiko" },
          { key: "history", label: "Riwayat & Grafik" },
        ].map((section) => (
          <button
            key={section.key}
            onClick={() => setActiveSection(section.key)}
            className={`px-4 py-2 rounded-md text-sm font-semibold transition ${
              activeSection === section.key
                ? "bg-primary-600 text-white shadow-sm"
                : "text-stone-600 hover:bg-primary-50 hover:text-primary-900"
            }`}
          >
            {section.label}
          </button>
        ))}
      </div>

      {/* SECTION B: Why At Risk? */}
      {activeSection === "overview" && (
      <div className="grid grid-cols-1 lg:grid-cols-[1.35fr_0.85fr] gap-6">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-semibold text-primary-900 mb-4">
          Mengapa Berisiko?
        </h2>
        {topReasons.length > 0 ? (
          <div className="space-y-3">
            {topReasons.map((reason, idx) => (
              <div
                key={idx}
                className={`flex items-start gap-3 p-4 rounded-lg border-l-4 ${
                  reason.impactLevel === "high"
                    ? "bg-red-50 border-red-500"
                    : reason.impactLevel === "medium"
                    ? "bg-yellow-50 border-yellow-500"
                    : "bg-primary-50 border-primary-300"
                }`}
              >
                <BarChart3 className="h-5 w-5 text-primary-600 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <h4 className="font-medium text-primary-900">
                      {reason.title}
                    </h4>
                    <Badge
                      color={
                        reason.impactLevel === "high"
                          ? "red"
                          : reason.impactLevel === "medium"
                          ? "yellow"
                          : "gray"
                      }
                    >
                      {reason.impactLevel === "high"
                        ? "Impact Tinggi"
                        : reason.impactLevel === "medium"
                        ? "Impact Sedang"
                        : "Impact Rendah"}
                    </Badge>
                  </div>
                  <p className="text-sm text-stone-600 mt-1">{reason.detail}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-primary-100 bg-primary-50 p-4">
            <p className="text-sm font-medium text-primary-900">
              SHAP explanation belum tersedia
            </p>
            <p className="mt-1 text-sm text-stone-600">
              Risk score tetap tersedia, tetapi alasan utama belum dihitung dari kontribusi model XGBoost.
              Jalankan retrain sampai artifact SHAP tersedia lalu jalankan Run Risk Scoring.
            </p>
          </div>
        )}
      </div>

      {/* SECTION B2: Profil Risiko & Sinyal Perilaku (NEW — Phase 4) */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-lg font-semibold text-primary-900 mb-1">
          Saran Operasional
        </h2>
        <p className="text-xs text-stone-500 mb-4">
          Saran berbasis indikator risiko dominan. Gunakan sebagai panduan follow-up, bukan keputusan otomatis.
        </p>

        <div className="space-y-3 mb-6">
          {suggestions.map((suggestion, idx) => (
            <div
              key={idx}
              className="flex items-start gap-3 p-3 bg-primary-50 rounded-lg hover:bg-primary-100 transition cursor-pointer"
              onClick={() => {
                if (suggestion.type !== "none") {
                  setShowCreateAction(true);
                }
              }}
            >
              <Lightbulb className="h-5 w-5 text-primary-600 mt-0.5 shrink-0" />
              <span className="flex-1 text-sm font-medium text-primary-800">
                {suggestion.text}
              </span>
              {suggestion.type !== "none" && (
                <Plus className="h-5 w-5 text-primary-400 shrink-0" />
              )}
            </div>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <Button
            icon={<Plus className="h-4 w-4" />}
            onClick={() => setShowCreateAction(true)}
            className="flex-1"
          >
            Buat Action
          </Button>
          <Button
            variant="outline"
            icon={<History className="h-4 w-4" />}
            onClick={() => setShowActionHistory(true)}
            className="flex-1"
          >
            Riwayat ({actions?.total || 0})
          </Button>
        </div>
      </div>
      </div>
      )}

      {activeSection === "signals" && (
      <>
      <div className="grid grid-cols-1 gap-6">
        {/* Profil Risiko (numeric_features) */}
        {numeric_features && Object.keys(numeric_features).length > 0 && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-lg font-semibold text-primary-900 mb-4 flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-primary-600" />
              Profil Risiko
            </h2>
            <div className="space-y-3">
              {Object.entries(numeric_features)
                .filter(([key]) => key !== "as_of_date")
                .slice(0, showAllFeatures ? undefined : 4)
                .map(([key, value]) => {
                  const label = FEATURE_LABELS[key] || key.replace(/_/g, " ");
                  const isMonetary = ["spend_90d", "avg_tx_value"].includes(key);
                  const displayValue = isMonetary
                    ? formatCurrency(value || 0)
                    : typeof value === "number"
                    ? value.toFixed(2)
                    : value || "-";

                  return (
                    <div
                      key={key}
                      className="flex items-center justify-between py-2 border-b border-primary-100 last:border-0"
                    >
                      <span className="text-sm text-stone-600">{label}</span>
                      <span className="text-sm font-semibold text-primary-900">
                        {displayValue}
                      </span>
                    </div>
                  );
                })}
            </div>
            
            {Object.keys(numeric_features).length > 5 && (
              <button
                onClick={() => setShowAllFeatures(!showAllFeatures)}
                className="mt-4 flex items-center justify-center gap-2 w-full py-2 text-sm text-primary-600 hover:bg-primary-50 rounded-lg transition"
              >
                {showAllFeatures ? (
                  <>
                    <ChevronUp className="h-4 w-4" /> Sembunyikan detail fitur
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-4 w-4" /> Lihat semua fitur teknis
                  </>
                )}
              </button>
            )}
          </div>
        )}

      </div>

      {/* SECTION B3: Sinyal Perilaku & Percakapan (NLP) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {/* Panel 1: Predictive Interaction Signals */}
        <div className="bg-white rounded-2xl shadow-md border border-pink-100 p-6 transition-all hover:shadow-lg">
          <h2 className="text-lg font-bold bg-gradient-to-r from-pink-500 to-purple-500 bg-clip-text text-transparent mb-2 flex items-center gap-2">
            <Activity className="h-5 w-5 text-pink-400" />
            Predictive Interaction Signals
          </h2>
          <p className="text-[11px] text-stone-500 mb-4 italic">
            *Sinyal prediktif dihitung dari chat dalam window 30 hari sebelum tanggal prediksi.
          </p>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 bg-stone-50 rounded-xl border border-stone-200">
                <p className="text-[10px] uppercase tracking-wide text-stone-400 font-bold">
                  Window Prediksi
                </p>
                <p className="text-sm font-semibold text-stone-700 mt-1">
                  30 hari sebelum {latest_prediction?.as_of_date || numeric_features?.as_of_date || "-"}
                </p>
              </div>
              <div className="p-3 bg-stone-50 rounded-xl border border-stone-200">
                <p className="text-[10px] uppercase tracking-wide text-stone-400 font-bold">
                  Chat Dalam Window
                </p>
                <p className="text-sm font-semibold text-stone-700 mt-1">
                  {text_signals?.msg_count_30d || 0} pesan
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="p-4 bg-gradient-to-br from-pink-50/50 to-white rounded-2xl border border-pink-100/50 text-center shadow-inner">
                <p className="text-xs text-stone-500 font-medium mb-1">Rata-rata Sentimen</p>
                <p className={`text-xl font-extrabold ${
                  (numeric_features?.avg_sentiment_score ?? 0) < 0.2 ? "text-rose-500" : "text-emerald-600"
                }`}>
                  {numeric_features?.avg_sentiment_score != null
                    ? `${(numeric_features.avg_sentiment_score * 100).toFixed(0)}%`
                    : "-"}
                </p>
                <p className="text-[10px] text-stone-400 mt-1.5 leading-relaxed">
                  Tingkat kepuasan chat (Skala -100% s/d +100%)
                </p>
              </div>

              <div className="p-4 bg-gradient-to-br from-purple-50/50 to-white rounded-2xl border border-purple-100/50 text-center shadow-inner">
                <p className="text-xs text-stone-500 font-medium mb-1">Tren Sentimen</p>
                <p className={`text-xl font-extrabold ${
                  (numeric_features?.sentiment_trend ?? 0) < 0 ? "text-rose-500" : "text-emerald-600"
                }`}>
                  {numeric_features?.sentiment_trend != null
                    ? numeric_features.sentiment_trend.toFixed(3)
                    : "-"}
                </p>
                <p className="text-[10px] text-stone-400 mt-1.5 leading-relaxed">
                  Arah pergeseran kepuasan komunikasi (Slope)
                </p>
              </div>
            </div>

            <div className="p-4 bg-gradient-to-br from-blue-50/50 to-white rounded-2xl border border-blue-100/50 shadow-inner flex items-center justify-between">
              <div>
                <h4 className="text-sm font-bold text-stone-700">Tren Pesan Masuk</h4>
                <p className="text-[10px] text-stone-500 mt-0.5">Smoothing intensitas chat WhatsApp</p>
              </div>
              <div className="text-right">
                <p className={`text-xl font-extrabold ${
                  (numeric_features?.msg_trend_smoothed ?? 0) < 0 ? "text-rose-500" : "text-emerald-600"
                }`}>
                  {numeric_features?.msg_trend_smoothed != null
                    ? numeric_features.msg_trend_smoothed.toFixed(3)
                    : "-"}
                </p>
                <span className="text-[10px] text-stone-400">Slope Volatilitas</span>
              </div>
            </div>
            
            <div className="p-4 bg-stone-50 rounded-2xl border border-stone-200/50">
              <span className="text-xs font-bold text-stone-600 flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-yellow-500" />
                Interpretasi Sinyal Prediktif
              </span>
              <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                {(text_signals?.msg_count_30d || 0) === 0
                  ? "Tidak ada chat pada window prediksi 30 hari, sehingga sinyal percakapan untuk model bernilai 0."
                  : (numeric_features?.avg_sentiment_score ?? 0) < 0.2
                  ? "Komunikasi pada window prediksi menunjukkan sinyal sentimen/keluhan yang perlu diperhatikan."
                  : "Intensitas dan tingkat kepuasan komunikasi pada window prediksi relatif stabil."}
              </p>
            </div>
          </div>
        </div>

        {/* Panel 2: Conversation Insights (Exploratory) */}
        <div className="bg-white rounded-2xl shadow-md border border-purple-100 p-6 transition-all hover:shadow-lg">
          <h2 className="text-lg font-bold bg-gradient-to-r from-purple-500 to-pink-500 bg-clip-text text-transparent mb-2 flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-purple-400" />
            Conversation Insights (Exploratory)
          </h2>
          <p className="text-[11px] text-stone-500 mb-4 italic">
            *Bagian atas memakai snapshot NLP pada window prediksi. Conversation historis di bawah hanya konteks, bukan input skor saat ini.
          </p>
          <div className="space-y-4">
            {/* Dominant Topic */}
            <div className="p-3 bg-purple-50 rounded-xl border border-purple-100 shadow-sm">
              <div className="flex items-center gap-2 text-purple-800 text-sm font-semibold mb-1">
                <Hash className="h-4 w-4 text-purple-500" />
                Topik Dominan: {text_semantics?.dominant_topic || "Belum tersedia"}
              </div>
              {Array.isArray(text_semantics?.top_keywords) && text_semantics.top_keywords.length > 0 ? (
                <div className="flex flex-wrap gap-1 mt-2">
                  {text_semantics.top_keywords.map((kw, i) => (
                    <span key={i} className="px-2 py-0.5 bg-white text-purple-600 text-xs rounded-full border border-purple-200 shadow-sm font-medium">
                      {kw}
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-purple-500 mt-2">
                  Keyword eksploratif belum tersedia untuk customer ini.
                </p>
              )}
            </div>

            {/* Sentiment Distribution */}
            <div>
              <h3 className="text-xs font-semibold text-stone-600 mb-2">Distribusi Tipe Chat</h3>
              <div className="flex gap-2">
                {["positive", "neutral", "negative"].map((label) => {
                  const count = text_semantics?.sentiment_dist?.[label] || 0;
                  const colors = {
                    positive: "bg-emerald-50 text-emerald-800 border-emerald-100",
                    neutral: "bg-primary-50 text-primary-800 border-primary-100",
                    negative: "bg-rose-50 text-rose-800 border-rose-100",
                  };
                  return (
                    <div key={label} className={`flex-1 p-2 rounded-xl text-center border ${colors[label]}`}>
                      <p className="text-lg font-bold">{count}</p>
                      <p className="text-[10px] capitalize font-medium">{label}</p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Last Messages */}
            <div>
              <h3 className="text-xs font-semibold text-stone-600 mb-2">Cuplikan Chat Dalam Window Prediksi</h3>
              {last_messages && last_messages.length > 0 ? (
                <div className="space-y-2">
                  {last_messages.slice(0, 3).map((msg, idx) => (
                    <div key={idx} className={`p-3 rounded-xl text-xs border-l-4 shadow-sm ${
                      msg.sentiment_label === "negative"
                        ? "border-l-rose-400 bg-rose-50/50"
                        : msg.sentiment_label === "positive"
                        ? "border-l-emerald-400 bg-emerald-50/50"
                        : "border-l-stone-300 bg-stone-50"
                    }`}>
                      <div className="flex items-center gap-2 mb-1.5">
                        {msg.sentiment_label && (
                          <Badge color={
                            msg.sentiment_label === "negative" ? "red" :
                            msg.sentiment_label === "positive" ? "green" : "gray"
                          } className="text-[9px] uppercase font-bold px-1.5 py-0.5">
                            {msg.sentiment_label}
                          </Badge>
                        )}
                        {msg.has_complaint && <Badge color="red" className="text-[9px] uppercase font-bold px-1.5 py-0.5">Komplain</Badge>}
                      </div>
                      <p className="text-stone-700 italic font-medium leading-relaxed">
                        {msg.text_snippet}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 rounded-xl text-xs border border-stone-200 bg-stone-50 text-stone-500">
                  Tidak ada chat dalam window prediksi 30 hari.
                </div>
              )}
            </div>

            <div>
              <h3 className="text-xs font-semibold text-stone-600 mb-2">Conversation Historis Terakhir</h3>
              {historical_messages && historical_messages.length > 0 ? (
                <div className="space-y-2">
                  {historical_messages.slice(0, 3).map((msg, idx) => (
                    <div key={idx} className="p-3 rounded-xl text-xs border-l-4 border-l-purple-300 bg-purple-50/40 shadow-sm">
                      <div className="flex items-center justify-between gap-2 mb-1.5">
                        <Badge color={msg.direction === "inbound" ? "purple" : "gray"} className="text-[9px] uppercase font-bold px-1.5 py-0.5">
                          {msg.direction || "chat"}
                        </Badge>
                        <span className="text-[10px] text-stone-400">
                          {formatRelativeTime(msg.timestamp)}
                        </span>
                      </div>
                      <p className="text-stone-700 italic font-medium leading-relaxed">
                        {msg.text_snippet}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="p-3 rounded-xl text-xs border border-stone-200 bg-stone-50 text-stone-500">
                  Belum ada conversation historis yang terhubung.
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      </>
      )}

      {/* SECTION B3: Behavioral Dynamics & Risk History */}
      {activeSection === "history" && (
      <>
      <div className="bg-white rounded-2xl shadow-md border border-primary-100 p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h2 className="text-lg font-bold text-primary-900 flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-primary-600" />
              Behavioral Dynamics & Risk History
            </h2>
            <p className="text-xs text-stone-500 mt-0.5">Visualisasi pergeseran perilaku dan skor risiko pelanggan dari waktu ke waktu.</p>
          </div>
          <div className="flex gap-1.5 bg-stone-100 p-1 rounded-xl">
            <button
              onClick={() => setActiveChartTab("risk")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeChartTab === "risk"
                  ? "bg-white text-primary-900 shadow-sm"
                  : "text-stone-600 hover:text-stone-900"
              }`}
            >
              Skor Risiko
            </button>
            <button
              onClick={() => setActiveChartTab("activity")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeChartTab === "activity"
                  ? "bg-white text-primary-900 shadow-sm"
                  : "text-stone-600 hover:text-stone-900"
              }`}
            >
              Transaksi & Spend
            </button>
            <button
              onClick={() => setActiveChartTab("chats")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeChartTab === "chats"
                  ? "bg-white text-primary-900 shadow-sm"
                  : "text-stone-600 hover:text-stone-900"
              }`}
            >
              Chat WhatsApp
            </button>
          </div>
        </div>

        <div className="h-[280px]">
          {activeChartTab === "risk" && (
            riskHistoryData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={riskHistoryData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#78716c" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e7e5e4" }}
                  />
                  <YAxis
                    domain={[0, 1]}
                    tick={{ fontSize: 11, fill: "#78716c" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e7e5e4" }}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#fff", borderRadius: "12px", border: "1px solid #e7e5e4", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                    formatter={(v) => [`${(v * 100).toFixed(1)}%`, "Estimasi Skor Risiko"]}
                    labelFormatter={(l) => `Tanggal: ${l}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="risk_score"
                    stroke="#db2777"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#db2777", strokeWidth: 2, stroke: "#fff" }}
                    activeDot={{ r: 7, strokeWidth: 2 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-stone-400 text-sm italic">
                Histori skor risiko belum tersedia.
              </div>
            )
          )}

          {activeChartTab === "activity" && (
            activityTimelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={activityTimelineData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#78716c" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e7e5e4" }}
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fontSize: 11, fill: "#78716c" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e7e5e4" }}
                    tickFormatter={(v) => `Rp ${v.toLocaleString("id-ID")}`}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    domain={[0, 'auto']}
                    tick={{ fontSize: 11, fill: "#78716c" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e7e5e4" }}
                    tickFormatter={(v) => `${v} Tx`}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#fff", borderRadius: "12px", border: "1px solid #e7e5e4", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                    labelFormatter={(l) => `Tanggal: ${l}`}
                  />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="spend"
                    name="Pengeluaran (Rupiah)"
                    stroke="#10b981"
                    strokeWidth={3}
                    dot={{ r: 4, fill: "#10b981", strokeWidth: 1 }}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="transactions"
                    name="Frekuensi Transaksi"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 4, fill: "#3b82f6", strokeWidth: 1 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-stone-400 text-sm italic">
                Data aktivitas transaksi dalam timeline kosong. Lakukan transaksi untuk melihat grafik dinamika pengeluaran.
              </div>
            )
          )}

          {activeChartTab === "chats" && (
            activityTimelineData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={activityTimelineData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#78716c" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e7e5e4" }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#78716c" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e7e5e4" }}
                    tickFormatter={(v) => `${v} Pesan`}
                  />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#fff", borderRadius: "12px", border: "1px solid #e7e5e4", boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)" }}
                    labelFormatter={(l) => `Tanggal: ${l}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="messages"
                    name="Jumlah Chat Masuk"
                    stroke="#8b5cf6"
                    strokeWidth={3}
                    dot={{ r: 5, fill: "#8b5cf6", strokeWidth: 2, stroke: "#fff" }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-stone-400 text-sm italic">
                Data aktivitas komunikasi WhatsApp kosong.
              </div>
            )
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SECTION C: Interaction Timeline */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4">
            Riwayat Interaksi
          </h2>

          {/* Tabs */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setActiveTab("transactions")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === "transactions"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-primary-100 text-stone-600 hover:bg-primary-200"
              }`}
            >
              Transaksi
            </button>
            <button
              onClick={() => setActiveTab("messages")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === "messages"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-primary-100 text-stone-600 hover:bg-primary-200"
              }`}
            >
              WhatsApp
            </button>
          </div>

          {/* Timeline Content */}
          <div className="space-y-3 max-h-[400px] overflow-y-auto">
            {timelineLoading ? (
              <div className="text-center py-8 text-stone-500">Memuat...</div>
            ) : timeline?.items?.length > 0 || timeline?.data?.length > 0 ? (
              (timeline.items || timeline.data).map((item, idx) => (
                <TimelineItem
                  key={item.id || idx}
                  item={item}
                  type={activeTab}
                />
              ))
            ) : (
              <div className="text-center py-8 text-stone-500">
                Tidak ada data{" "}
                {activeTab === "transactions" ? "transaksi" : "pesan"}
              </div>
            )}
          </div>
        </div>
      </div>
      </>
      )}

      {/* Modals */}
      <CreateActionModal
        isOpen={showCreateAction}
        onClose={() => setShowCreateAction(false)}
        customerId={id}
        customerName={customer.name}
      />

      <ActionHistoryModal
        isOpen={showActionHistory}
        onClose={() => setShowActionHistory(false)}
        actions={actions?.actions || []}
      />
    </div>
  );
}

function TimelineItem({ item, type }) {
  if (type === "transactions") {
    return (
      <div className="flex items-start gap-3 p-3 border-l-4 border-primary-500 bg-primary-50 rounded-r-lg">
        <Calendar className="h-5 w-5 text-primary-600 mt-0.5 shrink-0" />
        <div className="flex-1">
          <div className="flex justify-between items-start">
            <span className="font-medium text-primary-900">
              {item.data?.service_type || item.description || "Transaksi"}
            </span>
            <span className="text-green-600 font-semibold">
              {formatCurrency(item.amount || 0)}
            </span>
          </div>
          <span className="text-sm text-stone-500">{formatDate(item.date)}</span>
        </div>
      </div>
    );
  }

  // Messages/Feedback
  const isNegative =
    item.sentiment === "negative" ||
    (item.sentiment_score && item.sentiment_score < -0.3);
  return (
    <div
      className={`flex items-start gap-3 p-3 border-l-4 rounded-r-lg ${
        isNegative ? "border-red-500 bg-red-50" : "border-primary-300 bg-primary-50"
      }`}
    >
      <MessageSquare className="h-5 w-5 text-primary-600 mt-0.5 shrink-0" />
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          {item.sentiment === "negative" && <Badge color="red">Negatif</Badge>}
          {item.sentiment === "positive" && (
            <Badge color="green">Positif</Badge>
          )}
          {item.sentiment === "neutral" && <Badge color="gray">Netral</Badge>}
        </div>
        <p className="text-sm text-primary-800 line-clamp-2">{item.description}</p>
        <span className="text-xs text-stone-500 mt-1 block">
          {formatDate(item.date, "d MMM yyyy, HH:mm")}
        </span>
      </div>
    </div>
  );
}

export default CustomerDetail;
