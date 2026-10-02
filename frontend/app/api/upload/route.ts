import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    
    const res = await fetch(`${backendUrl}/upload`, {
      method: "POST",
      body: formData,
      // No timeout via fetch options in standard fetch API, but next.js fetch handles it
    });
    
    if (!res.ok) {
      const errorText = await res.text();
      return NextResponse.json({ error: errorText }, { status: res.status });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (e: any) {
    console.error("API Route Error:", e);
    return NextResponse.json({ error: e.message || "Failed to connect to backend" }, { status: 500 });
  }
}
