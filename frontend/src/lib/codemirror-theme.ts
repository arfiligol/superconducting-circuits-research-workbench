import type { Extension } from "@codemirror/state";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";

const vsCodeDarkHighlightStyle = HighlightStyle.define([
  { tag: [t.keyword, t.modifier, t.controlKeyword], color: "#c586c0" },
  { tag: [t.operatorKeyword, t.definitionKeyword], color: "#569cd6" },
  { tag: [t.function(t.variableName), t.labelName], color: "#dcdcaa" },
  { tag: [t.variableName, t.propertyName, t.attributeName], color: "#9cdcfe" },
  { tag: [t.className, t.typeName, t.namespace], color: "#4ec9b0" },
  { tag: [t.string, t.special(t.string)], color: "#ce9178" },
  { tag: [t.number, t.integer, t.float, t.bool, t.null], color: "#b5cea8" },
  { tag: [t.comment], color: "#6a9955", fontStyle: "italic" },
  { tag: [t.regexp, t.escape, t.url], color: "#d16969" },
  { tag: [t.punctuation, t.bracket, t.separator], color: "#d4d4d4" },
  { tag: [t.meta], color: "#9cdcfe" },
]);

export const vsCodeDarkEditorTheme: Extension = [
  EditorView.theme({
    "&": {
      backgroundColor: "#1e1e1e",
      color: "#d4d4d4",
    },
    ".cm-content": {
      caretColor: "#aeafad",
    },
    ".cm-cursor, .cm-dropCursor": {
      borderLeftColor: "#aeafad",
    },
    "&.cm-focused .cm-selectionBackground, .cm-selectionBackground, .cm-content ::selection": {
      backgroundColor: "#264f78",
    },
    ".cm-panels": {
      backgroundColor: "#1e1e1e",
      color: "#d4d4d4",
    },
    ".cm-gutters": {
      backgroundColor: "#252526",
      color: "#858585",
      borderRight: "1px solid #3c3c3c",
    },
    ".cm-activeLine": {
      backgroundColor: "#2a2d2e",
    },
    ".cm-activeLineGutter": {
      backgroundColor: "#2a2d2e",
    },
    ".cm-scroller": {
      fontFamily:
        "ui-monospace, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, Liberation Mono, monospace",
    },
  }),
  syntaxHighlighting(vsCodeDarkHighlightStyle),
];
