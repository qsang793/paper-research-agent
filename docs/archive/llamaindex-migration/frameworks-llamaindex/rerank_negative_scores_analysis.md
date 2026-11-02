# Rerank Negative Scores Analysis

**Date**: 2026-01-XX  
**Issue**: All cross-encoder scores are negative (-10 to -11), indicating no relevant snippets

## 📊 Log Analysis

### Observed Scores

```
[Rerank] All 6 snippets below threshold 0.1 (normalized).
[Rerank] Top raw score: -10.0265, normalized: 1.0000, threshold: 0.1000
[Rerank] All raw scores: [-10.02, -10.58, -10.58, -10.89, -11.07]
[Rerank] All normalized scores: [1.0, 0.47, 0.47, 0.17, 0.0]
```

### Interpretation

**Raw Scores (-10 to -11)**:
- **Meaning**: Cross-encoder model says **ALL snippets are NOT relevant** to query
- **Range**: -10 to +10 for ms-marco models
- **Positive (> 0)**: Relevant
- **Negative (< 0)**: Not relevant
- **Current**: All negative → Nothing relevant!

**Normalized Scores (0.0 to 1.0)**:
- **Top score: 1.0**: This is misleading! It's just the max in the range
- **Not meaningful**: When all scores negative, normalization doesn't help
- **Top snippet normalized = 1.0** doesn't mean it's good, just that it's the "best of bad"

## 🔍 Root Causes

### Possible Issues

1. **Snippets Don't Match Query**
   - Query: "What is RAG?"
   - Snippets: May be about different topics
   - Cross-encoder correctly identifies mismatch

2. **Empty/Missing Text**
   - Snippets may have empty `text` field
   - Cross-encoder can't score empty text
   - Returns very negative scores

3. **Text Extraction Problem**
   - Text not properly extracted from merged results
   - Missing text in snippets passed to rerank

4. **Query-Snippet Format Issue**
   - Query or snippet text may be malformed
   - Cross-encoder expects specific format

## 🛠️ Fixes Applied

### 1. Detect All-Negative Scores ✅

```python
all_negative = all(s < 0 for s in score_list)
if all_negative:
    logger.warning("ALL scores are NEGATIVE (not relevant)!")
    # Disable threshold filtering, use top-k anyway
```

### 2. Disable Threshold When All Negative ✅

```python
if all_negative:
    # Use top-k by raw score (best of bad)
    filtered_snippets = scored_snippets[:top_k]
else:
    # Normal threshold filtering
    ...
```

### 3. Check Empty Text ✅

```python
# In RRF merge
if not doc.get("text") or len(doc.get("text", "").strip()) == 0:
    logger.warning("Skipping document with empty text")
    continue
```

### 4. Better Fallback ✅

```python
# Always return top-k if available
# Better than returning nothing
filtered_snippets = scored_snippets[:top_k]
```

## 📊 Expected Behavior After Fix

### Before
```
Raw scores: [-10, -10.5, -10.6, -10.9, -11]
→ All filtered (threshold 0.1)
→ Return top-1 only
→ "Chưa đủ nguồn"
```

### After
```
Raw scores: [-10, -10.5, -10.6, -10.9, -11]
→ All negative detected
→ Disable threshold
→ Return top-6 (all available)
→ Generate với 6 snippets (best of bad)
→ Better than nothing!
```

## 🎯 Next Steps to Investigate

### 1. Check Snippet Text

Add logging to see actual snippet text:
```python
logger.debug(f"Snippet text: {text[:200]}...")
```

### 2. Check Query Expansion

Verify query is expanded correctly:
- "What is RAG?" → Should expand to "retrieval augmented generation"

### 3. Check Retrieval Quality

Verify retrieval is working:
- KB confidence
- Dense retrieval results
- BM25 results
- ArXiv API results

### 4. Check Text Extraction

Verify text is extracted correctly from:
- KB chunks
- ArXiv abstracts
- Merged results

## 💡 Recommendations

### Immediate
1. ✅ Disable threshold when all negative (done)
2. ✅ Check empty text (done)
3. ✅ Return top-k anyway (done)

### Short-term
4. Add snippet text logging
5. Verify query expansion
6. Check retrieval quality

### Long-term
7. Improve retrieval (better embeddings, better chunks)
8. Better query understanding
9. Consider different rerank model if scores consistently negative

## 📝 Summary

**Issue**: All cross-encoder scores negative → nothing relevant

**Root Cause**: Snippets don't match query, or text extraction failed

**Fix**: 
- Detect all-negative case
- Disable threshold filtering
- Return top-k anyway (better than nothing)
- Check for empty text

**Result**: System will return snippets even if scores are negative, allowing LLM to generate answer với available context.
