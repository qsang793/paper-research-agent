# Log Analysis: Rerank Threshold & HuggingFace Warnings

**Date**: 2026-01-XX  
**Issue**: "All snippets below threshold 0.3" và HuggingFace tokenizers warnings

## 📊 Log Analysis

### Issue 1: Rerank Threshold Filtering

**Log Message**:
```
All snippets below threshold 0.3. Returning top-1 anyway.
```

**Meaning**:
- Rerank model scored all snippets với score < 0.3
- Default threshold là 0.3 (RERANK_THRESHOLD)
- Tất cả snippets bị filter out
- Fallback: return top-1 snippet anyway (even if < 0.3)

**Root Cause**:
1. **Rerank scores quá thấp**: Cross-encoder model cho thấy snippets không relevant
2. **Threshold quá cao**: 0.3 có thể quá strict cho một số queries
3. **Snippet quality**: Snippets từ retrieval có thể không match query well

**Impact**:
- Chỉ có 1 snippet được pass qua rerank
- Generate node nhận ít snippets → có thể dẫn đến "Chưa đủ nguồn"
- Answer quality giảm vì thiếu context

### Issue 2: HuggingFace Tokenizers Warning

**Log Message**:
```
huggingface/tokenizers: The current process just got forked, after parallelism has already been used. 
Disabling parallelism to avoid deadlocks...
```

**Meaning**:
- HuggingFace tokenizers đã enable parallelism trong main process
- Process bị fork (uvicorn với --reload)
- Tokenizers disable parallelism để tránh deadlock

**Root Cause**:
- Uvicorn với `--reload` sử dụng multiprocessing
- Models (embedding, rerank) được load trước khi fork
- Tokenizers parallelism conflict với forking

**Impact**:
- ⚠️ Warning only, không phải error
- Performance có thể giảm nhẹ (no parallelism)
- Không ảnh hưởng functionality

## 🔍 Why This Happens

### Rerank Threshold Flow

```
1. Retrieve snippets (Dense + BM25) → 6 snippets
2. Rerank với cross-encoder → scores: [0.15, 0.18, 0.22, 0.25, 0.28, 0.19]
3. Filter với threshold 0.3 → All filtered out!
4. Fallback: Return top-1 (score: 0.28)
5. Generate với 1 snippet → May not be enough
```

### Possible Reasons for Low Scores

1. **Query-Snippet Mismatch**:
   - Query: "What is RAG?"
   - Snippets: May contain partial info, not comprehensive
   - Cross-encoder thấy không đủ relevant

2. **Threshold Too High**:
   - 0.3 có thể OK cho high-quality snippets
   - Nhưng nếu snippets từ retrieval không perfect, scores sẽ thấp
   - Cần balance giữa precision và recall

3. **Model Calibration**:
   - `ms-marco-MiniLM-L-6-v2` trained on MS MARCO
   - Scores có thể khác với expected range
   - Cần tune threshold based on actual scores

## 🛠️ Solutions

### Solution 1: Lower Rerank Threshold

**Option A: Lower Default Threshold**
```bash
# In .env
RERANK_THRESHOLD=0.1  # Lower threshold, keep more snippets
```

**Option B: Disable Threshold Filtering**
```bash
RERANK_THRESHOLD=0.0  # No filtering, only dynamic cutoff
```

**Option C: Adaptive Threshold**
- Use percentile-based threshold
- E.g., keep top 50% of scores

### Solution 2: Fix HuggingFace Warning

**Option A: Set Environment Variable**
```bash
# In .env or before starting uvicorn
TOKENIZERS_PARALLELISM=false
```

**Option B: Set in Code**
```python
# In api/main.py or agent initialization
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
```

**Option C: Disable Uvicorn Reload in Production**
```bash
# Production (no reload)
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Development (with reload, accept warning)
uvicorn api.main:app --reload
```

### Solution 3: Improve Retrieval Quality

**Better Retrieval → Better Rerank Scores**:
1. Tune embedding model
2. Improve chunking strategy
3. Better query understanding
4. Hybrid retrieval (Dense + BM25) - already done ✅

## 📊 Recommended Actions

### Immediate Fix (Quick)

1. **Lower Rerank Threshold**:
   ```bash
   RERANK_THRESHOLD=0.1
   ```

2. **Fix HuggingFace Warning**:
   ```bash
   TOKENIZERS_PARALLELISM=false
   ```

### Long-term Fix (Better)

1. **Monitor Rerank Scores**:
   - Log actual scores
   - Analyze distribution
   - Tune threshold based on data

2. **Adaptive Thresholding**:
   - Use percentile-based threshold
   - Or use top-k instead of absolute threshold

3. **Improve Retrieval**:
   - Better embedding model
   - Better chunking
   - Query expansion

## 🎯 Expected Results After Fix

### Before
```
[Rerank] All snippets below threshold 0.3 → Return top-1
[Generate] Snippets count: 1
[Generate] ⚠️ Chưa đủ nguồn (if 1 snippet not enough)
```

### After (Lower Threshold)
```
[Rerank] Re-ranking: 6 -> 4 (threshold 0.1) -> 4 (dynamic)
[Generate] Snippets count: 4
[Generate] Answer generated: 450 characters ✅
```

## 📝 Summary

**Issue 1: Rerank Threshold**
- **Problem**: Threshold 0.3 quá strict, filter hết snippets
- **Solution**: Lower threshold to 0.1 or 0.0
- **Impact**: More snippets → Better answers

**Issue 2: HuggingFace Warning**
- **Problem**: Tokenizers parallelism conflict với forking
- **Solution**: Set `TOKENIZERS_PARALLELISM=false`
- **Impact**: No warning, slight performance impact

**Next Steps**:
1. Lower `RERANK_THRESHOLD` to 0.1
2. Set `TOKENIZERS_PARALLELISM=false`
3. Test query "What is RAG?" again
4. Monitor rerank scores để tune further
