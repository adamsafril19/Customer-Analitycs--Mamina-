import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { actionsAPI } from "../lib/api";
import toast from "react-hot-toast";

export function useActions(params = {}) {
  return useQuery({
    queryKey: ["actions", params],
    queryFn: () => actionsAPI.getAll(params).then((res) => res.data),
    staleTime: 2 * 60 * 1000,
  });
}

export function useAction(actionId) {
  return useQuery({
    queryKey: ["action", actionId],
    queryFn: () => actionsAPI.getById(actionId).then((res) => res.data),
    enabled: !!actionId,
    staleTime: 2 * 60 * 1000,
  });
}

export function useCustomerActions(customerId) {
  return useQuery({
    queryKey: ["customerActions", customerId],
    queryFn: async () => {
      const res = await actionsAPI.getByCustomer(customerId);
      // Backend returns { customer_id, total, actions }
      return res.data;
    },
    enabled: !!customerId,
    staleTime: 2 * 60 * 1000,
  });
}

export function useCreateAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) => actionsAPI.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
      queryClient.invalidateQueries({ queryKey: ["customerActions"] });
      toast.success("Action berhasil dibuat!");
    },
    onError: (error) => {
      toast.error(error.response?.data?.message || "Gagal membuat action");
    },
  });
}

export function useUpdateAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }) => actionsAPI.update(id, data),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
      queryClient.invalidateQueries({ queryKey: ["action", id] });
      queryClient.invalidateQueries({ queryKey: ["customerActions"] });
      toast.success("Action berhasil diupdate!");
    },
    onError: (error) => {
      toast.error(error.response?.data?.message || "Gagal mengupdate action");
    },
  });
}

export function useDeleteAction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id) => actionsAPI.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["actions"] });
      queryClient.invalidateQueries({ queryKey: ["customerActions"] });
      toast.success("Action berhasil dihapus!");
    },
    onError: (error) => {
      toast.error(error.response?.data?.message || "Gagal menghapus action");
    },
  });
}
