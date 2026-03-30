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
    subtitle:
      "Treat the qubit as the reference oscillator. This is where monotonicity checks should be easiest and where nonphysical loss should be easiest to spot.",
    knobs: [
      "l_q_h",
      "c_q_f",
      "c_g1_f, c_g2_f",
      "qubit_port_res_ohm",
    ],
    matrixView:
      "Primary observable: reduced Ydm,in(ω), extracted fq from Im(Ydm,in)=0, and Re(Ydm,in) at resonance.",
    expected: [
      "Lq up should move fq down.",
      "Cq or pad-to-ground capacitance up should move fq down.",
      "With c_xy = c_rq = 0, Re(Ydm,in) should stay small and smooth.",
      "Pad asymmetry should affect CM/DM weighting, not spawn unrelated resonances.",
    ],
    goodSigns: [
      "Zero crossing moves monotonically under parameter sweeps.",
      "Retuning the bare qubit does not suddenly create large loss.",
      "Frequency extraction is stable under sweep refinement.",
    ],
    actualPrompt:
      "Insert: Lq sweep, Im(Ydm,in) zero-crossing traces, and one isolated-qubit sanity plot.",
  },
  {
    eyebrow: "Subsystem",
    title: "Readout Resonator",
    subtitle:
      "In this study the readout resonator is the quarter-wave resonator branch coupled into the readout line through the coupled window.",
    knobs: [
      "qwr_length_m",
      "common_l_per_m_h, common_c_per_m_f",
      "common_r_per_m_ohm, common_g_per_m_s",
      "qwr_target_dz_m",
    ],
    matrixView:
      "Primary observable: readout-line S21, fitted resonator poles from vector fitting, and optional local Y before reduction.",
    expected: [
      "Longer electrical length should move the readout-resonator resonance lower.",
      "Changing common RLGC should shift distributed resonances consistently, not arbitrarily.",
      "If c_rq1 = c_rq2 = 0, retuning the resonator should not move the qubit result.",
      "Mesh refinement should converge mode locations instead of reordering them.",
    ],
    goodSigns: [
      "The narrower fitted resonance tracks the readout resonator consistently.",
      "Resonance motion follows electrical length intuition.",
      "The resonator disappears from qubit behavior when the qubit interface is opened.",
    ],
    actualPrompt:
      "Insert: qwr length sweep on S21 and fitted resonance markers with c_rq toggled on/off.",
  },
  {
    eyebrow: "Subsystem",
    title: "XY Line",
    subtitle:
      "Important modeling fact: in this study the XY lane is represented as a terminated XY node plus the qubit-to-XY coupling capacitors, not as a long distributed geometry block.",
    knobs: [
      "c_xy1_f, c_xy2_f",
      "xy_port_res_ohm",
      "common RLGC only matters indirectly here",
      "No independent XY length parameter in this model",
    ],
    matrixView:
      "Primary observable: port-3 loading in the full Y(ω) and its effect on reduced Ydm,in(ω).",
    expected: [
      "Increasing c_xy should strengthen the XY-only loading contribution.",
      "Setting c_xy1 = c_xy2 = 0 should collapse the XY contribution cleanly.",
      "Changing xy_port_res_ohm should alter dissipative loading but should not create readout resonances.",
      "Any claim about XY distributed standing-wave motion should be treated carefully because this model does not expose an XY length knob.",
    ],
    goodSigns: [
      "XY-only loss vanishes in the zero-coupling limit.",
      "XY trends are monotonic with c_xy sweeps.",
      "The study narrative stays aligned with what the model actually contains.",
    ],
    actualPrompt:
      "Insert: c_xy sweep, xy_port_res sweep, and one note explaining the XY node abstraction.",
  },
  {
    eyebrow: "Subsystem",
    title: "Readout Line With Purcell Filter",
    subtitle:
      "This is the distributed branch from readout input to output, including left line, half-wave Purcell filter, right line, and terminations.",
    knobs: [
      "left_readout_length_m, right_readout_length_m",
      "purcell_filter_length_m",
      "pf_coupling_cap_in_f, pf_coupling_cap_out_f",
      "readout_port_res_ohm",
      "left/right/pf target_dz_m",
    ],
    matrixView:
      "Primary observable: raw readout-line S21, fitted S21 model, and extracted Purcell-filter / readout-resonator resonances.",
    expected: [
      "Increasing electrical length should move the associated resonances or notches lower.",
      "Changing PF coupling capacitors should alter bandwidth and feature strength.",
      "Port termination changes should alter line response smoothly, not invent extra physics.",
      "Discretization refinement should stabilize S21 features and fitted poles.",
    ],
    goodSigns: [
      "The broader fitted feature tracks the Purcell-filter mode consistently.",
      "Mode motion is consistent with length scaling and coupling strength.",
      "The branch can be characterized cleanly even when qubit couplings are disabled.",
    ],
    actualPrompt:
      "Insert: S21 sweeps versus PF length and coupling-cap sweeps, plus vector-fitting overlays.",
  },
];

const pairSlides = [
  {
    eyebrow: "Interface",
    title: "Qubit ↔ XY Line",
    type: "Direct Interface",
    tone: "primary",
    knobs: ["c_xy1_f", "c_xy2_f", "xy_port_res_ohm"],
    matrixView: "Use reduced Ydm,in(ω) near qubit resonance plus selected full Y(ω) traces for port 3.",
    expected: [
      "Increasing c_xy should increase XY-only loading and usually increase Re(Ydm,in).",
      "c_xy imbalance changes the centroid weights w1 and w2, so asymmetry should show up systematically.",
      "Setting c_xy1 = c_xy2 = 0 should collapse to the no-XY reference.",
    ],
    falsifiers: [
      "Loss stays large even when c_xy is zero.",
      "fq moves in the opposite direction with stronger XY loading without another explanation.",
      "Random extra resonances appear when only c_xy is swept.",
    ],
    actualPrompt:
      "Insert: XY-only sweep panel with c_xy magnitude and imbalance variants.",
  },
  {
    eyebrow: "Interface",
    title: "Qubit ↔ Readout Resonator",
    type: "Direct Interface",
    tone: "primary",
    knobs: ["c_rq1_f", "c_rq2_f", "qwr_length_m (alignment context)"],
    matrixView: "Use reduced Ydm,in(ω) at the qubit plus S21 context from the readout branch.",
    expected: [
      "Increasing c_rq should strengthen readout-mediated frequency shift and loss.",
      "Tuning the resonator closer to the qubit should increase loading.",
      "Setting c_rq1 = c_rq2 = 0 should disconnect the qubit from the entire readout branch.",
    ],
    falsifiers: [
      "The qubit still feels the readout branch when c_rq is zero.",
      "Changing qwr length strongly affects the qubit with the interface opened.",
      "Observed shift and loss move incoherently under the same c_rq sweep.",
    ],
    actualPrompt:
      "Insert: c_rq sweep, qwr detuning sweep, and readout-off null check.",
  },
  {
    eyebrow: "Interface",
    title: "Readout Resonator ↔ Readout Line + Purcell Filter",
    type: "Direct Interface",
    tone: "primary",
    knobs: [
      "coupled_window_length_m",
      "coupled_window_input_mode",
      "q2d_* or modal even/odd parameters",
      "pf_window_start_m, qwr_window_start_m",
    ],
    matrixView: "Use raw S21, fitted S21 model, and extracted resonances from the readout branch.",
    expected: [
      "Longer or stronger coupled-window interaction should increase hybridization.",
      "Window length → 0 or mutual terms → 0 should decouple the resonator from the line.",
      "Modal and q2d parameterizations should agree qualitatively on trend direction.",
    ],
    falsifiers: [
      "The resonator feature does not respond to window strength at all.",
      "The line still shows strong resonator loading with the window effectively off.",
      "q2d and modal modes disagree on basic trend direction.",
    ],
    actualPrompt:
      "Insert: coupled-window length sweep, modal-vs-q2d comparison, and one decoupling limit plot.",
  },
  {
    eyebrow: "Interface",
    title: "Qubit ↔ Readout Line + Purcell Filter",
    type: "Mediated Interface",
    tone: "warn",
    knobs: [
      "No direct knob in this model",
      "Path toggles: c_rq*, coupled_window_length_m, PF branch lengths",
    ],
    matrixView: "Use reduced Ydm,in(ω) for the qubit and S21 for the readout branch as a path-consistency check.",
    expected: [
      "This effect must disappear if either the qubit↔resonator or resonator↔line interface is opened.",
      "Changing PF geometry with c_rq = 0 should not move the qubit result.",
      "The effect should look path-mediated, not like a brand-new direct capacitor.",
    ],
    falsifiers: [
      "PF changes move the qubit even with c_rq opened.",
      "The qubit responds as if there were a direct line coupling that is absent from the netlist.",
      "Path-breaking toggles do not suppress the effect.",
    ],
    actualPrompt:
      "Insert: PF sweep with c_rq on/off, plus one path-break comparison panel.",
  },
  {
    eyebrow: "Interface",
    title: "Readout Resonator ↔ XY Line",
    type: "Mediated Interface",
    tone: "warn",
    knobs: [
      "No direct knob in this model",
      "Path toggles: c_rq*, c_xy*",
    ],
    matrixView: "Use Ydm,in(ω) and selected full-matrix traces only as a mediated-effect null test.",
    expected: [
      "This interaction should exist only through the shared qubit network.",
      "Zeroing either c_rq or c_xy should kill the path.",
      "Any residual feature should be small and systematic, not dominant.",
    ],
    falsifiers: [
      "A strong RR↔XY effect remains after zeroing one side of the path.",
      "A new standalone feature appears that cannot be routed through the qubit.",
      "Trend magnitude is first-order when the topology only allows higher-order mediation.",
    ],
    actualPrompt:
      "Insert: c_xy / c_rq path-break matrix and one residual-effect summary.",
  },
  {
    eyebrow: "Interface",
    title: "XY Line ↔ Readout Line + Purcell Filter",
    type: "Mediated Interface",
    tone: "warn",
    knobs: [
      "No direct knob in this model",
      "Path toggles: c_xy*, c_rq*, coupled_window_length_m",
    ],
    matrixView: "Use Ydm,in(ω) and branch S21 only as a mediated consistency check.",
    expected: [
      "This is a second-order path through the qubit and resonator network.",
      "Zeroing c_xy or c_rq should collapse the interaction.",
      "Changing PF geometry alone should not change the XY-only reference case.",
    ],
    falsifiers: [
      "PF geometry changes alter XY-only behavior without the readout path engaged.",
      "The mediated effect is larger than the direct interfaces without a clear explanation.",
      "Path-breaking toggles fail to suppress the effect.",
    ],
    actualPrompt:
      "Insert: XY-only versus XY+RO comparison with explicit path toggles.",
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
  slide.addText("Actual behavior / plot slot", {
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
  slide.addText("Recommended inserts", {
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
      "One sweep plot with a monotonic knob on the x-axis",
      "One null-test or decoupling-limit comparison",
      "One sentence on whether the observed trend matches expectation",
    ],
    x + 0.22,
    y + 1.52,
    w - 0.44,
    1.12,
    { fontSize: 9.5 }
  );
}

function addFooter(slide, text) {
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
  const accent = svgColor(theme.accent);
  const primarySoft = svgColor(theme.primarySoft);
  const warn = svgColor(theme.warn);
  const width = 1180;
  const height = 540;

  function box(x, y, w, h, title, body) {
    return `
      <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="24" fill="${bg}" stroke="${border}" stroke-width="2"/>
      <text x="${x + 26}" y="${y + 42}" font-family="${theme.bodyFont}" font-size="28" font-weight="700" fill="${ink}">${title}</text>
      <text x="${x + 26}" y="${y + 78}" font-family="${theme.bodyFont}" font-size="19" fill="${subInk}">${body}</text>
    `;
  }

  function direct(x1, y1, x2, y2, label) {
    return `
      <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${accent}" stroke-width="6" stroke-linecap="round"/>
      <text x="${(x1 + x2) / 2 + 10}" y="${(y1 + y2) / 2 - 10}" font-family="${theme.bodyFont}" font-size="18" font-weight="700" fill="${accent}">${label}</text>
    `;
  }

  function mediated(x1, y1, x2, y2, label) {
    return `
      <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${warn}" stroke-width="4" stroke-linecap="round" stroke-dasharray="10 9"/>
      <text x="${(x1 + x2) / 2 + 12}" y="${(y1 + y2) / 2 - 10}" font-family="${theme.bodyFont}" font-size="16" font-weight="700" fill="${warn}">${label}</text>
    `;
  }

  return `
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" rx="28" fill="${primarySoft}"/>
    ${box(70, 88, 260, 122, "Qubit", "Bare mode + reduced Ydm,in")}
    ${box(70, 332, 260, 122, "XY Line", "Terminated XY node in this model")}
    ${box(450, 88, 290, 122, "Readout Resonator", "Quarter-wave resonator (QWR)")}
    ${box(840, 210, 270, 122, "Readout Line + PF", "Distributed line and half-wave PF")}

    ${direct(330, 149, 450, 149, "c_rq1, c_rq2")}
    ${direct(200, 210, 200, 332, "c_xy1, c_xy2")}
    ${direct(740, 149, 840, 260, "coupled window")}

    ${mediated(330, 392, 450, 149, "mediated only")}
    ${mediated(330, 149, 840, 260, "mediated only")}
    ${mediated(330, 392, 840, 260, "mediated only")}

    <text x="70" y="34" font-family="${theme.bodyFont}" font-size="22" font-weight="700" fill="${ink}">Four structures, three direct interfaces, three mediated interfaces</text>
    <text x="70" y="490" font-family="${theme.bodyFont}" font-size="18" fill="${subInk}">Direct interfaces should be tested with monotonic parameter sweeps. Mediated interfaces should be tested with path-breaking null checks.</text>
  </svg>`;
}

function makePairwiseMatrixSvg() {
  const width = 1180;
  const height = 520;
  const ink = svgColor(theme.ink);
  const subInk = svgColor(theme.subInk);
  const border = svgColor(theme.border);
  const directFill = svgColor(theme.primarySoft);
  const directStroke = svgColor(theme.primaryBorder);
  const medFill = svgColor(theme.warnSoft);
  const medStroke = svgColor(theme.warnBorder);
  const labels = ["Qubit", "Readout Resonator", "XY Line", "Readout Line + PF"];
  const cells = [];
  const top = 90;
  const left = 250;
  const size = 150;

  for (let r = 0; r < labels.length; r += 1) {
    for (let c = 0; c < labels.length; c += 1) {
      const x = left + c * size;
      const y = top + r * size;
      let fill = "#FFFFFF";
      let stroke = border;
      let text = "";
      if (c <= r) {
        fill = "#FFFFFF";
        stroke = border;
      } else if (
        (r === 0 && c === 1) ||
        (r === 0 && c === 2) ||
        (r === 1 && c === 3)
      ) {
        fill = directFill;
        stroke = directStroke;
        text = "Direct";
      } else {
        fill = medFill;
        stroke = medStroke;
        text = "Mediated";
      }
      cells.push(`
        <rect x="${x}" y="${y}" width="${size - 10}" height="${size - 10}" rx="22" fill="${fill}" stroke="${stroke}" stroke-width="2"/>
        <text x="${x + (size - 10) / 2}" y="${y + 78}" text-anchor="middle" font-family="${theme.bodyFont}" font-size="24" font-weight="700" fill="${ink}">${text}</text>
      `);
    }
  }

  const rowLabels = labels
    .map(
      (label, index) =>
        `<text x="${left - 24}" y="${top + index * size + 78}" text-anchor="end" font-family="${theme.bodyFont}" font-size="22" font-weight="700" fill="${ink}">${label}</text>`
    )
    .join("");
  const colLabels = labels
    .map(
      (label, index) =>
        `<text x="${left + index * size + 68}" y="${top - 24}" text-anchor="middle" font-family="${theme.bodyFont}" font-size="21" font-weight="700" fill="${ink}">${label}</text>`
    )
    .join("");
  return `
  <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <rect width="${width}" height="${height}" rx="26" fill="#FFFFFF"/>
    ${cells.join("")}
    ${rowLabels}
    ${colLabels}
    <text x="60" y="40" font-family="${theme.bodyFont}" font-size="22" font-weight="700" fill="${ink}">Upper triangle shows how each pair should be audited</text>
    <text x="60" y="${height - 24}" font-family="${theme.bodyFont}" font-size="18" fill="${subInk}">Direct pairs get sweep-based monotonic checks. Mediated pairs get null tests and path-breaking checks.</text>
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

  addFooter(slide, "Front section: first explain the structure, then explain what the structure should do when its own knobs are swept.");
  validateSlide(slide, pptx);
}

function addPairSlide(pptx, def, pageNo) {
  const slide = pptx.addSlide();
  const contentTop = 2.10;
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo);
  addTitle(slide, def.eyebrow, def.title, "Each pair should be audited by asking whether the parameter-response pattern matches the topology that this model actually contains.", {
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

  addFooter(slide, "For mediated pairs, path-breaking null tests matter more than large parameter sweeps.");
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
  addHeaderChip(slide, "QECA PARAMETER-RESPONSE V&V");
  slide.addText("Verification deck for\nparameter-response falsification", {
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
    "The deck assumes you do not want to line-by-line audit every implementation detail. Instead, you audit each structure and each interface by sweeping the knobs that should expose incorrect behavior first.",
    0.82,
    2.72,
    6.2,
    0.95,
    { fontSize: 11.4 }
  );
  addPanel(slide, 9.18, 1.54, 3.08, 4.88);
  addPanelTitle(slide, 9.48, 1.88, 2.4, "Report Order");
  addBulletList(
    slide,
    [
      "Four structures: parameters and expected response",
      "Six pairwise interfaces: direct or mediated",
      "Expected behavior versus actual behavior slot",
      "End with a repeatable execution checklist",
    ],
    9.42,
    2.22,
    2.42,
    1.6,
    { fontSize: 9.8 }
  );
  addParagraph(
    slide,
    "Core matrix views in this study: reduced Ydm,in(ω), full Y(ω), Z→Y reductions, and readout-branch S21 with vector fitting.",
    9.48,
    5.24,
    2.2,
    0.8,
    { fontSize: 9.5 }
  );
  addFooter(slide, "Use this as the report front section before presenting any actual sweep results.");
  validateSlide(slide, pptx);

  slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  addTitle(slide, "Method", "Three-Part Verification Logic", "This deck is intentionally about verification first, solution verification second, and validation third.", {
    titleSize: 22,
    subtitleW: 8.6,
  });
  const methodCards = [
    {
      x: 0.82,
      title: "1. Verification",
      text: "Did the code implement the intended mathematical structure? Use parameter-response checks and decoupling limits.",
      fill: "EAF1FF",
      line: "BED1F9",
      tone: "2563EB",
    },
    {
      x: 4.38,
      title: "2. Solution Verification",
      text: "Are discretization, sweep resolution, matching windows, and fitting settings converged enough for this claim?",
      fill: "FFF5E5",
      line: "F0D49D",
      tone: "C88719",
    },
    {
      x: 7.94,
      title: "3. Validation",
      text: "Do the trends and magnitudes still look like plausible physics, not only plausible numerics?",
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
  addPanelTitle(slide, 1.08, 5.08, 4.0, "Operational Rule For This Study");
  addBulletList(
    slide,
    [
      "Start with self-structure sweeps where the expected trend is simplest and strongest.",
      "Move to direct interfaces and check monotonicity under the explicit coupling knob.",
      "Treat the remaining three pairs as mediated only, and audit them with path-breaking null tests.",
    ],
    1.02,
    5.36,
    10.9,
    0.7,
    { fontSize: 10.2 }
  );
  addFooter(slide, "The report should make it obvious what would have broken first if the implementation were wrong.");
  validateSlide(slide, pptx);

  slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  addTitle(slide, "Topology", "Model Topology Used By The Audit", "This summary matters because some interfaces are direct in the netlist, while others are only mediated through an intermediate path.", {
    titleSize: 22,
    subtitleW: 10.9,
  });
  addSvgImage(slide, "topology_map", makeTopologySvg(), 0.82, 2.14, 11.92, 4.76);
  addFooter(slide, "A good verification report should respect the actual topology of the study model, not only the physical story we tell around it.");
  validateSlide(slide, pptx);

  slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  addTitle(slide, "Inventory", "Pairwise Audit Inventory", "Direct interfaces get sweep-based checks. Mediated interfaces get null checks and path-breaking checks.", {
    titleSize: 22,
    subtitleW: 9.8,
  });
  addSvgImage(slide, "pairwise_matrix", makePairwiseMatrixSvg(), 0.82, 2.08, 11.9, 4.62);
  addFooter(slide, "This slide is the transition point between subsystem pages and pairwise-interface pages.");
  validateSlide(slide, pptx);

  structureSlides.forEach((def) => addSubsystemSlide(pptx, def, pageNo++));
  pairSlides.forEach((def) => addPairSlide(pptx, def, pageNo++));

  slide = pptx.addSlide();
  addFullBleedBackground(slide);
  addPageChrome(slide, pageNo++);
  addTitle(slide, "Execution", "How To Run The Audit", "This last slide turns the deck into a repeatable protocol instead of a one-off presentation.", {
    titleSize: 22,
    subtitleW: 9.2,
  });
  addPanel(slide, 0.82, 2.10, 5.9, 4.44);
  addPanelTitle(slide, 1.08, 2.36, 4.0, "Per-Slide Fill-In Rule");
  addBulletList(
    slide,
    [
      "Name the parameter being swept and which structure or interface it belongs to.",
      "State the expected matrix signature before showing the plot.",
      "Add the actual plot and one sentence: matched / partially matched / failed.",
      "If it fails, point to the first plausible implementation surface to inspect.",
    ],
    1.02,
    2.72,
    5.1,
    1.3,
    { fontSize: 10.2 }
  );
  addPanelTitle(slide, 1.08, 4.86, 4.0, "Recommended Score Columns");
  addMonoList(
    slide,
    [
      "structure_or_pair",
      "swept_knob",
      "primary_matrix_view",
      "expected_trend",
      "observed_trend",
      "pass_status",
      "confidence_delta",
    ],
    1.08,
    5.18,
    3.3,
    1.06
  );
  addPanel(slide, 7.0, 2.10, 5.52, 4.44, { fill: "F7F4EE" });
  addPanelTitle(slide, 7.28, 2.36, 3.8, "Minimum Black-Box Test Set");
  addBulletList(
    slide,
    [
      "One monotonic self-sweep per structure",
      "One zero-coupling or decoupling-limit test per direct interface",
      "One path-breaking null test per mediated interface",
      "One discretization or sweep-resolution refinement check on the final claim",
      "One external-physics sanity check on magnitude or mode location",
    ],
    7.22,
    2.72,
    4.75,
    1.62,
    { fontSize: 10.0 }
  );
  addPanelTitle(slide, 7.28, 5.06, 3.8, "Decision Rule");
  addParagraph(
    slide,
    "Do not ask whether the implementation feels reasonable. Ask whether the necessary failure signatures stayed absent under the sweeps that should have exposed them first.",
    7.28,
    5.36,
    4.7,
    0.66,
    { fontSize: 10.3, color: theme.ink }
  );
  addFooter(slide, "This protocol is designed for a researcher who cannot afford a full line-by-line code audit.");
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
