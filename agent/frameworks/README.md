# Framework Integrations (Optional)

This directory contains optional integrations with RAG frameworks like LlamaIndex and Haystack.

## Philosophy

**Current implementation is already optimized and production-ready.** These framework integrations are:
- ✅ **Optional**: Not required for core functionality
- ✅ **Incremental**: Use for specific features only
- ✅ **Non-breaking**: Don't affect existing code

## When to Use

### Use Current Implementation (Recommended)
- ✅ Core RAG pipeline
- ✅ Custom routing logic
- ✅ Hybrid retrieval (Dense + BM25 + RRF)
- ✅ Adaptive RAG

### Use Frameworks For
- 📄 Document loading/ingestion (LlamaIndex)
- 📊 Monitoring/observability (Haystack)
- 🔍 Specific retrieval strategies
- 📈 Future enhancements

## Available Integrations

### LlamaIndex (Planned)
- Document loaders
- Query engines (optional)
- Vector store adapters

### Haystack (Planned)
- Monitoring components
- Pipeline components (optional)
- Document stores

## Migration Path

If you want to migrate to a framework:

1. **Evaluate**: See `docs/framework_evaluation.md`
2. **Plan**: Identify which components to migrate
3. **Implement**: Use wrappers in this directory
4. **Test**: Ensure no regression
5. **Deploy**: Gradual rollout

## Current Status

- ✅ Framework evaluation completed
- ⏳ Optional wrappers (to be implemented if needed)
- ✅ Current implementation is recommended

---

**Note**: The current LangGraph-based implementation is well-optimized and production-ready. Framework integration is optional and should only be considered for specific use cases.
