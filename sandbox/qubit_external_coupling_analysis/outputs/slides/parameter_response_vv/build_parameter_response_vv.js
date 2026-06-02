const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const PptxGenJS = require("pptxgenjs");
const {
  warnIfSlideHasOverlaps,
  warnIfSlideElementsOutOfBounds,
} = require("./pptxgenjs_helpers/layout");

const OUT_DIR = path.join(__dirname, "output");
const ASSET_DIR = path.join(OUT_DIR, "generated_assets");
const SLIDE_W = 13.333;
const SLIDE_H = 7.5;

const theme = {
  bg: "FBFAF7",
  panel: "FFFFFF",
  sidebarWash: "F1EEE7",
  ink: "10233A",
  subInk: "667487",
  border: "DDD9CF",
  grid: "ECE8E0",
  accent: "2563EB",
  primarySoft: "EAF1FF",
  primaryBorder: "BED1F9",
  ok: "2D8A63",
  okSoft: "ECF7F1",
  okBorder: "B7DDCA",
  warn: "C88719",
  warnSoft: "FFF5E5",
  warnBorder: "F0D49D",
  fail: "C55C5C",
  failSoft: "FDEEEE",
  failBorder: "EABDBD",
  titleFont: "Avenir Next",
  bodyFont: "Avenir Next",
  monoFont: "Menlo",
};

const structureSlides = [
  {
    eyebrow: "Subsystem",
    title: "Qubit",
    subtitle: "[Add one-line framing for this structure.]",
    knobs: ["[Parameter 1]", "[Parameter 2]", "[Parameter 3]"],
    matrixView: "[Add primary matrix / observable for this structure.]",
    expected: ["[Expected response 1]", "[Expected response 2]", "[Expected response 3]"],
    goodSigns: ["[Pass signal 1]", "[Pass signal 2]", "[Pass signal 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
  {
    eyebrow: "Subsystem",
    title: "Readout Resonator",
    subtitle: "[Add one-line framing for this structure.]",
    knobs: ["[Parameter 1]", "[Parameter 2]", "[Parameter 3]"],
    matrixView: "[Add primary matrix / observable for this structure.]",
    expected: ["[Expected response 1]", "[Expected response 2]", "[Expected response 3]"],
    goodSigns: ["[Pass signal 1]", "[Pass signal 2]", "[Pass signal 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
  {
    eyebrow: "Subsystem",
    title: "XY Line",
    subtitle: "[Add one-line framing for this structure.]",
    knobs: ["[Parameter 1]", "[Parameter 2]", "[Parameter 3]"],
    matrixView: "[Add primary matrix / observable for this structure.]",
    expected: ["[Expected response 1]", "[Expected response 2]", "[Expected response 3]"],
    goodSigns: ["[Pass signal 1]", "[Pass signal 2]", "[Pass signal 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
  {
    eyebrow: "Subsystem",
    title: "Readout Line With Purcell Filter",
    subtitle: "[Add one-line framing for this structure.]",
    knobs: ["[Parameter 1]", "[Parameter 2]", "[Parameter 3]"],
    matrixView: "[Add primary matrix / observable for this structure.]",
    expected: ["[Expected response 1]", "[Expected response 2]", "[Expected response 3]"],
    goodSigns: ["[Pass signal 1]", "[Pass signal 2]", "[Pass signal 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
];

const pairSlides = [
  {
    eyebrow: "Interface",
    title: "Qubit ↔ XY Line",
    type: "Direct Interface",
    tone: "primary",
    knobs: ["[Controlling knob 1]", "[Controlling knob 2]", "[Controlling knob 3]"],
    matrixView: "[Add primary matrix / observable for this interface.]",
    expected: ["[Expected behavior 1]", "[Expected behavior 2]", "[Expected behavior 3]"],
    falsifiers: ["[Failure signature 1]", "[Failure signature 2]", "[Failure signature 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
  {
    eyebrow: "Interface",
    title: "Qubit ↔ Readout Resonator",
    type: "Direct Interface",
    tone: "primary",
    knobs: ["[Controlling knob 1]", "[Controlling knob 2]", "[Controlling knob 3]"],
    matrixView: "[Add primary matrix / observable for this interface.]",
    expected: ["[Expected behavior 1]", "[Expected behavior 2]", "[Expected behavior 3]"],
    falsifiers: ["[Failure signature 1]", "[Failure signature 2]", "[Failure signature 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
  {
    eyebrow: "Interface",
    title: "Readout Resonator ↔ Readout Line + Purcell Filter",
    type: "Direct Interface",
    tone: "primary",
    knobs: ["[Controlling knob 1]", "[Controlling knob 2]", "[Controlling knob 3]"],
    matrixView: "[Add primary matrix / observable for this interface.]",
    expected: ["[Expected behavior 1]", "[Expected behavior 2]", "[Expected behavior 3]"],
    falsifiers: ["[Failure signature 1]", "[Failure signature 2]", "[Failure signature 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
  {
    eyebrow: "Interface",
    title: "Qubit ↔ Readout Line + Purcell Filter",
    type: "Mediated Interface",
    tone: "warn",
    knobs: ["[Controlling knob 1]", "[Controlling knob 2]", "[Controlling knob 3]"],
    matrixView: "[Add primary matrix / observable for this interface.]",
    expected: ["[Expected behavior 1]", "[Expected behavior 2]", "[Expected behavior 3]"],
    falsifiers: ["[Failure signature 1]", "[Failure signature 2]", "[Failure signature 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
  {
    eyebrow: "Interface",
    title: "Readout Resonator ↔ XY Line",
    type: "Mediated Interface",
    tone: "warn",
    knobs: ["[Controlling knob 1]", "[Controlling knob 2]", "[Controlling knob 3]"],
    matrixView: "[Add primary matrix / observable for this interface.]",
    expected: ["[Expected behavior 1]", "[Expected behavior 2]", "[Expected behavior 3]"],
    falsifiers: ["[Failure signature 1]", "[Failure signature 2]", "[Failure signature 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
  {
    eyebrow: "Interface",
    title: "XY Line ↔ Readout Line + Purcell Filter",
    type: "Mediated Interface",
    tone: "warn",
    knobs: ["[Controlling knob 1]", "[Controlling knob 2]", "[Controlling knob 3]"],
    matrixView: "[Add primary matrix / observable for this interface.]",
    expected: ["[Expected behavior 1]", "[Expected behavior 2]", "[Expected behavior 3]"],
    falsifiers: ["[Failure signature 1]", "[Failure signature 2]", "[Failure signature 3]"],
    actualPrompt: "Paste plot, table, or notes here.",
  },
];

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function svgColor(value) {
  return value.startsWith("#") ? value : `#${value}`;
}

function rasterizeSvgToPng(svg, stem) {
  ensureDir(ASSET_DIR);
  const svgPath = path.join(ASSET_DIR, `${stem}.svg`);
  const pngPath = path.join(ASSET_DIR, `${stem}.png`);
  fs.writeFileSync(svgPath, svg);
  execFileSync("sips", ["-s", "format", "png", svgPath, "--out", pngPath], {
    stdio: "pipe",
  });
  return pngPath;
}

function addSvgImage(slide, stem, svg, x, y, w, h) {
  slide.addImage({
    path: rasterizeSvgToPng(svg, stem),
    x,
    y,
    w,
    h,
  });
}

function addFullBleedBackground(slide) {
  slide.background = { color: theme.bg };
}

function addPageChrome(slide, pageNo) {
  slide.addShape("rect", {
    x: 0,
    y: 0,
    w: SLIDE_W,
    h: 0.08,
    line: { color: theme.primaryBorder, transparency: 100 },
    fill: { color: theme.primaryBorder },
  });
  slide.addText(String(pageNo).padStart(2, "0"), {
    x: 12.28,
    y: 7.08,
    w: 0.34,
    h: 0.12,
    fontFace: theme.bodyFont,
    fontSize: 8.7,
    color: theme.subInk,
    margin: 0,
    align: "right",
  });
}

function addHeaderChip(slide, text, x = 0.82, y = 0.58, w = 2.85) {
  slide.addShape("roundRect", {
    x,
    y,
    w,
    h: 0.42,
    rectRadius: 0.09,
    line: { color: theme.primaryBorder, width: 1 },
    fill: { color: theme.primarySoft },
  });
  slide.addText(text, {
    x: x + 0.2,
    y: y + 0.11,
    w: w - 0.4,
    h: 0.16,
    fontFace: theme.bodyFont,
    fontSize: 9.2,
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
      w: opts.eyebrowW ?? 2.6,
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
    w: opts.w ?? 10.9,
    h: opts.h ?? 0.9,
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
      w: opts.subtitleW ?? 6.4,
      h: opts.subtitleH ?? 0.55,
      fontFace: theme.bodyFont,
      fontSize: 11,
      color: theme.subInk,
      margin: 0,
      valign: "top",
    });
  }
}

function addToneBadge(slide, text, tone, x, y) {
  const toneMap = {
    primary: { fill: theme.primarySoft, line: theme.primaryBorder, text: theme.accent },
    ok: { fill: theme.okSoft, line: theme.okBorder, text: theme.ok },
    warn: { fill: theme.warnSoft, line: theme.warnBorder, text: theme.warn },
    fail: { fill: theme.failSoft, line: theme.failBorder, text: theme.fail },
  };
  const resolved = toneMap[tone] ?? toneMap.primary;
  slide.addShape("roundRect", {
    x,
    y,
    w: 1.48,
    h: 0.34,
    rectRadius: 0.08,
    line: { color: resolved.line, width: 1 },
    fill: { color: resolved.fill },
  });
  slide.addText(text, {
    x,
    y: y + 0.09,
    w: 1.48,
    h: 0.12,
    fontFace: theme.bodyFont,
    fontSize: 8.8,
    color: resolved.text,
    bold: true,
    margin: 0,
    align: "center",
  });
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

function addParagraph(slide, text, x, y, w, h, opts = {}) {
  slide.addText(text, {
    x,
    y,
    w,
    h,
    fontFace: opts.fontFace ?? theme.bodyFont,
    fontSize: opts.fontSize ?? 10.6,
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
    fontSize: opts.fontSize ?? 10.3,
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

function addPlaceholder(slide, x, y, w, h, prompt) {
  slide.addShape("roundRect", {
    x,
    y,
    w,
    h,
    rectRadius: 0.12,
    line: { color: theme.primaryBorder, width: 1.2, dash: "dash" },
    fill: { color: "FFFFFF", transparency: 100 },
  });
  slide.addText("[Plot / notes area]", {
    x: x + 0.24,
    y: y + 0.24,
    w: w - 0.48,
    h: 0.18,
    fontFace: theme.bodyFont,
    fontSize: 11,
    color: theme.ink,
    bold: true,
    margin: 0,
  });
  addParagraph(slide, prompt, x + 0.24, y + 0.56, w - 0.48, 0.55, {
    fontSize: 10.2,
    color: theme.subInk,
  });
  slide.addText("[Optional checklist]", {
    x: x + 0.24,
    y: y + 1.28,
    w: w - 0.48,
    h: 0.16,
    fontFace: theme.bodyFont,
    fontSize: 9.7,
    color: theme.accent,
    bold: true,
    margin: 0,
  });
  addBulletList(
    slide,
    [
      "[Add visual 1]",
      "[Add visual 2]",
      "[Add short takeaway]",
    ],
    x + 0.22,
    y + 1.52,
    w - 0.44,
    1.12,
    { fontSize: 9.5 }
  );
}

function addFooter(slide, text) {
  if (!text) {
    return;
  }
  slide.addText(text, {
    x: 0.82,
    y: 7.08,
    w: 6.5,
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

function makeTopologySvg() {
  const bg = svgColor(theme.panel);
  const ink = svgColor(theme.ink);
  const subInk = svgColor(theme.subInk);
  const border = svgColor(theme.border);
  const width = 1180;
  const height = 540;

  return `
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" rx="28" fill="${svgColor(theme.primarySoft)}"/>
    <rect x="86" y="86" width="1008" height="366" rx="24" fill="${bg}" stroke="${border}" stroke-width="2" stroke-dasharray="12 10"/>
    <text x="590" y="210" text-anchor="middle" font-family="${theme.bodyFont}" font-size="34" font-weight="700" fill="${ink}">[Insert topology / structure diagram]</text>
    <text x="590" y="258" text-anchor="middle" font-family="${theme.bodyFont}" font-size="22" fill="${subInk}">[Optional labels, paths, or coupling annotations]</text>
    <text x="70" y="34" font-family="${theme.bodyFont}" font-size="22" font-weight="700" fill="${ink}">Diagram placeholder</text>
    <text x="70" y="490" font-family="${theme.bodyFont}" font-size="18" fill="${subInk}">Use this area for the system topology, simplified netlist, or path sketch.</text>
  </svg>`;
}

function makePairwiseMatrixSvg() {
  const width = 1180;
  const height = 520;
  const ink = svgColor(theme.ink);
  const subInk = svgColor(theme.subInk);
  const border = svgColor(theme.border);
  return `
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" rx="26" fill="#FFFFFF"/>
    <rect x="90" y="74" width="1000" height="360" rx="24" fill="#FFFFFF" stroke="${border}" stroke-width="2" stroke-dasharray="12 10"/>
    <text x="590" y="196" text-anchor="middle" font-family="${theme.bodyFont}" font-size="34" font-weight="700" fill="${ink}">[Insert pairwise map / table]</text>
    <text x="590" y="244" text-anchor="middle" font-family="${theme.bodyFont}" font-size="22" fill="${subInk}">[Example: direct vs mediated, coverage, or audit ownership]</text>
    <text x="60" y="40" font-family="${theme.bodyFont}" font-size="22" font-weight="700" fill="${ink}">Inventory placeholder</text>
    <text x="60" y="${height - 24}" font-family="${theme.bodyFont}" font-size="18" fill="${subInk}">Use this area for a matrix, table, or audit map.</text>
  </svg>`;
}

function addSubsystemSlide(pptx, def, pageNo) {
  const slide = pptx.addSlide();
  const contentTop = 2.12;
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo);
  addTitle(slide, def.eyebrow, def.title, def.subtitle, {
    titleSize: 21,
    subtitleW: 10.8,
    subtitleH: 0.54,
  });

  addPanel(slide, 0.82, contentTop, 3.44, 1.54, { fill: "F7F4EE" });
  addPanelTitle(slide, 1.08, contentTop + 0.26, 2.8, "Knobs In This Study");
  addMonoList(slide, def.knobs, 1.08, contentTop + 0.58, 2.86, 0.78);

  addPanel(slide, 0.82, contentTop + 1.72, 3.44, 1.74);
  addPanelTitle(slide, 1.08, contentTop + 1.98, 2.8, "Primary Matrix View");
  addParagraph(slide, def.matrixView, 1.08, contentTop + 2.30, 2.95, 0.9, {
    fontSize: 10.1,
  });

  addPanel(slide, 4.5, contentTop, 3.76, 3.46);
  addPanelTitle(slide, 4.78, contentTop + 0.26, 3.0, "Expected Qualitative Response");
  addBulletList(slide, def.expected, 4.72, contentTop + 0.60, 3.18, 1.56, {
    fontSize: 9.9,
  });
  addPanelTitle(slide, 4.78, contentTop + 2.38, 3.0, "What Counts As A Good Sign");
  addBulletList(slide, def.goodSigns, 4.72, contentTop + 2.72, 3.18, 0.84, {
    fontSize: 9.8,
  });

  addPanel(slide, 8.52, contentTop, 4.0, 3.46, { fill: "F7F4EE" });
  addPlaceholder(slide, 8.74, contentTop + 0.26, 3.56, 2.98, def.actualPrompt);

  addFooter(slide, "");
  validateSlide(slide, pptx);
}

function addPairSlide(pptx, def, pageNo) {
  const slide = pptx.addSlide();
  const contentTop = 2.10;
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo);
  addTitle(slide, def.eyebrow, def.title, "[Add one-line framing for this interface.]", {
    titleSize: 20.5,
    subtitleW: 10.7,
  });
  addToneBadge(slide, def.type, def.tone, 10.88, 0.62);

  addPanel(slide, 0.82, contentTop, 3.6, 1.3, { fill: "F7F4EE" });
  addPanelTitle(slide, 1.08, contentTop + 0.24, 2.8, "Controlling Knobs");
  addMonoList(slide, def.knobs, 1.08, contentTop + 0.54, 3.0, 0.6);

  addPanel(slide, 0.82, contentTop + 1.48, 3.6, 2.0);
  addPanelTitle(slide, 1.08, contentTop + 1.74, 2.8, "Primary Matrix View");
  addParagraph(slide, def.matrixView, 1.08, contentTop + 2.06, 3.0, 1.1, {
    fontSize: 10.1,
  });

  addPanel(slide, 4.64, contentTop, 3.82, 3.48);
  addPanelTitle(slide, 4.92, contentTop + 0.24, 3.0, "Expected Behavior");
  addBulletList(slide, def.expected, 4.86, contentTop + 0.56, 3.22, 1.3, {
    fontSize: 9.9,
  });
  addPanelTitle(slide, 4.92, contentTop + 2.36, 3.0, "If This Fails, Suspect");
  addBulletList(slide, def.falsifiers, 4.86, contentTop + 2.68, 3.22, 0.8, {
    fontSize: 9.8,
  });

  addPanel(slide, 8.68, contentTop, 3.84, 3.48, { fill: "F7F4EE" });
  addPlaceholder(slide, 8.92, contentTop + 0.24, 3.36, 3.0, def.actualPrompt);

  addFooter(slide, "");
  validateSlide(slide, pptx);
}

function buildDeck() {
  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.author = "Codex";
  pptx.company = "OpenAI";
  pptx.subject = "QECA parameter-response V&V report";
  pptx.title = "QECA Parameter-Response Verification Report";
  pptx.lang = "en-US";

  let pageNo = 1;

  let slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  slide.addShape("rect", {
    x: 8.82,
    y: 0.82,
    w: 4.51,
    h: 6.68,
    line: { color: theme.sidebarWash, transparency: 100 },
    fill: { color: theme.sidebarWash },
  });
  addHeaderChip(slide, "REPORT TEMPLATE");
  slide.addText("[Report title]", {
    x: 0.82,
    y: 1.44,
    w: 7.0,
    h: 1.1,
    fontFace: theme.titleFont,
    fontSize: 27,
    color: theme.ink,
    bold: true,
    margin: 0,
  });
  addParagraph(
    slide,
    "[Add subtitle, scope, or one-paragraph framing here.]",
    0.82,
    2.72,
    6.2,
    0.95,
    { fontSize: 11.4 }
  );
  addPanel(slide, 9.18, 1.54, 3.08, 4.88);
  addPanelTitle(slide, 9.48, 1.88, 2.4, "[Section list]");
  addBulletList(
    slide,
    [
      "[Section 1]",
      "[Section 2]",
      "[Section 3]",
      "[Section 4]",
    ],
    9.42,
    2.22,
    2.42,
    1.6,
    { fontSize: 9.8 }
  );
  addParagraph(
    slide,
    "[Optional notes / metadata]",
    9.48,
    5.24,
    2.2,
    0.8,
    { fontSize: 9.5 }
  );
  addFooter(slide, "");
  validateSlide(slide, pptx);

  slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  addTitle(slide, "Method", "[Method / framework slide]", "[Add method summary or leave blank.]", {
    titleSize: 22,
    subtitleW: 8.6,
  });
  const methodCards = [
    {
      x: 0.82,
      title: "1. Verification",
      text: "[Add criterion]",
      fill: "EAF1FF",
      line: "BED1F9",
      tone: "2563EB",
    },
    {
      x: 4.38,
      title: "2. Solution Verification",
      text: "[Add criterion]",
      fill: "FFF5E5",
      line: "F0D49D",
      tone: "C88719",
    },
    {
      x: 7.94,
      title: "3. Validation",
      text: "[Add criterion]",
      fill: "ECF7F1",
      line: "B7DDCA",
      tone: "2D8A63",
    },
  ];
  methodCards.forEach((card) => {
    addPanel(slide, card.x, 2.22, 3.02, 2.24, { fill: card.fill, line: card.line });
    slide.addText(card.title, {
      x: card.x + 0.24,
      y: 2.48,
      w: 2.32,
      h: 0.18,
      fontFace: theme.bodyFont,
      fontSize: 11.2,
      color: card.tone,
      bold: true,
      margin: 0,
    });
    addParagraph(slide, card.text, card.x + 0.24, 2.86, 2.4, 1.16, {
      fontSize: 10.2,
      color: theme.ink,
    });
  });
  addPanel(slide, 0.82, 4.82, 12.0, 1.58);
  addPanelTitle(slide, 1.08, 5.08, 4.0, "[Checklist / notes]");
  addBulletList(
    slide,
    [
      "[Item 1]",
      "[Item 2]",
      "[Item 3]",
    ],
    1.02,
    5.36,
    10.9,
    0.7,
    { fontSize: 10.2 }
  );
  addFooter(slide, "");
  validateSlide(slide, pptx);

  slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  addTitle(slide, "Topology", "[Topology / diagram slide]", "[Add context or leave blank.]", {
    titleSize: 22,
    subtitleW: 10.9,
  });
  addSvgImage(slide, "topology_map", makeTopologySvg(), 0.82, 2.14, 11.92, 4.76);
  addFooter(slide, "");
  validateSlide(slide, pptx);

  slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  addTitle(slide, "Inventory", "[Inventory / matrix slide]", "[Add context or leave blank.]", {
    titleSize: 22,
    subtitleW: 9.8,
  });
  addSvgImage(slide, "pairwise_matrix", makePairwiseMatrixSvg(), 0.82, 2.08, 11.9, 4.62);
  addFooter(slide, "");
  validateSlide(slide, pptx);

  structureSlides.forEach((def) => addSubsystemSlide(pptx, def, pageNo++));
  pairSlides.forEach((def) => addPairSlide(pptx, def, pageNo++));

  slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  addTitle(slide, "Execution", "[Execution / appendix slide]", "[Add instructions or leave blank.]", {
    titleSize: 22,
    subtitleW: 9.2,
  });
  addPanel(slide, 0.82, 2.10, 5.9, 4.44);
  addPanelTitle(slide, 1.08, 2.36, 4.0, "[Left panel title]");
  addBulletList(
    slide,
    [
      "[Item 1]",
      "[Item 2]",
      "[Item 3]",
      "[Item 4]",
    ],
    1.02,
    2.72,
    5.1,
    1.3,
    { fontSize: 10.2 }
  );
  addPanelTitle(slide, 1.08, 4.86, 4.0, "[Table / fields]");
  addMonoList(
    slide,
    [
      "[Field 1]",
      "[Field 2]",
      "[Field 3]",
      "[Field 4]",
      "[Field 5]",
    ],
    1.08,
    5.18,
    3.3,
    1.06
  );
  addPanel(slide, 7.0, 2.10, 5.52, 4.44, { fill: "F7F4EE" });
  addPanelTitle(slide, 7.28, 2.36, 3.8, "[Right panel title]");
  addBulletList(
    slide,
    [
      "[Item 1]",
      "[Item 2]",
      "[Item 3]",
      "[Item 4]",
      "[Item 5]",
    ],
    7.22,
    2.72,
    4.75,
    1.62,
    { fontSize: 10.0 }
  );
  addPanelTitle(slide, 7.28, 5.06, 3.8, "[Decision / notes]");
  addParagraph(
    slide,
    "[Add final note or rule.]",
    7.28,
    5.36,
    4.7,
    0.66,
    { fontSize: 10.3, color: theme.ink }
  );
  addFooter(slide, "");
  validateSlide(slide, pptx);

  return pptx;
}

async function main() {
  ensureDir(OUT_DIR);
  const outPath = path.join(OUT_DIR, "qeca_parameter_response_vv_report.pptx");
  const pptx = buildDeck();
  await pptx.writeFile({ fileName: outPath });
  console.log(`Wrote ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 1;
});
