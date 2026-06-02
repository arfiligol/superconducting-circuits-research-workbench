"use client";

import type { EditableNumericGridModel } from "@/features/data-browser/lib/trace-edit-grid";

type TraceEditNumericGridProps = Readonly<{
  model: EditableNumericGridModel | null;
  rows: readonly string[][];
  disabled?: boolean;
  onCellChange: (rowIndex: number, columnIndex: number, value: string) => void;
}>;

export function TraceEditNumericGrid({
  model,
  rows,
  disabled = false,
  onCellChange,
}: TraceEditNumericGridProps) {
  if (!model) {
    return (
      <div className="rounded-[1rem] border border-dashed border-border bg-background px-4 py-5 text-sm text-muted-foreground">
        Numeric payload editing is not exposed as tabular rows and columns in the current backend
        contract. Metadata fields can still be updated.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[1rem] border border-border/80 bg-background">
      <div className="border-b border-border/80 px-4 py-3">
        <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          Numeric Payload
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          Edit the backend-authoritative numeric cells directly.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full table-fixed text-left text-sm">
          <thead className="bg-surface text-xs uppercase tracking-[0.16em] text-muted-foreground">
            <tr>
              <th className="w-16 px-3 py-3">Row</th>
              {model.columns.map((column) => (
                <th key={column} className="min-w-[140px] px-3 py-3">
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border bg-background">
            {rows.map((row, rowIndex) => (
              <tr key={`grid-row-${rowIndex}`}>
                <td className="px-3 py-3 align-top text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                  {rowIndex + 1}
                </td>
                {model.columns.map((column, columnIndex) => (
                  <td key={`${column}-${rowIndex}`} className="px-3 py-3 align-top">
                    <input
                      value={row[columnIndex] ?? ""}
                      disabled={disabled}
                      onChange={(event) => {
                        onCellChange(rowIndex, columnIndex, event.target.value);
                      }}
                      className="w-full rounded-[0.85rem] border border-border/85 bg-surface px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary/45 focus:ring-2 focus:ring-primary/15 disabled:cursor-not-allowed disabled:opacity-60"
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
