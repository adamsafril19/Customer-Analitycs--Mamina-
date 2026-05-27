import { useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  Check,
  ClipboardList,
  Eye,
  Filter,
  Loader2,
  PhoneCall,
  Tag,
  XCircle,
} from "lucide-react";
import { useActions, useUpdateAction } from "../hooks/useActions";
import Table from "../components/common/Table";
import Pagination from "../components/common/Pagination";
import Badge from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import { TableRowSkeleton } from "../components/common/Skeleton";
import {
  ACTION_TYPE_LABELS,
  formatDate,
  formatRelativeTime,
} from "../lib/utils";

const STATUS_OPTIONS = [
  { value: "", label: "Semua" },
  { value: "pending", label: "Menunggu" },
  { value: "in_progress", label: "Dikerjakan" },
  { value: "completed", label: "Selesai" },
  { value: "cancelled", label: "Batal" },
];

const PRIORITY_OPTIONS = [
  { value: "", label: "Semua Prioritas" },
  { value: "high", label: "Tinggi" },
  { value: "medium", label: "Sedang" },
  { value: "low", label: "Rendah" },
];

const STATUS_BADGE = {
  pending: { color: "yellow", label: "Menunggu" },
  in_progress: { color: "blue", label: "Dikerjakan" },
  completed: { color: "green", label: "Selesai" },
  cancelled: { color: "gray", label: "Dibatalkan" },
};

const PRIORITY_BADGE = {
  high: { color: "red", label: "Tinggi" },
  medium: { color: "yellow", label: "Sedang" },
  low: { color: "gray", label: "Rendah" },
};

function getDueState(dueDate) {
  if (!dueDate) return { label: "Tanpa deadline", color: "gray" };

  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(dueDate);
  due.setHours(0, 0, 0, 0);
  const diffDays = Math.round((due - today) / 86400000);

  if (diffDays < 0) return { label: "Terlambat", color: "red" };
  if (diffDays === 0) return { label: "Hari ini", color: "orange" };
  if (diffDays <= 2) return { label: `${diffDays} hari lagi`, color: "yellow" };
  return { label: formatRelativeTime(dueDate), color: "gray" };
}

function ActionButtons({ action, onStatusUpdate, isPending }) {
  const disabled = isPending;

  return (
    <div className="flex items-center justify-end gap-1">
      {action.status === "pending" && (
        <button
          onClick={() => onStatusUpdate(action.action_id, "in_progress")}
          disabled={disabled}
          className="p-2 text-primary-600 hover:text-primary-800 hover:bg-primary-50 rounded-lg transition-colors disabled:opacity-50"
          title="Mulai kerjakan"
        >
          <Loader2 className="h-5 w-5" />
        </button>
      )}
      {action.status === "in_progress" && (
        <button
          onClick={() => onStatusUpdate(action.action_id, "completed")}
          disabled={disabled}
          className="p-2 text-emerald-600 hover:text-emerald-800 hover:bg-emerald-50 rounded-lg transition-colors disabled:opacity-50"
          title="Tandai selesai"
        >
          <Check className="h-5 w-5" />
        </button>
      )}
      {action.status !== "completed" && action.status !== "cancelled" && (
        <button
          onClick={() => onStatusUpdate(action.action_id, "cancelled")}
          disabled={disabled}
          className="p-2 text-rose-600 hover:text-rose-800 hover:bg-rose-50 rounded-lg transition-colors disabled:opacity-50"
          title="Batalkan"
        >
          <XCircle className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}

function Actions() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const status = searchParams.get("status") || "";
  const priority = searchParams.get("priority") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = 20;

  const { data, isLoading, error } = useActions({
    status: status || undefined,
    priority: priority || undefined,
    page,
    limit,
  });

  const actions = data?.actions || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);
  const updateAction = useUpdateAction();

  const stats = {
    open: actions.filter((a) => ["pending", "in_progress"].includes(a.status)).length,
    pending: actions.filter((a) => a.status === "pending").length,
    in_progress: actions.filter((a) => a.status === "in_progress").length,
    overdue: actions.filter(
      (a) =>
        !["completed", "cancelled"].includes(a.status) &&
        getDueState(a.due_date).label === "Terlambat"
    ).length,
  };

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

  const handleStatusUpdate = async (actionId, newStatus) => {
    await updateAction.mutateAsync({
      id: actionId,
      data: { status: newStatus },
    });
  };

  const renderActionMeta = (action) => {
    const due = getDueState(action.due_date);
    const statusInfo = STATUS_BADGE[action.status] || STATUS_BADGE.pending;
    const priorityInfo = PRIORITY_BADGE[action.priority] || PRIORITY_BADGE.medium;

    return { due, statusInfo, priorityInfo };
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-primary-900 flex items-center gap-2">
            <ClipboardList className="h-6 w-6 text-primary-600" />
            Follow-Up Actions
          </h1>
          <p className="text-stone-500 mt-1 font-medium">
            Queue tindak lanjut customer, dari assignment sampai selesai.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="rounded-lg bg-white border border-primary-100 px-4 py-3 shadow-sm">
            <p className="text-xs text-stone-500">Open queue</p>
            <p className="text-xl font-bold text-primary-900">{stats.open}</p>
          </div>
          <div className="rounded-lg bg-white border border-amber-100 px-4 py-3 shadow-sm">
            <p className="text-xs text-stone-500">Menunggu</p>
            <p className="text-xl font-bold text-amber-600">{stats.pending}</p>
          </div>
          <div className="rounded-lg bg-white border border-blue-100 px-4 py-3 shadow-sm">
            <p className="text-xs text-stone-500">Dikerjakan</p>
            <p className="text-xl font-bold text-blue-600">{stats.in_progress}</p>
          </div>
          <div className="rounded-lg bg-white border border-rose-100 px-4 py-3 shadow-sm">
            <p className="text-xs text-stone-500">Terlambat</p>
            <p className="text-xl font-bold text-rose-600">{stats.overdue}</p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-md p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-wrap items-center gap-1 bg-primary-100 rounded-lg p-1">
            {STATUS_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => handleFilterChange("status", option.value)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                  status === option.value
                    ? "bg-white shadow text-primary-700"
                    : "text-stone-600 hover:text-primary-900"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-primary-400" />
            <select
              value={priority}
              onChange={(e) => handleFilterChange("priority", e.target.value)}
              className="input w-full sm:w-auto"
            >
              {PRIORITY_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
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
            Gagal memuat data actions
          </div>
        ) : actions.length === 0 ? (
          <EmptyState
            icon={<ClipboardList className="h-14 w-14 mx-auto text-primary-300" />}
            title="Belum ada action"
            description="Buat action dari customer detail atau risk prioritization."
          />
        ) : (
          <>
            <div className="hidden xl:block">
              <Table className="table-fixed">
                <colgroup>
                  <col className="w-[21%]" />
                  <col className="w-[14%]" />
                  <col className="w-[12%]" />
                  <col className="w-[13%]" />
                  <col className="w-[15%]" />
                  <col className="w-[19%]" />
                  <col className="w-[6%]" />
                </colgroup>
                <Table.Header>
                  <Table.Row>
                    <Table.Head className="px-4">Customer</Table.Head>
                    <Table.Head className="px-4">Tipe</Table.Head>
                    <Table.Head className="px-4">Prioritas</Table.Head>
                    <Table.Head className="px-4">Status</Table.Head>
                    <Table.Head className="px-4">Deadline</Table.Head>
                    <Table.Head className="px-4">Catatan</Table.Head>
                    <Table.Head className="px-4 text-right">Aksi</Table.Head>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {actions.map((action) => {
                    const { due, statusInfo, priorityInfo } = renderActionMeta(action);
                    return (
                      <Table.Row key={action.action_id}>
                        <Table.Cell className="px-4 align-top whitespace-normal">
                          <button
                            onClick={() => navigate(`/customers/${action.customer_id}`)}
                            className="font-semibold text-primary-700 hover:text-primary-900 hover:underline text-left leading-snug"
                          >
                            {action.customer_name || "Customer"}
                          </button>
                          <p className="text-xs text-stone-500 mt-1">
                            Dibuat {formatRelativeTime(action.created_at)}
                          </p>
                        </Table.Cell>
                        <Table.Cell className="px-4 align-top whitespace-normal">
                          <div className="flex items-center gap-2 text-stone-700">
                            <PhoneCall className="h-4 w-4 text-primary-500 shrink-0" />
                            <span>
                              {ACTION_TYPE_LABELS[action.action_type] ||
                                action.action_type}
                            </span>
                          </div>
                        </Table.Cell>
                        <Table.Cell className="px-4 align-top">
                          <Badge color={priorityInfo.color}>{priorityInfo.label}</Badge>
                        </Table.Cell>
                        <Table.Cell className="px-4 align-top">
                          <Badge color={statusInfo.color}>{statusInfo.label}</Badge>
                        </Table.Cell>
                        <Table.Cell className="px-4 align-top whitespace-normal">
                          <div className="space-y-1">
                            <Badge color={due.color}>{due.label}</Badge>
                            <p className="text-xs text-stone-500">
                              {formatDate(action.due_date)}
                            </p>
                          </div>
                        </Table.Cell>
                        <Table.Cell className="px-4 align-top text-stone-600 whitespace-normal">
                          <p className="line-clamp-3">{action.notes || "-"}</p>
                          {action.assigned_to && (
                            <p className="text-xs text-stone-500 mt-1">
                              Assigned: {action.assigned_to}
                            </p>
                          )}
                        </Table.Cell>
                        <Table.Cell className="px-4 align-top text-right">
                          <ActionButtons
                            action={action}
                            onStatusUpdate={handleStatusUpdate}
                            isPending={updateAction.isPending}
                          />
                        </Table.Cell>
                      </Table.Row>
                    );
                  })}
                </Table.Body>
              </Table>
            </div>

            <div className="xl:hidden divide-y divide-gray-200">
              {actions.map((action) => {
                const { due, statusInfo, priorityInfo } = renderActionMeta(action);
                return (
                  <div key={action.action_id} className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap gap-2 mb-2">
                          <Badge color={statusInfo.color}>{statusInfo.label}</Badge>
                          <Badge color={priorityInfo.color}>
                            {priorityInfo.label}
                          </Badge>
                          <Badge color={due.color}>{due.label}</Badge>
                        </div>
                        <button
                          onClick={() => navigate(`/customers/${action.customer_id}`)}
                          className="font-semibold text-primary-800 text-left leading-snug"
                        >
                          {action.customer_name || "Customer"}
                        </button>
                        <p className="text-xs text-stone-500 mt-1">
                          {ACTION_TYPE_LABELS[action.action_type] ||
                            action.action_type}
                          {" | "}
                          {formatDate(action.due_date)}
                        </p>
                      </div>
                      <button
                        onClick={() => navigate(`/customers/${action.customer_id}`)}
                        className="p-2 text-blue-600 hover:text-blue-800 shrink-0"
                        title="Lihat customer"
                      >
                        <Eye className="h-5 w-5" />
                      </button>
                    </div>

                    <div className="mt-3 rounded-lg bg-primary-50 border border-primary-100 p-3">
                      <div className="flex items-start gap-2">
                        <Tag className="h-4 w-4 text-primary-500 mt-0.5 shrink-0" />
                        <p className="text-sm text-stone-700">
                          {action.notes || "Tidak ada catatan."}
                        </p>
                      </div>
                    </div>

                    <div className="mt-3 flex items-center justify-between">
                      <p className="text-xs text-stone-500">
                        Dibuat {formatRelativeTime(action.created_at)}
                      </p>
                      <ActionButtons
                        action={action}
                        onStatusUpdate={handleStatusUpdate}
                        isPending={updateAction.isPending}
                      />
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
    </div>
  );
}

export default Actions;
