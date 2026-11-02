# Integration Plan — 2026-05-31

## Verdict: PROCEED WITH CAUTION

**0 blockers.** The Lovable/AI Studio export is scenario-C HTML+CSS — it ships **no API calls of its own**; its behavior is described in plain-English interaction comments. The real wiring stays in the existing `web/` frontend, which already talks to the backend correctly. Every endpoint the design's core flows touch (login, signup, chat, streaming chat, delete session) **already exists in `api/` with matching request/response shapes**, and the design explicitly reuses the existing NextAuth credentials flow — so it introduces no new auth pattern. Proceed to `/ui-translator`, but go in aware of one feature gap (sidebar history has no backend) and one security note (chat endpoints are unauthenticated). Neither blocks the visual redesign.

## Blockers (🚨)

**None.**

## Medium issues (⚠️)

| Issue | Detail | Proposed adapter | Effort |
|---|---|---|---|
| Sidebar chat-history has no backend | Design `chat.html` renders a "Recents" list + empty state. Existing FE `chat-sidebar.tsx:18` already hardcodes mock history (*"backend doesn't support listing yet"*). Backend has only `DELETE /api/session/{id}` — no `GET /api/sessions`, and the `sessions` dict (`chat.py:27`) is in-memory with no per-user association. | **For the redesign:** keep the current mock data — the port just restyles the list, so no backend work needed. **Only if you want real history:** backend needs per-user session persistence + a `GET /api/sessions` list endpoint (data-model change, separate effort — not part of this UI work). | 0 (keep mock) / multi-day (real history, out of scope) |

## Minor issues (ℹ️)

- **Sidebar user profile is mock, but real data is already available.** `chat-sidebar.tsx:99-107` hardcodes "User Name / user@example.com". The real name + email are already in the NextAuth session (`auth.ts` session callback). Wire `useSession()` into the sidebar during the port — no backend call needed.
- **Backend login issues a JWT that the FE discards.** `POST /api/auth/login` returns a `token` (`auth.py:100-106`), but the NextAuth `authorize` callback (`auth.ts:46-50`) returns only `{id, email, name}` and drops it. Consequently the BE chat endpoints (`/api/chat`, `/api/chat/stream`) require **no auth** and accept any caller. Not a redesign concern, but flag for your developer — production auth should send the token and the chat routes should verify it.
- **"View Source" is a placeholder.** Landing page links to `https://github.com/your-repo` (`page.tsx:80`); design `landing.html` has a "view source code modal/redirect" comment. Cosmetic — point it at the real repo or remove during the port.
- **FE-only behaviors in the design are port details, not integration concerns.** New-chat-without-reload (replaces `window.location.reload()`), light/dark theme toggle (`data-theme` on `<html>`), and inline signup success (replaces `alert()`) involve **no backend** — `/ui-translator` handles them when porting the components.

## Endpoint match table

| Design / existing FE expects | Backend provides (`api/`) | Match? | Severity |
|---|---|---|---|
| `POST /api/auth/login` → `{id, email, name, token}` | `auth.py:69` `POST /api/auth/login` → `UserResponse{id, email, name, token}` | ✅ exact | — |
| `POST /api/auth/signup {email, password, name}` | `auth.py:38` `POST /api/auth/signup` → `{message, email}` | ✅ match | — |
| `POST /api/chat/stream` (mode, search_source) | `chat.py:191` `POST /api/chat/stream` | ✅ match | — |
| `POST /api/chat` → `{answer, citations[], session_id, response_time_ms}` | `chat.py:67` `ChatResponse` (same fields) | ✅ exact | — |
| `DELETE /api/session/{id}` | `chat.py:350` `DELETE /api/session/{session_id}` | ✅ exact | — |
| Citation `{title, authors[], url, arxiv_id?, relevance_score, snippet?}` | `models.Citation` (same fields, `_format_citations` `chat.py:30`) | ✅ exact | ℹ️ confirm design's citation block maps these fields during port |
| Search modes Auto / Search DB / Chat + Mixed/arXiv/Tavily | `ChatRequest.mode` + `search_source: "mixed"\|"arxiv"\|"tavily"` (`api.ts:17-23`) | ✅ match | — |
| `GET /api/sessions` (list history) | **absent** | ❌ missing | ⚠️ Medium (see above — not required for redesign) |

## Auth pattern check

- **Design assumes:** the existing NextAuth credentials flow — `login.html` comment: *"query NextAuth /api/auth/callback/credentials server endpoints."* No new auth scheme.
- **Existing FE provides:** NextAuth v5 Credentials provider (`auth.ts`) → calls backend `POST /api/auth/login` → stores `{id, email, name}` in a NextAuth JWT session cookie.
- **Backend provides:** `POST /api/auth/login` (bcrypt + JWT), `POST /api/auth/signup`, `GET /api/auth/verify`. Chat endpoints require no auth.
- **Compatible?** **Yes.** The design reuses the existing flow end-to-end; no auth change is needed to port the redesign. (Separate hardening note: the BE-issued JWT is currently unused and chat routes are open — pre-existing, flagged above as Minor, not a blocker.)

## Next step

✅ **PROCEED** — Invoke `/ui-translator` (scenario C). Port one component at a time, preserving the export's design tokens (the 60-token `:root` / `[data-theme="dark"]` system in `lovable-export/styles.css`) while rewriting markup into the existing Next.js + React + shadcn components. Keep the sidebar on mock history for now; treat real history as a separate backend task if you want it later.
