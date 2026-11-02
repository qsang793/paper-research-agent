# RAG Performance Improvements Plan

**Date**: 2026-01-XX  
**Issue**: "Chưa đủ nguồn" cho câu hỏi đơn giản "What is RAG?"

## 🔍 Root Cause Analysis

### Current Issues

1. **Rerank Threshold Too High**
   - Default: 0.3 (even though env.example says 0.1)
   - All snippets filtered out → only top-1 returned
   - Not enough context for generation

2. **KB Confidence Computation**
   - May be too strict
   - Low confidence → wrong routing decisions

3. **Query Understanding**
   - Simple queries may not expand well
   - Missing synonyms/related terms

4. **Retrieval Quality**
   - Dense retrieval may miss relevant docs
   - BM25 may not catch all variations
   - Need better hybrid strategy

## 🛠️ Improvement Strategies

### 1. Lower Rerank Threshold (Immediate)

**Current**: 0.3 (default)  
**Recommended**: 0.0-0.1

**Why**:
- Cross-encoder scores can be lower than expected
- Better to keep more snippets and let LLM filter
- LLM context window can handle more snippets

### 2. Improve Query Expansion

**Current**: Basic expansion (remove question words, add years)  
**Improvements**:
- Add synonyms (RAG → retrieval augmented generation)
- Add related terms
- Expand abbreviations more comprehensively

### 3. Better KB Confidence Thresholds

**Current**:
- KB_CONFIDENCE_THRESHOLD=0.7 (high)
- KB_RELEVANCE_THRESHOLD=0.5 (medium)

**Recommended**:
- Lower KB_CONFIDENCE_THRESHOLD to 0.5-0.6
- Lower KB_RELEVANCE_THRESHOLD to 0.3-0.4
- More lenient routing decisions

### 4. Increase Retrieval Diversity

**Current**: top_k=6  
**Improvements**:
- Retrieve more candidates (top_k * 2)
- Better RRF merging
- Ensure diversity in results

### 5. Query Rewriting (Optional)

**Add LLM-based query rewriting**:
- Rewrite "What is RAG?" → "Explain retrieval augmented generation, RAG architecture, how RAG works"
- Better query understanding
- More comprehensive retrieval

### 6. Fallback Strategy

**If retrieval fails**:
- Don't return "Chưa đủ nguồn" immediately
- Try with lower thresholds
- Use ArXiv API as primary source
- Generate with available context

## 📊 Implementation Priority

### Priority 1: Quick Wins (Immediate)
1. ✅ Lower default rerank threshold to 0.1
2. ✅ Lower KB confidence thresholds
3. ✅ Improve query expansion

### Priority 2: Medium-term
4. Increase retrieval diversity
5. Better fallback strategies
6. Improve logging for debugging

### Priority 3: Long-term
7. Query rewriting with LLM
8. Semantic chunking
9. Advanced reranking strategies
