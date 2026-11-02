# AI Research Agent — Stage 3 Progress (Quality & Robustness)

This file tracks progress against `stage_3_quality.md`.

## Goals (Stage 3)

- [ ] **Web Search Integration**: Tích hợp Tavily API để bổ sung nguồn tin ngoài ArXiv.
- [ ] **Query Transformation**: Rewrite câu hỏi người dùng để search hiệu quả hơn.
- [ ] **Advanced Retrieval**: Hoàn thiện Hybrid Search (Dense + BM25) và Re-ranking.
- [ ] **Evaluation**: Thiết lập pipeline đánh giá tự động (Ragas/TruLens).
- [ ] **Robustness**: Xử lý lỗi API, timeout, và fallback hợp lý.

## Current Status

- **Search & Ingestion**
  - Tavily API Integration: ☑️ (Hoàn thành - song song với ArXiv trong search_node)
  - Query Rewrite Node: ☑️ (Hoàn thành)
  
- **Retrieval**
  - Hybrid Search (BM25 + Chroma): ☑️ (Đã implement với RRF merge)
  - Adaptive RAG (Confidence-based routing): ☑️ (Hoàn thành)
  - Re-ranking: ☑️ (Hoàn thành - cross-encoder integrated vào graph)

- **Robustness & Quality**
  - Dynamic Intent Confidence: ☑️ (Hoàn thành - LLM-first approach)
  - KB Confidence Calculation: ☑️ (Hoàn thành - Cosine Similarity chuẩn)
  - KB Relevance Filtering: ☑️ (Hoàn thành - penalize irrelevant docs)
  - Intent Classification Strategy: ☑️ (LLM-first, fallback to rule-based)
  - Memory Management: ☑️ (Hoàn thành - ConversationMemory tích hợp vào prompt + Recent History Injection)
  - Error Handling: ☑️ (Hoàn thành - 2026-01-04)

- **Evaluation**
  - Setup Ragas/TruLens: ☑️ (Hoàn thành - Ragas framework với 4 metrics)
  - Test Set Creation: ☑️ (Hoàn thành - 10 câu hỏi covering different types/difficulties)

## Work Log

- **2025-11-xx**: Khởi tạo tài liệu Stage 3.
- **2025-12-29**: Tích hợp Tavily API cho web search.
- **2025-12-29**: Implement Query Rewriting với LLM.
- **2025-12-29**: Adaptive RAG với confidence-based source weighting.
- **2026-01-02 (Morning)**: Fix dynamic confidence calculation:
  - Intent: Variable confidence (0.45-0.95) thay vì hard-coded 0.6
  - KB: Relevance filtering với threshold 0.5
  - KB: Penalty logic khi không có relevant docs (cap at 0.2)
  - Test suite: test_intent_route_fixes.py
- **2026-01-02 (Afternoon)**: Major improvements to confidence calculation:
  - **Intent Classification**: Chuyển sang LLM-first approach
    - Gọi LLM trước (mặc định USE_LLM_INTENT=true)
    - Rule-based chỉ làm fallback khi LLM lỗi hoặc USE_LLM_INTENT=false
    - LLM phân loại chính xác hơn với câu hỏi phức tạp/mơ hồ
  - **KB Confidence**: Sử dụng Cosine Similarity chuẩn
    - Tính cosine_sim = dot(query, doc) / (norm(query) * norm(doc))
    - Không còn dùng heuristic 1 / (1 + distance)
    - Fallback: tính từ embeddings nếu Chroma không trả về
    - Clamp similarity về [0, 1] cho consistency
    - Cải thiện: Confidence phản ánh đúng semantic similarity
- **2026-01-03**: 
  - **ArXiv Search Fix**: Tự động lọc ký tự đặc biệt (?, !, *) khỏi query để tránh 500 error
  - **Re-ranking**: Tích hợp cross-encoder (ms-marco-MiniLM-L-6-v2) vào graph pipeline
  - **Tavily Integration (FIXED)**: Tích hợp thực sự Tavily vào search_node
    - Search song song cả ArXiv và Tavily
    - Normalize kết quả về định dạng chung
    - Prioritize Tavily results có score cao (>0.7)
    - Log source distribution (ArXiv vs Tavily)
  - **Memory Integration (FIXED)**: Tích hợp ConversationMemory vào LLM prompt
    - Thêm {memory} placeholder vào DEFAULT_PROMPT
    - Pass memory_context từ state vào generate_answer()
    - Format memory dưới dạng "LỊCH SỬ HỘI THOẠI LIÊN QUAN"
    - LLM giờ có context của các câu hỏi trước đó liên quan
    - Cải thiện khả năng trả lời câu hỏi follow-up
    - **Optimization**: Inject thêm Last 1 turn (Recent History) vào context để đảm bảo tính liền mạch cho các câu hỏi ngắn/mơ hồ.
- **2026-01-04**:
  - **Memory Optimization**: Tăng recent history window từ n=1 lên n=5
    - Agent giờ nhớ 5 cặp hỏi-đáp gần nhất
    - Cải thiện đáng kể tính liền mạch trong hội thoại dài
  - **Evaluation Pipeline**: Setup Ragas framework
    - Tạo test dataset với 10 câu hỏi (definition, summary, comparison, etc.)
    - Implement 4 metrics: Faithfulness, Answer Relevancy, Context Precision, Context Recall
    - Script eval/evaluate.py tự động chạy và lưu kết quả
    - Documentation trong eval/README.md
    - **Results**: Faithfulness (0.84), Answer Relevancy (0.72), Context Recall (0.78), Context Precision (0.43)
  - **Error Handling & Robustness** (Completed):
    - Created `agent/utils.py` with retry utilities (`retry_with_backoff`, `safe_execute`)
    - **Search Error Handling**:
      - Added retry logic with exponential backoff to ArXiv API calls (max 3 retries)
      - Tavily search now has internal retry mechanism
      - Graceful degradation: if one source fails, continues with others
      - Comprehensive logging for debugging
    - **LLM Error Handling**:
      - All LLM backends (Ollama, Gemini, OpenRouter) now have retry logic
      - Exponential backoff on API failures
      - Clear error messages for troubleshooting
    - **ChromaDB Error Handling**:
      - Retry logic for connection issues
      - Fallback to empty results on failure
      - Prevents crashes when ChromaDB is unavailable

## Next Actions

### High Priority (Blocking issues resolved)
1. ✅ ~~Đăng ký API Key Tavily~~ (Done)
2. ✅ ~~Tạo file `ingest/tavily_search.py`~~ (Done)
3. ✅ ~~**Error Handling & Fallbacks**~~ (Done - 2026-01-04)
   - Retry logic with exponential backoff for all API calls
   - Graceful degradation when services fail
   - Comprehensive logging for debugging
   - Fallback mechanisms for ChromaDB, ArXiv, Tavily, LLM APIs

## Stage 3 Status: ✅ COMPLETE

All objectives for Stage 3 have been achieved:
- ✅ Web Search Integration (Tavily)
- ✅ Advanced Retrieval (Hybrid Search + Re-ranking)
- ✅ Query Transformation
- ✅ Evaluation Pipeline (Ragas)
- ✅ Error Handling & Robustness

**Next Phase**: Stage 4 - Optimization & Production Readiness - 2026-01-02)

### Medium Priority (Stage 3 completion)
5. ✅ ~~**Re-ranking Implementation**~~ (Done - 2026-01-03)
   - Add cross-encoder re-ranker (ms-marco-MiniLM-L-6-v2)
   - Re-rank top-20 results before sending to LLM

6. ✅ ~~**Evaluation Pipeline**~~ (Done - 2026-01-04)
   - Setup Ragas framework
   - Test set created (10 questions)
   - **Results**: Faithfulness (0.84), Recall (0.78), Precision (0.43)
   - *Note*: Precision tuning moved to Stage 4.

7. **Error Handling & Fallbacks**:
   - API timeout/failure handling for Tavily/Gemini/OpenRouter
   - Retry logic with exponential backoff
   - Fallback to cached results when APIs unavailable

### Stage 4 (Optimization & UI)
- **Precision Tuning**:
  - Tighten Re-ranking Threshold (>0.5).
  - Refine Hybrid Search Weights.
  - Dynamic Top-K.
- **UI Improvements**: Streamlit chat interface enhancements.
- **Deployment**: Dockerize application.

### Low Priority (Nice to have)
8. **Index more diverse papers**: Expand KB beyond RAG papers
9. **Streaming responses**: Add streaming for long answers
10. **Cost tracking**: Log API usage for Tavily/Gemini/OpenRouter
