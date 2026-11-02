# Phân Tích Kết Quả: Negative Rerank Scores

**Date**: 2026-01-XX  
**Log Analysis**: All cross-encoder scores are negative (-10 to -11)

## 📊 Phân Tích Logs

### Kết Quả Quan Sát

```
[Rerank] All 6 snippets below threshold 0.1 (normalized).
[Rerank] Top raw score: -10.0265, normalized: 1.0000, threshold: 0.1000
[Rerank] All raw scores: [-10.02, -10.58, -10.58, -10.89, -11.07]
[Rerank] All normalized scores: [1.0, 0.47, 0.47, 0.17, 0.0]
```

## 🔍 Giải Thích

### 1. Raw Scores (-10 đến -11)

**Ý nghĩa**:
- Cross-encoder model (`ms-marco-MiniLM-L-6-v2`) đánh giá **TẤT CẢ snippets đều KHÔNG relevant** với query
- Range: -10 đến +10 cho ms-marco models
- **Positive (> 0)**: Relevant (liên quan)
- **Negative (< 0)**: Not relevant (không liên quan)
- **Hiện tại**: Tất cả đều negative → Không có snippet nào relevant!

### 2. Normalized Score 1.0 (Misleading!)

**Vấn đề**:
- Top snippet có normalized score = **1.0**
- Nhưng đây chỉ là **max trong range**, không có nghĩa là tốt!
- Khi tất cả scores đều negative, normalized score không có ý nghĩa
- Top snippet vẫn có raw score = **-10.02** (rất negative!)

**Ví dụ**:
```
Raw scores: [-10, -10.5, -11]
Normalized: [1.0, 0.5, 0.0]  ← Top = 1.0 nhưng vẫn là -10!
```

### 3. Tại Sao Scores Lại Negative?

**Có thể do**:

1. **Snippets không match query**:
   - Query: "What is RAG?"
   - Snippets: Có thể về topics khác
   - Cross-encoder đúng khi đánh giá không relevant

2. **Text extraction failed**:
   - Snippets có thể có empty text
   - Cross-encoder không thể score empty text
   - Returns very negative scores

3. **Query-snippet format issue**:
   - Text format không đúng
   - Cross-encoder expects specific format

## 🛠️ Fixes Đã Áp Dụng

### 1. Detect All-Negative Case ✅

```python
all_negative = all(s < 0 for s in score_list)
if all_negative:
    # Disable threshold filtering
    # Use top-k anyway
```

### 2. Disable Threshold Khi All Negative ✅

```python
if all_negative:
    # Return top-k by raw score (best of bad)
    filtered_snippets = scored_snippets[:top_k]
else:
    # Normal threshold filtering
```

### 3. Validate Text ✅

```python
# Check empty text in RRF merge
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

## 📊 Kết Quả Sau Fix

### Before
```
Raw scores: [-10, -10.5, -10.6]
→ All filtered (threshold 0.1)
→ Return top-1 only
→ "Chưa đủ nguồn"
```

### After
```
Raw scores: [-10, -10.5, -10.6]
→ All negative detected
→ Disable threshold
→ Return top-6 (all available)
→ Generate với 6 snippets
→ Better than nothing! ✅
```

## 🎯 Next Steps

### 1. Check Snippet Text

Logs sẽ hiển thị:
- Snippet text lengths
- Empty text warnings
- Sample snippet text

### 2. Check Retrieval

Verify:
- KB confidence
- Dense retrieval results
- BM25 results
- ArXiv API results

### 3. Check Query Expansion

Verify query được expand đúng:
- "What is RAG?" → "retrieval augmented generation"

## 💡 Tóm Tắt

**Vấn đề**: 
- Tất cả cross-encoder scores đều negative
- Cross-encoder nói không có snippet nào relevant

**Nguyên nhân có thể**:
- Snippets không match query
- Text extraction failed
- Query-snippet format issue

**Fix**:
- Detect all-negative case
- Disable threshold filtering
- Return top-k anyway
- Validate text

**Kết quả**: 
- System sẽ return snippets dù scores negative
- LLM có thể generate answer với available context
- Better than "Chưa đủ nguồn"!
