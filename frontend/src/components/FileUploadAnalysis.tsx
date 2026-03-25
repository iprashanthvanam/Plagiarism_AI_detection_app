
/**
 * FileUploadAnalysis.tsx  — BATCH UPLOAD + PARALLEL POLLING
 *
 * WHAT CHANGED:
 * ─────────────────────────────────────────────────────────────
 * OLD flow (sequential, blocking):
 *   for each file:
 *     await POST /upload        ← one file at a time, includes extraction
 *     await POST /analyze/{id}  ← triggers one Celery task
 *     poll /analysis-status     ← wait for that one task to finish
 *     only then start next file
 *
 * NEW flow (batch, parallel):
 *   1. Collect ALL pending files
 *   2. POST /upload-batch  ← single request with all files in FormData
 *      Backend saves every file to disk, creates DB records, and
 *      immediately enqueues a process_document Celery task per file.
 *      Returns { document_ids: [25, 26, 27] }  ← instant (<200ms)
 *   3. Map document_ids back to local file entries
 *   4. Start independent pollWithBackoff() for EVERY id simultaneously
 *      Each file shows its own live progress as its worker advances.
 *
 * RESULT:
 *   3 files uploaded → 3 workers start simultaneously →
 *   all 3 show "Analysing..." in parallel → each completes independently.
 *   Total wall-clock time ≈ time for the SLOWEST single file,
 *   not the sum of all files.
 * ─────────────────────────────────────────────────────────────
 */ 



import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Upload,
  FileText,
  Image,
  BarChart3,
  CheckCircle,
  AlertCircle,
  Clock,
  Download,
  X,
  File,
  Loader2,
  Globe,
  Database,
  Search,
} from "lucide-react";

import { Button }   from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge }    from "@/components/ui/badge";
import { Alert }    from "@/components/ui/alert";
import api          from "@/lib/api";

import { AnalysisResult, AnalysisStatus } from "@/lib/types";
import { generateAndDownloadReport }      from "@/lib/reportGenerator";

/* ─────────────────────────────────────────────────────────────
   CONFIG
───────────────────────────────────────────────────────────── */
const MAX_FILE_SIZE_BYTES   = 50 * 1024 * 1024;  // 50 MB
const POLLING_INITIAL_DELAY = 2_000;               // ms
const POLLING_MAX_DELAY     = 10_000;              // ms
const POLLING_BACKOFF       = 1.5;
const POLLING_MAX_RETRIES   = 60;                  // ~10 min at max delay

const SUPPORTED_TYPES = {
  "application/pdf": {
    icon: FileText, label: "PDF", color: "bg-red-50 text-red-600 border-red-100",
  },
  "application/msword": {
    icon: FileText, label: "DOC", color: "bg-blue-50 text-blue-600 border-blue-100",
  },
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
    icon: FileText, label: "DOCX", color: "bg-blue-50 text-blue-600 border-blue-100",
  },
  "application/vnd.ms-excel": {
    icon: BarChart3, label: "XLS", color: "bg-green-50 text-green-600 border-green-100",
  },
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
    icon: BarChart3, label: "XLSX", color: "bg-green-50 text-green-600 border-green-100",
  },
  "application/vnd.ms-powerpoint": {
    icon: Image, label: "PPT", color: "bg-orange-50 text-orange-600 border-orange-100",
  },
  "application/vnd.openxmlformats-officedocument.presentationml.presentation": {
    icon: Image, label: "PPTX", color: "bg-orange-50 text-orange-600 border-orange-100",
  },
  "text/plain": {
    icon: FileText, label: "TXT", color: "bg-slate-100 text-slate-600 border-slate-200",
  },
  "image/jpeg": {
    icon: Image, label: "JPEG", color: "bg-purple-50 text-purple-600 border-purple-100",
  },
  "image/png": {
    icon: Image, label: "PNG", color: "bg-purple-50 text-purple-600 border-purple-100",
  },
} as const;

/* ─────────────────────────────────────────────────────────────
   TYPES
───────────────────────────────────────────────────────────── */
interface UploadedFile {
  file:       File;
  id:         string;   // local UUID — never sent to backend
  status:     "pending" | "uploading" | "analyzing" | "completed" | "error";
  progress:   number;
  analysisId?: string;  // document_id returned by backend
  result?:    AnalysisResult;
  error?:     string;
}

interface Props {
  userType:            "admin" | "student";
  userId:              string;
  onAnalysisComplete?: (r: AnalysisResult) => void;
}

/* ─────────────────────────────────────────────────────────────
   COMPONENT
───────────────────────────────────────────────────────────── */
export function FileUploadAnalysis({
  userType,
  userId,
  onAnalysisComplete,
}: Props) {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading,   setIsUploading]   = useState(false);
  const [isDragOver,    setIsDragOver]    = useState(false);

  // Map fileId → "still polling?" for cleanup on unmount / removal
  const pollRefs    = useRef<Map<string, boolean>>(new Map());
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => pollRefs.current.clear(), []);

  /* ── helpers ─────────────────────────────────────────────── */
  const generateId   = () => crypto.randomUUID();

  const formatFileSize = (bytes: number) =>
    bytes >= 1_048_576
      ? `${(bytes / 1_048_576).toFixed(1)} MB`
      : `${(bytes / 1024).toFixed(1)} KB`;

  const validateFile = (file: File): string | null => {
    if (file.size > MAX_FILE_SIZE_BYTES) return "File exceeds 50 MB limit";
    if (!(file.type in SUPPORTED_TYPES))  return "Unsupported file type";
    return null;
  };

  /* ── add files to local queue ────────────────────────────── */
  const handleFileSelect = (files: FileList | File[]) => {
    const next:   UploadedFile[] = [];
    const errors: string[]       = [];
    Array.from(files).forEach((file) => {
      const err = validateFile(file);
      if (err) errors.push(`${file.name}: ${err}`);
      else     next.push({ file, id: generateId(), status: "pending", progress: 0 });
    });
    if (errors.length) alert(errors.join("\n"));
    if (next.length)   setUploadedFiles((p) => [...p, ...next]);
  };

  const removeFile = (id: string) => {
    pollRefs.current.delete(id);
    setUploadedFiles((p) => p.filter((f) => f.id !== id));
  };

  /* ── poll one file until complete ───────────────────────────
     Exponential back-off: 2s → 3s → 4.5s → … → 10s cap.
     Stops when: completed | failed | max retries | component unmount.
  ─────────────────────────────────────────────────────────── */
  const pollWithBackoff = useCallback(
    async (fileId: string, documentId: string) => {
      let delay    = POLLING_INITIAL_DELAY;
      let attempts = 0;
      pollRefs.current.set(fileId, true);

      while (pollRefs.current.get(fileId) && attempts < POLLING_MAX_RETRIES) {
        try {
          const res    = await api.get(`/analysis-status/${documentId}`);
          const status: AnalysisStatus = res.data;

          if (status.status === "completed" && status.result) {
            pollRefs.current.delete(fileId);
            onAnalysisComplete?.(status.result);
            setUploadedFiles((p) =>
              p.map((f) =>
                f.id === fileId
                  ? { ...f, status: "completed", progress: 100, result: status.result }
                  : f
              )
            );
            return;
          }

          if (status.status === "failed") {
            pollRefs.current.delete(fileId);
            setUploadedFiles((p) =>
              p.map((f) =>
                f.id === fileId
                  ? { ...f, status: "error", error: status.error ?? "Analysis failed" }
                  : f
              )
            );
            return;
          }

          // Update progress while still running
          setUploadedFiles((p) =>
            p.map((f) =>
              f.id === fileId
                ? { ...f, progress: status.progress_percentage ?? f.progress }
                : f
            )
          );
        } catch (err: any) {
          // Network blip — keep retrying
          console.warn(`Poll attempt ${attempts} for doc ${documentId}:`, err?.message);
        }

        await new Promise((r) => setTimeout(r, delay));
        delay    = Math.min(delay * POLLING_BACKOFF, POLLING_MAX_DELAY);
        attempts++;
      }

      // Max retries reached without completion
      if (pollRefs.current.get(fileId)) {
        pollRefs.current.delete(fileId);
        setUploadedFiles((p) =>
          p.map((f) =>
            f.id === fileId
              ? { ...f, status: "error", error: "Analysis timed out. Please try again." }
              : f
          )
        );
      }
    },
    [onAnalysisComplete]
  );

  /* ─────────────────────────────────────────────────────────
     BATCH UPLOAD — core of the new architecture
     ─────────────────────────────────────────────────────────
     1. Collect all "pending" files.
     2. Set them all to "uploading" immediately (UI feedback).
     3. Build one FormData with all files appended under "files".
     4. POST /upload-batch → { document_ids: [25, 26, 27] }
        This is instant (<200 ms) — backend just saves to disk
        and enqueues process_document Celery tasks.
     5. Map each returned document_id to the matching local file entry.
     6. Set every file to "analyzing" with its document_id.
     7. Start pollWithBackoff() for EACH file independently.
        They all run concurrently via Promise — no awaiting each other.
  ───────────────────────────────────────────────────────────*/
  const handleBatchAnalyze = async () => {
    const pending = uploadedFiles.filter((f) => f.status === "pending");
    if (pending.length === 0) return;

    setIsUploading(true);

    // Mark all as "uploading"
    setUploadedFiles((p) =>
      p.map((f) =>
        f.status === "pending" ? { ...f, status: "uploading", progress: 5 } : f
      )
    );

    try {
      // Build single FormData with all files
      const formData = new FormData();
      pending.forEach((f) => formData.append("files", f.file));

      const res = await api.post<{ document_ids: number[] }>(
        "/upload-batch",
        formData,
        {
          // Show aggregate upload progress across all files
          onUploadProgress: (e: any) => {
            const pct = Math.round(((e.loaded ?? 0) * 20) / (e.total ?? 1));
            setUploadedFiles((p) =>
              p.map((f) =>
                f.status === "uploading" ? { ...f, progress: Math.max(5, pct) } : f
              )
            );
          },
        }
      );

      const { document_ids } = res.data;

      // Map returned ids back to local file entries (same order)
      pending.forEach((pendingFile, idx) => {
        const docId = String(document_ids[idx]);

        // Transition to "analyzing"
        setUploadedFiles((p) =>
          p.map((f) =>
            f.id === pendingFile.id
              ? { ...f, status: "analyzing", analysisId: docId, progress: 20 }
              : f
          )
        );

        // Start polling independently — NOT awaited here, so all polls
        // run concurrently in the background.
        pollWithBackoff(pendingFile.id, docId);
      });
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ?? err?.message ?? "Upload failed";

      // Mark ALL uploading files as error
      setUploadedFiles((p) =>
        p.map((f) =>
          f.status === "uploading" ? { ...f, status: "error", error: msg } : f
        )
      );
    } finally {
      setIsUploading(false);
    }
  };

  /* ── single-file analyze (for individual "Start Analysis" buttons) ──
     Wraps the single file in a batch call for consistency.
  ───────────────────────────────────────────────────────────────────── */
  const handleSingleAnalyze = async (f: UploadedFile) => {
    setUploadedFiles((p) =>
      p.map((x) =>
        x.id === f.id ? { ...x, status: "uploading", progress: 5 } : x
      )
    );

    try {
      const formData = new FormData();
      formData.append("files", f.file);

      const res = await api.post<{ document_ids: number[] }>(
        "/upload-batch",
        formData
      );

      const docId = String(res.data.document_ids[0]);
      setUploadedFiles((p) =>
        p.map((x) =>
          x.id === f.id
            ? { ...x, status: "analyzing", analysisId: docId, progress: 20 }
            : x
        )
      );
      pollWithBackoff(f.id, docId);
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ?? err?.message ?? "Upload failed";
      setUploadedFiles((p) =>
        p.map((x) =>
          x.id === f.id ? { ...x, status: "error", error: msg } : x
        )
      );
    }
  };

  /* ─────────────────────────────────────────────────────────
     RENDER
  ───────────────────────────────────────────────────────────*/
  const pendingCount  = uploadedFiles.filter((f) => f.status === "pending").length;
  const activeCount   = uploadedFiles.filter(
    (f) => f.status === "uploading" || f.status === "analyzing"
  ).length;

  return (
    <div className="space-y-8 font-sans">

      {/* ── UPLOAD ZONE ──────────────────────────────────────── */}
      <div
        className={`border-2 border-dashed rounded-3xl p-12 text-center transition-all duration-300 cursor-pointer flex flex-col items-center justify-center gap-4 group ${
          isDragOver
            ? "border-indigo-400 bg-white/20 scale-[1.02]"
            : "border-white/20 bg-white/5 hover:bg-white/10 hover:border-white/40"
        }`}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragOver(false);
          handleFileSelect(e.dataTransfer.files);
        }}
        onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
        onDragLeave={(e) => { e.preventDefault(); setIsDragOver(false); }}
        onClick={() => fileInputRef.current?.click()}
      >
        <div
          className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-500 shadow-xl ${
            isDragOver
              ? "bg-indigo-500 text-white rotate-12"
              : "bg-white/10 text-white group-hover:bg-black group-hover:text-white"
          }`}
        >
          <Upload className="h-10 w-10" strokeWidth={1.5} />
        </div>
        <div className="space-y-2">
          <p className="text-black font-bold text-xl tracking-tight">
            Click to upload or drag & drop
          </p>
          <p className="text-black text-sm font-medium">
            Supports PDF, DOCX, XLSX, Images (Max 50 MB) — multiple files at once
          </p>
        </div>
        <input
          type="file"
          multiple
          ref={fileInputRef}
          onChange={(e) => {
            if (e.target.files) handleFileSelect(e.target.files);
            e.target.value = "";
          }}
          className="hidden"
          accept=".pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.txt,.jpg,.jpeg,.png"
        />
      </div>

      {/* ── FILE QUEUE LIST ──────────────────────────────────── */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-4">

          {/* Header + batch action button */}
          <div className="flex justify-between items-center px-1">
            <h3 className="text-white font-bold text-sm uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-indigo-500" />
              Processing Queue ({uploadedFiles.length})
              {activeCount > 0 && (
                <span className="text-indigo-300 font-normal normal-case">
                  — {activeCount} running in parallel
                </span>
              )}
            </h3>

            {pendingCount > 0 && (
              <Button
                onClick={handleBatchAnalyze}
                disabled={isUploading}
                className="bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase px-5 py-2.5 h-auto shadow-lg shadow-indigo-500/30 rounded-xl transition-all hover:scale-105 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isUploading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Search className="w-4 h-4 mr-2" />
                )}
                {isUploading
                  ? "Uploading…"
                  : `Analyse ${pendingCount} File${pendingCount > 1 ? "s" : ""}`}
              </Button>
            )}
          </div>

          <div className="grid gap-4">
            {uploadedFiles.map((file) => {
              const type =
                SUPPORTED_TYPES[
                  file.file.type as keyof typeof SUPPORTED_TYPES
                ] ?? { icon: File, label: "FILE", color: "bg-slate-100 text-slate-600 border-slate-200" };

              return (
                <div
                  key={file.id}
                  className="bg-white/95 backdrop-blur-xl border border-white/50 rounded-2xl p-6 shadow-xl hover:shadow-2xl transition-all duration-300"
                >
                  {/* File header */}
                  <div className="flex justify-between items-start mb-5">
                    <div className="flex items-center gap-4">
                      <div
                        className={`w-12 h-12 rounded-xl flex items-center justify-center border ${type.color} bg-opacity-30`}
                      >
                        {React.createElement(type.icon, { className: "h-6 w-6" })}
                      </div>
                      <div>
                        <p className="text-slate-800 font-extrabold text-base line-clamp-1 tracking-tight">
                          {file.file.name}
                        </p>
                        <div className="text-xs text-slate-500 flex items-center gap-2 mt-1 font-medium">
                          <span className="font-mono bg-slate-100 px-2 py-0.5 rounded text-slate-600 border border-slate-200">
                            {type.label}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock size={10} /> {formatFileSize(file.file.size)}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {file.status === "pending"   && <Badge variant="outline" className="bg-amber-50 text-amber-600 border-amber-200">Pending</Badge>}
                      {file.status === "uploading" && <Badge variant="outline" className="bg-blue-50 text-blue-600 border-blue-200 animate-pulse">Uploading</Badge>}
                      {file.status === "analyzing" && <Badge variant="outline" className="bg-purple-50 text-purple-600 border-purple-200 animate-pulse">Analysing</Badge>}
                      {file.status === "completed" && (
                        <Badge variant="outline" className="bg-emerald-50 text-emerald-600 border-emerald-200 flex gap-1 items-center">
                          <CheckCircle size={10} /> Done
                        </Badge>
                      )}
                      {file.status === "error" && <Badge variant="outline" className="bg-red-50 text-red-600 border-red-200">Failed</Badge>}

                      <button
                        onClick={() => removeFile(file.id)}
                        className="text-slate-400 hover:text-red-500 transition-colors p-1 hover:bg-red-50 rounded-full"
                      >
                        <X size={18} />
                      </button>
                    </div>
                  </div>

                  {/* Progress bar */}
                  {(file.status === "uploading" || file.status === "analyzing") && (
                    <div className="mb-4 bg-slate-50 p-3 rounded-lg border border-slate-100">
                      <div className="flex justify-between text-xs mb-2 font-bold tracking-wide">
                        <span className="text-indigo-600 uppercase">{file.status}…</span>
                        <span className="text-slate-500">{file.progress}%</span>
                      </div>
                      <Progress value={file.progress} className="h-2 bg-slate-200" />
                    </div>
                  )}

                  {/* Error */}
                  {file.status === "error" && file.error && (
                    <Alert className="bg-red-50 border-red-100 mt-2 p-3">
                      <div className="flex gap-2 items-center">
                        <AlertCircle className="h-4 w-4 text-red-600" />
                        <span className="text-red-600 text-xs font-bold">{file.error}</span>
                      </div>
                    </Alert>
                  )}

                  {/* Analysis results */}
                  {file.status === "completed" && file.result && (
                    <div className="mt-5 bg-slate-50 rounded-xl p-5 border border-slate-200/60 shadow-inner">
                      <div className="grid grid-cols-3 gap-4 mb-5">
                        <div className="p-4 bg-white rounded-xl border border-slate-100 text-center shadow-sm hover:shadow-md transition-shadow">
                          <p className="text-2xl font-black text-red-500">
                            {file.result.ai_detected_percentage}%
                          </p>
                          <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mt-1">
                            AI Probability
                          </p>
                        </div>
                        <div className="p-4 bg-white rounded-xl border border-slate-100 text-center shadow-sm hover:shadow-md transition-shadow">
                          <p className="text-2xl font-black text-amber-500">
                            {file.result.web_source_percentage}%
                          </p>
                          <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mt-1">
                            Plagiarism
                          </p>
                        </div>
                        <div className="p-4 bg-white rounded-xl border border-slate-100 text-center shadow-sm hover:shadow-md transition-shadow">
                          <p className="text-2xl font-black text-emerald-500">
                            {file.result.human_written_percentage}%
                          </p>
                          <p className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mt-1">
                            Originality
                          </p>
                        </div>
                      </div>

                      {file.result.analysis_summary && (
                        <div className="bg-white p-4 rounded-xl border border-slate-100 mb-5 shadow-sm">
                          <p className="text-slate-600 text-sm italic leading-relaxed font-medium">
                            "{file.result.analysis_summary}"
                          </p>
                        </div>
                      )}

                      {file.result.matched_sources && file.result.matched_sources.length > 0 && (
                        <div className="bg-white p-4 rounded-xl border border-slate-100 mb-5 shadow-sm">
                          <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide mb-3 flex items-center gap-2">
                            <Globe size={14} className="text-blue-500" />
                            Matched Sources ({file.result.matched_sources.length})
                          </h4>
                          <ul className="space-y-2">
                            {file.result.matched_sources.map((source, index) => {
                              const matchPct = (source as any).match_pct;
                              const isWeb    = source.type === "web";
                              return (
                                <li
                                  key={index}
                                  className="text-xs p-3 rounded-lg bg-slate-50 border border-slate-100 hover:bg-slate-100 transition-colors"
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-start gap-2.5 flex-1 min-w-0">
                                      <div
                                        className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
                                          isWeb ? "bg-blue-500" : "bg-orange-500"
                                        }`}
                                      />
                                      {isWeb ? (
                                        <a
                                          href={source.source}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          className="text-blue-600 hover:text-blue-800 font-bold hover:underline break-all"
                                          title={source.source}
                                        >
                                          {source.source}
                                        </a>
                                      ) : (
                                        <div className="text-slate-600 font-medium flex items-center gap-1.5">
                                          <Database
                                            size={12}
                                            className="text-orange-500 flex-shrink-0"
                                          />
                                          <span className="break-all">
                                            Internal Match: {source.source}
                                          </span>
                                        </div>
                                      )}
                                    </div>

                                    {isWeb && matchPct !== undefined && (
                                      <div className="flex-shrink-0 ml-2">
                                        <span
                                          className={`inline-block px-2.5 py-1 rounded-md font-bold text-[10px] whitespace-nowrap ${
                                            matchPct >= 20
                                              ? "bg-red-100 text-red-700"
                                              : matchPct >= 10
                                              ? "bg-amber-100 text-amber-700"
                                              : matchPct >= 5
                                              ? "bg-yellow-100 text-yellow-700"
                                              : "bg-slate-100 text-slate-600"
                                          }`}
                                        >
                                          {matchPct.toFixed(1)}%
                                        </span>
                                      </div>
                                    )}
                                  </div>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}

                      <Button
                        size="sm"
                        onClick={() =>
                          generateAndDownloadReport(
                            file.result!,
                            userId,
                            file.file.name,
                            file.result!.extracted_text
                          )
                        }
                        className="w-full bg-slate-900 hover:bg-indigo-600 text-white font-bold uppercase tracking-wide text-xs h-10 rounded-lg shadow-md transition-all"
                      >
                        <Download className="h-4 w-4 mr-2" />
                        Download Full Report
                      </Button>
                    </div>
                  )}

                  {/* Per-file "Start Analysis" (pending only) */}
                  {file.status === "pending" && (
                    <div className="mt-6 pt-5 border-t border-slate-100">
                      <Button
                        size="sm"
                        onClick={() => handleSingleAnalyze(file)}
                        variant="outline"
                        className="w-full border-2 border-indigo-100 text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50 font-bold uppercase text-xs h-10 rounded-lg"
                      >
                        Start Analysis
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}