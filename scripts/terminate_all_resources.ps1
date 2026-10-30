# ========================================================
# ResearchSphere - Terminate All Cloud AWS Resources
# ========================================================
Write-Host "========================================================" -ForegroundColor Yellow
Write-Host "  ResearchSphere - Terminate All Cloud AWS Resources" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Yellow
Write-Host ""

$scriptPath = Join-Path $PSScriptRoot "terminate_all_resources.py"
python $scriptPath
Write-Host ""
Write-Host "Done. Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
