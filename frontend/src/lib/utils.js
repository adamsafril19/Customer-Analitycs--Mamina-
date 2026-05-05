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
 * Get risk level from behavioral risk score (0-1)
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
 * Feature labels mapping v3.0.0 — 20 behavioral risk features to Indonesian
 */
export const FEATURE_LABELS = {
  // Trend (5)
  recency_ratio: "Rasio Keterlambatan Kunjungan",
  frequency_trend_smoothed: "Tren Frekuensi Kunjungan",
  spend_trend_smoothed: "Tren Pengeluaran",
  msg_trend_smoothed: "Tren Komunikasi",
  sentiment_trend: "Tren Sentimen",
  // Context (5)
  recency_days: "Hari Sejak Kunjungan Terakhir",
  tx_count_90d: "Jumlah Transaksi (90 Hari)",
  spend_90d: "Total Pengeluaran (90 Hari)",
  avg_tx_value: "Rata-rata Nilai Transaksi",
  tenure_days: "Lama Berlangganan",
  // Magnitude (2)
  activity_mean: "Rata-rata Aktivitas",
  recent_activity_avg: "Aktivitas Terkini",
  // Volatility (3)
  activity_std: "Stabilitas Frekuensi",
  activity_cv: "Volatilitas Aktivitas",
  spend_volatility_cv: "Volatilitas Pengeluaran",
  // Interaction (1)
  trend_magnitude_interaction: "Interaksi Tren × Aktivitas",
  // NLP (4)
  avg_sentiment_score: "Sentimen Rata-rata",
  complaint_ratio: "Rasio Komplain",
  msg_volatility: "Volatilitas Pesan",
  response_delay_mean: "Waktu Respon Admin",
};

/**
 * Explainability mapping v3.0.0 — Behavioral risk factor descriptions
 */
const impactLabel = (impact) =>
  Math.abs(impact) > 0.2 ? "Tinggi" : Math.abs(impact) > 0.1 ? "Sedang" : "Rendah";

export const EXPLAINABILITY_MAP = {
  recency_ratio: {
    icon: "⏰",
    title: "Kunjungan terlambat dari pola biasa",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Rasio keterlambatan: ${value?.toFixed(1)}x`,
  },
  frequency_trend_smoothed: {
    icon: "📉",
    title: "Tren frekuensi kunjungan menurun",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Slope tren: ${value?.toFixed(3)}`,
  },
  spend_trend_smoothed: {
    icon: "💸",
    title: "Tren pengeluaran menurun",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Slope tren: ${value?.toFixed(3)}`,
  },
  msg_trend_smoothed: {
    icon: "💬",
    title: "Tren komunikasi menurun",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Slope tren: ${value?.toFixed(3)}`,
  },
  sentiment_trend: {
    icon: "😔",
    title: "Sentimen memburuk",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Perubahan sentimen: ${value?.toFixed(2)}`,
  },
  recency_days: {
    icon: "📅",
    title: "Sudah lama tidak berkunjung",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | ${Math.round(value || 0)} hari sejak kunjungan terakhir`,
  },
  tx_count_90d: {
    icon: "🔢",
    title: "Frekuensi transaksi rendah",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | ${Math.round(value || 0)} transaksi dalam 90 hari`,
  },
  spend_90d: {
    icon: "💰",
    title: "Pengeluaran dalam 90 hari",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Rp ${(value || 0).toLocaleString("id-ID")}`,
  },
  avg_tx_value: {
    icon: "🧾",
    title: "Rata-rata nilai transaksi",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Rp ${(value || 0).toLocaleString("id-ID")}`,
  },
  tenure_days: {
    icon: "⚠️",
    title: "Durasi berlangganan",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Bergabung ${Math.floor((value || 0) / 30)} bulan lalu`,
  },
  activity_mean: {
    icon: "📊",
    title: "Tingkat aktivitas rata-rata",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Rata-rata: ${value?.toFixed(1)} per window`,
  },
  recent_activity_avg: {
    icon: "📈",
    title: "Aktivitas terkini",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Aktivitas terkini: ${value?.toFixed(1)}`,
  },
  activity_std: {
    icon: "📉",
    title: "Ketidakstabilan frekuensi",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Std deviasi: ${value?.toFixed(2)}`,
  },
  activity_cv: {
    icon: "🔀",
    title: "Volatilitas aktivitas tinggi",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | CV: ${value?.toFixed(2)}`,
  },
  spend_volatility_cv: {
    icon: "💱",
    title: "Pengeluaran tidak stabil",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | CV pengeluaran: ${value?.toFixed(2)}`,
  },
  trend_magnitude_interaction: {
    icon: "🔗",
    title: "Penurunan pada customer aktif",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Interaksi tren×aktivitas: ${value?.toFixed(3)}`,
  },
  avg_sentiment_score: {
    icon: "😐",
    title: "Sentimen rata-rata rendah",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Sentimen: ${((value || 0) * 100).toFixed(0)}%`,
  },
  complaint_ratio: {
    icon: "🚨",
    title: "Rasio komplain tinggi",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Komplain: ${((value || 0) * 100).toFixed(0)}%`,
  },
  msg_volatility: {
    icon: "📱",
    title: "Pola komunikasi tidak stabil",
    getDetail: (value, impact) =>
      `Impact: ${impactLabel(impact)} | Volatilitas: ${value?.toFixed(2)}`,
  },
  response_delay_mean: {
    icon: "⏱️",
    title: "Waktu respon admin lambat",
    getDetail: (value, impact) => {
      const hours = ((value || 0) / 3600).toFixed(1);
      return `Impact: ${impactLabel(impact)} | Rata-rata ${hours} jam`;
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
