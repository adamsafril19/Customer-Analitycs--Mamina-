import { useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  ClipboardList,
  Filter,
  Check,
  Clock,
  XCircle,
  Loader2,
} from "lucide-react";
import { useActions, useUpdateAction } from "../hooks/useActions";
import Table from "../components/common/Table";
import Pagination from "../components/common/Pagination";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import EmptyState from "../components/common/EmptyState";
import Modal from "../components/common/Modal";
import { TableRowSkeleton } from "../components/common/Skeleton";
import {
  formatDate,
  formatRelativeTime,
  ACTION_TYPE_LABELS,
  ACTION_STATUS_LABELS,
  PRIORITY_LABELS,
  getStatusColors,
  getPriorityColors,
} from "../lib/utils";

function Actions() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedAction, setSelectedAction] = useState(null);
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  // Get params from URL
  const status = searchParams.get("status") || "";
  const priority = searchParams.get("priority") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = 20;

  // Fetch actions
  const { data, isLoading, error } = useActions({
    status: status || undefined,
    priority: priority || undefined,
    page,
    limit,
  });

  const actions = data?.actions || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit);

  // Update action mutation
  const updateAction = useUpdateAction();

  // Handle filter change
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

  // Handle page change
  const handlePageChange = useCallback(
    (newPage) => {
      const newParams = new URLSearchParams(searchParams);
      newParams.set("page", newPage.toString());
      setSearchParams(newParams);
    },
    [searchParams, setSearchParams]
  );

  // Handle status update
  const handleStatusUpdate = async (actionId, newStatus) => {
    try {
      await updateAction.mutateAsync({
        id: actionId,
        data: { status: newStatus },
      });
    } catch (error) {
      // Error handled by mutation
    }
  };

  // Stats calculation
  const stats = {
    pending: actions.filter((a) => a.status === "pending").length,
    in_progress: actions.filter((a) => a.status === "in_progress").length,
    completed: actions.filter((a) => a.status === "completed").length,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <ClipboardList className="h-6 w-6 text-blue-600" />
            Follow-Up Actions
          </h1>
          <p className="text-gray-500 mt-1">Kelola tindak lanjut customer</p>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <Clock className="h-8 w-8 text-yellow-600" />
            <div>
              <p className="text-2xl font-bold text-yellow-700">
                {stats.pending}
              </p>
              <p className="text-sm text-yellow-600">Menunggu</p>
            </div>
          </div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <Loader2 className="h-8 w-8 text-blue-600" />
            <div>
              <p className="text-2xl font-bold text-blue-700">
                {stats.in_progress}
              </p>
              <p className="text-sm text-blue-600">Sedang Dikerjakan</p>
            </div>
          </div>
        </div>
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <Check className="h-8 w-8 text-green-600" />
            <div>
              <p className="text-2xl font-bold text-green-700">
                {stats.completed}
              </p>
              <p className="text-sm text-green-600">Selesai</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-gray-400" />
            <select
              value={status}
              onChange={(e) => handleFilterChange("status", e.target.value)}
              className="input w-auto"
            >
              <option value="">Semua Status</option>
              <option value="pending">Menunggu</option>
              <option value="in_progress">Sedang Dikerjakan</option>
              <option value="completed">Selesai</option>
              <option value="cancelled">Dibatalkan</option>
            </select>
          </div>

          {/* Priority Filter */}
          <select
            value={priority}
            onChange={(e) => handleFilterChange("priority", e.target.value)}
            className="input w-auto"
          >
            <option value="">Semua Prioritas</option>
            <option value="high">Prioritas Tinggi</option>
            <option value="medium">Prioritas Sedang</option>
            <option value="low">Prioritas Rendah</option>
          </select>
        </div>
      </div>

      {/* Actions Table */}
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
            icon="📋"
            title="Belum ada action"
            description="Buat action dari halaman customer detail"
          />
        ) : (
          <Table>
            <Table.Header>
              <Table.Row>
                <Table.Head>Customer</Table.Head>
                <Table.Head>Tipe Aksi</Table.Head>
                <Table.Head>Prioritas</Table.Head>
                <Table.Head>Status</Table.Head>
                <Table.Head>Deadline</Table.Head>
                <Table.Head>Catatan</Table.Head>
                <Table.Head className="text-right">Aksi</Table.Head>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {actions.map((action) => (
                <Table.Row key={action.action_id}>
                  <Table.Cell>
                    <button
                      onClick={() =>
                        navigate(`/customers/${action.customer_id}`)
                      }
                      className="font-medium text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      {action.customer_name}
                    </button>
                  </Table.Cell>
                  <Table.Cell>
                    {ACTION_TYPE_LABELS[action.action_type] ||
                      action.action_type}
                  </Table.Cell>
                  <Table.Cell>
                    <span
                      className={`badge ${getPriorityColors(action.priority)}`}
                    >
                      {PRIORITY_LABELS[action.priority] || action.priority}
                    </span>
                  </Table.Cell>
                  <Table.Cell>
                    <span className={`badge ${getStatusColors(action.status)}`}>
                      {ACTION_STATUS_LABELS[action.status] || action.status}
                    </span>
                  </Table.Cell>
                  <Table.Cell className="text-gray-500">
                    {formatDate(action.due_date)}
                  </Table.Cell>
                  <Table.Cell className="text-gray-500 max-w-xs truncate">
                    {action.notes || "-"}
                  </Table.Cell>
                  <Table.Cell className="text-right">
                    <div className="flex items-center justify-end gap-1">
                      {action.status === "pending" && (
                        <button
                          onClick={() =>
                            handleStatusUpdate(action.action_id, "in_progress")
                          }
                          className="p-1 text-blue-600 hover:text-blue-800"
                          title="Mulai Kerjakan"
                        >
                          <Loader2 className="h-5 w-5" />
                        </button>
                      )}
                      {action.status === "in_progress" && (
                        <button
                          onClick={() =>
                            handleStatusUpdate(action.action_id, "completed")
                          }
                          className="p-1 text-green-600 hover:text-green-800"
                          title="Selesaikan"
                        >
                          <Check className="h-5 w-5" />
                        </button>
                      )}
                      {action.status !== "completed" &&
                        action.status !== "cancelled" && (
                          <button
                            onClick={() =>
                              handleStatusUpdate(action.action_id, "cancelled")
                            }
                            className="p-1 text-red-600 hover:text-red-800"
                            title="Batalkan"
                          >
                            <XCircle className="h-5 w-5" />
                          </button>
                        )}
                    </div>
                  </Table.Cell>
                </Table.Row>
              ))}
            </Table.Body>
          </Table>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
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
