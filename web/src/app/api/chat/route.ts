import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { buildBackendHeaders } from "@/lib/backend-request";
import {
    attachServerUserId,
    buildBackendChatRequestBody,
    getAuthenticatedUserId,
    getMessageText,
    parseChatRequestBody,
} from "./route-helpers";

export {
    attachServerUserId,
    buildBackendChatRequestBody,
    getMessageText,
    parseChatRequestBody,
};

/**
 * Simple pass-through proxy for chat API.
 * Backend now outputs the correct Vercel AI SDK v3 UI Message Stream Protocol format.
 * This proxy just forwards the request and streams the response.
 */
export async function POST(req: Request) {
    let requestBody: unknown;
    try {
        requestBody = await req.json();
    } catch {
        return NextResponse.json(
            { error: "Invalid JSON request body" },
            { status: 400 }
        );
    }

    try {
        const parsedBody = parseChatRequestBody(requestBody);
        if (!parsedBody.ok) {
            return NextResponse.json({ error: parsedBody.error }, { status: 400 });
        }
        const session = await auth();
        const userId = getAuthenticatedUserId(session);
        if (!userId) {
            return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
        }

        // Extract the last user message as the query
        const backendBody = attachServerUserId(
            buildBackendChatRequestBody(parsedBody.lastMessage, parsedBody.body),
            userId
        );

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

        // Forward the request to the FastAPI backend
        const response = await fetch(`${apiUrl}/api/chat/stream`, {
            method: "POST",
            headers: buildBackendHeaders(),
            body: JSON.stringify(backendBody),
            cache: "no-store",
        });

        if (!response.ok) {
            const errorText = await response.text();
            return NextResponse.json({ error: errorText }, { status: response.status });
        }

        if (!response.body) {
            return NextResponse.json({ error: "No response body" }, { status: 500 });
        }

        // Pass through the SSE stream directly from backend
        // Backend now outputs the correct format with x-vercel-ai-ui-message-stream: v1 header
        return new Response(response.body, {
            headers: {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                // Forward the critical header from backend
                "x-vercel-ai-ui-message-stream": response.headers.get("x-vercel-ai-ui-message-stream") || "v1",
            },
        });

    } catch (error) {
        console.error("Proxy error:", error);
        return NextResponse.json(
            { error: "Internal Server Error" },
            { status: 500 }
        );
    }
}
