"use client"

import * as React from "react"
import { SendHorizontal, Loader2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

import { SearchModeSelector, type SearchMode } from "./search-mode-selector"

interface ChatInputProps {
    isLoading: boolean
    value?: string
    mode: SearchMode
    onModeChange: (mode: SearchMode) => void
    dropdownSide?: "top" | "bottom" | "left" | "right"
    onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void
    onSubmit?: (e: React.FormEvent) => void
}

export function ChatInput({
    isLoading,
    value,
    mode,
    onModeChange,
    dropdownSide = "top",
    onChange,
    onSubmit,
}: ChatInputProps) {
    return (
        <div className="mx-auto w-full max-w-3xl px-4 pb-6">
            {/* Flat composer surface (V2) */}
            <form
                onSubmit={onSubmit}
                className="flex flex-col gap-2 rounded-md border border-[var(--border-strong)] bg-[var(--bg-2)] p-2"
            >
                <Input
                    value={value}
                    onChange={onChange}
                    placeholder="Query your private document pool…"
                    className="h-auto border-0 bg-transparent px-2 py-2 text-base shadow-none focus:border-0"
                    disabled={isLoading}
                    autoFocus
                    aria-label="Chat message"
                />

                <div className="flex items-center justify-between">
                    <SearchModeSelector
                        mode={mode}
                        onModeChange={onModeChange}
                        disabled={isLoading}
                        side={dropdownSide}
                    />
                    <Button
                        type="submit"
                        size="icon"
                        variant="default"
                        disabled={!value?.trim() || isLoading}
                        className="h-9 w-9 shrink-0 rounded-full"
                        aria-label="Send message"
                    >
                        {isLoading ? (
                            <Loader2 className="h-5 w-5 animate-spin" />
                        ) : (
                            <SendHorizontal className="h-5 w-5" />
                        )}
                    </Button>
                </div>
            </form>
            <p className="mt-2 text-center text-xs text-[var(--text-muted)]">
                AI Research Agent can make mistakes. Verify important information.
            </p>
        </div>
    )
}
