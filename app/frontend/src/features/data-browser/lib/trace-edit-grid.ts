"use client";

type GridSourceShape = "points" | "rows_array" | "rows_objects" | "column_arrays";

type PrimitiveCell = string | number | boolean | null;

type GridPayloadBase = Readonly<Record<string, unknown>>;

export type EditableNumericGridModel = Readonly<{
  sourceShape: GridSourceShape;
  basePayload: GridPayloadBase;
  columns: readonly string[];
  rows: readonly string[][];
  originalRows: readonly (readonly unknown[] | Readonly<Record<string, unknown>>)[];
  arrayKeys?: readonly string[];
}>;

const numberPattern = /^-?(?:\d+|\d*\.\d+)(?:[eE][+-]?\d+)?$/;

export function resolveEditableNumericGridModel(
  payload: Readonly<Record<string, unknown>>,
): EditableNumericGridModel | null {
  const pointsModel = resolvePointsGridModel(payload);
  if (pointsModel) {
    return pointsModel;
  }

  const rowsArrayModel = resolveRowsArrayGridModel(payload);
  if (rowsArrayModel) {
    return rowsArrayModel;
  }

  const rowsObjectsModel = resolveRowsObjectsGridModel(payload);
  if (rowsObjectsModel) {
    return rowsObjectsModel;
  }

  return resolveColumnArraysGridModel(payload);
}

export function updateEditableNumericGridCell(
  rows: readonly string[][],
  rowIndex: number,
  columnIndex: number,
  nextValue: string,
) {
  return rows.map((row, currentRowIndex) =>
    currentRowIndex === rowIndex
      ? row.map((cell, currentColumnIndex) =>
          currentColumnIndex === columnIndex ? nextValue : cell,
        )
      : row,
  );
}

export function serializeEditableNumericGridModel(
  model: EditableNumericGridModel,
  rows: readonly string[][],
): Record<string, unknown> {
  switch (model.sourceShape) {
    case "points":
      return {
        ...model.basePayload,
        points: rows.map((row, rowIndex) =>
          row.map((value, columnIndex) =>
            coerceEditedCellValue(
              value,
              Array.isArray(model.originalRows[rowIndex])
                ? model.originalRows[rowIndex][columnIndex]
                : undefined,
            ),
          ),
        ),
      };
    case "rows_array":
      return {
        ...model.basePayload,
        columns: [...model.columns],
        rows: rows.map((row, rowIndex) =>
          row.map((value, columnIndex) =>
            coerceEditedCellValue(
              value,
              Array.isArray(model.originalRows[rowIndex])
                ? model.originalRows[rowIndex][columnIndex]
                : undefined,
            ),
          ),
        ),
      };
    case "rows_objects":
      return {
        ...model.basePayload,
        columns: [...model.columns],
        rows: rows.map((row, rowIndex) =>
          Object.fromEntries(
            model.columns.map((column, columnIndex) => [
              column,
              coerceEditedCellValue(
                row[columnIndex] ?? "",
                isRecord(model.originalRows[rowIndex])
                  ? model.originalRows[rowIndex][column]
                  : undefined,
              ),
            ]),
          ),
        ),
      };
    case "column_arrays": {
      const nextPayload: Record<string, unknown> = {
        ...model.basePayload,
      };

      for (const [columnIndex, column] of model.columns.entries()) {
        nextPayload[column] = rows.map((row, rowIndex) =>
          coerceEditedCellValue(
            row[columnIndex] ?? "",
            Array.isArray(model.originalRows[rowIndex])
              ? model.originalRows[rowIndex][columnIndex]
              : undefined,
          ),
        );
      }

      return nextPayload;
    }
  }
}

function resolvePointsGridModel(
  payload: Readonly<Record<string, unknown>>,
): EditableNumericGridModel | null {
  if (!Array.isArray(payload.points) || payload.points.length === 0) {
    return null;
  }

  if (!payload.points.every((row) => Array.isArray(row))) {
    return null;
  }

  const originalRows = payload.points as readonly unknown[][];
  const width = Math.max(...originalRows.map((row) => row.length), 0);
  const columns = Array.from({ length: width }, (_, index) =>
    index === 0 ? "X" : index === 1 ? "Y" : `Value ${index + 1}`,
  );

  return {
    sourceShape: "points",
    basePayload: payload,
    columns,
    rows: originalRows.map((row) => columns.map((_, index) => stringifyCellValue(row[index]))),
    originalRows,
  };
}

function resolveRowsArrayGridModel(
  payload: Readonly<Record<string, unknown>>,
): EditableNumericGridModel | null {
  if (!Array.isArray(payload.rows) || payload.rows.length === 0) {
    return null;
  }

  if (!payload.rows.every((row) => Array.isArray(row))) {
    return null;
  }

  const originalRows = payload.rows as readonly unknown[][];
  const width = Math.max(
    Array.isArray(payload.columns)
      ? payload.columns.filter((column): column is string => typeof column === "string").length
      : 0,
    ...originalRows.map((row) => row.length),
  );
  const columns =
    Array.isArray(payload.columns) &&
    payload.columns.every((column): column is string => typeof column === "string")
      ? payload.columns
      : Array.from({ length: width }, (_, index) => `Column ${index + 1}`);

  return {
    sourceShape: "rows_array",
    basePayload: payload,
    columns,
    rows: originalRows.map((row) => columns.map((_, index) => stringifyCellValue(row[index]))),
    originalRows,
  };
}

function resolveRowsObjectsGridModel(
  payload: Readonly<Record<string, unknown>>,
): EditableNumericGridModel | null {
  if (!Array.isArray(payload.rows) || payload.rows.length === 0) {
    return null;
  }

  if (!payload.rows.every((row) => isRecord(row))) {
    return null;
  }

  const originalRows = payload.rows as readonly Readonly<Record<string, unknown>>[];
  const columns = resolveObjectColumns(payload, originalRows);
  if (columns.length === 0) {
    return null;
  }

  return {
    sourceShape: "rows_objects",
    basePayload: payload,
    columns,
    rows: originalRows.map((row) => columns.map((column) => stringifyCellValue(row[column]))),
    originalRows,
  };
}

function resolveColumnArraysGridModel(
  payload: Readonly<Record<string, unknown>>,
): EditableNumericGridModel | null {
  const entries = Object.entries(payload).filter((entry) => isPrimitiveArray(entry[1]));
  if (entries.length === 0) {
    return null;
  }

  const lengths = new Set(entries.map(([, value]) => (value as readonly PrimitiveCell[]).length));
  if (lengths.size !== 1) {
    return null;
  }

  const arrayKeys = entries.map(([key]) => key);
  const rowCount = entries[0]?.[1] && Array.isArray(entries[0][1]) ? entries[0][1].length : 0;
  const originalRows = Array.from({ length: rowCount }, (_, rowIndex) =>
    arrayKeys.map((column) => {
      const value = payload[column];
      return Array.isArray(value) ? value[rowIndex] : undefined;
    }),
  );

  return {
    sourceShape: "column_arrays",
    basePayload: payload,
    columns: arrayKeys,
    rows: originalRows.map((row) => row.map((value) => stringifyCellValue(value))),
    originalRows,
    arrayKeys,
  };
}

function resolveObjectColumns(
  payload: Readonly<Record<string, unknown>>,
  rows: readonly Readonly<Record<string, unknown>>[],
) {
  if (
    Array.isArray(payload.columns) &&
    payload.columns.every((column): column is string => typeof column === "string")
  ) {
    return payload.columns;
  }

  const seen = new Set<string>();
  const columns: string[] = [];

  for (const row of rows) {
    for (const key of Object.keys(row)) {
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      columns.push(key);
    }
  }

  return columns;
}

function stringifyCellValue(value: unknown) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

function coerceEditedCellValue(value: string, originalValue: unknown): unknown {
  const trimmed = value.trim();

  if (trimmed.length === 0) {
    return typeof originalValue === "number" ? null : "";
  }

  if (typeof originalValue === "number" || originalValue === null || originalValue === undefined) {
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : value;
  }

  if (typeof originalValue === "boolean") {
    if (trimmed === "true") {
      return true;
    }
    if (trimmed === "false") {
      return false;
    }
    return value;
  }

  if (typeof originalValue === "string" && numberPattern.test(trimmed)) {
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : value;
  }

  return value;
}

function isPrimitiveArray(value: unknown): value is readonly PrimitiveCell[] {
  return (
    Array.isArray(value) &&
    value.every(
      (cell) =>
        cell === null ||
        typeof cell === "string" ||
        typeof cell === "number" ||
        typeof cell === "boolean",
    )
  );
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
