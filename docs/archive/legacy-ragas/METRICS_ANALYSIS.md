# Phân Tích Kết Quả Evaluation

## Kết quả hiện tại

```
Faithfulness:       0.854 ✓
Answer Relevancy:   0.685 ⚠
Context Precision:  0.400 ✗
Context Recall:     0.320 ✗
```

## Phân tích chi tiết

### 1. 🟢 Faithfulness: 0.854 (TốT)
**Ý nghĩa**: Câu trả lời có dựa trên context được retrieve hay không (không hallucinate)

**Đánh giá**: 
- ✅ **Điểm mạnh**: Hệ thống trả lời rất trung thực với context
- ✅ Ít hallucination (bịa đặt thông tin)
- ✅ LLM tuân thủ tốt instruction "chỉ trả lời dựa trên CONTEXT"

**Lý do tốt**:
- Prompt generation có instruction rõ ràng về grounding
- Citation validator hoạt động tốt
- LLM quality (OpenRouter GPT-4o) tốt

---

### 2. ⚠️ Answer Relevancy: 0.685 (TRUNG BÌNH)
**Ý nghĩa**: Câu trả lời có đúng trọng tâm câu hỏi không

**Đánh giá**:
- ⚠️ Một số câu trả lời lan man hoặc không tập trung vào câu hỏi
- ⚠️ Có thể trả lời đúng nhưng không đủ ngắn gọn

**Nguyên nhân có thể**:
1. **Intent classification chưa tốt**: Không hiểu đúng ý định người dùng
2. **Query không được refine**: Câu hỏi không được làm rõ trước khi retrieve
3. **Generation prompt chưa tối ưu**: Thiếu hướng dẫn về độ ngắn gọn, trọng tâm

**Cách cải thiện**:
```python
# 1. Cải thiện intent classification
- Review lại agent/nodes/intent.py
- Thêm examples cho từng intent type
- Test với các câu hỏi edge cases

# 2. Query refinement tốt hơn
- Implement query expansion cho câu hỏi phức tạp
- Add query rewriting cho câu hỏi mơ hồ

# 3. Prompt engineering
- Thêm instruction: "Answer concisely and directly"
- Thêm few-shot examples
```

---

### 3. 🔴 Context Precision: 0.400 (THẤP - ƯU TIÊN CAO)
**Ý nghĩa**: Trong các documents được retrieve, bao nhiêu % thực sự liên quan?

**Đánh giá**:
- ❌ **VẤN ĐỀ NGHIÊM TRỌNG**: 60% documents retrieved KHÔNG liên quan
- ❌ Retrieval đang "ném lưới" rộng nhưng không chính xác
- ❌ Gây nhiễu cho LLM khi generation

**Nguyên nhân**:
1. **Embedding model yếu**: `all-MiniLM-L6-v2` (6 layers) là model nhỏ
2. **Chunking không tối ưu**: Size, overlap có thể không phù hợp
3. **Thiếu reranking hiệu quả**: Reranker có thể chưa được config tốt
4. **top_k = 6 quá ít**: Không đủ để "chọn lọc" các docs tốt

**Cách cải thiện (Priority Order)**:

#### A. IMMEDIATE (Quick wins)
```bash
# 1. Tăng top_k và test reranker
python eval/evaluate.py --backend openrouter --top-k 15

# 2. Kiểm tra reranker threshold
# agent/nodes/rerank.py - adjust RERANK_THRESHOLD
```

#### B. SHORT TERM (1-2 days)
```python
# 1. Upgrade embedding model
# Thay đổi trong config
EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"  # 768 dim, better
# hoặc
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"  # For Vietnamese

# 2. Implement Hybrid Search
# Kết hợp BM25 (lexical) + Dense embeddings
# File: agent/retriever.py
def hybrid_search(query, top_k=10):
    # Dense retrieval
    dense_results = chroma_search(query, top_k=top_k*2)
    
    # BM25 retrieval
    bm25_results = bm25_search(query, top_k=top_k*2)
    
    # Fusion (RRF - Reciprocal Rank Fusion)
    combined = reciprocal_rank_fusion([dense_results, bm25_results])
    return combined[:top_k]

# 3. Query Expansion
def expand_query(original_query):
    # Sử dụng LLM để tạo variants
    variants = llm.generate(f"Generate 3 variations: {original_query}")
    return [original_query] + variants
```

#### C. MEDIUM TERM (1 week)
```python
# 1. Re-chunking với semantic splitting
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,  # Test 500, 1000, 1500
    chunk_overlap=200,  # 20% overlap
    separators=["\n\n", "\n", ". ", " "],  # Semantic boundaries
)

# 2. Add metadata filtering
# Trong ingest/index.py, thêm metadata:
metadata = {
    "arxiv_id": paper_id,
    "title": paper_title,
    "section": section_name,  # Introduction, Methods, Results, etc.
    "year": publish_year,
}

# 3. Fine-tune reranker
# Train cross-encoder trên domain-specific data (ArXiv papers)
```

---

### 4. 🔴 Context Recall: 0.320 (THẤP - ƯU TIÊN CAO)
**Ý nghĩa**: Documents retrieved có đủ thông tin để trả lời câu hỏi không?

**Đánh giá**:
- ❌ **VẤN ĐỀ NGHIÊM TRỌNG**: 68% thông tin cần thiết KHÔNG được retrieve
- ❌ Hệ thống "miss" nhiều documents quan trọng
- ❌ Ngay cả khi có paper đúng trong DB, vẫn không retrieve được

**Nguyên nhân**:
1. **top_k = 6 QUÁ THẤP**: Không đủ coverage
2. **Query không match với document content**: 
   - User hỏi bằng tiếng Việt
   - Documents là tiếng Anh
   - Embedding không handle tốt cross-lingual
3. **Chunking strategy**: Thông tin quan trọng bị "split" ra nhiều chunks
4. **Database chưa đủ**: Thiếu papers liên quan

**Cách cải thiện**:

#### A. IMMEDIATE
```bash
# 1. Tăng top_k
python eval/evaluate.py --backend openrouter --top-k 20

# 2. Test với multilingual embedding
EMBED_MODEL="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
```

#### B. SHORT TERM
```python
# 1. Multi-query retrieval
def multi_query_retrieve(query, top_k=6):
    # Tạo multiple queries
    queries = [
        query,  # Original
        translate_to_english(query),  # English version
        decompose_query(query),  # Sub-questions
    ]
    
    all_results = []
    for q in queries:
        results = retrieve(q, top_k=top_k)
        all_results.extend(results)
    
    # Deduplicate and merge
    return deduplicate(all_results)[:top_k]

# 2. Query decomposition cho câu hỏi phức tạp
# "So sánh A và B" -> ["Giải thích A", "Giải thích B", "Khác biệt A vs B"]

# 3. Parent Document Retrieval
# Khi retrieve chunk nhỏ, lấy luôn parent document hoặc adjacent chunks
def retrieve_with_context(query, top_k=6):
    chunks = retrieve(query, top_k=top_k)
    
    expanded_chunks = []
    for chunk in chunks:
        # Lấy thêm chunks trước và sau
        expanded_chunks.extend([
            get_chunk(chunk.id - 1),
            chunk,
            get_chunk(chunk.id + 1),
        ])
    
    return deduplicate(expanded_chunks)
```

#### C. MEDIUM TERM
```python
# 1. Index nhiều papers hơn
# Crawl thêm papers từ ArXiv về các topics quan trọng

# 2. Improve indexing với better chunking
# Sử dụng semantic chunking thay vì fixed-size

# 3. Add caching cho frequent queries
# Cache top_k results cho queries phổ biến
```

---

## Tổng kết & Action Plan

### 🔴 Priority 1 (URGENT - This Week)
**Problem**: Retrieval quality quá thấp (Precision 0.4, Recall 0.32)

**Actions**:
1. ✅ **Tăng top_k lên 15-20** (Quick test)
   ```bash
   python eval/evaluate.py --backend openrouter --top-k 15
   python eval/evaluate.py --backend openrouter --top-k 20
   ```

2. ✅ **Test multilingual embedding**
   ```bash
   # In config or .env
   EMBED_MODEL="sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
   ```

3. ✅ **Review reranker configuration**
   - Check `agent/nodes/rerank.py`
   - Test different thresholds (0.2, 0.3, 0.4)
   - Ensure reranker is actually being used

4. ✅ **Implement hybrid search** (BM25 + Dense)
   - Add BM25 retrieval alongside dense embeddings
   - Use Reciprocal Rank Fusion to combine results

**Expected Impact**: 
- Context Precision: 0.40 → 0.55-0.60
- Context Recall: 0.32 → 0.45-0.55

---

### 🟡 Priority 2 (Next Week)
**Problem**: Answer Relevancy can be improved (0.685)

**Actions**:
1. Improve intent classification
2. Add query refinement step
3. Better generation prompts
4. Implement query decomposition for complex questions

**Expected Impact**:
- Answer Relevancy: 0.685 → 0.75-0.80

---

### 🟢 Priority 3 (Ongoing)
**Problem**: Maintain faithfulness while improving other metrics

**Actions**:
1. Continue monitoring hallucination
2. Maintain strong citation validation
3. Regular testing with edge cases

---

## Testing Strategy

### Phase 1: Quick Experiments (Today)
```bash
# Test 1: Increase top_k
python eval/evaluate.py --backend openrouter --top-k 10
python eval/evaluate.py --backend openrouter --top-k 15
python eval/evaluate.py --backend openrouter --top-k 20

# Test 2: Different embedding model
# Change EMBED_MODEL in .env, then re-index
python -m ingest.index --input ./cache/clean --chroma ./chroma_v2

# Test 3: Check current reranker usage
# Add logging to agent/nodes/rerank.py to verify it's working
```

### Phase 2: Implementation (This Week)
1. Implement hybrid search (BM25 + Dense)
2. Add multi-query retrieval
3. Improve chunking strategy

### Phase 3: Fine-tuning (Next Week)
1. Fine-tune reranker on domain data
2. Optimize all hyperparameters
3. A/B testing different configurations

---

## Expected Final Scores (After All Improvements)

```
Faithfulness:       0.85 → 0.85 (maintain)
Answer Relevancy:   0.69 → 0.78 (+0.09)
Context Precision:  0.40 → 0.65 (+0.25)  ← Biggest improvement
Context Recall:     0.32 → 0.60 (+0.28)  ← Biggest improvement
```

**Target Overall Score**: 0.70+ average (currently 0.57)

---

## Key Insights

1. **Root cause**: Retrieval quality is the bottleneck
   - Low precision = too many irrelevant docs
   - Low recall = missing critical information
   
2. **Faithfulness is good**: Shows the system design is sound
   - Just need better inputs (retrieved context)
   
3. **Quick wins available**: 
   - Increase top_k (no code change)
   - Better embedding model (minimal change)
   - Enable hybrid search (already have reranker)

4. **Investment priority**: Focus on retrieval pipeline
   - 80% of improvements come from better retrieval
   - 20% from better generation/prompting
