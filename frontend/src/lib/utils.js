import { clsx } from "clsx";
import { format, formatDistanceToNow, parseISO } from "date-fns";
import { id } from "date-fns/locale";

/**
 * Combine class names with clsx
 */
export function cn(...inputs) {
  return clsx(inputs);
}

/**
 * Format currency to Indonesian Rupiah
 */
export function formatCurrency(amount) {
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
}

/**
 * Format date to Indonesian locale
 */
export function formatDate(date, formatStr = "d MMMM yyyy") {
  if (!date) return "-";
  const parsedDate = typeof date === "string" ? parseISO(date) : date;
  return format(parsedDate, formatStr, { locale: id });
}

/**
 * Format date to relative time (e.g., "3 hari lalu")
 */
export function formatRelativeTime(date) {
  if (!date) return "-";
  const parsedDate = typeof date === "string" ? parseISO(date) : date;
  return formatDistanceToNow(parsedDate, { addSuffix: true, locale: id });
}

/**
 * Get risk level from churn score
 */
export function getRiskLevel(score) {
  if (score >= 0.7) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

/**
 * Get risk label in Indonesian
 */
export function getRiskLabel(level) {
  const labels = {
    low: "Risiko Rendah",
    medium: "Risiko Sedang",
    high: "Risiko Tinggi",
  };
  return labels[level] || level;
}

/**
 * Get risk color classes
 */
export function getRiskColors(level) {
  const colors = {
    low: {
      bg: "bg-green-100",
      text: "text-green-800",
      border: "border-green-500",
      badge: "bg-green-500 text-white",
      progress: "bg-green-500",
    },
    medium: {
      bg: "bg-yellow-100",
      text: "text-yellow-800",
      border: "border-yellow-500",
      badge: "bg-yellow-500 text-white",
      progress: "bg-yellow-500",
    },
    high: {
      bg: "bg-red-100",
      text: "text-red-800",
      border: "border-red-500",
      badge: "bg-red-500 text-white",
      progress: "bg-red-500",
    },
  };
  return colors[level] || colors.low;
}

/**
 * Mask phone number for display
 */
export function maskPhone(phone) {
  if (!phone) return "-";
  if (phone.length < 8) return phone;
  return phone.slice(0, 4) + "****" + phone.slice(-4);
}

/**
 * Truncate text with ellipsis
 */
export function truncate(text, maxLength = 50) {
  if (!text) return "";
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

/**
 * Get initials from name
 */
export function getInitials(name) {
  if (!name) return "??";
  return name
    .split(" ")
    .map((word) => word[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

/**
 * Feature labels mapping (SHAP features to Indonesian)
 */
export const FEATURE_LABELS = {
  avg_sentiment_30: "Sentimen Negatif",
  f_score: "Frekuensi Kunjungan",
  response_time_secs: "Waktu Respon Admin",
  m_score: "Nilai Transaksi",
  tenure_days: "Lama Berlangganan",
  r_score: "Recency Kunjungan",
  total_transactions: "Total Transaksi",
  avg_transaction_value: "Nilai Rata-rata Transaksi",
  message_count_30: "Jumlah Pesan",
  negative_message_ratio: "Rasio Pesan Negatif",
};

/**
 * Explainability mapping for SHAP features
 */
export const EXPLAINABILITY_MAP = {
  avg_sentiment_30: {
    icon: "⬇️",
    title: "Sentimen negatif berulang",
    getDetail: (value, impact) => {
      const impactLabel =
        Math.abs(impact) > 0.2
          ? "Tinggi"
          : Math.abs(impact) > 0.1
          ? "Sedang"
          : "Rendah";
      return `Impact: ${impactLabel} | Sentimen rata-rata: ${(
        value * 100
      ).toFixed(0)}%`;
    },
  },
  f_score: {
    icon: "⬇️",
    title: "Frekuensi kunjungan menurun",
    getDetail: (value, impact) => {
      const impactLabel =
        Math.abs(impact) > 0.2
          ? "Tinggi"
          : Math.abs(impact) > 0.1
          ? "Sedang"
          : "Rendah";
      return `Impact: ${impactLabel} | Skor frekuensi: ${(value * 100).toFixed(
        0
      )}%`;
    },
  },
  response_time_secs: {
    icon: "⬆️",
    title: "Waktu respon admin meningkat",
    getDetail: (value, impact) => {
      const hours = (value / 3600).toFixed(1);
      const impactLabel =
        Math.abs(impact) > 0.2
          ? "Tinggi"
          : Math.abs(impact) > 0.1
          ? "Sedang"
          : "Rendah";
      return `Impact: ${impactLabel} | Rata-rata ${hours} jam`;
    },
  },
  m_score: {
    icon: "⬇️",
    title: "Nilai transaksi menurun",
    getDetail: (value, impact) => {
      const impactLabel =
        Math.abs(impact) > 0.2
          ? "Tinggi"
          : Math.abs(impact) > 0.1
          ? "Sedang"
          : "Rendah";
      return `Impact: ${impactLabel} | Skor nilai: ${(value * 100).toFixed(
        0
      )}%`;
    },
  },
  tenure_days: {
    icon: "⚠️",
    title: "Customer masih baru",
    getDetail: (value, impact) => {
      const months = Math.floor(value / 30);
      const impactLabel =
        Math.abs(impact) > 0.2
          ? "Tinggi"
          : Math.abs(impact) > 0.1
          ? "Sedang"
          : "Rendah";
      return `Impact: ${impactLabel} | Bergabung ${months} bulan lalu`;
    },
  },
  r_score: {
    icon: "⬇️",
    title: "Sudah lama tidak berkunjung",
    getDetail: (value, impact) => {
      const impactLabel =
        Math.abs(impact) > 0.2
          ? "Tinggi"
          : Math.abs(impact) > 0.1
          ? "Sedang"
          : "Rendah";
      return `Impact: ${impactLabel} | Skor recency: ${(value * 100).toFixed(
        0
      )}%`;
    },
  },
};

/**
 * Action suggestions based on risk level
 */
export const ACTION_SUGGESTIONS = {
  high: [
    { icon: "📞", text: "Follow up via WhatsApp", type: "call" },
    { icon: "🎁", text: "Tawarkan promo reactivation 20%", type: "promo" },
    { icon: "📅", text: "Jadwalkan reminder booking", type: "reminder" },
  ],
  medium: [
    { icon: "💬", text: "Kirim pesan check-in", type: "message" },
    { icon: "🎉", text: "Info promo member", type: "promo" },
  ],
  low: [{ icon: "👍", text: "Customer dalam kondisi baik", type: "none" }],
};

/**
 * Action type labels
 */
export const ACTION_TYPE_LABELS = {
  call: "Telepon/WhatsApp",
  message: "Kirim Pesan",
  promo: "Promo/Diskon",
  reminder: "Reminder",
  visit: "Kunjungan",
  other: "Lainnya",
};

/**
 * Action status labels
 */
export const ACTION_STATUS_LABELS = {
  pending: "Menunggu",
  in_progress: "Sedang Dikerjakan",
  completed: "Selesai",
  cancelled: "Dibatalkan",
};

/**
 * Action priority labels
 */
export const PRIORITY_LABELS = {
  low: "Rendah",
  medium: "Sedang",
  high: "Tinggi",
};

/**
 * Get priority color classes
 */
export function getPriorityColors(priority) {
  const colors = {
    low: "bg-gray-100 text-gray-800",
    medium: "bg-blue-100 text-blue-800",
    high: "bg-red-100 text-red-800",
  };
  return colors[priority] || colors.low;
}

/**
 * Get action status color classes
 */
export function getStatusColors(status) {
  const colors = {
    pending: "bg-yellow-100 text-yellow-800",
    in_progress: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    cancelled: "bg-gray-100 text-gray-800",
  };
  return colors[status] || colors.pending;
}

/**
 * Sentiment color based on value
 */
export function getSentimentColor(sentiment) {
  if (sentiment >= 0.3) return "text-green-600";
  if (sentiment >= -0.3) return "text-yellow-600";
  return "text-red-600";
}

/**
 * Sentiment emoji based on value
 */
export function getSentimentEmoji(sentiment) {
  if (sentiment >= 0.3) return "😊";
  if (sentiment >= -0.3) return "😐";
  return "😞";
}
