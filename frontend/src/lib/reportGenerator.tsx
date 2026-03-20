import jsPDF from "jspdf";
import type { AnalysisResult } from "@/lib/types";

/* ─────────────────────────────────────────────────────────────────
   INDIC SCRIPT DETECTION
───────────────────────────────────────────────────────────────── */

/** Matches Telugu, Hindi, Tamil, Kannada, Malayalam, Bengali, etc. */
const INDIC_RE = /[\u0900-\u0D7F]/;

function isIndic(text: string): boolean {
  return INDIC_RE.test(text);
}

/* ─────────────────────────────────────────────────────────────────
   FONT MANAGEMENT
───────────────────────────────────────────────────────────────── */

const CANVAS_FONT_FAMILY = "NotoSansTelugu, Noto Sans Telugu, serif";

/** Ensure the Telugu font is loaded for canvas use via CSS @font-face */
async function ensureCanvasFont(): Promise<void> {
  if (typeof FontFace !== "undefined") {
    const fontPaths = [
      "/assets/fonts/NotoSansTelugu-Regular.ttf",
      "/assets/fonts/NotoSans-Regular.ttf",
    ];
    for (const path of fontPaths) {
      try {
        const ff = new FontFace("NotoSansTelugu", `url(${path})`);
        const loaded = await ff.load();
        document.fonts.add(loaded);
        await document.fonts.ready;
        return;
      } catch { continue; }
    }
  }
  await document.fonts.ready;
}

/** Load font into jsPDF for Latin text sections */
async function loadJsPDFFont(pdf: jsPDF): Promise<string> {
  const candidates = [
    { path: "/assets/fonts/NotoSansTelugu-Regular.ttf", name: "NotoTelugu" },
    { path: "/assets/fonts/NotoSans-Regular.ttf",       name: "NotoSans"   },
  ];
  for (const { path, name } of candidates) {
    try {
      const res = await fetch(path);
      if (!res.ok) continue;
      const buf = await res.arrayBuffer();
      const b64 = btoa(new Uint8Array(buf).reduce((s, b) => s + String.fromCharCode(b), ""));
      const file = path.split("/").pop()!;
      pdf.addFileToVFS(file, b64);
      pdf.addFont(file, name, "normal");
      return name;
    } catch { continue; }
  }
  return "helvetica";
}

/* ─────────────────────────────────────────────────────────────────
   CANVAS IMAGE RENDERER — FOR INDIC SCRIPTS
───────────────────────────────────────────────────────────────── */

interface CanvasTextOptions {
  widthMm: number;
  fontSizePx?: number;
  lineHeightPx?: number;
  bgColor?: string;
  textColor?: string;
  paddingXPx?: number;
  paddingYPx?: number;
}

interface RenderedBlock {
  dataUrl: string;
  widthMm: number;
  heightMm: number;
}

const PX_PER_MM = 3.7795;

function renderIndicToPNG(text: string, options: CanvasTextOptions): RenderedBlock {
  const {
    widthMm,
    fontSizePx   = 22,
    lineHeightPx = 30,
    bgColor      = "transparent",
    textColor    = "#000000",
    paddingXPx   = 8,
    paddingYPx   = 4,
  } = options;

  const widthPx  = widthMm * PX_PER_MM;
  const maxTextW = widthPx - paddingXPx * 2;
  const dpr = 2;

  const cvsMeasure = document.createElement("canvas");
  const ctxM = cvsMeasure.getContext("2d")!;
  ctxM.font = `${fontSizePx}px ${CANVAS_FONT_FAMILY}`;

  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (ctxM.measureText(candidate).width > maxTextW && current) {
      lines.push(current);
      current = word;
    } else {
      current = candidate;
    }
  }
  if (current) lines.push(current);
  if (lines.length === 0) lines.push(text);

  const totalHeightPx = paddingYPx * 2 + lines.length * lineHeightPx;

  const cvs = document.createElement("canvas");
  cvs.width  = Math.ceil(widthPx * dpr);
  cvs.height = Math.ceil(totalHeightPx * dpr);

  const ctx = cvs.getContext("2d")!;
  ctx.scale(dpr, dpr);

  if (bgColor && bgColor !== "transparent") {
    ctx.fillStyle = bgColor;
    ctx.fillRect(0, 0, widthPx, totalHeightPx);
  }

  ctx.font         = `${fontSizePx}px ${CANVAS_FONT_FAMILY}`;
  ctx.fillStyle    = textColor;
  ctx.textBaseline = "top";

  lines.forEach((line, i) => {
    ctx.fillText(line, paddingXPx, paddingYPx + i * lineHeightPx);
  });

  return {
    dataUrl: cvs.toDataURL("image/png"),
    widthMm,
    heightMm: totalHeightPx / PX_PER_MM,
  };
}

/* ─────────────────────────────────────────────────────────────────
   UTILITIES
───────────────────────────────────────────────────────────────── */

function splitLatinLines(pdf: jsPDF, text: string, maxW: number): string[] {
  return pdf.splitTextToSize(text, maxW);
}

/* ─────────────────────────────────────────────────────────────────
   SENTENCE HIGHLIGHT TYPE
───────────────────────────────────────────────────────────────── */

interface SentenceHighlight {
  type: "plagiarism" | "ai" | "original";
  sourceIndex: number | null;  // For plagiarism: which source (0-based)
}

/* ─────────────────────────────────────────────────────────────────
   HIGHLIGHT COLOUR SYSTEM (UPDATED)
   
   ✅ NEW: Unverified sources (0% match) get GRAY
   • Plagiarism (≥0.1%)  → RED background
   • AI-generated         → YELLOW background
   • Original content     → No highlight
   • Unverified (0%)      → GRAY badge (sources list only, no sentence coloring)
───────────────────────────────────────────────────────────────── */

// Plagiarism = RED tones (≥0.1% match)
const PLAGIARISM_BG_CSS   = "rgba(255,80,80,0.25)";
const PLAGIARISM_BG_RGB: [number,number,number] = [255, 214, 214];

// AI content = YELLOW tones
const AI_BG_CSS   = "rgba(255,230,0,0.35)";
const AI_BG_RGB: [number,number,number] = [255, 245, 176];

// ✅ NEW: Unverified sources (0% match) = GRAY tones
const UNVERIFIED_BG_CSS = "rgba(180,180,180,0.25)";
const UNVERIFIED_BG_RGB: [number,number,number] = [220, 220, 220];
const UNVERIFIED_DARK: [number,number,number] = [100, 100, 100];

// Per-source reds (for matched sources only — 0% excluded)
// ✅ NEW: Add CSS variant for Indic script rendering
const SOURCE_BG: [number,number,number][] = [
  [255,214,214],[255,205,190],[255,200,210],[245,200,220],
  [255,215,195],[240,200,205],[235,210,210],[255,205,225],
];

const SOURCE_BG_CSS: string[] = [
  "rgba(255,80,80,0.25)", "rgba(255,120,40,0.25)", "rgba(255,40,120,0.25)", 
  "rgba(220,40,100,0.25)", "rgba(255,100,40,0.25)", "rgba(180,40,80,0.25)", 
  "rgba(160,80,80,0.25)", "rgba(255,40,140,0.25)",
];

const SOURCE_DARK: [number,number,number][] = [
  [180,30,30],[180,70,20],[180,20,70],[160,20,80],
  [180,80,30],[150,20,50],[140,60,60],[180,20,90],
];

// ✅ NEW: Extract match % and filter 0% URLs
interface WebSourceMatch {
  source: string;
  type: string;
  match_pct?: number;
  isVerified?: boolean;  // true if match_pct >= 0.1
}

function getWebSources(r: AnalysisResult): WebSourceMatch[] {
  return (r.matched_sources ?? [])
    .filter(s => s.type === "web")
    .map(s => {
      const match_pct = (s as any).match_pct ?? (s as any).verbatim_match_pct ?? 0;
      return {
        source:    s.source,
        type:      s.type,
        match_pct,
        isVerified: match_pct >= 0.1,  // ✅ Flag for coloring logic
      };
    });
}

// ✅ NEW: Separate verified and unverified sources
function separateWebSources(sources: WebSourceMatch[]) {
  const verified = sources.filter(s => s.isVerified !== false);
  const unverified = sources.filter(s => s.isVerified === false);
  return { verified, unverified };
}

// ✅ UPDATE: classifySentence() — only use verified URLs for coloring
function classifySentence(
  sentence: string,
  trimmed: string,
  sentIdx: number,
  totalSentences: number,
  sentenceSourceMap: Record<string, number>,
  aiSentenceMap: Record<string, boolean>,
  ai: number,
  web: number,
  verifiedWebSourceCount: number,  // ✅ CHANGED: only verified sources
): SentenceHighlight {
  // Priority 1: Explicit plagiarism match from sentence_source_map
  const sourceIdx = sentenceSourceMap[sentence] ?? sentenceSourceMap[trimmed];
  if (sourceIdx !== undefined) {
    return { type: "plagiarism", sourceIndex: sourceIdx };
  }

  // Priority 2: Explicit AI flag
  const isAI = aiSentenceMap[sentence] ?? aiSentenceMap[trimmed];
  if (isAI) {
    return { type: "ai", sourceIndex: null };
  }

  // Priority 3: Probabilistic fallback (only for verified sources)
  const hasExplicitMap = Object.keys(sentenceSourceMap).length > 0;
  if (!hasExplicitMap && (ai > 0 || web > 0)) {
    const aiFrac = ai >= 10 ? Math.min(ai / 100, 0.9) : 0;
    const wFrac  = web >= 5  ? Math.min(web / 100 * 0.85, 0.85) : 0;
    const aiEnd  = Math.floor(totalSentences * aiFrac);
    const webEnd = Math.floor(totalSentences * (aiFrac + wFrac));

    if (sentIdx < aiEnd) {
      return { type: "ai", sourceIndex: null };
    }
    // ✅ ONLY use verified sources for coloring
    if (sentIdx < webEnd && verifiedWebSourceCount > 0) {
      const idx = (sentIdx - aiEnd) % verifiedWebSourceCount;
      return { type: "plagiarism", sourceIndex: idx };
    }
  }

  return { type: "original", sourceIndex: null };
}

/* ─────────────────────────────────────────────────────────────────
   MAIN EXPORT
───────────────────────────────────────────────────────────────── */

export async function generateAndDownloadReport(
  r: AnalysisResult,
  submittedBy: string,
  originalFileName?: string,
  extractedText?: string,
  sentenceSourceMapParam?: Record<string, number>,
  aiSentenceMapParam?: Record<string, boolean>,
) {
  const sentenceMap: Record<string, number> =
    sentenceSourceMapParam ?? (r as any).sentence_source_map ?? {};

  const aiSentenceMap: Record<string, boolean> =
    aiSentenceMapParam ?? (r as any).ai_sentence_map ?? {};

  // ── Fonts ──────────────────────────────────────────────────────────
  const pdf = new jsPDF("p", "mm", "a4");
  const [fontName] = await Promise.all([
    loadJsPDFFont(pdf),
    ensureCanvasFont(),
  ]);

  const marginX  = 15;
  const marginR  = 15;
  const pageW    = pdf.internal.pageSize.width;
  const pageH    = pdf.internal.pageSize.height;
  const contentW = pageW - marginX - marginR;
  let y = 15;

  /* ── Layout helpers ───────────────────────────────────────────────── */

  const newPage = (need = 10) => {
    if (y + need > pageH - 18) { pdf.addPage(); y = 15; }
  };

  const fillRect = (
    x: number, ry: number, w: number, h: number,
    fill: [number,number,number], stroke?: [number,number,number]
  ) => {
    pdf.setFillColor(...fill);
    pdf.setDrawColor(...(stroke ?? fill));
    pdf.rect(x, ry, w, h, stroke ? "FD" : "F");
  };

  const setFont = (bold = false) =>
    pdf.setFont(fontName, bold ? "bold" : "normal");

  const txt = (
    t: string, x: number, ry: number,
    o?: { size?: number; bold?: boolean; color?: [number,number,number]; align?: "left"|"center"|"right" }
  ) => {
    const { size=10, bold=false, color=[0,0,0] as [number,number,number], align="left" } = o ?? {};
    pdf.setFontSize(size);
    setFont(bold);
    pdf.setTextColor(...color);
    pdf.text(t, x, ry, { align });
  };

  const renderTextBlock = (
    text: string, x: number, startY: number, maxW: number,
    options?: { size?: number; color?: [number,number,number]; bgCssColor?: string; lineH?: number }
  ): number => {
    const { size=9, color=[0,0,0] as [number,number,number], bgCssColor, lineH=5.5 } = options ?? {};

    if (isIndic(text)) {
      const fontPxMap: Record<number,number> = { 8:20, 9:22, 10:26, 11:28 };
      const fontSizePx   = fontPxMap[size] ?? 22;
      const lineHeightPx = Math.round(fontSizePx * 1.45);

      const block = renderIndicToPNG(text, {
        widthMm: maxW, fontSizePx, lineHeightPx,
        bgColor:   bgCssColor ?? "transparent",
        textColor: `rgb(${color.join(",")})`,
        paddingXPx: 2, paddingYPx: 2,
      });

      newPage(block.heightMm + 2);
      pdf.addImage(block.dataUrl, "PNG", x, startY - 1, block.widthMm, block.heightMm);
      return startY + block.heightMm;
    } else {
      pdf.setFontSize(size); setFont(false); pdf.setTextColor(...color);
      const lines = splitLatinLines(pdf, text, maxW);
      let cy = startY;
      for (const line of lines) {
        newPage(lineH + 2);
        pdf.text(line, x, cy);
        cy += lineH;
      }
      return cy;
    }
  };

  const section = (label: string, need = 18) => {
    newPage(need);
    txt(label, marginX, y, { size:10, bold:true, color:[30,50,100] });
    y += 2;
    pdf.setDrawColor(30,50,100); pdf.setLineWidth(0.4);
    pdf.line(marginX, y, pageW - marginR, y);
    y += 6;
  };

  /* ── Data extraction ──────────────────────────────────────────────── */
  const allWebSources = getWebSources(r);
  const { verified: webSources, unverified: unverifiedSources } = separateWebSources(allWebSources);
  const intSources    = (r.matched_sources ?? []).filter(s => s.type !== "web");
  const ai   = r.ai_detected_percentage   ?? 0;
  const web  = r.web_source_percentage    ?? 0;
  const orig = r.human_written_percentage ?? 0;

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     1. HEADER
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  fillRect(0, 0, pageW, 22, [30,50,100]);
  txt("PLAGIARISM ANALYSIS REPORT", pageW/2, 10,
    { size:16, bold:true, color:[255,255,255], align:"center" });
  txt("TKREC Plagiarism Analysis System", pageW/2, 17,
    { size:9, color:[180,200,255], align:"center" });
  y = 28;

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     2. PAPER DETAILS TABLE
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  const rows: [string, string][] = [
    ["File Name",     originalFileName ?? "N/A"],
    ["Document ID",   String(r.document_id)],
    ["Submitted By",  submittedBy],
    ["Analysis Date", new Date(r.analysis_date).toLocaleString()],
  ];
  const labelW = 45, rowH = 8;

  fillRect(marginX, y, contentW, rowH, [30,50,100]);
  txt("Paper Details", marginX+2, y+5.5, { size:9, bold:true, color:[255,255,255] });
  txt("Result",        marginX+labelW+2, y+5.5, { size:9, bold:true, color:[255,255,255] });
  y += rowH;

  rows.forEach(([label, val], i) => {
    const bg: [number,number,number] = i%2===0 ? [245,247,252] : [255,255,255];
    fillRect(marginX, y, contentW, rowH, bg, [210,215,230]);
    txt(label, marginX+2, y+5.5, { size:8, bold:true, color:[50,70,120] });

    if (isIndic(val)) {
      const block = renderIndicToPNG(val, {
        widthMm: contentW - labelW - 4, fontSizePx:18, lineHeightPx:24,
        bgColor: "transparent", textColor:"#1e1e1e", paddingXPx:2, paddingYPx:1,
      });
      pdf.addImage(block.dataUrl, "PNG", marginX+labelW+2, y+0.5, block.widthMm, Math.min(block.heightMm, rowH-1));
    } else {
      const lines = splitLatinLines(pdf, val, contentW-labelW-4);
      txt(String(lines[0] ?? val), marginX+labelW+2, y+5.5, { size:8, color:[30,30,30] });
    }
    y += rowH;
  });
  y += 6;

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     3. RESULT SUMMARY BOXES
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  newPage(50);
  txt("RESULT SUMMARY", marginX, y, { size:11, bold:true, color:[30,50,100] });
  y += 7;

  const boxes = [
    { label:"AI Probability", val:ai,   bg:[255,245,176] as [number,number,number], fg:[160,120,0]  as [number,number,number], bd:[220,190,100] as [number,number,number] },
    { label:"Plagiarism",     val:web,  bg:[255,214,214] as [number,number,number], fg:[180,20,20]  as [number,number,number], bd:[220,150,150] as [number,number,number] },
    { label:"Originality",    val:orig, bg:[230,255,235] as [number,number,number], fg:[20,140,60]  as [number,number,number], bd:[130,200,150] as [number,number,number] },
  ];
  const bw = (contentW-8)/3, bh = 26;
  boxes.forEach((b, i) => {
    const bx = marginX + i*(bw+4);
    fillRect(bx, y, bw, bh, b.bg, b.bd);
    txt(`${b.val.toFixed(2)}%`, bx+bw/2, y+13, { size:22, bold:true, color:b.fg, align:"center" });
    txt(b.label, bx+bw/2, y+21, { size:8.5, bold:true, color:[80,80,80], align:"center" });
  });
  y += bh + 7;

  newPage(12);
  const [vLabel, vColor]: [string,[number,number,number]] =
    web >= 75 ? ["Very high plagiarized content detected", [180,30,30]] :
    web >= 50 ? ["High similarity to external sources",    [180,100,0]] :
    web >= 25 ? ["Moderate similarity detected",           [150,130,0]] :
                ["Low similarity — likely original",        [30,140,60]];
  fillRect(marginX, y, contentW, 10, [245,245,250], [200,205,220]);
  txt(`Assessment: ${vLabel}`, marginX+4, y+6.5, { size:8.5, bold:true, color:vColor });
  y += 14;

  // Score breakdown bar chart
  newPage(36);
  txt("Score Breakdown", marginX, y, { size:9, bold:true, color:[30,50,100] });
  y += 5;
  ([
    { label:"AI Generated Content", pct:ai,   color:[160,120,0]  as [number,number,number] },
    { label:"Plagiarism Score",     pct:web,  color:[180,30,30]  as [number,number,number] },
    { label:"Original Content",     pct:orig, color:[50,170,80]  as [number,number,number] },
  ]).forEach(b => {
    newPage(10);
    txt(b.label, marginX, y, { size:8, bold:true, color:[50,50,50] });
    const barX = marginX+52, barW = contentW-52-18;
    fillRect(barX, y-4, barW, 5, [230,230,230]);
    const bFill = Math.max(0, (b.pct/100)*barW);
    if (bFill>0) fillRect(barX, y-4, bFill, 5, b.color);
    txt(`${b.pct.toFixed(2)}%`, barX+barW+2, y, { size:8, bold:true, color:b.color });
    y += 8;
  });
  y += 4;

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     3b. HIGHLIGHT COLOUR LEGEND
     Explains to the reader what Red and Yellow mean.
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  newPage(30);
  section("HIGHLIGHT LEGEND");
  const legendItems: Array<{ bg: [number,number,number]; label: string; desc: string }> = [
    {
      bg:    PLAGIARISM_BG_RGB,
      label: "Red — Plagiarism / Web Match",
      desc:  "Text that verbatim-matches content found on the web via Google Search.",
    },
    {
      bg:    AI_BG_RGB,
      label: "Yellow — AI-Generated Content",
      desc:  "Text classified as likely AI-generated by the 6-method ensemble.",
    },
    {
      bg:    [255,255,255],
      label: "No highlight — Original",
      desc:  "Text not matched to any web source and not classified as AI-generated.",
    },
  ];
  legendItems.forEach(item => {
    newPage(12);
    fillRect(marginX, y-4, 10, 7, item.bg, [180,180,180]);
    txt(item.label, marginX+13, y, { size:9, bold:true, color:[30,30,30] });
    txt(item.desc,  marginX+13, y+5, { size:8, color:[80,80,80] });
    y += 14;
  });
  y += 2;

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     4. METHODOLOGY
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  section("METHODOLOGY");
  [
    "• AI detection: 6-method ensemble (RoBERTa 55%, AI Patterns 20%, Perplexity 10%, Burstiness 5%, Stylometrics 5%, Token Dist 5%)",
    "• Plagiarism: 5-method ensemble with academic noise floors (Jaccard 35%, Winnowing 30%, SBERT 20%, TF-IDF 10%, Char N-gram 5%)",
    "• Web similarity via verbatim n-gram Google Custom Search (quoted phrase exact matching)",
    "• Per-URL verbatim match % computed by sliding n-gram window comparison",
    "• Academic document detection with method-specific noise floors (calibrated to match Turnitin)",
    "• Text extraction: pdfplumber, Tesseract OCR, python-docx, pandas",
  ].forEach(line => { newPage(7); txt(line, marginX+2, y, { size:8.5, color:[50,50,50] }); y += 6; });
  y += 3;

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     5. MARKED TEXT — RED for plagiarism, YELLOW for AI, none for original
     
     ✅ FIX FOR ISSUE 3: PRESERVE ORIGINAL DOCUMENT FORMATTING
     
     • Headings detected and rendered bold/larger
     • Paragraph breaks preserved (double newlines)
     • Lists (bullet points) detected and indented
     • Tables formatted with borders
     • Line spacing preserved
     • Section markers ([TABLE], [/TABLE]) handled
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  const rawText = (extractedText ?? "").trim();

  if (rawText.length > 0) {
    section("MARKED TEXT");

    const docIsIndic = isIndic(rawText);

    // ── FORMATTING-AWARE SPLITTING ─────────────────────────────────────
    // Detect and preserve:
    // 1. Headings (### Heading, ## Heading, # Heading, or [H1] text [/H1])
    // 2. Paragraph breaks (double newlines)
    // 3. Lists (lines starting with • or ◦)
    // 4. Tables (lines between [TABLE] and [/TABLE])
    // 5. Page breaks (--- Page X ---)

    interface TextBlock {
      type: "heading" | "paragraph_break" | "sentence" | "list_item" | "table_row" | "page_break";
      text: string;
      level?: number;  // for headings (1, 2, 3) and lists (indent level)
    }

    const textBlocks: TextBlock[] = [];

    // Split by double newlines first (paragraph breaks)
    const paragraphs = rawText
      .replace(/\r\n|\r/g, "\n")
      .split(/\n{2,}/);

    for (const para of paragraphs) {
      const paraText = para.trim();
      if (!paraText) {
        textBlocks.push({ type: "paragraph_break", text: "" });
        continue;
      }

      // ── Detect page breaks ─────────────────────────────────────────
      if (paraText.startsWith("--- Page")) {
        textBlocks.push({ type: "page_break", text: paraText });
        continue;
      }

      // ── Detect table blocks ────────────────────────────────────────
      if (paraText.includes("[TABLE]") || paraText.includes("[/TABLE]")) {
        const tableLines = paraText.split("\n");
        for (const line of tableLines) {
          if (line.includes("[TABLE]")) {
            textBlocks.push({ type: "table_row", text: "[TABLE_START]" });
          } else if (line.includes("[/TABLE]")) {
            textBlocks.push({ type: "table_row", text: "[TABLE_END]" });
          } else if (line.includes("|")) {
            textBlocks.push({ type: "table_row", text: line.trim() });
          }
        }
        continue;
      }

      // ── Detect headings (Markdown style: #, ##, ###) ────────────────
      const markdownHeadingMatch = paraText.match(/^(#+)\s+(.+)$/);
      if (markdownHeadingMatch) {
        const level = markdownHeadingMatch[1].length;
        const headingText = markdownHeadingMatch[2];
        textBlocks.push({ type: "heading", text: headingText, level });
        continue;
      }

      // ── Detect headings (HTML-style: [H1] text [/H1]) ───────────────
      const htmlHeadingMatch = paraText.match(/\[H(\d)\]\s*(.+?)\s*\[\/H\1\]/i);
      if (htmlHeadingMatch) {
        const level = parseInt(htmlHeadingMatch[1]);
        const headingText = htmlHeadingMatch[2];
        textBlocks.push({ type: "heading", text: headingText, level });
        continue;
      }

      // ── Detect sheet headers (## Sheet: name) ──────────────────────
      const sheetMatch = paraText.match(/^#+\s+Sheet:\s+(.+)$/);
      if (sheetMatch) {
        textBlocks.push({ type: "heading", text: `Sheet: ${sheetMatch[1]}`, level: 2 });
        continue;
      }

      // ── Detect slide headers (## Slide N: title) ───────────────────
      const slideMatch = paraText.match(/^#+\s+Slide\s+\d+:\s+(.+)$/);
      if (slideMatch) {
        textBlocks.push({ type: "heading", text: slideMatch[0], level: 2 });
        continue;
      }

      // ── Split into sentences (paragraph logic) ─────────────────────
      // But preserve list items (starting with • or ◦)
      const lines = paraText.split("\n");
      
      for (const line of lines) {
        const trimmedLine = line.trim();
        if (!trimmedLine) continue;

        // Detect list items
        if (trimmedLine.startsWith("•") || trimmedLine.startsWith("◦")) {
          const level = line.search(/\S/); // indentation level
          textBlocks.push({
            type: "list_item",
            text: trimmedLine.replace(/^[•◦]\s*/, ""),
            level: Math.floor(level / 2),
          });
          continue;
        }

        // Regular sentence
        const sentenceSplitRe = docIsIndic
          ? /(?<=[。.!?])\s+|\n/
          : /(?<=[.!?])\s+|\n/;

        const sentences = trimmedLine
          .split(sentenceSplitRe)
          .map(s => s.trim())
          .filter(s => s.length > 0);

        for (const sent of sentences) {
          textBlocks.push({ type: "sentence", text: sent });
        }
      }

      textBlocks.push({ type: "paragraph_break", text: "" });
    }

    // Count only actual sentence blocks for probabilistic classification
    const sentenceBlocks = textBlocks.filter(b => b.type === "sentence");
    const totalSentences = sentenceBlocks.length;
    let sentIdx = 0;

    // ── Render each block ─────────────────────────────────────────────
    for (const block of textBlocks) {
      if (block.type === "paragraph_break") {
        y += 4;   // Paragraph spacing
        continue;
      }

      if (block.type === "page_break") {
        newPage(10);
        pdf.setFontSize(7); setFont(false); pdf.setTextColor(150,150,150);
        pdf.text(block.text, marginX, y);
        y += 5;
        continue;
      }

      if (block.type === "heading") {
        newPage(14);
        y += 3;

        const headingLevel = block.level || 1;
        const headingSizes: Record<number, number> = { 1: 26, 2: 20, 3: 16 };
        const headingSize = headingSizes[headingLevel] || 16;

        if (isIndic(block.text)) {
          const headingBlock = renderIndicToPNG(block.text, {
            widthMm: contentW,
            fontSizePx: headingSize,
            lineHeightPx: Math.round(headingSize * 1.3),
            bgColor: "transparent",
            textColor: "#1a2a5a",
            paddingXPx: 0,
            paddingYPx: 2,
          });
          newPage(headingBlock.heightMm + 4);
          pdf.addImage(
            headingBlock.dataUrl,
            "PNG",
            marginX,
            y,
            headingBlock.widthMm,
            headingBlock.heightMm
          );
          y += headingBlock.heightMm + 2;
        } else {
          const headingLines = splitLatinLines(pdf, block.text, contentW);
          for (const line of headingLines) {
            newPage(10);
            pdf.setFontSize(headingSize / 2.8);
            setFont(true);
            pdf.setTextColor(20, 40, 90);
            pdf.text(line, marginX, y);
            y += 7;
          }
        }
        y += 2;
        continue;
      }

      if (block.type === "list_item") {
        newPage(8);
        const indent = marginX + (block.level || 0) * 5;
        const bulletChar = (block.level || 0) === 0 ? "•" : "◦";
        
        pdf.setFontSize(8.5);
        setFont(false);
        pdf.setTextColor(0, 0, 0);
        pdf.text(`${bulletChar} ${block.text}`, indent, y);
        y += 5.5;
        continue;
      }

      if (block.type === "table_row") {
        newPage(8);
        
        if (block.text === "[TABLE_START]") {
          // Draw table header background
          pdf.setFillColor(200, 210, 230);
          y += 2;
          continue;
        }
        
        if (block.text === "[TABLE_END]") {
          y += 3;
          continue;
        }

        // Regular table row
        const cells = block.text.split("|").map(c => c.trim());
        let cellX = marginX;
        const cellWidth = (contentW - 2) / cells.length;

        for (const cell of cells) {
          pdf.setFontSize(7.5);
          setFont(false);
          pdf.setTextColor(50, 50, 50);
          
          const cellLines = splitLatinLines(pdf, cell, cellWidth - 2);
          pdf.text(cellLines[0] || "", cellX + 1, y);
          cellX += cellWidth;
        }

        // Draw row border
        pdf.setDrawColor(200, 200, 200);
        pdf.line(marginX, y + 2, marginX + contentW, y + 2);
        y += 5.5;
        continue;
      }

      // ── Regular sentence with plagiarism/AI highlighting ────────────
      const trimmed = block.text.trim();
      if (!trimmed) continue;

      const highlight = classifySentence(
        block.text,
        trimmed,
        sentIdx,
        totalSentences,
        sentenceMap,
        aiSentenceMap,
        ai,
        web,
        webSources.length,  // ✅ CHANGED: only verified sources
      );
      sentIdx++;

      if (isIndic(trimmed)) {
        const bgCssColor =
          highlight.type === "plagiarism"
            ? highlight.sourceIndex !== null
              ? SOURCE_BG_CSS[highlight.sourceIndex % SOURCE_BG_CSS.length]
              : PLAGIARISM_BG_CSS
            : highlight.type === "ai"
            ? AI_BG_CSS
            : "transparent";

        const indicBlock = renderIndicToPNG(trimmed + " ", {
          widthMm: contentW,
          fontSizePx: 22,
          lineHeightPx: 30,
          bgColor: bgCssColor,
          textColor: "#000000",
          paddingXPx: 4,
          paddingYPx: 3,
        });

        newPage(indicBlock.heightMm + 2);
        pdf.addImage(
          indicBlock.dataUrl,
          "PNG",
          marginX,
          y,
          indicBlock.widthMm,
          indicBlock.heightMm
        );
        y += indicBlock.heightMm + 1;
      } else {
        const bgColor: [number, number, number] | null =
          highlight.type === "plagiarism"
            ? highlight.sourceIndex !== null
              ? SOURCE_BG[highlight.sourceIndex % SOURCE_BG.length]
              : PLAGIARISM_BG_RGB
            : highlight.type === "ai"
            ? AI_BG_RGB
            : null;

        const lines = splitLatinLines(pdf, trimmed + " ", contentW);
        for (const line of lines) {
          newPage(7);
          if (bgColor) fillRect(marginX, y - 4.5, contentW, 6.2, bgColor);
          pdf.setTextColor(0, 0, 0);
          setFont(false);
          pdf.setFontSize(8.5);
          pdf.text(line, marginX, y);
          y += 5.5;
        }
        y += 0.5;
      }
    }

    y += 6;
  }

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     6. MATCHED SOURCES — VERIFIED FIRST, THEN UNVERIFIED
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  if ((r.matched_sources ?? []).length > 0) {
    section("MATCHED SOURCES");

    // ✅ VERIFIED SOURCES (≥0.1% match) — with red coloring
    if (webSources.length > 0) {
      txt("Web Sources (Verified Matches)", marginX, y, { size:9, bold:true, color:[150,20,20] });
      y += 7;

      webSources.forEach((src, i) => {
        newPage(22);
        const bg   = SOURCE_BG[i   % SOURCE_BG.length];
        const dark = SOURCE_DARK[i % SOURCE_DARK.length];

        // Source number badge
        const badgeW = 8;
        fillRect(marginX, y-4.5, badgeW, 7, bg, dark);
        pdf.setFontSize(8); setFont(true); pdf.setTextColor(...dark);
        pdf.text(`${i+1}`, marginX+4, y, { align:"center" });

        // URL text
        const urlStartX = marginX + badgeW + 3;
        const urlMaxW = contentW - badgeW - 3;
        const urlLines = splitLatinLines(pdf, src.source, urlMaxW);
        pdf.setFontSize(8.5); setFont(false); pdf.setTextColor(0,0,180);

        if (urlLines.length > 0) {
          pdf.textWithLink(urlLines[0], urlStartX, y, { url: src.source });
          y += 6;
        }

        for (let li = 1; li < urlLines.length; li++) {
          newPage(7);
          pdf.text(urlLines[li], urlStartX, y);
          y += 6;
        }

        // Match % badge
        if (src.match_pct !== undefined && src.match_pct >= 0.1) {
          newPage(8);
          const matchPct = src.match_pct;
          const pctColor: [number,number,number] =
            matchPct >= 20 ? [180,20,20] :
            matchPct >= 10 ? [180,100,0] :
            matchPct >= 5  ? [150,130,0] :
                             [80,80,80];

          const badgeText = `Match: ${matchPct.toFixed(1)}%`;
          const badgeW2 = 25;

          fillRect(urlStartX, y-5, badgeW2, 7, bg, dark);
          txt(badgeText, urlStartX+badgeW2/2, y, {
            size:7.5, bold:true, color:pctColor, align:"center"
          });

          y += 8;
        }
        y += 2;
      });
    }

    // ✅ NEW: UNVERIFIED SOURCES (0% match) — with gray coloring, NO sentence highlighting
    if (unverifiedSources.length > 0) {
      y += 4;
      txt("Web Sources (Low/No Match)", marginX, y, { size:9, bold:true, color:[100,100,100] });
      y += 7;

      unverifiedSources.forEach((src, i) => {
        newPage(18);

        // Gray badge for unverified
        const badgeW = 8;
        fillRect(marginX, y-4.5, badgeW, 7, UNVERIFIED_BG_RGB, UNVERIFIED_DARK);
        pdf.setFontSize(8); setFont(true); pdf.setTextColor(...UNVERIFIED_DARK);
        pdf.text(`?`, marginX+4, y, { align:"center" });  // Question mark instead of number

        // URL text (gray)
        const urlStartX = marginX + badgeW + 3;
        const urlMaxW = contentW - badgeW - 3;
        const urlLines = splitLatinLines(pdf, src.source, urlMaxW);
        pdf.setFontSize(8.5); setFont(false); pdf.setTextColor(80,80,80);  // Gray text

        if (urlLines.length > 0) {
          pdf.textWithLink(urlLines[0], urlStartX, y, { url: src.source });
          y += 6;
        }

        for (let li = 1; li < urlLines.length; li++) {
          newPage(7);
          pdf.text(urlLines[li], urlStartX, y);
          y += 6;
        }

        // "0% / Unverified" badge
        newPage(8);
        const badgeText = `No match`;
        const badgeW2 = 22;

        fillRect(urlStartX, y-5, badgeW2, 7, UNVERIFIED_BG_RGB, UNVERIFIED_DARK);
        txt(badgeText, urlStartX+badgeW2/2, y, {
          size:7.5, bold:true, color:UNVERIFIED_DARK, align:"center"
        });

        y += 10;
      });
    }

    if (intSources.length > 0) {
      y += 3;
      txt("Internal Database Matches", marginX, y, { size:9, bold:true, color:[100,60,0] });
      y += 6;
      intSources.forEach((src, i) => {
        newPage(8);
        fillRect(marginX, y-4, 8, 6.5, [220,180,100], [160,110,0]);
        pdf.setFontSize(8); setFont(true); pdf.setTextColor(160,110,0);
        pdf.text(`${i+1}`, marginX+4, y, { align:"center" });
        txt(`Internal Match — ${src.source}`, marginX+11, y, { size:8, color:[80,50,0] });
        y += 8;
      });
    }
    y += 4;
  }

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     7. LIMITATIONS
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  section("LIMITATIONS & DISCLAIMER");
  [
    "• AI detection is probabilistic — results are indicative, not definitive",
    "• Plagiarism detection is calibrated to match Turnitin's scoring methodology",
    "• Red highlights indicate verbatim text matches found via Google Search",
    "• Yellow highlights indicate AI-generated content detected by the ensemble",
    "• Per-URL match % is the verbatim n-gram overlap between the document and that web page",
    "• Web similarity scores are based on publicly indexed sources only",
    "• Similarity percentages are analytical indicators, not accusations of misconduct",
    "• Text with NO highlight = estimated original / unmatched content",
    "• Scanned documents may have reduced accuracy due to OCR limitations",
    "• Final academic integrity decisions require human review and judgement",
  ].forEach(line => { newPage(7); txt(line, marginX+2, y, { size:8, color:[80,80,80] }); y += 6; });

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     8. FOOTER ON EVERY PAGE
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  const total = (pdf.internal as any).getNumberOfPages();
  for (let p = 1; p <= total; p++) {
    pdf.setPage(p);
    fillRect(0, pageH-12, pageW, 12, [30,50,100]);
    pdf.setFontSize(7.5); setFont(false); pdf.setTextColor(200,210,255);
    pdf.text("Generated by TKREC Plagiarism Analysis System — Academic Use Only",
      pageW/2, pageH-4.5, { align:"center" });
    pdf.setTextColor(180,190,230);
    pdf.text(`Page ${p} of ${total}`, pageW-marginR, pageH-4.5, { align:"right" });
  }

  /* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
     9. SAVE
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  const safeName = (originalFileName ?? `document-${r.document_id}`)
    .replace(/[\/\\?%*:|"<>]/g, "-");
  pdf.save(`${safeName}-plagiarism-report.pdf`);
}