# UI Audit — ai-research-agent / web (2026-06-14)

> Supersedes the 2026-05-24 audit. Since then the codebase added CSS-variable design
> tokens, a light theme + theme toggle, ARIA attributes, and a `prefers-reduced-motion`
> guard — so the prior High items (no tokens / zero ARIA / hardwired dark) are largely
> resolved. This pass re-audits the current state **against `DESIGN.md` (the Cohere system)**.

## Stack
- Framework: Next.js 16 (App Router) + React 19
- Build tool: next (Turbopack), PostCSS
- CSS: Tailwind v4 + CSS-variable design tokens in `src/app/globals.css`; component variants via `class-variance-authority` (cva). `cn()` (clsx + tailwind-merge) for class composition.
- State: native React + Vercel AI SDK (`@ai-sdk/react` `useChat`); auth via next-auth v5. No Redux/Zustand.

## Pages / Routes (user-facing only)
- `/` — `src/app/page.tsx` (landing, 174 lines)
- `/chat` — `src/app/chat/page.tsx` (chat workspace, 301 lines)
- `/auth/login` — `src/app/auth/login/page.tsx` (156 lines)
- `/auth/register` — `src/app/auth/register/page.tsx` (185 lines)
- Shared chrome — `src/app/layout.tsx` (GradientBackground + AuthProvider)
- (Non-UI API routes under `src/app/api/*` excluded)

Components: `ui/` (button, input, glass-card, gradient-background, dropdown-menu, theme-toggle), `chat/` (chat-input, chat-message, chat-sidebar, search-mode-selector), `providers/`.

## Style approach
Styling is already **centralized and token-driven**: a `:root` / `.dark` block in `globals.css` defines colors, shadows, fonts, and glass surfaces as CSS variables, and components reference them (`bg-[var(--accent)]`). No hardcoded hex in any `.tsx`, no `<img>` missing `alt`, all files healthy-sized (largest 301 lines). The architecture is good — the problem is the **values**: the current system implements a **glassmorphism** aesthetic (backdrop-blur, animated gradient blob, drop shadows, violet/blue accent, Inter / Space Grotesk / JetBrains Mono, dark-by-default). DESIGN.md mandates the **Cohere** system: flat (no shadows), white-canvas default with deep-green/navy bands, near-black pill CTAs, coral editorial accents, blue links, and a CohereText / Unica77 / CohereMono type split.

## Pain points (prioritized against DESIGN.md)

### 🔴 High
- **Token values implement the wrong design language.** Accent is violet `#8b5cf6` / blue `#3b82f6`; DESIGN.md wants near-black `#17171c` primary, deep-green `#003c33`, navy `#071829`, coral `#ff7759`, blue links `#1863dc`. Tokens are already well-used → highest-leverage fix is re-valuing them, not rewriting components.
- **Wrong font stack + missing type split.** Loads Inter / Space Grotesk / JetBrains Mono; DESIGN.md wants CohereText (display) / Unica77 (body/UI) / CohereMono (labels) with documented fallbacks. No token covers the 12-step display→micro hierarchy.
- **Flat-design violations baked into global chrome.** `GradientBackground` (animated `blob`) renders in the root layout on every page; `--shadow-sm/md/lg` + `.glass-card-hover` add drop shadows/lift. DESIGN.md: "Cohere is mostly flat… do not add heavy drop shadows… do not use saturated gradients as normal UI backgrounds."
- **Dark-by-default vs white-canvas default.** Theme init defaults to dark; Cohere's dominant surface is white canvas, with deep green/navy used as deliberate full-width bands.

### 🟡 Medium
- **Button vocabulary mismatch.** `button.tsx` defaults to a `glass` variant with `rounded-md`. Cohere: `button-primary` = near-black **pill** (32px); `button-secondary` = underlined **text link**; plus a `pill-outline` for filters. Variants need remapping.
- **No radius / spacing scale tokens.** DESIGN.md defines explicit `rounded` (xs→full) and `spacing` (xxs→section 80px) scales; `globals.css` centralizes shadows/colors/fonts but not these, so radius/spacing are ad-hoc Tailwind utilities.
- **Missing Cohere component primitives.** No announcement-bar, trust-logo-strip, dark-feature-band, research-table, blog-filter-chip, hero-photo-card — the landing page can't express the target system without them.

### 🟢 Low
- **Thin responsive coverage.** ~14 responsive prefixes total across all `.tsx`. Workable now, but Cohere's split-hero → stacked behavior across 6 breakpoints will need attention.
- **Legacy components become dead weight.** `glass-card.tsx`, `gradient-background.tsx`, and the glass `@theme` utilities go orphaned after the re-skin (flag, don't delete pre-existing until their last consumer is migrated).

## Recommendation
**Scenario C** (brownfield, keep stack). The Next.js + Tailwind v4 + cva + CSS-token architecture is sound and well-organized; this is a **design-system re-skin** (re-value tokens, swap fonts, remap primitives, remove glass/shadow chrome), not a rewrite. Estimate: days, not weeks.
