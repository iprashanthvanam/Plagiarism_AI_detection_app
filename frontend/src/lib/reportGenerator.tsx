// import jsPDF from "jspdf";
// import type { AnalysisResult } from "@/lib/types";

// /* ─────────────────────────────────────────────────────────────────
//    INDIC SCRIPT DETECTION
// ───────────────────────────────────────────────────────────────── */

// /** Matches Telugu, Hindi, Tamil, Kannada, Malayalam, Bengali, etc. */
// const INDIC_RE = /[\u0900-\u0D7F]/;

// function isIndic(text: string): boolean {
//   return INDIC_RE.test(text);
// }

// /* ─────────────────────────────────────────────────────────────────
//    FONT MANAGEMENT
//    - Custom Unicode font for jsPDF (used for Latin sections)
//    - Separate CSS font-face for canvas (used for Indic sections)
// ───────────────────────────────────────────────────────────────── */

// const CANVAS_FONT_FAMILY = "NotoSansTelugu, Noto Sans Telugu, serif";

// /** Ensure the Telugu font is loaded for canvas use via CSS @font-face */
// async function ensureCanvasFont(): Promise<void> {
//   // If FontFace API is available, explicitly load and wait for the font
//   if (typeof FontFace !== "undefined") {
//     const fontPaths = [
//       "/assets/fonts/NotoSansTelugu-Regular.ttf",
//       "/assets/fonts/NotoSans-Regular.ttf",
//     ];
//     for (const path of fontPaths) {
//       try {
//         const ff = new FontFace("NotoSansTelugu", `url(${path})`);
//         const loaded = await ff.load();
//         document.fonts.add(loaded);
//         await document.fonts.ready;
//         return;
//       } catch { continue; }
//     }
//   }
//   // Fallback: just wait for document fonts to be ready
//   await document.fonts.ready;
// }

// /** Load font into jsPDF for Latin text sections */
// async function loadJsPDFFont(pdf: jsPDF): Promise<string> {
//   const candidates = [
//     { path: "/assets/fonts/NotoSansTelugu-Regular.ttf", name: "NotoTelugu" },
//     { path: "/assets/fonts/NotoSans-Regular.ttf",       name: "NotoSans"   },
//   ];
//   for (const { path, name } of candidates) {
//     try {
//       const res = await fetch(path);
//       if (!res.ok) continue;
//       const buf = await res.arrayBuffer();
//       const b64 = btoa(new Uint8Array(buf).reduce((s, b) => s + String.fromCharCode(b), ""));
//       const file = path.split("/").pop()!;
//       pdf.addFileToVFS(file, b64);
//       pdf.addFont(file, name, "normal");
//       return name;
//     } catch { continue; }
//   }
//   return "helvetica";
// }

// /* ─────────────────────────────────────────────────────────────────
//    CANVAS IMAGE RENDERER — THE CORE FIX FOR TELUGU
// ───────────────────────────────────────────────────────────────── */

// interface CanvasTextOptions {
//   widthMm: number;           // target width in PDF mm
//   fontSizePx?: number;       // canvas font size in px (default 22)
//   lineHeightPx?: number;     // line height in px (default 30)
//   bgColor?: string;          // CSS background color (default transparent)
//   textColor?: string;        // CSS text color (default #000)
//   paddingXPx?: number;       // horizontal padding in px
//   paddingYPx?: number;       // vertical padding in px
// }

// interface RenderedBlock {
//   dataUrl: string;            // PNG data URL
//   widthMm: number;
//   heightMm: number;
// }

// const PX_PER_MM = 3.7795;    // at 96 dpi: 1mm = 3.7795px

// /**
//  * Render a Telugu/Indic text block to a canvas PNG image.
//  *
//  * The browser's canvas 2D context applies the full HarfBuzz shaping
//  * pipeline — all GSUB/GPOS OpenType rules are executed automatically.
//  * This produces pixel-perfect Telugu with correct conjuncts and diacritics.
//  *
//  * @param text      The Telugu (or mixed) text to render
//  * @param options   Width, font size, colors, padding
//  * @returns         PNG data URL + dimensions in PDF mm
//  */
// function renderIndicToPNG(text: string, options: CanvasTextOptions): RenderedBlock {
//   const {
//     widthMm,
//     fontSizePx   = 22,
//     lineHeightPx = 30,
//     bgColor      = "transparent",
//     textColor    = "#000000",
//     paddingXPx   = 8,
//     paddingYPx   = 4,
//   } = options;

//   const widthPx = widthMm * PX_PER_MM;
//   const maxTextW = widthPx - paddingXPx * 2;
//   const dpr = 2; // 2× for crisp text at any zoom level

//   // ── Step 1: Measure word-wrapped lines using canvas measurement ───────
//   // (canvas measureText correctly accounts for Telugu glyph widths)
//   const cvsMeasure = document.createElement("canvas");
//   const ctxM = cvsMeasure.getContext("2d")!;
//   ctxM.font = `${fontSizePx}px ${CANVAS_FONT_FAMILY}`;

//   const words = text.split(/\s+/).filter(Boolean);
//   const lines: string[] = [];
//   let current = "";

//   for (const word of words) {
//     const candidate = current ? `${current} ${word}` : word;
//     if (ctxM.measureText(candidate).width > maxTextW && current) {
//       lines.push(current);
//       current = word;
//     } else {
//       current = candidate;
//     }
//   }
//   if (current) lines.push(current);
//   if (lines.length === 0) lines.push(text);

//   const totalHeightPx = paddingYPx * 2 + lines.length * lineHeightPx;

//   // ── Step 2: Render at 2× resolution ──────────────────────────────────
//   const cvs = document.createElement("canvas");
//   cvs.width  = Math.ceil(widthPx * dpr);
//   cvs.height = Math.ceil(totalHeightPx * dpr);

//   const ctx = cvs.getContext("2d")!;
//   ctx.scale(dpr, dpr);

//   // Background (highlight color for matched sentences)
//   if (bgColor && bgColor !== "transparent") {
//     ctx.fillStyle = bgColor;
//     ctx.fillRect(0, 0, widthPx, totalHeightPx);
//   }

//   // ── Step 3: Draw text — browser applies HarfBuzz shaping here ────────
//   // This is the key: fillText() → GSUB conjuncts + GPOS diacritics = correct
//   ctx.font         = `${fontSizePx}px ${CANVAS_FONT_FAMILY}`;
//   ctx.fillStyle    = textColor;
//   ctx.textBaseline = "top";

//   lines.forEach((line, i) => {
//     ctx.fillText(line, paddingXPx, paddingYPx + i * lineHeightPx);
//   });

//   const heightMm = totalHeightPx / PX_PER_MM;

//   return {
//     dataUrl: cvs.toDataURL("image/png"),
//     widthMm,
//     heightMm,
//   };
// }

// /* ─────────────────────────────────────────────────────────────────
//    MIXED-SCRIPT LINE SPLITTER (for Latin sections)
// ───────────────────────────────────────────────────────────────── */

// function splitLatinLines(pdf: jsPDF, text: string, maxW: number): string[] {
//   return pdf.splitTextToSize(text, maxW);
// }

// /* ─────────────────────────────────────────────────────────────────
//    COLOUR SYSTEM
// ───────────────────────────────────────────────────────────────── */

// // CSS colors for canvas backgrounds (Indic path)
// const SOURCE_BG_CSS = [
//   "rgba(255,178,178,1)", "rgba(178,210,255,1)", "rgba(178,255,188,1)",
//   "rgba(255,225,153,1)", "rgba(222,178,255,1)", "rgba(255,178,229,1)",
//   "rgba(153,240,235,1)", "rgba(255,240,153,1)",
// ];

// // jsPDF RGB arrays for Latin path
// const SOURCE_BG: [number,number,number][] = [
//   [255,178,178],[178,210,255],[178,255,188],[255,225,153],
//   [222,178,255],[255,178,229],[153,240,235],[255,240,153],
// ];
// const SOURCE_DARK: [number,number,number][] = [
//   [180,30,30],[20,90,200],[20,140,50],[180,120,0],
//   [120,30,190],[180,20,120],[0,140,130],[160,130,0],
// ];

// /* ─────────────────────────────────────────────────────────────────
//    MAIN EXPORT
// ───────────────────────────────────────────────────────────────── */

// export async function generateAndDownloadReport(
//   r: AnalysisResult,
//   submittedBy: string,
//   originalFileName?: string,
//   extractedText?: string,
//   sentenceSourceMapParam?: Record<string, number>
// ) {
//   const sentenceMap: Record<string, number> =
//     sentenceSourceMapParam ?? (r as any).sentence_source_map ?? {};

//   // Load fonts in parallel
//   const pdf = new jsPDF("p", "mm", "a4");
//   const [fontName] = await Promise.all([
//     loadJsPDFFont(pdf),
//     ensureCanvasFont(),        // preloads Telugu font for canvas rendering
//   ]);

//   const marginX  = 15;
//   const marginR  = 15;
//   const pageW    = pdf.internal.pageSize.width;
//   const pageH    = pdf.internal.pageSize.height;
//   const contentW = pageW - marginX - marginR;
//   let y = 15;

//   /* ── layout helpers ──────────────────────────────────── */

//   const newPage = (need = 10) => {
//     if (y + need > pageH - 18) { pdf.addPage(); y = 15; }
//   };

//   const fillRect = (
//     x: number, ry: number, w: number, h: number,
//     fill: [number,number,number], stroke?: [number,number,number]
//   ) => {
//     pdf.setFillColor(...fill);
//     pdf.setDrawColor(...(stroke ?? fill));
//     pdf.rect(x, ry, w, h, stroke ? "FD" : "F");
//   };

//   const setFont = (bold = false) =>
//     pdf.setFont(fontName, bold ? "bold" : "normal");

//   // Latin text only — do NOT use for Indic text
//   const txt = (
//     t: string, x: number, ry: number,
//     o?: { size?: number; bold?: boolean; color?: [number,number,number]; align?: "left"|"center"|"right" }
//   ) => {
//     const { size=10, bold=false, color=[0,0,0] as [number,number,number], align="left" } = o ?? {};
//     pdf.setFontSize(size);
//     setFont(bold);
//     pdf.setTextColor(...color);
//     pdf.text(t, x, ry, { align });
//   };

//   /**
//    * Render a text block that MAY contain Indic characters.
//    *
//    * • Indic text  → canvas PNG image (correct OpenType shaping)
//    * • Latin text  → jsPDF text (fast, searchable)
//    *
//    * Returns new Y position after rendering.
//    */
//   const renderTextBlock = (
//     text: string,
//     x: number,
//     startY: number,
//     maxW: number,
//     options?: {
//       size?: number;
//       color?: [number,number,number];
//       bgCssColor?: string;    // for Indic highlight backgrounds
//       lineH?: number;
//     }
//   ): number => {
//     const { size=9, color=[0,0,0] as [number,number,number], bgCssColor, lineH=5.5 } = options ?? {};

//     if (isIndic(text)) {
//       // ── Canvas image path (Telugu, Hindi, Tamil, etc.) ──────────────
//       // fontSizePx calibration: jsPDF 9pt ≈ 22px canvas for same visual size
//       const fontPxMap: Record<number,number> = { 8:20, 9:22, 10:26, 11:28 };
//       const fontSizePx  = fontPxMap[size] ?? 22;
//       const lineHeightPx = Math.round(fontSizePx * 1.45);

//       const block = renderIndicToPNG(text, {
//         widthMm:      maxW,
//         fontSizePx,
//         lineHeightPx,
//         bgColor:      bgCssColor ?? "transparent",
//         textColor:    `rgb(${color.join(",")})`,
//         paddingXPx:   2,
//         paddingYPx:   2,
//       });

//       newPage(block.heightMm + 2);
//       pdf.addImage(block.dataUrl, "PNG", x, startY - 1, block.widthMm, block.heightMm);
//       return startY + block.heightMm;

//     } else {
//       // ── jsPDF text path (Latin / ASCII) ─────────────────────────────
//       pdf.setFontSize(size);
//       setFont(false);
//       pdf.setTextColor(...color);
//       const lines = splitLatinLines(pdf, text, maxW);
//       let cy = startY;
//       for (const line of lines) {
//         newPage(lineH + 2);
//         pdf.text(line, x, cy);
//         cy += lineH;
//       }
//       return cy;
//     }
//   };

//   const section = (label: string, need = 18) => {
//     newPage(need);
//     txt(label, marginX, y, { size:10, bold:true, color:[30,50,100] });
//     y += 2;
//     pdf.setDrawColor(30,50,100); pdf.setLineWidth(0.4);
//     pdf.line(marginX, y, pageW - marginR, y);
//     y += 6;
//   };

//   const webSources = (r.matched_sources ?? []).filter(s => s.type === "web");
//   const intSources = (r.matched_sources ?? []).filter(s => s.type !== "web");
//   const ai   = r.ai_detected_percentage   ?? 0;
//   const web  = r.web_source_percentage    ?? 0;
//   const orig = r.human_written_percentage ?? 0;

//   /* ── 1. HEADER ───────────────────────────────────────── */
//   fillRect(0, 0, pageW, 22, [30,50,100]);
//   txt("PLAGIARISM ANALYSIS REPORT", pageW/2, 10,
//     { size:16, bold:true, color:[255,255,255], align:"center" });
//   txt("TKREC Plagiarism Analysis System", pageW/2, 17,
//     { size:9, color:[180,200,255], align:"center" });
//   y = 28;

//   /* ── 2. PAPER DETAILS TABLE ──────────────────────────── */
//   const rows: [string, string][] = [
//     ["File Name",     originalFileName ?? "N/A"],
//     ["Document ID",   String(r.document_id)],
//     ["Submitted By",  submittedBy],
//     ["Analysis Date", new Date(r.analysis_date).toLocaleString()],
//   ];
//   const labelW = 45, rowH = 8;

//   fillRect(marginX, y, contentW, rowH, [30,50,100]);
//   txt("Paper Details", marginX+2, y+5.5, { size:9, bold:true, color:[255,255,255] });
//   txt("Result",        marginX+labelW+2, y+5.5, { size:9, bold:true, color:[255,255,255] });
//   y += rowH;

//   rows.forEach(([label, val], i) => {
//     const bg: [number,number,number] = i%2===0 ? [245,247,252] : [255,255,255];
//     fillRect(marginX, y, contentW, rowH, bg, [210,215,230]);
//     txt(label, marginX+2, y+5.5, { size:8, bold:true, color:[50,70,120] });

//     if (isIndic(val)) {
//       // File name contains Telugu — render as canvas image in cell
//       const block = renderIndicToPNG(val, {
//         widthMm:      contentW - labelW - 4,
//         fontSizePx:   18,
//         lineHeightPx: 24,
//         bgColor:      "transparent",
//         textColor:    "#1e1e1e",
//         paddingXPx:   2,
//         paddingYPx:   1,
//       });
//       pdf.addImage(block.dataUrl, "PNG", marginX+labelW+2, y+0.5, block.widthMm, Math.min(block.heightMm, rowH-1));
//     } else {
//       const lines = splitLatinLines(pdf, val, contentW-labelW-4);
//       txt(String(lines[0] ?? val), marginX+labelW+2, y+5.5, { size:8, color:[30,30,30] });
//     }
//     y += rowH;
//   });
//   y += 6;

//   /* ── 3. RESULT SUMMARY BOXES ─────────────────────────── */
//   newPage(50);
//   txt("RESULT SUMMARY", marginX, y, { size:11, bold:true, color:[30,50,100] });
//   y += 7;

//   const boxes = [
//     { label:"AI Probability", val:ai,   bg:[255,235,235] as [number,number,number], fg:[180,20,20]  as [number,number,number], bd:[220,150,150] as [number,number,number] },
//     { label:"Plagiarism",     val:web,  bg:[255,248,220] as [number,number,number], fg:[160,100,0]  as [number,number,number], bd:[220,190,100] as [number,number,number] },
//     { label:"Originality",    val:orig, bg:[230,255,235] as [number,number,number], fg:[20,140,60]  as [number,number,number], bd:[130,200,150] as [number,number,number] },
//   ];
//   const bw = (contentW-8)/3, bh = 26;
//   boxes.forEach((b, i) => {
//     const bx = marginX + i*(bw+4);
//     fillRect(bx, y, bw, bh, b.bg, b.bd);
//     txt(`${b.val.toFixed(2)}%`, bx+bw/2, y+13, { size:22, bold:true, color:b.fg, align:"center" });
//     txt(b.label, bx+bw/2, y+21, { size:8.5, bold:true, color:[80,80,80], align:"center" });
//   });
//   y += bh + 7;

//   newPage(12);
//   const [vLabel, vColor]: [string,[number,number,number]] =
//     web >= 75 ? ["Very high plagiarized content detected", [180,30,30]] :
//     web >= 50 ? ["High similarity to external sources",    [180,100,0]] :
//     web >= 25 ? ["Moderate similarity detected",           [150,130,0]] :
//                 ["Low similarity — likely original",        [30,140,60]];
//   fillRect(marginX, y, contentW, 10, [245,245,250], [200,205,220]);
//   txt(`Assessment: ${vLabel}`, marginX+4, y+6.5, { size:8.5, bold:true, color:vColor });
//   y += 14;

//   newPage(36);
//   txt("Score Breakdown", marginX, y, { size:9, bold:true, color:[30,50,100] });
//   y += 5;
//   ([
//     { label:"AI Generated Content", pct:ai,   color:[210,60,60]  as [number,number,number] },
//     { label:"Plagiarism Score",     pct:web,  color:[210,160,30] as [number,number,number] },
//     { label:"Original Content",     pct:orig, color:[50,170,80]  as [number,number,number] },
//   ]).forEach(b => {
//     newPage(10);
//     txt(b.label, marginX, y, { size:8, bold:true, color:[50,50,50] });
//     const barX = marginX+52, barW = contentW-52-18;
//     fillRect(barX, y-4, barW, 5, [230,230,230]);
//     const bFill = Math.max(0, (b.pct/100)*barW);
//     if (bFill>0) fillRect(barX, y-4, bFill, 5, b.color);
//     txt(`${b.pct.toFixed(2)}%`, barX+barW+2, y, { size:8, bold:true, color:b.color });
//     y += 8;
//   });
//   y += 4;

//   /* ── 4. METHODOLOGY ──────────────────────────────────── */
//   section("METHODOLOGY");
//   [
//     "• AI detection using roberta-base transformer model (OpenAI detector)",
//     "• Web similarity via Google Custom Search Engine (indexed public sources)",
//     "• Local institutional database comparison (TF-IDF cosine similarity)",
//     "• Text extraction: pdfplumber, Tesseract OCR, python-docx, pandas",
//   ].forEach(line => { newPage(7); txt(line, marginX+2, y, { size:9, color:[50,50,50] }); y += 6; });
//   y += 3;

//   /* ── 5. MARKED TEXT ──────────────────────────────────────
//      ★ KEY SECTION — Indic text rendered via canvas images
//        so every Telugu diacritic, conjunct, and vowel sign
//        appears exactly as it does in the original document.
//   ─────────────────────────────────────────────────────── */
//   const rawText = (extractedText ?? "").trim();

//   if (rawText.length > 0) {
//     section("MARKED TEXT");

//     const hasSentenceMap = Object.keys(sentenceMap).length > 0;
//     const docIsIndic     = isIndic(rawText);

//     // Sentence splitting: include Indic daṇḍa (।) for Hindi/Sanskrit
//     const sentences = rawText
//       .replace(/\r\n|\r/g, "\n")
//       .split(docIsIndic
//         ? /(?<=[।.!?])\s+|\n\n+/
//         : /(?<=[.!?])\s+|\n\n+/
//       )
//       .filter(s => s.trim().length > 0);

//     sentences.forEach((sentence, sentIdx) => {
//       const trimmed = sentence.trim();
//       if (!trimmed) { y += 3; return; }

//       // Determine highlight color for this sentence
//       let bgIdx: number | null = null;

//       if (hasSentenceMap) {
//         const idx = sentenceMap[sentence] ?? sentenceMap[trimmed];
//         if (idx !== undefined) bgIdx = idx;
//       } else if (web >= 20 && webSources.length > 0) {
//         const total  = sentences.length;
//         const aiFrac = ai >= 60 ? Math.min(ai/100*0.5, 0.45) : 0;
//         const wFrac  = Math.min(web/100*0.75, 0.6);
//         if (sentIdx < Math.floor(total*aiFrac)) {
//           bgIdx = -1; // AI highlight (red)
//         } else if (sentIdx < Math.floor(total*(aiFrac+wFrac))) {
//           bgIdx = (sentIdx - Math.floor(total*aiFrac)) % webSources.length;
//         }
//       }

//       newPage(8);

//       if (isIndic(trimmed)) {
//         // ── CANVAS IMAGE PATH — correct OpenType shaping ─────────────
//         const bgCssColor = bgIdx === -1
//           ? "rgba(255,185,185,1)"
//           : bgIdx !== null
//             ? SOURCE_BG_CSS[bgIdx % SOURCE_BG_CSS.length]
//             : "transparent";

//         const block = renderIndicToPNG(trimmed + " ", {
//           widthMm:      contentW,
//           fontSizePx:   22,
//           lineHeightPx: 30,
//           bgColor:      bgCssColor,
//           textColor:    "#000000",
//           paddingXPx:   4,
//           paddingYPx:   3,
//         });

//         newPage(block.heightMm + 2);
//         pdf.addImage(block.dataUrl, "PNG", marginX, y, block.widthMm, block.heightMm);
//         y += block.heightMm + 1;

//       } else {
//         // ── jsPDF text path for Latin sentences ──────────────────────
//         const bgColor: [number,number,number] | null =
//           bgIdx === -1 ? [255,185,185] :
//           bgIdx !== null ? SOURCE_BG[bgIdx % SOURCE_BG.length] : null;

//         const lines = splitLatinLines(pdf, trimmed + " ", contentW);
//         lines.forEach((line: string) => {
//           newPage(7);
//           if (bgColor) fillRect(marginX, y-4.5, contentW, 6.2, bgColor);
//           pdf.setTextColor(0,0,0);
//           setFont(false);
//           pdf.setFontSize(8.5);
//           pdf.text(line, marginX, y);
//           y += 5.5;
//         });
//         y += 1;
//       }
//     });
//     y += 6;
//   }

//   /* ── 6. MATCHED SOURCES ──────────────────────────────── */
//   if ((r.matched_sources ?? []).length > 0) {
//     section("MATCHED SOURCES");

//     if (webSources.length > 0) {
//       txt("Web Sources", marginX, y, { size:9, bold:true, color:[50,80,160] });
//       y += 7;

//       webSources.forEach((src, i) => {
//         newPage(14);
//         const bg   = SOURCE_BG[i   % SOURCE_BG.length];
//         const dark = SOURCE_DARK[i % SOURCE_DARK.length];
//         fillRect(marginX, y-4.5, 8, 6.5, bg, dark);
//         pdf.setFontSize(8); setFont(true);
//         pdf.setTextColor(...dark);
//         pdf.text(`${i+1}`, marginX+4, y, { align:"center" });

//         const urlLines = splitLatinLines(pdf, src.source, contentW-12);
//         pdf.setFontSize(8.5); setFont(false);
//         pdf.setTextColor(0,0,180);
//         urlLines.forEach((line: string, li: number) => {
//           newPage(7);
//           if (li===0) pdf.textWithLink(line, marginX+11, y, { url:src.source });
//           else        pdf.text(line, marginX+11, y);
//           y += 6;
//         });
//         y += 2;
//       });
//     }

//     if (intSources.length > 0) {
//       y += 3;
//       txt("Internal Database Matches", marginX, y, { size:9, bold:true, color:[100,60,0] });
//       y += 6;
//       intSources.forEach((src, i) => {
//         newPage(8);
//         fillRect(marginX, y-4, 8, 6.5, [220,180,100], [160,110,0]);
//         pdf.setFontSize(8); setFont(true);
//         pdf.setTextColor(160,110,0);
//         pdf.text(`${i+1}`, marginX+4, y, { align:"center" });
//         txt(`Internal Match — ${src.source}`, marginX+11, y, { size:8, color:[80,50,0] });
//         y += 8;
//       });
//     }
//     y += 4;
//   }

//   /* ── 7. LIMITATIONS ──────────────────────────────────── */
//   section("LIMITATIONS & DISCLAIMER");
//   [
//     "• AI detection is probabilistic — results are indicative, not definitive",
//     "• Web similarity scores are based on publicly indexed sources only",
//     "• Similarity percentages are analytical indicators, not accusations of misconduct",
//     "• Highlighted text shows suspected AI / plagiarised regions; colours match Source legend",
//     "• Text with NO highlight = estimated original / unmatched content",
//     "• Scanned documents may have reduced accuracy due to OCR limitations",
//     "• Final academic integrity decisions require human review and judgement",
//   ].forEach(line => { newPage(7); txt(line, marginX+2, y, { size:8, color:[80,80,80] }); y += 6; });

//   /* ── 8. FOOTER ON EVERY PAGE ─────────────────────────── */
//   const total = (pdf.internal as any).getNumberOfPages();
//   for (let p = 1; p <= total; p++) {
//     pdf.setPage(p);
//     fillRect(0, pageH-12, pageW, 12, [30,50,100]);
//     pdf.setFontSize(7.5); setFont(false);
//     pdf.setTextColor(200,210,255);
//     pdf.text("Generated by TKREC Plagiarism Analysis System — Academic Use Only",
//       pageW/2, pageH-4.5, { align:"center" });
//     pdf.setTextColor(180,190,230);
//     pdf.text(`Page ${p} of ${total}`, pageW-marginR, pageH-4.5, { align:"right" });
//   }

//   /* ── 9. SAVE ─────────────────────────────────────────── */
//   const safeName = (originalFileName ?? `document-${r.document_id}`)
//     .replace(/[\/\\?%*:|"<>]/g, "-");
//   pdf.save(`${safeName}-plagiarism-report.pdf`);
// }

















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
   HIGHLIGHT COLOUR SYSTEM
   
   Issue 5 Requirement:
   • Plagiarism (web match)  → RED background    (#FFD6D6 / rgb 255,214,214)
   • AI-generated content    → YELLOW background (#FFF5B0 / rgb 255,245,176)
   • Original content        → No highlight (white background)
   
   Per-source colouring (for the source legend):
   Multiple web sources get different shades of red so the user can
   tell which source each sentence matched.
───────────────────────────────────────────────────────────────── */

// Issue 5: Plagiarism = RED tones
const PLAGIARISM_BG_CSS   = "rgba(255,80,80,0.25)";   // light red for canvas path
const PLAGIARISM_BG_RGB: [number,number,number] = [255, 214, 214]; // light red for jsPDF path

// Issue 5: AI content = YELLOW tones
const AI_BG_CSS   = "rgba(255,230,0,0.35)";            // yellow for canvas path
const AI_BG_RGB: [number,number,number] = [255, 245, 176]; // yellow for jsPDF path

// Per-source variant reds (for multi-source identification)
const SOURCE_BG_CSS = [
  "rgba(255,80,80,0.25)",   "rgba(255,100,60,0.25)",
  "rgba(255,60,100,0.25)",  "rgba(240,80,130,0.25)",
  "rgba(255,120,80,0.25)",  "rgba(200,60,80,0.25)",
  "rgba(230,100,100,0.25)", "rgba(255,80,150,0.25)",
];
const SOURCE_BG: [number,number,number][] = [
  [255,214,214],[255,205,190],[255,200,210],[245,200,220],
  [255,215,195],[240,200,205],[235,210,210],[255,205,225],
];
const SOURCE_DARK: [number,number,number][] = [
  [180,30,30],[180,70,20],[180,20,70],[160,20,80],
  [180,80,30],[150,20,50],[140,60,60],[180,20,90],
];

/* ─────────────────────────────────────────────────────────────────
   SENTENCE CLASSIFICATION — DETERMINES HIGHLIGHT TYPE
   
   Classification priority:
   1. If sentence appears in sentence_source_map → plagiarism (RED)
   2. If sentence is AI-generated (from ai_sentence_map) → AI (YELLOW)
   3. Otherwise → original (no highlight)
───────────────────────────────────────────────────────────────── */

type HighlightType = "plagiarism" | "ai" | "original";

interface SentenceHighlight {
  type: HighlightType;
  sourceIndex: number | null;  // which web source (for plagiarism), null for AI/original
}

function classifySentence(
  sentence: string,
  trimmed: string,
  sentIdx: number,
  totalSentences: number,
  sentenceSourceMap: Record<string, number>,
  aiSentenceMap: Record<string, boolean>,
  ai: number,
  web: number,
  webSourceCount: number,
): SentenceHighlight {
  // Priority 1: Explicit plagiarism match from sentence_source_map
  const sourceIdx = sentenceSourceMap[sentence] ?? sentenceSourceMap[trimmed];
  if (sourceIdx !== undefined) {
    return { type: "plagiarism", sourceIndex: sourceIdx };
  }

  // Priority 2: Explicit AI flag from ai_sentence_map (if available)
  const isAI = aiSentenceMap[sentence] ?? aiSentenceMap[trimmed];
  if (isAI) {
    return { type: "ai", sourceIndex: null };
  }

  // Priority 3: Probabilistic fallback when no explicit maps are provided
  // This is used when the backend doesn't supply sentence-level maps.
  // Uses aggregate score percentages to estimate which sentences to highlight.
  const hasExplicitMap = Object.keys(sentenceSourceMap).length > 0;
  if (!hasExplicitMap && (ai > 0 || web > 0)) {
    const aiFrac = ai >= 10 ? Math.min(ai / 100, 0.9) : 0;
    const wFrac  = web >= 5  ? Math.min(web / 100 * 0.85, 0.85) : 0;
    const aiEnd  = Math.floor(totalSentences * aiFrac);
    const webEnd = Math.floor(totalSentences * (aiFrac + wFrac));

    if (sentIdx < aiEnd) {
      return { type: "ai", sourceIndex: null };
    }
    if (sentIdx < webEnd && webSourceCount > 0) {
      const idx = (sentIdx - aiEnd) % webSourceCount;
      return { type: "plagiarism", sourceIndex: idx };
    }
  }

  return { type: "original", sourceIndex: null };
}

/* ─────────────────────────────────────────────────────────────────
   WEB SOURCE MATCH DATA EXTRACTION
   
   The new google_search.py returns per-URL verbatim match percentages.
   This function extracts them from the AnalysisResult for display in the report.
───────────────────────────────────────────────────────────────── */

interface WebSourceMatch {
  source: string;
  type: string;
  match_pct?: number;  // per-URL verbatim match percentage from google_search.py
}

function getWebSources(r: AnalysisResult): WebSourceMatch[] {
  return (r.matched_sources ?? [])
    .filter(s => s.type === "web")
    .map(s => ({
      source:    s.source,
      type:      s.type,
      match_pct: (s as any).match_pct ?? (s as any).verbatim_match_pct ?? undefined,
    }));
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
  const webSources    = getWebSources(r);
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
     
     Issue 5 Requirement:
     • Plagiarism text → Red background
     • AI-generated text → Yellow background
     • Original text → No highlight
     • Original document formatting PRESERVED (headings, paragraphs, structure)
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  const rawText = (extractedText ?? "").trim();

  if (rawText.length > 0) {
    section("MARKED TEXT");

    const docIsIndic = isIndic(rawText);

    // ── Paragraph-aware splitting ─────────────────────────────────────
    // We preserve formatting by splitting on paragraph breaks FIRST,
    // then sentences within each paragraph.
    // This ensures headings, section titles, and paragraph structure are kept.

    interface TextBlock {
      type: "heading" | "paragraph_break" | "sentence";
      text: string;
    }

    const textBlocks: TextBlock[] = [];

    // Split into paragraphs first (double newline = paragraph break)
    const paragraphs = rawText
      .replace(/\r\n|\r/g, "\n")
      .split(/\n{2,}/);

    for (const para of paragraphs) {
      const paraText = para.trim();
      if (!paraText) {
        textBlocks.push({ type: "paragraph_break", text: "" });
        continue;
      }

      // Detect headings: short lines (< 80 chars) that don't end with a period
      // and are followed by paragraph content. These are section titles.
      const isHeading = (
        paraText.length < 100 &&
        !paraText.endsWith(".") &&
        !paraText.endsWith(",") &&
        paraText === paraText.replace(/\n/g, " ").trim() && // single line
        /^[A-Z0-9\s\-–:\.]{3,}$/.test(paraText.trim()) // all-caps or title-like
      );

      if (isHeading) {
        textBlocks.push({ type: "heading", text: paraText });
        continue;
      }

      // Split paragraph into sentences
      const sentenceSplitRe = docIsIndic
        ? /(?<=[।.!?])\s+|\n/
        : /(?<=[.!?])\s+|\n/;

      const sentences = paraText
        .split(sentenceSplitRe)
        .map(s => s.trim())
        .filter(s => s.length > 0);

      for (const sent of sentences) {
        textBlocks.push({ type: "sentence", text: sent });
      }

      // Add paragraph break after each paragraph
      textBlocks.push({ type: "paragraph_break", text: "" });
    }

    // Count only actual sentence blocks for probabilistic classification
    const sentenceBlocks = textBlocks.filter(b => b.type === "sentence");
    const totalSentences = sentenceBlocks.length;
    let sentIdx = 0;

    // ── Render each block ─────────────────────────────────────────────
    for (const block of textBlocks) {
      if (block.type === "paragraph_break") {
        y += 4;   // Paragraph spacing — preserves paragraph structure
        continue;
      }

      if (block.type === "heading") {
        // ── Heading: render bold, no highlight, slightly larger font ───
        newPage(12);
        y += 3;

        if (isIndic(block.text)) {
          const headingBlock = renderIndicToPNG(block.text, {
            widthMm: contentW, fontSizePx: 26, lineHeightPx: 34,
            bgColor: "transparent", textColor: "#1a2a5a",
            paddingXPx: 0, paddingYPx: 2,
          });
          newPage(headingBlock.heightMm + 4);
          pdf.addImage(headingBlock.dataUrl, "PNG", marginX, y, headingBlock.widthMm, headingBlock.heightMm);
          y += headingBlock.heightMm + 2;
        } else {
          const headingLines = splitLatinLines(pdf, block.text, contentW);
          for (const line of headingLines) {
            newPage(8);
            txt(line, marginX, y, { size:10, bold:true, color:[20,40,90] });
            y += 6.5;
          }
        }
        y += 2;
        continue;
      }

      // ── Sentence: classify and apply highlight ──────────────────────
      const trimmed = block.text.trim();
      if (!trimmed) continue;

      const highlight = classifySentence(
        block.text, trimmed, sentIdx, totalSentences,
        sentenceMap, aiSentenceMap, ai, web, webSources.length,
      );
      sentIdx++;

      if (isIndic(trimmed)) {
        // Canvas image path (correct OpenType shaping for Indic scripts)
        const bgCssColor =
          highlight.type === "plagiarism"
            ? (highlight.sourceIndex !== null
                ? SOURCE_BG_CSS[highlight.sourceIndex % SOURCE_BG_CSS.length]
                : PLAGIARISM_BG_CSS)
            : highlight.type === "ai"
              ? AI_BG_CSS
              : "transparent";

        const indicBlock = renderIndicToPNG(trimmed + " ", {
          widthMm: contentW, fontSizePx:22, lineHeightPx:30,
          bgColor: bgCssColor, textColor:"#000000",
          paddingXPx:4, paddingYPx:3,
        });

        newPage(indicBlock.heightMm + 2);
        pdf.addImage(indicBlock.dataUrl, "PNG", marginX, y, indicBlock.widthMm, indicBlock.heightMm);
        y += indicBlock.heightMm + 1;

      } else {
        // jsPDF text path for Latin/ASCII sentences
        const bgColor: [number,number,number] | null =
          highlight.type === "plagiarism"
            ? (highlight.sourceIndex !== null
                ? SOURCE_BG[highlight.sourceIndex % SOURCE_BG.length]
                : PLAGIARISM_BG_RGB)
            : highlight.type === "ai"
              ? AI_BG_RGB
              : null;

        const lines = splitLatinLines(pdf, trimmed + " ", contentW);
        for (const line of lines) {
          newPage(7);
          if (bgColor) fillRect(marginX, y-4.5, contentW, 6.2, bgColor);
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
     6. MATCHED SOURCES — WITH PER-URL VERBATIM MATCH PERCENTAGE
     
     Issue 5 Requirement: Display match% for each scraped URL.
     The match% comes from google_search.py's verbatim_match_percentage().
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  if ((r.matched_sources ?? []).length > 0) {
    section("MATCHED SOURCES");

    if (webSources.length > 0) {
      txt("Web Sources", marginX, y, { size:9, bold:true, color:[150,20,20] });
      y += 7;

      webSources.forEach((src, i) => {
        newPage(18);
        const bg   = SOURCE_BG[i   % SOURCE_BG.length];
        const dark = SOURCE_DARK[i % SOURCE_DARK.length];

        // Source number badge
        fillRect(marginX, y-4.5, 8, 7, bg, dark);
        pdf.setFontSize(8); setFont(true); pdf.setTextColor(...dark);
        pdf.text(`${i+1}`, marginX+4, y, { align:"center" });

        // ── Per-URL verbatim match percentage (Issue 5 requirement) ───
        // Displayed prominently in a colored badge
        const matchPct = src.match_pct;
        if (matchPct !== undefined) {
          const pctColor: [number,number,number] =
            matchPct >= 20 ? [180,20,20] :
            matchPct >= 10 ? [180,100,0] :
            matchPct >= 5  ? [150,130,0] :
                             [80,80,80];
          // Badge: "14.3% match"
          const badgeText = `${matchPct.toFixed(1)}% verbatim match`;
          fillRect(marginX+contentW-35, y-5, 35, 7, bg, dark);
          txt(badgeText, marginX+contentW-33, y, { size:7.5, bold:true, color:pctColor });
        }

        // URL (clickable link)
        const urlLines = splitLatinLines(pdf, src.source, contentW - 50);
        pdf.setFontSize(8.5); setFont(false); pdf.setTextColor(0,0,180);
        urlLines.forEach((line: string, li: number) => {
          newPage(7);
          if (li===0) pdf.textWithLink(line, marginX+11, y, { url:src.source });
          else        pdf.text(line, marginX+11, y);
          y += 6;
        });

        y += 2;
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