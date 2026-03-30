import { useState, useMemo, useCallback } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { Search, Filter, Plus, Grid, List } from "lucide-react";
import { useCustomers } from "../hooks/useCustomers";
import CustomerTable from "../components/customer/CustomerTable";
import CustomerCard from "../components/customer/CustomerCard";
import Pagination from "../components/common/Pagination";
import Button from "../components/common/Button";
import EmptyState from "../components/common/EmptyState";
import {
  TableRowSkeleton,
  CustomerCardSkeleton,
} from "../components/common/Skeleton";
import { useDebounce } from "../hooks/useDebounce";

function CustomerList() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [viewMode, setViewMode] = useState("table"); // 'table' | 'grid'

  // Get params from URL
  const search = searchParams.get("search") || "";
  const risk = searchParams.get("risk") || "";
  const city = searchParams.get("city") || "";
  const page = parseInt(searchParams.get("page") || "1", 10);
  const limit = 20;

  // Local search state with debounce
  const [searchInput, setSearchInput] = useState(search);
  const debouncedSearch = useDebounce(searchInput, 500);

  // Update URL when debounced search changes
  useMemo(() => {
    if (debouncedSearch !== search) {
      const newParams = new URLSearchParams(searchParams);
      if (debouncedSearch) {
        newParams.set("search", debouncedSearch);
      } else {
        newParams.delete("search");
      }
      newParams.set("page", "1");
      setSearchParams(newParams);
    }
  }, [debouncedSearch]);

  // Fetch customers
  const { data, isLoading, error } = useCustomers({
    search: debouncedSearch,
    risk: risk || undefined,
    city: city || undefined,
    page,
    limit,
  });

  const customers = data?.customers || [];
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Customers</h1>
          <p className="text-gray-500 mt-1">
            {total > 0 ? `${total} customer ditemukan` : "Kelola data customer"}
          </p>
        </div>
        <Button
          icon={<Plus className="h-4 w-4" />}
          onClick={() => navigate("/customers/new")}
        >
          Tambah Customer
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-md p-4">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Cari nama, telepon, email..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="input pl-10"
            />
          </div>

          {/* Risk Filter */}
          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-gray-400" />
            <select
              value={risk}
              onChange={(e) => handleFilterChange("risk", e.target.value)}
              className="input w-auto"
            >
              <option value="">Semua Risiko</option>
              <option value="low">Risiko Rendah</option>
              <option value="medium">Risiko Sedang</option>
              <option value="high">Risiko Tinggi</option>
            </select>
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
            <button
              onClick={() => setViewMode("table")}
              className={`p-2 rounded ${
                viewMode === "table" ? "bg-white shadow" : "hover:bg-gray-200"
              }`}
            >
              <List className="h-5 w-5 text-gray-600" />
            </button>
            <button
              onClick={() => setViewMode("grid")}
              className={`p-2 rounded ${
                viewMode === "grid" ? "bg-white shadow" : "hover:bg-gray-200"
              }`}
            >
              <Grid className="h-5 w-5 text-gray-600" />
            </button>
          </div>
        </div>
      </div>

      {/* Customer List */}
      <div className="bg-white rounded-lg shadow-md">
        {isLoading ? (
          viewMode === "table" ? (
            <table className="min-w-full">
              <tbody>
                {Array.from({ length: 5 }).map((_, i) => (
                  <TableRowSkeleton key={i} columns={6} />
                ))}
              </tbody>
            </table>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <CustomerCardSkeleton key={i} />
              ))}
            </div>
          )
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Gagal memuat data customer
          </div>
        ) : customers.length === 0 ? (
          <EmptyState
            icon="👥"
            title="Tidak ada customer"
            description={
              search || risk
                ? "Tidak ada customer yang sesuai dengan filter"
                : "Belum ada data customer"
            }
            action={search || risk ? "Reset Filter" : "Tambah Customer"}
            onAction={() => {
              if (search || risk) {
                setSearchParams(new URLSearchParams());
                setSearchInput("");
              } else {
                navigate("/customers/new");
              }
            }}
          />
        ) : viewMode === "table" ? (
          <CustomerTable customers={customers} />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
            {customers.map((customer) => (
              <CustomerCard key={customer.customer_id} customer={customer} />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Menampilkan {(page - 1) * limit + 1}-{Math.min(page * limit, total)}{" "}
            dari {total} customer
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

export default CustomerList;
