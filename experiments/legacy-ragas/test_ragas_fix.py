"""Test Ragas metrics initialization."""
import os
from dotenv import load_dotenv
load_dotenv()

from ragas import evaluate
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
)
from ragas.llms import llm_factory
from openai import OpenAI
from datasets import Dataset

# Create LLM wrapper
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

llm = llm_factory(
    model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o"),
    client=client,
    max_tokens=4096
)

# Create simple test dataset
test_data = {
    "question": ["What is RAG?"],
    "answer": ["RAG stands for Retrieval-Augmented Generation."],
    "contexts": [["RAG is a technique that combines retrieval and generation."]],
    "ground_truth": ["RAG is Retrieval-Augmented Generation"]
}

dataset = Dataset.from_dict(test_data)

# Initialize metrics WITHOUT llm/embeddings parameters
metrics = [
    Faithfulness(),
    AnswerRelevancy(),
    ContextPrecision(),
    ContextRecall(),
]

print("Testing Ragas evaluation...")
print(f"Metrics: {[m.name for m in metrics]}")

try:
    result = evaluate(
        dataset,
        metrics=metrics,
        llm=llm,
        # No embeddings parameter - let Ragas handle it
    )
    print("\n✓ Evaluation successful!")
    print(f"Results: {result}")
except Exception as e:
    print(f"\n✗ Evaluation failed: {e}")
    import traceback
    traceback.print_exc()
