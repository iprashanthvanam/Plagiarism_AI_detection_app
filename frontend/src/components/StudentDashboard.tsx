import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'; 
import { 
  FileText, 
  LogOut, 
  Download, 
  Eye, 
  User, 
  BarChart, 
  UploadCloud, 
  Clock, 
  Image as ImageIcon, 
  FileSpreadsheet, 
  Presentation 
} from 'lucide-react';
import api from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { FileUploadAnalysis } from './FileUploadAnalysis';
import { generateAndDownloadReport } from "@/lib/reportGenerator";

/* ========================================================================
   TYPES & HELPERS
   ======================================================================== */
interface DocumentEntry {
  id: number;
  file_name: string;
  upload_date: string;
}

const getFileStyle = (fileName: string) => {
  const ext = fileName.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'pdf': return { icon: FileText, color: 'text-red-500', bg: 'bg-red-50' };
    case 'doc':
    case 'docx': return { icon: FileText, color: 'text-blue-500', bg: 'bg-blue-50' };
    case 'xls':
    case 'xlsx': return { icon: FileSpreadsheet, color: 'text-green-500', bg: 'bg-green-50' };
    case 'ppt':
    case 'pptx': return { icon: Presentation, color: 'text-orange-500', bg: 'bg-orange-50' };
    case 'png':
    case 'jpg':
    case 'jpeg': return { icon: ImageIcon, color: 'text-purple-500', bg: 'bg-purple-50' };
    default: return { icon: FileText, color: 'text-slate-500', bg: 'bg-slate-100' };
  }
};

/* ========================================================================
   STUDENT DASHBOARD COMPONENT
   ======================================================================== */
export function StudentDashboard() {
  const { user, logout, loading } = useAuth();
  const navigate = useNavigate();

  const [documents, setDocuments] = useState<DocumentEntry[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);

  useEffect(() => {
    const fetchStudentDocs = async () => {
      try {
        setDocsLoading(true);
        const res = await api.get("/student/dashboard");
        
        // ✅ NEW: Validate response is array
        if (Array.isArray(res.data)) {
          setDocuments(res.data);
        } else if (res.data && Array.isArray(res.data.documents)) {
          setDocuments(res.data.documents);
        } else {
          console.warn("Unexpected response format:", res.data);
          setDocuments([]);
        }
      } catch (err) {
        console.error("Error fetching documents:", err);
        setDocuments([]);  // ✅ Default to empty array on error
      } finally {
        setDocsLoading(false);
      }
    };
    
    if (user?.id) {
      fetchStudentDocs();
    }
  }, [user?.id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center">
        <p className="text-indigo-400 text-sm font-bold tracking-widest animate-pulse">VERIFYING SESSION...</p>
      </div>
    );
  }

  if (!user || user.role !== "student") {
    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
        <div className="bg-white/90 backdrop-blur-md border-none p-8 rounded-2xl shadow-2xl text-center max-w-md w-full">
          <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <LogOut className="text-red-600" size={32} />
          </div>
          <h2 className="text-xl font-bold text-slate-800 mb-2">Access Denied</h2>
          <p className="text-slate-600 text-sm mb-6">You do not have permission to view this dashboard.</p>
          <button onClick={() => navigate('/')} className="bg-slate-900 text-white px-6 py-2.5 rounded-lg text-sm font-semibold hover:bg-slate-800 transition-all w-full">
            Return to Home
          </button>
        </div>
      </div>
    );
  }

  const handleLogout = () => { logout(); navigate('/'); };

  const handleView = async (id: number, fileName: string) => {
    try {
      const res = await api.get(`/files/original/${id}`, { responseType: "blob" });
      const blob = new Blob([res.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url; a.download = fileName;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (error) { console.error("Download failed", error); alert("Failed to download file."); }
  };

  // ✅ FIXED: fetch result then pass result.extracted_text as 4th arg
  const handleDownload = async (docId: number, fileName?: string) => {
    try {
      const res = await api.get(`/analysis-status/${docId}`);
      const result = res.data.result;
      generateAndDownloadReport(
        result,
        user.username,
        fileName,
        result.extracted_text   // ← now works because types.tsx has this field
      );
    } catch (error) {
      console.error("Report generation failed", error);
      alert("Failed to generate report.");
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-900 via-purple-900 to-rose-900 flex flex-col font-sans overflow-x-hidden pb-32 md:pb-24 text-slate-100">
      
      <div className="flex-1 w-full max-w-7xl mx-auto px-4 md:px-8 pt-6 pb-6">
        
        {/* --- HEADER --- */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4 bg-white/10 backdrop-blur-md p-6 rounded-3xl shadow-lg border border-white/10">
          <div>
            <h2 className="text-3xl font-bold text-white flex items-center gap-3">
              <div className="bg-white/20 p-2 rounded-xl text-white backdrop-blur-sm shadow-inner"><User size={28} /></div>
              Student Dashboard
            </h2>
            <p className="text-indigo-200 text-sm mt-2 ml-14 font-medium tracking-wide">Manage your documents and view plagiarism reports</p>
          </div>
          <div className="flex items-center gap-4 bg-black/20 px-5 py-3 rounded-2xl border border-white/5 backdrop-blur-sm">
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-indigo-400 to-purple-400 flex items-center justify-center text-white font-bold text-sm shadow-lg border border-white/20">
              {user.username.charAt(0).toUpperCase()}
            </div>
            <div className="text-sm">
              <span className="text-indigo-200 text-xs font-bold uppercase block tracking-wider">Logged in as</span>
              <span className="font-bold text-white text-base">{user.username}</span>
            </div>
          </div>
        </div>

        {/* --- TABS --- */}
        <div className="w-full">
          <Tabs defaultValue="your-data" className="w-full">
            <div className="mb-6">
              <TabsList className="grid w-full md:w-[600px] md:h-[60px] grid-cols-3 bg-black/20 backdrop-blur-md p-1 rounded-2xl border border-white/10">
                <TabsTrigger value="your-data" className="data-[state=active]:bg-white data-[state=active]:text-purple-900 data-[state=active]:shadow-lg text-indigo-200 font-bold text-sm py-3 rounded-xl transition-all flex items-center justify-center gap-2">
                  <FileText size={18} /> <span className="hidden sm:inline">My Documents</span>
                </TabsTrigger>
                <TabsTrigger value="analysis" className="data-[state=active]:bg-white data-[state=active]:text-purple-900 data-[state=active]:shadow-lg text-indigo-200 font-bold text-sm py-3 rounded-xl transition-all flex items-center justify-center gap-2">
                  <BarChart size={18} /> <span className="hidden sm:inline">New Analysis</span>
                </TabsTrigger>
                <TabsTrigger value="logout" onClick={handleLogout} className="data-[state=active]:bg-rose-500 data-[state=active]:text-white text-indigo-200 font-bold text-sm py-3 rounded-xl transition-all flex items-center justify-center gap-2 hover:text-rose-300">
                  <LogOut size={18} /> <span className="hidden sm:inline">Logout</span>
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="space-y-6">
              {/* TAB: MY DOCUMENTS */}
              <TabsContent value="your-data" className="mt-0 w-full">
                {docsLoading ? (
                  <div className="text-center py-20 flex flex-col items-center justify-center bg-white/5 rounded-3xl backdrop-blur-sm border border-white/10">
                    <div className="w-12 h-12 border-4 border-indigo-200 border-t-white rounded-full animate-spin mb-4"></div>
                    <p className="text-indigo-200 text-sm font-bold tracking-wide">FETCHING DOCUMENTS...</p>
                  </div>
                ) : documents.length === 0 ? (
                  <div className="text-center py-24 bg-white/5 rounded-3xl backdrop-blur-sm border border-dashed border-white/20">
                    <UploadCloud className="text-white mx-auto mb-4" size={36} />
                    <h3 className="text-white font-bold text-lg mb-1">No Documents Found</h3>
                    <p className="text-indigo-200 text-sm">Upload a document in the Analysis tab.</p>
                  </div>
                ) : (
                  <div className="grid gap-4 w-full">
                    {documents.map((doc) => {
                      const style = getFileStyle(doc.file_name);
                      const Icon = style.icon;
                      return (
                        <div key={doc.id} className="group bg-white/95 backdrop-blur-md rounded-2xl p-6 flex flex-col md:flex-row justify-between items-center shadow-xl hover:shadow-2xl hover:bg-white transition-all duration-300 w-full">
                          <div className="flex items-center gap-5 w-full md:w-auto mb-4 md:mb-0">
                            <div className={`w-14 h-14 ${style.bg} ${style.color} rounded-2xl flex items-center justify-center shrink-0 shadow-inner`}><Icon size={24} /></div>
                            <div>
                              <h3 className="text-slate-800 font-extrabold text-lg truncate">{doc.file_name}</h3>
                              <div className="flex items-center gap-2 text-xs text-slate-500 mt-1.5"><Clock size={12} /><span className="font-medium">{new Date(doc.upload_date).toLocaleString()}</span></div>
                            </div>
                          </div>
                          <div className="flex flex-col sm:flex-row gap-3 w-full md:w-auto">
                            <button onClick={() => handleView(doc.id, doc.file_name)} className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-slate-100 text-slate-700 hover:bg-indigo-50 hover:text-indigo-600 px-6 py-3 rounded-xl text-sm font-bold transition-all"><Eye size={16} /> View</button>
                            {/* ✅ FIXED: passes doc.file_name */}
                            <button onClick={() => handleDownload(doc.id, doc.file_name)} className="flex-1 md:flex-none flex items-center justify-center gap-2 bg-gradient-to-r from-slate-900 to-slate-800 hover:from-indigo-600 hover:to-purple-600 text-white px-6 py-3 rounded-xl text-sm font-bold transition-all shadow-lg"><Download size={16} /> Report</button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </TabsContent>

              {/* TAB: ANALYSIS */}
              <TabsContent value="analysis" className="mt-0 w-full space-y-6">
                <div className="bg-white/10 backdrop-blur-md rounded-2xl p-6 shadow-lg border border-white/10 flex flex-col md:flex-row justify-between items-center">
                  <div className="mb-4 md:mb-0">
                    <h3 className="text-white font-bold text-xl">New Analysis Request</h3>
                    <p className="text-indigo-200 text-sm mt-1">Upload a document to check for plagiarism.</p>
                  </div>
                  <span className="text-[10px] font-bold bg-white/20 border border-white/10 px-4 py-1.5 rounded-full text-white uppercase tracking-wide">Supports PDF, DOCX, PPT, Images</span>
                </div>
                <FileUploadAnalysis userType="student" userId={user?.id || ''} onAnalysisComplete={(result) => console.log('Analysis Complete:', result)} />
              </TabsContent>
            </div>
          </Tabs>
        </div>
      </div>

      <footer className="fixed bottom-0 left-0 w-full bg-black/40 backdrop-blur-lg text-center py-4 px-4 text-xs border-t border-white/5 z-50">
        <div className="flex flex-col gap-1 md:gap-1 w-full max-w-7xl mx-auto">
          <p className="font-medium text-slate-200 tracking-wide">© 2026 Teegala Krishna Reddy Engineering College. All Rights Reserved.</p>
          <p className="text-indigo-300/60 text-[10px]">Designed & Developed under the Guidance of Dr. B. Srinivasa Rao (Dean Academics)</p>
        </div>
      </footer>

    </div>
  );
}