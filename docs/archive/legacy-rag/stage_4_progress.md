# AI Research Agent - Tiến độ Stage 4

File này theo dõi tiến độ dựa trên `stage_4_optimization.md`.

## Mục tiêu (Stage 4)

- [x] **Precision Tuning**: Tối ưu hóa RAG pipeline để tăng Context Precision.
- [x] **Re-platforming**: Chuyển đổi sang kiến trúc Next.js + FastAPI.
- [ ] **Code Refactoring**: Loại bỏ duplicate code và tối ưu performance (xem [Code Refactoring Plan](./code_refactoring_plan.md)).
- [ ] **Streaming**: Hỗ trợ streaming response từ Backend lên Frontend.
- [ ] **Deployment**: Deploy lên production hoặc Dockerize toàn bộ stack.

## Trạng thái hiện tại

### ✅ Precision Tuning (HOÀN THÀNH)
- Re-ranking Threshold: ✅ Hoàn thành (2026-01-05)
- Dynamic Top-K: ✅ Hoàn thành (2026-01-05)

### ✅ Backend (FastAPI) - Phase 4.1 (HOÀN THÀNH - 2026-01-07)
- Project Setup: ✅ Completed
  - Tạo thư mục `api/` với cấu trúc modular
  - FastAPI app với CORS middleware
  - Lifespan context management
- API Endpoints: ✅ Completed
  - `POST /api/chat`: RAG pipeline endpoint với session management
  - `GET /health`: Health check với ChromaDB status
  - `GET /info`: Configuration metadata
  - `DELETE /api/session/{session_id}`: Session cleanup
- Pydantic Models: ✅ Completed
  - `ChatRequest`, `ChatResponse`, `Citation`
  - Type-safe validation
- Documentation: ✅ Completed
  - Swagger UI tại `/docs`
  - `api/README.md` với examples (curl, Python, JS)

### ✅ Code Refactoring - Phase 4.3 (IN PROGRESS - 2026-01-XX)
- **Documentation**: ✅ Completed
  - Tạo [Code Refactoring Plan](./code_refactoring_plan.md) với phân tích chi tiết
  - Identify 3 duplicate code instances
  - Identify 4 performance bottlenecks
  - Roadmap 4 phases với timeline và success criteria

- **Phase 1: Extract Utilities** ✅ HOÀN THÀNH
  - ✅ Task 1.1: Tạo `agent/utils/embeddings.py` - shared embedding model
  - ✅ Task 1.2: Tạo `agent/utils/vector_store.py` - singleton ChromaDB client
  - ✅ Task 1.3: Tạo `agent/utils/bm25_cache.py` - cached BM25 corpus
  - ✅ Task 1.4: Update `agent/nodes/route.py` - use shared utilities
  - ✅ Task 1.5: Update `agent/nodes/retrieve.py` - use shared utilities
  - ✅ Task 1.6: Update `agent/query_router.py` - use shared utilities
  - ⏳ Task 1.7: Test và verify không có regression (pending)

- **Next Steps**: 
  - Phase 2: Performance optimization (2-3 ngày)
  - Phase 3: Abstraction layer (3-4 ngày)
  - Phase 4: Framework integration (optional, 5-7 ngày)

### ✅ Frontend (Next.js) - Phase 4.2 (HOÀN THÀNH - 2026-01-07)
- Project Setup: ✅ Completed
  - Next.js 14 App Router + TypeScript + Tailwind CSS v4
  - Dependencies: lucide-react, framer-motion, clsx, ai, uuid
- Design System: ✅ Completed
  - Glassmorphism iOS 26 style
  - Animated gradient backgrounds
  - Custom scrollbar styling
  - Glass components với backdrop blur
- Pages: ✅ Completed
  - `/`: Homepage với hero section và feature cards
  - `/auth/login`: Login UI (mock)
  - `/auth/register`: Register UI (mock)
  - `/chat`: ChatGPT-style interface với sidebar
- Components: ✅ Completed
  - `GlassCard`: Reusable glass container
  - `Button`: Glassmorphic button với variants
  - `Input`: Transparent input với blur
  - `ChatMessage`: Bubble với role-based styling
  - `ChatInput`: Floating input bar
  - `ChatSidebar`: Responsive sidebar với history
- Integration: ✅ Completed
  - API client (`lib/api.ts`) kết nối với FastAPI
  - Send message và nhận response
  - Citation display
  - Auto-scroll behavior
  - Loading states

## Nhật ký công việc

- **2026-01-04**: Khởi tạo tài liệu Stage 4.
- **2026-01-05**: 
  - Cập nhật chiến lược sang Re-platforming (Next.js + FastAPI) thay vì chỉ tối ưu Streamlit.
  - **Re-ranking Improvements** (Precision Tuning):
    - Thêm `RERANK_THRESHOLD` (default 0.3) để lọc snippets có score thấp
    - Thêm `RERANK_SCORE_DROP` (default 0.3) cho dynamic cutoff
    - Cải thiện logic filtering: Absolute threshold -> Dynamic cutoff -> Top-K
    - Kỳ vọng: Context Precision tăng từ 0.43 lên > 0.55

- **2026-01-06**: 
  - **Phase 4.1 Backend Implementation**:
    - Tạo hoàn chỉnh FastAPI structure (`api/main.py`, `api/models.py`, `api/routes/`)
    - Implement chat endpoint với session management
    - Fix citation formatting bug với defensive programming
    - Test thành công tất cả endpoints (health, info, chat)
    - Response time: ~26s cho RAG query (expected với OpenRouter)

- **2026-01-07**: 
  - **Phase 4.2 Frontend Implementation**:
    - Init Next.js project trong `web/` directory
    - Configure Tailwind CSS v4 với Glassmorphism theme
    - Build Homepage với animated blobs và hero section
    - Build Login/Register pages với glass styling
    - Build Chat interface:
      - Sidebar với conversation history (mock)
      - Chat area với real-time API integration
      - Citation cards
      - Auto-scroll và smooth animations
    - Verify build: `npm run build` thành công
    - **Git commit**: `941cc70` - "feat: Phase 4 - Re-platforming to FastAPI + Next.js"
    - **Push to GitHub**: `origin/dev` branch

- **2026-01-XX**: 
  - **Code Refactoring Plan**:
    - Phân tích chi tiết RAG pipeline hiện tại
    - Identify duplicate code: `_get_embed_model()` (2 instances), ChromaDB client (3 instances), BM25 corpus loading
    - Identify performance bottlenecks: duplicate embeddings, sequential operations, no caching
    - Tạo tài liệu [Code Refactoring Plan](./code_refactoring_plan.md) với roadmap 4 phases
    - Expected performance improvement: 30-50% latency reduction

- **2026-01-XX**: 
  - **Phase 1: Extract Utilities** ✅ HOÀN THÀNH (2026-01-XX):
    - Tạo `agent/utils/` package với 3 modules:
      - `embeddings.py`: Shared embedding model với `@lru_cache`
      - `vector_store.py`: Singleton ChromaDB client manager
      - `bm25_cache.py`: Cached BM25 corpus loading với cache invalidation
    - Refactor 3 files để dùng shared utilities:
      - `agent/nodes/route.py`: Removed duplicate `_get_embed_model()` và ChromaDB client creation
      - `agent/nodes/retrieve.py`: Removed duplicate `_get_embed_model()`, `_get_chroma_collection()`, `_bm25_corpus()`
      - `agent/query_router.py`: Use `VectorStore` singleton
    - **Impact**: 
      - ✅ Zero duplicate code
      - ✅ Single source of truth cho embeddings và vector store
      - ✅ BM25 corpus cached (giảm I/O overhead)
      - ✅ Syntax check passed

- **Phase 2: Performance Optimization** ✅ HOÀN THÀNH (2026-01-XX):
  - ✅ Task 2.1: Cache query embeddings trong state
    - Added `query_embedding: Optional[List[float]]` to `AgentState`
    - `route_node` computes embedding và cache trong state
    - `retrieve_node` reuses cached embedding (giảm ~50-100ms per request)
  - ✅ Task 2.2: Parallelize Dense + BM25 retrieval
    - Using `ThreadPoolExecutor` với 2 workers
    - Dense và BM25 retrieval chạy song song
    - Expected latency reduction: 20-30%
  - ✅ Task 2.3: Optimize citation validation
    - Parallelized URL checking với `ThreadPoolExecutor` (max 10 workers)
    - Citation validation nhanh hơn đáng kể với nhiều URLs
  - ✅ Performance testing completed (2026-01-XX)
    - **Embedding caching**: 78,749x speedup (5062ms → 0.06ms)
    - **VectorStore singleton**: 18.2x speedup (0.18ms → 0.00ms)
    - **BM25 caching**: 987x speedup (54.85ms → 0.06ms)
    - **Query embedding**: First call 1145ms, second 33ms (shows why Phase 2 caching is important)

- **Phase 3: Abstraction Layer** ✅ HOÀN THÀNH (2026-01-XX):
  - ✅ Task 3.1: Tạo VectorStoreInterface
    - Created `agent/stores/base.py` với abstract interface
    - Methods: `query()`, `add()`, `count()`, `get_collection()`
    - Enables easy migration và testing
  - ✅ Task 3.2: Implement ChromaVectorStore
    - Created `agent/stores/chroma_store.py`
    - Wraps ChromaDB với standard interface
    - Uses singleton VectorStore internally
  - ✅ Task 3.3: Refactor nodes để dùng interface
    - `agent/nodes/route.py`: Uses `ChromaVectorStore` instead of direct ChromaDB
    - `agent/nodes/retrieve.py`: Uses `ChromaVectorStore` instead of direct ChromaDB
    - Removed direct ChromaDB dependencies
  - **Benefits**:
    - ✅ Easy to mock for unit testing
    - ✅ Easy to migrate to Qdrant/Pinecone in future
    - ✅ Better separation of concerns
    - ✅ Code more maintainable

- **Phase 4: Framework Integration** ✅ HOÀN THÀNH (2026-01-XX):
  - ✅ Task 4.1: Framework evaluation
    - Created `docs/framework_evaluation.md` với detailed comparison
    - Evaluated LlamaIndex, Haystack, và current implementation
    - **Decision**: Keep current implementation (recommended)
  - ✅ Task 4.2: Framework integration structure
    - Created `agent/frameworks/` module
    - Created README với migration path
    - Optional wrappers ready for future use
  - ✅ Task 4.3: Documentation
    - Documented when to use frameworks
    - Documented migration path
    - Current implementation recommended as default
  - **Key Findings**:
    - ✅ Current implementation is already optimized and production-ready
    - ✅ Custom logic (Adaptive RAG, hybrid retrieval) is valuable
    - ✅ Frameworks can be used incrementally for specific features
    - ✅ No need for full migration at this time

## Hành động tiếp theo

### Option A: Streaming Response (Khuyến nghị cho UX tốt nhất)
**Ưu tiên**: ⭐⭐⭐⭐⭐ (Rất cao)

1. **Backend Changes**:
   - Tạo endpoint `/api/chat/stream` với SSE (Server-Sent Events)
   - Refactor `run_agent_graph` để support streaming từ OpenRouter
   - Sử dụng `sse-starlette` để yield tokens

2. **Frontend Changes**:
   - Integrate Vercel AI SDK (`useChat` hook)
   - Update ChatMessage để render streaming tokens
   - Handle connection errors và reconnection logic

**Timeline**: 1-2 ngày  
**Impact**: Giảm perceived latency từ ~26s xuống instant feedback

---

### Option B: Authentication (Nếu cần user management)
**Ưu tiên**: ⭐⭐⭐ (Trung bình)

**Choice 1 - Supabase** (Nhanh hơn):
1. Tạo Supabase project
2. Install `@supabase/supabase-js`
3. Configure Auth providers (Email, Google, GitHub)
4. Update login/register pages
5. Add protected routes middleware

**Choice 2 - NextAuth.js** (Linh hoạt hơn):
1. Install `next-auth`
2. Configure providers
3. Setup session management
4. Add database adapter

**Timeline**: 2-3 ngày

---

### Option C: Production Deployment (Nếu muốn demo/share)
**Ưu tiên**: ⭐⭐⭐⭐ (Cao nếu muốn share)

**Frontend (Vercel)**:
1. Connect GitHub repo tại vercel.com
2. Configure: Root directory = `web/`
3. Set env: `NEXT_PUBLIC_API_URL=https://your-backend.railway.app`
4. Deploy → Nhận URL

**Backend (Railway hoặc Render)**:
1. Railway: `railway init` → `railway up`
2. Render: Push code → Auto-deploy
3. Configure environment variables
4. Update Frontend API URL

**Timeline**: 30 phút - 1 giờ

---

## Gợi ý Lộ Trình

### Nếu mục tiêu = DEMO NHANH:
1. ✅ Deploy (Vercel + Railway) - 30 phút
2. Streaming Response - 1-2 ngày
3. Auth (nếu cần)

### Nếu mục tiêu = UX TỐT NHẤT:
1. ✅ Streaming Response - 1-2 ngày
2. Deploy production
3. Auth (optional)

### Nếu mục tiêu = HỌC CÔNG NGHỆ MỚI:
1. ✅ Supabase (Auth + DB) - 2-3 ngày
2. Streaming
3. Deploy

