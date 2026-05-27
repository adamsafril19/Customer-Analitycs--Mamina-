import { useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  CalendarClock,
  CheckCircle2,
  Eye,
  Filter,
  Plus,
  Target,
} from "lucide-react";
import { usePredictions } from "../hooks/useDashboard";
import Table from "../components/common/Table";
import Pagination from "../components/common/Pagination";
import Badge from "../components/common/Badge";
import RiskLevelBadge from "../components/customer/RiskLevelBadge";
import EmptyState from "../components/common/EmptyState";
import { TableRowSkeleton } from "../components/common/Skeleton";
import CreateActionModal from "../components/actions/CreateActionModal";
import {
  ACTION_STATUS_LABELS,
  formatCurrency,
  formatRelativeTime,
  truncate,
} from "../lib/utils";

const URGENCY_BADGE = {
  critical: { color: "red", label: "Hari ini" },
  high: { color: "orange", label: "Segera" },
  medium: { color: "yellow", label: "Pantau" },
  low: { color: "gray", label: "Monitoring" },
  in_progress: { color: "blue", label: "Aktif" },
};

const STATUS_BADGE = {
  not_started: { color: "red", label: "Belum ditindak" },
  pending: { color: "yellow", label: "Menunggu" },
  in_progress: { color: "blue", label: "Dikerjakan" },
  completed: { color: "green", label: "Selesai" },
  cancelled: { color: "gray", label: "Dibatalkan" },
};

function RecommendationSummary({ recommendation, compact = false }) {
  const label = recommendation?.label || "Review manual";
  const notes = recommendation?.notes || "Belum ada penjabaran rekomendasi.";
  const previewLength = compact ? 120 : 86;

  return (
    <div className="relative group">
      <p className="font-medium text-stone-700">
        {label}
      </p>
      <p className="text-xs text-stone-500 mt-1 cursor-help">
        {truncate(notes, previewLength)}
      </p>
      <div className="pointer-events-none absolute left-0 top-full z-30 mt-2 hidden w-[min(28rem,calc(100vw-2rem))] max-h-64 overflow-y-auto rounded-lg border border-primary-100 bg-white p-4 text-left shadow-xl group-hover:block">
        <p className="text-xs font-semibold uppercase text-primary-600">
          Penjabaran rekomendasi
        </p>
        <p className="mt-1 whitespace-normal break-words text-sm font-semibold leading-snug text-stone-800">
          {label}
        </p>
        <p className="mt-2 whitespace-pre-wrap break-words text-xs leading-relaxed text-stone-600">
          {notes}
        </p>
      </div>
    </div>
  );
}

function ChurnRisk() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedWorkItem, setSelectedWorkItem] = useState(null);
  const [showCreateAction, setShowCreateAction] = useState(false);

  const label = searchParams.get("label") || "high";
  const sort = searchParams.get("sort") || "priority";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = 20;

  const { data, isLoading, error } = usePredictions({
    label: label || undefined,
    sort,
    order: "desc",
    page,
    limit,
  });

  const predictions = data?.predictions || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);
  const openQueueCount = predictions.filter(
    (prediction) => prediction.work_status === "not_started"
  ).length;
  const activeFollowUps = predictions.filter((prediction) =>
    ["pending", "in_progress"].includes(prediction.work_status)
  ).length;

  const handleFilterChange = useCallback(
    (key, value) => {
      const newParams = new URLSearchParams(searchParams);
      if (value) {
        newParams.set(key, value);
      } else {
        newParams.delete(key);
      }
      newParams.set("page", "1");
      setSearchParams(newParams);
    },
    [searchParams, setSearchParams]
  );

  const handlePageChange = useCallback(
    (newPage) => {
      const newParams = new URLSearchParams(searchParams);
      newParams.set("page", newPage.toString());
      setSearchParams(newParams);
    },
    [searchParams, setSearchParams]
  );

  const handleCreateAction = (prediction) => {
    setSelectedWorkItem(prediction);
    setShowCreateAction(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-primary-900 flex items-center gap-2">
            <Target className="h-6 w-6 text-rose-500" />
            Risk Prioritization
          </h1>
          <p className="text-stone-500 mt-1">
            Work queue untuk menentukan customer yang perlu ditindaklanjuti dulu.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          <div className="rounded-lg bg-white border border-primary-100 px-4 py-3 shadow-sm">
            <p className="text-xs text-stone-500">Queue terbuka</p>
            <p className="text-xl font-bold text-rose-600">{openQueueCount}</p>
          </div>
          <div className="rounded-lg bg-white border border-primary-100 px-4 py-3 shadow-sm">
            <p className="text-xs text-stone-500">Follow-up aktif</p>
            <p className="text-xl font-bold text-blue-600">{activeFollowUps}</p>
          </div>
          <div className="rounded-lg bg-white border border-primary-100 px-4 py-3 shadow-sm col-span-2 sm:col-span-1">
            <p className="text-xs text-stone-500">Total hasil filter</p>
            <p className="text-xl font-bold text-primary-900">{total}</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-md p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-1 bg-primary-100 rounded-lg p-1">
            {[
              { value: "high", label: "Prioritas Tinggi" },
              { value: "medium", label: "Risiko Sedang" },
              { value: "", label: "Semua Risiko" },
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => handleFilterChange("label", option.value)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                  label === option.value
                    ? "bg-white shadow text-blue-600"
                    : "text-stone-600 hover:text-primary-900"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <Filter className="h-5 w-5 text-primary-400" />
            <select
              value={sort}
              onChange={(e) => handleFilterChange("sort", e.target.value)}
              className="input w-auto"
            >
              <option value="priority">Prioritas: Risk Score</option>
              <option value="score">Risk Score Tertinggi</option>
              <option value="name">Nama Customer</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-md">
        {isLoading ? (
          <table className="min-w-full">
            <tbody>
              {Array.from({ length: 10 }).map((_, i) => (
                <TableRowSkeleton key={i} columns={7} />
              ))}
            </tbody>
          </table>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Gagal memuat work queue risiko
          </div>
        ) : predictions.length === 0 ? (
          <EmptyState
            icon="OK"
            title="Tidak ada customer dalam queue"
            description="Tidak ada customer yang sesuai filter saat ini"
          />
        ) : (
          <>
          <div className="hidden xl:block">
          <Table className="table-fixed">
            <colgroup>
              <col className="w-[11%]" />
              <col className="w-[18%]" />
              <col className="w-[14%]" />
              <col className="w-[25%]" />
              <col className="w-[20%]" />
              <col className="w-[8%]" />
              <col className="w-[4%]" />
            </colgroup>
            <Table.Header>
              <Table.Row>
                <Table.Head className="px-4">Prioritas</Table.Head>
                <Table.Head className="px-4">Customer</Table.Head>
                <Table.Head className="px-4">Risiko</Table.Head>
                <Table.Head className="px-4">Alasan dan Data</Table.Head>
                <Table.Head className="px-4">Rekomendasi</Table.Head>
                <Table.Head className="px-4">Status</Table.Head>
                <Table.Head className="px-4 text-right">Aksi</Table.Head>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {predictions.map((prediction) => {
                const urgency = URGENCY_BADGE[prediction.urgency] || URGENCY_BADGE.low;
                const status =
                  STATUS_BADGE[prediction.work_status] || STATUS_BADGE.not_started;
                const hasOpenAction = ["pending", "in_progress"].includes(
                  prediction.work_status
                );

                return (
                  <Table.Row
                    key={prediction.pred_id}
                    onClick={() => navigate(`/customers/${prediction.customer_id}`)}
                  >
                    <Table.Cell className="px-4 align-top whitespace-normal">
                      <div className="space-y-2">
                        <Badge color={urgency.color}>{urgency.label}</Badge>
                        <p className="text-xs text-stone-500">
                          {prediction.urgency_label}
                        </p>
                      </div>
                    </Table.Cell>

                    <Table.Cell className="px-4 align-top whitespace-normal font-medium text-primary-900">
                      <div>
                        <p className="leading-snug">
                          {prediction.customer_name || prediction.customer_id}
                        </p>
                        <p className="text-xs font-normal text-stone-500">
                          {prediction.customer_city || "Kota belum tersedia"}
                        </p>
                      </div>
                    </Table.Cell>

                    <Table.Cell className="px-4 align-top whitespace-normal">
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="w-16 bg-primary-200 rounded-full h-2 shrink-0">
                            <div
                              className={`h-2 rounded-full ${
                                prediction.risk_score > 0.7
                                  ? "bg-red-500"
                                  : prediction.risk_score > 0.4
                                  ? "bg-yellow-500"
                                  : "bg-green-500"
                              }`}
                              style={{
                                width: `${Math.min(
                                  100,
                                  prediction.risk_score * 100
                                )}%`,
                              }}
                            />
                          </div>
                          <span className="text-sm font-semibold">
                            {(prediction.risk_score * 100).toFixed(0)}%
                          </span>
                        </div>
                        <RiskLevelBadge level={prediction.risk_label} />
                      </div>
                    </Table.Cell>

                    <Table.Cell className="px-4 align-top text-stone-600 whitespace-normal">
                      <div className="space-y-2">
                        <p className="font-medium text-stone-700">
                          {prediction.top_reason
                            ? truncate(prediction.top_reason, 84)
                            : "Belum ada alasan model"}
                        </p>
                        <div className="grid grid-cols-1 gap-1 text-xs text-stone-500">
                          <span className="inline-flex items-center">
                            <CalendarClock className="inline h-3.5 w-3.5 mr-1" />
                            {prediction.last_visit
                              ? formatRelativeTime(prediction.last_visit)
                              : "Belum ada kunjungan"}
                          </span>
                          {prediction.recency_days != null && (
                            <span>{prediction.recency_days} hari sejak kunjungan</span>
                          )}
                          <span>
                            {prediction.tx_count_90d ?? "-"} transaksi/90 hari
                            {prediction.spend_90d != null
                              ? ` | ${formatCurrency(prediction.spend_90d)}`
                              : ""}
                          </span>
                        </div>
                      </div>
                    </Table.Cell>

                    <Table.Cell className="px-4 align-top text-stone-600 whitespace-normal">
                      <RecommendationSummary
                        recommendation={prediction.recommended_action}
                      />
                    </Table.Cell>

                    <Table.Cell className="px-4 align-top whitespace-normal">
                      <div className="space-y-2">
                        <Badge color={status.color} className="whitespace-nowrap">
                          {status.label}
                        </Badge>
                        {prediction.latest_action && (
                          <p className="text-xs text-stone-500">
                            {ACTION_STATUS_LABELS[prediction.latest_action.status] ||
                              prediction.latest_action.status}
                            {prediction.latest_action.due_date
                              ? ` - due ${formatRelativeTime(
                                  prediction.latest_action.due_date
                                )}`
                              : ""}
                          </p>
                        )}
                      </div>
                    </Table.Cell>

                    <Table.Cell className="px-4 align-top text-right">
                      <div className="flex flex-col items-end gap-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            navigate(`/customers/${prediction.customer_id}`);
                          }}
                          className="p-1 text-blue-600 hover:text-blue-800"
                          title="Lihat Detail"
                        >
                          <Eye className="h-5 w-5" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCreateAction(prediction);
                          }}
                          className={`p-1 ${
                            hasOpenAction
                              ? "text-stone-400 hover:text-stone-600"
                              : "text-green-600 hover:text-green-800"
                          }`}
                          title={
                            hasOpenAction
                              ? "Tambah follow-up lanjutan"
                              : "Buat action follow-up"
                          }
                        >
                          {hasOpenAction ? (
                            <CheckCircle2 className="h-5 w-5" />
                          ) : (
                            <Plus className="h-5 w-5" />
                          )}
                        </button>
                      </div>
                    </Table.Cell>
                  </Table.Row>
                );
              })}
            </Table.Body>
          </Table>
          </div>

          <div className="xl:hidden divide-y divide-gray-200">
            {predictions.map((prediction) => {
              const urgency = URGENCY_BADGE[prediction.urgency] || URGENCY_BADGE.low;
              const status =
                STATUS_BADGE[prediction.work_status] || STATUS_BADGE.not_started;
              const hasOpenAction = ["pending", "in_progress"].includes(
                prediction.work_status
              );

              return (
                <div
                  key={prediction.pred_id}
                  onClick={() => navigate(`/customers/${prediction.customer_id}`)}
                  className="p-4 cursor-pointer hover:bg-primary-50"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-2">
                        <Badge color={urgency.color}>{urgency.label}</Badge>
                        <Badge color={status.color}>{status.label}</Badge>
                        <RiskLevelBadge level={prediction.risk_label} />
                      </div>
                      <p className="font-semibold text-primary-900 leading-snug">
                        {prediction.customer_name || prediction.customer_id}
                      </p>
                      <p className="text-xs text-stone-500">
                        {prediction.customer_city || "Kota belum tersedia"}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <p className="text-lg font-bold text-rose-600">
                        {(prediction.risk_score * 100).toFixed(0)}%
                      </p>
                      <p className="text-xs text-stone-500">risk score</p>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-2">
                    <div>
                      <p className="text-xs font-semibold uppercase text-stone-400">
                        Alasan
                      </p>
                      <p className="text-sm text-stone-700 mt-1">
                        {prediction.top_reason
                          ? truncate(prediction.top_reason, 110)
                          : "Belum ada alasan model"}
                      </p>
                      <div className="mt-2 grid gap-1 text-xs text-stone-500">
                        <span className="inline-flex items-center">
                          <CalendarClock className="h-3.5 w-3.5 mr-1" />
                          {prediction.last_visit
                            ? formatRelativeTime(prediction.last_visit)
                            : "Belum ada kunjungan"}
                        </span>
                        <span>
                          {prediction.recency_days ?? "-"} hari sejak kunjungan
                          {" | "}
                          {prediction.tx_count_90d ?? "-"} transaksi/90 hari
                        </span>
                        {prediction.spend_90d != null && (
                          <span>{formatCurrency(prediction.spend_90d)}</span>
                        )}
                      </div>
                    </div>

                    <div>
                      <p className="text-xs font-semibold uppercase text-stone-400">
                        Rekomendasi
                      </p>
                      <div className="mt-1">
                        <RecommendationSummary
                          recommendation={prediction.recommended_action}
                          compact
                        />
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center justify-between gap-3">
                    <p className="text-xs text-stone-500">
                      {prediction.latest_action
                        ? ACTION_STATUS_LABELS[prediction.latest_action.status] ||
                          prediction.latest_action.status
                        : prediction.urgency_label}
                    </p>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/customers/${prediction.customer_id}`);
                        }}
                        className="p-2 text-blue-600 hover:text-blue-800"
                        title="Lihat Detail"
                      >
                        <Eye className="h-5 w-5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleCreateAction(prediction);
                        }}
                        className={`p-2 ${
                          hasOpenAction
                            ? "text-stone-400 hover:text-stone-600"
                            : "text-green-600 hover:text-green-800"
                        }`}
                        title={
                          hasOpenAction
                            ? "Tambah follow-up lanjutan"
                            : "Buat action follow-up"
                        }
                      >
                        {hasOpenAction ? (
                          <CheckCircle2 className="h-5 w-5" />
                        ) : (
                          <Plus className="h-5 w-5" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          </>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-stone-500">
            Menampilkan {(page - 1) * limit + 1}-{Math.min(page * limit, total)}{" "}
            dari {total}
          </p>
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={handlePageChange}
          />
        </div>
      )}

      {selectedWorkItem && (
        <CreateActionModal
          isOpen={showCreateAction}
          onClose={() => {
            setShowCreateAction(false);
            setSelectedWorkItem(null);
          }}
          customerId={selectedWorkItem.customer_id}
          customerName={selectedWorkItem.customer_name}
          predictionId={selectedWorkItem.pred_id}
          defaultActionType={selectedWorkItem.recommended_action?.action_type || "call"}
          defaultPriority={selectedWorkItem.risk_label === "high" ? "high" : "medium"}
          defaultNotes={selectedWorkItem.recommended_action?.notes || ""}
        />
      )}
    </div>
  );
}

export default ChurnRisk;
