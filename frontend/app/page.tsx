"use client";

import { useState, useEffect } from "react";
import { Upload, FileText, CheckCircle, AlertCircle, ServerCrash } from "lucide-react";
import Link from "next/link";

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [backendUp, setBackendUp] = useState<boolean>(true);

  useEffect(() => {
    // Check if backend is alive
    fetch("http://localhost:8000/", { method: "GET" })
      .then(() => setBackendUp(true))
      .catch(() => setBackendUp(false));
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    
    setLoading(true);
    setError(null);
    setResults([]);

    const formData = new FormData();
    files.forEach(file => {
      formData.append("files", file);
    });

    try {
      const res = await fetch("http://localhost:8000/v1/upload", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        throw new Error(`Server error: ${res.statusText}`);
      }

      const data = await res.json();
      setResults(data.results || []);
    } catch (err: any) {
      if (err.name === 'TypeError' && err.message === 'Failed to fetch') {
        setError("Backend is unreachable. Please ensure the FastAPI server is running.");
        setBackendUp(false);
      } else {
        setError(err.message || "Failed to upload files");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto w-full px-4 py-12">
      {!backendUp && (
        <div className="mb-8 bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded shadow-sm flex items-center">
          <ServerCrash className="w-6 h-6 mr-3" />
          <div>
            <p className="font-bold">Backend is Offline</p>
            <p className="text-sm">Cannot reach the FastAPI server at http://localhost:8000. Is the Docker container running?</p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Upload PDFs</h1>
          <p className="text-gray-500">Extract text, generate embeddings, and chat with your documents.</p>
        </div>

        <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:bg-gray-50 transition">
          <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
          <div className="flex text-sm text-gray-600 justify-center">
            <label className="relative cursor-pointer bg-white rounded-md font-medium text-blue-600 hover:text-blue-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-blue-500">
              <span>Select files</span>
              <input type="file" multiple accept=".pdf" className="sr-only" onChange={handleFileChange} />
            </label>
            <p className="pl-1">or drag and drop</p>
          </div>
          <p className="text-xs text-gray-500 mt-2">PDF up to 50MB</p>
        </div>

        {files.length > 0 && (
          <div className="mt-6">
            <h4 className="text-sm font-medium text-gray-900 mb-3">Selected files</h4>
            <ul className="space-y-2 mb-6">
              {files.map((f, i) => (
                <li key={i} className="flex items-center text-sm text-gray-600 bg-gray-50 px-3 py-2 rounded-md">
                  <FileText className="w-4 h-4 mr-2 text-gray-400" />
                  {f.name} ({(f.size / 1024 / 1024).toFixed(2)} MB)
                </li>
              ))}
            </ul>
            
            <button
              onClick={handleUpload}
              disabled={loading}
              className="w-full flex justify-center py-2.5 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
            >
              {loading ? "Processing..." : "Create Embeddings"}
            </button>
          </div>
        )}

        {error && (
          <div className="mt-6 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md flex items-start">
            <AlertCircle className="w-5 h-5 mr-2 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {results.length > 0 && (
          <div className="mt-8 border-t pt-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Results</h3>
            <div className="space-y-3 mb-6">
              {results.map((res, i) => (
                <div key={i} className={`p-4 rounded-md border ${res.status === 'success' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                  <div className="flex items-center">
                    {res.status === 'success' ? (
                      <CheckCircle className="w-5 h-5 text-green-500 mr-2" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-red-500 mr-2" />
                    )}
                    <span className="font-medium text-gray-900">{res.filename}</span>
                  </div>
                  <div className="mt-1 ml-7 text-sm text-gray-600">
                    {res.status === 'success' ? `Stored ${res.num_chunks} chunks.` : res.detail}
                  </div>
                </div>
              ))}
            </div>
            
            <Link href="/chat" className="text-blue-600 hover:text-blue-800 font-medium text-sm flex justify-center border border-blue-200 bg-blue-50 py-2 rounded-md transition">
              Go to Chat →
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}
