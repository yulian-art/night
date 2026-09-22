@echo off
setlocal
if not defined STAR_UE_ROOT set "STAR_UE_ROOT=D:\UE\UE_5.8"
start "" "%STAR_UE_ROOT%\Engine\Binaries\Win64\UnrealEditor.exe" "%~dp0StarJourney.uproject" -NoSplash
