@echo off
title ResearchSphere - Delete All Cloud Instances (1-Click)
cd /d "%~dp0\.."

echo ======================================================================
echo    ResearchSphere: Terminating All Cloud Instances (1-Click)
echo ======================================================================
echo.

python scripts\delete_instances.py

echo.
echo ======================================================================
echo Execution finished. Press any key to close this window.
pause >nul
