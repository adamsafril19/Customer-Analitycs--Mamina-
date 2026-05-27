import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { modelAPI, pipelineAPI } from "../lib/api";

export function usePipelineStatus() {
  return useQuery({
    queryKey: ["pipelineStatus"],
    queryFn: () => pipelineAPI.getStatus().then((res) => res.data),
    staleTime: 30 * 1000,
    retry: 1,
    refetchOnWindowFocus: false,
  });
}

export function usePipelineTask(taskId) {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["pipelineTask", taskId],
    queryFn: () => pipelineAPI.getTask(taskId).then((res) => res.data),
    enabled: !!taskId,
    retry: 1,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && ["SUCCESS", "FAILURE", "REVOKED"].includes(status) ? false : 3000;
    },
  });

  useEffect(() => {
    if (["SUCCESS", "FAILURE", "REVOKED"].includes(query.data?.status)) {
      queryClient.invalidateQueries({ queryKey: ["pipelineStatus"] });
      queryClient.invalidateQueries({ queryKey: ["modelEvaluation"] });
      queryClient.invalidateQueries({ queryKey: ["riskDistribution"] });
    }
  }, [query.data?.status, queryClient]);

  return query;
}

function usePipelineMutation(mutationFn, label) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => mutationFn().then((res) => res.data),
    onSuccess: () => {
      toast.success(`${label} masuk antrean proses`);
      queryClient.invalidateQueries({ queryKey: ["pipelineStatus"] });
      queryClient.invalidateQueries({ queryKey: ["modelEvaluation"] });
      queryClient.invalidateQueries({ queryKey: ["riskDistribution"] });
    },
    onError: (err) => {
      const message = err.response?.data?.error || err.response?.data?.message || `${label} gagal dijalankan`;
      toast.error(message);
    },
  });
}

export function useProcessNLP() {
  return usePipelineMutation(pipelineAPI.processNLP, "NLP Processing");
}

export function useTrainTopicModel() {
  return usePipelineMutation(pipelineAPI.trainTopicModel, "Train Topic Model");
}

export function useGenerateFeatures() {
  return usePipelineMutation(pipelineAPI.generateFeatures, "Generate Behavioral Features");
}

export function useRunScoring() {
  return usePipelineMutation(pipelineAPI.runScoring, "Generate Risk Scores");
}

export function useRetrainModel() {
  return usePipelineMutation(pipelineAPI.retrainModel, "Retrain Model");
}

export function useModelEvaluation() {
  return useQuery({
    queryKey: ["modelEvaluation"],
    queryFn: () => modelAPI.getEvaluation().then((res) => res.data),
    staleTime: 60 * 1000,
  });
}

export function useFeatureImportance() {
  return useQuery({
    queryKey: ["featureImportance"],
    queryFn: () => modelAPI.getFeatureImportance().then((res) => res.data),
    staleTime: 60 * 1000,
  });
}

export function useThresholdSensitivity() {
  return useQuery({
    queryKey: ["thresholdSensitivity"],
    queryFn: () => modelAPI.getThresholdSensitivity().then((res) => res.data),
    staleTime: 60 * 1000,
  });
}

export function useRiskDistribution() {
  return useQuery({
    queryKey: ["riskDistribution"],
    queryFn: () => modelAPI.getRiskDistribution().then((res) => res.data),
    staleTime: 60 * 1000,
  });
}
