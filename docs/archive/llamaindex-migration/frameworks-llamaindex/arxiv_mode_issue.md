# ArXiv Mode Issue Analysis

**Date**: 2026-01-XX  
**Issue**: ArXiv API results bị ignore khi KB có >= 3 snippets, dù KB snippets có thể low quality

## 🔍 Problem Analysis

### Current Flow (ArXiv Mode)

```
1. search_node runs
   → Calls ArXiv API
   → Populates state["search_results"] với ArXiv papers
   ✅ ArXiv API được gọi

2. retrieve_node checks KB
   → Gets KB snippets từ ChromaDB
   → Counts unique KB documents (kb_count)

3. Decision Logic:
   if kb_count >= MIN_KB_THRESHOLD (3):
       ✅ Use KB only
       ❌ IGNORE search_results (ArXiv API results!)
   else:
       ✅ Include search_results
```

### The Problem

**Scenario**: Query "What is RAG?"

1. **ArXiv API** returns 5 high-quality papers về RAG ✅
2. **KB (ChromaDB)** có 4 snippets về RAG, nhưng:
   - Snippets có thể là chunks nhỏ, không comprehensive
   - Quality có thể không tốt bằng full ArXiv abstracts
   - Rerank scores thấp (< 0.3) vì snippets không match query tốt

3. **Decision**: `kb_count = 4 >= 3` → Use KB only
4. **Result**: ArXiv API results bị ignore! ❌
5. **Rerank**: KB snippets có scores thấp → all filtered
6. **Generate**: Chỉ có 1 snippet (fallback) → "Chưa đủ nguồn"

### Why Rerank Scores Are Low

**Not because ArXiv không có papers về RAG!**

**Real reasons**:
1. **KB snippets là chunks nhỏ**: 
   - ChromaDB stores document chunks (1024 chars)
   - ArXiv abstracts là full context
   - Chunks có thể không contain enough context

2. **Query-Snippet Mismatch**:
   - Query: "What is RAG?" (general, comprehensive)
   - KB chunks: May contain specific details, not overview
   - Cross-encoder thấy không đủ relevant

3. **KB Quality**:
   - Chunks có thể từ papers cũ
   - Hoặc không được chunked optimally
   - Missing important context

## 🛠️ Solutions

### Solution 1: Use KB Confidence Instead of Count

**Current**:
```python
if kb_count >= MIN_KB_THRESHOLD:  # Count-based
    use KB only
```

**Better**:
```python
if kb_confidence >= 0.5:  # Quality-based
    use KB + ArXiv (weighted by confidence)
else:
    use ArXiv primarily
```

### Solution 2: Always Include ArXiv in ArXiv Mode

**Current**:
```python
if kb_count >= MIN_KB_THRESHOLD:
    merged = _rrf_merge(dense, bm25, [], ...)  # No search_results!
```

**Better**:
```python
# Always include ArXiv results in ArXiv mode
# Weight by KB confidence
kb_weight = min(kb_confidence, 0.7)  # Cap at 0.7
merged = _rrf_merge(
    dense, 
    bm25, 
    search_results,  # Always include!
    kb_confidence=kb_weight
)
```

### Solution 3: Hybrid Approach (Recommended)

**Logic**:
- If KB confidence high (>= 0.6): Use KB primarily, ArXiv as supplement
- If KB confidence medium (0.3-0.6): Use both equally
- If KB confidence low (< 0.3): Use ArXiv primarily, KB as supplement

**Implementation**:
```python
if search_source == "arxiv":
    if kb_confidence >= 0.6:
        # High KB confidence: KB primary, ArXiv supplement
        kb_weight = 0.7
        merged = _rrf_merge(dense, bm25, search_results, kb_confidence=kb_weight)
    elif kb_confidence >= 0.3:
        # Medium: Equal weight
        merged = _rrf_merge(dense, bm25, search_results, kb_confidence=0.5)
    else:
        # Low: ArXiv primary
        merged = _rrf_merge(dense, bm25, search_results, kb_confidence=0.3)
```

## 📊 Expected Results After Fix

### Before (Current)
```
[Retrieve] KB count: 4 >= 3 → Use KB only
[Retrieve] ArXiv API results: 5 papers → IGNORED ❌
[Rerank] KB snippets scores: [0.15, 0.18, 0.22, 0.25] → All < 0.3
[Rerank] Return top-1 only
[Generate] 1 snippet → "Chưa đủ nguồn"
```

### After (Fixed)
```
[Retrieve] KB confidence: 0.4 → Medium, use both
[Retrieve] KB snippets: 4
[Retrieve] ArXiv API results: 5 papers → INCLUDED ✅
[Retrieve] Merged: 6 snippets (KB + ArXiv)
[Rerank] Scores: [0.65, 0.72, 0.68, 0.55, 0.61, 0.58] → All > 0.1
[Rerank] Return 6 snippets
[Generate] 6 snippets → Comprehensive answer ✅
```

## 🎯 Recommended Fix

**Change in `agent/nodes/retrieve.py`**:

Replace count-based logic với confidence-based logic:

```python
# ARXIV mode: KB first, use ArXiv API results based on KB confidence
if search_source == "arxiv":
    logger.info(f"[Retrieve Node] ARXIV mode: KB count={kb_count}, KB confidence={kb_confidence:.4f}")
    
    # Always include ArXiv results, weight by KB confidence
    if kb_confidence >= 0.6:
        # High KB confidence: KB primary (70%), ArXiv supplement (30%)
        kb_weight = 0.7
        logger.info("[Retrieve Node] ARXIV: High KB confidence, KB primary")
    elif kb_confidence >= 0.3:
        # Medium: Equal weight
        kb_weight = 0.5
        logger.info("[Retrieve Node] ARXIV: Medium KB confidence, equal weight")
    else:
        # Low: ArXiv primary (70%), KB supplement (30%)
        kb_weight = 0.3
        logger.info("[Retrieve Node] ARXIV: Low KB confidence, ArXiv primary")
    
    merged = _rrf_merge(
        dense_results, 
        bm25_results, 
        search_results,  # Always include ArXiv API results!
        k=top_k,
        kb_confidence=kb_weight,
        route_type="both"
    )
```

## 📝 Summary

**Root Cause**:
- ArXiv mode uses **count-based** logic (kb_count >= 3)
- Ignores ArXiv API results khi KB có >= 3 snippets
- KB snippets có thể low quality → rerank scores thấp

**Solution**:
- Use **confidence-based** logic instead
- Always include ArXiv API results
- Weight by KB confidence

**Result**:
- ArXiv API results luôn được sử dụng
- Better answer quality
- No more "Chưa đủ nguồn" với valid queries
