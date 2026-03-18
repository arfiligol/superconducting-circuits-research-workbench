import {
  EditorState,
  RangeSetBuilder,
  StateField,
  type Extension,
  type Range,
} from "@codemirror/state";
import {
  Decoration,
  EditorView,
  GutterMarker,
  WidgetType,
  gutter,
} from "@codemirror/view";

import type { SchemdrawDiagnostic } from "@/features/circuit-schemdraw/lib/api";
import type { SchemdrawFailureDetail } from "@/features/circuit-schemdraw/lib/render";

export type SchemdrawEditorDiagnosticTarget = "source" | "relation";

export type SchemdrawEditorDiagnostic = Readonly<{
  id: string;
  target: SchemdrawEditorDiagnosticTarget;
  severity: SchemdrawDiagnostic["severity"];
  code: string;
  message: string;
  source: SchemdrawDiagnostic["source"];
  blocking: boolean;
  line: number | null;
  column: number | null;
}>;

export function buildSchemdrawEditorDiagnostics(
  diagnostics: readonly SchemdrawDiagnostic[],
): Readonly<{
  sourceDiagnostics: readonly SchemdrawEditorDiagnostic[];
  relationDiagnostics: readonly SchemdrawEditorDiagnostic[];
}> {
  const mappedDiagnostics = diagnostics.map((diagnostic, index) =>
    mapSchemdrawEditorDiagnostic(diagnostic, index),
  );

  return {
    sourceDiagnostics: mappedDiagnostics.filter((diagnostic) => diagnostic.target === "source"),
    relationDiagnostics: mappedDiagnostics.filter((diagnostic) => diagnostic.target === "relation"),
  };
}

export function summarizeSchemdrawEditorNotice(input: Readonly<{
  diagnostics: readonly SchemdrawEditorDiagnostic[];
  failureDetail: SchemdrawFailureDetail | null;
  target: SchemdrawEditorDiagnosticTarget;
  developerModeEnabled: boolean;
}>):
  | Readonly<{
      tone: "default" | "warning" | "error";
      title: string;
      message: string;
    }>
  | null {
  const primaryDiagnostic = input.diagnostics[0] ?? null;
  const relevantFailure =
    input.failureDetail &&
    ((input.target === "relation" && input.failureDetail.kind === "relation_config") ||
      (input.target === "source" && input.failureDetail.kind !== "relation_config"))
      ? input.failureDetail
      : null;

  if (relevantFailure) {
    return {
      tone: relevantFailure.kind === "relation_config" ? "warning" : "error",
      title:
        input.target === "relation"
          ? "Advanced mapping issue"
          : "Preview request issue",
      message: input.developerModeEnabled
        ? [
            relevantFailure.errorCode,
            relevantFailure.technicalMessage ?? relevantFailure.userMessage,
          ]
            .filter(Boolean)
            .join(" · ")
        : relevantFailure.technicalMessage ?? relevantFailure.userMessage,
    };
  }

  if (!primaryDiagnostic) {
    return null;
  }

  const blockingCount = input.diagnostics.filter((diagnostic) => diagnostic.blocking).length;
  return {
    tone: primaryDiagnostic.severity === "error" ? "error" : "warning",
    title:
      input.target === "relation"
        ? "Advanced mapping diagnostics"
        : "Source diagnostics",
    message: input.developerModeEnabled
      ? [
          `${input.diagnostics.length} issue${input.diagnostics.length === 1 ? "" : "s"}`,
          blockingCount > 0 ? `${blockingCount} blocking` : "non-blocking",
          `${primaryDiagnostic.code}: ${primaryDiagnostic.message}`,
        ].join(" · ")
      : blockingCount > 0
        ? "Highlighted lines in the editor block the next backend render."
        : "Highlighted lines in the editor have diagnostics worth reviewing.",
  };
}

export function createSchemdrawDiagnosticsExtension(input: Readonly<{
  diagnostics: readonly SchemdrawEditorDiagnostic[];
  developerModeEnabled: boolean;
}>): Extension {
  const locatedDiagnostics = input.diagnostics.filter((diagnostic) => diagnostic.line !== null);
  if (locatedDiagnostics.length === 0) {
    return EditorView.theme({});
  }

  const diagnosticTheme = EditorView.baseTheme({
    ".cm-diagnostic-gutter-marker": {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      width: "0.8rem",
      height: "0.8rem",
      borderRadius: "999px",
      marginInlineStart: "0.1rem",
      boxShadow: "0 0 0 1px color-mix(in srgb, var(--border) 75%, transparent)",
    },
    ".cm-diagnostic-gutter-marker--error": {
      backgroundColor: "color-mix(in srgb, oklch(0.62 0.21 24) 88%, var(--card))",
    },
    ".cm-diagnostic-gutter-marker--warning": {
      backgroundColor: "color-mix(in srgb, oklch(0.82 0.14 82) 92%, var(--card))",
    },
    ".cm-diagnostic-gutter-marker--info": {
      backgroundColor: "color-mix(in srgb, var(--primary) 86%, var(--card))",
    },
    ".cm-diagnostic-line--error": {
      backgroundColor: "color-mix(in srgb, oklch(0.62 0.21 24) 10%, transparent)",
      boxShadow: "inset 3px 0 0 color-mix(in srgb, oklch(0.62 0.21 24) 78%, transparent)",
    },
    ".cm-diagnostic-line--warning": {
      backgroundColor: "color-mix(in srgb, oklch(0.82 0.14 82) 12%, transparent)",
      boxShadow: "inset 3px 0 0 color-mix(in srgb, oklch(0.82 0.14 82) 82%, transparent)",
    },
    ".cm-diagnostic-line--info": {
      backgroundColor: "color-mix(in srgb, var(--primary) 10%, transparent)",
      boxShadow: "inset 3px 0 0 color-mix(in srgb, var(--primary) 72%, transparent)",
    },
    ".cm-diagnostic-mark--error": {
      backgroundColor: "color-mix(in srgb, oklch(0.62 0.21 24) 18%, transparent)",
      textDecoration: "underline 2px color-mix(in srgb, oklch(0.62 0.21 24) 90%, transparent)",
      textUnderlineOffset: "0.16rem",
    },
    ".cm-diagnostic-mark--warning": {
      backgroundColor: "color-mix(in srgb, oklch(0.82 0.14 82) 18%, transparent)",
      textDecoration: "underline 2px color-mix(in srgb, oklch(0.82 0.14 82) 92%, transparent)",
      textUnderlineOffset: "0.16rem",
    },
    ".cm-diagnostic-mark--info": {
      backgroundColor: "color-mix(in srgb, var(--primary) 16%, transparent)",
      textDecoration: "underline 2px color-mix(in srgb, var(--primary) 88%, transparent)",
      textUnderlineOffset: "0.16rem",
    },
    ".cm-diagnostic-inline-chip": {
      marginInlineStart: "0.6rem",
      display: "inline-flex",
      alignItems: "center",
      borderRadius: "999px",
      border: "1px solid color-mix(in srgb, var(--border) 90%, transparent)",
      backgroundColor: "color-mix(in srgb, var(--surface) 88%, transparent)",
      padding: "0.15rem 0.55rem",
      fontSize: "0.68rem",
      fontWeight: "600",
      letterSpacing: "0.08em",
      textTransform: "uppercase",
      color: "color-mix(in srgb, var(--foreground) 88%, transparent)",
      maxWidth: "22rem",
      whiteSpace: "nowrap",
      overflow: "hidden",
      textOverflow: "ellipsis",
    },
  });

  const groupedByLine = groupDiagnosticsByLine(locatedDiagnostics);

  return [
    diagnosticTheme,
    StateField.define({
      create(state) {
        return buildEditorDecorations({
          state,
          groupedByLine,
          developerModeEnabled: input.developerModeEnabled,
        });
      },
      update(decorations, transaction) {
        if (!transaction.docChanged) {
          return decorations;
        }
        return buildEditorDecorations({
          state: transaction.state,
          groupedByLine,
          developerModeEnabled: input.developerModeEnabled,
        });
      },
      provide: (field) => EditorView.decorations.from(field),
    }),
    gutter({
      class: "cm-diagnostic-gutter",
      markers: (view) =>
        buildGutterMarkers({
          state: view.state,
          groupedByLine,
        }),
    }),
  ];
}

function mapSchemdrawEditorDiagnostic(
  diagnostic: SchemdrawDiagnostic,
  index: number,
): SchemdrawEditorDiagnostic {
  return {
    id: `${diagnostic.source}-${diagnostic.code}-${diagnostic.line ?? "na"}-${diagnostic.column ?? "na"}-${index}`,
    target: diagnostic.source === "relation_config" ? "relation" : "source",
    severity: diagnostic.severity,
    code: diagnostic.code,
    message: diagnostic.message,
    source: diagnostic.source,
    blocking: diagnostic.blocking,
    line: diagnostic.line ?? null,
    column: diagnostic.column ?? null,
  };
}

function groupDiagnosticsByLine(
  diagnostics: readonly SchemdrawEditorDiagnostic[],
) {
  const grouped = new Map<number, readonly SchemdrawEditorDiagnostic[]>();
  for (const diagnostic of diagnostics) {
    if (diagnostic.line === null) {
      continue;
    }
    grouped.set(diagnostic.line, [...(grouped.get(diagnostic.line) ?? []), diagnostic]);
  }
  return grouped;
}

function buildEditorDecorations(input: Readonly<{
  state: EditorState;
  groupedByLine: ReadonlyMap<number, readonly SchemdrawEditorDiagnostic[]>;
  developerModeEnabled: boolean;
}>) {
  const ranges: Range<Decoration>[] = [];
  const sortedLineNumbers = [...input.groupedByLine.keys()].sort((left, right) => left - right);

  for (const lineNumber of sortedLineNumbers) {
    const diagnostics = input.groupedByLine.get(lineNumber);
    if (!diagnostics || diagnostics.length === 0) {
      continue;
    }
    if (lineNumber < 1 || lineNumber > input.state.doc.lines) {
      continue;
    }
    const lineInfo = input.state.doc.line(lineNumber);
    const dominantDiagnostic = resolveDominantDiagnostic(diagnostics);
    ranges.push(
      Decoration.line({
        class: `cm-diagnostic-line--${dominantDiagnostic.severity}`,
      }).range(lineInfo.from),
    );

    const sortedDiagnostics = [...diagnostics].sort((left, right) => {
      const lineDelta = (left.line ?? 0) - (right.line ?? 0);
      if (lineDelta !== 0) {
        return lineDelta;
      }
      const columnDelta = (left.column ?? 1) - (right.column ?? 1);
      if (columnDelta !== 0) {
        return columnDelta;
      }
      return severityWeight(right.severity) - severityWeight(left.severity);
    });

    for (const diagnostic of sortedDiagnostics) {
      const columnStart = Math.max((diagnostic.column ?? 1) - 1, 0);
      const from = Math.min(lineInfo.to, lineInfo.from + columnStart);
      const to =
        lineInfo.to > lineInfo.from
          ? Math.max(
              from + 1,
              Math.min(lineInfo.to, from + Math.min(18, Math.max(1, Math.ceil(diagnostic.message.length / 4)))),
            )
          : from;
      if (to > from) {
        ranges.push(
          Decoration.mark({
            class: `cm-diagnostic-mark--${diagnostic.severity}`,
          }).range(from, to),
        );
      }
    }

    const inlineMessage = input.developerModeEnabled
      ? `${dominantDiagnostic.code} · ${dominantDiagnostic.message}`
      : dominantDiagnostic.message;
    ranges.push(
      Decoration.widget({
        widget: new DiagnosticInlineWidget(inlineMessage),
        side: 1,
      }).range(lineInfo.to),
    );
  }

  return Decoration.set(ranges, true);
}

function buildGutterMarkers(input: Readonly<{
  state: EditorState;
  groupedByLine: ReadonlyMap<number, readonly SchemdrawEditorDiagnostic[]>;
}>) {
  const markerBuilder = new RangeSetBuilder<GutterMarker>();
  for (const [lineNumber, diagnostics] of input.groupedByLine.entries()) {
    if (lineNumber < 1 || lineNumber > input.state.doc.lines) {
      continue;
    }
    const lineInfo = input.state.doc.line(lineNumber);
    markerBuilder.add(
      lineInfo.from,
      lineInfo.from,
      new DiagnosticGutterMarker(resolveDominantDiagnostic(diagnostics).severity),
    );
  }

  return markerBuilder.finish();
}

function resolveDominantDiagnostic(
  diagnostics: readonly SchemdrawEditorDiagnostic[],
) {
  return [...diagnostics].sort((left, right) => severityWeight(right.severity) - severityWeight(left.severity))[0];
}

function severityWeight(severity: SchemdrawDiagnostic["severity"]) {
  switch (severity) {
    case "error":
      return 3;
    case "warning":
      return 2;
    case "info":
    default:
      return 1;
  }
}

class DiagnosticGutterMarker extends GutterMarker {
  constructor(private readonly severity: SchemdrawDiagnostic["severity"]) {
    super();
  }

  toDOM() {
    const element = document.createElement("span");
    element.className = `cm-diagnostic-gutter-marker cm-diagnostic-gutter-marker--${this.severity}`;
    element.setAttribute("aria-hidden", "true");
    return element;
  }
}

class DiagnosticInlineWidget extends WidgetType {
  constructor(private readonly label: string) {
    super();
  }

  toDOM() {
    const element = document.createElement("span");
    element.className = "cm-diagnostic-inline-chip";
    element.textContent = this.label;
    return element;
  }
}
