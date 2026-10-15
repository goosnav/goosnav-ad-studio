@echo off
rem The Ad Studio harness runs on Linux/macOS. On Windows it runs inside WSL, which needs
rem python3, the codex/claude CLIs, Blender and FFmpeg installed in the WSL distribution.
cd /d "%~dp0"
wsl ./"Start Ad Studio.sh" --no-browser %*
if errorlevel 1 echo WSL is required: https://learn.microsoft.com/windows/wsl/install
pause
