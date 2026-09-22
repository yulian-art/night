@echo off
chcp 65001 >nul 2>&1
setlocal EnableExtensions
REM Batch script for generating Blender assets.

echo ========================================
echo  StarJourney Asset Generator
echo ========================================
echo.

REM Run from the folder that holds this script so the relative .py paths resolve.
cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM Locate blender.exe.
REM Priority: BLENDER_PATH env var - system PATH - usual install locations.
REM Never quote a bare command name like "blender": cmd then searches only the
REM current directory, ignores PATH, and fails with 9009.
REM ---------------------------------------------------------------------------
if not defined BLENDER_PATH (
    for %%B in (blender.exe) do set "BLENDER_PATH=%%~$PATH:B"
)
if defined BLENDER_PATH goto :blender_ready

if exist "%ProgramFiles%\Blender Foundation" (
    for /d %%D in ("%ProgramFiles%\Blender Foundation\*") do (
        if not defined BLENDER_PATH if exist "%%~fD\blender.exe" set "BLENDER_PATH=%%~fD\blender.exe"
    )
)
if defined BLENDER_PATH goto :blender_ready

if exist "D:\blender\blender.exe" set "BLENDER_PATH=D:\blender\blender.exe"
if defined BLENDER_PATH goto :blender_ready

echo [ERROR] Blender command not found.
echo.
echo Searched:
echo   - the BLENDER_PATH environment variable
echo   - blender.exe on the system PATH
echo   - %ProgramFiles%\Blender Foundation\
echo   - D:\blender\blender.exe
echo.
echo Set BLENDER_PATH once and re-run, for example:
echo   setx BLENDER_PATH "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
echo.
pause
exit /b 1

:blender_ready
echo [INFO] Blender path: %BLENDER_PATH%
"%BLENDER_PATH%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Cannot run "%BLENDER_PATH%"
    pause
    exit /b 1
)

call :run_step "wind_post_assets.py" "Step 1/2: Generating Wind Post Assets"
if errorlevel 1 exit /b 1

echo.
echo.

call :run_step "cloud_whale_assets.py" "Step 2/2: Generating Cloud Whale Assets"
if errorlevel 1 exit /b 1

echo ========================================
echo  All Assets Generated Successfully!
echo ========================================
echo.
echo Output directories:
echo   D:\UE\Projects\StarJourney\Content\StarJourney\Models\WindPost
echo   D:\UE\Projects\StarJourney\Content\StarJourney\Models\CloudWhale
echo.
echo Next steps:
echo   1. Open UE Editor
echo   2. Import FBX files in Content Browser
echo   3. Refer to SCENE_DESIGN.md for material creation
echo.

pause
exit /b 0

REM ---------------------------------------------------------------------------
REM Usage: call :run_step wind_post_assets.py "Friendly name"
REM ---------------------------------------------------------------------------
:run_step
set "STEP_NAME=%~2"
echo ========================================
echo  %STEP_NAME%
echo ========================================
echo.
"%BLENDER_PATH%" --background --python "%~1"
if errorlevel 1 goto :run_step_failed
echo.
echo [SUCCESS] %STEP_NAME%
echo.
exit /b 0

:run_step_failed
echo.
echo [ERROR] %STEP_NAME% failed.
pause
exit /b 1