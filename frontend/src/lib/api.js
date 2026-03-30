import axios from "axios";
import toast from "react-hot-toast";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000/api";

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor - add auth token
api.interceptors.request.use(
  (config) => {
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
      toast.error("Terjadi kesalahan pada server");
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
};

// Customers API
export const customersAPI = {
  getAll: (params) => api.get("/customers", { params }),
  getById: (id) => api.get(`/customers/${id}`),
  get360: (id) => api.get(`/customers/${id}/360`),
  getTimeline: (id, type = "transactions", limit = 10) =>
    api.get(`/customers/${id}/timeline`, { params: { type, limit } }),
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
