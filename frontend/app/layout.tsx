import type { Metadata } from "next";
import "./globals.css";
import Navbar from "@/components/Navbar";
import TracewayProvider from "./TracewayProvider";

export const metadata: Metadata = {
  title: "RAG Pipeline",
  description: "Next.js frontend for RAG backend",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 flex flex-col text-gray-900">
        <TracewayProvider>
          <Navbar />
          <main className="flex-1 flex flex-col">
            {children}
          </main>
        </TracewayProvider>
      </body>
    </html>
  );
}
