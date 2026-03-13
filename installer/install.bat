@echo off
setlocal EnableDelayedExpansion
title StockFlow Installer
color 0A

echo.
echo  ================================================
echo   StockFlow - Installer for Windows
echo  ================================================
echo.

:: ── Detect if update or fresh install ────────────────────────────────────────
set "INSTALL_DIR=%USERPROFILE%\StockFlow"
set "IS_UPDATE=false"

if exist "%INSTALL_DIR%\.env" (
    set "IS_UPDATE=true"
    echo  [INFO] Existing installation detected. Running UPDATE...
) else (
    echo  [INFO] No existing installation found. Running FRESH INSTALL...
)

:: ── Check internet ────────────────────────────────────────────────────────────
echo.
echo  [1/6] Checking internet connection...
ping -n 1 github.com >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] No internet connection detected.
    echo         StockFlow needs internet once to download its files.
    echo         Please connect and try again.
    pause
    exit /b 1
)
echo  [OK] Internet connection available.

:: ── Check/Install Python ─────────────────────────────────────────────────────
echo.
echo  [2/6] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Python not found. Downloading Python 3.11...
    curl -o "%TEMP%\python_installer.exe" "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    echo  [INFO] Installing Python silently...
    "%TEMP%\python_installer.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    del "%TEMP%\python_installer.exe"
    :: Refresh PATH
    call refreshenv >nul 2>&1
    echo  [OK] Python installed.
) else (
    echo  [OK] Python already installed.
)

:: ── Check/Install MongoDB ─────────────────────────────────────────────────────
echo.
echo  [3/6] Checking MongoDB...
set "MONGO_DIR=%USERPROFILE%\mongodb"
set "MONGOD=%MONGO_DIR%\bin\mongod.exe"

if not exist "%MONGOD%" (
    echo  [INFO] MongoDB not found. Downloading MongoDB 7.0...
    curl -L -o "%TEMP%\mongodb.zip" "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-7.0.11.zip"
    echo  [INFO] Extracting MongoDB...
    powershell -Command "Expand-Archive -Path '%TEMP%\mongodb.zip' -DestinationPath '%TEMP%\mongoextract' -Force"
    :: Find extracted folder and move it
    for /d %%i in ("%TEMP%\mongoextract\mongodb-*") do (
        xcopy "%%i" "%MONGO_DIR%" /E /I /Q >nul
    )
    del "%TEMP%\mongodb.zip"
    rd /s /q "%TEMP%\mongoextract" >nul 2>&1
    :: Create data directory
    mkdir "%USERPROFILE%\StockFlow-data\db" >nul 2>&1
    echo  [OK] MongoDB installed.
) else (
    echo  [OK] MongoDB already installed.
)

:: ── Clone or update StockFlow ─────────────────────────────────────────────────
echo.
echo  [4/6] Getting StockFlow code...

if "%IS_UPDATE%"=="true" (
    echo  [INFO] Pulling latest updates from GitHub...
    cd /d "%INSTALL_DIR%"
    git pull origin main
    echo  [OK] StockFlow updated.
) else (
    echo  [INFO] Cloning StockFlow from GitHub...
    git clone https://github.com/VINN5/StockFlow.git "%INSTALL_DIR%"
    echo  [OK] StockFlow downloaded.
)

:: ── Install Python dependencies ───────────────────────────────────────────────
echo.
echo  [5/6] Installing dependencies...
cd /d "%INSTALL_DIR%"
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
echo  [OK] Dependencies installed.

:: ── Create .env file (fresh install only) ────────────────────────────────────
if "%IS_UPDATE%"=="false" (
    echo.
    echo  [6/6] Creating configuration...

    :: Generate a random secret key
    for /f %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set "SECRET_KEY=%%i"

    (
        echo SECRET_KEY=!SECRET_KEY!
        echo MONGODB_URI=mongodb://localhost:27017/stockflow
        echo MPESA_ENV=sandbox
        echo AT_USERNAME=sandbox
    ) > "%INSTALL_DIR%\.env"

    echo  [OK] Configuration created.
) else (
    echo.
    echo  [6/6] Keeping existing configuration ^(update^).
    echo  [OK] .env preserved.
)

:: ── Seed sample data (fresh install only) ────────────────────────────────────
if "%IS_UPDATE%"=="false" (
    echo.
    echo  [INFO] Starting MongoDB to seed sample data...
    mkdir "%USERPROFILE%\StockFlow-data\db" >nul 2>&1
    start /B "" "%MONGOD%" --dbpath "%USERPROFILE%\StockFlow-data\db" --logpath "%USERPROFILE%\StockFlow-data\mongod.log" --quiet
    timeout /t 4 >nul
    python "%INSTALL_DIR%\installer\seed.py"
    echo  [OK] Sample data loaded.
)

:: ── Create startup script ─────────────────────────────────────────────────────
(
    echo @echo off
    echo title StockFlow
    echo echo Starting StockFlow...
    echo start /B "" "%MONGOD%" --dbpath "%USERPROFILE%\StockFlow-data\db" --logpath "%USERPROFILE%\StockFlow-data\mongod.log" --quiet
    echo timeout /t 3 ^>nul
    echo start "" "http://localhost:5000"
    echo cd /d "%INSTALL_DIR%"
    echo python -m backend.app
) > "%USERPROFILE%\Desktop\StockFlow.bat"

:: ── Create uninstaller ────────────────────────────────────────────────────────
copy "%INSTALL_DIR%\installer\uninstall.bat" "%INSTALL_DIR%\Uninstall StockFlow.bat" >nul 2>&1

echo.
echo  ================================================
if "%IS_UPDATE%"=="true" (
    echo   StockFlow updated successfully!
) else (
    echo   StockFlow installed successfully!
)
echo  ================================================
echo.
echo   A shortcut "StockFlow.bat" has been placed
echo   on your Desktop. Double-click it to start.
echo.
echo   StockFlow will open at: http://localhost:5000
echo.
pause

:: ── Ask to launch now ─────────────────────────────────────────────────────────
set /p LAUNCH="Launch StockFlow now? (y/n): "
if /i "%LAUNCH%"=="y" (
    call "%USERPROFILE%\Desktop\StockFlow.bat"
)