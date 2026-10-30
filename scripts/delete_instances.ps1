# ResearchSphere - Delete All Cloud Instances (1-Click)
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   ResearchSphere: Terminating All Cloud Instances (1-Click)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path "$scriptDir\.."

python scripts\delete_instances.py
