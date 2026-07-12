/**
 * usePipelineTasks — Persists active Celery task IDs to localStorage.
 *
 * Problem solved:
 *   The old implementation stored task IDs in React component state (useState).
 *   When the user navigated away from the ML Pipeline page the component
 *   unmounted and the IDs were lost, making running tasks appear cancelled
 *   even though the Celery worker was still processing them in the background.
 *
 * Solution:
 *   Task IDs are stored in localStorage under the key "pipeline_task_ids".
 *   On mount, the hook rehydrates from localStorage so in-progress tasks
 *   resume polling immediately when the page is revisited.
 *   Completed / failed / revoked tasks are automatically cleared from storage
 *   so stale IDs never block the next run.
 */

import { useCallback, useEffect, useState } from "react";
import { usePipelineTask } from "./usePipeline";

const STORAGE_KEY = "pipeline_task_ids";

// ── Read / write helpers ──────────────────────────────────────────────────────

function loadTaskIds() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveTaskIds(tasks) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks));
  } catch {
    // Quota exceeded or private-browsing restriction — degrade gracefully.
  }
}

// ── Terminal Celery statuses (no more polling needed) ─────────────────────────
const TERMINAL_STATUSES = new Set(["SUCCESS", "FAILURE", "REVOKED"]);

// ── Individual task watcher ───────────────────────────────────────────────────
// Wraps usePipelineTask and automatically removes the ID from localStorage
// once the task has reached a terminal state.

function useTrackedTask(key, taskId, onTerminal) {
  const query = usePipelineTask(taskId);

  useEffect(() => {
    if (taskId && query.data && TERMINAL_STATUSES.has(query.data.status)) {
      onTerminal(key);
    }
  }, [key, taskId, query.data, onTerminal]);

  return query;
}

// ── Public hook ───────────────────────────────────────────────────────────────

/**
 * @returns {{
 *   tasks: Record<string, string>,
 *   setTask: (key: string, id: string) => void,
 *   clearTask: (key: string) => void,
 *   taskQueries: Record<string, object>,
 * }}
 */
export function usePipelineTasks() {
  // Initialise from localStorage so that in-progress tasks survive navigation.
  const [tasks, setTasksState] = useState(() => loadTaskIds());

  // Persist any change to localStorage.
  const setTask = useCallback((key, id) => {
    setTasksState((prev) => {
      const next = { ...prev, [key]: id };
      saveTaskIds(next);
      return next;
    });
  }, []);

  const clearTask = useCallback((key) => {
    setTasksState((prev) => {
      const next = { ...prev };
      delete next[key];
      saveTaskIds(next);
      return next;
    });
  }, []);

  // Called by each useTrackedTask when its task reaches a terminal status.
  const handleTerminal = useCallback(
    (key) => clearTask(key),
    [clearTask]
  );

  // One watcher per pipeline step.
  const nlpQuery          = useTrackedTask("nlp",             tasks.nlp,             handleTerminal);
  const topicModelQuery   = useTrackedTask("topicModel",      tasks.topicModel,      handleTerminal);
  const featuresQuery     = useTrackedTask("features",        tasks.features,        handleTerminal);
  const scoringQuery      = useTrackedTask("scoring",         tasks.scoring,         handleTerminal);
  const recommendationsQuery = useTrackedTask("recommendations", tasks.recommendations, handleTerminal);
  const retrainQuery      = useTrackedTask("retrain",         tasks.retrain,         handleTerminal);

  return {
    tasks,
    setTask,
    clearTask,
    taskQueries: {
      nlp:             nlpQuery,
      topicModel:      topicModelQuery,
      features:        featuresQuery,
      scoring:         scoringQuery,
      recommendations: recommendationsQuery,
      retrain:         retrainQuery,
    },
  };
}
