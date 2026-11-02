# Project Documentation

Use this file as the docs entrypoint. When files disagree, trust the canonical
docs listed here over archived plans or historical phase notes.

## Canonical Docs

- [../README.md](../README.md) - project quickstart and current top-level
  overview.
- [../CLAUDE.md](../CLAUDE.md) - current architecture and coding guidance for
  AI agents.
- [research-workflow/README.md](./research-workflow/README.md) - production
  research workflow entrypoint.
- [research-workflow/ARCHITECTURE.md](./research-workflow/ARCHITECTURE.md) -
  current chat workflow architecture.
- [research-workflow/ROADMAP.md](./research-workflow/ROADMAP.md) - active
  research workflow roadmap.
- [research-workflow/CHECKLOG.md](./research-workflow/CHECKLOG.md) - durable
  decisions, verification logs, and handoff notes.

## Deployment Docs

- [DEPLOYMENT.md](./DEPLOYMENT.md) - canonical protected production release,
  verification, and rollback path.
- [OPENROUTER_SETUP.md](./OPENROUTER_SETUP.md)
- [LOCAL_BACKEND_DEPLOYMENT.md](./LOCAL_BACKEND_DEPLOYMENT.md) - local/private
  demo only; not the production source of truth.
- [QUICK_TUNNEL_GUIDE.md](./QUICK_TUNNEL_GUIDE.md)
- [CLOUDFLARE_TUNNEL_SETUP.md](./CLOUDFLARE_TUNNEL_SETUP.md)

## Archived Docs

Historical docs live under [archive/](./archive/). They are kept for provenance
and old implementation context only. They may describe Streamlit, the legacy
LangGraph chat path, old rollout flags, or abandoned source-selection behavior.

Root-level historical notes were moved to
[archive/root-notes/](./archive/root-notes/). Stale deployment notes were moved
to [archive/deployment/](./archive/deployment/).

Optional framework notes live under [frameworks/](./frameworks/). These are not
the production chat path unless a future plan explicitly promotes them.
