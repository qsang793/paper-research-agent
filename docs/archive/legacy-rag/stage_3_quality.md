# 🧠 AI Research Agent — Stage 3: Quality & Robustness

## 🎯 Mục tiêu (Definition of Done)

Chuyển trọng tâm từ "chạy được" (Stage 2) sang "chạy tốt" và "đáng tin cậy".
Hệ thống phải xử lý được các câu hỏi khó, tìm kiếm thông tin chính xác từ Internet (không chỉ ArXiv), và tự đánh giá chất lượng câu trả lời.

**Tiêu chí thành công:**
- **Search Quality**: Tích hợp Web Search (Tavily) để trả lời các câu hỏi ngoài phạm vi ArXiv.
- **Retrieval Accuracy**: Cải thiện độ chính xác tìm kiếm bằng Hybrid Search (Vector + Keyword) và Re-ranking.
- **Evaluation**: Có hệ thống chấm điểm tự động (Ragas/TruLens) cho Faithfulness và Answer Relevance.
- **Robustness**: Xử lý lỗi duyên dáng (graceful degradation) khi API lỗi hoặc không tìm thấy thông tin.

---

## 🏗️ 1. Nâng cấp Search & Ingestion

### 🌐 Tích hợp Web Search (Tavily API)
*   **Vấn đề hiện tại**: ArXiv quá hẹp, search keyword cứng nhắc.
*   **Giải pháp**: Thêm tool `web_search` dùng Tavily API.
*   **Chiến lược**:
    *   Nếu Intent = `fresh` hoặc `mixed`: Gọi song song ArXiv + Tavily.
    *   Tavily trả về nội dung đã clean -> đưa vào context ngay (hoặc index nhanh vào RAM).

### 🔄 Query Transformation (Rewrite)
*   **Vấn đề**: Người dùng hỏi câu dài/phức tạp -> Search engine không hiểu.
*   **Giải pháp**: Dùng LLM viết lại câu hỏi trước khi search.
    *   *Input*: "Tại sao search chán thế này?"
    *   *Rewrite*: "Nguyên nhân RAG search kém hiệu quả và cách khắc phục"

---

## 🔎 2. Advanced Retrieval (RAG nâng cao)

### 🧲 Hybrid Search
*   Kết hợp **Dense Retrieval** (ChromaDB cosine similarity) và **Keyword Search** (BM25).
*   **Lý do**: Vector giỏi tìm ý nghĩa bao quát, BM25 giỏi tìm từ khóa chính xác (tên riêng, thuật ngữ).
*   **Thuật toán**: Reciprocal Rank Fusion (RRF) để trộn 2 danh sách kết quả.

### 🥇 Re-ranking (Tùy chọn nhưng khuyến khích)
*   Dùng Cross-Encoder (như `bge-reranker` hoặc `ms-marco-MiniLM`) để chấm điểm lại top-k kết quả từ bước trên.
*   Lọc bỏ các đoạn văn bản không liên quan trước khi gửi cho LLM -> Tăng độ chính xác, giảm hallucination.

---

## ⚖️ 3. Evaluation & Observability

### 📊 Tích hợp Ragas / TruLens
*   Xây dựng pipeline đánh giá tự động.
*   **Metrics quan trọng**:
    *   **Faithfulness**: Câu trả lời có dựa trên context không? (Chống bịa đặt).
    *   **Answer Relevance**: Câu trả lời có đúng trọng tâm câu hỏi không?
    *   **Context Precision**: Context tìm được có chứa thông tin cần thiết không?

### 📝 Logging & Tracing
*   Ghi log chi tiết từng bước trong LangGraph (Input, Output, Latency).
*   Lưu lại các câu hỏi "failed" (điểm eval thấp) để phân tích.

---

## 🚀 4. Production Readiness (Chuẩn bị cho Stage 4)

*   **LLM Serving**: Lên kế hoạch chuyển từ Ollama sang **vLLM** (nếu self-host) hoặc Gemini Flash (nếu dùng API) để chịu tải tốt hơn.
*   **Vector DB**: Cân nhắc chuyển sang Qdrant (Docker) nếu dữ liệu lớn.

---

## 📅 Lộ trình triển khai (2 tuần)

### Tuần 1: Search & Retrieval
1.  Tích hợp **Tavily API** vào node `search`.
2.  Thêm bước **Query Rewrite** vào node `search`.
3.  Cập nhật `retriever.py` để chạy **Hybrid Search** (đã có code nền, cần tinh chỉnh).

### Tuần 2: Eval & Refine
1.  Cài đặt **Ragas/TruLens**.
2.  Viết script đánh giá trên bộ test set (10-20 câu hỏi).
3.  Tinh chỉnh prompt và tham số (top_k, chunk_size) dựa trên kết quả eval.

---

## 📦 Dependencies mới (Dự kiến)

```txt
tavily-python
ragas
# hoặc trulens-eval
sentence-transformers (update mới nhất)
```
