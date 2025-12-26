# Chuuk Dictionary - Start Development Servers (PowerShell)
# This script starts both Flask backend and React frontend

Write-Host "🏝️  Starting Chuuk Dictionary Development Environment..." -ForegroundColor Cyan
Write-Host ""

# Check if in correct directory
if (-not (Test-Path "app.py")) {
    Write-Host "❌ Error: Must run from project root directory" -ForegroundColor Red
    exit 1
}

# Check if .venv exists
if (-not (Test-Path ".venv")) {
    Write-Host "⚠️  Virtual environment not found. Creating .venv..." -ForegroundColor Yellow
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "❌ Failed to create virtual environment" -ForegroundColor Red
        exit 1
    }
}

Write-Host "📦 Checking dependencies..." -ForegroundColor Blue

# Install Python dependencies
Write-Host "⚠️  Installing/updating Python dependencies..." -ForegroundColor Yellow
./.venv/bin/python -m pip install -r requirements.txt > $null 2>&1

# Check Node modules
if (-not (Test-Path "frontend/node_modules")) {
    Write-Host "⚠️  Installing Node dependencies..." -ForegroundColor Yellow
    Push-Location frontend
    npm install
    Pop-Location
}

Write-Host "✅ Dependencies ready" -ForegroundColor Green
Write-Host ""

# Create logs directory if it doesn't exist
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Start Flask backend
Write-Host "🐍 Starting Flask backend on http://localhost:5002" -ForegroundColor Blue

# Start Flask in background using .venv
$flaskJob = Start-Job -ScriptBlock {
    param($projectPath)
    Set-Location $projectPath
    & "$projectPath/.venv/bin/python" app.py 2>&1 | Out-File -FilePath "$projectPath/logs/flask.log"
} -ArgumentList (Get-Location).Path

Start-Sleep -Seconds 3

# Check if Flask started successfully
if ($flaskJob.State -ne "Running") {
    Write-Host "❌ Failed to start Flask backend" -ForegroundColor Red
    Write-Host "Check logs/flask.log for errors" -ForegroundColor Yellow
    Get-Content logs/flask.log
    exit 1
}

Write-Host "✅ Flask backend running" -ForegroundColor Green
Write-Host ""

# Start Vite frontend
Write-Host "⚛️  Starting React frontend on http://localhost:5173" -ForegroundColor Blue

$viteJob = Start-Job -ScriptBlock {
    param($projectPath)
    Set-Location "$projectPath/frontend"
    npm run dev 2>&1 | Out-File -FilePath "$projectPath/logs/vite.log"
} -ArgumentList (Get-Location).Path

Start-Sleep -Seconds 3

# Check if Vite started successfully
if ($viteJob.State -ne "Running") {
    Write-Host "❌ Failed to start React frontend" -ForegroundColor Red
    Write-Host "Check logs/vite.log for errors" -ForegroundColor Yellow
    Stop-Job $flaskJob
    Remove-Job $flaskJob
    exit 1
}

Write-Host "✅ React frontend running" -ForegroundColor Green
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🎉 Development servers are running!" -ForegroundColor Green
Write-Host ""
Write-Host "📱 Frontend:  " -NoNewline; Write-Host "http://localhost:5173" -ForegroundColor Blue
Write-Host "🔧 Backend:   " -NoNewline; Write-Host "http://localhost:5002" -ForegroundColor Blue
Write-Host "📝 Flask logs: logs/flask.log"
Write-Host "📝 Vite logs:  logs/vite.log"
Write-Host ""
Write-Host "Press Ctrl+C to stop both servers" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Wait for user interrupt
try {
    Write-Host "Monitoring servers... (Ctrl+C to stop)" -ForegroundColor Gray
    while ($true) {
        Start-Sleep -Seconds 5
        
        # Check if jobs are still running
        if ($flaskJob.State -ne "Running") {
            Write-Host "⚠️  Flask backend stopped unexpectedly" -ForegroundColor Yellow
            Get-Content logs/flask.log | Select-Object -Last 20
            break
        }
        
        if ($viteJob.State -ne "Running") {
            Write-Host "⚠️  React frontend stopped unexpectedly" -ForegroundColor Yellow
            Get-Content logs/vite.log | Select-Object -Last 20
            break
        }
    }
}
finally {
    Write-Host ""
    Write-Host "🛑 Shutting down servers..." -ForegroundColor Yellow
    
    # Stop both jobs
    Stop-Job $flaskJob -ErrorAction SilentlyContinue
    Stop-Job $viteJob -ErrorAction SilentlyContinue
    
    Remove-Job $flaskJob -ErrorAction SilentlyContinue
    Remove-Job $viteJob -ErrorAction SilentlyContinue
    
    Write-Host "✅ Servers stopped" -ForegroundColor Green
}
