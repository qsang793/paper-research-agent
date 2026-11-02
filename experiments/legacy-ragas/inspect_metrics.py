try:
    import ragas.metrics.collections
    print("ragas.metrics.collections dir:", dir(ragas.metrics.collections))
    
    # Check if we can import Class names from there
    try:
        from ragas.metrics.collections import Faithfulness
        print("Faithfulness import successful from collections. Type:", type(Faithfulness))
    except ImportError as e:
        print("Faithfulness import failed from collections:", e)
        
    try:
        from ragas.metrics import Faithfulness
        print("Faithfulness import successful from metrics (deprecated). Type:", type(Faithfulness))
    except ImportError:
        pass

except ImportError as e:
    print("ragas.metrics.collections import failed:", e)
