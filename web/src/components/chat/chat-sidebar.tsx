"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { MessageSquarePlus, Search, Settings, X } from "lucide-react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { useSession } from "next-auth/react";

interface ChatSidebarProps {
    isOpen: boolean;
    onClose: () => void;
    onNewChat: () => void;
    className?: string;
}

export function ChatSidebar({ isOpen, onClose, onNewChat, className }: ChatSidebarProps) {
    const { data: session } = useSession();

    const userName = session?.user?.name || "Researcher";
    const userEmail = session?.user?.email || "";
    const initial = userName.charAt(0).toUpperCase();
    const hasHistory = false;

    const recentsNotice = "History is not yet available while this feature is shipping. Your recent chats will appear here once the list endpoint is live.";

    return (
        <>
            {/* Mobile overlay */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 z-40 bg-black/80 p-0 backdrop-blur-sm lg:hidden"
                    />
                )}
            </AnimatePresence>

            {/* Sidebar panel */}
            <motion.aside
                role="navigation"
                aria-label="Chat history"
                className={cn(
                    "fixed inset-y-0 left-0 z-50 flex h-full w-64 flex-col border-r border-[var(--border-strong)] bg-[var(--bg-1)] shadow-xl transition-transform duration-300 ease-in-out lg:static lg:translate-x-0",
                    isOpen ? "translate-x-0" : "-translate-x-full",
                    className
                )}
            >
                {/* Brand */}
                <div className="flex h-16 items-center justify-between border-b border-[var(--border-strong)] px-4">
                    <Link href="/" className="flex items-center gap-2 font-semibold text-[var(--text-primary)]">
                        <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--accent)] text-[var(--background)]">
                            <span className="text-xs font-bold">AI</span>
                        </div>
                        <span style={{ fontFamily: "var(--font-display)" }}>Research Agent</span>
                    </Link>
                    <Button variant="ghost" size="icon" onClick={onClose} className="lg:hidden" aria-label="Close sidebar">
                        <X className="h-5 w-5" />
                    </Button>
                </div>

                {/* New chat */}
                <div className="p-3">
                    <Button
                        onClick={onNewChat}
                        variant="default"
                        className="h-10 w-full justify-start gap-2"
                        aria-label="Start a new chat"
                    >
                        <MessageSquarePlus className="h-4 w-4" />
                        New Chat
                    </Button>
                </div>

                {/* Recents */}
                <div className="flex-1 overflow-y-auto px-2 py-2">
                    <div className="mb-2 px-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-muted)]">
                        Recents
                    </div>
                    {hasHistory ? (
                        <ul className="space-y-1" role="list">
                            {/* Placeholder for future API-driven history rendering */}
                        </ul>
                    ) : (
                        <div className="space-y-2 px-2 py-3">
                            <p className="rounded-md border border-[var(--border-subtle)] bg-[var(--bg-2)] p-2 text-xs text-[var(--text-secondary)]">
                                {recentsNotice}
                            </p>
                            <div className="rounded-md border border-dashed border-[var(--border-subtle)] bg-[var(--bg-1)] p-2 text-xs text-[var(--text-muted)]">
                                <p className="font-medium text-[var(--text-secondary)]">Example rows (not clickable)</p>
                                <ul className="mt-2 space-y-1">
                                    <li className="truncate px-1">Research query: RAG model comparison</li>
                                    <li className="truncate px-1">Chat: explain vector search tradeoffs</li>
                                    <li className="truncate px-1">Paper review: arXiv summarization</li>
                                </ul>
                            </div>
                        </div>
                    )}
                </div>

                {/* Utilities */}
                <div className="space-y-1 border-t border-[var(--border-strong)] p-3">
                    <Button variant="ghost" className="h-9 w-full justify-start gap-2 text-[var(--text-secondary)]">
                        <Search className="h-4 w-4" />
                        Search History
                    </Button>
                    <Button variant="ghost" className="h-9 w-full justify-start gap-2 text-[var(--text-secondary)]">
                        <Settings className="h-4 w-4" />
                        Settings
                    </Button>
                </div>

                {/* User profile — real session data */}
                <div className="border-t border-[var(--border-strong)] p-4">
                    <div className="flex items-center gap-3">
                        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--bg-3)] text-sm font-semibold text-[var(--text-primary)]">
                            {initial}
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-[var(--text-primary)]">{userName}</p>
                            {userEmail && (
                                <p className="truncate text-xs text-[var(--text-muted)]">{userEmail}</p>
                            )}
                        </div>
                    </div>
                </div>
            </motion.aside>
        </>
    );
}
