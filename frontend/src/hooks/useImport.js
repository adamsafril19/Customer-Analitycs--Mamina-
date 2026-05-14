import { useMutation } from "@tanstack/react-query";
import { importAPI } from "../lib/api";

/**
 * Hook for previewing a CSV file before import.
 * @param {"customers"|"transactions"|"messages"} type
 */
export function usePreviewCSV(type) {
  const previewFn = {
    customers: importAPI.previewCustomers,
    transactions: importAPI.previewTransactions,
    messages: importAPI.previewMessages,
  }[type];

  return useMutation({
    mutationFn: (file) => previewFn(file).then((res) => res.data),
  });
}

/**
 * Hook for importing a CSV file.
 * @param {"customers"|"transactions"|"messages"} type
 */
export function useImportCSV(type) {
  const importFn = {
    customers: importAPI.importCustomers,
    transactions: importAPI.importTransactions,
    messages: importAPI.importMessages,
  }[type];

  return useMutation({
    mutationFn: (file) => importFn(file).then((res) => res.data),
  });
}
