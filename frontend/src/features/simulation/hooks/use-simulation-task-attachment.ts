"use client";

import { useCallback, useEffect, useMemo, useRef, useTransition } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { parseSimulationDefinitionIdParam } from "@/features/simulation/lib/definition-id";
import type { SimulationPageContext } from "@/features/simulation/lib/workflow";
import type { TaskSummary, TaskDetail } from "@/lib/api/tasks";
import {
  resolveTaskConnectionState,
  resolveTaskRecoveryNotice,
} from "@/lib/task-surface";

function buildSimulationSearchHref(
  pathname: string,
  searchParamsValue: string,
  updates: Readonly<Record<string, string | null>>,
) {
  const params = new URLSearchParams(searchParamsValue);

  for (const [key, value] of Object.entries(updates)) {
    if (value === null) {
      params.delete(key);
    } else {
      params.set(key, value);
    }
  }

  const nextSearch = params.toString();
  return nextSearch ? `${pathname}?${nextSearch}` : pathname;
}

function parseTaskIdParam(value: string | null): number | null {
  if (!value) {
    return null;
  }

  const parsedValue = Number.parseInt(value, 10);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

function buildAttachedTaskStorageKey(
  definitionId: number | null,
  datasetId: string | null,
): string | null {
  if (typeof definitionId !== "number" || !datasetId) {
    return null;
  }

  return `simulation:attached-task:${definitionId}:${datasetId}`;
}

function readStoredAttachedTaskId(storageKey: string | null): number | null {
  if (typeof window === "undefined" || !storageKey) {
    return null;
  }

  return parseTaskIdParam(window.sessionStorage.getItem(storageKey));
}

type UseSimulationTaskAttachmentOptions = Readonly<{
  resolvedDefinitionId: number | null;
  resolvedTaskId: number | null;
  latestSimulationTask: TaskSummary | undefined;
  activeTask: TaskDetail | undefined;
  activeTaskError: Error | undefined;
  pageContext: SimulationPageContext;
}>;

export function useSimulationTaskAttachment({
  resolvedDefinitionId,
  resolvedTaskId,
  latestSimulationTask,
  activeTask,
  activeTaskError,
  pageContext,
}: UseSimulationTaskAttachmentOptions) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [, startTransition] = useTransition();
  const searchParamsString = searchParams.toString();
  const requestedDefinitionId = searchParams.get("definitionId");
  const requestedTaskId = parseTaskIdParam(searchParams.get("taskId"));
  const rawDefinitionId = parseSimulationDefinitionIdParam(requestedDefinitionId);
  const attachedTaskStorageKey = useMemo(
    () => buildAttachedTaskStorageKey(pageContext.definitionId, pageContext.datasetId),
    [pageContext.datasetId, pageContext.definitionId],
  );
  const autoRestoredTaskIdRef = useRef<number | null>(null);

  const replaceSearchState = useCallback(
    (updates: Readonly<Record<string, string | null>>) => {
      startTransition(() => {
        router.replace(buildSimulationSearchHref(pathname, searchParamsString, updates), {
          scroll: false,
        });
      });
    },
    [pathname, router, searchParamsString, startTransition],
  );

  const rememberAttachedTask = useCallback(
    (taskId: number) => {
      if (typeof window === "undefined" || attachedTaskStorageKey === null) {
        return;
      }

      window.sessionStorage.setItem(attachedTaskStorageKey, String(taskId));
    },
    [attachedTaskStorageKey],
  );

  const attachTask = useCallback(
    (taskId: number) => {
      rememberAttachedTask(taskId);
      replaceSearchState({
        definitionId: resolvedDefinitionId !== null ? String(resolvedDefinitionId) : null,
        taskId: String(taskId),
      });
    },
    [rememberAttachedTask, replaceSearchState, resolvedDefinitionId],
  );

  const clearRequestedTask = useCallback(() => {
    autoRestoredTaskIdRef.current = null;
    replaceSearchState({
      definitionId: resolvedDefinitionId !== null ? String(resolvedDefinitionId) : null,
      taskId: null,
    });
  }, [replaceSearchState, resolvedDefinitionId]);

  useEffect(() => {
    if (resolvedDefinitionId === null || resolvedDefinitionId === rawDefinitionId) {
      return;
    }

    replaceSearchState({
      definitionId: String(resolvedDefinitionId),
    });
  }, [rawDefinitionId, replaceSearchState, resolvedDefinitionId]);

  useEffect(() => {
    if (requestedTaskId !== null || attachedTaskStorageKey === null) {
      return;
    }

    const storedTaskId = readStoredAttachedTaskId(attachedTaskStorageKey);
    if (storedTaskId === null) {
      return;
    }

    autoRestoredTaskIdRef.current = storedTaskId;
    replaceSearchState({
      definitionId: resolvedDefinitionId !== null ? String(resolvedDefinitionId) : null,
      taskId: String(storedTaskId),
    });
  }, [attachedTaskStorageKey, replaceSearchState, requestedTaskId, resolvedDefinitionId]);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      attachedTaskStorageKey === null ||
      !activeTask ||
      requestedTaskId !== activeTask.taskId
    ) {
      return;
    }

    window.sessionStorage.setItem(attachedTaskStorageKey, String(activeTask.taskId));
    if (autoRestoredTaskIdRef.current === activeTask.taskId) {
      autoRestoredTaskIdRef.current = null;
    }
  }, [activeTask, attachedTaskStorageKey, requestedTaskId]);

  useEffect(() => {
    if (
      typeof window === "undefined" ||
      attachedTaskStorageKey === null ||
      !activeTaskError ||
      requestedTaskId === null ||
      autoRestoredTaskIdRef.current !== requestedTaskId
    ) {
      return;
    }

    window.sessionStorage.removeItem(attachedTaskStorageKey);
    clearRequestedTask();
  }, [
    activeTaskError,
    attachedTaskStorageKey,
    clearRequestedTask,
    requestedTaskId,
  ]);

  useEffect(() => {
    if (
      requestedTaskId === null ||
      !activeTask ||
      pageContext.definitionId === null ||
      pageContext.datasetId === null ||
      (activeTask.definitionId === pageContext.definitionId &&
        activeTask.datasetId === pageContext.datasetId)
    ) {
      return;
    }

    clearRequestedTask();
  }, [activeTask, clearRequestedTask, pageContext.datasetId, pageContext.definitionId, requestedTaskId]);

  const taskConnectionState = resolveTaskConnectionState({
    requestedTaskId,
    resolvedTaskId,
    latestTaskId: latestSimulationTask?.taskId ?? null,
    activeTask,
  });
  const taskRecovery = resolveTaskRecoveryNotice(
    requestedTaskId,
    latestSimulationTask?.taskId ?? null,
    activeTaskError,
  );
  const resetAutoRestoreState = useCallback(() => {
    autoRestoredTaskIdRef.current = null;
  }, []);

  return {
    requestedDefinitionId,
    requestedTaskId,
    rawDefinitionId,
    attachedTaskStorageKey,
    taskConnectionState,
    taskRecovery,
    replaceSearchState,
    rememberAttachedTask,
    attachTask,
    clearRequestedTask,
    resetAutoRestoreState,
    wasAutoRestoredTask(taskId: number | null) {
      return autoRestoredTaskIdRef.current === taskId;
    },
  };
}
