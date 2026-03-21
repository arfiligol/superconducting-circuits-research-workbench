"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useWatch, type UseFormReturn } from "react-hook-form";

import type { OfficialSimulationExamplePreset } from "@/features/simulation/lib/official-example";
import {
  buildSimulationSetupFormValuesFromPersistedSetup,
  cloneSimulationSetupFormValues,
  defaultSimulationSetupFormValues,
  serializeSimulationSetupFormValues,
  type SimulationSetupFormValues,
} from "@/features/simulation/lib/setup-form";
import {
  createSavedSimulationSetupRecord,
  filterSavedSimulationSetupsByDefinition,
  readSavedSimulationSetupRecords,
  removeSavedSimulationSetupRecord,
  replaceSavedSimulationSetupRecord,
  SAVED_SIMULATION_SETUPS_STORAGE_KEY,
  serializeSavedSimulationSetupRecords,
  type SavedSimulationSetupRecord,
} from "@/features/simulation/lib/saved-setups";
import {
  defaultRequestValues,
  simulationStageFieldNames,
  type SimulationRequestValues,
} from "@/features/simulation/lib/request-form";
import type { TaskDetail } from "@/lib/api/tasks";

type StageTone = "default" | "primary" | "success" | "warning" | "error";

export type SimulationSetupSource =
  | Readonly<{ kind: "default" }>
  | Readonly<{ kind: "task"; taskId: number }>
  | Readonly<{ kind: "saved"; recordId: string; name: string }>
  | Readonly<{ kind: "official-example"; presetId: string }>;

type SimulationSetupAuthorityPresentation = Readonly<{
  primaryTag: Readonly<{ label: string; tone: StageTone }>;
  secondaryTag?: Readonly<{ label: string; tone: StageTone }> | null;
  message: string;
  restoreLabel: string | null;
}>;

type UseSavedSimulationSetupsOptions = Readonly<{
  form: UseFormReturn<SimulationRequestValues>;
  workflowContextResetKey: string;
  resolvedDefinitionId: number | null;
  selectedDefinitionName: string | null;
  displayedSimulationTaskDetail: TaskDetail | undefined;
  officialExamplePreset: OfficialSimulationExamplePreset | null;
}>;

function resolveSimulationSetupAuthorityPresentation(
  source: SimulationSetupSource,
  isDirty: boolean,
): SimulationSetupAuthorityPresentation {
  switch (source.kind) {
    case "task":
      return {
        primaryTag: {
          label: isDirty ? `Edited from task #${source.taskId}` : `Task-backed · #${source.taskId}`,
          tone: isDirty ? "warning" : "primary",
        },
        secondaryTag: isDirty ? { label: "Local draft", tone: "default" } : null,
        message: isDirty
          ? "Current Stage 2 edits differ from this task's persisted simulation setup."
          : "Viewing the saved simulation setup from the current run.",
        restoreLabel: isDirty ? "Sync Last Task Setup" : null,
      };
    case "official-example":
      return {
        primaryTag: {
          label: isDirty ? "Edited from Official Example" : "Official Example",
          tone: isDirty ? "warning" : "primary",
        },
        secondaryTag: isDirty ? { label: "Local draft", tone: "default" } : null,
        message: isDirty
          ? "Current Stage 2 edits diverge from the Josephson official example preset."
          : "Loaded from the Josephson official example seed for this definition.",
        restoreLabel: isDirty ? "Reload Official Example" : null,
      };
    case "saved":
      return {
        primaryTag: {
          label: isDirty ? "Edited from saved draft" : `Saved draft · ${source.name}`,
          tone: isDirty ? "warning" : "success",
        },
        secondaryTag: isDirty ? { label: "Browser-local", tone: "default" } : null,
        message: isDirty
          ? "Current Stage 2 edits differ from the browser-saved draft."
          : "Browser-saved convenience draft for this definition.",
        restoreLabel: isDirty ? "Reload saved draft" : null,
      };
    case "default":
    default:
      return {
        primaryTag: {
          label: isDirty ? "Unsaved draft" : "Generic default",
          tone: "default",
        },
        message: isDirty
          ? "Current Stage 2 edits are browser-local until you save them or submit a task."
          : "Using the generic fallback setup for the selected definition.",
        restoreLabel: null,
      };
  }
}

function snapshotSimulationSetup(values: SimulationRequestValues): SimulationSetupFormValues {
  return cloneSimulationSetupFormValues({
    simulationStartGhz: values.simulationStartGhz,
    simulationStopGhz: values.simulationStopGhz,
    simulationPointCount: values.simulationPointCount,
    simulationSpacing: values.simulationSpacing,
    simulationParameterSweepEnabled: values.simulationParameterSweepEnabled,
    simulationParameterSweepAxes: values.simulationParameterSweepAxes,
    simulationSolverFamily: values.simulationSolverFamily,
    simulationMaxIterations: values.simulationMaxIterations,
    simulationConvergenceTolerance: values.simulationConvergenceTolerance,
    simulationHarmonicBalanceEnabled: values.simulationHarmonicBalanceEnabled,
    simulationHarmonicCount: values.simulationHarmonicCount,
    simulationOversampleFactor: values.simulationOversampleFactor,
    simulationSources: values.simulationSources,
    simulationPtcEnabled: values.simulationPtcEnabled,
    simulationPtcMode: values.simulationPtcMode,
    simulationPtcCompensatePorts: values.simulationPtcCompensatePorts,
    simulationPtcManualNotes: values.simulationPtcManualNotes,
    simulationAdvancedDampingStrategy: values.simulationAdvancedDampingStrategy,
    simulationAdvancedLineSearchEnabled: values.simulationAdvancedLineSearchEnabled,
    simulationAdvancedResidualClamp: values.simulationAdvancedResidualClamp,
    simulationAdvancedNewtonRelaxation: values.simulationAdvancedNewtonRelaxation,
    simulationAdvancedNotes: values.simulationAdvancedNotes,
  });
}

function buildDefaultSnapshotKey() {
  return serializeSimulationSetupFormValues(defaultSimulationSetupFormValues);
}

export function useSavedSimulationSetups({
  form,
  workflowContextResetKey,
  resolvedDefinitionId,
  selectedDefinitionName,
  displayedSimulationTaskDetail,
  officialExamplePreset,
}: UseSavedSimulationSetupsOptions) {
  const [savedSimulationSetups, setSavedSimulationSetups] = useState<
    readonly SavedSimulationSetupRecord[]
  >([]);
  const [hasHydratedSavedSetups, setHasHydratedSavedSetups] = useState(false);
  const [selectedSavedSetupId, setSelectedSavedSetupId] = useState<string | null>(null);
  const [isSaveDialogOpen, setIsSaveDialogOpen] = useState(false);
  const [isManageDialogOpen, setIsManageDialogOpen] = useState(false);
  const [saveSetupNameDraft, setSaveSetupNameDraft] = useState("");
  const [savedSetupFeedback, setSavedSetupFeedback] = useState<string | null>(null);
  const [simulationSetupSource, setSimulationSetupSource] = useState<SimulationSetupSource>({
    kind: "default",
  });
  const [hydratedSimulationSetupAuthorityKey, setHydratedSimulationSetupAuthorityKey] =
    useState<string | null>(null);
  const [appliedSimulationSetupSnapshotKey, setAppliedSimulationSetupSnapshotKey] = useState(
    buildDefaultSnapshotKey(),
  );
  const lastWorkflowContextResetKeyRef = useRef<string | null>(null);

  useWatch({
    control: form.control,
    name: simulationStageFieldNames,
  });

  const visibleSavedSetups = useMemo(
    () => filterSavedSimulationSetupsByDefinition(savedSimulationSetups, resolvedDefinitionId),
    [resolvedDefinitionId, savedSimulationSetups],
  );
  const activeSavedSetup =
    visibleSavedSetups.find((setup) => setup.id === selectedSavedSetupId) ?? null;
  const displayedSimulationSetupAuthorityKey = useMemo(() => {
    if (!displayedSimulationTaskDetail?.simulationSetup) {
      return null;
    }

    return `task:${displayedSimulationTaskDetail.taskId}:${JSON.stringify(
      displayedSimulationTaskDetail.simulationSetup,
    )}`;
  }, [displayedSimulationTaskDetail]);
  const currentSimulationSetupSnapshot = snapshotSimulationSetup(form.getValues());
  const currentSimulationSetupSnapshotKey = serializeSimulationSetupFormValues(
    currentSimulationSetupSnapshot,
  );
  const isSimulationSetupDirtyToSource =
    currentSimulationSetupSnapshotKey !== appliedSimulationSetupSnapshotKey;
  const simulationSetupAuthorityPresentation = resolveSimulationSetupAuthorityPresentation(
    simulationSetupSource,
    isSimulationSetupDirtyToSource,
  );

  const applySimulationSetupValues = useCallback(
    (
      nextValues: Readonly<SimulationSetupFormValues>,
      source: SimulationSetupSource,
      input?: Readonly<{
        keepSavedSelection?: boolean;
        feedback?: string | null;
        hydratedAuthorityKey?: string | null;
      }>,
    ) => {
      const normalizedValues = cloneSimulationSetupFormValues(nextValues);
      form.reset(
        {
          ...form.getValues(),
          ...normalizedValues,
        },
        { keepDefaultValues: true },
      );
      const nextHydratedAuthorityKey =
        input?.hydratedAuthorityKey !== undefined
          ? input.hydratedAuthorityKey
          : source.kind === "task"
            ? displayedSimulationSetupAuthorityKey
            : displayedSimulationSetupAuthorityKey ?? null;
      setAppliedSimulationSetupSnapshotKey(serializeSimulationSetupFormValues(normalizedValues));
      setSimulationSetupSource(source);
      setHydratedSimulationSetupAuthorityKey(nextHydratedAuthorityKey);
      if (!input?.keepSavedSelection) {
        setSelectedSavedSetupId(null);
      }
      setSavedSetupFeedback(input?.feedback ?? null);
    },
    [displayedSimulationSetupAuthorityKey, form],
  );

  const buildSavedSetupNameSuggestion = useCallback(() => {
    const baseName = selectedDefinitionName ?? "Simulation Setup";
    const nextIndex = visibleSavedSetups.length + 1;
    return `${baseName} ${nextIndex}`;
  }, [selectedDefinitionName, visibleSavedSetups.length]);

  const restoreSimulationSetupFromCurrentSource = useCallback(() => {
    if (simulationSetupSource.kind === "task" && displayedSimulationTaskDetail?.simulationSetup) {
      applySimulationSetupValues(
        buildSimulationSetupFormValuesFromPersistedSetup(
          currentSimulationSetupSnapshot,
          displayedSimulationTaskDetail.simulationSetup,
        ),
        simulationSetupSource,
        {
          hydratedAuthorityKey: displayedSimulationSetupAuthorityKey,
          feedback: `Reloaded task-backed setup from task #${simulationSetupSource.taskId}.`,
        },
      );
      return;
    }

    if (simulationSetupSource.kind === "saved" && activeSavedSetup) {
      applySimulationSetupValues(activeSavedSetup.values, simulationSetupSource, {
        keepSavedSelection: true,
        feedback: `Reloaded saved draft “${activeSavedSetup.name}”.`,
      });
      return;
    }

    if (
      simulationSetupSource.kind === "official-example" &&
      officialExamplePreset &&
      officialExamplePreset.id === simulationSetupSource.presetId
    ) {
      applySimulationSetupValues(officialExamplePreset.values, simulationSetupSource, {
        feedback: "Reloaded the Official Example preset.",
      });
    }
  }, [
    activeSavedSetup,
    applySimulationSetupValues,
    currentSimulationSetupSnapshot,
    displayedSimulationSetupAuthorityKey,
    displayedSimulationTaskDetail,
    officialExamplePreset,
    simulationSetupSource,
  ]);

  const applySavedSetup = useCallback(
    (record: SavedSimulationSetupRecord) => {
      applySimulationSetupValues(
        record.values,
        {
          kind: "saved",
          recordId: record.id,
          name: record.name,
        },
        {
          keepSavedSelection: true,
          feedback: `Loaded saved setup “${record.name}”.`,
        },
      );
      setSelectedSavedSetupId(record.id);
      setIsSaveDialogOpen(false);
      setIsManageDialogOpen(false);
    },
    [applySimulationSetupValues],
  );

  const applyOfficialExample = useCallback(() => {
    if (!officialExamplePreset) {
      return;
    }

    applySimulationSetupValues(
      officialExamplePreset.values,
      {
        kind: "official-example",
        presetId: officialExamplePreset.id,
      },
      {
        feedback: `Loaded the Official Example preset for ${officialExamplePreset.exampleName}.`,
      },
    );
    setIsSaveDialogOpen(false);
    setIsManageDialogOpen(false);
  }, [applySimulationSetupValues, officialExamplePreset]);

  const persistSavedSetup = useCallback(
    (name: string, existingRecordId?: string | null) => {
      if (resolvedDefinitionId === null) {
        setSavedSetupFeedback("Select a definition before saving a setup.");
        return;
      }

      const trimmedName = name.trim();
      if (!trimmedName) {
        setSavedSetupFeedback("Saved setup name is required.");
        return;
      }

      const existingRecord = existingRecordId
        ? visibleSavedSetups.find((record) => record.id === existingRecordId) ?? null
        : null;
      const nowIso = new Date().toISOString();
      const nextRecord = createSavedSimulationSetupRecord({
        id:
          existingRecord?.id ??
          (typeof crypto !== "undefined" ? crypto.randomUUID() : `setup-${Date.now()}`),
        definitionId: resolvedDefinitionId,
        definitionName: selectedDefinitionName,
        name: trimmedName,
        createdAt: existingRecord?.createdAt ?? nowIso,
        updatedAt: nowIso,
        values: currentSimulationSetupSnapshot,
      });

      setSavedSimulationSetups((current) => replaceSavedSimulationSetupRecord(current, nextRecord));
      setSelectedSavedSetupId(nextRecord.id);
      setSavedSetupFeedback(
        existingRecord
          ? `Updated saved setup “${nextRecord.name}”.`
          : `Saved “${nextRecord.name}” in this browser.`,
      );
      if (simulationSetupSource.kind === "saved" && simulationSetupSource.recordId === nextRecord.id) {
        setSimulationSetupSource({
          kind: "saved",
          recordId: nextRecord.id,
          name: nextRecord.name,
        });
      }
      setSaveSetupNameDraft(nextRecord.name);
      setIsSaveDialogOpen(false);
    },
    [
      currentSimulationSetupSnapshot,
      resolvedDefinitionId,
      selectedDefinitionName,
      simulationSetupSource,
      visibleSavedSetups,
    ],
  );

  const deleteSavedSetup = useCallback(
    (recordId: string) => {
      const record = savedSimulationSetups.find((entry) => entry.id === recordId);
      setSavedSimulationSetups((current) => removeSavedSimulationSetupRecord(current, recordId));
      if (selectedSavedSetupId === recordId) {
        setSelectedSavedSetupId(null);
      }
      setSavedSetupFeedback(
        record ? `Deleted saved setup “${record.name}”.` : "Deleted saved setup.",
      );
    },
    [savedSimulationSetups, selectedSavedSetupId],
  );

  const openSaveDialog = useCallback(() => {
    if (activeSavedSetup) {
      persistSavedSetup(activeSavedSetup.name, activeSavedSetup.id);
      return;
    }

    setSaveSetupNameDraft(buildSavedSetupNameSuggestion());
    setIsSaveDialogOpen(true);
  }, [activeSavedSetup, buildSavedSetupNameSuggestion, persistSavedSetup]);

  const openManageDialog = useCallback(() => {
    setIsManageDialogOpen(true);
  }, []);

  const openSaveAsNewFromManage = useCallback(() => {
    setIsManageDialogOpen(false);
    setSaveSetupNameDraft(buildSavedSetupNameSuggestion());
    setIsSaveDialogOpen(true);
  }, [buildSavedSetupNameSuggestion]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    setSavedSimulationSetups(
      readSavedSimulationSetupRecords(
        window.localStorage.getItem(SAVED_SIMULATION_SETUPS_STORAGE_KEY),
      ),
    );
    setHasHydratedSavedSetups(true);
  }, []);

  useEffect(() => {
    if (!hasHydratedSavedSetups || typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(
      SAVED_SIMULATION_SETUPS_STORAGE_KEY,
      serializeSavedSimulationSetupRecords(savedSimulationSetups),
    );
  }, [hasHydratedSavedSetups, savedSimulationSetups]);

  useEffect(() => {
    if (
      !displayedSimulationTaskDetail?.simulationSetup ||
      displayedSimulationSetupAuthorityKey === null ||
      displayedSimulationSetupAuthorityKey === hydratedSimulationSetupAuthorityKey
    ) {
      return;
    }

    applySimulationSetupValues(
      buildSimulationSetupFormValuesFromPersistedSetup(
        currentSimulationSetupSnapshot,
        displayedSimulationTaskDetail.simulationSetup,
      ),
      {
        kind: "task",
        taskId: displayedSimulationTaskDetail.taskId,
      },
      {
        hydratedAuthorityKey: displayedSimulationSetupAuthorityKey,
      },
    );
  }, [
    applySimulationSetupValues,
    currentSimulationSetupSnapshot,
    displayedSimulationSetupAuthorityKey,
    displayedSimulationTaskDetail,
    hydratedSimulationSetupAuthorityKey,
  ]);

  useEffect(() => {
    if (!selectedSavedSetupId) {
      return;
    }

    if (!visibleSavedSetups.some((setup) => setup.id === selectedSavedSetupId)) {
      setSelectedSavedSetupId(null);
    }
  }, [selectedSavedSetupId, visibleSavedSetups]);

  useEffect(() => {
    const fallbackToAuthoritativeSource = () => {
      if (displayedSimulationTaskDetail?.simulationSetup) {
        applySimulationSetupValues(
          buildSimulationSetupFormValuesFromPersistedSetup(
            currentSimulationSetupSnapshot,
            displayedSimulationTaskDetail.simulationSetup,
          ),
          {
            kind: "task",
            taskId: displayedSimulationTaskDetail.taskId,
          },
          {
            hydratedAuthorityKey: displayedSimulationSetupAuthorityKey,
          },
        );
        return;
      }

      applySimulationSetupValues(defaultSimulationSetupFormValues, { kind: "default" }, {
        hydratedAuthorityKey: null,
      });
    };

    if (simulationSetupSource.kind === "saved") {
      if (!visibleSavedSetups.some((setup) => setup.id === simulationSetupSource.recordId)) {
        fallbackToAuthoritativeSource();
      }
      return;
    }

    if (
      simulationSetupSource.kind === "official-example" &&
      (!officialExamplePreset || officialExamplePreset.id !== simulationSetupSource.presetId)
    ) {
      fallbackToAuthoritativeSource();
    }
  }, [
    applySimulationSetupValues,
    currentSimulationSetupSnapshot,
    displayedSimulationSetupAuthorityKey,
    displayedSimulationTaskDetail,
    officialExamplePreset,
    simulationSetupSource,
    visibleSavedSetups,
  ]);

  useEffect(() => {
    const previousContextKey = lastWorkflowContextResetKeyRef.current;
    lastWorkflowContextResetKeyRef.current = workflowContextResetKey;
    if (previousContextKey === null || previousContextKey === workflowContextResetKey) {
      return;
    }

    setSelectedSavedSetupId(null);
    setIsSaveDialogOpen(false);
    setIsManageDialogOpen(false);
    setSaveSetupNameDraft("");
    setSavedSetupFeedback(null);
    setSimulationSetupSource({ kind: "default" });
    setHydratedSimulationSetupAuthorityKey(null);
    setAppliedSimulationSetupSnapshotKey(buildDefaultSnapshotKey());
  }, [workflowContextResetKey]);

  const resetForWorkflowContext = useCallback(() => {
    form.reset(defaultRequestValues, { keepDefaultValues: true });
    setSelectedSavedSetupId(null);
    setIsSaveDialogOpen(false);
    setIsManageDialogOpen(false);
    setSaveSetupNameDraft("");
    setSavedSetupFeedback(null);
    setSimulationSetupSource({ kind: "default" });
    setHydratedSimulationSetupAuthorityKey(null);
    setAppliedSimulationSetupSnapshotKey(buildDefaultSnapshotKey());
  }, [form]);

  return {
    activeSavedSetup,
    visibleSavedSetups,
    isSaveDialogOpen,
    isManageDialogOpen,
    saveSetupNameDraft,
    savedSetupFeedback,
    simulationSetupSource,
    simulationSetupAuthorityPresentation,
    currentSimulationSetupSnapshot,
    applySimulationSetupValues,
    restoreSimulationSetupFromCurrentSource,
    applySavedSetup,
    applyOfficialExamplePreset: applyOfficialExample,
    persistSavedSetup,
    deleteSavedSetup,
    openSaveDialog,
    openManageDialog,
    openSaveAsNewFromManage,
    setSaveSetupNameDraft,
    setIsSaveDialogOpen,
    setIsManageDialogOpen,
    resetForWorkflowContext,
  };
}
