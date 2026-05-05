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

function RiskTrendChart({ data }) {
  const formattedData =
    data?.map((item) => ({
      ...item,
      date: format(parseISO(item.date), "d MMM", { locale: id }),
      // Backend returns risk_rate already as percentage
      risk_rate: parseFloat((item.risk_rate || 0).toFixed(1)),
    })) || [];

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 rounded-lg shadow-lg border">
          <p className="text-sm font-medium text-gray-900">{label}</p>
          <p className="text-sm text-gray-600">
            Risk rate:{" "}
            <span className="font-semibold">{payload[0].value}%</span>
          </p>
          {payload[0].payload.high_risk !== undefined && (
            <p className="text-sm text-gray-600">
              High risk:{" "}
              <span className="font-semibold text-red-600">
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
    <div className="bg-white rounded-lg shadow-md p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">
        Tren Risiko (30 Hari Terakhir)
      </h3>
      <div className="h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={formattedData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#e5e7eb" }}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "#e5e7eb" }}
              tickFormatter={(value) => `${value}%`}
            />
            <Tooltip content={<CustomTooltip />} />
            <Line
              type="monotone"
              dataKey="risk_rate"
              stroke="#ef4444"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6, strokeWidth: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default RiskTrendChart;
