// src/components/common/Button.jsx
import { cn } from "../../lib/utils";
import { Sparkles } from "lucide-react";

const variants = {
  primary: "bg-gradient-to-r from-pink-400 to-purple-400 text-white shadow-md shadow-pink-300/30 hover:shadow-pink-400/40 hover:-translate-y-0.5",
  secondary: "bg-pink-100 text-pink-700 hover:bg-pink-200 hover:-translate-y-0.5",
  danger: "bg-gradient-to-r from-rose-400 to-rose-500 text-white shadow-md shadow-rose-300/30 hover:shadow-rose-400/40 hover:-translate-y-0.5",
  success: "bg-gradient-to-r from-emerald-400 to-emerald-500 text-white shadow-md shadow-emerald-300/30 hover:shadow-emerald-400/40 hover:-translate-y-0.5",
  outline: "border-2 border-pink-200 text-pink-600 hover:bg-pink-50 bg-white/80 hover:-translate-y-0.5 shadow-sm",
  ghost: "text-pink-600 hover:bg-pink-50",
};

const sizes = {
  sm: "px-3 py-1.5 text-sm rounded-xl",
  md: "px-4 py-2 rounded-xl",
  lg: "px-6 py-3 text-lg rounded-2xl",
};

function Button({
  children,
  variant = "primary",
  size = "md",
  className,
  disabled,
  loading,
  icon,
  ...props
}) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-pink-300 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95",
        variants[variant],
        sizes[size],
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <svg
          className="animate-spin h-4 w-4"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      ) : icon ? (
        icon
      ) : (
        variant === "primary" && <Sparkles className="h-4 w-4" />
      )}
      {children}
    </button>
  );
}

export default Button;