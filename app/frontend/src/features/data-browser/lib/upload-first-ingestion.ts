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

function fileStem(fileName: string) {
  return fileName.replace(/\.[^.]+$/, "");
}

function humanizeStem(value: string) {
  return value
    .split(/[_\-\s]+/)
    .filter((segment) => segment.length > 0)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function humanizeFileStem(fileName: string) {
  return humanizeStem(fileStem(fileName));
}

function resolveDesignNameSuggestion(fileName: string) {
  const stem = fileStem(fileName);
  const hfssMatch = stem.match(/^([A-Za-z0-9]+)_Q(\d+)(?:[_\-\s]|$)/i);
  if (hfssMatch) {
    return `${hfssMatch[1]?.toUpperCase()} Q${hfssMatch[2]}`;
  }

  return humanizeStem(stem);
}

function formatTraceProvenance(input: Readonly<{
  kind: RawDataIngestionKind;
  fileName: string;
  header: string;
  parameter: string;
  representation: string;
}>) {
  const source = input.kind === "measurement" ? "Measurement" : "Layout simulation";
  return `${source} import · ${input.fileName} · ${input.header} · ${input.parameter} ${input.representation}`;
}

function parseAxisHeader(header: string) {
  const normalizedHeader = header.trim().replace(/^"|"$/g, "");
  const match = normalizedHeader.match(/^(.+?)\s*\[([^\]]*)\]\s*$/);
  if (!match) {
    return null;
  }

  const name = match[1]?.trim();
  if (!name) {
    return null;
  }

  return {
    name,
    unit: match[2]?.trim() ?? "",
  };
}

function formatParameterToken(token: (typeof parameterTokens)[number]) {
  return token === "yin" ? "Yin" : token.toUpperCase();
}

function resolveParameterFromText(value: string) {
  const normalized = value.toLowerCase();
  const token = parameterTokens.find((candidate) => normalized.includes(candidate));
  return token ? formatParameterToken(token) : null;
}

function isHfssFormulaHeader(header: string) {
  return /(?:im|re|ang_rad)\s*\(\s*[ys]t\s*\(/i.test(header);
}

function inferFormulaMetadata(columnHeader: string) {
  const match = columnHeader.match(/(im|re|ang_rad)\s*\(\s*([ys])t\s*\(/i);
  if (!match) {
    return null;
  }

  const operator = match[1]?.toLowerCase();
  const matrix = match[2]?.toLowerCase();
  const family: TraceFamily = matrix === "s" ? "s_matrix" : "y_matrix";
  const representation =
    operator === "im" ? "imaginary" : operator === "re" ? "real" : "phase";

  return { family, representation };
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

  const parsedAxis = parseAxisHeader(headers[index] ?? "");

  return {
    index,
    axisName: "frequency",
    axisUnit: parsedAxis?.unit || "GHz",
  } as const;
}

function resolveHfssSweepColumn(headers: readonly string[], frequencyColumnIndex: number) {
  if (headers.length !== 3) {
    return null;
  }

  const nonFrequencyColumns = headers
    .map((header, index) => ({ header, index }))
    .filter(({ index }) => index !== frequencyColumnIndex);
  const dataColumns = nonFrequencyColumns.filter(({ header }) => isHfssFormulaHeader(header));
  const sweepColumns = nonFrequencyColumns.filter(({ header }) => {
    const parsedAxis = parseAxisHeader(header);
    return Boolean(parsedAxis?.unit) && !isHfssFormulaHeader(header);
  });

  if (dataColumns.length !== 1 || sweepColumns.length !== 1) {
    return null;
  }

  const parsedAxis = parseAxisHeader(sweepColumns[0]?.header ?? "");
  if (!parsedAxis?.unit) {
    return null;
  }

  return {
    index: sweepColumns[0]?.index ?? -1,
    name: parsedAxis.name,
    unit: parsedAxis.unit,
  };
}

function resolveTraceMetadata(columnHeader: string, fileName: string): ResolvedTraceMetadata {
  const combined = `${columnHeader} ${fileName}`.toLowerCase();
  const formulaMetadata = inferFormulaMetadata(columnHeader);
  const parameter = resolveParameterFromText(`${columnHeader} ${fileName}`);
  if (!parameter) {
    throw new Error(
      `Could not infer a trace parameter from column "${columnHeader}". Use names like Y11_imaginary or S21_magnitude.`,
    );
  }

  let family: TraceFamily = parameter.startsWith("S")
    ? "s_matrix"
    : parameter.startsWith("Y")
      ? "y_matrix"
      : "z_matrix";
  let representation = formulaMetadata?.representation ?? "";

  if (parameter === "Yin") {
    family = "y_matrix";
  } else if (formulaMetadata) {
    family = formulaMetadata.family;
  }

  if (combined.includes("complex")) {
    representation = "complex";
  } else if (
    !representation &&
    (combined.includes("imaginary") ||
      combined.includes(" imag") ||
      combined.includes("im ") ||
      combined.includes("im_") ||
      columnHeader.trim().toLowerCase().startsWith("im("))
  ) {
    representation = "imaginary";
  } else if (
    !representation &&
    (combined.includes("real") ||
      combined.includes(" re ") ||
      combined.startsWith("re ") ||
      combined.includes("re_") ||
      columnHeader.trim().toLowerCase().startsWith("re("))
  ) {
    representation = "real";
  } else if (!representation && combined.includes("unwrapped")) {
    representation = "unwrapped_phase";
  } else if (
    !representation &&
    (combined.includes("phase") ||
      combined.includes(" deg") ||
      combined.includes(" rad") ||
      combined.includes("ang"))
  ) {
    representation = "phase";
  } else if (
    !representation &&
    (combined.includes("magnitude") ||
      combined.includes(" mag") ||
      combined.includes("mag_") ||
      combined.includes("amp"))
  ) {
    representation = "magnitude";
  }

  if (!representation && parseAxisHeader(columnHeader)?.unit) {
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
  sweepColumn: Readonly<{ index: number; name: string; unit: string }> | null,
): readonly RawDataTraceDraft[] {
  const traceColumnIndexes = parsedCsv.headers
    .map((header, index) => ({ header, index }))
    .filter(({ index }) => index !== frequencyColumnIndex && index !== sweepColumn?.index);

  if (traceColumnIndexes.length === 0) {
    throw new Error("CSV must include at least one trace data column.");
  }

  return traceColumnIndexes.map(({ header, index }) => {
    const metadata = resolveTraceMetadata(header, fileName);

    if (sweepColumn) {
      const frequencyValues = new Set<number>();
      const sweepValues = new Set<number>();
      const valueByCoordinate = new Map<string, number>();

      parsedCsv.rows.forEach((row, rowIndex) => {
        const frequency = parseNumericValue(
          row[frequencyColumnIndex] ?? "",
          `row ${rowIndex + 2} frequency column`,
        );
        const sweep = parseNumericValue(
          row[sweepColumn.index] ?? "",
          `row ${rowIndex + 2} sweep column ${sweepColumn.name}`,
        );
        const value = parseNumericValue(
          row[index] ?? "",
          `row ${rowIndex + 2} column ${header}`,
        );
        const coordinateKey = `${frequency}\u0000${sweep}`;
        if (valueByCoordinate.has(coordinateKey)) {
          throw new Error(
            `CSV includes duplicate values for frequency ${frequency} and ${sweepColumn.name} ${sweep}.`,
          );
        }

        frequencyValues.add(frequency);
        sweepValues.add(sweep);
        valueByCoordinate.set(coordinateKey, value);
      });

      const frequencyAxisValues = [...frequencyValues].sort((left, right) => left - right);
      const sweepAxisValues = [...sweepValues].sort((left, right) => left - right);
      const expectedGridSize = frequencyAxisValues.length * sweepAxisValues.length;
      if (expectedGridSize !== parsedCsv.rows.length) {
        throw new Error(
          `CSV rows (${parsedCsv.rows.length}) do not match the expected grid size (${frequencyAxisValues.length} x ${sweepAxisValues.length}).`,
        );
      }

      const values = frequencyAxisValues.map((frequency) =>
        sweepAxisValues.map((sweep) => {
          const value = valueByCoordinate.get(`${frequency}\u0000${sweep}`);
          if (value === undefined) {
            throw new Error(
              `CSV is missing a value for frequency ${frequency} and ${sweepColumn.name} ${sweep}.`,
            );
          }
          return value;
        }),
      );

      return {
        trace_id: null,
        family: metadata.family,
        parameter: metadata.parameter,
        representation: metadata.representation,
        trace_mode_group: "base",
        stage_kind: "raw",
        provenance_summary: formatTraceProvenance({
          kind,
          fileName,
          header,
          parameter: metadata.parameter,
          representation: metadata.representation,
        }),
        axes: [
          {
            name: axisName,
            unit: axisUnit,
            length: frequencyAxisValues.length,
          },
          {
            name: sweepColumn.name,
            unit: sweepColumn.unit,
            length: sweepAxisValues.length,
          },
        ],
        preview_payload: {
          kind: "nd_grid",
          axes: [
            { name: axisName, unit: axisUnit, values: frequencyAxisValues },
            { name: sweepColumn.name, unit: sweepColumn.unit, values: sweepAxisValues },
          ],
          values,
        },
      } satisfies RawDataTraceDraft;
    }

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
      provenance_summary: formatTraceProvenance({
        kind,
        fileName,
        header,
        parameter: metadata.parameter,
        representation: metadata.representation,
      }),
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
  const sweepColumn = resolveHfssSweepColumn(parsedCsv.headers, frequencyColumn.index);
  const draftTraces = buildTraceDrafts(
    input.fileName,
    parsedCsv,
    frequencyColumn.index,
    frequencyColumn.axisName,
    frequencyColumn.axisUnit,
    input.kind,
    sweepColumn,
  );
  const dataHeaders = parsedCsv.headers.filter(
    (_, headerIndex) =>
      headerIndex !== frequencyColumn.index && headerIndex !== sweepColumn?.index,
  );

  return {
    fileName: input.fileName,
    designNameSuggestion: resolveDesignNameSuggestion(input.fileName),
    provenanceLabelSuggestion: `${
      input.kind === "measurement" ? "Measurement" : "Layout simulation"
    } import · ${humanizeFileStem(input.fileName)}`,
    axisName: frequencyColumn.axisName,
    axisUnit: frequencyColumn.axisUnit,
    pointCount: parsedCsv.rows.length,
    traces: draftTraces.map((trace, index) => {
      const pointCount = trace.axes.reduce((total, axis) => total * axis.length, 1);
      return {
        family: trace.family,
        parameter: trace.parameter,
        representation: trace.representation,
        pointCount,
        headerLabel: dataHeaders[index] ?? trace.parameter,
        previewPointCount: Array.isArray(trace.preview_payload.points)
          ? trace.preview_payload.points.length
          : pointCount,
      };
    }),
    draftTraces,
  };
}

export function buildUploadFirstIngestionDraft(input: Readonly<{
  kind: RawDataIngestionKind;
  designName: string;
  designId?: string | null;
  provenanceLabel: string;
  validation: UploadValidationResult;
}>): RawDataIngestionDraft {
  return {
    kind: input.kind,
    design_name: input.designName.trim(),
    design_id: input.designId ?? null,
    provenance_label: input.provenanceLabel.trim(),
    traces: [...input.validation.draftTraces],
  };
}
