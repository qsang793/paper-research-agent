#!/bin/bash
# Script to run performance tests with virtual environment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔍 Looking for virtual environment..."

# Try different common locations
if [ -d ".venv" ]; then
    VENV_PATH=".venv"
elif [ -d "venv" ]; then
    VENV_PATH="venv"
elif [ -d "../.venv" ]; then
    VENV_PATH="../.venv"
elif [ -d "../venv" ]; then
    VENV_PATH="../venv"
else
    echo "❌ Virtual environment not found!"
    echo "Please create one with: python3 -m venv .venv"
    exit 1
fi

echo "✅ Found virtual environment: $VENV_PATH"
echo "📦 Activating virtual environment..."

source "$VENV_PATH/bin/activate"

echo "✅ Virtual environment activated"
echo "🐍 Python: $(which python)"
echo "📋 Python version: $(python --version)"
echo ""

# Check if required packages are installed
echo "🔍 Checking dependencies..."
python -c "import sentence_transformers; import chromadb; import rank_bm25" 2>/dev/null || {
    echo "❌ Missing dependencies. Installing..."
    pip install -q sentence-transformers chromadb rank-bm25 requests
}

echo ""
echo "🚀 Running performance tests..."
echo "============================================================"
echo ""

python tests/test_performance.py

echo ""
echo "✅ Performance tests completed!"
