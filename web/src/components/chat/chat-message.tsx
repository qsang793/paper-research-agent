import type { ComponentPropsWithoutRef, ReactElement } from "react";
import { cn } from "@/lib/utils";
import { ExternalLink } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Citation } from "@/lib/api";

interface ChatMessageProps {
    role: "user" | "assistant";
    content: string;
    citations?: Citation[];
}

const markdownComponents: {
    a: (props: ComponentPropsWithoutRef<"a">) => ReactElement;
    p: (props: ComponentPropsWithoutRef<"p">) => ReactElement;
    ul: (props: ComponentPropsWithoutRef<"ul">) => ReactElement;
    ol: (props: ComponentPropsWithoutRef<"ol">) => ReactElement;
    code: (props: ComponentPropsWithoutRef<"code">) => ReactElement;
} = {
    a: ({ ...props }) => (
        <a {...props} target="_blank" rel="noopener noreferrer" className="text-[var(--link)] hover:underline" />
    ),
    p: ({ className, ...props }) => <p {...props} className={["mb-2 last:mb-0", className].filter(Boolean).join(" ")} />,
    ul: ({ className, ...props }) => (
        <ul {...props} className={["mb-2 list-disc pl-4 last:mb-0", className].filter(Boolean).join(" ")} />
    ),
    ol: ({ className, ...props }) => (
        <ol {...props} className={["mb-2 list-decimal pl-4 last:mb-0", className].filter(Boolean).join(" ")} />
    ),
    code: ({ className, children, ...rest }) => {
        const match = /language-(\w+)/.exec(className || "");
        return match ? (
            <code {...rest} className={className}>
                {children}
            </code>
        ) : (
            <code
                {...rest}
                className={["rounded bg-[var(--bg-2)] px-1 py-0.5 text-xs", className].filter(Boolean).join(" ")}
                style={{ fontFamily: "var(--font-mono)" }}
            >
                {children}
            </code>
        );
    },
};

export function ChatMessage({ role, content, citations }: ChatMessageProps) {
    const isUser = role === "user";
    const topAuthorString = (authors: string[]) => {
        if (authors.length === 0) return "";
        if (authors.length <= 2) return authors.join(", ");
        return `${authors.slice(0, 2).join(", ")}…`;
    };
    const formatRelevance = (score: number) => `${Math.round(score * 100)}%`;

    return (
        <article
            className={cn(
                "mb-6 max-w-[90%] rounded-md border p-4",
                isUser
                    ? "ml-auto border-[var(--border-subtle)] bg-[var(--bg-2)]"
                    : "mr-auto border-[var(--border-strong)] bg-[var(--bg-1)]"
            )}
        >
            <header
                className="mb-2 text-xs font-semibold text-[var(--text-muted)]"
                style={{ fontFamily: "var(--font-mono)" }}
            >
                {isUser ? "You" : "AI Research Assistant"}
            </header>

            <div className="prose prose-sm dark:prose-invert max-w-none break-words leading-relaxed text-[var(--text-primary)]">
                <ReactMarkdown components={markdownComponents}>{content}</ReactMarkdown>
            </div>

            {/* Citations */}
            {!isUser && citations && citations.length > 0 && (
                <footer className="mt-4 border-t border-[var(--border-strong)] pt-3">
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">
                        Source grounds ({citations.length} citation{citations.length === 1 ? "" : "s"})
                    </div>
                    <div className="space-y-2">
                        {citations.map((cit, idx) => (
                            <a
                                key={idx}
                                href={cit.url || "#"}
                                target="_blank"
                                rel="noopener noreferrer"
                                title={cit.title || undefined}
                                className="flex flex-col gap-1 rounded-md border border-[var(--border-strong)] bg-[var(--bg-2)] px-2.5 py-2 text-[0.725rem] text-[var(--text-secondary)] transition-colors hover:border-[var(--link)] hover:bg-[var(--bg-3)]"
                                style={{ fontFamily: "var(--font-mono)" }}
                            >
                                <span className="truncate text-[0.7rem] font-semibold text-[var(--text-primary)]">
                                    [E{idx + 1}] {cit.title || "Untitled source"}
                                </span>
                                <span className="truncate text-[0.68rem] text-[var(--text-muted)]">
                                    {cit.arxiv_id ? `arXiv:${cit.arxiv_id}` : cit.url}
                                </span>
                                <div className="flex flex-wrap gap-2 text-[0.65rem] text-[var(--text-muted)]">
                                    {cit.authors?.length > 0 && <span>Authors: {topAuthorString(cit.authors)}</span>}
                                    <span>Relevance: {formatRelevance(cit.relevance_score)}</span>
                                    <ExternalLink className="h-3 w-3 shrink-0 text-[var(--link)]" />
                                </div>
                                {cit.snippet ? (
                                    <span className="line-clamp-2 text-[0.68rem] text-[var(--text-secondary)]">
                                        {cit.snippet}
                                    </span>
                                ) : null}
                            </a>
                        ))}
                    </div>
                </footer>
            )}
        </article>
    );
}
