"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, FileCode2, LoaderCircle } from "lucide-react";

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
  const [isNetlistOpen, setIsNetlistOpen] = useState(false);

  return (
    <WorkflowStageSection
      step={1}
      title="Current Definition"
      description="Select the definition for this run."
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

      <div className="space-y-3">
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

        <div className="rounded-[0.95rem] border border-border bg-surface px-4 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <FileCode2 className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm font-medium text-foreground">Expanded Netlist</p>
            </div>
            <button
              type="button"
              onClick={() => {
                setIsNetlistOpen((current) => !current);
              }}
              className="inline-flex cursor-pointer items-center gap-2 rounded-full border border-border bg-background px-3 py-2 text-xs font-medium text-foreground transition hover:border-primary/35 hover:bg-primary/10"
            >
              {isNetlistOpen ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
              {isNetlistOpen ? "Hide Netlist" : "Show Netlist"}
            </button>
          </div>
          {isNetlistOpen ? (
            <div className="mt-3">
              <ReadOnlyCodeSurface
                label="Expanded Netlist"
                value={formattedExpandedNetlist}
                height="240px"
              />
            </div>
          ) : null}
        </div>
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
