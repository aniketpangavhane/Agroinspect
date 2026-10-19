# PowerShell Script to Run Crop Recommendation System

Write-Host "========================================" -ForegroundColor Green
Write-Host "Crop Recommendation System" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Starting server..." -ForegroundColor Cyan
Write-Host ""

Set-Location "d:\scrap\Crop-Recommendation-System-Using-Machine-Learning-main (1) - Copy\Crop-Recommendation-System-Using-Machine-Learning-main"

Write-Host "Server will run at: http://127.0.0.1:5000" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python app.py

Write-Host ""
Write-Host "Server stopped." -ForegroundColor Yellow
