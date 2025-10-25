#!/bin/bash
# Trend Reports API - Unix/Mac Startup Script

set -e

echo "============================================================"
echo "Starting Trend Reports API"
echo "============================================================"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if ChromaDB exists
if [ ! -d "chroma_data" ]; then
    echo ""
    echo "ERROR: ChromaDB not found!"
    echo "Please run 'python process_pdfs.py' first to create the database."
    echo ""
    exit 1
fi

# Count documents
echo "Checking ChromaDB..."
python -c "import chromadb; c = chromadb.PersistentClient('./chroma_data'); print(f'Documents in database: {c.get_collection(\"trend_reports\").count()}')"

echo ""
echo "Starting FastAPI server..."
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
