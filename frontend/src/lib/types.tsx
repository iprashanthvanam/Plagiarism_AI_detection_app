




// export type MatchedSource = {
//   type: "web" | "local_db";
//   source: string;
// };

// export interface AnalysisStatus {
//   status: "pending" | "analyzing" | "completed" | "failed";
//   progress_percentage?: number;
//   result?: AnalysisResult;
//   error?: string;
// }

// export interface AnalysisResult {
//   document_id: number;
//   file_name: string;
//   ai_detected_percentage: number;
//   web_source_percentage: number;
//   human_written_percentage: number;
//   analysis_summary?: string;
//   analysis_date: string;
//   matched_sources?: MatchedSource[];
//   extracted_text?: string;          // ← NEW: full document text for highlighted report
// }

// export interface AuthUser {
//   userId: string;
//   role: "admin" | "student";
// }





















export type MatchedSource = {
  type: "web" | "local_db";
  source: string;
};

export interface AnalysisStatus {
  status: "pending" | "analyzing" | "completed" | "failed";
  progress_percentage?: number;
  result?: AnalysisResult;
  error?: string;
}

export interface AnalysisResult {
  document_id: number;
  file_name?: string;
  ai_detected_percentage: number;
  web_source_percentage: number;
  local_similarity_percentage?: number;    // internal DB — separate from web score
  human_written_percentage: number;
  analysis_summary?: string;
  analysis_date: string;
  matched_sources?: MatchedSource[];
  extracted_text?: string;                 // full document text for highlighted report
  sentence_source_map?: Record<string, number>; // sentence → URL index (0-based)
  processing_time_seconds?: number;
}

export interface AuthUser {
  userId: string;
  role: "admin" | "student";
}