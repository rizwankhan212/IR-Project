@echo off
title Terminate ResearchSphere AWS Resources
echo ========================================================
echo   ResearchSphere - Terminate All Cloud AWS Resources
echo ========================================================
echo.
python "%~dp0terminate_all_resources.py"
echo.
pause
