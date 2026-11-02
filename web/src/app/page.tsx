"use client";

import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { ArrowRight, Bot, Database, Search, Zap } from "lucide-react";
import Link from "next/link";
import { motion } from "framer-motion";

const features = [
  {
    icon: Search,
    title: "Deep Research",
    description: "Access and analyze millions of documents instantly.",
  },
  {
    icon: Database,
    title: "RAG Pipeline",
    description: "Advanced retrieval augmented generation for accurate, grounded answers.",
  },
  {
    icon: Bot,
    title: "AI Analysis",
    description: "Synthesize information with state-of-the-art language models.",
  },
  {
    icon: Zap,
    title: "High Performance",
    description: "Optimized retrieval with sub-second latency.",
  },
];

export default function Home() {
  return (
    <>
      {/* Sticky global header — solid white canvas + hairline rule (Cohere nav) */}
      <header
        role="banner"
        className="sticky top-0 z-50 border-b border-[var(--border-strong)] bg-[var(--bg-page)]"
      >
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-4">
          <Link
            href="/"
            aria-label="AI Research Agent home"
            className="text-xl tracking-tight text-[var(--text-primary)]"
            style={{ fontFamily: "var(--font-display)" }}
          >
            AI Research Agent
          </Link>
          <nav className="flex items-center gap-3" aria-label="Main navigation">
            <ThemeToggle />
            <Link href="/auth/login">
              <Button variant="default">Sign In</Button>
            </Link>
          </nav>
        </div>
      </header>

      <main id="main-content" className="flex-1">
        {/* Hero — monumental, carved ink headline on white canvas (no glow, no gradient text) */}
        <section className="relative px-6 pt-28 pb-20 text-center">
          <div className="relative z-10 mx-auto max-w-4xl">
            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              className="type-hero text-5xl text-[var(--text-primary)] md:text-7xl"
            >
              AI Research Agent
              <br />
              <span className="text-[var(--text-secondary)]">Next-Gen Document Intelligence</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1, duration: 0.5 }}
              className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-[var(--text-secondary)] md:text-xl"
            >
              Your intelligent research companion. Ask questions, retrieve verified citations,
              and synthesize knowledge from your document base — grounded by high-accuracy RAG search.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2, duration: 0.5 }}
              className="mt-10 flex flex-wrap justify-center gap-4"
            >
              <Link href="/auth/login">
                <Button variant="default" size="lg">
                  Get Started
                  <ArrowRight className="ml-2 h-5 w-5" />
                </Button>
              </Link>
              <Link href="https://github.com/qsang793/ai-research-agent" target="_blank" rel="noopener noreferrer">
                <Button variant="secondary" size="lg">
                  View Source Code
                </Button>
              </Link>
            </motion.div>
          </div>
        </section>

        {/* Features */}
        <section className="px-6 pb-32 pt-8" aria-labelledby="features-title">
          <div className="mx-auto max-w-7xl">
            <div className="mb-14 text-center">
              <h2
                id="features-title"
                className="type-section mb-3 text-3xl text-[var(--text-primary)]"
              >
                Designed for Precision Research
              </h2>
              <p className="mx-auto max-w-xl text-[var(--text-secondary)]">
                Four interconnected modules crafted for serious research workflows.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {features.map((feature, index) => {
                const Icon = feature.icon;
                return (
                  <GlassCard
                    key={feature.title}
                    elevated
                    className="p-8 transition-colors hover:border-[var(--accent)]"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 + index * 0.1, duration: 0.4 }}
                  >
                    <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-lg border border-[var(--border-strong)] bg-[var(--bg-2)] text-[var(--accent)]">
                      <Icon className="h-6 w-6" />
                    </div>
                    <h3 className="mb-3 text-xl font-medium text-[var(--text-primary)]">
                      {feature.title}
                    </h3>
                    <p className="leading-relaxed text-[var(--text-secondary)]">
                      {feature.description}
                    </p>
                  </GlassCard>
                );
              })}
            </div>
          </div>
        </section>
      </main>

      <footer role="contentinfo" className="border-t border-[var(--border-strong)] px-6 py-12 text-center">
        <p className="text-sm text-[var(--text-secondary)]">
          &copy; 2026 AI Research Agent. Built with accessible, token-driven design.
        </p>
      </footer>
    </>
  );
}
