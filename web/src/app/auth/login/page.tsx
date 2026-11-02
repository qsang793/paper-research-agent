"use client";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Github } from "lucide-react";
import Link from "next/link";
import { signIn } from "next-auth/react";
import { useState } from "react";

export default function LoginPage() {
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSignIn = async () => {
        setIsSubmitting(true);
        await signIn("github", { callbackUrl: "/chat" });
    };

    return (
        <>
            <a
                href="#main-auth"
                className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-[var(--accent)] focus:px-4 focus:py-2 focus:text-[var(--background)]"
            >
                Skip to sign in
            </a>
            <ThemeToggle className="absolute right-4 top-4 z-50" />
            <main id="main-auth" className="flex flex-1 items-center justify-center px-4 py-8">
                <GlassCard elevated className="w-full max-w-md p-8 text-center md:p-10">
                    <Link
                        href="/"
                        className="text-2xl font-bold tracking-tight text-[var(--text-primary)]"
                        style={{ fontFamily: "var(--font-display)" }}
                    >
                        AI Research Agent
                    </Link>
                    <p className="mb-8 mt-2 text-sm text-[var(--text-secondary)]">
                        Sign in with your GitHub identity to continue your research.
                    </p>
                    <Button
                        type="button"
                        variant="default"
                        className="h-11 w-full gap-2"
                        disabled={isSubmitting}
                        onClick={handleSignIn}
                    >
                        <Github className="h-5 w-5" aria-hidden="true" />
                        {isSubmitting ? "Redirecting…" : "Continue with GitHub"}
                    </Button>
                </GlassCard>
            </main>
        </>
    );
}
