@echo off
REM Trend Reports API - Windows Startup Script

echo ============================================================
echo Starting Trend Reports API
echo ============================================================
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if ChromaDB exists
if not exist "chroma_data" (
    echo.
    echo ERROR: ChromaDB not found!
    echo Please run process_pdfs.py first to create the database.
    echo.
    pause
    exit /b 1
)

REM Count documents
echo Checking ChromaDB...
python -c "import chromadb; c = chromadb.PersistentClient('./chroma_data'); print(f'Documents in database: {c.get_collection(\"trend_reports\").count()}')"

echo.
echo Starting FastAPI server...
echo API will be available at: http://localhost:8000
echo API docs at: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
