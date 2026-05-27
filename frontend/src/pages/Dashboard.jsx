// src/pages/Dashboard.jsx (sudah baby spa ready)
import {
  Users,
  AlertTriangle,
  TrendingUp,
  RefreshCw,
  Heart,
  Sparkles,
  Baby,
  Cloud,
  Flower2,
  MessageSquare,
} from "lucide-react";
import {
  useDashboardStats,
  useDashboardTrend,
  useTopDrivers,
  useBehavioralInsights,
} from "../hooks/useDashboard";
import { useCustomers } from "../hooks/useCustomers";
import KPICard from "../components/dashboard/KPICard";
import RiskTrendChart from "../components/dashboard/RiskTrendChart";
import TopDriversChart from "../components/dashboard/TopDriversChart";
import RecentHighRiskTable from "../components/dashboard/RecentHighRiskTable";
import { CardSkeleton, ChartSkeleton } from "../components/common/Skeleton";
import Button from "../components/common/Button";

const ICON_MAP = {
  TrendingUp: TrendingUp,
  Users: Users,
  AlertTriangle: AlertTriangle,
  Heart: Heart,
  Baby: Baby,
  MessageSquare: MessageSquare,
};

const COLOR_MAP = {
  pink: {
    card: "from-pink-50/50 to-white border-pink-100/50",
    icon: "bg-pink-100/80 text-pink-600",
  },
  purple: {
    card: "from-purple-50/50 to-white border-purple-100/50",
    icon: "bg-purple-100/80 text-purple-600",
  },
  rose: {
    card: "from-rose-50/50 to-white border-rose-100/50",
    icon: "bg-rose-100/80 text-rose-600",
  },
  blue: {
    card: "from-blue-50/50 to-white border-blue-100/50",
    icon: "bg-blue-100/80 text-blue-600",
  },
};

function Dashboard() {
  const {
    data: stats,
    isLoading: statsLoading,
    refetch: refetchStats,
  } = useDashboardStats();
  const { data: trend, isLoading: trendLoading } = useDashboardTrend(30);
  const { data: drivers, isLoading: driversLoading } = useTopDrivers();
  const { data: insightsData, isLoading: insightsLoading } = useBehavioralInsights();
  const { data: highRiskCustomers, isLoading: customersLoading } = useCustomers(
    {
      risk_level: "high",
      sort: "risk_score",
      order: "desc",
      limit: 5,
    }
  );

  const handleRefresh = () => {
    refetchStats();
  };

  const insights = insightsData?.insights || [];

  return (
    <div className="relative space-y-6">
      {/* Decorative floating elements (Dashboard specific) */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden -z-10">
        <Cloud className="absolute top-5 left-5 h-20 w-20 text-pink-100 opacity-60 animate-float" />
        <Cloud className="absolute bottom-10 right-10 h-24 w-24 text-blue-100 opacity-50 animate-float-delayed" />
        <Sparkles className="absolute top-1/3 right-12 h-6 w-6 text-yellow-200 animate-spin-slow" />
        <Heart className="absolute bottom-1/4 left-8 h-5 w-5 text-pink-200 animate-pulse" />
        <Flower2 className="absolute top-2/3 left-1/4 h-7 w-7 text-purple-100 animate-bounce-slow" />
        <Baby className="absolute bottom-5 right-20 h-8 w-8 text-pink-200/30 rotate-12" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-pink-500 via-purple-500 to-blue-500 bg-clip-text text-transparent flex items-center gap-2">
              <Heart className="h-7 w-7 text-pink-400 fill-pink-200" />
              Dashboard Baby Spa
              <Sparkles className="h-5 w-5 text-yellow-400" />
            </h1>
            <p className="text-stone-500 mt-1 font-medium flex items-center gap-1.5">
              <Baby className="h-4 w-4 text-pink-400" />
              Prioritas risiko penurunan aktivitas pelanggan
              <Sparkles className="h-3.5 w-3.5 text-yellow-400" />
            </p>
          </div>
          <Button
            variant="outline"
            icon={<RefreshCw className="h-4 w-4" />}
            onClick={handleRefresh}
            className="border-pink-200"
          >
            Refresh
          </Button>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-6">
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
                icon={<Users className="h-6 w-6 text-pink-500" />}
                subtext="Total customers aktif"
              />
              <KPICard
                title="Activity Decline Risk"
                value={stats?.at_risk_count?.toLocaleString() || "0"}
                icon={<AlertTriangle className="h-6 w-6 text-rose-400" />}
                subtext="Butuh perhatian prioritas"
                className="border-l-4 border-rose-300"
              />
              <KPICard
                title="Rata-rata Risk Score"
                value={`${((stats?.avg_risk_score || 0) * 100).toFixed(1)}%`}
                icon={<TrendingUp className="h-6 w-6 text-purple-500" />}
                subtext="Tingkat disengagement rata-rata"
              />
              <KPICard
                title="Estimasi Risiko Baru"
                value={stats?.new_predictions_7d?.toLocaleString() || "0"}
                icon={<Baby className="h-6 w-6 text-blue-400" />}
                subtext="Penilaian 7 hari terakhir"
              />
            </>
          )}
        </div>

        {/* Behavioral Insights Summary — Dynamic from ML data */}
        <div className="mb-6">
          <h2 className="text-xl font-bold text-primary-900 mb-3 flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-pink-500" />
            Behavioral Insights Summary
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {insightsLoading ? (
              <>
                <CardSkeleton />
                <CardSkeleton />
                <CardSkeleton />
                <CardSkeleton />
              </>
            ) : insights.length > 0 ? (
              insights.map((insight) => {
                const IconComponent = ICON_MAP[insight.icon] || TrendingUp;
                const colors = COLOR_MAP[insight.color] || COLOR_MAP.pink;
                return (
                  <div
                    key={insight.key}
                    className={`bg-gradient-to-br ${colors.card} backdrop-blur-sm p-4 rounded-2xl border shadow-sm flex items-start gap-3`}
                  >
                    <div className={`p-2 ${colors.icon} rounded-xl mt-0.5`}>
                      <IconComponent className="h-4 w-4" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-stone-700">
                        {insight.title}
                      </h4>
                      <p className="text-xs text-stone-500 mt-1 leading-relaxed">
                        {insight.description}
                      </p>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="col-span-full text-center py-8 text-stone-400 text-sm">
                Belum ada data insight. Jalankan ML Pipeline terlebih dahulu.
              </div>
            )}
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {trendLoading ? (
            <ChartSkeleton />
          ) : (
            <RiskTrendChart data={trend?.data} />
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
    </div>
  );
}

export default Dashboard;
