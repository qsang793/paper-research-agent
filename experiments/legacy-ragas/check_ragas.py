try:
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    print("Imported from ragas.metrics:", type(faithfulness))
except ImportError as e:
    print("Import from ragas.metrics failed:", e)

try:
    from ragas.metrics.collections import faithfulness as f2
    print("Imported from ragas.metrics.collections:", type(f2))
except ImportError as e:
    print("Import from ragas.metrics.collections failed:", e)

import ragas
print("Ragas version:", getattr(ragas, "__version__", "unknown"))
