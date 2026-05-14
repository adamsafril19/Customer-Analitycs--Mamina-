// src/components/dashboard/KPICard.jsx
import { cn } from "../../lib/utils";
import { Sparkles } from "lucide-react";

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
    <div
      className={cn(
        "relative overflow-hidden bg-white/80 backdrop-blur-sm rounded-2xl border border-pink-100 shadow-md hover:shadow-pink-200/40 transition-all duration-300 hover:-translate-y-1 p-6",
        className
      )}
    >
      {/* Decorative tiny sparkle */}
      <div className="absolute top-2 right-2 text-pink-200 opacity-50">
        <Sparkles className="h-4 w-4" />
      </div>

      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-stone-500 flex items-center gap-1">
            {title}
          </p>
          <p className="text-3xl font-bold bg-gradient-to-r from-pink-600 to-purple-600 bg-clip-text text-transparent mt-1">
            {value}
          </p>
          {subtext && (
            <p className="text-xs text-pink-400 mt-1 font-medium">{subtext}</p>
          )}
          {trend && (
            <div
              className={cn(
                "flex items-center gap-1 mt-2 text-sm font-medium",
                trend === "up" ? "text-emerald-500" : "text-rose-500"
              )}
            >
              <span>{trend === "up" ? "↑" : "↓"}</span>
              <span>{trendValue}</span>
            </div>
          )}
        </div>
        {icon && (
          <div className="p-3 bg-gradient-to-br from-pink-100 to-purple-100 rounded-2xl shadow-inner border border-white/50">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

export default KPICard;