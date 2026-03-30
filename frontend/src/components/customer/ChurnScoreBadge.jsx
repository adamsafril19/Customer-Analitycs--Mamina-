import { cn, getRiskLevel, getRiskColors } from "../../lib/utils";

function ChurnScoreBadge({ score, showLabel = true, size = "md" }) {
  const level = getRiskLevel(score);
  const colors = getRiskColors(level);
  const percentage = (score * 100).toFixed(0);

  const sizes = {
    sm: "h-1.5",
    md: "h-2.5",
    lg: "h-3",
  };

  return (
    <div className="flex items-center gap-2">
      <div
        className={cn("w-full bg-gray-200 rounded-full flex-1", sizes[size])}
      >
        <div
          className={cn(
            "rounded-full transition-all duration-500",
            sizes[size],
            colors.progress
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-sm font-semibold min-w-[3rem] text-right">
          {percentage}%
        </span>
      )}
    </div>
  );
}

export default ChurnScoreBadge;
