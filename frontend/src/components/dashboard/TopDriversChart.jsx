import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { FEATURE_LABELS } from "../../lib/utils";

const COLORS = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#3b82f6"];

function TopDriversChart({ data }) {
  // data is already an array from the hook
  const driversArray = Array.isArray(data) ? data : data?.drivers || [];

  const formattedData =
    driversArray.map((item, index) => ({
      ...item,
      label: item.description || FEATURE_LABELS[item.feature] || item.feature,
      // Backend returns avg_impact
      impact: parseFloat(
        (Math.abs(item.avg_impact || item.impact || 0) * 100).toFixed(1)
      ),
      color: COLORS[index % COLORS.length],
    })) || [];

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border">
          <p className="text-sm font-medium text-gray-900">
            {payload[0].payload.label}
          </p>
          <p className="text-sm text-gray-600">
            Impact: <span className="font-semibold">{payload[0].value}%</span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Faktor Utama Penyebab Churn
      </h3>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={formattedData}
            layout="vertical"
            margin={{ left: 20, right: 20 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#f0f0f0"
              horizontal={false}
            />
            <XAxis
              type="number"
              domain={[0, "auto"]}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#e5e7eb" }}
              tickFormatter={(value) => `${value}%`}
            />
            <YAxis
              dataKey="label"
              type="category"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={150}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="impact" radius={[0, 4, 4, 0]}>
              {formattedData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default TopDriversChart;
