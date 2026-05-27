import {
  cloneSimulationSetupFormValues,
  type SimulationSetupFormValues,
} from "@/features/simulation/lib/setup-form";
import type { CircuitDefinitionId } from "@/features/circuit-definition-editor/lib/schema-identity";

export const SAVED_SIMULATION_SETUPS_STORAGE_KEY = "sc-simulation-saved-setups-v1";

export type SavedSimulationSetupRecord = Readonly<{
  id: string;
  definitionId: CircuitDefinitionId;
  definitionName: string | null;
  name: string;
  createdAt: string;
  updatedAt: string;
  values: SimulationSetupFormValues;
}>;

type SavedSimulationSetupPayload = Readonly<{
  id: string;
  definitionId: CircuitDefinitionId;
  definitionName: string | null;
  name: string;
  createdAt: string;
  updatedAt: string;
  values: SimulationSetupFormValues;
}>;

function isSavedSimulationSetupPayload(value: unknown): value is SavedSimulationSetupPayload {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<SavedSimulationSetupPayload>;
  return (
    typeof candidate.id === "string" &&
    typeof candidate.definitionId === "string" &&
    (candidate.definitionName === null || typeof candidate.definitionName === "string") &&
    typeof candidate.name === "string" &&
    typeof candidate.createdAt === "string" &&
    typeof candidate.updatedAt === "string" &&
    !!candidate.values &&
    typeof candidate.values === "object"
  );
}

export function createSavedSimulationSetupRecord(input: Readonly<{
  id: string;
  definitionId: CircuitDefinitionId;
  definitionName: string | null;
  name: string;
  createdAt: string;
  updatedAt: string;
  values: Readonly<SimulationSetupFormValues>;
}>): SavedSimulationSetupRecord {
  return {
    id: input.id,
    definitionId: input.definitionId,
    definitionName: input.definitionName,
    name: input.name.trim(),
    createdAt: input.createdAt,
    updatedAt: input.updatedAt,
    values: cloneSimulationSetupFormValues(input.values),
  };
}

export function replaceSavedSimulationSetupRecord(
  records: readonly SavedSimulationSetupRecord[],
  nextRecord: SavedSimulationSetupRecord,
) {
  const remaining = records.filter((record) => record.id !== nextRecord.id);
  return sortSavedSimulationSetupRecords([...remaining, nextRecord]);
}

export function removeSavedSimulationSetupRecord(
  records: readonly SavedSimulationSetupRecord[],
  recordId: string,
) {
  return records.filter((record) => record.id !== recordId);
}

export function sortSavedSimulationSetupRecords(records: readonly SavedSimulationSetupRecord[]) {
  return [...records].sort((left, right) => {
    const timeDelta =
      new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
    if (timeDelta !== 0) {
      return timeDelta;
    }
    return left.name.localeCompare(right.name);
  });
}

export function filterSavedSimulationSetupsByDefinition(
  records: readonly SavedSimulationSetupRecord[],
  definitionId: CircuitDefinitionId | null,
) {
  if (definitionId === null) {
    return [];
  }

  return sortSavedSimulationSetupRecords(
    records.filter((record) => record.definitionId === definitionId),
  );
}

export function readSavedSimulationSetupRecords(raw: string | null) {
  if (!raw) {
    return [] as readonly SavedSimulationSetupRecord[];
  }

  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [] as const;
    }

    const records = parsed
      .filter(isSavedSimulationSetupPayload)
      .map((record) =>
        createSavedSimulationSetupRecord({
          ...record,
          values: record.values,
        }),
      );

    return sortSavedSimulationSetupRecords(records);
  } catch {
    return [] as const;
  }
}

export function serializeSavedSimulationSetupRecords(
  records: readonly SavedSimulationSetupRecord[],
) {
  return JSON.stringify(records);
}
