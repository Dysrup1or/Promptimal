@echo off
REM ============================================
REM Catalyze 3.0 - UI Startup Script (Windows)
REM ============================================

echo.
echo    ____      _        _                  
echo   / ___^|__ _^| ^|_ __ _^| ^|_   _ _______   
echo  ^| ^|   / _` ^| __/ _` ^| ^| ^| ^| ^|_  / _ \  
echo  ^| ^|__^| (_^| ^| ^|^| (_^| ^| ^| ^|_^| ^|/ /  __/  
echo   \____\__,_^|\__\__,_^|_^|\__, /___\___|  
echo                         ^|___/           
echo.
echo Starting Catalyze - Prompt Transformation Engine...
echo.

REM Check if streamlit is installed
python -c "import streamlit" 2>NUL
if errorlevel 1 (
    echo [WARNING] Streamlit not installed. Installing now...
    pip install streamlit
    echo.
)

REM Check if .env exists
if not exist ".env" (
    echo [WARNING] .env file not found!
    echo Please create a .env file with your API keys:
    echo   GEMINI_API_KEY=your-key-here
    echo   DEEPSEEK_API_KEY=your-key-here
    echo.
    echo You can enter keys in the UI sidebar as well.
    echo.
)

REM Launch Streamlit
echo Launching browser at http://localhost:8501
echo Press Ctrl+C to stop the server.
echo.

python -m streamlit run app.py --server.headless=false --browser.gatherUsageStats=false
