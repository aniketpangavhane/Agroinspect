param(
    [switch]$Monitoring
)

$ErrorActionPreference = 'Stop'
$modelPath = Join-Path $PSScriptRoot 'artifacts\maharashtra_crop_suitability_v1\model.joblib'

if (-not (Test-Path -LiteralPath $modelPath -PathType Leaf)) {
    throw "Trained model not found at '$modelPath'. Run crop-advisor-train first."
}

$env:CROP_ADVISOR_MODEL_SHA256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $modelPath).Hash.ToLowerInvariant()
Push-Location -LiteralPath $PSScriptRoot
try {
    if ($Monitoring) {
        docker compose --profile monitoring up --build
    } else {
        docker compose up --build
    }
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose exited with code $LASTEXITCODE. Check that Docker Desktop is installed and running."
    }
} finally {
    Pop-Location
    Remove-Item Env:CROP_ADVISOR_MODEL_SHA256 -ErrorAction SilentlyContinue
}
