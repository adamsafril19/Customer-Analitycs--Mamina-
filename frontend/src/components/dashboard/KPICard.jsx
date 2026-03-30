import { cn } from "../../lib/utils";

function KPICard({
  title,
  value,
  icon,
  subtext,
  trend,
  trendValue,
  className,
}) {
  return (
    <div className={cn("bg-white rounded-lg shadow-md p-6", className)}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-500">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          {subtext && <p className="text-sm text-gray-500 mt-1">{subtext}</p>}
          {trend && (
            <div
              className={cn(
                "flex items-center gap-1 mt-2 text-sm font-medium",
                trend === "up" ? "text-green-600" : "text-red-600"
              )}
            >
              <span>{trend === "up" ? "↑" : "↓"}</span>
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        {icon && <div className="p-3 bg-blue-50 rounded-full">{icon}</div>}
      </div>
    </div>
  );
}

export default KPICard;
