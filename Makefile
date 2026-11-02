
# -----------------------------------------------------------------------------
# AI Agent - Makefile
# -----------------------------------------------------------------------------

.PHONY: help install install-api install-web run-api run-web dev clean migrate-e5 test-e5 eval-research eval-research-live eval-research-gate eval-conversational-memory test-memory-postgres docker-build docker-run docker-test compose-db compose-up compose-down compose-logs compose-ps setup-env start-local stop-local tunnel stop-tunnel export-reqs

# --- Help ---
help:
	@echo "🚀 AI Research Agent - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       - Install dependencies for both Backend and Frontend"
	@echo "  make install-api   - Install Python dependencies for Backend"
	@echo "  make install-web   - Install Node dependencies for Frontend"
	@echo "  make setup-env     - Setup environment files from templates"
	@echo ""
	@echo "Development:"
	@echo "  make run-api       - Run Backend (FastAPI) at http://localhost:8000"
	@echo "  make run-web       - Run Frontend (Next.js) at http://localhost:3000"
	@echo "  make dev           - Run BOTH Backend and Frontend concurrently"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container locally"
	@echo "  make docker-test   - Test Docker container"
	@echo "  make compose-db    - Start Postgres/pgvector for durable memory"
	@echo "  make compose-up    - Start API + Postgres/pgvector stack"
	@echo "  make compose-down  - Stop Docker Compose stack"
	@echo "  make compose-logs  - Follow Docker Compose logs"
	@echo "  make compose-ps    - Show Docker Compose services"
	@echo ""
	@echo "Local Production:"
	@echo "  make start-local   - Start backend + Cloudflare tunnel in tmux"
	@echo "  make stop-local    - Stop local production environment"
	@echo ""
	@echo "Quick Tunnel (Free, No Domain):"
	@echo "  make tunnel        - Start Quick Tunnel (auto-updates .env.local)"
	@echo "  make stop-tunnel   - Stop Quick Tunnel"
	@echo ""
	@echo "Migration:"
	@echo "  make migrate-e5    - Migrate ChromaDB to e5-base-v2 embeddings (with backup)"
	@echo "  make test-e5       - Test e5-base-v2 performance"
	@echo "  make eval-research - Run deterministic research workflow eval"
	@echo "  make eval-research-live - Run live research workflow eval"
	@echo "  make eval-research-gate - Run live research workflow promotion gate"
	@echo "  make eval-conversational-memory - Validate conversational-memory golden set shape"
	@echo "  make test-memory-postgres - Run PostgresMemoryStore integration tests (needs compose-db)"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean         - Remove temporary files (pycache, etc)"

# --- Installation ---
install: install-api install-web

install-api:
	@echo "Installing Backend dependencies (UV)..."
	uv sync --extra api

install-web:
	@echo "Installing Frontend dependencies..."
	cd web && npm install

# --- Running ---
run-api:
	@echo "Starting Backend (UV)..."
	uv run uvicorn api.main:app --reload --port 8000

run-web:
	@echo "Starting Frontend..."
	cd web && npm run dev

dev:
	@echo "Starting Full Stack (Backend + Frontend)..."
	make -j 2 run-api run-web

# --- Migration ---
migrate-e5:
	@echo "🔄 Migrating ChromaDB to e5-base-v2 embeddings..."
	uv run python scripts/migrate_to_e5.py --input ./cache/clean --chroma ./chroma --backup

test-e5:
	@echo "🧪 Testing e5-base-v2 performance..."
	uv run python scripts/test_e5_performance.py --chroma ./chroma --backup-dir $$(ls -td ./chroma_backup_* 2>/dev/null | head -1)

eval-research:
	@echo "📊 Running research workflow eval..."
	uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --dry-run

eval-research-live:
	@echo "📊 Running live research workflow eval..."
	uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --top-k 10

eval-research-gate:
	@echo "📊 Running live research workflow promotion gate..."
	@mkdir -p .cache/research
	uv run python eval/research_eval.py --dataset eval/research_golden_set.jsonl --top-k 10 --min-recall 0.55 --min-mrr 0.35 --sleep 3 --resume .cache/research/eval-research-gate.json --out .cache/research/eval-research-gate.json --require-provider-config

eval-conversational-memory:
	@echo "📘 Validating conversational-memory eval golden set..."
	uv run python eval/conversational_memory_eval.py

test-memory-postgres:
	@test -n "$$MEMORY_TEST_DATABASE_URL" || (echo "❌ Set MEMORY_TEST_DATABASE_URL (start DB first: make compose-db)"; exit 1)
	uv run pytest tests/integration/test_postgres_store_integration.py -v

# --- Utilities ---
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".next" -exec rm -rf {} +

# --- Export requirements.txt fallback from uv.lock ---
export-reqs:
	@echo "📤 Exporting requirements.txt from uv.lock..."
	uv export --no-hashes --no-dev --extra api -o requirements.txt

# --- Docker ---
docker-build:
	@echo "🐳 Building Docker image..."
	docker build -t ai-research-agent:latest .

docker-run:
	@echo "🐳 Running Docker container..."
	docker run -p 8000:8000 --env-file .env ai-research-agent:latest

docker-test: docker-build
	@echo "🧪 Testing Docker container..."
	docker run -d -p 8000:8000 --env-file .env --name ai-agent-test ai-research-agent:latest
	@sleep 10
	@curl -f http://localhost:8000/health || (docker stop ai-agent-test && docker rm ai-agent-test && exit 1)
	@echo "✅ Docker container is healthy"
	@docker stop ai-agent-test
	@docker rm ai-agent-test

compose-db:
	@echo "🐘 Starting Postgres/pgvector for durable memory..."
	docker compose up -d postgres

compose-up:
	@echo "🐳 Starting API + Postgres/pgvector stack..."
	docker compose up --build

compose-down:
	@echo "🛑 Stopping Docker Compose stack..."
	docker compose down

compose-logs:
	docker compose logs -f

compose-ps:
	docker compose ps

# --- Local Production ---
start-local:
	@echo "🚀 Starting local production environment..."
	@bash scripts/start_local_production.sh

stop-local:
	@echo "🛑 Stopping local production environment..."
	@tmux kill-session -t ai-agent || echo "No active session found"

# --- Quick Tunnel (Free, No Domain) ---
tunnel:
	@echo "🌐 Starting Quick Tunnel (auto-updates Frontend .env.local)..."
	@bash scripts/start_quick_tunnel.sh

stop-tunnel:
	@echo "🛑 Stopping Quick Tunnel..."
	@pkill -f "cloudflared tunnel" || echo "No tunnel running"
	@rm -f /tmp/cloudflared-tunnel.pid /tmp/cloudflared-tunnel.log
	@echo "✅ Tunnel stopped"

# --- Environment Setup ---
setup-env:
	@echo "📝 Setting up environment files..."
	@if [ ! -f .env ]; then cp .env.example .env && echo "✅ Created .env from .env.example"; fi
	@if [ ! -f web/.env.local ]; then cp web/.env.example web/.env.local && echo "✅ Created web/.env.local from web/.env.example"; fi
	@echo "⚠️  Don't forget to fill in API keys in .env and web/.env.local"
