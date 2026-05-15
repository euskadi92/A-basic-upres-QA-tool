@echo off
setlocal

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

python -m PyInstaller --onefile --windowed --name "Upres-QA-Tool" main.py

if exist dist\Upres-QA-Tool.exe (
    echo.
    echo Build successful!
    echo Executable: dist\Upres-QA-Tool.exe
) else (
    echo.
    echo Build failed. Check error messages above.
)

pause
