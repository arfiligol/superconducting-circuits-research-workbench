const fs = require("fs");
const path = require("path");
const PptxGenJS = require("pptxgenjs");
const {
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require("../parameter_response_vv/pptxgenjs_helpers/layout");

const OUT_DIR = path.join(__dirname, "output");
const SLIDE_W = 13.333;
const SLIDE_H = 7.5;

const theme = {
  bg: "FBFAF7",
  panel: "FFFFFF",
  wash: "F3EFE7",
  softBlue: "EAF1FF",
  softBlueBorder: "BED1F9",
  ink: "10233A",
  subInk: "667487",
  border: "DDD9CF",
  accent: "2563EB",
  okSoft: "ECF7F1",
  okBorder: "B7DDCA",
  warnSoft: "FFF5E5",
  warnBorder: "F0D49D",
  failSoft: "FDEEEE",
  failBorder: "EABDBD",
  titleFont: "Avenir Next",
  bodyFont: "Avenir Next",
  monoFont: "Menlo",
};

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function addBackground(slide) {
  slide.background = { color: theme.bg };
}

function addChrome(slide, pageNo) {
  slide.addShape("rect", {
    x: 0,
    y: 0,
    w: SLIDE_W,
    h: 0.08,
    line: { color: theme.softBlueBorder, transparency: 100 },
    fill: { color: theme.softBlueBorder },
  });
  slide.addText(String(pageNo).padStart(2, "0"), {
    x: 12.24,
    y: 7.07,
    w: 0.4,
    h: 0.12,
    fontFace: theme.bodyFont,
    fontSize: 8.6,
    color: theme.subInk,
    margin: 0,
    align: "right",
  });
}

function addChip(slide, text, x = 0.82, y = 0.58, w = 2.9) {
  slide.addShape("roundRect", {
    x,
    y,
    w,
    h: 0.42,
    rectRadius: 0.08,
    line: { color: theme.softBlueBorder, width: 1 },
    fill: { color: theme.softBlue },
  });
  slide.addText(text, {
    x: x + 0.18,
    y: y + 0.11,
    w: w - 0.36,
    h: 0.16,
    fontFace: theme.bodyFont,
    fontSize: 9,
    color: theme.accent,
    bold: true,
    margin: 0,
  });
}

function addTitle(slide, eyebrow, title, subtitle, opts = {}) {
  if (eyebrow) {
    slide.addText(eyebrow, {
      x: opts.x ?? 0.82,
      y: opts.y ?? 0.58,
      w: opts.eyebrowW ?? 3.2,
      h: 0.18,
      fontFace: theme.bodyFont,
      fontSize: 9.5,
      color: theme.accent,
      bold: true,
      margin: 0,
    });
  }
  slide.addText(title, {
    x: opts.x ?? 0.82,
    y: (opts.y ?? 0.58) + 0.36,
    w: opts.w ?? 10.8,
    h: opts.h ?? 0.86,
    fontFace: theme.titleFont,
    fontSize: opts.titleSize ?? 22,
    color: theme.ink,
    bold: true,
    margin: 0,
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: opts.x ?? 0.82,
      y: (opts.y ?? 0.58) + 1.18,
      w: opts.subtitleW ?? 8.0,
      h: opts.subtitleH ?? 0.56,
      fontFace: theme.bodyFont,
      fontSize: 11,
      color: theme.subInk,
      margin: 0,
      valign: "top",
    });
  }
}

function addPanel(slide, x, y, w, h, opts = {}) {
  slide.addShape("roundRect", {
    x,
    y,
    w,
    h,
    rectRadius: 0.12,
    line: { color: opts.line ?? theme.border, width: opts.lineWidth ?? 1.05 },
    fill: { color: opts.fill ?? theme.panel },
  });
}

function addPanelTitle(slide, x, y, w, title) {
  slide.addText(title, {
    x,
    y,
    w,
    h: 0.18,
    fontFace: theme.bodyFont,
    fontSize: 10.9,
    color: theme.ink,
    bold: true,
    margin: 0,
  });
}

function addMetricChip(slide, x, y, w, label, value, opts = {}) {
  addPanel(slide, x, y, w, 0.74, {
    fill: opts.fillColor ?? theme.softBlue,
    line: opts.lineColor ?? theme.softBlueBorder,
  });
  slide.addText(label, {
    x: x + 0.12,
    y: y + 0.10,
    w: w - 0.24,
    h: 0.12,
    fontFace: theme.bodyFont,
    fontSize: 8.2,
    color: theme.subInk,
    bold: true,
    margin: 0,
  });
  slide.addText(value, {
    x: x + 0.12,
    y: y + 0.26,
    w: w - 0.24,
    h: 0.26,
    fontFace: theme.titleFont,
    fontSize: 16,
    color: opts.valueColor ?? theme.accent,
    bold: true,
    margin: 0,
  });
}

function addParagraph(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x,
    y,
    w,
    h,
    fontFace: opts.fontFace ?? theme.bodyFont,
    fontSize: opts.fontSize ?? 10.5,
    color: opts.color ?? theme.subInk,
    margin: 0,
    valign: opts.valign ?? "top",
  });
}

function addBulletList(slide, lines, x, y, w, h, opts = {}) {
  const runs = [];
  lines.forEach((line) => {
    runs.push({
      text: line,
      options: {
        bullet: { indent: 12 },
        breakLine: true,
      },
    });
  });
  slide.addText(runs, {
    x,
    y,
    w,
    h,
    fontFace: opts.fontFace ?? theme.bodyFont,
    fontSize: opts.fontSize ?? 10,
    color: opts.color ?? theme.ink,
    margin: 0,
    breakLine: false,
    valign: "top",
  });
}

function addMonoList(slide, lines, x, y, w, h) {
  slide.addText(lines.join("\n"), {
    x,
    y,
    w,
    h,
    fontFace: theme.monoFont,
    fontSize: 9.2,
    color: theme.subInk,
    margin: 0,
    valign: "top",
  });
}

function addDashedPlaceholder(slide, x, y, w, h, title, subtitle) {
  slide.addShape("roundRect", {
    x,
    y,
    w,
    h,
    rectRadius: 0.12,
    line: { color: theme.softBlueBorder, width: 1.2, dash: "dash" },
    fill: { color: "FFFFFF", transparency: 100 },
  });
  slide.addText(title, {
    x: x + 0.28,
    y: y + 0.26,
    w: w - 0.56,
    h: 0.22,
    fontFace: theme.bodyFont,
    fontSize: 12,
    color: theme.ink,
    bold: true,
    margin: 0,
    align: "center",
  });
  slide.addText(subtitle, {
    x: x + 0.28,
    y: y + 0.64,
    w: w - 0.56,
    h: 0.28,
    fontFace: theme.bodyFont,
    fontSize: 10.6,
    color: theme.subInk,
    margin: 0,
    align: "center",
  });
}

function addFooter(slide, text) {
  if (!text) {
    return;
  }
  slide.addText(text, {
    x: 0.82,
    y: 7.08,
    w: 7.0,
    h: 0.12,
    fontFace: theme.bodyFont,
    fontSize: 8.7,
    color: theme.subInk,
    margin: 0,
  });
}

function validateSlide(slide, pptx) {
  warnIfSlideHasOverlaps(slide, pptx, {
    ignoreLines: true,
    ignoreDecorativeShapes: true,
    muteContainment: true,
  });
  warnIfSlideElementsOutOfBounds(slide, pptx);
}

function addCoverSlide(pptx, pageNo) {
  const slide = pptx.addSlide();
  addBackground(slide);
  addChrome(slide, pageNo);
  slide.addShape("rect", {
    x: 8.78,
    y: 0.82,
    w: 4.55,
    h: 6.68,
    line: { color: theme.wash, transparency: 100 },
    fill: { color: theme.wash },
  });
  addChip(slide, "PERSONAL SLIDE TEMPLATE", 0.82, 0.58, 2.9);
  slide.addText("[Cover headline]", {
    x: 0.82,
    y: 1.48,
    w: 6.9,
    h: 1.05,
    fontFace: theme.titleFont,
    fontSize: 27,
    color: theme.ink,
    bold: true,
    margin: 0,
  });
  addParagraph(
    slide,
    "[Subtitle or one-paragraph framing.]",
    0.82,
    2.70,
    5.9,
    0.62,
    { fontSize: 11.4 }
  );
  addMetricChip(slide, 0.82, 4.18, 2.1, "[Chip A]", "[Value]", {
    lineColor: theme.softBlueBorder,
    fillColor: theme.softBlue,
    valueColor: theme.accent,
  });
  addMetricChip(slide, 3.08, 4.18, 2.1, "[Chip B]", "[Value]", {
    lineColor: theme.softBlueBorder,
    fillColor: theme.softBlue,
    valueColor: theme.accent,
  });
  addMetricChip(slide, 5.34, 4.18, 2.1, "[Chip C]", "[Value]", {
    lineColor: theme.softBlueBorder,
    fillColor: theme.softBlue,
    valueColor: theme.accent,
  });
  addPanel(slide, 9.15, 1.60, 3.1, 4.8);
  addPanelTitle(slide, 9.48, 1.92, 2.3, "[Default structure]");
  addBulletList(
    slide,
    [
      "[Headline claim]",
      "[One clean figure]",
      "[Three takeaways]",
      "[Compact confidence note]",
      "[Minimal detail on-slide]",
    ],
    9.42,
    2.24,
    2.35,
    1.56,
    { fontSize: 9.7 }
  );
  addParagraph(
    slide,
    "[Optional footer note / use case.]",
    9.48,
    5.44,
    2.2,
    0.7,
    { fontSize: 9.2 }
  );
  addFooter(slide, "Template page: cover");
  validateSlide(slide, pptx);
}

function addSectionDividerSlide(pptx, pageNo) {
  const slide = pptx.addSlide();
  addBackground(slide);
  addChrome(slide, pageNo);
  addChip(slide, "SECTION DIVIDER");
  slide.addShape("roundRect", {
    x: 0.82,
    y: 1.88,
    w: 7.4,
    h: 3.62,
    rectRadius: 0.16,
    line: { color: theme.softBlueBorder, width: 1.1 },
    fill: { color: theme.softBlue },
  });
  slide.addText("[Section title]", {
    x: 1.12,
    y: 2.42,
    w: 6.3,
    h: 0.7,
    fontFace: theme.titleFont,
    fontSize: 28,
    color: theme.ink,
    bold: true,
    margin: 0,
  });
  addParagraph(
    slide,
    "[Use this page to reset context before a new block of content.]",
    1.12,
    3.36,
    5.9,
    0.6,
    { fontSize: 11.2, color: theme.subInk }
  );
  addPanel(slide, 8.58, 1.88, 3.68, 3.62, { fill: "FFFFFF" });
  addPanelTitle(slide, 8.88, 2.18, 2.8, "[Quick notes]");
  addBulletList(
    slide,
    ["[Context]", "[Goal]", "[Key question]"],
    8.84,
    2.56,
    2.9,
    1.2,
    { fontSize: 10 }
  );
  addFooter(slide, "Template page: section divider");
  validateSlide(slide, pptx);
}

function addEvidencePageSlide(pptx, pageNo) {
  const slide = pptx.addSlide();
  addBackground(slide);
  addChrome(slide, pageNo);
  addTitle(
    slide,
    "Template",
    "[Slide title]",
    "",
    { titleSize: 22, subtitleW: 9.2, w: 10.6 }
  );
  slide.addText("Evidence page", {
    x: 11.55,
    y: 0.72,
    w: 0.95,
    h: 0.14,
    fontFace: theme.bodyFont,
    fontSize: 8.5,
    color: theme.accent,
    bold: true,
    align: "right",
    margin: 0,
  });

  addPanel(slide, 0.82, 1.52, 7.65, 4.95);
  addDashedPlaceholder(
    slide,
    1.06,
    1.80,
    7.20,
    4.34,
    "[Large visual area]",
    "[Plot / image / table / screenshot]"
  );

  addPanel(slide, 8.82, 1.52, 3.68, 1.42);
  addPanelTitle(slide, 9.12, 1.80, 2.6, "[Setup]");
  addBulletList(
    slide,
    ["[Knob / sweep]", "[Fixed inputs]", "[Conditions]"],
    9.08,
    2.10,
    2.94,
    0.56,
    { fontSize: 9.5 }
  );

  addPanel(slide, 8.82, 3.12, 3.68, 1.42);
  addPanelTitle(slide, 9.12, 3.40, 2.6, "[Interpretation]");
  addBulletList(
    slide,
    ["[Observed trend]", "[Interpretation]", "[Conclusion]"],
    9.08,
    3.70,
    2.94,
    0.56,
    { fontSize: 9.5 }
  );

  addPanel(slide, 8.82, 4.72, 3.68, 1.75, { fill: "F7F4EE" });
  addPanelTitle(slide, 9.12, 5.00, 2.6, "[Credibility]");
  addMetricChip(slide, 9.12, 5.35, 1.0, "V", "[ ]", {
    lineColor: theme.okBorder,
    fillColor: theme.okSoft,
    valueColor: "2D8A63",
  });
  addMetricChip(slide, 10.20, 5.35, 1.0, "SV", "[ ]", {
    lineColor: theme.warnBorder,
    fillColor: theme.warnSoft,
    valueColor: "C88719",
  });
  addMetricChip(slide, 11.28, 5.35, 1.0, "VAL", "[ ]", {
    lineColor: theme.failBorder,
    fillColor: theme.failSoft,
    valueColor: "C55C5C",
  });

  addFooter(slide, "Template page: evidence layout");
  validateSlide(slide, pptx);
}

function addStructureSlide(pptx, pageNo) {
  const slide = pptx.addSlide();
  const top = 2.12;
  addBackground(slide);
  addChrome(slide, pageNo);
  addTitle(slide, "Template", "[Structure slide]", "[Use for one subsystem or one concept.]", {
    titleSize: 21,
    subtitleW: 9.8,
  });

  addPanel(slide, 0.82, top, 3.44, 1.54, { fill: "F7F4EE" });
  addPanelTitle(slide, 1.08, top + 0.26, 2.8, "[Knobs / inputs]");
  addMonoList(slide, ["[Item 1]", "[Item 2]", "[Item 3]"], 1.08, top + 0.58, 2.8, 0.76);

  addPanel(slide, 0.82, top + 1.72, 3.44, 1.74);
  addPanelTitle(slide, 1.08, top + 1.98, 2.8, "[Primary view]");
  addParagraph(slide, "[Matrix, metric, or observable]", 1.08, top + 2.30, 2.96, 0.84);

  addPanel(slide, 4.5, top, 3.76, 3.46);
  addPanelTitle(slide, 4.78, top + 0.26, 3.0, "[Expected response]");
  addBulletList(
    slide,
    ["[Trend 1]", "[Trend 2]", "[Trend 3]"],
    4.72,
    top + 0.60,
    3.16,
    1.2,
    { fontSize: 10 }
  );
  addPanelTitle(slide, 4.78, top + 2.36, 3.0, "[Pass signals]");
  addBulletList(
    slide,
    ["[Signal 1]", "[Signal 2]", "[Signal 3]"],
    4.72,
    top + 2.68,
    3.16,
    0.78,
    { fontSize: 10 }
  );

  addPanel(slide, 8.52, top, 4.0, 3.46, { fill: "F7F4EE" });
  addDashedPlaceholder(
    slide,
    8.76,
    top + 0.26,
    3.52,
    2.98,
    "[Visual / notes area]",
    "[Paste plot, figure, or supporting note]"
  );

  addFooter(slide, "Template page: subsystem / concept layout");
  validateSlide(slide, pptx);
}

function addComparisonSlide(pptx, pageNo) {
  const slide = pptx.addSlide();
  const top = 2.10;
  addBackground(slide);
  addChrome(slide, pageNo);
  addTitle(slide, "Template", "[Comparison / interface slide]", "[Use for pairwise comparisons, before/after, or alternatives.]", {
    titleSize: 20.5,
    subtitleW: 10.0,
  });

  addPanel(slide, 0.82, top, 3.6, 1.3, { fill: "F7F4EE" });
  addPanelTitle(slide, 1.08, top + 0.24, 2.8, "[Controls]");
  addMonoList(slide, ["[Knob 1]", "[Knob 2]", "[Knob 3]"], 1.08, top + 0.54, 3.0, 0.56);

  addPanel(slide, 0.82, top + 1.48, 3.6, 2.0);
  addPanelTitle(slide, 1.08, top + 1.74, 2.8, "[Primary view]");
  addParagraph(slide, "[Matrix, chart, or table reference]", 1.08, top + 2.06, 3.0, 0.9);

  addPanel(slide, 4.64, top, 3.82, 3.48);
  addPanelTitle(slide, 4.92, top + 0.24, 3.0, "[Expected / key differences]");
  addBulletList(
    slide,
    ["[Point 1]", "[Point 2]", "[Point 3]"],
    4.86,
    top + 0.56,
    3.2,
    1.24,
    { fontSize: 10 }
  );
  addPanelTitle(slide, 4.92, top + 2.36, 3.0, "[Risks / failure signs]");
  addBulletList(
    slide,
    ["[Risk 1]", "[Risk 2]", "[Risk 3]"],
    4.86,
    top + 2.68,
    3.2,
    0.8,
    { fontSize: 10 }
  );

  addPanel(slide, 8.68, top, 3.84, 3.48, { fill: "F7F4EE" });
  addDashedPlaceholder(
    slide,
    8.92,
    top + 0.24,
    3.36,
    3.0,
    "[Comparison visual]",
    "[Overlay plot / chart / image pair]"
  );

  addFooter(slide, "Template page: comparison / interface layout");
  validateSlide(slide, pptx);
}

function addDiagramSlide(pptx, pageNo) {
  const slide = pptx.addSlide();
  addBackground(slide);
  addChrome(slide, pageNo);
  addTitle(slide, "Template", "[Diagram / topology slide]", "[Use for architecture, topology, or system sketches.]", {
    titleSize: 22,
    subtitleW: 9.8,
  });

  slide.addShape("roundRect", {
    x: 0.82,
    y: 2.08,
    w: 12.02,
    h: 4.86,
    rectRadius: 0.16,
    line: { color: theme.softBlueBorder, width: 1.1 },
    fill: { color: theme.softBlue },
  });
  slide.addText("[Diagram placeholder]", {
    x: 1.08,
    y: 2.26,
    w: 3.0,
    h: 0.24,
    fontFace: theme.titleFont,
    fontSize: 14,
    color: theme.ink,
    bold: true,
    margin: 0,
  });
  addDashedPlaceholder(
    slide,
    1.12,
    2.86,
    10.8,
    3.32,
    "[Insert diagram / topology / sketch]",
    "[Optional arrows, labels, or annotations]"
  );
  addParagraph(slide, "[Optional bottom note]", 1.08, 6.38, 5.0, 0.24, {
    fontSize: 9.8,
  });

  addFooter(slide, "Template page: diagram canvas");
  validateSlide(slide, pptx);
}

function addMatrixSlide(pptx, pageNo) {
  const slide = pptx.addSlide();
  addBackground(slide);
  addChrome(slide, pageNo);
  addTitle(slide, "Template", "[Matrix / table slide]", "[Use for inventories, scorecards, checklists, or comparisons.]", {
    titleSize: 22,
    subtitleW: 9.8,
  });

  addPanel(slide, 0.82, 2.08, 8.14, 4.8);
  addPanelTitle(slide, 1.08, 2.34, 3.8, "[Table / matrix area]");
  addDashedPlaceholder(
    slide,
    1.08,
    2.72,
    7.62,
    3.86,
    "[Insert table / matrix]",
    "[Rows, columns, and status indicators]"
  );

  addPanel(slide, 9.18, 2.08, 3.34, 4.8, { fill: "F7F4EE" });
  addPanelTitle(slide, 9.44, 2.34, 2.5, "[Notes]");
  addBulletList(
    slide,
    ["[Legend]", "[How to read]", "[Key takeaway]", "[Next step]"],
    9.40,
    2.72,
    2.5,
    1.44,
    { fontSize: 10 }
  );
  addPanelTitle(slide, 9.44, 5.12, 2.5, "[Optional fields]");
  addMonoList(slide, ["[Field 1]", "[Field 2]", "[Field 3]"], 9.44, 5.46, 2.3, 0.7);

  addFooter(slide, "Template page: matrix / table layout");
  validateSlide(slide, pptx);
}

function addSummarySlide(pptx, pageNo) {
  const slide = pptx.addSlide();
  addBackground(slide);
  addChrome(slide, pageNo);
  slide.addText("[Executive summary structure]", {
    x: 0.82,
    y: 0.68,
    w: 6.2,
    h: 0.34,
    fontFace: theme.titleFont,
    fontSize: 20,
    bold: true,
    color: theme.ink,
    margin: 0,
  });
  slide.addText("[Best when you need to land a decision, not narrate every intermediate step.]", {
    x: 0.82,
    y: 1.06,
    w: 6.0,
    h: 0.26,
    fontFace: theme.bodyFont,
    fontSize: 9.8,
    color: theme.subInk,
    margin: 0,
  });

  const cards = [
    { x: 0.82, label: "[Claim]" },
    { x: 3.92, label: "[Evidence]" },
    { x: 7.02, label: "[Failure mode]" },
    { x: 10.12, label: "[Decision]" },
  ];
  cards.forEach((card) => {
    addPanel(slide, card.x, 1.78, 2.72, 2.0);
    slide.addShape("rect", {
      x: card.x,
      y: 1.78,
      w: 2.72,
      h: 0.18,
      line: { color: theme.accent, transparency: 100 },
      fill: { color: theme.accent },
    });
    slide.addText(card.label, {
      x: card.x + 0.24,
      y: 2.08,
      w: 2.0,
      h: 0.18,
      fontFace: theme.bodyFont,
      fontSize: 10.9,
      color: theme.ink,
      bold: true,
      margin: 0,
    });
    slide.addText("[Short prompt / note]", {
      x: card.x + 0.24,
      y: 2.44,
      w: 2.18,
      h: 0.84,
      fontFace: theme.bodyFont,
      fontSize: 9.4,
      color: theme.subInk,
      margin: 0,
    });
  });

  addPanel(slide, 0.82, 4.28, 7.15, 2.08);
  addPanelTitle(slide, 1.08, 4.56, 3.2, "[Summary visual]");
  addDashedPlaceholder(
    slide,
    1.08,
    4.94,
    6.60,
    1.12,
    "[Insert compact visual]",
    "[Matrix / scorecard / summary chart]"
  );

  addPanel(slide, 8.20, 4.28, 4.3, 2.08, { fill: "F7F4EE" });
  addPanelTitle(slide, 8.50, 4.56, 2.7, "[Tradeoff]");
  addParagraph(
    slide,
    "[Add the main tradeoff, caveat, or scope boundary here.]",
    8.50,
    4.92,
    3.2,
    0.82,
    { fontSize: 9.5 }
  );

  addFooter(slide, "Template page: executive summary");
  validateSlide(slide, pptx);
}

function buildDeck() {
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "Codex";
  pptx.company = "OpenAI";
  pptx.subject = "Personal slide template deck";
  pptx.title = "QECA Personal Slide Template";
  pptx.lang = "en-US";

  let pageNo = 1;
  addCoverSlide(pptx, pageNo++);
  addSectionDividerSlide(pptx, pageNo++);
  addEvidencePageSlide(pptx, pageNo++);
  addStructureSlide(pptx, pageNo++);
  addComparisonSlide(pptx, pageNo++);
  addDiagramSlide(pptx, pageNo++);
  addMatrixSlide(pptx, pageNo++);
  addSummarySlide(pptx, pageNo++);
  return pptx;
}

async function main() {
  ensureDir(OUT_DIR);
  const outPath = path.join(OUT_DIR, "qeca_personal_slide_template.pptx");
  const pptx = buildDeck();
  await pptx.writeFile({ fileName: outPath });
  console.log(`Wrote ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
