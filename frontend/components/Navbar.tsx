import Link from "next/link";
import { FileText, MessageSquare } from "lucide-react";

export default function Navbar() {
  return (
    <nav className="border-b bg-white">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center">
              <span className="font-bold text-xl text-blue-600">Simple RAG</span>
            </div>
            <div className="ml-6 flex space-x-8">
              <Link
                href="/"
                className="inline-flex items-center px-1 pt-1 border-b-2 border-transparent hover:border-blue-500 text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                <FileText className="w-4 h-4 mr-2" />
                Upload PDF's & Ask Questions
              </Link>
              <Link
                href="/chat"
                className="inline-flex items-center px-1 pt-1 border-b-2 border-transparent hover:border-blue-500 text-sm font-medium text-gray-700 hover:text-gray-900"
              >
                <MessageSquare className="w-4 h-4 mr-2" />
                Chat
              </Link>
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
