# AI Research Agent - Stage 4: Tối ưu hóa & Re-platforming

## Tổng quan
Stage 4 tập trung vào việc tinh chỉnh độ chính xác của hệ thống và thực hiện **Re-platforming** (chuyển đổi nền tảng) từ Streamlit sang kiến trúc hiện đại hơn (Next.js + FastAPI) để sẵn sàng cho Production.

## Mục tiêu

### 1. Tinh chỉnh độ chính xác (RAG Optimization)
- **Re-ranking Threshold**: Tăng độ khắt khe (ví dụ: > 0.5) để giảm nhiễu (hiện tại Context Precision chỉ khoảng ~0.43).
- **Hybrid Search Weights**: Thử nghiệm tỷ lệ giữa Dense và Sparse (ví dụ: 0.3/0.7) để cân bằng giữa Recall và Precision.
- **Dynamic Top-K**: Triển khai phương pháp "Elbow" hoặc cắt dựa trên điểm số để ngừng lấy thêm chunks khi độ liên quan giảm mạnh.

### 2. Re-platforming (Next.js + FastAPI)
- **Backend (FastAPI)**:
  - Chuyển đổi logic Agent hiện tại thành API Server chuẩn.
  - Hỗ trợ Async và Streaming response.
  - Expose endpoints: `/chat`, `/search`, `/feedback`.
- **Frontend (Next.js + TypeScript + Tailwind)**:
  - Xây dựng giao diện chat hiện đại, tối ưu UX.
  - Sử dụng Vercel AI SDK để quản lý state và streaming.
  - Tận dụng Server Components cho hiệu năng và SEO.
  - **Vibe Coding**: Sử dụng Tailwind để styling nhanh chóng và linh hoạt.

### 3. Hiệu năng & Độ ổn định
- **Caching**: Triển khai caching mạnh mẽ cho Search và ArXiv API calls.
- **Async Optimization**: Đảm bảo tất cả các tác vụ I/O bound hoàn toàn không chặn (non-blocking).
- **Cost Tracking**: Theo dõi lượng token sử dụng và chi phí API.

### 4. Deployment
- **Dockerization**: Containerize cả Backend và Frontend.
- **Compose**: Orchestrate toàn bộ stack (Next.js + FastAPI + ChromaDB) với Docker Compose.

## Lộ trình

### Phase 4.1: Backend API ✅ HOÀN THÀNH
- [x] **FastAPI Setup**: Khởi tạo project FastAPI, wrap `agent/pipeline.py`.
- [x] **API Endpoints**: Implement `/api/chat` endpoint với JSON response.
- [x] **Pydantic Models**: Type-safe request/response schemas.
- [x] **Session Management**: In-memory conversation memory.
- [x] **CORS Configuration**: Cho phép Next.js frontend gọi API.
- [x] **Documentation**: Swagger UI tự động tại `/docs`.

### Phase 4.2: Frontend Development ✅ HOÀN THÀNH
- [x] **Next.js Setup**: Khởi tạo project Next.js 14 + TS + Tailwind CSS v4.
- [x] **Glassmorphism Design**: iOS 26 style với backdrop blur và animated gradients.
- [x] **Homepage**: Hero section với feature cards.
- [x] **Auth UI**: Login/Register pages (mock).
- [x] **Chat Interface**: ChatGPT-style layout với sidebar.
- [x] **Integration**: Kết nối với FastAPI backend.
- [x] **Citations UI**: Hiển thị nguồn trích dẫn rõ ràng.
- [x] **Auto-scroll**: Tự động cuộn xuống tin nhắn mới.

### Phase 4.3: Advanced Features (KẾ TIẾP)

#### Option A: Streaming Response ⚡ (Ưu tiên cao)
**Mục tiêu**: Hiển thị từng token khi LLM tạo ra, giảm perceived latency từ ~26s.

**Backend Changes**:
- [ ] Thêm endpoint `/api/chat/stream` với Server-Sent Events (SSE).
- [ ] Refactor `run_agent_graph` để support streaming từ LLM.
- [ ] Handle streaming với `sse-starlette`.

**Frontend Changes**:
- [ ] Tích hợp Vercel AI SDK `useChat` hook.
- [ ] Update ChatMessage component để hiển thị streaming tokens.
- [ ] Handle loading states và connection errors.

**Tech Stack**:
- Backend: `sse-starlette`, `asyncio`
- Frontend: `ai` package (Vercel AI SDK)

---

#### Option B: Authentication 🔐 (Ưu tiên trung bình)

**Option B1 - Supabase** (Khuyến nghị nếu muốn nhanh):
- [ ] Tạo Supabase project và configure Auth providers.
- [ ] Install `@supabase/supabase-js` và `@supabase/auth-helpers-nextjs`.
- [ ] Update login/register pages với Supabase Auth.
- [ ] Thêm protected routes middleware.
- [ ] Setup PostgreSQL database cho user data.

**Ưu điểm**:
- All-in-one: Auth + Database + Storage
- Free tier: 50K monthly active users
- Built-in user management UI

**Option B2 - NextAuth.js**:
- [ ] Install `next-auth` và configure providers (Google, GitHub).
- [ ] Tạo `app/api/auth/[...nextauth]/route.ts`.
- [ ] Setup session management.
- [ ] Add middleware protection.
- [ ] Configure database adapter (Prisma/Drizzle).

**Ưu điểm**:
- Không vendor lock-in
- Linh hoạt với database bất kỳ
- Phổ biến, nhiều tài liệu

---

#### Option C: Production Deployment 🚀 (Ưu tiên cao nếu muốn demo)

**Frontend Deployment (Vercel)**:
- [ ] Connect GitHub repo với Vercel.
- [ ] Configure build settings (Root: `web/`).
- [ ] Set environment variables: `NEXT_PUBLIC_API_URL`.
- [ ] Deploy và nhận production URL.

**Backend Deployment**:

**Option C1 - Railway.app**:
- [ ] Install Railway CLI: `npm install -g @railway/cli`
- [ ] Login: `railway login`
- [ ] Init project: `railway init`
- [ ] Deploy: `railway up`
- [ ] Configure environment variables.

**Option C2 - Render.com**:
- [ ] Tạo `render.yaml` config.
- [ ] Connect GitHub repo.
- [ ] Auto-deploy khi push code.

**Free Tiers**:
- Vercel: Unlimited deploys
- Railway: $5/month credit
- Render: 512MB RAM free

---

### Phase 4.4: Deployment & Containerization (Tương lai)
- [ ] **Docker**: Tạo Dockerfile cho BE và FE.
- [ ] **Compose**: Tạo `docker-compose.yml` để chạy toàn bộ hệ thống.
- [ ] **Documentation**: Cập nhật hướng dẫn chạy và deploy.

## Chỉ số thành công
- **Context Precision**: Tăng từ 0.43 lên > 0.60.
- **Latency**: Giảm độ trễ cảm nhận xuống < 1s (nhờ Streaming).
- **Architecture**: ✅ Chuyển đổi thành công sang mô hình Client-Server tách biệt.
- **UX**: ✅ Giao diện hiện đại với Glassmorphism design.

## Khuyến nghị Lộ Trình

### Nếu mục tiêu là Demo nhanh:
1. **Deploy ngay** (Frontend: Vercel, Backend: Railway) → 30 phút
2. Streaming Response → 1-2 ngày
3. Authentication → Sau

### Nếu mục tiêu là UX tốt nhất:
1. **Streaming Response** → 1-2 ngày
2. Deploy lên production
3. Authentication (nếu cần)

### Nếu muốn học công nghệ mới:
1. **Supabase** (Auth + DB + Storage) → 2-3 ngày
2. Streaming
3. Deploy

