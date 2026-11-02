"use client";

import { useEffect, useState } from "react";
import { Sun, Moon, Monitor } from "lucide-react";
import { Button } from "@/components/ui/button";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "theme";

/** Resolve a Theme to an actual dark/light boolean and apply it to <html>. */
function applyTheme(theme: Theme) {
    const root = document.documentElement;
    const prefersDark =
        typeof window !== "undefined" &&
        window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = theme === "dark" || (theme === "system" && prefersDark);
    // Keep both signals in sync: the .dark class drives Tailwind `dark:` utilities,
    // the data-theme attribute drives the CSS-variable token system.
    root.classList.toggle("dark", isDark);
    root.setAttribute("data-theme", isDark ? "dark" : "light");
}

export function ThemeToggle({ className }: { className?: string }) {
    // Default to light for deterministic SSR output, then hydrate from localStorage
    // on client after first paint.
    const [theme, setTheme] = useState<Theme>("light");

    // Read stored preference after mount to avoid SSR/client hydration drift.
    useEffect(() => {
        const raf = requestAnimationFrame(() => {
            const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
            if (stored === "light" || stored === "dark" || stored === "system") {
                setTheme(stored);
            }
        });

        return () => cancelAnimationFrame(raf);
    }, []);

    // Apply on change, and follow OS changes while in "system" mode.
    useEffect(() => {
        applyTheme(theme);
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        const onChange = () => {
            if (theme === "system") applyTheme("system");
        };
        mq.addEventListener("change", onChange);
        return () => mq.removeEventListener("change", onChange);
    }, [theme]);

    const cycle = () => {
        const next: Theme =
            theme === "system" ? "light" : theme === "light" ? "dark" : "system";
        setTheme(next);
        localStorage.setItem(STORAGE_KEY, next);
    };

    const Icon = theme === "system" ? Monitor : theme === "light" ? Sun : Moon;
    const label = `Theme: ${theme} (click to change)`;

    return (
        <Button
            variant="ghost"
            size="icon"
            onClick={cycle}
            aria-label={label}
            title={label}
            className={className}
        >
            <Icon className="h-5 w-5" />
        </Button>
    );
}
