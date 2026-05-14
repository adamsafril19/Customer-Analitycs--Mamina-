import { cn } from "../../lib/utils";

const colorMap = {
  green: "bg-emerald-100 text-emerald-800 border border-emerald-200",
  yellow: "bg-amber-100 text-amber-800 border border-amber-200",
  red: "bg-rose-100 text-rose-800 border border-rose-200",
  blue: "bg-primary-100 text-primary-800 border border-primary-200",
  gray: "bg-primary-100 text-primary-800 border border-primary-200",
  purple: "bg-purple-100 text-purple-800 border border-purple-200",
  orange: "bg-orange-100 text-orange-800 border border-orange-200",
};

function Badge({ children, color = "gray", className, ...props }) {
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
        colorMap[color],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}

export default Badge;
