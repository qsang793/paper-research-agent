"use client"

import { MessageSquare, Search, Sparkles } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { cn } from "@/lib/utils"

export type SearchMode = "auto" | "search" | "chat"

interface SearchModeSelectorProps {
    mode: SearchMode
    onModeChange: (mode: SearchMode) => void
    disabled?: boolean
    side?: "top" | "bottom" | "left" | "right"
}

export function SearchModeSelector({
    mode,
    onModeChange,
    disabled,
    side = "bottom"
}: SearchModeSelectorProps) {
    const modes = [
        {
            value: "auto",
            label: "Auto",
            icon: Sparkles,
            description: "Detects static, chat, or paper-search intent",
        },
        {
            value: "search",
            label: "Research Papers",
            icon: Search,
            description: "Forces the canonical paper workflow",
        },
        {
            value: "chat",
            label: "Chat Only",
            icon: MessageSquare,
            description: "Standard LLM chat without retrieval",
        },
    ] as const

    const currentMode = modes.find((m) => m.value === mode) || modes[0]

    return (
        <div className="relative">
            <DropdownMenu>
                <DropdownMenuTrigger asChild>
                    <Button
                        variant="ghost"
                        type="button"
                        disabled={disabled}
                        className="gap-1 rounded-md border border-[var(--border-strong)] bg-[var(--bg-1)] px-2 text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--text-primary)]"
                    >
                        <currentMode.icon className="mr-1 h-4 w-4" />
                        <span className="text-xs font-medium">{currentMode.label}</span>
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                    align="start"
                    side={side}
                    className="w-[220px] border-[var(--border-strong)] bg-[var(--bg-2)] p-1 text-[var(--text-primary)]"
                >
                    {modes.map((item) => (
                        <DropdownMenuItem
                            key={item.value}
                            onClick={() => onModeChange(item.value)}
                            className={cn(
                                "flex flex-col items-start gap-1 rounded-md p-2 focus:bg-[var(--bg-3)]",
                                mode === item.value ? "bg-[var(--accent-muted)]" : "hover:bg-[var(--bg-3)]"
                            )}
                        >
                            <div className="flex items-center gap-2">
                                <item.icon className="h-4 w-4 text-[var(--text-secondary)]" />
                                <span className={cn("font-medium", mode === item.value && "text-[var(--text-primary)]")}>
                                    {item.label}
                                </span>
                            </div>
                            <span className="text-xs text-[var(--text-muted)]">{item.description}</span>
                        </DropdownMenuItem>
                    ))}
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    )
}
