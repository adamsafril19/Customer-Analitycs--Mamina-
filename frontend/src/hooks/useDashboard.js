import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { dashboardAPI, predictionsAPI } from "../lib/api";

export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboardStats"],
    queryFn: async () => {
      const res = await dashboardAPI.getStats();
      // Backend returns { success: true, data: {...} }
      return res.data.data || res.data;
    },
    staleTime: 2 * 60 * 1000,
  });
}

export function useDashboardTrend(days = 30) {
  return useQuery({
    queryKey: ["dashboardTrend", days],
    queryFn: async () => {
      const res = await dashboardAPI.getTrend(days);
      // Backend returns { success: true, data: [...] }
      return { data: res.data.data || res.data };
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useTopDrivers() {
  return useQuery({
    queryKey: ["topDrivers"],
    queryFn: async () => {
      const res = await dashboardAPI.getTopDrivers();
      // Backend returns { success: true, data: [...] }
      // Ensure we always return an array
      const data = res.data.data || res.data;
      return Array.isArray(data) ? data : [data];
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function usePredictions(params = {}) {
  return useQuery({
    queryKey: ["predictions", params],
    queryFn: () => predictionsAPI.getAll(params).then((res) => res.data),
    staleTime: 2 * 60 * 1000,
  });
}

export function useCustomerPredictions(customerId) {
  return useQuery({
    queryKey: ["customerPredictions", customerId],
    queryFn: () =>
      predictionsAPI.getByCustomer(customerId).then((res) => res.data),
    enabled: !!customerId,
    staleTime: 2 * 60 * 1000,
  });
}

export function useCreatePrediction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (customerId) => predictionsAPI.create(customerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["predictions"] });
      queryClient.invalidateQueries({ queryKey: ["customerPredictions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardStats"] });
    },
  });
}

export function useRunBatchPrediction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => predictionsAPI.runBatch(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["predictions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardStats"] });
      queryClient.invalidateQueries({ queryKey: ["dashboardTrend"] });
    },
  });
}
