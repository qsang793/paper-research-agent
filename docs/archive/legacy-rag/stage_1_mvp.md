# 🧠 AI Research Agent — MVP (Chặng 1)

## 🎯 Mục tiêu (Definition of Done)

Khi người dùng nhập câu hỏi, hệ thống thực hiện chuỗi:

> search → crawl → parse → chunk → embed → upsert → retrieve → generate

Yêu cầu tối thiểu:
- Trả lời có trích dẫn nguồn (URL + tiêu đề), tối thiểu 2 citation hợp lệ (HTTP 200).
- UI Streamlit đơn giản, hiển thị log từng bước + thời gian từng stage.
- Có bộ sanity tests (5–10 câu hỏi) với tiêu chí pass rõ ràng.

Ngưỡng chất lượng & hiệu năng:
- Latency P95:
  - search+crawl+parse (lần đầu): ≤ 15s cho 3–5 URL (máy cá nhân).
  - retrieve+generate (đã có index): ≤ 4–6s.
- Tỷ lệ lỗi crawl < 10% (timeout, 4xx/5xx).
- Mỗi câu trả lời:
  - ≥ 2 citation hợp lệ (HTTP 200).
  - Nếu thiếu context: phải trả “chưa đủ nguồn” và gợi ý tìm tiếp.

---

## 🏗️ 1. Khởi tạo dự án

### 📁 Cấu trúc thư mục

```text
ai-research-agent/
├── app/
│   ├── main.py            # FastAPI (optional ở chặng 1)
│   └── ui.py              # Streamlit app
├── agent/
│   ├── pipeline.py        # Orchestrate MVP steps
│   ├── retriever.py       # retrieve + re-rank (simple)
│   └── generator.py       # call LLM (Ollama)
├── ingest/
│   ├── search.py          # web search (provider stub)
│   ├── crawl.py           # fetch HTML/PDF
│   ├── parse.py           # Unstructured.io
│   └── index.py           # chunk + embed + upsert
├── stores/
│   ├── vector_store.py    # Chroma
│   └── schemas.py         # metadata schemas
├── config/
│   └── settings.py        # load env
├── tests/
│   └── sanity_mvp.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## 📦 2. Thiết lập môi trường

### ⚙️ requirements.txt (gợi ý)

```txt
llama-index==0.11.15
chromadb==0.5.5
sentence-transformers==2.7.0
unstructured==0.15.7
requests==2.32.3
beautifulsoup4==4.12.3
tavily-python==0.3.5
python-dotenv==1.0.1
streamlit==1.38.0
ollama==0.3.3
rank-bm25==0.2.2
```

### 🌍 .env.example

```env
# Models & Runtime
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2
LLM_MODEL=llama3
OLLAMA_BASE=http://localhost:11434

# Vector store
CHROMA_PATH=./chroma

# Search
SEARCH_PROVIDER=tavily
TAVILY_API_KEY=xxx
SEARCH_MAX_RESULTS=5
CACHE_TTL_HOURS=48

# Ingestion
CHUNK_SIZE=1024
CHUNK_OVERLAP=100
INDEX_BATCH_SIZE=64
MAX_CONTENT_MB=2
CRAWL_TIMEOUT_SEC=15
CRAWL_MAX_RETRIES=2
CRAWL_BACKOFF_BASE_SEC=2

# Retrieval
TOP_K=6
USE_BM25=true
RRF_K=60

# Misc
LOG_LEVEL=INFO
```

---

## 🤖 3. Thiết lập LLM & Embedding

- Cài **Ollama** và pull model:

  ```bash
  ollama pull llama3
  ```

* Dùng embedding offline: `all-MiniLM-L6-v2` (nhanh, phổ biến).
* Viết adapter nhỏ để dễ thay đổi sang `nomic-embed-text` sau này.

---

## 🌐 4. Search → Crawl → Parse (Ingestion)

### 🔍 Search

* Dùng **Tavily/Serper** (hoặc stub URL tĩnh để test).

### 🕸️ Crawl

* `requests` + `timeout` + loại trùng theo `normalized_url`.
* Timeout/Retry/Backoff: `CRAWL_TIMEOUT_SEC` (mặc định 15s), retry tối đa `CRAWL_MAX_RETRIES`=2 với exponential backoff `CRAWL_BACKOFF_BASE_SEC`=2.
* Bỏ qua tài liệu > `MAX_CONTENT_MB` và chỉ nhận `text/html`, `application/pdf` (PDF có thể tắt ở chặng 1).

### 🧩 Parse

* Dùng `unstructured.partition` → trả text + metadata.

**Chuẩn hóa metadata:**

```text
source_url, title, retrieved_at, published_at, content_hash, language, doc_type
```

### 🔧 Chuẩn hoá URL & Hashing (dedup)

- `normalized_url`: lower-case host, bỏ fragment, sort query, strip trailing slashes.
- `content_hash`: tránh re-index và làm id chuỗi.

Đề xuất:
- `content_hash = sha256(normalized_url + canonical_title + cleaned_text[:4096])`

```python
# ingest/utils_normalize.py
import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

def normalize_url(url: str) -> str:
    p = urlparse(url.strip())
    host = p.hostname.lower() if p.hostname else ""
    path = p.path.rstrip("/")
    query = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
    normalized = urlunparse((p.scheme.lower() or "http", host, path, p.params, query, ""))  # drop fragment
    return normalized

def compute_content_hash(normalized_url: str, title: str, cleaned_text: str) -> str:
    h = hashlib.sha256()
    h.update(normalized_url.encode("utf-8"))
    h.update((title or "").strip().encode("utf-8"))
    h.update((cleaned_text or "")[:4096].encode("utf-8"))
    return h.hexdigest()
```

### 💾 Caching

- Lưu kết quả search vào `./cache/search_results.json` (kèm `retrieved_at`).
- Lưu raw HTML/PDF: `./cache/raw/{sha1_url}.bin`.
- Lưu parsed/clean: `./cache/clean/{content_hash}.json`.
- TTL cache: `CACHE_TTL_HOURS` (mặc định 48h).
- Khi chạy lại, ưu tiên dùng cache hợp lệ để giảm latency.

### ⚠️ Bẫy thường gặp

* Trang JS động: ưu tiên nguồn tĩnh (blog, arXiv abs).
* PDF nặng: giới hạn kích thước hoặc bỏ qua.

---

## 📚 5. Chunk → Embed → Upsert (Indexing)

* Chunk rule: `size=1024`, `overlap=100`, tách theo heading.
* Embedding theo batch (64–128).
* Upsert vào **Chroma**:

  ```python
  id = content_hash
  metadata = {...}
  ```

**Tiêu chí chất lượng:**

* Mỗi document sinh 10–200 chunk.
* Mỗi chủ đề ≥ 2 nguồn (tránh “single-source bias”).

---

## 🔎 6. Retrieve → Generate (Answering)

### 🧮 Retrieve (Hybrid tối giản)

* Dense: cosine top-k (k=TOP_K) từ Chroma.
* Keyword: BM25 (rank-bm25) trên tập chunk text (cache sẵn token hoá đơn giản).
* Hợp nhất bằng Reciprocal Rank Fusion (RRF) với tham số `RRF_K` (mặc định 60).
* Ưu tiên `published_at` mới hơn (nếu có) bằng cộng điểm nhỏ (time boost).

```python
# agent/retriever.py (RRF hợp nhất)
def rrf_merge(ranked_lists, k=60):
    scores = {}
    for lst in ranked_lists:
        for rank, item in enumerate(lst, start=1):
            scores[item.id] = scores.get(item.id, 0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### 🧠 Generate (Ollama)

* Truyền context + yêu cầu citation.

**Định dạng citation:**

```text
[Title](URL)
```

### 🧾 Prompt mẫu

```text
Bạn là trợ lý nghiên cứu. Chỉ sử dụng thông tin trong CONTEXT để trả lời ngắn gọn, có trích dẫn.
- Bắt buộc trích dẫn theo [Title](URL) ngay tại câu chứa thông tin đó.
- Nếu CONTEXT không đủ, hãy nói: "Chưa đủ nguồn" và gợi ý tìm thêm từ khóa.
- Không suy đoán ngoài CONTEXT.

CONTEXT:
{{top_k_snippets_with_titles_and_urls}}

CÂU HỎI: {{user_query}}
```

### ✅ Citation Validation

- Kiểm tra HTTP 200 cho mỗi URL đã trích dẫn (HEAD → fallback GET).
- Nếu URL chết, hiển thị cảnh báo trong UI và loại khỏi tính điểm “citation hợp lệ”.

```python
# agent/citation_validator.py
import requests

def is_alive(url: str, timeout=5) -> bool:
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        if 200 <= r.status_code < 400:
            return True
    except requests.RequestException:
        pass
    try:
        r = requests.get(url, allow_redirects=True, timeout=timeout)
        return 200 <= r.status_code < 400
    except requests.RequestException:
        return False
```

---

## 🖥️ 7. UI tối thiểu (Streamlit)

**Input:**

* Câu hỏi của người dùng.

**Nút:** `"Fetch & Index"`

* Cho phép nhập 1–3 từ khóa → chạy `search → crawl → parse → index`.

**Output:**

* Câu trả lời + citation (clickable).
* Log bảng: số URL, số chunk, thời gian từng bước.

---

## 🧾 8. Logging & Cấu hình

* **Logging:** `logging.INFO` cho từng stage: search, crawl, parse, index, retrieve, generate (start/end + duration ms + số lượng).
* **UI metrics tối thiểu:** `total_time_ms`, `search_count`, `crawled_ok/failed`, `chunks_indexed`, `top_k`, `model`, `citations_ok/total`.
* **Timing:** đo thời gian từng bước → hiển thị UI.
* **Config:** đọc từ `.env`, có default an toàn.

---

## ✅ 9. Sanity Tests

**File:** `tests/sanity_mvp.py`

Bộ câu hỏi mẫu: 5–10 câu (có thể kèm dataset offline 5–10 URL tĩnh trong `tests/fixtures/urls.txt`).

Tiêu chí pass:

* Mỗi câu: ≥ 2 citation hợp lệ (HTTP 200).
* Nếu không có context phù hợp: trả "Chưa đủ nguồn" (không bịa).
* P95 thời gian trả lời (retrieve+generate) ≤ 6s với index nhỏ (≤ 2k chunk).
* Tỷ lệ crawl fail ≤ 10% trên bộ URL mẫu.

---

## ⚡ 10. Rủi ro & Giải pháp

| Rủi ro                 | Giải pháp                                         |
| ---------------------- | ------------------------------------------------- |
| Crawl fail             | Fallback URL đã biết                              |
| Parse PDF lỗi          | Bỏ qua PDF ở chặng 1                              |
| Embedding chậm         | Giảm `CHUNK_SIZE`, tăng batch size                |
| Llama3 trả lời lan man | Thêm ràng buộc "chỉ dùng thông tin trong CONTEXT" |

---

## 🧩 11. Checkpoint & Demo Script

Chạy pipeline từng bước:

```bash
# 1) Chuẩn bị môi trường
ollama pull llama3

# 2) Ingestion lần đầu
python -m ingest.search --q "RAG 2025 trends" --out ./cache/search_results.json
python -m ingest.crawl --from ./cache/search_results.json --out ./cache/raw
python -m ingest.parse --input ./cache/raw --out ./cache/clean
python -m ingest.index --input ./cache/clean --chroma ./chroma

# 3) Chạy UI
streamlit run app/ui.py
```

**Theo dõi:**

* Số URL
* Số chunk
* Thời gian từng bước
* Retrieval hit-rate (thủ công)

---

## 🗂️ Ưu tiên triển khai

1. ✅ Embedding + Chroma hoạt động (index → retrieve).
2. ✅ Ollama generate với context (chưa cần search).
3. ✅ Parse (unstructured) 1 URL tĩnh → index → answer.
4. ✅ Bật search → crawl nhiều URL → index lại → answer có citation.
5. ✅ Tích hợp Streamlit UI + logging.

---

## ✅ Checklist “sẵn sàng MVP”

- Pin dependencies + .env mẫu hoàn chỉnh.
- Normalized URL + content_hash + cache hoạt động.
- Timeout/retry/backoff khi crawl; size/type filter.
- Index/retrieve chạy; BM25 + RRF optional bật/tắt.
- Prompt có guardrails; citation validator chạy.
- UI hiển thị metrics tối thiểu.
- Sanity tests đạt ngưỡng đã đặt.

## 📍 Kết luận

> **MVP hoàn thiện** khi:
>
> * Có thể nhập câu hỏi → trả lời có citation.
> * Có thể index nguồn mới qua UI.
> * Có log, test và chạy mượt trên dữ liệu nhỏ (5–10 URL).

---

Bạn có muốn mình giúp tạo thêm **README badge + sơ đồ Mermaid kiến trúc tổng quan** ở đầu file (để hiển thị đẹp trên GitHub)?  
Ví dụ: badges cho Python, Streamlit, Ollama, Chroma và một sơ đồ tổng quan agent pipeline.
