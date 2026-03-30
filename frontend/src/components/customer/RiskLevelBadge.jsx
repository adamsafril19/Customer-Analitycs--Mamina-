import { cn, getRiskLevel, getRiskLabel, getRiskColors } from "../../lib/utils";

function RiskLevelBadge({ level, score, size = "md" }) {
  const riskLevel = level || getRiskLevel(score);
  const colors = getRiskColors(riskLevel);
  const label = getRiskLabel(riskLevel);

  const sizes = {
    sm: "px-2 py-0.5 text-xs",
    md: "px-2.5 py-0.5 text-xs",
    lg: "px-3 py-1 text-sm",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-medium",
        sizes[size],
        colors.bg,
        colors.text
      )}
    >
      {label}
    </span>
  );
}

export default RiskLevelBadge;
