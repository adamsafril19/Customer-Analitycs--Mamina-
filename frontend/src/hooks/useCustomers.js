import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { customersAPI } from "../lib/api";

export function useCustomers(params = {}) {
  return useQuery({
    queryKey: ["customers", params],
    queryFn: () => customersAPI.getAll(params).then((res) => res.data),
    staleTime: 5 * 60 * 1000,
  });
}

export function useCustomer(customerId) {
  return useQuery({
    queryKey: ["customer", customerId],
    queryFn: () => customersAPI.getById(customerId).then((res) => res.data),
    enabled: !!customerId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCustomer360(customerId) {
  return useQuery({
    queryKey: ["customer360", customerId],
    queryFn: () => customersAPI.get360(customerId).then((res) => res.data),
    enabled: !!customerId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCustomerTimeline(
  customerId,
  type = "transactions",
  limit = 10
) {
  return useQuery({
    queryKey: ["customerTimeline", customerId, type, limit],
    queryFn: async () => {
      const res = await customersAPI.getTimeline(customerId, type, limit);
      // Backend returns { customer_id, type, total, items }
      // Return as-is, component will access .items
      return res.data;
    },
    enabled: !!customerId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => customersAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useUpdateCustomer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => customersAPI.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["customer", id] });
      queryClient.invalidateQueries({ queryKey: ["customer360", id] });
    },
  });
}

export function useDeleteCustomer() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => customersAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}
