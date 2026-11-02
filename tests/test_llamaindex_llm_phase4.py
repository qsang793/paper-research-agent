"""
Phase 4: Test LlamaIndex LLM Integration.

Tests:
1. LlamaIndexLLMWrapper basic functionality
2. Streaming support
3. Compare với current generate_answer
4. Performance benchmarking
"""

import pytest
import os
from typing import Dict, List

# Check if LlamaIndex LLM is available
try:
    from agent.frameworks.llamaindex import LlamaIndexLLMWrapper, generate_node_llamaindex
    from agent.frameworks.llamaindex.llm import LLAMAINDEX_LLM_AVAILABLE
    LLAMAINDEX_LLM_AVAILABLE_TEST = LLAMAINDEX_LLM_AVAILABLE
except ImportError:
    LLAMAINDEX_LLM_AVAILABLE_TEST = False

from agent.nodes.generate import generate_node
from agent.state import AgentState
from agent.generator import generate_answer


@pytest.mark.skipif(not LLAMAINDEX_LLM_AVAILABLE_TEST, reason="LlamaIndex LLM not installed")
def test_llamaindex_llm_wrapper_basic():
    """Test basic LlamaIndexLLMWrapper functionality."""
    # Only test OpenRouter (other backends need additional packages)
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")
    
    # Create LLM wrapper
    llm = LlamaIndexLLMWrapper(
        backend="openrouter",
        temperature=0.2
    )
    
    # Test completion
    response = llm.complete("Hello, how are you?")
    assert isinstance(response, str)
    assert len(response) > 0
    print(f"✅ LLM completion returned {len(response)} characters")


@pytest.mark.skipif(not LLAMAINDEX_LLM_AVAILABLE_TEST, reason="LlamaIndex LLM not installed")
@pytest.mark.asyncio
async def test_llamaindex_llm_streaming():
    """Test LlamaIndex LLM streaming."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")
    
    # Create LLM wrapper
    llm = LlamaIndexLLMWrapper(
        backend="openrouter",
        temperature=0.2
    )
    
    # Test streaming
    tokens = []
    async for token in llm.stream("Say hello in one sentence."):
        tokens.append(token)
    
    assert len(tokens) > 0
    full_text = "".join(tokens)
    assert len(full_text) > 0
    print(f"✅ LLM streaming returned {len(tokens)} tokens, {len(full_text)} characters")


@pytest.mark.skipif(not LLAMAINDEX_LLM_AVAILABLE_TEST, reason="LlamaIndex LLM not installed")
@pytest.mark.asyncio
async def test_generate_node_llamaindex_basic():
    """Test generate_node_llamaindex với basic state."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")
    
    # Create test state with snippets
    snippets = [
        {
            "text": "Machine learning is a subset of artificial intelligence.",
            "metadata": {
                "title": "ML Introduction",
                "source_url": "https://example.com/ml"
            }
        }
    ]
    
    state: AgentState = {
        "query": "What is machine learning?",
        "merged_snippets": snippets,
        "memory_context": "",
        "llm_backend": "openrouter",
        "temperature": 0.2
    }
    
    # Run generate_node_llamaindex
    result_state = await generate_node_llamaindex(state)
    
    # Check results
    assert "answer" in result_state
    answer = result_state["answer"]
    assert isinstance(answer, str)
    assert len(answer) > 0
    print(f"✅ generate_node_llamaindex returned answer: {len(answer)} characters")


@pytest.mark.skipif(not LLAMAINDEX_LLM_AVAILABLE_TEST, reason="LlamaIndex LLM not installed")
@pytest.mark.asyncio
async def test_compare_with_current_generate():
    """So sánh generate_node_llamaindex với generate_node hiện tại."""
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")
    
    # Create test state
    snippets = [
        {
            "text": "Deep learning uses neural networks with multiple layers.",
            "metadata": {
                "title": "Deep Learning",
                "source_url": "https://example.com/dl"
            }
        }
    ]
    
    state: AgentState = {
        "query": "What is deep learning?",
        "merged_snippets": snippets,
        "memory_context": "",
        "llm_backend": "openrouter",
        "temperature": 0.2
    }
    
    # Run both generators
    llamaindex_state = await generate_node_llamaindex(state.copy())
    current_state = generate_node(state.copy())
    
    # Compare results
    llamaindex_answer = llamaindex_state.get("answer", "")
    current_answer = current_state.get("answer", "")
    
    print(f"✅ LlamaIndex: {len(llamaindex_answer)} characters")
    print(f"✅ Current: {len(current_answer)} characters")
    
    # Both should return answers
    assert len(llamaindex_answer) > 0, "LlamaIndex should return answer"
    assert len(current_answer) > 0, "Current should return answer"
    
    # Answers should be similar in length (within 50% difference)
    length_ratio = len(llamaindex_answer) / len(current_answer) if len(current_answer) > 0 else 0
    assert 0.5 <= length_ratio <= 2.0, f"Answer lengths should be similar (ratio: {length_ratio:.2f})"


@pytest.mark.skipif(not LLAMAINDEX_LLM_AVAILABLE_TEST, reason="LlamaIndex LLM not installed")
@pytest.mark.asyncio
async def test_performance_benchmark():
    """Benchmark performance của generate_node_llamaindex."""
    import time
    
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")
    
    snippets = [
        {
            "text": "Transformer architecture revolutionized NLP.",
            "metadata": {
                "title": "Transformers",
                "source_url": "https://example.com/transformer"
            }
        }
    ]
    
    state: AgentState = {
        "query": "What is transformer architecture?",
        "merged_snippets": snippets,
        "memory_context": "",
        "llm_backend": "openrouter",
        "temperature": 0.2
    }
    
    # Benchmark LlamaIndex (single run due to API costs)
    start = time.time()
    await generate_node_llamaindex(state.copy())
    llamaindex_time = time.time() - start
    
    # Benchmark current (single run)
    start = time.time()
    generate_node(state.copy())
    current_time = time.time() - start
    
    print(f"✅ LlamaIndex: {llamaindex_time*1000:.2f}ms")
    print(f"✅ Current: {current_time*1000:.2f}ms")
    
    ratio = llamaindex_time / current_time if current_time > 0 else 0
    print(f"✅ Performance ratio: {ratio:.2f}x")
    
    # Performance should be within 2x (acceptable for Phase 4)
    assert ratio < 2.0, f"LlamaIndex should not be more than 2x slower (ratio: {ratio:.2f})"


def test_module_imports():
    """Test that modules can be imported."""
    try:
        from agent.frameworks.llamaindex import LlamaIndexLLMWrapper, generate_node_llamaindex
        assert True
    except ImportError as e:
        pytest.skip(f"LlamaIndex LLM modules not available: {e}")
