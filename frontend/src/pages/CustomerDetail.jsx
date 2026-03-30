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
} from "lucide-react";
import { useCustomer360, useCustomerTimeline } from "../hooks/useCustomers";
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
  EXPLAINABILITY_MAP,
  ACTION_SUGGESTIONS,
  getSentimentEmoji,
  getSentimentColor,
} from "../lib/utils";

function CustomerDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("transactions");
  const [showCreateAction, setShowCreateAction] = useState(false);
  const [showActionHistory, setShowActionHistory] = useState(false);

  const { data, isLoading, error } = useCustomer360(id);
  const { data: timeline, isLoading: timelineLoading } = useCustomerTimeline(
    id,
    activeTab
  );
  const { data: actions } = useCustomerActions(id);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
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
  } = data;

  // Map data if quick_stats doesn't exist (backward compatibility)
  const stats = quick_stats || {
    total_transactions: transaction_summary?.total_transactions || 0,
    total_spent: transaction_summary?.total_spent || 0,
    last_visit:
      transaction_summary?.last_transaction_date ||
      customer.last_seen_at ||
      customer.created_at,
    message_count: sentiment_summary?.neg_msg_count_30 || 0, // Fallback, should be total message count
    avg_sentiment_30: sentiment_summary?.avg_sentiment_30 || 0,
  };

  const riskLevel = getRiskLevel(latest_prediction?.churn_score || 0);
  const riskColors = getRiskColors(riskLevel);
  const suggestions = ACTION_SUGGESTIONS[riskLevel] || [];

  // Process top reasons
  const topReasons = (latest_prediction?.top_reasons || [])
    .slice(0, 5)
    .map((reason) => {
      const mapping = EXPLAINABILITY_MAP[reason.feature] || {
        icon: "📊",
        title: reason.feature,
        getDetail: () => reason.description,
      };

      // Calculate impact label
      const impactLevel =
        Math.abs(reason.impact) > 0.2
          ? "high"
          : Math.abs(reason.impact) > 0.1
          ? "medium"
          : "low";

      // Get detail text - use description as fallback if value is not provided
      let detail;
      try {
        if (reason.value !== undefined && reason.value !== null) {
          detail = mapping.getDetail(reason.value, reason.impact);
        } else {
          // Fallback to description from backend
          const impactLabel =
            impactLevel === "high"
              ? "Tinggi"
              : impactLevel === "medium"
              ? "Sedang"
              : "Rendah";
          detail = `Impact: ${impactLabel} | ${reason.description}`;
        }
      } catch {
        detail = reason.description || "Faktor yang mempengaruhi churn";
      }

      return {
        ...reason,
        icon: mapping.icon,
        title: mapping.title,
        detail,
        impactLevel,
      };
    });

  return (
    <div className="space-y-6">
      {/* Back Button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="h-5 w-5" />
        <span>Kembali ke Customers</span>
      </button>

      {/* SECTION A: Customer Summary */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex flex-col lg:flex-row lg:items-start gap-6">
          {/* Avatar & Info */}
          <div className="flex items-start gap-4 flex-1">
            <div className="w-20 h-20 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
              <span className="text-blue-600 font-bold text-2xl">
                {getInitials(customer.name)}
              </span>
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-3 flex-wrap">
                <h1 className="text-2xl font-bold text-gray-900">
                  {customer.name}
                </h1>
                <RiskLevelBadge
                  score={latest_prediction?.churn_score || 0}
                  size="lg"
                />
              </div>
              <div className="flex flex-wrap gap-4 mt-3 text-sm text-gray-600">
                <div className="flex items-center gap-1">
                  <Phone className="h-4 w-4" />
                  <span>
                    {maskPhone(customer.phone_display || customer.phone)}
                  </span>
                </div>
                {customer.email && (
                  <div className="flex items-center gap-1">
                    <Mail className="h-4 w-4" />
                    <span>{customer.email}</span>
                  </div>
                )}
                {customer.city && (
                  <div className="flex items-center gap-1">
                    <MapPin className="h-4 w-4" />
                    <span>{customer.city}</span>
                  </div>
                )}
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  <span>Member sejak {formatDate(customer.created_at)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Churn Score Display */}
          <div className={`p-4 rounded-lg ${riskColors.bg} w-full lg:w-64`}>
            <p className="text-sm font-medium text-gray-600 mb-2">
              Risiko Churn
            </p>
            <div className="mb-2">
              <ChurnScoreBadge
                score={latest_prediction?.churn_score || 0}
                size="lg"
              />
            </div>
            <p className="text-xs text-gray-500">
              Terakhir diperbarui:{" "}
              {formatRelativeTime(latest_prediction?.created_at)}
            </p>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-6 pt-6 border-t">
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <DollarSign className="h-6 w-6 text-green-600 mx-auto mb-2" />
            <p className="text-2xl font-bold text-gray-900">
              {stats?.total_transactions || 0}
            </p>
            <p className="text-sm text-gray-500">Total Transaksi</p>
            <p className="text-xs text-gray-400 mt-1">
              {formatCurrency(stats?.total_spent || 0)}
            </p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <Clock className="h-6 w-6 text-blue-600 mx-auto mb-2" />
            <p className="text-2xl font-bold text-gray-900">
              {stats?.last_visit ? formatRelativeTime(stats.last_visit) : "-"}
            </p>
            <p className="text-sm text-gray-500">Kunjungan Terakhir</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <MessageSquare className="h-6 w-6 text-purple-600 mx-auto mb-2" />
            <p className="text-2xl font-bold text-gray-900">
              {stats?.message_count || 0}
            </p>
            <p className="text-sm text-gray-500">Total Pesan</p>
          </div>
          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <span className="text-3xl block mb-1">
              {getSentimentEmoji(stats?.avg_sentiment_30 || 0)}
            </span>
            <p
              className={`text-xl font-bold ${getSentimentColor(
                stats?.avg_sentiment_30 || 0
              )}`}
            >
              {((stats?.avg_sentiment_30 || 0) * 100).toFixed(0)}%
            </p>
            <p className="text-sm text-gray-500">Sentimen (30 hari)</p>
          </div>
        </div>
      </div>

      {/* SECTION B: Why At Risk? */}
      {topReasons.length > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Mengapa Berisiko Churn?
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
                    : "bg-gray-50 border-gray-300"
                }`}
              >
                <span className="text-2xl">{reason.icon}</span>
                <div className="flex-1">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <h4 className="font-medium text-gray-900">
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
                  <p className="text-sm text-gray-600 mt-1">{reason.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SECTION C: Interaction Timeline */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Riwayat Interaksi
          </h2>

          {/* Tabs */}
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setActiveTab("transactions")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === "transactions"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              Transaksi
            </button>
            <button
              onClick={() => setActiveTab("messages")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                activeTab === "messages"
                  ? "bg-blue-100 text-blue-700"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              WhatsApp
            </button>
          </div>

          {/* Timeline Content */}
          <div className="space-y-3 max-h-[400px] overflow-y-auto">
            {timelineLoading ? (
              <div className="text-center py-8 text-gray-500">Memuat...</div>
            ) : timeline?.items?.length > 0 || timeline?.data?.length > 0 ? (
              (timeline.items || timeline.data).map((item, idx) => (
                <TimelineItem
                  key={item.id || idx}
                  item={item}
                  type={activeTab}
                />
              ))
            ) : (
              <div className="text-center py-8 text-gray-500">
                Tidak ada data{" "}
                {activeTab === "transactions" ? "transaksi" : "pesan"}
              </div>
            )}
          </div>
        </div>

        {/* SECTION D: Suggested Actions */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Rekomendasi Tindakan
          </h2>

          <div className="space-y-3 mb-6">
            {suggestions.map((suggestion, idx) => (
              <div
                key={idx}
                className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition cursor-pointer"
                onClick={() => {
                  if (suggestion.type !== "none") {
                    setShowCreateAction(true);
                  }
                }}
              >
                <span className="text-2xl">{suggestion.icon}</span>
                <span className="flex-1 font-medium text-gray-700">
                  {suggestion.text}
                </span>
                {suggestion.type !== "none" && (
                  <Plus className="h-5 w-5 text-gray-400" />
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
      <div className="flex items-start gap-3 p-3 border-l-4 border-blue-500 bg-blue-50 rounded-r-lg">
        <span className="text-xl">📅</span>
        <div className="flex-1">
          <div className="flex justify-between items-start">
            <span className="font-medium text-gray-900">
              {item.data?.service_type || item.description || "Transaksi"}
            </span>
            <span className="text-green-600 font-semibold">
              {formatCurrency(item.amount || 0)}
            </span>
          </div>
          <span className="text-sm text-gray-500">{formatDate(item.date)}</span>
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
        isNegative ? "border-red-500 bg-red-50" : "border-gray-300 bg-gray-50"
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
        <p className="text-sm text-gray-700 line-clamp-2">{item.description}</p>
        <span className="text-xs text-gray-500 mt-1 block">
          {formatDate(item.date, "d MMM yyyy, HH:mm")}
        </span>
      </div>
    </div>
  );
}

export default CustomerDetail;
