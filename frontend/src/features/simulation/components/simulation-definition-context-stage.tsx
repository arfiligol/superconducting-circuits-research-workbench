"use client";

import { LoaderCircle } from "lucide-react";

import type {
  CircuitDefinitionDetail,
  CircuitDefinitionSummary,
} from "@/features/circuit-definition-editor/lib/contracts";
import {
  AppSelectField,
  type AppSelectOption,
} from "@/features/shared/components/app-select";
import {
  ReadOnlyCodeSurface,
  StageNotice,
  WorkflowStageSection,
} from "@/features/simulation/components/simulation-workbench-stage-kit";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";

function formatCodeValue(value: string | null | undefined, fallback: string) {
  const trimmed = value?.trim();
  if (!trimmed) {
    return fallback;
  }

  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2);
  } catch {
    return trimmed;
  }
}

function formatExpandedNetlist(activeDefinition: CircuitDefinitionDetail | undefined) {
  const fallback = "// Expanded netlist is loading for the selected definition.";
  const normalizedOutput = activeDefinition?.normalized_output?.trim();
  if (!normalizedOutput) {
    return fallback;
  }

  try {
    const parsed = JSON.parse(normalizedOutput) as Record<string, unknown>;
    const expanded = parsed?.expanded;

    if (typeof expanded === "string") {
      return expanded.trim() || fallback;
    }

    if (expanded && typeof expanded === "object") {
      return JSON.stringify(expanded, null, 2);
    }

    return formatCodeValue(normalizedOutput, fallback);
  } catch {
    return normalizedOutput;
  }
}

type DefinitionRecoveryNotice = Readonly<{
  tone: "default" | "warning";
  title: string;
  message: string;
}> | null;

export function SimulationDefinitionContextStage({
  activeDefinition,
  activeDefinitionErrorMessage,
  definitionOptions,
  definitionRecovery,
  isDefinitionTransitioning,
  isDefinitionsLoading,
  resolvedDefinitionId,
  selectedDefinitionDisplay,
  onDefinitionChange,
}: Readonly<{
  activeDefinition: CircuitDefinitionDetail | undefined;
  activeDefinitionErrorMessage: string | null;
  definitionOptions: readonly AppSelectOption[];
  definitionRecovery: DefinitionRecoveryNotice;
  isDefinitionTransitioning: boolean;
  isDefinitionsLoading: boolean;
  resolvedDefinitionId: CircuitDefinitionId | null;
  selectedDefinitionDisplay: CircuitDefinitionSummary | { name: string } | null;
  onDefinitionChange: (value: string) => void;
}>) {
  const formattedExpandedNetlist = formatExpandedNetlist(activeDefinition);

  return (
    <WorkflowStageSection
      step={1}
      title="Definition / Netlist Context"
      description="Select the definition and inspect the expanded netlist before launching a run."
      status={{
        label: activeDefinition ? "Ready" : isDefinitionsLoading ? "Loading" : "Blocked",
        tone: activeDefinition ? "success" : isDefinitionsLoading ? "primary" : "warning",
        message: activeDefinition
          ? "Definition context is ready."
          : "Select a visible definition first.",
      }}
    >
      {definitionRecovery ? (
        <StageNotice
          tone={definitionRecovery.tone}
          title={definitionRecovery.title}
          message={definitionRecovery.message}
        />
      ) : null}

      {activeDefinitionErrorMessage ? (
        <StageNotice
          tone="error"
          title="Definition detail unavailable"
          message={`Unable to load definition detail. ${activeDefinitionErrorMessage}`}
        />
      ) : null}

      <div className="space-y-4">
        <AppSelectField
          label="Selected Definition"
          value={resolvedDefinitionId !== null ? String(resolvedDefinitionId) : ""}
          onChange={onDefinitionChange}
          options={definitionOptions}
          placeholder={
            selectedDefinitionDisplay
              ? selectedDefinitionDisplay.name
              : isDefinitionsLoading
                ? "Loading definitions"
                : definitionOptions.length
                  ? "Select a definition"
                  : "No definitions available"
          }
          disabled={definitionOptions.length === 0}
        />

        <ReadOnlyCodeSurface
          label="Expanded Netlist"
          value={formattedExpandedNetlist}
          height="320px"
        />
      </div>

      {isDefinitionTransitioning ? (
        <div className="flex items-center gap-3 rounded-[0.95rem] border border-border bg-surface px-4 py-4 text-sm text-muted-foreground">
          <LoaderCircle className="h-4 w-4 animate-spin" />
          Refreshing definition context...
        </div>
      ) : null}
    </WorkflowStageSection>
  );
}
