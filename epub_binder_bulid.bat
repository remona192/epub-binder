@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "SCRIPT=epub_binder4.3.4.py"
set "VENV=.venv"
set "EXE_NAME=EpubBinder5.1.0"
set "ICON=config\icon\app_icon.ico"

cd /d "%~dp0"

echo.
echo ==========================================
echo   EpubBinder Build Script
echo ==========================================
echo.

if not exist "%SCRIPT%" (
    echo ERROR: %SCRIPT% not found
    pause
    exit /b 1
)

:: --- 1. Create venv ---
if not exist "%VENV%\Scripts\activate.bat" (
    echo [1/6] Creating venv...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo ERROR: venv creation failed
        pause
        exit /b 1
    )
    echo [1/6] Done
) else (
    echo [1/6] Venv already exists - reusing
)

:: --- 2. Activate venv ---
call "%VENV%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: venv activation failed
    pause
    exit /b 1
)
echo [2/6] Venv activated

:: --- 3. Check/install packages ---
echo [3/6] Checking packages...
python -c "import PyQt6, PIL, numpy, py7zr, PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo      Missing packages detected - installing once...
    python -m pip install --upgrade pip --quiet
    python -m pip install pyqt6 pyinstaller pillow numpy py7zr --quiet
    if errorlevel 1 (
        echo ERROR: pip install failed
        pause
        exit /b 1
    )
) else (
    echo      Packages already installed - skipping pip install
)
echo [3/6] Done

:: --- 4. Detect icon and UPX ---
echo [4/6] Detecting icon and UPX...
if exist "%ICON%" (
    set "ICON_FLAG=--icon=%ICON%"
    set "ICON_DATA_FLAG=--add-data=%ICON%;config/icon"
    echo      Icon: %ICON%
) else (
    set "ICON_FLAG="
    set "ICON_DATA_FLAG="
    echo      Icon: not found - building without icon
)

set "UPX_FLAG="
if exist "upx.exe" (
    set "UPX_FLAG=--upx-dir=%CD%"
    echo      UPX: %CD%\upx.exe
) else if exist "tools\upx\upx.exe" (
    set "UPX_FLAG=--upx-dir=%CD%\tools\upx"
    echo      UPX: %CD%\tools\upx\upx.exe
) else (
    for /f "delims=" %%I in ('where upx.exe 2^>nul') do (
        if not defined UPX_FLAG (
            set "UPX_FLAG=--upx-dir=%%~dpI"
            echo      UPX: %%I
        )
    )
)

if not defined UPX_FLAG (
    echo      UPX: not found - building without UPX compression
)

:: --- 5. Clean previous build ---
echo [5/6] Cleaning old build...
if exist "dist\%EXE_NAME%.exe" del /f /q "dist\%EXE_NAME%.exe"
if exist "build" rmdir /s /q "build"
if exist "%EXE_NAME%.spec" del /f /q "%EXE_NAME%.spec"

:: --- 6. Build ---
echo [6/6] Building... (1-2 min)
echo.

python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "%EXE_NAME%" ^
    %ICON_FLAG% ^
    %ICON_DATA_FLAG% ^
    %UPX_FLAG% ^
    --hidden-import=PyQt6 ^
    --hidden-import=PyQt6.QtCore ^
    --hidden-import=PyQt6.QtGui ^
    --hidden-import=PyQt6.QtWidgets ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=numpy ^
    --hidden-import=py7zr ^
    --hidden-import=epub_binder_app ^
    --hidden-import=epub_binder_app.settings ^
    --hidden-import=epub_binder_app.workers ^
    --hidden-import=epub_binder_app.ui ^
    --hidden-import=epub_binder_app.ui.widgets ^
    --hidden-import=epub_binder_app.ui.dialogs ^
    --hidden-import=epub_binder_app.ui.helpers ^
    --hidden-import=epub_binder_app.ui.style ^
    --hidden-import=epub_binder_app.ui.main_window ^
    --hidden-import=epub_binder_core ^
    --hidden-import=epub_binder_core.title_parser ^
    --hidden-import=epub_binder_core.title_metadata ^
    --hidden-import=epub_binder_core.epub_io ^
    --hidden-import=epub_binder_core.naver_series ^
    "%SCRIPT%"

if errorlevel 1 (
    echo.
    echo ERROR: Build failed
    pause
    exit /b 1
)

if not exist "dist\%EXE_NAME%.exe" (
    echo.
    echo ERROR: dist\%EXE_NAME%.exe was not created
    pause
    exit /b 1
)

copy /y "dist\%EXE_NAME%.exe" "%EXE_NAME%.exe" >nul
if errorlevel 1 (
    echo.
    echo ERROR: failed to copy dist\%EXE_NAME%.exe to %EXE_NAME%.exe
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   Build complete!
echo   dist\%EXE_NAME%.exe
echo   %EXE_NAME%.exe
echo ==========================================
echo.
pause
