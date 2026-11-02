"""
Evaluation pipeline for AI Research Agent using Ragas.

Metrics:
- Faithfulness: Answer is grounded in retrieved context
- Answer Relevance: Answer addresses the question
- Context Precision: Retrieved context is relevant to question
- Context Recall: Retrieved context covers all aspects needed
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

from agent.pipeline import run_agent_graph
from datasets import Dataset

try:
    from ragas import evaluate
    # Use legacy metrics module (compatible with evaluate() function)
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    )
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from langchain_huggingface import HuggingFaceEmbeddings as LangchainHFEmbeddings

except ImportError as e:
    print(f"Ragas or LangChain dependencies not installed: {e}")
    print("Install with: pip install ragas langchain-openai langchain-huggingface")
    sys.exit(1)


def get_llm_wrapper(backend: str = "openrouter"):
    """
    Create LLM wrapper for Ragas evaluation using LangChain.
    
    Args:
        backend: LLM backend (openrouter, gemini, or ollama)
    
    Returns:
        LangchainLLMWrapper instance (compatible with legacy metrics)
    """
    if backend == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        model_name = os.getenv("OPENROUTER_MODEL", "xiaomi/mimo-v2-flash:free")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        
        langchain_llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            model=model_name,
            max_tokens=4096,
            temperature=0,
        )
        return LangchainLLMWrapper(langchain_llm)
    
    elif backend == "gemini":
        raise NotImplementedError("Gemini backend for Ragas not yet implemented")
    
    else:
        # Default to OpenRouter
        return get_llm_wrapper("openrouter")


def get_embeddings_wrapper(model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    """
    Create embeddings wrapper for Ragas evaluation using LangChain.
    
    Args:
        model_name: HuggingFace model name
    
    Returns:
        LangchainEmbeddingsWrapper instance
    """
    langchain_embeddings = LangchainHFEmbeddings(model_name=model_name)
    return LangchainEmbeddingsWrapper(langchain_embeddings)


def load_test_dataset(path: str = "eval/dataset.json") -> List[Dict]:
    """Load test questions from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_evaluation(
    dataset_path: str = "eval/dataset.json",
    chroma_path: str = "./chroma",
    embed_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    llm_backend: str = "gemini",
    clean_dir: str = "./cache/clean",
    top_k: int = 6,
) -> Dict:
    """
    Run evaluation pipeline on test dataset.
    
    Args:
        dataset_path: Path to test dataset JSON
        chroma_path: ChromaDB path
        embed_model: Embedding model
        llm_backend: LLM backend (ollama/gemini/openrouter)
        clean_dir: Clean cache directory
        top_k: Number of snippets to retrieve
    
    Returns:
        Dictionary with evaluation results
    """
    # Load test questions
    test_data = load_test_dataset(dataset_path)
    
    # Run agent on each question
    questions = []
    answers = []
    contexts_list = []
    ground_truths = []
    
    print(f"Running evaluation on {len(test_data)} questions...")
    print(f"LLM Backend: {llm_backend}")
    print("-" * 60)
    
    for i, item in enumerate(test_data, 1):
        question = item["question"]
        print(f"\n[{i}/{len(test_data)}] {question}")
        
        try:
            result = run_agent_graph(
                query=question,
                chroma_path=chroma_path,
                embed_model=embed_model,
                llm_backend=llm_backend,
                clean_dir=clean_dir,
                top_k=top_k,
            )
            
            answer = result.get("answer", "")
            snippets = result.get("merged_snippets", []) or []
            
            # Extract context from snippets
            contexts = [s.get("text", "") for s in snippets if s.get("text")]
            
            questions.append(question)
            answers.append(answer)
            contexts_list.append(contexts)
            
            # Ground truth: Use expected topics as pseudo-ground-truth
            # In real scenario, you'd have human-annotated answers
            ground_truth = " ".join(item.get("expected_topics", []))
            ground_truths.append(ground_truth)
            
            print(f"✓ Answer: {answer[:100]}...")
            print(f"✓ Contexts: {len(contexts)} snippets")
            
        except Exception as exc:
            print(f"✗ Error: {exc}")
            # Add empty values to maintain alignment
            questions.append(question)
            answers.append("")
            contexts_list.append([])
            ground_truths.append("")
    
    # Prepare dataset for Ragas
    print("\n" + "=" * 60)
    print("Preparing Ragas evaluation dataset...")
    
    eval_dataset = Dataset.from_dict({
        "question": questions,
        "answer": answers,
        "contexts": contexts_list,
        "ground_truth": ground_truths,
    })
    
    # Run Ragas evaluation
    print("Running Ragas metrics...")
    print("Metrics: Faithfulness, Answer Relevancy, Context Precision, Context Recall")
    print("-" * 60)
    
    # Initialize LLM and embeddings wrappers
    print(f"Initializing Ragas LLM and embeddings wrappers for: {llm_backend}")
    try:
        llm_wrapper = get_llm_wrapper(llm_backend)
        embeddings_wrapper = get_embeddings_wrapper(embed_model)
    except Exception as exc:
        print(f"✗ Failed to initialize LLM/Embeddings: {exc}")
        return {}
    
    # Use legacy pre-instantiated metric objects
    # These are singletons already configured
    metrics = [
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
    ]
    
    try:
        result = evaluate(
            eval_dataset,
            metrics=metrics,
            llm=llm_wrapper,
            embeddings=embeddings_wrapper,
        )
        
        # Helper function to extract metric value
        def get_metric_value(metric_result):
            """Extract scalar value from metric result (handles both float and list)."""
            if isinstance(metric_result, list):
                # If list, compute mean
                import numpy as np
                return float(np.mean(metric_result))
            return float(metric_result)
        
        print("\n" + "=" * 60)
        print("EVALUATION RESULTS")
        print("=" * 60)
        
        faithfulness_val = get_metric_value(result['faithfulness'])
        answer_relevancy_val = get_metric_value(result['answer_relevancy'])
        context_precision_val = get_metric_value(result['context_precision'])
        context_recall_val = get_metric_value(result['context_recall'])
        
        print(f"Faithfulness:       {faithfulness_val:.3f}")
        print(f"Answer Relevancy:   {answer_relevancy_val:.3f}")
        print(f"Context Precision:  {context_precision_val:.3f}")
        print(f"Context Recall:     {context_recall_val:.3f}")
        print("=" * 60)
        
        # Save results
        results_path = "eval/results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metrics": {
                        "faithfulness": faithfulness_val,
                        "answer_relevancy": answer_relevancy_val,
                        "context_precision": context_precision_val,
                        "context_recall": context_recall_val,
                    },
                    "config": {
                        "llm_backend": llm_backend,
                        "embed_model": embed_model,
                        "top_k": top_k,
                        "num_questions": len(test_data),
                    },
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        
        print(f"\nResults saved to: {results_path}")
        
        # Return extracted metric values (result object cannot be directly converted to dict)
        return {
            "faithfulness": faithfulness_val,
            "answer_relevancy": answer_relevancy_val,
            "context_precision": context_precision_val,
            "context_recall": context_recall_val,
        }
        
    except Exception as exc:
        print(f"\n✗ Ragas evaluation failed: {exc}")
        import traceback
        traceback.print_exc()
        return {}


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Evaluate AI Research Agent")
    parser.add_argument("--dataset", default="eval/dataset.json", help="Test dataset path")
    parser.add_argument("--chroma", default="./chroma", help="ChromaDB path")
    parser.add_argument("--embed-model", default="sentence-transformers/paraphrase-multilingual-mpnet-base-v2")
    parser.add_argument("--backend", default="gemini", choices=["ollama", "gemini", "openrouter"])
    parser.add_argument("--clean-dir", default="./cache/clean")
    parser.add_argument("--top-k", type=int, default=6)
    
    args = parser.parse_args()
    
    run_evaluation(
        dataset_path=args.dataset,
        chroma_path=args.chroma,
        embed_model=args.embed_model,
        llm_backend=args.backend,
        clean_dir=args.clean_dir,
        top_k=args.top_k,
    )
