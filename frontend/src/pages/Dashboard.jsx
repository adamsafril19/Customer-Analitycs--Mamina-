import {
  Users,
  AlertTriangle,
  TrendingUp,
  Bell,
  RefreshCw,
} from "lucide-react";
import {
  useDashboardStats,
  useDashboardTrend,
  useTopDrivers,
} from "../hooks/useDashboard";
import { useCustomers } from "../hooks/useCustomers";
import KPICard from "../components/dashboard/KPICard";
import ChurnTrendChart from "../components/dashboard/ChurnTrendChart";
import TopDriversChart from "../components/dashboard/TopDriversChart";
import RecentHighRiskTable from "../components/dashboard/RecentHighRiskTable";
import { CardSkeleton, ChartSkeleton } from "../components/common/Skeleton";
import Button from "../components/common/Button";

function Dashboard() {
  const {
    data: stats,
    isLoading: statsLoading,
    refetch: refetchStats,
  } = useDashboardStats();
  const { data: trend, isLoading: trendLoading } = useDashboardTrend(30);
  const { data: drivers, isLoading: driversLoading } = useTopDrivers();
  const { data: highRiskCustomers, isLoading: customersLoading } = useCustomers(
    {
      risk_level: "high",
      limit: 5,
    }
  );

  const handleRefresh = () => {
    refetchStats();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Overview risiko churn customer</p>
        </div>
        <Button
          variant="outline"
          icon={<RefreshCw className="h-4 w-4" />}
          onClick={handleRefresh}
        >
          Refresh
        </Button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statsLoading ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : (
          <>
            <KPICard
              title="Total Customers"
              value={stats?.total_customers?.toLocaleString() || "0"}
              icon={<Users className="h-6 w-6 text-blue-600" />}
              subtext="Total customers aktif"
            />
            <KPICard
              title="Customers At Risk"
              value={stats?.at_risk_count?.toLocaleString() || "0"}
              icon={<AlertTriangle className="h-6 w-6 text-red-600" />}
              subtext="Butuh perhatian"
              className="border-l-4 border-red-500"
            />
            <KPICard
              title="Rata-rata Churn Score"
              value={`${((stats?.avg_churn_score || 0) * 100).toFixed(1)}%`}
              icon={<TrendingUp className="h-6 w-6 text-yellow-600" />}
              subtext="Level risiko keseluruhan"
            />
            <KPICard
              title="Prediksi Baru (7 Hari)"
              value={stats?.new_predictions_7d?.toLocaleString() || "0"}
              icon={<Bell className="h-6 w-6 text-green-600" />}
              subtext="Penilaian terbaru"
            />
          </>
        )}
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {trendLoading ? (
          <ChartSkeleton />
        ) : (
          <ChurnTrendChart data={trend?.data} />
        )}

        {driversLoading ? (
          <ChartSkeleton />
        ) : (
          <TopDriversChart data={drivers} />
        )}
      </div>

      {/* Recent High Risk Table */}
      {customersLoading ? (
        <ChartSkeleton height={200} />
      ) : (
        <RecentHighRiskTable customers={highRiskCustomers?.customers} />
      )}
    </div>
  );
}

export default Dashboard;
