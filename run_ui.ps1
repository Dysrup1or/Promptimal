# ============================================
# Catalyze 3.0 - UI Startup Script (PowerShell)
# ============================================

Write-Host ""
Write-Host "   ____      _        _                  " -ForegroundColor Cyan
Write-Host "  / ___|__ _| |_ __ _| |_   _ _______   " -ForegroundColor Cyan
Write-Host " | |   / _` | __/ _` | | | | |_  / _ \  " -ForegroundColor Cyan
Write-Host " | |__| (_| | || (_| | | |_| |/ /  __/  " -ForegroundColor Cyan
Write-Host "  \____\__,_|\__\__,_|_|\__, /___\___|  " -ForegroundColor Cyan
Write-Host "                        |___/           " -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting Catalyze - Prompt Transformation Engine..." -ForegroundColor Green
Write-Host ""

# Check if streamlit is installed
$streamlitCheck = python -c "import streamlit" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Streamlit not installed. Installing now..." -ForegroundColor Yellow
    pip install streamlit
    Write-Host ""
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "[WARNING] .env file not found!" -ForegroundColor Yellow
    Write-Host "Please create a .env file with your API keys:" -ForegroundColor Yellow
    Write-Host "  GROQ_API_KEY=your-key-here   # Primary for normal runs" -ForegroundColor Gray
    Write-Host "  DEEPSEEK_API_KEY=your-key-here # Fallback (optional but recommended)" -ForegroundColor Gray
    Write-Host "  GEMINI_API_KEY=your-key-here  # Required only for image upload" -ForegroundColor Gray
    Write-Host "  OPENAI_API_KEY=your-key-here  # Required only for voice transcription" -ForegroundColor Gray
    Write-Host ""
    Write-Host "You can enter keys in the UI sidebar as well." -ForegroundColor Gray
    Write-Host ""
}

# Launch Streamlit
Write-Host "Launching browser at http://localhost:8501" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Gray
Write-Host ""

python -m streamlit run app.py --server.headless=false --browser.gatherUsageStats=false
