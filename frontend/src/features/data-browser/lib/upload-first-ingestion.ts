import type {
  RawDataIngestionDraft,
  RawDataIngestionKind,
  RawDataTraceDraft,
  TraceFamily,
} from "@/features/data-browser/lib/contracts";

const parameterTokens = ["s11", "s12", "s21", "s22", "yin", "y11", "y12", "y21", "y22", "z11", "z12", "z21", "z22"] as const;

export type UploadValidatedTrace = Readonly<{
  family: TraceFamily;
  parameter: string;
  representation: string;
  pointCount: number;
  headerLabel: string;
  previewPointCount: number;
}>;

export type UploadValidationResult = Readonly<{
  fileName: string;
  designNameSuggestion: string;
  provenanceLabelSuggestion: string;
  axisName: string;
  axisUnit: string;
  pointCount: number;
  traces: readonly UploadValidatedTrace[];
  draftTraces: readonly RawDataTraceDraft[];
}>;

type ParsedCsv = Readonly<{
  headers: readonly string[];
  rows: ReadonlyArray<readonly string[]>;
}>;

type ResolvedTraceMetadata = Readonly<{
  family: TraceFamily;
  parameter: string;
  representation: string;
}>;

function normalizeText(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/\[[^\]]+\]|\([^)]+\)/g, " ")
    .replace(/[^a-z0-9]+/g, " ");
}

function humanizeFileStem(fileName: string) {
  return fileName
    .replace(/\.[^.]+$/, "")
    .split(/[_\-\s]+/)
    .filter((segment) => segment.length > 0)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function parseCsv(text: string): ParsedCsv {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let insideQuotes = false;
  const normalizedText = text.replace(/^\uFEFF/, "");

  for (let index = 0; index < normalizedText.length; index += 1) {
    const character = normalizedText[index];
    const nextCharacter = normalizedText[index + 1];

    if (character === '"') {
      if (insideQuotes && nextCharacter === '"') {
        cell += '"';
        index += 1;
      } else {
        insideQuotes = !insideQuotes;
      }
      continue;
    }

    if (character === "," && !insideQuotes) {
      row.push(cell.trim());
      cell = "";
      continue;
    }

    if ((character === "\n" || character === "\r") && !insideQuotes) {
      if (character === "\r" && nextCharacter === "\n") {
        index += 1;
      }
      row.push(cell.trim());
      cell = "";
      if (row.some((value) => value.length > 0)) {
        rows.push(row);
      }
      row = [];
      continue;
    }

    cell += character;
  }

  row.push(cell.trim());
  if (row.some((value) => value.length > 0)) {
    rows.push(row);
  }

  if (rows.length < 2) {
    throw new Error("CSV must include one header row and at least one data row.");
  }

  const [headers, ...dataRows] = rows;
  if (headers.length < 2) {
    throw new Error("CSV must include one frequency column and at least one trace column.");
  }

  return {
    headers,
    rows: dataRows,
  };
}

function resolveFrequencyColumn(headers: readonly string[]) {
  const index = headers.findIndex((header) => {
    const normalized = normalizeText(header);
    return normalized.includes("freq") || normalized.includes("frequency");
  });

  if (index < 0) {
    throw new Error("CSV must include a frequency column such as frequency_ghz.");
  }

  return {
    index,
    axisName: "frequency",
    axisUnit: "GHz",
  } as const;
}

function resolveTraceMetadata(columnHeader: string, fileName: string): ResolvedTraceMetadata {
  const combined = `${columnHeader} ${fileName}`.toLowerCase();
  const parameterToken = parameterTokens.find((token) => combined.includes(token));
  if (!parameterToken) {
    throw new Error(
      `Could not infer a trace parameter from column "${columnHeader}". Use names like Y11_imaginary or S21_magnitude.`,
    );
  }

  const parameter = parameterToken.toUpperCase();
  const family = parameter.startsWith("S")
    ? "s_matrix"
    : parameter.startsWith("Y")
      ? "y_matrix"
      : "z_matrix";

  let representation = "";
  if (combined.includes("complex")) {
    representation = "complex";
  } else if (
    combined.includes("imaginary") ||
    combined.includes(" imag") ||
    combined.includes("im ") ||
    combined.includes("im_")
  ) {
    representation = "imaginary";
  } else if (
    combined.includes("real") ||
    combined.includes(" re ") ||
    combined.startsWith("re ") ||
    combined.includes("re_")
  ) {
    representation = "real";
  } else if (combined.includes("unwrapped")) {
    representation = "unwrapped_phase";
  } else if (
    combined.includes("phase") ||
    combined.includes(" deg") ||
    combined.includes(" rad") ||
    combined.includes("ang")
  ) {
    representation = "phase";
  } else if (
    combined.includes("magnitude") ||
    combined.includes(" mag") ||
    combined.includes("mag_") ||
    combined.includes("amp")
  ) {
    representation = "magnitude";
  }

  if (!representation) {
    throw new Error(
      `Could not infer a representation from column "${columnHeader}". Include imaginary, real, magnitude, or phase in the series name.`,
    );
  }

  if (representation === "complex") {
    throw new Error(
      `Column "${columnHeader}" resolves to complex data. Upload-first CSV currently supports scalar series columns only.`,
    );
  }

  return {
    family,
    parameter,
    representation,
  };
}

function parseNumericValue(value: string, label: string) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error(`"${value}" in ${label} is not a valid numeric value.`);
  }
  return parsed;
}

function buildTraceDrafts(
  fileName: string,
  parsedCsv: ParsedCsv,
  frequencyColumnIndex: number,
  axisName: string,
  axisUnit: string,
  kind: RawDataIngestionKind,
): readonly RawDataTraceDraft[] {
  const traceColumnIndexes = parsedCsv.headers
    .map((header, index) => ({ header, index }))
    .filter(({ index }) => index !== frequencyColumnIndex);

  if (traceColumnIndexes.length === 0) {
    throw new Error("CSV must include at least one trace data column.");
  }

  return traceColumnIndexes.map(({ header, index }) => {
    const metadata = resolveTraceMetadata(header, fileName);
    const points = parsedCsv.rows.map((row, rowIndex) => {
      const frequency = parseNumericValue(
        row[frequencyColumnIndex] ?? "",
        `row ${rowIndex + 2} frequency column`,
      );
      const value = parseNumericValue(
        row[index] ?? "",
        `row ${rowIndex + 2} column ${header}`,
      );
      return [frequency, value] as const;
    });

    return {
      trace_id: null,
      family: metadata.family,
      parameter: metadata.parameter,
      representation: metadata.representation,
      trace_mode_group: "base",
      stage_kind: "raw",
      provenance_summary: `${
        kind === "measurement" ? "Measurement" : "Layout simulation"
      } import · ${metadata.parameter} ${metadata.representation}`,
      axes: [
        {
          name: axisName,
          unit: axisUnit,
          length: points.length,
        },
      ],
      preview_payload: {
        kind: "sampled_series",
        points,
      },
    } satisfies RawDataTraceDraft;
  });
}

export function validateUploadFirstCsv(input: Readonly<{
  kind: RawDataIngestionKind;
  fileName: string;
  fileText: string;
}>): UploadValidationResult {
  const parsedCsv = parseCsv(input.fileText);
  const frequencyColumn = resolveFrequencyColumn(parsedCsv.headers);
  const draftTraces = buildTraceDrafts(
    input.fileName,
    parsedCsv,
    frequencyColumn.index,
    frequencyColumn.axisName,
    frequencyColumn.axisUnit,
    input.kind,
  );

  return {
    fileName: input.fileName,
    designNameSuggestion: humanizeFileStem(input.fileName),
    provenanceLabelSuggestion: `${
      input.kind === "measurement" ? "Measurement" : "Layout simulation"
    } import · ${humanizeFileStem(input.fileName)}`,
    axisName: frequencyColumn.axisName,
    axisUnit: frequencyColumn.axisUnit,
    pointCount: parsedCsv.rows.length,
    traces: draftTraces.map((trace, index) => ({
      family: trace.family,
      parameter: trace.parameter,
      representation: trace.representation,
      pointCount: trace.axes[0]?.length ?? 0,
      headerLabel: parsedCsv.headers.filter((_, headerIndex) => headerIndex !== frequencyColumn.index)[
        index
      ] ?? trace.parameter,
      previewPointCount:
        Array.isArray(trace.preview_payload.points) ? trace.preview_payload.points.length : 0,
    })),
    draftTraces,
  };
}

export function buildUploadFirstIngestionDraft(input: Readonly<{
  kind: RawDataIngestionKind;
  designName: string;
  provenanceLabel: string;
  validation: UploadValidationResult;
}>): RawDataIngestionDraft {
  return {
    kind: input.kind,
    design_name: input.designName.trim(),
    design_id: null,
    provenance_label: input.provenanceLabel.trim(),
    traces: [...input.validation.draftTraces],
  };
}
