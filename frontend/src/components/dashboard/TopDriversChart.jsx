// src/components/dashboard/TopDriversChart.jsx
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
import { Flower2 } from "lucide-react";

const COLORS = ["#f97316", "#ec4899", "#a855f7", "#06b6d4", "#84cc16"];

function TopDriversChart({ data }) {
  const driversArray = Array.isArray(data) ? data : data?.drivers || [];

  const formattedData =
    driversArray.map((item, index) => ({
      ...item,
      label: item.description || FEATURE_LABELS[item.feature] || item.feature,
      impact: parseFloat(
        (
          Math.abs(item.avg_contribution ?? item.avg_impact ?? item.impact ?? 0) * 100
        ).toFixed(1)
      ),
      color: COLORS[index % COLORS.length],
    })) || [];

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white/90 backdrop-blur-sm p-3 rounded-2xl shadow-lg border border-purple-100">
          <p className="text-sm font-semibold text-purple-600">
            {payload[0].payload.label}
          </p>
          <p className="text-sm text-stone-600">
            Impact: <span className="font-bold text-purple-500">{payload[0].value}%</span>
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="relative bg-white/70 backdrop-blur-sm rounded-2xl border border-purple-100 shadow-md p-5 transition-all hover:shadow-lg">
      <div className="absolute top-3 right-3 text-purple-200">
        <Flower2 className="h-5 w-5" />
      </div>
      <h3 className="text-lg font-bold bg-gradient-to-r from-purple-500 to-pink-500 bg-clip-text text-transparent mb-4 flex items-center gap-2">
        Faktor Utama Risiko
      </h3>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={formattedData}
            layout="vertical"
            margin={{ left: 20, right: 20 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#f3e8ff" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, "auto"]}
              tick={{ fontSize: 12, fill: "#a8a29e" }}
              tickLine={false}
              axisLine={{ stroke: "#e9d5ff" }}
              tickFormatter={(value) => `${value}%`}
            />
            <YAxis
              dataKey="label"
              type="category"
              tick={{ fontSize: 12, fill: "#a8a29e" }}
              tickLine={false}
              axisLine={false}
              width={150}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="impact" radius={[0, 8, 8, 0]} barSize={32}>
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
