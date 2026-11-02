# RAG Performance Analysis & Improvements

**Date**: 2026-01-XX  
**Issue**: Query "what is RAG in AI Field?" returns "Chưa đủ nguồn" despite data in ChromaDB

## 🔍 Root Cause Analysis

### 1. ChromaDB Data Check ✅

**Status**: ChromaDB has **110 documents** in collection

**Finding**: 
- Collection exists và has data
- Sample documents are present
- **Issue**: Embedding dimension mismatch detected (768 vs 384)

### 2. KB Confidence Computation Error ❌

**Error**: 
```
The truth value of an array with more than one element is ambiguous. Use a.any() or a.all()
```

**Location**: `agent/nodes/route.py` - `_compute_kb_confidence()`

**Root Cause**: Comparing numpy arrays directly in boolean context

**Line 90**: 
```python
if similarity >= RELEVANCE_THRESHOLD:  # This works
```

But the error suggests there's a comparison issue with numpy arrays elsewhere.

### 3. System Prompt Language ⚠️

**Current**: Vietnamese prompt
```python
"Bạn là trợ lý nghiên cứu. Sử dụng thông tin trong CONTEXT..."
```

**Impact**: 
- May affect LLM understanding for English queries
- English LLMs may perform better with English prompts
- Mixed language context can confuse models

### 4. Model Loading Strategy ⚠️

**Current Behavior**:
- **Embedding models**: Lazy load (first use)
- **CrossEncoder**: Lazy load (first use)  
- **LLM**: No preload, API call each time

**Issues**:
- First request has cold start delay
- No option to preload models at startup
- No warmup mechanism

## 🛠️ Fixes & Improvements

### Fix 1: KB Confidence Computation Error

**Problem**: Numpy array comparison in boolean context

**Solution**: Ensure all comparisons use scalar values

```python
# In agent/nodes/route.py line 90
if float(similarity) >= RELEVANCE_THRESHOLD:  # Explicit float conversion
    relevant_count += 1
```

### Fix 2: Embedding Dimension Mismatch

**Problem**: ChromaDB expects 768 but getting 384

**Solution**: 
1. Check current embed model dimension
2. Ensure consistency between ingestion và query
3. Add dimension validation

### Fix 3: System Prompt Optimization

**Recommendation**: Use English prompt for better LLM performance

**Benefits**:
- Better compatibility với English LLMs
- More consistent với research paper context
- Better citation handling

### Fix 4: Model Preloading

**Recommendation**: Add `PRELOAD_MODELS` env flag

**Implementation**:
- Preload embedding model at startup
- Preload CrossEncoder at startup
- Optional LLM warmup

## 📊 Performance Improvements

### Immediate Fixes

1. **Fix KB confidence error** → Restore routing logic
2. **Fix embedding dimension** → Ensure correct model
3. **Add error handling** → Better fallback behavior

### Medium-term Improvements

1. **English system prompt** → Better LLM responses
2. **Model preloading** → Reduce cold start
3. **Better logging** → Debug issues faster

### Long-term Optimizations

1. **Embedding cache** → Faster retrieval
2. **Query expansion** → Better matching
3. **Hybrid search tuning** → Better relevance

## 🎯 Action Items

- [ ] Fix KB confidence computation error
- [ ] Verify embedding model dimension
- [ ] Add model preloading flag
- [ ] Test English vs Vietnamese prompt
- [ ] Add better error messages
- [ ] Improve logging for debugging
