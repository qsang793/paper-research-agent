import { NextResponse } from "next/server";
import { buildBackendHeaders } from "@/lib/backend-request";

export async function GET() {
    try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const response = await fetch(`${apiUrl}/api/features`, {
            cache: "no-store",
            headers: buildBackendHeaders(),
        });
        if (!response.ok) {
            return NextResponse.json({ research_search_available: false });
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch {
        return NextResponse.json({ research_search_available: false });
    }
}
