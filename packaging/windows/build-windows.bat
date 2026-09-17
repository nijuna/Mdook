@echo off
REM build-windows.bat - Builds standalone Mdook Windows executable using PyInstaller

echo ========================================================
echo Building Mdook Windows Standalone Executable
echo ========================================================

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    exit /b 1
)

REM Sync dependencies with dev packages
echo Syncing dependencies...
pip install -e .[dev]
if %errorlevel% neq 0 (
    echo Error installing dependencies.
    exit /b 1
)

REM Run PyInstaller using mdook.spec
echo Running PyInstaller...
pyinstaller --clean -y mdook.spec
if %errorlevel% neq 0 (
    echo Error: PyInstaller build failed.
    exit /b 1
)

echo.
echo Build complete. Executable generated at: dist\mdook.exe
echo ========================================================
