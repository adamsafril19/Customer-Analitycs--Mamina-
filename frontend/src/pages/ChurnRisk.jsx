import { useState, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { AlertTriangle, Eye, Plus, Filter } from "lucide-react";
import { usePredictions } from "../hooks/useDashboard";
import Table from "../components/common/Table";
import Pagination from "../components/common/Pagination";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import RiskLevelBadge from "../components/customer/RiskLevelBadge";
import EmptyState from "../components/common/EmptyState";
import { TableRowSkeleton } from "../components/common/Skeleton";
import CreateActionModal from "../components/actions/CreateActionModal";
import { formatRelativeTime, truncate } from "../lib/utils";

function ChurnRisk() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [showCreateAction, setShowCreateAction] = useState(false);

  // Get params from URL
  const label = searchParams.get("label") || "high";
  const sort = searchParams.get("sort") || "score";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = 20;

  // Fetch predictions
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

  // Handle create action
  const handleCreateAction = (prediction) => {
    setSelectedCustomer({
      id: prediction.customer_id,
      name: prediction.customer_name,
    });
    setShowCreateAction(true);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-red-500" />
            Churn Risk Management
          </h1>
          <p className="text-gray-500 mt-1">
            {total > 0
              ? `${total} customer berisiko`
              : "Pantau customer berisiko churn"}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Risk Level Tabs */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            {[
              { value: "", label: "Semua" },
              { value: "high", label: "Tinggi (>0.7)" },
              { value: "medium", label: "Sedang (0.4-0.7)" },
              { value: "low", label: "Rendah (<0.4)" },
            ].map((option) => (
              <button
                key={option.value}
                onClick={() => handleFilterChange("label", option.value)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition ${
                  label === option.value
                    ? "bg-white shadow text-blue-600"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>

          {/* Sort */}
          <div className="flex items-center gap-2 ml-auto">
            <Filter className="h-5 w-5 text-gray-400" />
            <select
              value={sort}
              onChange={(e) => handleFilterChange("sort", e.target.value)}
              className="input w-auto"
            >
              <option value="score">Urutkan: Skor Tertinggi</option>
              <option value="last_visit">Urutkan: Kunjungan Terakhir</option>
              <option value="name">Urutkan: Nama A-Z</option>
            </select>
          </div>
        </div>
      </div>

      {/* Predictions Table */}
      <div className="bg-white rounded-lg shadow-md">
        {isLoading ? (
          <table className="min-w-full">
            <tbody>
              {Array.from({ length: 10 }).map((_, i) => (
                <TableRowSkeleton key={i} columns={6} />
              ))}
            </tbody>
          </table>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Gagal memuat data prediksi
          </div>
        ) : predictions.length === 0 ? (
          <EmptyState
            icon="✅"
            title="Tidak ada customer berisiko"
            description="Semua customer dalam kondisi baik"
          />
        ) : (
          <Table>
            <Table.Header>
              <Table.Row>
                <Table.Head>Customer</Table.Head>
                <Table.Head>Skor Churn</Table.Head>
                <Table.Head>Risk Level</Table.Head>
                <Table.Head>Alasan Utama</Table.Head>
                <Table.Head>Prediksi Terakhir</Table.Head>
                <Table.Head className="text-right">Aksi</Table.Head>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {predictions.map((prediction) => (
                <Table.Row
                  key={prediction.pred_id}
                  onClick={() =>
                    navigate(`/customers/${prediction.customer_id}`)
                  }
                >
                  <Table.Cell className="font-medium text-gray-900">
                    {prediction.customer_name}
                  </Table.Cell>
                  <Table.Cell>
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-gray-200 rounded-full h-2">
                        <div
                          className={`h-2 rounded-full ${
                            prediction.churn_score > 0.7
                              ? "bg-red-500"
                              : prediction.churn_score > 0.4
                              ? "bg-yellow-500"
                              : "bg-green-500"
                          }`}
                          style={{ width: `${prediction.churn_score * 100}%` }}
                        />
                      </div>
                      <span className="text-sm font-semibold">
                        {(prediction.churn_score * 100).toFixed(0)}%
                      </span>
                    </div>
                  </Table.Cell>
                  <Table.Cell>
                    <RiskLevelBadge level={prediction.churn_label} />
                  </Table.Cell>
                  <Table.Cell className="text-gray-500 max-w-xs">
                    {truncate(prediction.top_reason, 40)}
                  </Table.Cell>
                  <Table.Cell className="text-gray-500">
                    {formatRelativeTime(prediction.created_at)}
                  </Table.Cell>
                  <Table.Cell className="text-right">
                    <div className="flex items-center justify-end gap-2">
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
                        className="p-1 text-green-600 hover:text-green-800"
                        title="Buat Action"
                      >
                        <Plus className="h-5 w-5" />
                      </button>
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

      {/* Create Action Modal */}
      {selectedCustomer && (
        <CreateActionModal
          isOpen={showCreateAction}
          onClose={() => {
            setShowCreateAction(false);
            setSelectedCustomer(null);
          }}
          customerId={selectedCustomer.id}
          customerName={selectedCustomer.name}
        />
      )}
    </div>
  );
}

export default ChurnRisk;
