@echo off
REM Deployment Verification Script for Trend Intelligence Platform (Windows)
REM Usage: verify_deployment.bat <BACKEND_URL> <API_KEY>

setlocal EnableDelayedExpansion

if "%~2"=="" (
    echo Usage: %0 ^<BACKEND_URL^> ^<API_KEY^>
    echo Example: %0 https://trend-reports-api.onrender.com your_api_key
    exit /b 1
)

set BACKEND_URL=%~1
set API_KEY=%~2

echo ================================================================
echo   Trend Intelligence Platform - Deployment Verification
echo ================================================================
echo.

REM Test 1: Health Check
echo [1/6] Testing Health Endpoint...
curl -s -o nul -w "HTTP Status: %%{http_code}" "%BACKEND_URL%/health"
echo.
curl -s "%BACKEND_URL%/health"
echo.
echo.

REM Test 2: Simple Search
echo [2/6] Testing Simple Search...
curl -s -o nul -w "HTTP Status: %%{http_code}" ^
    -X POST "%BACKEND_URL%/search" ^
    -H "Content-Type: application/json" ^
    -H "Authorization: Bearer %API_KEY%" ^
    -d "{\"query\": \"AI trends\", \"top_k\": 3}"
echo.
echo.

REM Test 3: Advanced Search
echo [3/6] Testing Advanced Search...
curl -s -o nul -w "HTTP Status: %%{http_code}" ^
    -X POST "%BACKEND_URL%/search/advanced" ^
    -H "Content-Type: application/json" ^
    -H "Authorization: Bearer %API_KEY%" ^
    -d "{\"query\": \"AI marketing\", \"query_type\": \"multi_dimensional\", \"dimensions\": [\"AI\", \"personalization\"], \"top_k\": 3}"
echo.
echo.

REM Test 4: Synthesis
echo [4/6] Testing Synthesis Endpoint...
curl -s -o nul -w "HTTP Status: %%{http_code}" ^
    -X POST "%BACKEND_URL%/search/synthesized" ^
    -H "Content-Type: application/json" ^
    -H "Authorization: Bearer %API_KEY%" ^
    -d "{\"query\": \"customer experience\", \"top_k\": 10}"
echo.
echo.

REM Test 5: Structured Report
echo [5/6] Testing Structured Report Endpoint...
curl -s -o nul -w "HTTP Status: %%{http_code}" ^
    -X POST "%BACKEND_URL%/search/structured" ^
    -H "Content-Type: application/json" ^
    -H "Authorization: Bearer %API_KEY%" ^
    -d "{\"query\": \"Gen Z shopping\", \"top_k\": 10}"
echo.
echo.

REM Test 6: Categories
echo [6/6] Testing Categories Endpoint...
curl -s -o nul -w "HTTP Status: %%{http_code}" "%BACKEND_URL%/categories"
echo.
curl -s "%BACKEND_URL%/categories"
echo.
echo.

echo ================================================================
echo   Verification Complete
echo ================================================================
echo.
echo Next Steps:
echo   1. Check all endpoints returned HTTP 200
echo   2. Health check should show 6109 documents
echo   3. Test frontend interface
echo   4. Configure Custom GPT (optional)
echo.

endlocal
