# LlamaIndex Installation Guide

## Vấn đề với LlamaIndex 0.11.15

LlamaIndex 0.11.15 là version cũ (2024), và một số integration packages có thể:
- Không tồn tại với tên đó
- Có tên khác
- Được tích hợp sẵn trong core package

## Giải pháp

### Option 1: Cài đặt từng package (Recommended)

```bash
# Core LlamaIndex (đã có trong requirements.txt)
pip install llama-index==0.11.15

# ChromaDB integration (có sẵn)
pip install llama-index-vector-stores-chroma

# Các packages khác có thể không tồn tại cho 0.11.15
# Thử cài và bỏ qua nếu lỗi
pip install llama-index-embeddings-sentence-transformers || echo "Package not available"
pip install llama-index-llms-ollama || echo "Package not available"
pip install llama-index-llms-openai || echo "Package not available"
```

### Option 2: Upgrade LlamaIndex (Nếu muốn dùng packages mới nhất)

```bash
# Upgrade lên version mới hơn (có thể có breaking changes)
pip install --upgrade llama-index

# Sau đó cài các integration packages
pip install llama-index-vector-stores-chroma
pip install llama-index-embeddings-sentence-transformers
pip install llama-index-llms-ollama
pip install llama-index-llms-openai
```

### Option 3: Sử dụng Extras (Nếu có)

Một số version của LlamaIndex hỗ trợ extras:

```bash
pip install llama-index[vector-stores-chroma]
```

## Kiểm tra Installation

```python
from agent.frameworks.llamaindex.utils import (
    check_llamaindex_installed,
    get_llamaindex_version
)

if check_llamaindex_installed():
    print(f"✅ LlamaIndex installed: {get_llamaindex_version()}")
else:
    print("❌ LlamaIndex not installed")
```

## Test Integration

```python
# Test vector store integration
try:
    from agent.frameworks.llamaindex import LlamaIndexVectorStoreAdapter
    print("✅ Vector store adapter available")
except ImportError as e:
    print(f"❌ Vector store adapter not available: {e}")
```

## Lưu ý

1. **LlamaIndex 0.11.15**: Một số packages có thể không tồn tại
2. **Code đã handle gracefully**: Code sẽ skip nếu packages không có
3. **Optional**: Các packages này là optional - code hiện tại vẫn hoạt động

## Troubleshooting

### Lỗi: "No matching distribution found"

**Nguyên nhân**: Package không tồn tại cho version này

**Giải pháp**: 
- Bỏ qua package đó (code sẽ hoạt động bình thường)
- Hoặc upgrade LlamaIndex

### Lỗi: "Requires-Python >=3.8.1,<3.12"

**Nguyên nhân**: Package yêu cầu Python < 3.12

**Giải pháp**:
- Upgrade LlamaIndex lên version mới hơn (hỗ trợ Python 3.12)
- Hoặc dùng Python 3.11

## Recommendation

**Cho Phase 1**: Chỉ cần `llama-index` và `llama-index-vector-stores-chroma` là đủ.

Các packages khác sẽ cần cho Phase 2-3, nhưng có thể cài sau hoặc upgrade LlamaIndex.
