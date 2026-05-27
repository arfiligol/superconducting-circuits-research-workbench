import type {
  CharacterizationArtifactCompareGroup,
  CharacterizationArtifactMemberRef,
  CharacterizationArtifactPayload,
  CharacterizationArtifactPayloadLayout,
  CharacterizationArtifactPayloadViewKind,
  CharacterizationArtifactPlotSeries,
  CharacterizationArtifactPreset,
  CharacterizationArtifactRef,
  CharacterizationEmbeddedFallbackTable,
  CharacterizationResultDetail,
} from "@/features/characterization/lib/contracts";

function readString(value: unknown) {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function readNullableNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function readStringOrNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  return readString(value);
}

function readSeriesMask(value: unknown) {
  if (!Array.isArray(value)) {
    return [] as readonly boolean[];
  }

  return value.map((item) => item === true);
}

function readNullableNumberArray(value: unknown) {
  if (!Array.isArray(value)) {
    return [] as readonly (number | null)[];
  }

  return value.map((item) => readNullableNumber(item));
}

function readStringOrNumberArray(value: unknown) {
  if (!Array.isArray(value)) {
    return [] as readonly (string | number)[];
  }

  return value.filter(
    (item): item is string | number =>
      typeof item === "string" || (typeof item === "number" && Number.isFinite(item)),
  );
}

function readMember(value: unknown): CharacterizationArtifactMemberRef | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const payload = value as Record<string, unknown>;
  const memberKey = readString(payload.member_key);
  const label = readString(payload.label);
  const traceId = readString(payload.trace_id);
  const sourceKind = readString(payload.source_kind);
  const traceModeGroup = readString(payload.trace_mode_group);
  const parameter = readString(payload.parameter);
  const representation = readString(payload.representation);
  const provenanceSummary = readString(payload.provenance_summary);

  if (
    !memberKey ||
    !label ||
    !traceId ||
    !sourceKind ||
    !traceModeGroup ||
    !parameter ||
    !representation ||
    !provenanceSummary
  ) {
    return null;
  }

  return {
    memberKey,
    label,
    traceId,
    sourceKind,
    traceModeGroup,
    parameter,
    representation,
    provenanceSummary,
  };
}

function readCells(value: unknown) {
  if (!Array.isArray(value)) {
    return [] as readonly (readonly (number | null)[])[];
  }

  return value.map((row) => readNullableNumberArray(row));
}

function readMaskMatrix(value: unknown) {
  if (!Array.isArray(value)) {
    return [] as readonly (readonly boolean[])[];
  }

  return value.map((row) => readSeriesMask(row));
}

function readPlotSeries(value: unknown): CharacterizationArtifactPlotSeries[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const payload = item as Record<string, unknown>;
      const seriesKey = readString(payload.series_key);
      const seriesLabel = readString(payload.series_label);
      if (!seriesKey || !seriesLabel) {
        return null;
      }

      return {
        seriesKey,
        seriesLabel,
        seriesValue:
          typeof payload.series_value === "string" ||
          (typeof payload.series_value === "number" &&
            Number.isFinite(payload.series_value))
            ? payload.series_value
            : null,
        xValues: readStringOrNumberArray(payload.x_values),
        yValues: readNullableNumberArray(payload.y_values),
        mask: readSeriesMask(payload.mask),
        compareKey: readString(payload.compare_key),
        compareLabel: readString(payload.compare_label),
        member: readMember(payload.member),
      } satisfies CharacterizationArtifactPlotSeries;
    })
    .filter((series): series is CharacterizationArtifactPlotSeries => series !== null);
}

export function resolveCharacterizationArtifactSelection(
  artifacts: readonly CharacterizationArtifactRef[],
  selectedArtifactId: string | null,
) {
  if (artifacts.length === 0) {
    return null;
  }

  if (selectedArtifactId) {
    const selectedArtifact = artifacts.find((artifact) => artifact.artifactId === selectedArtifactId);
    if (selectedArtifact) {
      return selectedArtifact;
    }
  }

  return artifacts[0] ?? null;
}

export function resolveCharacterizationArtifactViewMode(
  artifact: CharacterizationArtifactRef | null,
  selectedViewMode: CharacterizationArtifactPayloadViewKind | null,
): CharacterizationArtifactPayloadViewKind | null {
  if (!artifact) {
    return null;
  }

  const supportedViewModes = artifact.querySpec?.supportedViewModes ?? [];
  if (selectedViewMode && supportedViewModes.includes(selectedViewMode)) {
    return selectedViewMode;
  }

  const defaultViewMode = artifact.querySpec?.defaultPresetsByViewMode[0]?.viewMode ?? null;
  if (defaultViewMode && supportedViewModes.includes(defaultViewMode)) {
    return defaultViewMode;
  }

  if (
    artifact.viewKind !== "preset_query" &&
    supportedViewModes.includes(artifact.viewKind)
  ) {
    return artifact.viewKind;
  }

  if (supportedViewModes.length > 0) {
    return supportedViewModes[0] ?? null;
  }

  return artifact.viewKind === "preset_query" ? null : artifact.viewKind;
}

export function resolveCharacterizationArtifactPresetViews(
  artifact: CharacterizationArtifactRef | null,
  viewMode: CharacterizationArtifactPayloadViewKind | null,
) {
  if (!artifact || !viewMode) {
    return [] as readonly CharacterizationArtifactPreset[];
  }

  const supportedPresetIds = artifact.querySpec?.supportedPresetIds.length
    ? new Set(artifact.querySpec.supportedPresetIds)
    : null;

  return artifact.presets.filter((preset) => {
    if (preset.viewKind !== viewMode) {
      return false;
    }

    if (!supportedPresetIds) {
      return true;
    }

    return supportedPresetIds.has(preset.presetId);
  });
}

export function resolveCharacterizationArtifactPresetId(
  artifact: CharacterizationArtifactRef | null,
  viewMode: CharacterizationArtifactPayloadViewKind | null,
  selectedPresetId: string | null,
) {
  const presetViews = resolveCharacterizationArtifactPresetViews(artifact, viewMode);
  if (presetViews.length === 0) {
    return null;
  }

  if (selectedPresetId && presetViews.some((preset) => preset.presetId === selectedPresetId)) {
    return selectedPresetId;
  }

  const queryDefault = artifact?.querySpec?.defaultPresetId ?? artifact?.defaultPresetId ?? null;
  if (queryDefault && presetViews.some((preset) => preset.presetId === queryDefault)) {
    return queryDefault;
  }

  const defaultForViewMode = artifact?.querySpec?.defaultPresetsByViewMode.find(
    (preset) => preset.viewMode === viewMode,
  );
  if (
    defaultForViewMode &&
    presetViews.some((preset) => preset.presetId === defaultForViewMode.presetId)
  ) {
    return defaultForViewMode.presetId;
  }

  return presetViews[0]?.presetId ?? null;
}

export function buildCharacterizationArtifactPayloadRequest(input: Readonly<{
  artifact: CharacterizationArtifactRef | null;
  viewMode: CharacterizationArtifactPayloadViewKind | null;
  presetId: string | null;
}>) {
  if (!input.artifact) {
    return null;
  }

  if (input.artifact.viewKind === "preset_query") {
    if (!input.viewMode) {
      return null;
    }

    return {
      viewMode: input.viewMode,
      presetId:
        input.presetId &&
        resolveCharacterizationArtifactPresetViews(input.artifact, input.viewMode).some(
          (preset) => preset.presetId === input.presetId,
        )
          ? input.presetId
          : null,
    };
  }

  return {
    viewMode:
      input.viewMode && input.viewMode !== input.artifact.viewKind ? input.viewMode : null,
    presetId: null,
  };
}

function resolveLegacyFitTable(
  resultDetail: CharacterizationResultDetail,
): CharacterizationEmbeddedFallbackTable | null {
  const fitTable = resultDetail.payload.fit_table;
  if (!Array.isArray(fitTable) || fitTable.length === 0) {
    return null;
  }

  const rows: Readonly<Record<string, string | number | null>>[] = [];

  for (const item of fitTable) {
    if (!item || typeof item !== "object") {
      continue;
    }

    const payload = item as Record<string, unknown>;
    const parameter = readString(payload.parameter);
    if (!parameter) {
      continue;
    }

    rows.push({
      parameter,
      value: readStringOrNumber(payload.value),
      unit: readString(payload.unit),
    });
  }

  if (rows.length === 0) {
    return null;
  }

  return {
    columns: [
      { key: "parameter", label: "Parameter" },
      { key: "value", label: "Value" },
      { key: "unit", label: "Unit" },
    ],
    rows,
  };
}

function hasRecordEntries(value: unknown) {
  return typeof value === "object" && value !== null && Object.keys(value).length > 0;
}

export function resolveCharacterizationArtifactCompatibilityPayload(input: Readonly<{
  resultDetail: CharacterizationResultDetail | null;
  artifact: CharacterizationArtifactRef | null;
}>) {
  if (!input.resultDetail || !input.artifact) {
    return null;
  }

  const fallbackSummary =
    "Using the persisted result detail because this older result does not expose artifact payload routes.";

  const category = input.artifact.category;
  const artifactId = input.artifact.artifactId.toLowerCase();

  if (category === "fit_table" || artifactId.includes("fit-table")) {
    const embeddedFallbackTable = resolveLegacyFitTable(input.resultDetail);
    if (!embeddedFallbackTable) {
      return null;
    }

    return {
      artifactId: input.artifact.artifactId,
      title: input.artifact.title,
      presetId: "embedded_fit_table",
      viewKind: "table",
      axes: input.artifact.axes,
      metric: input.artifact.metric,
      payload: input.resultDetail.payload,
      diagnostics: [],
      embeddedFallbackTable,
      compatibilityFallback: {
        source: "embedded_result_payload",
        summary: fallbackSummary,
      },
    } satisfies CharacterizationArtifactPayload;
  }

  if (
    (category === "report" || input.artifact.viewKind === "json") &&
    hasRecordEntries(input.resultDetail.payload)
  ) {
    return {
      artifactId: input.artifact.artifactId,
      title: input.artifact.title,
      presetId: "embedded_result_payload",
      viewKind: "json",
      axes: input.artifact.axes,
      metric: input.artifact.metric,
      payload: input.resultDetail.payload,
      diagnostics: [],
      embeddedFallbackTable: null,
      compatibilityFallback: {
        source: "embedded_result_payload",
        summary: fallbackSummary,
      },
    } satisfies CharacterizationArtifactPayload;
  }

  return null;
}

export function resolveCharacterizationArtifactLayout(
  payload: CharacterizationArtifactPayload | null,
): CharacterizationArtifactPayloadLayout | null {
  const layout = payload?.payload.layout;
  if (!layout || typeof layout !== "object") {
    return null;
  }

  const value = layout as Record<string, unknown>;
  return {
    rowsAxis: readString(value.rows_axis),
    columnsAxis: readString(value.columns_axis),
    cellMetric: readString(value.cell_metric),
    xAxis: readString(value.x_axis),
    yMetric: readString(value.y_metric),
    seriesAxis: readString(value.series_axis),
    compareAxis: readString(value.compare_axis),
  };
}

export function resolveCharacterizationArtifactCompareGroups(
  payload: CharacterizationArtifactPayload | null,
): readonly CharacterizationArtifactCompareGroup[] {
  const compareGroups = payload?.payload.compare_groups;
  if (!Array.isArray(compareGroups)) {
    return [];
  }

  const resolvedGroups: CharacterizationArtifactCompareGroup[] = [];

  for (const item of compareGroups) {
    if (!item || typeof item !== "object") {
      continue;
    }

    const group = item as Record<string, unknown>;
    const compareKey = readString(group.compare_key);
    const compareLabel = readString(group.compare_label);
    if (!compareKey || !compareLabel) {
      continue;
    }

    resolvedGroups.push({
      compareKey,
      compareLabel,
      member: readMember(group.member),
      cells: readCells(group.cells),
      mask: readMaskMatrix(group.mask),
      series: readPlotSeries(group.series),
    });
  }

  return resolvedGroups;
}

export function resolveCharacterizationArtifactPlotSeries(
  payload: CharacterizationArtifactPayload | null,
) {
  return readPlotSeries(payload?.payload.series);
}

export function resolveCharacterizationEmbeddedFallbackTable(
  payload: CharacterizationArtifactPayload | null,
) {
  return payload?.embeddedFallbackTable ?? null;
}

export function resolveCharacterizationArtifactTableRows(
  payload: CharacterizationArtifactPayload | null,
) {
  const rows = payload?.payload.rows;
  if (!Array.isArray(rows)) {
    return [] as readonly { axisValue: string | number; label: string; unit: string | null }[];
  }

  return rows
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const row = item as Record<string, unknown>;
      const label = readString(row.label);
      const axisValue = row.axis_value;
      if (
        !label ||
        !(
          typeof axisValue === "string" ||
          (typeof axisValue === "number" && Number.isFinite(axisValue))
        )
      ) {
        return null;
      }

      return {
        axisValue,
        label,
        unit: readString(row.unit),
      };
    })
    .filter(
      (
        row,
      ): row is { axisValue: string | number; label: string; unit: string | null } =>
        row !== null,
    );
}

export function resolveCharacterizationArtifactTableColumns(
  payload: CharacterizationArtifactPayload | null,
) {
  const columns = payload?.payload.columns;
  if (!Array.isArray(columns)) {
    return [] as readonly { axisValue: string | number; label: string; unit: string | null }[];
  }

  return columns
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const column = item as Record<string, unknown>;
      const label = readString(column.label);
      const axisValue = column.axis_value;
      if (
        !label ||
        !(
          typeof axisValue === "string" ||
          (typeof axisValue === "number" && Number.isFinite(axisValue))
        )
      ) {
        return null;
      }

      return {
        axisValue,
        label,
        unit: readString(column.unit),
      };
    })
    .filter(
      (
        column,
      ): column is { axisValue: string | number; label: string; unit: string | null } =>
        column !== null,
    );
}

export function resolveCharacterizationSingleMemberTableProjection(
  payload: CharacterizationArtifactPayload | null,
) {
  return {
    cells: readCells(payload?.payload.cells),
    mask: readMaskMatrix(payload?.payload.mask),
  };
}
