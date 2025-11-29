@echo off
REM WhatsApp Support Bot - Resume Project Command
REM Usage: resume.bat [options]

echo Starting WhatsApp Support Bot Project Resume...

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Run the resume script with any passed arguments
python resume_project.py %*

pause