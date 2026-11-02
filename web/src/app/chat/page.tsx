"use client";

import { useChat } from "@ai-sdk/react";
import { ChatInput } from "@/components/chat/chat-input";
import { ChatMessage } from "@/components/chat/chat-message";
import { ChatSidebar } from "@/components/chat/chat-sidebar";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Menu, LogOut, Loader2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { type Citation } from "@/lib/api";
import { type SearchMode } from "@/components/chat/search-mode-selector";
import { useSession, signOut } from "next-auth/react";
import { useRouter } from "next/navigation";
import { getBrowserSessionStorage, getOrCreateChatSessionId, rotateChatSessionId } from "./session-id";

const SUGGESTIONS = [
    { title: "What is RAG?", desc: "Mechanics of document-grounded generation.", q: "What is RAG?" },
    { title: "Explain embedding models", desc: "Dimensional tradeoffs & distance metrics.", q: "Explain embedding models" },
    { title: "Summarize recent papers", desc: "Multi-source synthesis from the index.", q: "Summarize recent papers" },
    { title: "Best practices for vector DBs", desc: "Partitioning, pruning & indexing.", q: "Best practices for vector DBs" },
];

type ChatMessageLike = {
    id?: string;
    role?: string;
    content?: unknown;
    parts?: unknown[];
};

type ChatDataItem = {
    citations?: Citation[];
};

type SendMessage = (
    message: { role: "user"; content: string },
    options?: { body: Record<string, unknown> }
) => Promise<unknown> | unknown;

type ChatHelpers = {
    messages: ChatMessageLike[];
    isLoading: boolean;
    error?: Error;
    data?: ChatDataItem[];
    status?: string;
    sendMessage?: SendMessage;
    append?: SendMessage;
    submitMessage?: SendMessage;
    stop?: () => void;
    setMessages?: (messages: ChatMessageLike[]) => void;
};

type TextPart = {
    type: "text";
    text?: unknown;
};

type SourcePart = {
    type?: unknown;
    sourceType?: unknown;
    url?: unknown;
    title?: unknown;
    source?: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null;
}

function isTextPart(part: unknown): part is TextPart {
    return isRecord(part) && part.type === "text";
}

function isSourcePart(part: unknown): part is SourcePart {
    return isRecord(part) && (part.type === "source-url" || part.sourceType === "url");
}

// Extract plain text from a message that may use the old `content` field or the new `parts` array.
function getMessageText(msg?: ChatMessageLike): string {
    if (typeof msg?.content === "string") return msg.content;
    if (Array.isArray(msg?.parts)) {
        return msg.parts
            .filter(isTextPart)
            .map((part) => (typeof part.text === "string" ? part.text : ""))
            .join("");
    }
    return "";
}

function getArxivIdFromUrl(url?: string): string | undefined {
    if (!url) return undefined;
    return url.match(/arxiv\.org\/abs\/([^/?#]+)/)?.[1];
}

function getMessageCitations(msg?: ChatMessageLike): Citation[] {
    const parts = Array.isArray(msg?.parts) ? msg.parts : [];
    return parts
        .filter(isSourcePart)
        .map((part) => {
            const source = isRecord(part.source) ? part.source : undefined;
            const url =
                (typeof part.url === "string" ? part.url : undefined) ||
                (typeof source?.url === "string" ? source.url : undefined) ||
                "";
            return {
                title:
                    (typeof part.title === "string" ? part.title : undefined) ||
                    (typeof source?.title === "string" ? source.title : undefined) ||
                    "Source",
                authors: [],
                url,
                relevance_score: 0,
                arxiv_id: getArxivIdFromUrl(url),
            } satisfies Citation;
        })
        .filter((citation: Citation) => citation.url);
}

export default function ChatPage() {
    const { data: session, status } = useSession();
    const router = useRouter();

    useEffect(() => {
        if (status === "unauthenticated") {
            router.push("/auth/login");
        }
    }, [status, router]);

    const [isSidebarOpen, setIsSidebarOpen] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const [input, setInput] = useState("");
    const [searchMode, setSearchMode] = useState<SearchMode>("auto");
    const [activeSearchMode, setActiveSearchMode] = useState<SearchMode>("auto");
    const [chatSessionId, setChatSessionId] = useState<string>(() =>
        getOrCreateChatSessionId(getBrowserSessionStorage())
    );

    const apiUrl = "/api/chat";

    // Casting to a local compatibility shape for currently mixed @ai-sdk/react helpers.
    const chatHelpers = useChat({
        api: apiUrl,
        onError: (err: Error) => {
            console.error("[ChatPage] Chat error:", err);
        },
    } as unknown as Parameters<typeof useChat>[0]) as unknown as ChatHelpers;

    const { messages, isLoading, error, data, status: chatStatus } = chatHelpers;
    const sendMessage = chatHelpers.sendMessage || chatHelpers.append || chatHelpers.submitMessage;

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setInput(e.target.value);
    };

    const send = (text: string, mode: SearchMode = searchMode) => {
        if (!sendMessage) {
            console.error("[ChatPage] No sendMessage function available!");
            return;
        }
        setActiveSearchMode(mode);
        return sendMessage(
            { role: "user", content: text },
            {
                body: {
                    session_id: chatSessionId,
                    mode,
                    search_source: mode === "search" ? "research" : undefined,
                },
            }
        );
    };

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!input.trim()) return;
        const userMessage = input;
        setInput("");
        try {
            await send(userMessage, searchMode);
        } catch (err) {
            console.error("[ChatPage] Failed to send message:", err);
        }
    };

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    // Start a fresh chat without a full page reload (falls back to reload if unsupported).
    const handleNewChat = () => {
        chatHelpers.stop?.();
        const nextSessionId = rotateChatSessionId(getBrowserSessionStorage());
        setChatSessionId(nextSessionId);
        if (typeof chatHelpers.setMessages === "function") {
            chatHelpers.setMessages([]);
            setInput("");
            setIsSidebarOpen(false);
        } else {
            window.location.reload();
        }
    };

    const getLastCitations = (): Citation[] | undefined => {
        if (!data) return undefined;
        const lastData = [...data].reverse().find((item) => item?.citations);
        return lastData?.citations;
    };

    // Checking session
    if (status === "loading") {
        return (
            <div className="flex h-screen items-center justify-center bg-[var(--bg-page)]">
                <Loader2 className="h-6 w-6 animate-spin text-[var(--accent)]" />
            </div>
        );
    }

    if (!session) return null;

    const isBusy = isLoading || chatStatus === "submitted";
    const lastMsg = messages[messages.length - 1];
    const showLoadingState =
        isBusy && (lastMsg?.role === "user" || (lastMsg?.role === "assistant" && !getMessageText(lastMsg).trim()));

    const loadingCopy =
        activeSearchMode === "search"
            ? "Research Papers: searching relevant papers, then drafting the answer."
            : activeSearchMode === "auto"
              ? "Auto mode: selecting the best workflow and writing your answer."
              : "Chat Only: writing a direct answer.";

    const composer = (side: "top" | "bottom") => (
        <ChatInput
            value={input}
            mode={searchMode}
            onModeChange={setSearchMode}
            dropdownSide={side}
            onChange={handleInputChange}
            onSubmit={handleSubmit}
            isLoading={isLoading}
        />
    );

    return (
        <div className="flex h-screen overflow-hidden bg-[var(--bg-page)]">
            <ChatSidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)} onNewChat={handleNewChat} />

            <div className="relative flex flex-1 flex-col overflow-hidden">
                {/* Header */}
                <header className="flex items-center justify-between border-b border-[var(--border-strong)] bg-[var(--bg-1)] px-4 py-3">
                    <div className="flex items-center gap-2">
                        <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setIsSidebarOpen(true)}
                            className="lg:hidden"
                            aria-label="Open sidebar"
                        >
                            <Menu className="h-5 w-5" />
                        </Button>
                        <span className="font-semibold text-[var(--text-primary)]" style={{ fontFamily: "var(--font-display)" }}>
                            AI Research Agent
                        </span>
                    </div>
                    <div className="flex items-center gap-1">
                        <ThemeToggle />
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                rotateChatSessionId(getBrowserSessionStorage());
                                signOut({ callbackUrl: "/auth/login" });
                            }}
                            className="gap-2 text-[var(--text-secondary)]"
                        >
                            <LogOut className="h-4 w-4" />
                            Logout
                        </Button>
                    </div>
                </header>

                {messages.length === 0 ? (
                    /* Empty state */
                    <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-4">
                        <div className="w-full max-w-2xl py-8">
                            <div className="mb-8 text-center">
                                <h2 className="type-section mb-2 text-3xl text-[var(--text-primary)]">
                                    Private Research Node
                                </h2>
                                <p className="text-sm text-[var(--text-secondary)]">
                                    Ground queries against your document index. Pick a starter below or ask your own.
                                </p>
                            </div>

                            <div className="mb-4 grid gap-3 sm:grid-cols-2" role="region" aria-label="Suggested prompts">
                                {SUGGESTIONS.map((s) => (
                                    <button
                                        key={s.title}
                                        onClick={() => {
                                            setInput(s.q);
                                            send(s.q);
                                        }}
                                        className="rounded-md border border-[var(--border-strong)] bg-[var(--bg-1)] p-4 text-left transition-colors hover:border-[var(--accent)]"
                                        aria-label={`Suggest: ${s.q}`}
                                    >
                                        <div className="mb-1 text-sm font-semibold text-[var(--accent)]">{s.title}</div>
                                        <div className="text-xs text-[var(--text-secondary)]">{s.desc}</div>
                                    </button>
                                ))}
                            </div>

                            {composer("top")}
                        </div>
                    </div>
                ) : (
                    <>
                        <div className="flex-1 overflow-y-auto px-4 py-6" role="log" aria-live="polite" aria-label="Conversation">
                            <div className="mx-auto max-w-3xl">
                                {messages.map((msg, idx) => {
                                    const isLastAssistant = msg.role === "assistant" && idx === messages.length - 1;
                                    const messageCitations = getMessageCitations(msg);
                                    const citations = messageCitations.length > 0 ? messageCitations : isLastAssistant ? getLastCitations() : undefined;
                                    const messageContent = getMessageText(msg);

                                    // Skip the empty assistant placeholder while streaming starts
                                    if (msg.role === "assistant" && !messageContent && idx === messages.length - 1 && isLoading) {
                                        return null;
                                    }

                                    return (
                                        <ChatMessage
                                            key={msg.id}
                                            role={msg.role === "user" ? "user" : "assistant"}
                                            content={messageContent}
                                            citations={citations}
                                        />
                                    );
                                })}

                                {error && (
                                    <div
                                        role="alert"
                                        className="mb-6 rounded-md border px-4 py-3 text-sm"
                                        style={{
                                            backgroundColor: "var(--danger-bg)",
                                            borderColor: "var(--danger)",
                                            color: "var(--text-primary)",
                                        }}
                                    >
                                        Error: {error.message}
                                    </div>
                                )}

                                {showLoadingState && (
                                    <div
                                        role="status"
                                        aria-live="polite"
                                        className="mr-auto mb-6 flex w-full max-w-[90%] items-center gap-2 rounded-md border border-[var(--border-strong)] bg-[var(--bg-1)] p-3 text-sm"
                                    >
                                        <Loader2 className="h-4 w-4 animate-spin text-[var(--accent)]" />
                                        <span className="text-[var(--text-secondary)]">{loadingCopy}</span>
                                    </div>
                                )}
                                <div ref={messagesEndRef} />
                            </div>
                        </div>

                        <div className="border-t border-[var(--border-strong)] bg-[var(--bg-page)] pt-4">
                            {composer("top")}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
