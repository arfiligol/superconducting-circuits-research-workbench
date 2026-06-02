import type { CircuitDefinitionDraft } from "@/features/circuit-definition-editor/lib/contracts";

export type CircuitNetlistComponent = Readonly<{
  name: string;
  unit: string;
  default?: number;
  value_ref?: string;
}>;

export type CircuitNetlistParameter = Readonly<{
  name: string;
  default: number;
  unit: string;
}>;

export type CircuitNetlistTopologyRow = readonly [string, string, string, string | number];

export type CircuitNetlistDocument = Readonly<{
  name: string;
  components: readonly CircuitNetlistComponent[];
  topology: readonly CircuitNetlistTopologyRow[];
  parameters?: readonly CircuitNetlistParameter[];
}>;

export type CircuitNetlistDiagnostic = Readonly<{
  path: string;
  message: string;
  severity: "error" | "warning";
}>;

export type ParsedCircuitNetlistSource = Readonly<{
  document: CircuitNetlistDocument | null;
  formattedSource: string;
  diagnostics: readonly CircuitNetlistDiagnostic[];
}>;

export type CircuitDefinitionSerializerBoundary = Readonly<{
  definitionName: string;
  sourceDocumentName: string | null;
  canonicalSourceText: string;
  willRewriteSourceName: boolean;
  detail: string;
}>;

const nodeTokenPattern = /^\d+$/;
const MAX_INLINE_LINE_LENGTH = 100;

function normalizePythonLikeSource(sourceText: string) {
  return sourceText
    .replace(/\bTrue\b/g, "true")
    .replace(/\bFalse\b/g, "false")
    .replace(/\bNone\b/g, "null")
    .replace(/'/g, "\"")
    .replace(/\(/g, "[")
    .replace(/\)/g, "]")
    .replace(/,\s*([}\]])/g, "$1");
}

function parseJsonObject(sourceText: string): Record<string, unknown> | null {
  try {
    const parsed = JSON.parse(sourceText) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>;
    }
  } catch {
    return null;
  }

  return null;
}

function toFiniteNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function indent(level: number) {
  return "  ".repeat(level);
}

function fitsInline(text: string, indentLevel: number) {
  return indent(indentLevel).length + text.length <= MAX_INLINE_LINE_LENGTH;
}

function serializePrimitiveJson(value: string | number | boolean | null) {
  return JSON.stringify(value);
}

function serializeInlineJsonArray(values: readonly (string | number | boolean | null)[]) {
  return `[${values.map((value) => serializePrimitiveJson(value)).join(", ")}]`;
}

function serializeInlineJsonObject(
  entries: readonly (readonly [string, string | number | boolean | null])[],
) {
  const parts = entries.map(
    ([key, value]) => `${JSON.stringify(key)}: ${serializePrimitiveJson(value)}`,
  );
  return `{ ${parts.join(", ")} }`;
}

function serializeComponentLine(component: CircuitNetlistComponent, indentLevel: number) {
  const entries: [string, string | number | boolean | null][] = [
    ["name", component.name],
    ["unit", component.unit],
  ];
  if (component.default !== undefined) {
    entries.push(["default", component.default]);
  }
  if (component.value_ref !== undefined) {
    entries.push(["value_ref", component.value_ref]);
  }

  const inline = serializeInlineJsonObject(entries);
  if (fitsInline(inline, indentLevel)) {
    return inline;
  }

  const lines = entries.map(
    ([key, value], index) =>
      `${indent(indentLevel + 1)}${JSON.stringify(key)}: ${serializePrimitiveJson(value)}${
        index < entries.length - 1 ? "," : ""
      }`,
  );
  return `{\n${lines.join("\n")}\n${indent(indentLevel)}}`;
}

function serializeParameterLine(parameter: CircuitNetlistParameter, indentLevel: number) {
  const entries: [string, string | number | boolean | null][] = [
    ["name", parameter.name],
    ["default", parameter.default],
    ["unit", parameter.unit],
  ];

  const inline = serializeInlineJsonObject(entries);
  if (fitsInline(inline, indentLevel)) {
    return inline;
  }

  const lines = entries.map(
    ([key, value], index) =>
      `${indent(indentLevel + 1)}${JSON.stringify(key)}: ${serializePrimitiveJson(value)}${
        index < entries.length - 1 ? "," : ""
      }`,
  );
  return `{\n${lines.join("\n")}\n${indent(indentLevel)}}`;
}

function serializeTopologyRowLine(row: CircuitNetlistTopologyRow, indentLevel: number) {
  const inline = serializeInlineJsonArray(row);
  if (fitsInline(inline, indentLevel)) {
    return inline;
  }

  const lines = row.map(
    (value, index) =>
      `${indent(indentLevel + 1)}${serializePrimitiveJson(value)}${
        index < row.length - 1 ? "," : ""
      }`,
  );
  return `[\n${lines.join("\n")}\n${indent(indentLevel)}]`;
}

function serializeCircuitNetlist(document: CircuitNetlistDocument) {
  const parameters = document.parameters ?? [];
  const lines: string[] = ["{"];

  lines.push(`${indent(1)}"name": ${serializePrimitiveJson(document.name)},`);

  if (document.components.length === 0) {
    lines.push(`${indent(1)}"components": [],`);
  } else {
    lines.push(`${indent(1)}"components": [`);
    for (const [index, component] of document.components.entries()) {
      lines.push(
        `${indent(2)}${serializeComponentLine(component, 2)}${
          index < document.components.length - 1 ? "," : ""
        }`,
      );
    }
    lines.push(`${indent(1)}],`);
  }

  if (document.topology.length === 0) {
    lines.push(`${indent(1)}"topology": []${parameters.length ? "," : ""}`);
  } else {
    lines.push(`${indent(1)}"topology": [`);
    for (const [index, row] of document.topology.entries()) {
      lines.push(
        `${indent(2)}${serializeTopologyRowLine(row, 2)}${
          index < document.topology.length - 1 ? "," : ""
        }`,
      );
    }
    lines.push(`${indent(1)}]${parameters.length ? "," : ""}`);
  }

  if (parameters.length > 0) {
    lines.push(`${indent(1)}"parameters": [`);
    for (const [index, parameter] of parameters.entries()) {
      lines.push(
        `${indent(2)}${serializeParameterLine(parameter, 2)}${
          index < parameters.length - 1 ? "," : ""
        }`,
      );
    }
    lines.push(`${indent(1)}]`);
  }

  lines.push("}");
  return lines.join("\n");
}

type ParseCircuitNetlistOptions = Readonly<{
  canonicalName?: string;
}>;

export function parseCircuitNetlistSource(
  sourceText: string,
  options?: ParseCircuitNetlistOptions,
): ParsedCircuitNetlistSource {
  const trimmedSource = sourceText.trim();
  if (trimmedSource.length === 0) {
    return {
      document: null,
      formattedSource: "",
      diagnostics: [
        {
          path: "source_text",
          message: "Circuit netlist source is required.",
          severity: "error",
        },
      ],
    };
  }

  const parsedObject =
    parseJsonObject(trimmedSource) ?? parseJsonObject(normalizePythonLikeSource(trimmedSource));

  if (!parsedObject) {
    return {
      document: null,
      formattedSource: trimmedSource,
      diagnostics: [
        {
          path: "source_text",
          message: "Source must be a JSON or Python-literal object that matches the circuit-netlist contract.",
          severity: "error",
        },
      ],
    };
  }

  const document = coerceCircuitNetlistDocument(parsedObject);
  const normalizedDocument =
    options?.canonicalName && options.canonicalName.trim().length > 0
      ? {
          ...document,
          name: options.canonicalName.trim(),
        }
      : document;
  const diagnostics = validateCircuitNetlistDocument(normalizedDocument);

  return {
    document: normalizedDocument,
    formattedSource: serializeCircuitNetlist(normalizedDocument),
    diagnostics,
  };
}

export function formatCircuitNetlistSource(
  sourceText: string,
  options?: ParseCircuitNetlistOptions,
) {
  return parseCircuitNetlistSource(sourceText, options);
}

export function buildCircuitDefinitionDraft(input: Readonly<{
  name: string;
  sourceText: string;
}>): Readonly<{
  draft: CircuitDefinitionDraft | null;
  formattedSource: string;
  diagnostics: readonly CircuitNetlistDiagnostic[];
}> {
  const parsed = parseCircuitNetlistSource(input.sourceText, {
    canonicalName: input.name,
  });
  if (!parsed.document) {
    return {
      draft: null,
      formattedSource: parsed.formattedSource,
      diagnostics: parsed.diagnostics,
    };
  }

  const document: CircuitNetlistDocument = {
    ...parsed.document,
    name: input.name.trim(),
  };
  const diagnostics = validateCircuitNetlistDocument(document);
  const blockingDiagnostics = diagnostics.filter((diagnostic) => diagnostic.severity === "error");

  if (blockingDiagnostics.length > 0) {
    return {
      draft: null,
      formattedSource: serializeCircuitNetlist(document),
      diagnostics,
    };
  }

  return {
    draft: {
      name: input.name.trim(),
      source_text: serializeCircuitNetlist(document),
    },
    formattedSource: serializeCircuitNetlist(document),
    diagnostics,
  };
}

export function summarizeCircuitDefinitionSerializerBoundary(input: Readonly<{
  name: string;
  sourceText: string;
}>): CircuitDefinitionSerializerBoundary {
  const parsed = parseCircuitNetlistSource(input.sourceText);
  const definitionName = input.name.trim();
  const sourceDocumentName = parsed.document?.name?.trim() || null;
  const canonicalSourceText = parsed.document
    ? serializeCircuitNetlist({
        ...parsed.document,
        name: definitionName,
      })
    : parsed.formattedSource;
  const willRewriteSourceName =
    parsed.document !== null &&
    sourceDocumentName !== null &&
    sourceDocumentName.length > 0 &&
    sourceDocumentName !== definitionName;

  return {
    definitionName,
    sourceDocumentName,
    canonicalSourceText,
    willRewriteSourceName,
    detail: willRewriteSourceName
      ? `Format and Save will rewrite the netlist document name from "${sourceDocumentName}" to "${definitionName}".`
      : "Serializer output already matches the current definition identity.",
  };
}

export function summarizeCircuitNetlistDocument(document: CircuitNetlistDocument | null) {
  return {
    componentCount: document?.components.length ?? 0,
    topologyCount: document?.topology.length ?? 0,
    parameterCount: document?.parameters?.length ?? 0,
  };
}

function coerceCircuitNetlistDocument(
  value: Record<string, unknown>,
): CircuitNetlistDocument {
  const components = Array.isArray(value.components)
    ? value.components
        .map((component) => coerceComponent(component))
        .filter((component): component is CircuitNetlistComponent => component !== null)
    : [];
  const topology = Array.isArray(value.topology)
    ? value.topology
        .map((row) => coerceTopologyRow(row))
        .filter((row): row is CircuitNetlistTopologyRow => row !== null)
    : [];
  const parameters = Array.isArray(value.parameters)
    ? value.parameters
        .map((parameter) => coerceParameter(parameter))
        .filter((parameter): parameter is CircuitNetlistParameter => parameter !== null)
    : [];

  return {
    name: typeof value.name === "string" ? value.name : "",
    components,
    topology,
    ...(parameters.length > 0 ? { parameters } : {}),
  };
}

function coerceComponent(value: unknown): CircuitNetlistComponent | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  const record = value as Record<string, unknown>;
  const defaultValue = toFiniteNumber(record.default);

  return {
    name: typeof record.name === "string" ? record.name : "",
    unit: typeof record.unit === "string" ? record.unit : "",
    ...(defaultValue !== null ? { default: defaultValue } : {}),
    ...(typeof record.value_ref === "string" ? { value_ref: record.value_ref } : {}),
  };
}

function coerceParameter(value: unknown): CircuitNetlistParameter | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }

  const record = value as Record<string, unknown>;
  const defaultValue = toFiniteNumber(record.default);
  if (defaultValue === null) {
    return null;
  }

  return {
    name: typeof record.name === "string" ? record.name : "",
    default: defaultValue,
    unit: typeof record.unit === "string" ? record.unit : "",
  };
}

function coerceTopologyRow(value: unknown): CircuitNetlistTopologyRow | null {
  if (!Array.isArray(value) || value.length !== 4) {
    return null;
  }

  const [elementName, node1, node2, componentRef] = value;
  if (
    typeof elementName !== "string" ||
    typeof node1 !== "string" ||
    typeof node2 !== "string" ||
    !(typeof componentRef === "string" || typeof componentRef === "number")
  ) {
    return null;
  }

  return [elementName, node1, node2, componentRef];
}

function validateCircuitNetlistDocument(
  document: CircuitNetlistDocument,
): readonly CircuitNetlistDiagnostic[] {
  const diagnostics: CircuitNetlistDiagnostic[] = [];
  const parameterMap = new Map(document.parameters?.map((parameter) => [parameter.name, parameter]));
  const componentMap = new Map(document.components.map((component) => [component.name, component]));

  if (document.name.trim().length === 0) {
    diagnostics.push({
      path: "name",
      message: "Netlist name is required.",
      severity: "error",
    });
  }

  if (document.components.length === 0) {
    diagnostics.push({
      path: "components",
      message: "At least one component is required.",
      severity: "error",
    });
  }

  if (document.topology.length === 0) {
    diagnostics.push({
      path: "topology",
      message: "At least one topology row is required.",
      severity: "error",
    });
  }

  document.components.forEach((component, index) => {
    const defaultDefined = component.default !== undefined;
    const valueRefDefined = component.value_ref !== undefined;

    if (component.name.trim().length === 0) {
      diagnostics.push({
        path: `components[${index}].name`,
        message: "Component name is required.",
        severity: "error",
      });
    }

    if (component.unit.trim().length === 0) {
      diagnostics.push({
        path: `components[${index}].unit`,
        message: `Component "${component.name || index}" must declare a unit.`,
        severity: "error",
      });
    }

    if (defaultDefined === valueRefDefined) {
      diagnostics.push({
        path: `components[${index}]`,
        message: `Component "${component.name || index}" must define exactly one of "default" or "value_ref".`,
        severity: "error",
      });
    }

    if (component.value_ref) {
      const parameter = parameterMap.get(component.value_ref);
      if (!parameter) {
        diagnostics.push({
          path: `components[${index}].value_ref`,
          message: `Component "${component.name}" references undefined parameter "${component.value_ref}".`,
          severity: "error",
        });
      } else if (parameter.unit !== component.unit) {
        diagnostics.push({
          path: `components[${index}].unit`,
          message: `Component "${component.name}" and parameter "${parameter.name}" must use the same unit.`,
          severity: "error",
        });
      }
    }
  });

  document.parameters?.forEach((parameter, index) => {
    if (parameter.name.trim().length === 0) {
      diagnostics.push({
        path: `parameters[${index}].name`,
        message: "Parameter name is required.",
        severity: "error",
      });
    }

    if (parameter.unit.trim().length === 0) {
      diagnostics.push({
        path: `parameters[${index}].unit`,
        message: `Parameter "${parameter.name || index}" must declare a unit.`,
        severity: "error",
      });
    }
  });

  document.topology.forEach((row, index) => {
    const [elementName, node1, node2, componentRef] = row;

    if (!nodeTokenPattern.test(node1) || !nodeTokenPattern.test(node2)) {
      diagnostics.push({
        path: `topology[${index}]`,
        message: `Topology row "${elementName}" must use numeric string node tokens and ground token "0".`,
        severity: "error",
      });
    }

    if (elementName.startsWith("P")) {
      if (!Number.isInteger(componentRef)) {
        diagnostics.push({
          path: `topology[${index}][3]`,
          message: `Port row "${elementName}" must use an integer port index in the 4th field.`,
          severity: "error",
        });
      }
      return;
    }

    if (elementName.startsWith("K")) {
      if (!node1.startsWith("L") || !node2.startsWith("L")) {
        diagnostics.push({
          path: `topology[${index}]`,
          message: `Mutual coupling row "${elementName}" must reference inductor element names in positions 2 and 3.`,
          severity: "error",
        });
      }

      if (typeof componentRef !== "string" || !componentMap.has(componentRef)) {
        diagnostics.push({
          path: `topology[${index}][3]`,
          message: `Mutual coupling row "${elementName}" must reference an existing coupling component name.`,
          severity: "error",
        });
      }
      return;
    }

    if (typeof componentRef !== "string" || !componentMap.has(componentRef)) {
      diagnostics.push({
        path: `topology[${index}][3]`,
        message: `Topology row "${elementName}" must reference an existing component name.`,
        severity: "error",
      });
    }
  });

  return diagnostics;
}
