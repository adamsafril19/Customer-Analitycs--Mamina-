import { useState } from "react";
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
  TrendingUp,
  Activity,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Hash,
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
  getSentimentEmoji,
  getSentimentColor,
} from "../lib/utils";

function CustomerDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("transactions");
  const [showCreateAction, setShowCreateAction] = useState(false);
  const [showActionHistory, setShowActionHistory] = useState(false);
  const [showAllFeatures, setShowAllFeatures] = useState(false);

  const { data, isLoading, error } = useCustomer360(id);
  const { data: timeline, isLoading: timelineLoading } = useCustomerTimeline(
    id,
    activeTab
  );
  const { data: actions } = useCustomerActions(id);
  const { data: riskHistory } = useCustomerRiskHistory(id);

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
  } = data;

  // Map data if quick_stats doesn't exist (backward compatibility)
  const stats = quick_stats || {
    total_transactions: transaction_summary?.total_transactions || 0,
    total_spent: transaction_summary?.total_spent || 0,
    last_visit:
      transaction_summary?.last_transaction_date ||
      customer.last_seen_at ||
      customer.created_at,
    message_count: sentiment_summary?.neg_msg_count_30 || 0,
    avg_sentiment_30: sentiment_summary?.avg_sentiment_30 || 0,
  };

  const riskLevel = getRiskLevel(latest_prediction?.risk_score || 0);
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
        icon: mapping.icon,
        title: mapping.title || FEATURE_LABELS[reason.feature] || reason.feature,
        detail,
        impactLevel,
      };
    });

  // Risk history chart data
  const riskHistoryData = (riskHistory?.history || []).map((h) => ({
    date: h.as_of_date,
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
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex flex-col lg:flex-row lg:items-start gap-6">
          {/* Left: Profile Info */}
          <div className="flex-1">
            <div className="flex flex-col md:flex-row md:items-center gap-6">
              <div className="h-20 w-20 bg-gradient-to-br from-primary-100 to-primary-200 rounded-full flex items-center justify-center shrink-0 border-4 border-white shadow-sm">
                <span className="text-primary-700 font-bold text-2xl">
                  {getInitials(customer.name)}
                </span>
              </div>
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-2xl font-bold text-primary-900">
                    {customer.name}
                  </h1>
                  <RiskLevelBadge
                    score={latest_prediction?.risk_score || 0}
                    size="lg"
                  />
                </div>
                <div className="flex items-center gap-4 text-stone-500 mt-1 flex-wrap">
                  {customer.phone_display && (
                    <span className="flex items-center gap-1 text-sm font-medium">
                      <Phone className="h-4 w-4" />
                      {maskPhone(customer.phone_display)}
                    </span>
                  )}
                  {customer.email && (
                    <span className="flex items-center gap-1 text-sm font-medium">
                      <Mail className="h-4 w-4" />
                      {customer.email}
                    </span>
                  )}
                  {customer.city && (
                    <span className="flex items-center gap-1 text-sm font-medium">
                      <MapPin className="h-4 w-4" />
                      {customer.city}
                    </span>
                  )}
                  <span className="flex items-center gap-1 text-sm font-medium">
                    <Calendar className="h-4 w-4" />
                    Member sejak {formatDate(customer.created_at)}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
              <div className="text-center p-4 bg-primary-50 rounded-xl border border-primary-100">
                <DollarSign className="h-5 w-5 text-emerald-500 mx-auto mb-1.5" />
                <p className="text-lg font-bold text-primary-800">
                  {formatCurrency(stats.total_spent || 0)}
                </p>
                <p className="text-xs font-medium text-stone-500">Total Spent</p>
              </div>
              <div className="text-center p-4 bg-primary-50 rounded-xl border border-primary-100">
                <Clock className="h-5 w-5 text-primary-500 mx-auto mb-1.5" />
                <p className="text-lg font-bold text-primary-800">
                  {formatRelativeTime(stats.last_visit)}
                </p>
                <p className="text-xs font-medium text-stone-500">Kunjungan Terakhir</p>
              </div>
              <div className="text-center p-4 bg-primary-50 rounded-xl border border-primary-100">
                <MessageSquare className="h-5 w-5 text-purple-500 mx-auto mb-1.5" />
                <p className="text-lg font-bold text-primary-800">
                  {stats.message_count || 0}
                </p>
                <p className="text-sm text-stone-500">Pesan (30 hari)</p>
              </div>
              <div className="text-center p-3 bg-primary-50 rounded-lg">
                <span className="text-xl block mb-1">
                  {getSentimentEmoji(stats.avg_sentiment_30 || 0)}
                </span>
                <p
                  className={`text-lg font-semibold ${getSentimentColor(
                    stats.avg_sentiment_30 || 0
                  )}`}
                >
                  {((stats.avg_sentiment_30 || 0) * 100).toFixed(0)}%
                </p>
                <p className="text-sm text-stone-500">Sentimen (30 hari)</p>
              </div>
            </div>
          </div>

          {/* Right: Risk Score Display */}
          <div className={`p-4 rounded-lg ${riskColors.bg} w-full lg:w-64`}>
            <p className="text-sm font-medium text-stone-600 mb-2">
              Risk Score
            </p>
            <div className="mb-2">
              <ChurnScoreBadge
                score={latest_prediction?.risk_score || 0}
                size="lg"
              />
            </div>
            <p className="text-xs text-stone-500 mt-2">
              Model: {latest_prediction?.model_version || "-"}
            </p>
            <p className="text-xs text-stone-500">
              Prediksi: {formatDate(latest_prediction?.as_of_date)}
            </p>
          </div>
        </div>
      </div>

      {/* SECTION B: Why At Risk? */}
      {topReasons.length > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4">
            Mengapa Berisiko?
          </h2>
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
                <span className="text-2xl">{reason.icon}</span>
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
        </div>
      )}

      {/* SECTION B2: Profil Risiko & Sinyal Perilaku (NEW — Phase 4) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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

        {/* Sinyal Perilaku (text_signals + text_semantics) */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4 flex items-center gap-2">
            <Activity className="h-5 w-5 text-purple-600" />
            Sinyal Perilaku
          </h2>
          <div className="space-y-4">
            {/* Text Signals */}
            {text_signals && Object.keys(text_signals).length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-stone-500 mb-2">Komunikasi</h3>
                <div className="grid grid-cols-2 gap-3">
                  {text_signals.msg_count_7d != null && (
                    <div className="p-3 bg-primary-50 rounded-lg text-center">
                      <p className="text-lg font-semibold text-primary-800">{text_signals.msg_count_7d}</p>
                      <p className="text-xs text-primary-600">Pesan 7 Hari</p>
                    </div>
                  )}
                  {text_signals.msg_count_30d != null && (
                    <div className="p-3 bg-primary-50 rounded-lg text-center">
                      <p className="text-lg font-semibold text-primary-800">{text_signals.msg_count_30d}</p>
                      <p className="text-xs text-primary-600">Pesan 30 Hari</p>
                    </div>
                  )}
                  {text_signals.complaint_rate_30d != null && (
                    <div className={`p-3 rounded-lg text-center ${
                      text_signals.complaint_rate_30d > 0.3 ? "bg-red-50" : "bg-green-50"
                    }`}>
                      <p className={`text-lg font-semibold ${
                        text_signals.complaint_rate_30d > 0.3 ? "text-red-800" : "text-green-800"
                      }`}>
                        {(text_signals.complaint_rate_30d * 100).toFixed(0)}%
                      </p>
                      <p className={`text-xs ${
                        text_signals.complaint_rate_30d > 0.3 ? "text-red-600" : "text-green-600"
                      }`}>
                        Rasio Komplain
                      </p>
                    </div>
                  )}
                  {text_signals.response_delay_mean != null && (
                    <div className="p-3 bg-primary-50 rounded-lg text-center">
                      <p className="text-lg font-semibold text-primary-800">
                        {(text_signals.response_delay_mean / 3600).toFixed(1)}h
                      </p>
                      <p className="text-xs text-stone-600">Avg Respon</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Sentiment & Topics (BERTopic Integration) */}
            {text_semantics && (
              <div className="space-y-4">
                {/* Dominant Topic */}
                {text_semantics.dominant_topic && (
                  <div className="p-3 bg-purple-50 rounded-lg border border-purple-100">
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2 text-purple-800 font-medium">
                        <Hash className="h-4 w-4" />
                        Topik Dominan: {text_semantics.dominant_topic}
                      </div>
                    </div>
                    <p className="text-[10px] text-purple-600 mb-2 italic">
                      *Topik di-generate oleh BERTopic untuk eksplorasi keluhan, tidak memengaruhi skor risiko secara langsung.
                    </p>
                    {text_semantics.top_keywords && text_semantics.top_keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {text_semantics.top_keywords.map((kw, i) => (
                          <span key={i} className="px-2 py-0.5 bg-white text-purple-600 text-xs rounded-full border border-purple-200">
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                
                {/* Sentiment Distribution */}
                {text_semantics.sentiment_dist && (
                  <div>
                    <h3 className="text-sm font-medium text-stone-500 mb-2">Distribusi Sentimen</h3>
                    <div className="flex gap-2">
                      {Object.entries(text_semantics.sentiment_dist).map(([label, count]) => {
                        const colors = {
                          positive: "bg-green-100 text-green-800",
                          neutral: "bg-primary-100 text-primary-800",
                          negative: "bg-red-100 text-red-800",
                        };
                        return (
                          <div key={label} className={`flex-1 p-2 rounded-lg text-center ${colors[label] || "bg-primary-100 text-primary-800"}`}>
                            <p className="text-lg font-semibold">{count}</p>
                            <p className="text-xs capitalize">{label}</p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Last Messages */}
            {last_messages && last_messages.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-stone-500 mb-2">Pesan Terakhir</h3>
                <div className="space-y-2">
                  {last_messages.slice(0, 3).map((msg, idx) => (
                    <div key={idx} className={`p-2 rounded text-sm border-l-3 ${
                      msg.sentiment_label === "negative"
                        ? "border-l-red-400 bg-red-50"
                        : msg.sentiment_label === "positive"
                        ? "border-l-green-400 bg-green-50"
                        : "border-l-gray-300 bg-primary-50"
                    }`}>
                      <div className="flex items-center gap-2 mb-1">
                        {msg.sentiment_label && (
                          <Badge color={
                            msg.sentiment_label === "negative" ? "red" :
                            msg.sentiment_label === "positive" ? "green" : "gray"
                          } className="text-xs">
                            {msg.sentiment_label}
                          </Badge>
                        )}
                        {msg.has_complaint && <Badge color="red" className="text-xs">Komplain</Badge>}
                      </div>
                      <p className="text-primary-800 text-xs">{msg.text_snippet}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Empty state */}
            {(!text_signals || Object.keys(text_signals).length === 0) &&
             (!text_semantics || Object.keys(text_semantics).length === 0) &&
             (!last_messages || last_messages.length === 0) && (
              <p className="text-sm text-primary-400 text-center py-4">
                Belum ada data sinyal perilaku
              </p>
            )}
          </div>
        </div>
      </div>

      {/* SECTION B3: Risk Score History (NEW — Phase 4) */}
      {riskHistoryData.length > 1 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4 flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-red-500" />
            Histori Risk Score
          </h2>
          <div className="h-[250px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={riskHistoryData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#e5e7eb" }}
                />
                <YAxis
                  domain={[0, 1]}
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: "#e5e7eb" }}
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                />
                <Tooltip
                  formatter={(v) => [`${(v * 100).toFixed(1)}%`, "Risk Score"]}
                  labelFormatter={(l) => `Tanggal: ${l}`}
                />
                <Line
                  type="monotone"
                  dataKey="risk_score"
                  stroke="#ef4444"
                  strokeWidth={2}
                  dot={{ r: 4, fill: "#ef4444" }}
                  activeDot={{ r: 6, strokeWidth: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

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

        {/* SECTION D: Suggested Actions */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-primary-900 mb-4">
            Rekomendasi Tindakan
          </h2>

          <div className="space-y-3 mb-6">
            {suggestions.map((suggestion, idx) => (
              <div
                key={idx}
                className="flex items-center gap-3 p-3 bg-primary-50 rounded-lg hover:bg-primary-100 transition cursor-pointer"
                onClick={() => {
                  if (suggestion.type !== "none") {
                    setShowCreateAction(true);
                  }
                }}
              >
                <span className="text-2xl">{suggestion.icon}</span>
                <span className="flex-1 font-medium text-primary-800">
                  {suggestion.text}
                </span>
                {suggestion.type !== "none" && (
                  <Plus className="h-5 w-5 text-primary-400" />
                )}
              </div>
            ))}
          </div>

          <div className="flex gap-3">
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
        <span className="text-xl">📅</span>
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
      <span className="text-xl">💬</span>
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
