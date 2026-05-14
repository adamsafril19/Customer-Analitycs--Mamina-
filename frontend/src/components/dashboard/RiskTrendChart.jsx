// src/components/dashboard/RiskTrendChart.jsx
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { format, parseISO } from "date-fns";
import { id } from "date-fns/locale";
import { Heart } from "lucide-react";

function RiskTrendChart({ data }) {
  const formattedData =
    data?.map((item) => ({
      ...item,
      date: format(parseISO(item.date), "d MMM", { locale: id }),
      risk_rate: parseFloat((item.risk_rate || 0).toFixed(1)),
    })) || [];

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white/90 backdrop-blur-sm p-3 rounded-2xl shadow-lg border border-pink-100">
          <p className="text-sm font-semibold text-pink-600">{label}</p>
          <p className="text-sm text-stone-600">
            Risk rate:{" "}
            <span className="font-bold text-rose-500">{payload[0].value}%</span>
          </p>
          {payload[0].payload.high_risk !== undefined && (
            <p className="text-sm text-stone-600">
              High risk:{" "}
              <span className="font-semibold text-rose-600">
                {payload[0].payload.high_risk}
              </span>
            </p>
          )}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="relative bg-white/70 backdrop-blur-sm rounded-2xl border border-pink-100 shadow-md p-5 transition-all hover:shadow-lg">
      {/* Decorative heart */}
      <div className="absolute top-3 right-3 text-pink-200">
        <Heart className="h-5 w-5 fill-pink-100" />
      </div>
      <h3 className="text-lg font-bold bg-gradient-to-r from-pink-500 to-purple-500 bg-clip-text text-transparent mb-4 flex items-center gap-2">
        Tren Risiko (30 Hari Terakhir)
      </h3>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={formattedData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#fce7f3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12, fill: "#a8a29e" }}
              tickLine={false}
              axisLine={{ stroke: "#fbcfe8" }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 12, fill: "#a8a29e" }}
              tickLine={false}
              axisLine={{ stroke: "#fbcfe8" }}
              tickFormatter={(value) => `${value}%`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="risk_rate"
              stroke="#f43f5e"
              strokeWidth={3}
              dot={{ fill: "#f43f5e", r: 4 }}
              activeDot={{ r: 7, strokeWidth: 2, stroke: "#fecdd3" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default RiskTrendChart;