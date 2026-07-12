import axios from "axios";
import toast from "react-hot-toast";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:5000/api";

const api = axios.create({
  baseURL: API_URL,
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
    if (config.data instanceof FormData) {
      delete config.headers["Content-Type"];
    }
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - handle errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.message || "Terjadi kesalahan";

    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/login";
      toast.error("Sesi telah berakhir, silakan login kembali");
    } else if (error.response?.status === 403) {
      toast.error("Anda tidak memiliki akses");
    } else if (error.response?.status === 404) {
      toast.error("Data tidak ditemukan");
    } else if (error.response?.status >= 500) {
      toast.error(message);
    }

    return Promise.reject(error);
  }
);

export default api;

// Auth API
export const authAPI = {
  login: (credentials) => api.post("/auth/login", credentials),
  logout: () => api.post("/auth/logout"),
  me: () => api.get("/auth/me"),
};

// Dashboard API
export const dashboardAPI = {
  getStats: () => api.get("/dashboard/stats"),
  getTrend: (days = 30) => api.get(`/dashboard/trend?days=${days}`),
  getTopDrivers: () => api.get("/dashboard/top-drivers"),
  getBehavioralInsights: () => api.get("/dashboard/behavioral-insights"),
};

// Customers API
export const customersAPI = {
  getAll: (params) => api.get("/customers", { params }),
  getById: (id) => api.get(`/customers/${id}`),
  get360: (id) => api.get(`/customers/${id}/360`),
  getTimeline: (id, type = "transactions", limit = 10) =>
    api.get(`/customers/${id}/timeline`, { params: { type, limit } }),
  getRiskHistory: (id, limit = 20) =>
    api.get(`/customers/${id}/risk-history`, { params: { limit } }),
  getLeadInsights: (limit = 20) =>
    api.get("/leads/insights", { params: { limit } }),
  reviewRecommendation: (contextId, status) =>
    api.patch(`/recommendations/${contextId}/review`, { status }),
  create: (data) => api.post("/customers", data),
  update: (id, data) => api.put(`/customers/${id}`, data),
  delete: (id) => api.delete(`/customers/${id}`),
};

// Predictions API
export const predictionsAPI = {
  getAll: (params) => api.get("/predictions", { params }),
  getByCustomer: (customerId) => api.get(`/predictions/customer/${customerId}`),
  create: (customerId) => api.post(`/predictions`, { customer_id: customerId }),
  runBatch: () => api.post("/predictions/batch"),
};

// Actions API
export const actionsAPI = {
  getAll: (params) => api.get("/actions", { params }),
  getById: (id) => api.get(`/actions/${id}`),
  create: (data) => api.post("/actions", data),
  update: (id, data) => api.patch(`/actions/${id}`, data),
  delete: (id) => api.delete(`/actions/${id}`),
  getByCustomer: (customerId) => api.get(`/actions/customer/${customerId}`),
};

// Settings API
export const settingsAPI = {
  get: () => api.get("/settings"),
  update: (data) => api.put("/settings", data),
};

// Import API (CSV/TXT ingestion)
const _uploadFile = (url, file, metadata = {}) => {
  const formData = new FormData();
  formData.append("file", file);
  Object.entries(metadata).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      formData.append(key, value);
    }
  });
  return api.post(url, formData);
};

export const importAPI = {
  previewCustomers: (file) => _uploadFile("/import/customers/preview", file),
  importCustomers: (file) => _uploadFile("/import/customers", file),
  previewTransactions: (file) => _uploadFile("/import/transactions/preview", file),
  importTransactions: (file) => _uploadFile("/import/transactions", file),
  previewMessages: (file, metadata) => _uploadFile("/import/messages/preview", file, metadata),
  importMessages: (file, metadata) => _uploadFile("/import/messages", file, metadata),
  downloadTemplate: async (type) => {
    const response = await api.get(`/import/template/${type}`, {
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement("a");
    link.href = url;
    const disposition = response.headers["content-disposition"];
    const fallbackName = ["customers", "transactions"].includes(type)
      ? `template_${type}.xlsx`
      : `template_${type}.csv`;
    const filename = disposition
      ? disposition.split('filename="')[1]?.replace('"', "") || fallbackName
      : fallbackName;
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
};

// ML Pipeline API
export const pipelineAPI = {
  getStatus: () => api.get("/pipeline/status"),
  trainTopicModel: (data = {}) => api.post("/pipeline/train-topic-model", data),
  processNLP: () => api.post("/pipeline/process-nlp"),
  generateFeatures: () => api.post("/pipeline/generate-features"),
  runScoring: () => api.post("/pipeline/run-scoring"),
  generateRecommendations: () => api.post("/pipeline/generate-recommendations"),
  retrainModel: (data = {}) => api.post("/pipeline/retrain-model", data),
  getTask: (taskId) => api.get(`/admin/tasks/${taskId}`),
};

// Model Evaluation API
export const modelAPI = {
  getEvaluation: () => api.get("/model/evaluation"),
  getFeatureImportance: () => api.get("/model/feature-importance"),
  getThresholdSensitivity: () => api.get("/model/threshold-sensitivity"),
  getRiskDistribution: () => api.get("/model/risk-distribution"),
  getTopicEvaluation: () => api.get("/model/topic-evaluation"),
};
